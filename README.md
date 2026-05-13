# Home Assistant: Bose SoundTouch Bridge

A Home Assistant add-on that fires **events** when physical preset
buttons are pressed on Bose SoundTouch speakers — after the **Bose cloud
retirement (2026)** broke TuneIn presets, the SoundTouch app, and most
cloud sources.

The add-on listens to the speaker's local WebSocket and fires a
`bose_soundtouch_preset_pressed` event in Home Assistant. Use
automations to react — e.g. play music via Music Assistant, trigger
scenes, or control any media player.

See [`bose_bridge/README.md`](bose_bridge/README.md) for full docs,
event format, and example automations.

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
| Physical preset buttons | ❌ mostly dead | ✅ fires HA event → automation handles playback |
| Any media via Music Assistant | — | ✅ triggered by preset button event |

## License

MIT — see [`LICENSE`](LICENSE).
