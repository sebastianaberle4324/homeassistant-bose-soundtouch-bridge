# Changelog

## 3.3.4

- **Remove hardcoded `media_type: radio` from play_media call.** Music
  Assistant auto-detects the media type, so presets now work with
  playlists, albums, tracks, and radio stations without any extra config.

## 3.3.3

- **Fix power on/off detection (critical).** `SOURCE_RE` was matching
  `<source>STANDBY</source>` (XML element) but the speaker sends
  `source="STANDBY"` (XML attribute). The regex never matched, so
  standby detection, auto-stop, and auto-play were all silently broken.

## 3.3.2

- **Fix power-on detection.** On startup the addon now reads `/now_playing`
  to detect whether the speaker is already in standby. Previously
  `was_standby` always started as `false`, so the first
  STANDBY -> INVALID_SOURCE transition was missed.

## 3.3.1

- **Security: remove admin role.** Config persistence now uses a local
  file (`/data/discovered.json`) instead of the Supervisor API, so
  `hassio_role: admin` is no longer needed. The addon runs with the
  default (minimal) Supervisor role.
- **Security: XML escape preset names.** Preset names are now escaped
  before embedding in XML payloads sent to the speaker.

## 3.3.0

- **Auto-save discovered config.** When `bose_host` or `media_player_entity`
  are left blank, the auto-discovered values are now saved back to the
  addon config via the Supervisor API. Clear a field to re-trigger
  auto-discovery on next restart.
- **Smarter MA entity detection.** When multiple Music Assistant players
  exist, the addon now matches by Bose device ID in the `active_queue`
  attribute (exact hardware match) instead of just picking the first one.
  Falls back to speaker model name matching.
- **Preset name sync.** `sync_presets` now also updates preset slots
  whose display name differs from the configured name, not just empty slots.

## 3.2.0

- **Power on/off detection.** The addon detects when the speaker enters
  or leaves standby via the WebSocket and fires separate events:
  `bose_soundtouch_power_on` and `bose_soundtouch_power_off`.
- **Auto-play on power on.** When the speaker powers on, the addon
  automatically resumes the last played preset via Music Assistant.
  Defaults to preset 1 if none was pressed yet.
  Controlled by the new `auto_play_on_power_on` option (default: on).
- **Auto-stop on power off.** When the speaker enters standby, the
  addon stops Music Assistant playback so MA doesn't accidentally
  restart the speaker.
- **Flat preset config.** Presets are now individual fields
  (`preset_1_media_id`, `preset_1_name`, etc.) instead of a nested list.
  No more "Add" button or expand/collapse in the config UI.
- **Fix:** Detect MA entities by `mass_player_type` attribute (was
  `mass_player_id`).
- **Removed:** `placeholder_url` config option (hardcoded internally).

## 3.1.0

- **Auto-detect Music Assistant entity.** If `media_player_entity` is
  left blank, the addon queries HA for entities with a `mass_player_type`
  attribute. If exactly one is found it is used automatically.
- **Preset defaults.** Empty presets now show "Preset 1"..."Preset 6"
  in the config UI instead of blank fields.
- **Config descriptions.** Each option now has a help text with examples
  (e.g. `192.168.1.42`, `library://radio/6`).
- **Removed `placeholder_url` from config.** The placeholder stream URL
  is now hardcoded internally — it was never user-facing functionality.
- **Updated README** to reflect v3 features (direct MA playback,
  auto-discovery, hybrid event/playback mode).

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
