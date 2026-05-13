# Changelog

## 3.0.0

- **Breaking: Direct Music Assistant integration.** The `preset_names`
  config option is replaced by a `presets` list. Each preset slot can now
  have a `media_id` (e.g. `library://radio/6`) and a `name`.
- **New config options:** `media_player_entity` (the Music Assistant
  media player to target), `presets` (list of `{media_id, name}` per slot).
- **Hybrid mode:** Presets with a `media_id` trigger Music Assistant
  playback **and** fire the `bose_soundtouch_preset_pressed` HA event.
  Presets without a `media_id` only fire the HA event, so automations
  can still handle them.
- **Auto-resolve preset names:** If a preset has a `media_id` but no
  `name`, the addon briefly plays it on startup and reads back the
  station name from the entity state.
- **Removed config options:** `preset_names` (superseded by `presets`).

## 2.1.0

- **Feature:** New `preset_names` config option — set custom display names
  per preset button (e.g. "Radio Hamburg", "N-JOY"). These names appear on
  the SoundTouch speaker's on-device display when a button is pressed.
  Defaults to "Preset 1" … "Preset 6".

## 2.0.1

- **Fix:** Add `hassio_api` and `homeassistant_api` flags to `config.yaml`.
  Without these, the addon did not receive a `SUPERVISOR_TOKEN` and could not
  fire events to Home Assistant (HTTP 401).
- Set default `placeholder_url` to `http://icecast.vrtcdn.be/radio1-high.mp3`.

## 2.0.0

- **Breaking: Event-based architecture.** The add-on no longer pushes
  streams to the speaker via UPnP. Instead, it fires a
  `bose_soundtouch_preset_pressed` Home Assistant event whenever a
  physical preset button is pressed. Use HA automations to react — e.g.
  play music via Music Assistant, trigger scenes, etc.
- **Preset sync via `/storePreset` API.** Empty preset slots are
  populated on startup using the speaker's native `/storePreset`
  endpoint — instant, no audio blips, no UPnP needed. Each slot gets a
  unique placeholder URL (query parameter) to avoid deduplication.
  Configure `placeholder_url` with any HTTP stream URL.
- **Removed:** UPnP stream pushing, MQTT button entities,
  radio-browser.info metadata lookup, standalone Docker support.
- **Removed config options:** `preset_1_url` … `preset_6_url`.
- **New config options:** `placeholder_url` (stream URL for empty
  preset slots), `sync_presets_on_startup` (default `true`).
- **Simplified dependencies:** removed `upnpclient`, `paho-mqtt`,
  `py3-lxml`. Only `websocket-client` remains.
- Event data includes `preset` (1–6), `device_id`, `device_name`, and
  `speaker_host` for use in automations.

## 1.5.0

- **Standalone Docker image** for Home Assistant Container / plain
  Docker / NAS / Pi deployments where the Supervisor isn't available.
  Published at `ghcr.io/sandervg/bose-soundtouch-bridge:latest`
  (multi-arch: amd64 + arm64). See `docker-compose.example.yml` and the
  repo README.
- `bridge.py` now reads config from environment variables
  (`BOSE_HOST`, `PRESET_1_URL` … `PRESET_6_URL`,
  `SYNC_PRESETS_ON_STARTUP`, `MQTT_HOST`, `MQTT_PORT`, `MQTT_USERNAME`,
  `MQTT_PASSWORD`) when `/data/options.json` isn't present, so the
  same code runs inside Supervisor and standalone.
- GitHub Actions workflow builds and publishes the standalone image to
  GHCR on every version tag.

## 1.4.0

- **Auto-sync presets to the speaker on startup.** New
  `sync_presets_on_startup` option (default `true`). The add-on writes
  each configured URL onto the speaker's preset slot so physical button
  presses always emit a `nowSelectionUpdated` event for the bridge to
  intercept. Without this, factory-reset speakers leave preset slots
  empty and physical button presses become silent no-ops.
- The sync skips slots that already match the configured URL, mutes the
  speaker during the write to hide the audio blip, and verifies each
  save took effect.
- IMPORTANT firmware quirk: the SoundTouch firmware refuses to save
  preset items that carry DIDL-Lite metadata (it sets
  `isPresetable="false"`). The sync therefore writes presets without
  metadata; runtime playback still applies full DIDL via
  `SetAVTransportURI` so the speaker shows the station name and logo.

## 1.3.1

- Stop the speaker before each SetAVTransportURI so the DIDL-Lite
  metadata (station name + favicon) lands cleanly in `now_playing` even
  when the press came from a physical preset button that started
  loading a stale on-device source first (TuneIn / cached UPnP item).

## 1.3.0

- **Speaker now displays the station name and logo.** Each `Play` call
  carries DIDL-Lite metadata (`dc:title`, `upnp:albumArtURI`,
  `audioBroadcast` class). Station name + favicon are auto-fetched from
  [radio-browser.info](https://www.radio-browser.info/) by stream URL
  at startup and cached for the session.
- **Trigger presets from Home Assistant.** The add-on connects to the
  Supervisor-provided MQTT broker (Mosquitto add-on) and publishes Home
  Assistant MQTT-discovery configs so each preset auto-appears as a
  `button.bose_<id>_preset_N` entity. Press the entity in HA → bridge
  plays the same URL it would play on a physical button press.
  Requires the Mosquitto Broker add-on running and the MQTT integration
  configured in HA (the standard auto-discovery setup).
- The add-on declares `services: ["mqtt:need"]` so the Supervisor
  injects MQTT credentials automatically — no manual configuration.
  Falls back gracefully if MQTT is unavailable (logs a warning, only
  physical buttons keep working).

## 1.2.1

- Fix multi-architecture build. The `1.2.0` Dockerfile only pulled the
  amd64 base image and failed on aarch64 (ARM64) Home Assistant
  installations. Re-added `build.yaml` mapping each supported
  architecture to its correct base image.
- Dropped deprecated `armv7`, `armhf`, `i386` from `arch` (modern
  Supervisor flags these). Supported architectures are now `amd64` and
  `aarch64`.

## 1.2.0

- Polished release for public use.
- Auto-discovers the SoundTouch via SSDP if `bose_host` is left blank.
- Auto-derives the UPnP description URL from the speaker's `/info`
  endpoint — works on any SoundTouch model out of the box.
- Removed deprecated `build.yaml` (FROM image inlined into Dockerfile).
- Default config is now empty so first-time users can paste their own
  URLs.

## 1.1.0

- Added 6 configurable preset URL fields and a `bose_host` field via the
  add-on **Configuration** tab.

## 1.0.0

- Initial WebSocket → UPnP bridge with hardcoded URL map.
