# Bose SoundTouch Bridge

Maps physical **preset buttons** on Bose SoundTouch speakers to
**Music Assistant** playback — after the **Bose cloud retirement (2026)**.

## What this does

When you press one of the six preset buttons on the speaker, this add-on
can do two things (or both):

1. **Play media via Music Assistant** — if you configured a `media_id`
   for that preset (e.g. `library://radio/6`).
2. **Fire a Home Assistant event** (`bose_soundtouch_preset_pressed`) —
   always, so you can add custom automations on top.

Presets without a `media_id` only fire the event, giving you full
flexibility for non-Music-Assistant use cases (scenes, scripts, etc.).

## How it works

- On startup the add-on connects to the speaker's local WebSocket
  (port 8080) and listens for preset button presses.
- Empty preset slots are automatically populated with placeholders so
  all 6 buttons fire events (via the speaker's `/storePreset` API).
- If `media_player_entity` is left blank, the add-on auto-detects your
  Music Assistant media player.
- If a preset has a `media_id` but no `name`, the add-on resolves the
  name from Music Assistant on startup.

## Events

### Preset pressed

```yaml
event_type: bose_soundtouch_preset_pressed
data:
  preset: 3          # 1-6
  device_id: "A0B1C2D3E4F5"
  device_name: "Living Room"
  speaker_host: "192.168.1.42"
```

### Power on / off

```yaml
event_type: bose_soundtouch_power_on   # or bose_soundtouch_power_off
data:
  device_id: "A0B1C2D3E4F5"
  device_name: "Living Room"
  speaker_host: "192.168.1.42"
```

## Setup

1. Install this add-on (see root README for install button).
2. Open the add-on Configuration tab.
3. Set `bose_host` to the speaker's IP, or leave blank for auto-discovery.
   When auto-discovered, the IP is saved to the config automatically —
   clear the field to trigger auto-discovery again.
4. Set `media_player_entity` to your Music Assistant media player
   (e.g. `media_player.soundtouch_20_music_assistant`), or leave blank
   for auto-detection. When auto-detected, the entity is saved to the
   config automatically — clear the field to trigger auto-detection again.
5. Fill in the preset fields — set `preset_N_media_id` for Music
   Assistant playback (e.g. `library://radio/6`), or leave empty for
   event-only. The `preset_N_name` field is shown on the speaker's
   display; leave blank to auto-resolve from Music Assistant.
6. **Save** then **Start** the add-on. Check the **Log** tab:
   ```
   [info] speaker: Living Room (SoundTouch 30) - id A0B1C2D3E4F5
   [ma] auto-detected: media_player.soundtouch_30_music_assistant
   [cfg] preset 1: library://radio/6 (Radio Hamburg)
   [cfg] preset 2: library://radio/9 (N-JOY)
   [cfg] preset 3: (event only)
   [sync] 6 empty slot(s) need writing: [1, 2, 3, 4, 5, 6]
   [ws] connected to ws://192.168.1.42:8080
   ```
7. Press a preset button on the speaker!

## Configuration

| Option | Default | Description |
|---|---|---|
| `bose_host` | `""` | Speaker IP. Auto-discovered via SSDP if blank; saved to config once found. Clear to re-discover. |
| `sync_presets_on_startup` | `true` | Populate empty preset slots so all 6 buttons work. |
| `auto_play_on_power_on` | `true` | Resume last preset when speaker powers on. |
| `media_player_entity` | `""` | Music Assistant entity. Auto-detected if blank (matched by Bose device ID); saved to config once found. Clear to re-detect. |
| `preset_N_media_id` | `""` | MA media ID for preset N (e.g. `library://radio/6`). Leave empty for event-only. |
| `preset_N_name` | `"Preset N"` | Display name on the speaker for preset N. |

## Example automation (event-only preset)

```yaml
automation:
  - alias: "Bose Preset 5 - Toggle lights"
    trigger:
      - platform: event
        event_type: bose_soundtouch_preset_pressed
        event_data:
          preset: 5
    action:
      - action: light.toggle
        target:
          entity_id: light.living_room
```

## Requirements

- A Bose SoundTouch speaker (any model) on the same network as
  Home Assistant
- Home Assistant OS or Supervised
- Music Assistant (optional, for direct playback)

## Install

1. In Home Assistant: **Settings → Add-ons → App Store → ⋮ → Repositories**
2. Add this repository's GitHub URL
3. The "Bose SoundTouch Bridge" add-on appears in the store — click
   **Install** → **Start**

## Limitations

- One bridge per speaker. Multi-speaker support is on the roadmap.

## License

MIT
