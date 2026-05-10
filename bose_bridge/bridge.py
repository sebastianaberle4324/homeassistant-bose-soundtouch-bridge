#!/usr/bin/env python3
"""
Bose SoundTouch preset-to-radio bridge.

- Listens to the speaker's WebSocket. When a preset button is pressed,
  pushes the configured stream URL via UPnP SetAVTransportURI + Play
  with DIDL-Lite metadata so the station name and logo show up on the
  speaker.
- Looks up station name + favicon from radio-browser.info at startup
  (cached) for each configured URL.
- Connects to the Supervisor-provided MQTT broker and publishes Home
  Assistant MQTT-discovery configs so each preset appears as a
  `button.bose_preset_N` entity. Triggering the entity (UI / automation
  / script) plays the same preset over UPnP.
"""

import html
import json
import os
import re
import socket
import threading
import time
import urllib.parse
import urllib.request

import paho.mqtt.client as mqtt
import upnpclient
import websocket

OPTIONS_PATH = "/data/options.json"
SUPERVISOR_TOKEN = os.environ.get("SUPERVISOR_TOKEN")
SUPERVISOR_URL = "http://supervisor"
RADIO_BROWSER_BASES = [
    "https://de1.api.radio-browser.info",
    "https://nl1.api.radio-browser.info",
    "https://at1.api.radio-browser.info",
]
PRESET_RE = re.compile(r'<nowSelectionUpdated>\s*<preset id="(\d+)"')
SSDP_ADDR = ("239.255.255.250", 1900)
SSDP_TARGET = "urn:schemas-upnp-org:device:MediaRenderer:1"


# ---------- config ---------------------------------------------------------


def load_options() -> dict:
    if not os.path.exists(OPTIONS_PATH):
        print(f"[cfg] {OPTIONS_PATH} missing — running with empty config")
        return {}
    with open(OPTIONS_PATH) as f:
        return json.load(f)


# ---------- Bose discovery -------------------------------------------------


def discover_soundtouch() -> str | None:
    msg = (
        "M-SEARCH * HTTP/1.1\r\n"
        f"HOST: {SSDP_ADDR[0]}:{SSDP_ADDR[1]}\r\n"
        'MAN: "ssdp:discover"\r\n'
        "MX: 2\r\n"
        f"ST: {SSDP_TARGET}\r\n\r\n"
    ).encode()
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.settimeout(3)
    s.sendto(msg, SSDP_ADDR)
    try:
        while True:
            data, addr = s.recvfrom(2048)
            text = data.decode(errors="ignore")
            loc = next(
                (l.split(": ", 1)[1].strip() for l in text.split("\r\n") if l.lower().startswith("location:")),
                None,
            )
            if not loc:
                continue
            try:
                desc = urllib.request.urlopen(loc, timeout=3).read().decode()
            except Exception:
                continue
            if "SoundTouch" in desc or "Bose" in desc:
                return addr[0]
    except socket.timeout:
        return None
    finally:
        s.close()


def fetch_speaker_info(host: str) -> tuple[str, str, str]:
    """Return (device_id, friendly_name, model) by hitting /info."""
    with urllib.request.urlopen(f"http://{host}:8090/info", timeout=5) as r:
        info = r.read().decode()
    device_id = re.search(r'deviceID="([0-9A-F]+)"', info).group(1)
    name = re.search(r"<name>([^<]+)</name>", info)
    model = re.search(r"<type>([^<]+)</type>", info)
    return device_id, (name.group(1) if name else "SoundTouch"), (model.group(1) if model else "SoundTouch")


def get_av_service(host: str, device_id: str):
    desc_url = f"http://{host}:8091/XD/BO5EBO5E-F00D-F00D-FEED-{device_id}.xml"
    print(f"[upnp] description: {desc_url}")
    d = upnpclient.Device(desc_url)
    return next(s for s in d.services if "AVTransport" in s.service_id)


# ---------- radio-browser.info ---------------------------------------------


def lookup_station(url: str) -> dict:
    """Return {'name': str, 'favicon': str} or empty dict if not found."""
    body = urllib.parse.urlencode({"url": url}).encode()
    for base in RADIO_BROWSER_BASES:
        try:
            req = urllib.request.Request(
                f"{base}/json/stations/byurl",
                data=body,
                headers={
                    "Content-Type": "application/x-www-form-urlencoded",
                    "User-Agent": "homeassistant-bose-soundtouch-bridge/1.3.0",
                },
            )
            with urllib.request.urlopen(req, timeout=4) as r:
                stations = json.load(r)
            if stations:
                s = stations[0]
                return {"name": s.get("name", ""), "favicon": s.get("favicon", "")}
            return {}
        except Exception as e:
            print(f"[meta] {base} failed: {e}")
            continue
    return {}


def build_didl(url: str, meta: dict) -> str:
    title = html.escape(meta.get("name") or "Internet Radio")
    art = html.escape(meta.get("favicon") or "")
    art_tag = f"<upnp:albumArtURI>{art}</upnp:albumArtURI>" if art else ""
    return (
        '<DIDL-Lite xmlns="urn:schemas-upnp-org:metadata-1-0/DIDL-Lite/" '
        'xmlns:dc="http://purl.org/dc/elements/1.1/" '
        'xmlns:upnp="urn:schemas-upnp-org:metadata-1-0/upnp/">'
        '<item id="0" parentID="-1" restricted="1">'
        f"<dc:title>{title}</dc:title>"
        "<upnp:class>object.item.audioItem.audioBroadcast</upnp:class>"
        f"{art_tag}"
        f'<res protocolInfo="http-get:*:audio/mpeg:*">{html.escape(url)}</res>'
        "</item></DIDL-Lite>"
    )


# ---------- MQTT -----------------------------------------------------------


def fetch_mqtt_creds() -> dict | None:
    if not SUPERVISOR_TOKEN:
        return None
    try:
        req = urllib.request.Request(
            f"{SUPERVISOR_URL}/services/mqtt",
            headers={"Authorization": f"Bearer {SUPERVISOR_TOKEN}"},
        )
        with urllib.request.urlopen(req, timeout=5) as r:
            return json.load(r).get("data")
    except Exception as e:
        print(f"[mqtt] cannot fetch creds: {e}")
        return None


def publish_discovery(client: mqtt.Client, device_id: str, friendly: str, model: str, presets: dict):
    """Publish Home Assistant MQTT-discovery configs for the 6 preset buttons."""
    device = {
        "identifiers": [f"bose_soundtouch_{device_id}"],
        "name": f"Bose {friendly}",
        "manufacturer": "Bose",
        "model": model,
    }
    cmd_base = f"bose_bridge/{device_id}/preset"
    for n in range(1, 7):
        meta = presets.get(n, {})
        url = meta.get("url", "")
        label = meta.get("name") or (f"Preset {n}" if not url else f"Preset {n}")
        unique = f"bose_{device_id}_preset_{n}"
        cfg = {
            "name": f"Preset {n}: {label}" if url else f"Preset {n}",
            "unique_id": unique,
            "object_id": unique,
            "command_topic": f"{cmd_base}/{n}/command",
            "icon": "mdi:radio",
            "device": device,
            "availability_topic": f"bose_bridge/{device_id}/status",
            "payload_available": "online",
            "payload_not_available": "offline",
        }
        topic = f"homeassistant/button/{unique}/config"
        client.publish(topic, json.dumps(cfg), qos=1, retain=True)
    print(f"[mqtt] published HA discovery for 6 buttons (device {device_id})")


# ---------- main loop ------------------------------------------------------


def main():
    cfg = load_options()
    host = (cfg.get("bose_host") or "").strip()
    if not host:
        print("[cfg] bose_host blank — auto-discovering via SSDP...")
        host = discover_soundtouch()
        if not host:
            raise SystemExit(
                "no SoundTouch found on the network. Set bose_host in the addon "
                "Configuration tab and restart."
            )
        print(f"[cfg] discovered SoundTouch at {host}")

    device_id, friendly, model = fetch_speaker_info(host)
    print(f"[upnp] speaker: {friendly} ({model}) — id {device_id}")

    presets = {}
    for n in range(1, 7):
        url = (cfg.get(f"preset_{n}_url") or "").strip()
        if not url:
            continue
        meta = lookup_station(url)
        presets[n] = {"url": url, **meta}
        print(f"[meta] preset {n}: {url} -> {meta or '(no metadata found)'}")

    av = get_av_service(host, device_id)

    def play_preset(n: int):
        entry = presets.get(n)
        if not entry:
            print(f"[play] preset {n} not configured")
            return
        url = entry["url"]
        didl = build_didl(url, entry)
        print(f"[play] preset {n} -> {url}")
        try:
            av.SetAVTransportURI(InstanceID=0, CurrentURI=url, CurrentURIMetaData=didl)
            av.Play(InstanceID=0, Speed="1")
        except Exception as e:
            print(f"[play] failed: {e}")

    # MQTT --------------------------------------------------------------
    mqtt_client = None
    creds = fetch_mqtt_creds()
    status_topic = f"bose_bridge/{device_id}/status"
    if creds:
        client = mqtt.Client(
            mqtt.CallbackAPIVersion.VERSION2,
            client_id=f"bose_bridge_{device_id}",
        )
        if creds.get("username"):
            client.username_pw_set(creds["username"], creds.get("password", ""))
        client.will_set(status_topic, "offline", qos=1, retain=True)

        def on_connect(c, _u, _f, rc, _p=None):
            print(f"[mqtt] connected (rc={rc})")
            publish_discovery(c, device_id, friendly, model, presets)
            c.publish(status_topic, "online", qos=1, retain=True)
            c.subscribe(f"bose_bridge/{device_id}/preset/+/command")

        def on_message(_c, _u, msg):
            m = re.search(r"/preset/(\d+)/command$", msg.topic)
            if not m:
                return
            n = int(m.group(1))
            print(f"[mqtt] preset {n} requested via HA")
            play_preset(n)

        client.on_connect = on_connect
        client.on_message = on_message
        try:
            client.connect(creds["host"], int(creds.get("port", 1883)), keepalive=60)
            client.loop_start()
            mqtt_client = client
        except Exception as e:
            print(f"[mqtt] connect failed, continuing without HA control: {e}")
    else:
        print("[mqtt] no Supervisor MQTT credentials — HA buttons disabled")

    # WebSocket loop ----------------------------------------------------
    def on_message(_ws, msg):
        m = PRESET_RE.search(msg)
        if not m:
            return
        n = int(m.group(1))
        if n == 0:
            return
        print(f"[ws] physical preset {n} press")
        play_preset(n)

    def on_open(_ws):
        print(f"[ws] connected to ws://{host}:8080")

    def on_error(_ws, e):
        print(f"[ws] error: {e}")

    def on_close(_ws, code, reason):
        print(f"[ws] closed: {code} {reason}")

    while True:
        ws = websocket.WebSocketApp(
            f"ws://{host}:8080",
            subprotocols=["gabbo"],
            on_open=on_open,
            on_message=on_message,
            on_error=on_error,
            on_close=on_close,
        )
        ws.run_forever(ping_interval=30, ping_timeout=10)
        print("[ws] reconnecting in 5s")
        time.sleep(5)


if __name__ == "__main__":
    main()
