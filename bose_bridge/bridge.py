#!/usr/bin/env python3
"""
Bose SoundTouch preset-to-event bridge.

Listens to the speaker's WebSocket. When a physical preset button is
pressed, fires a Home Assistant event (bose_soundtouch_preset_pressed)
via the Supervisor REST API so automations can react — e.g. to play
music through Music Assistant or any other integration.
"""

import json
import os
import re
import socket
import urllib.request

import websocket

OPTIONS_PATH = "/data/options.json"
SUPERVISOR_TOKEN = os.environ.get("SUPERVISOR_TOKEN")
SUPERVISOR_URL = "http://supervisor"
PRESET_RE = re.compile(r'<nowSelectionUpdated>\s*<preset id="(\d+)"')
SSDP_ADDR = ("239.255.255.250", 1900)
SSDP_TARGET = "urn:schemas-upnp-org:device:MediaRenderer:1"


# ---------- config ---------------------------------------------------------


def load_options() -> dict:
    """Read add-on options from /data/options.json (Supervisor mode)."""
    if os.path.exists(OPTIONS_PATH):
        with open(OPTIONS_PATH) as f:
            return json.load(f)
    return {
        "bose_host": os.environ.get("BOSE_HOST", "").strip(),
        "sync_presets_on_startup": os.environ.get(
            "SYNC_PRESETS_ON_STARTUP", "true").lower() in ("1", "true", "yes", "on"),
        "placeholder_url": os.environ.get("PLACEHOLDER_URL", "").strip(),
    }


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


# ---------- preset sync ----------------------------------------------------


def _get_populated_presets(host: str) -> set[int]:
    """Return set of preset IDs that already have content stored."""
    try:
        with urllib.request.urlopen(f"http://{host}:8090/presets", timeout=5) as r:
            xml = r.read().decode()
    except Exception:
        return set()
    return set(int(m) for m in re.findall(r'<preset id="(\d+)"', xml))


def sync_presets(host: str, placeholder_url: str, preset_names: list[str] | None = None):
    """Ensure all 6 preset slots are populated so physical button presses
    emit WebSocket events. Writes a placeholder via /storePreset to any
    empty slot. Uses unique URLs per slot to avoid deduplication."""
    names = preset_names or []
    populated = _get_populated_presets(host)
    empty = [n for n in range(1, 7) if n not in populated]
    if not empty:
        print("[sync] all 6 preset slots already populated — skipping")
        return
    print(f"[sync] {len(empty)} empty slot(s) need writing: {empty}")
    for n in empty:
        url = f"{placeholder_url}?preset={n}" if "?" not in placeholder_url else f"{placeholder_url}&preset={n}"
        name = names[n - 1] if n - 1 < len(names) else f"Preset {n}"
        body = (
            f'<preset id="{n}">'
            f'<ContentItem source="UPNP" location="{url}" '
            f'sourceAccount="UPnPUserName" isPresetable="true">'
            f'<itemName>{name}</itemName>'
            f'</ContentItem></preset>'
        ).encode()
        req = urllib.request.Request(
            f"http://{host}:8090/storePreset",
            data=body,
            headers={"Content-Type": "application/xml"},
        )
        try:
            urllib.request.urlopen(req, timeout=5).read()
            print(f"[sync]  ✓ preset {n} stored")
        except Exception as e:
            print(f"[sync]  ✗ preset {n} failed: {e}")


# ---------- Home Assistant event -------------------------------------------


def fire_ha_event(preset: int, device_id: str, device_name: str, host: str):
    """Fire a bose_soundtouch_preset_pressed event via the Supervisor API."""
    if not SUPERVISOR_TOKEN:
        print("[ha] SUPERVISOR_TOKEN not set — cannot fire event")
        return
    data = json.dumps({
        "preset": preset,
        "device_id": device_id,
        "device_name": device_name,
        "speaker_host": host,
    }).encode()
    req = urllib.request.Request(
        f"{SUPERVISOR_URL}/core/api/events/bose_soundtouch_preset_pressed",
        data=data,
        headers={
            "Authorization": f"Bearer {SUPERVISOR_TOKEN}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            r.read()
        print(f"[ha] fired bose_soundtouch_preset_pressed (preset={preset})")
    except Exception as e:
        print(f"[ha] failed to fire event: {e}")


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
    print(f"[info] speaker: {friendly} ({model}) — id {device_id}")

    if not SUPERVISOR_TOKEN:
        print("[ha] WARNING: SUPERVISOR_TOKEN not set — events cannot be fired")

    # Preset sync -------------------------------------------------------
    placeholder = (cfg.get("placeholder_url") or "").strip()
    preset_names = cfg.get("preset_names") or []
    if cfg.get("sync_presets_on_startup", True) and placeholder:
        try:
            sync_presets(host, placeholder, preset_names)
        except Exception as e:
            print(f"[sync] failed: {e}")
    elif cfg.get("sync_presets_on_startup", True) and not placeholder:
        print("[sync] sync_presets_on_startup enabled but no placeholder_url set — skipping")
    else:
        print("[sync] preset sync disabled")

    # WebSocket loop ----------------------------------------------------
    def on_message(_ws, msg):
        m = PRESET_RE.search(msg)
        if not m:
            return
        n = int(m.group(1))
        if n == 0:
            return
        print(f"[ws] physical preset {n} press")
        fire_ha_event(n, device_id, friendly, host)

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
