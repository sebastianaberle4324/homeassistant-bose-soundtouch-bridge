#!/usr/bin/env python3
"""
Bose SoundTouch preset-to-Music-Assistant bridge.

Listens to the speaker's WebSocket. When a physical preset button is
pressed, plays the configured media via Music Assistant and fires a
Home Assistant event (bose_soundtouch_preset_pressed) for additional
automations.
"""

import json
import os
import re
import socket
import time
import urllib.request

import websocket

OPTIONS_PATH = "/data/options.json"
SUPERVISOR_TOKEN = os.environ.get("SUPERVISOR_TOKEN")
SUPERVISOR_URL = "http://supervisor"
PRESET_RE = re.compile(r'<nowSelectionUpdated>\s*<preset id="(\d+)"')
SSDP_ADDR = ("239.255.255.250", 1900)
SSDP_TARGET = "urn:schemas-upnp-org:device:MediaRenderer:1"
PLACEHOLDER_URL = "http://icecast.vrtcdn.be/radio1-high.mp3"


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
        "media_player_entity": os.environ.get("MEDIA_PLAYER_ENTITY", "").strip(),
        "presets": [],
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


def _preset_name(presets: list[dict], n: int) -> str:
    """Get display name for preset n (1-based), fallback to 'Preset N'."""
    if n - 1 < len(presets):
        name = (presets[n - 1].get("name") or "").strip()
        if name:
            return name
    return f"Preset {n}"


def _preset_media_id(presets: list[dict], n: int) -> str:
    """Get media_id for preset n (1-based), or empty string."""
    if n - 1 < len(presets):
        return (presets[n - 1].get("media_id") or "").strip()
    return ""


def sync_presets(host: str, presets: list[dict]):
    """Ensure all 6 preset slots are populated so physical button presses
    emit WebSocket events. Writes a placeholder via /storePreset to any
    empty slot. Uses unique URLs per slot to avoid deduplication."""
    populated = _get_populated_presets(host)
    empty = [n for n in range(1, 7) if n not in populated]
    if not empty:
        print("[sync] all 6 preset slots already populated — skipping")
        return
    print(f"[sync] {len(empty)} empty slot(s) need writing: {empty}")
    for n in empty:
        url = f"{PLACEHOLDER_URL}?preset={n}"
        name = _preset_name(presets, n)
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
            print(f"[sync]  ✓ preset {n} stored ({name})")
        except Exception as e:
            print(f"[sync]  ✗ preset {n} failed: {e}")


# ---------- Home Assistant API ---------------------------------------------


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


def play_media(entity_id: str, media_id: str):
    """Call music_assistant.play_media via the Supervisor API."""
    if not SUPERVISOR_TOKEN:
        print("[ha] SUPERVISOR_TOKEN not set — cannot call service")
        return
    data = json.dumps({
        "entity_id": entity_id,
        "media_id": media_id,
        "media_type": "radio",
        "enqueue": "replace",
    }).encode()
    req = urllib.request.Request(
        f"{SUPERVISOR_URL}/core/api/services/music_assistant/play_media",
        data=data,
        headers={
            "Authorization": f"Bearer {SUPERVISOR_TOKEN}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            r.read()
        print(f"[ma] playing {media_id} on {entity_id}")
    except Exception as e:
        print(f"[ma] failed to play media: {e}")


def discover_media_player() -> str:
    """Auto-detect a Music Assistant media_player entity via the HA states API.
    Returns the entity_id of the first entity whose platform is
    'music_assistant', or empty string if none found."""
    if not SUPERVISOR_TOKEN:
        return ""
    try:
        req = urllib.request.Request(
            f"{SUPERVISOR_URL}/core/api/states",
            headers={"Authorization": f"Bearer {SUPERVISOR_TOKEN}"},
        )
        with urllib.request.urlopen(req, timeout=10) as r:
            states = json.loads(r.read().decode())
    except Exception as e:
        print(f"[ma] auto-discovery failed: {e}")
        return ""

    ma_entities = [
        s["entity_id"] for s in states
        if s.get("entity_id", "").startswith("media_player.")
        and s.get("attributes", {}).get("mass_player_id")
    ]
    if not ma_entities:
        print("[ma] no Music Assistant media_player entities found")
        return ""
    if len(ma_entities) == 1:
        print(f"[ma] auto-detected: {ma_entities[0]}")
        return ma_entities[0]
    # Multiple found — list them, pick none
    print(f"[ma] found {len(ma_entities)} Music Assistant entities:")
    for e in ma_entities:
        print(f"[ma]   - {e}")
    print("[ma] set media_player_entity in config to pick one")
    return ""


def resolve_preset_names(entity_id: str, presets: list[dict]) -> list[dict]:
    """Resolve missing preset names from Music Assistant. For each preset
    that has a media_id but no name, briefly plays it and reads back the
    station name from the entity state."""
    if not SUPERVISOR_TOKEN or not entity_id:
        return presets

    resolved = [dict(p) for p in presets]
    for i, p in enumerate(resolved):
        media_id = (p.get("media_id") or "").strip()
        name = (p.get("name") or "").strip()
        if media_id and not name:
            try:
                play_media(entity_id, media_id)
                time.sleep(4)
                req = urllib.request.Request(
                    f"{SUPERVISOR_URL}/core/api/states/{entity_id}",
                    headers={"Authorization": f"Bearer {SUPERVISOR_TOKEN}"},
                )
                with urllib.request.urlopen(req, timeout=5) as r:
                    state = json.loads(r.read().decode())
                attrs = state.get("attributes", {})
                station_name = (attrs.get("media_album_name") or
                                attrs.get("media_title") or "").strip()
                if station_name:
                    resolved[i]["name"] = station_name
                    print(f"[ma] preset {i+1}: resolved name → {station_name}")
                else:
                    print(f"[ma] preset {i+1}: could not resolve name for {media_id}")
            except Exception as e:
                print(f"[ma] preset {i+1}: name resolution failed: {e}")

    # Stop playback after resolution
    try:
        stop_data = json.dumps({"entity_id": entity_id}).encode()
        req = urllib.request.Request(
            f"{SUPERVISOR_URL}/core/api/services/media_player/media_stop",
            data=stop_data,
            headers={
                "Authorization": f"Bearer {SUPERVISOR_TOKEN}",
                "Content-Type": "application/json",
            },
        )
        urllib.request.urlopen(req, timeout=5).read()
    except Exception:
        pass

    return resolved


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
        print("[ha] WARNING: SUPERVISOR_TOKEN not set — events and playback disabled")

    entity_id = (cfg.get("media_player_entity") or "").strip()
    presets = cfg.get("presets") or []

    # Auto-detect media_player entity if not configured
    if not entity_id:
        entity_id = discover_media_player()

    # Log preset config
    has_ma_presets = False
    for i, p in enumerate(presets):
        mid = (p.get("media_id") or "").strip()
        name = (p.get("name") or "").strip()
        if mid:
            has_ma_presets = True
            print(f"[cfg] preset {i+1}: {mid}" + (f" ({name})" if name else ""))
        else:
            print(f"[cfg] preset {i+1}: (event only)")

    if entity_id and has_ma_presets:
        print(f"[cfg] media_player: {entity_id}")
        print(f"[cfg] mode: Music Assistant playback + HA events")
    elif has_ma_presets and not entity_id:
        print("[cfg] WARNING: presets have media_id but no media_player_entity — playback disabled")
        print(f"[cfg] mode: HA events only")
    else:
        print(f"[cfg] mode: HA events only (configure presets with media_id for MA playback)")

    # Resolve missing names from Music Assistant
    if entity_id and any(
        (p.get("media_id") or "").strip() and not (p.get("name") or "").strip()
        for p in presets
    ):
        print("[ma] resolving preset names from Music Assistant...")
        presets = resolve_preset_names(entity_id, presets)

    # Preset sync -------------------------------------------------------
    if cfg.get("sync_presets_on_startup", True):
        try:
            sync_presets(host, presets)
        except Exception as e:
            print(f"[sync] failed: {e}")
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

        # Play via Music Assistant if this preset has a media_id
        media_id = _preset_media_id(presets, n)
        if media_id and entity_id:
            play_media(entity_id, media_id)

        # Always fire HA event (for automations / presets without media_id)
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
