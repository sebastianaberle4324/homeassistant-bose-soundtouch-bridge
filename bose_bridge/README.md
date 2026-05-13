# Bose SoundTouch Bridge

Fires **Home Assistant events** when physical preset buttons are pressed
on Bose SoundTouch speakers — after the **Bose cloud retirement (2026)**.

## What this does

When you press one of the six preset buttons on the speaker, this add-on
fires a `bose_soundtouch_preset_pressed` event in Home Assistant. You
can then use automations to react — e.g. play music via Music Assistant,
trigger scenes, or anything else HA can do.

This gives you full flexibility: instead of being limited to plain HTTP
streams, you can play commercial streaming services (Spotify, Tidal,
etc.) through Music Assistant or any other integration.

## Event format

```yaml
event_type: bose_soundtouch_preset_pressed
data:
  preset: 3          # 1–6
  device_id: "A0B1C2D3E4F5"
  device_name: "Living Room"
  speaker_host: "192.168.1.42"
```

## Example automation

```yaml
automation:
  - alias: "Bose Preset 1 → Play Radio via Music Assistant"
    trigger:
      - platform: event
        event_type: bose_soundtouch_preset_pressed
        event_data:
          preset: 1
    action:
      - action: mass.play_media
        data:
          media_id: "Radio 1"
          media_type: radio
        target:
          entity_id: media_player.bose_soundtouch

  - alias: "Bose Preset 2 → Play Spotify playlist"
    trigger:
      - platform: event
        event_type: bose_soundtouch_preset_pressed
        event_data:
          preset: 2
    action:
      - action: mass.play_media
        data:
          media_id: "spotify://playlist/37i9dQZF1DXcBWIGoYBM5M"
          media_type: playlist
        target:
          entity_id: media_player.bose_soundtouch
```

## Requirements

- A Bose SoundTouch speaker (any model) on the same network as
  Home Assistant
- Home Assistant OS or Supervised

## Setup

1. Install this add-on (see *Install* below).
2. Open the add-on → **Configuration**.
3. Either leave `bose_host` blank to auto-discover the speaker via SSDP,
   or set it to the speaker's IP address (e.g. `192.168.1.42`).
4. Set `placeholder_url` to any valid HTTP stream URL (e.g.
   `http://icecast.vrtcdn.be/radio1-high.mp3`). This is used to populate
   empty preset slots on the speaker so all 6 buttons fire events.
   Leave blank if all presets are already set.
5. Leave `sync_presets_on_startup` enabled (default). On startup, the
   add-on writes a placeholder into any empty preset slot via the
   speaker's `/storePreset` API — instant, no audio blips.
6. **Save** → **Start** → check the **Log** tab; it should print:
   ```
   [info] speaker: Living Room (SoundTouch 30) — id A0B1C2D3E4F5
   [sync] 4 empty slot(s) need writing: [1, 2, 3, 4]
   [sync]  ✓ preset 1 stored
   ...
   [ws] connected to ws://192.168.1.42:8080
   ```
7. Press a preset button → check **Developer Tools → Events** for
   `bose_soundtouch_preset_pressed`.
8. Create automations that react to the event (see example above).

## Configuration

| Option | Default | Description |
|---|---|---|
| `bose_host` | `""` | Speaker IP. Leave blank for SSDP auto-discovery. |
| `sync_presets_on_startup` | `true` | Write placeholders into empty preset slots so all 6 buttons fire events. |
| `placeholder_url` | `""` | Any HTTP stream URL used as placeholder for empty slots. |

## Install

1. In Home Assistant: **Settings → Add-ons → App Store → ⋮ → Repositories**
2. Add this repository's GitHub URL
3. The "Bose SoundTouch Bridge" add-on appears in the store — click
   **Install** → **Start**

## How it works

- Bose's stock firmware exposes a WebSocket notification stream on
  `ws://<speaker>:8080` (subprotocol `gabbo`). It emits an event for
  every preset button press:
  `<nowSelectionUpdated><preset id="N">…`
- The add-on catches these events and fires a Home Assistant event via
  the Supervisor REST API.
- On startup, empty preset slots are populated via the speaker's
  `/storePreset` API (unique placeholder URL per slot to avoid
  deduplication).
- No Bose cloud, no UPnP, no MQTT — just HTTP API + WebSocket + HA
  events.

## Limitations

- One bridge per speaker. Multi-speaker support is on the roadmap.

## License

MIT
