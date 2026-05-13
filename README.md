# Home Assistant: Bose SoundTouch Bridge

A Home Assistant add-on that maps **physical preset buttons** on Bose
SoundTouch speakers to **Music Assistant** playback — after the
**Bose cloud retirement (2026)** broke TuneIn presets, the SoundTouch
app, and most cloud sources.

Press a preset button on the speaker and it plays the configured radio
station or media via Music Assistant. Presets without a media ID simply
fire a Home Assistant event for custom automations.

See [`bose_bridge/README.md`](bose_bridge/README.md) for full docs,
configuration options, and example automations.

## Features

- **Direct Music Assistant playback** — configure a `media_id` per
  preset button (e.g. `library://radio/6`)
- **Event-only mode** — presets without a `media_id` fire
  `bose_soundtouch_preset_pressed` events for custom automations
- **Auto-discovery** — speaker (SSDP) and Music Assistant entity are
  detected automatically if not configured
- **Auto-resolve preset names** — station names are read from Music
  Assistant and shown on the speaker's display
- **Preset sync** — empty slots are populated on startup so all 6
  buttons work out of the box

## Install

1. **Settings → Add-ons → App Store → ⋮ → Repositories**
2. Paste this repository's URL and click **Add**
3. The "Bose SoundTouch Bridge" add-on appears in the App Store —
   **Install** → **Start**.

[![Open your Home Assistant instance and show the add add-on repository dialog with a specific repository URL pre-filled.](https://my.home-assistant.io/badges/supervisor_add_addon_repository.svg)](https://my.home-assistant.io/redirect/supervisor_add_addon_repository/?repository_url=https%3A%2F%2Fgithub.com%2Fsebastianaberle4324%2Fhomeassistant-bose-soundtouch-bridge)

## What works / what doesn't

| Source | Status after Bose cloud retirement | This add-on |
|---|---|---|
| Spotify Connect | ✅ still works | not needed |
| AUX in | ✅ still works | not needed |
| TuneIn presets | ❌ broken | ✅ fires HA event |
| Physical preset buttons | ❌ mostly dead | ✅ plays via Music Assistant or fires HA event |
| Any media via Music Assistant | — | ✅ configured per preset button |

## License

MIT — see [`LICENSE`](LICENSE).
