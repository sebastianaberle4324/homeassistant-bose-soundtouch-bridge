#!/usr/bin/env python3
"""
Local test script for the Bose SoundTouch Bridge.

Usage:
  # Auto-discover speaker, just print events:
  python test_local.py

  # Specify speaker IP:
  python test_local.py --host 192.168.1.42

  # Sync empty preset slots first (needs a placeholder stream URL):
  python test_local.py --host 192.168.1.42 --sync --placeholder-url http://icecast.vrtcdn.be/radio1-high.mp3

  # Actually fire events to a Home Assistant instance:
  python test_local.py --host 192.168.1.42 --ha-url http://192.168.1.100:8123 --ha-token YOUR_LONG_LIVED_TOKEN

Environment variables work too:
  BOSE_HOST=192.168.1.42 HA_URL=http://... HA_TOKEN=... python test_local.py
"""

import argparse
import json
import os
import re
import socket
import sys
import time
import urllib.request

import websocket

SSDP_ADDR = ("239.255.255.250", 1900)
SSDP_TARGET = "urn:schemas-upnp-org:device:MediaRenderer:1"
PRESET_RE = re.compile(r'<nowSelectionUpdated>\s*<preset id="(\d+)"')

CYAN = "\033[36m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
RED = "\033[31m"
BOLD = "\033[1m"
RESET = "\033[0m"


def discover_soundtouch() -> str | None:
    print(f"{CYAN}[ssdp]{RESET} searching for SoundTouch speakers...")
    msg = (
        "M-SEARCH * HTTP/1.1\r\n"
        f"HOST: {SSDP_ADDR[0]}:{SSDP_ADDR[1]}\r\n"
        'MAN: "ssdp:discover"\r\n'
        "MX: 2\r\n"
        f"ST: {SSDP_TARGET}\r\n\r\n"
    ).encode()
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.settimeout(5)
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
    with urllib.request.urlopen(f"http://{host}:8090/info", timeout=5) as r:
        info = r.read().decode()
    device_id = re.search(r'deviceID="([0-9A-F]+)"', info).group(1)
    name = re.search(r"<name>([^<]+)</name>", info)
    model = re.search(r"<type>([^<]+)</type>", info)
    return device_id, (name.group(1) if name else "SoundTouch"), (model.group(1) if model else "SoundTouch")


def fire_ha_event(ha_url: str, ha_token: str, event_data: dict):
    data = json.dumps(event_data).encode()
    req = urllib.request.Request(
        f"{ha_url}/api/events/bose_soundtouch_preset_pressed",
        data=data,
        headers={
            "Authorization": f"Bearer {ha_token}",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=5) as r:
        r.read()


# ---------- preset sync (optional) -----------------------------------------


def _get_populated_presets(host: str) -> set[int]:
    try:
        with urllib.request.urlopen(f"http://{host}:8090/presets", timeout=5) as r:
            xml = r.read().decode()
    except Exception:
        return set()
    return set(int(m) for m in re.findall(r'<preset id="(\d+)"', xml))


def sync_presets(host: str, placeholder_url: str):
    populated = _get_populated_presets(host)
    empty = [n for n in range(1, 7) if n not in populated]
    if not empty:
        print(f"{GREEN}[sync]{RESET} all 6 preset slots already populated — skipping")
        return
    print(f"{YELLOW}[sync]{RESET} {len(empty)} empty slot(s) need writing: {empty}")
    for n in empty:
        url = f"{placeholder_url}?preset={n}" if "?" not in placeholder_url else f"{placeholder_url}&preset={n}"
        body = (
            f'<preset id="{n}">'
            f'<ContentItem source="UPNP" location="{url}" '
            f'sourceAccount="UPnPUserName" isPresetable="true">'
            f'<itemName>Preset {n}</itemName>'
            f'</ContentItem></preset>'
        ).encode()
        req = urllib.request.Request(
            f"http://{host}:8090/storePreset",
            data=body,
            headers={"Content-Type": "application/xml"},
        )
        try:
            urllib.request.urlopen(req, timeout=5).read()
            print(f"{GREEN}[sync]{RESET}  ✓ preset {n} stored")
        except Exception as e:
            print(f"{RED}[sync]{RESET}  ✗ preset {n} failed: {e}")


# ---------- main -----------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(description="Local test for Bose SoundTouch Bridge")
    parser.add_argument("--host", default=os.environ.get("BOSE_HOST", ""),
                        help="Speaker IP (auto-discover if omitted)")
    parser.add_argument("--ha-url", default=os.environ.get("HA_URL", ""),
                        help="Home Assistant URL, e.g. http://192.168.1.100:8123")
    parser.add_argument("--ha-token", default=os.environ.get("HA_TOKEN", ""),
                        help="Home Assistant long-lived access token")
    parser.add_argument("--sync", action="store_true",
                        help="Write placeholder to empty preset slots so all 6 buttons fire events")
    parser.add_argument("--placeholder-url", default=os.environ.get("PLACEHOLDER_URL", ""),
                        help="Stream URL to write into empty preset slots (required with --sync)")
    args = parser.parse_args()

    host = args.host.strip()
    ha_url = args.ha_url.strip().rstrip("/")
    ha_token = args.ha_token.strip()

    # Discover speaker
    if not host:
        host = discover_soundtouch()
        if not host:
            print(f"{RED}[error]{RESET} No SoundTouch found. Use --host <IP>")
            sys.exit(1)
        print(f"{GREEN}[ssdp]{RESET} found speaker at {BOLD}{host}{RESET}")

    # Fetch speaker info
    try:
        device_id, friendly, model = fetch_speaker_info(host)
    except Exception as e:
        print(f"{RED}[error]{RESET} Cannot reach speaker at {host}:8090 — {e}")
        sys.exit(1)

    print(f"{GREEN}[info]{RESET} speaker: {BOLD}{friendly}{RESET} ({model}) — id {device_id}")

    # Preset sync
    if args.sync:
        placeholder = args.placeholder_url.strip()
        if not placeholder:
            print(f"{RED}[error]{RESET} --sync requires --placeholder-url")
            sys.exit(1)
        print(f"{CYAN}[sync]{RESET} syncing empty preset slots with: {placeholder}")
        try:
            sync_presets(host, placeholder)
        except Exception as e:
            print(f"{RED}[sync]{RESET} failed: {e}")

    if ha_url and ha_token:
        print(f"{GREEN}[ha]{RESET}   will fire events to {BOLD}{ha_url}{RESET}")
    else:
        print(f"{YELLOW}[ha]{RESET}   no --ha-url/--ha-token → dry-run mode (events printed, not fired)")
        print(f"{YELLOW}[ha]{RESET}   to fire real events: --ha-url http://YOUR_HA:8123 --ha-token TOKEN")

    print()
    print(f"{BOLD}Waiting for preset button presses... (Ctrl+C to stop){RESET}")
    print()

    # WebSocket
    def on_message(_ws, msg):
        m = PRESET_RE.search(msg)
        if not m:
            return
        n = int(m.group(1))
        if n == 0:
            return

        event_data = {
            "preset": n,
            "device_id": device_id,
            "device_name": friendly,
            "speaker_host": host,
        }

        print(f"{GREEN}[preset]{RESET} {BOLD}Button {n} pressed!{RESET}")
        print(f"  event_type: bose_soundtouch_preset_pressed")
        print(f"  data: {json.dumps(event_data, indent=6)}")

        if ha_url and ha_token:
            try:
                fire_ha_event(ha_url, ha_token, event_data)
                print(f"  {GREEN}→ event fired to HA ✓{RESET}")
            except Exception as e:
                print(f"  {RED}→ failed to fire event: {e}{RESET}")
        else:
            print(f"  {YELLOW}→ dry-run (not sent to HA){RESET}")
        print()

    def on_open(_ws):
        print(f"{GREEN}[ws]{RESET} connected to ws://{host}:8080")

    def on_error(_ws, e):
        print(f"{RED}[ws]{RESET} error: {e}")

    def on_close(_ws, code, reason):
        print(f"{YELLOW}[ws]{RESET} closed: {code} {reason}")

    while True:
        try:
            ws = websocket.WebSocketApp(
                f"ws://{host}:8080",
                subprotocols=["gabbo"],
                on_open=on_open,
                on_message=on_message,
                on_error=on_error,
                on_close=on_close,
            )
            ws.run_forever(ping_interval=30, ping_timeout=10)
            print(f"{YELLOW}[ws]{RESET} reconnecting in 5s...")
            time.sleep(5)
        except KeyboardInterrupt:
            print(f"\n{CYAN}bye{RESET}")
            sys.exit(0)


if __name__ == "__main__":
    main()
