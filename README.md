# Smart Remote Control

[![Release](https://img.shields.io/github/v/release/zookzon/Smart-Remote-Control?label=release)](https://github.com/zookzon/Smart-Remote-Control/releases)
![Home Assistant](https://img.shields.io/badge/Home%20Assistant-2026.5%2B-41BDF5)
![HACS](https://img.shields.io/badge/HACS-Custom-41BDF5)
![License](https://img.shields.io/badge/License-Non--Commercial-orange)
[![HACS Validation](https://github.com/zookzon/Smart-Remote-Control/actions/workflows/hacs.yml/badge.svg)](https://github.com/zookzon/Smart-Remote-Control/actions/workflows/hacs.yml)
[![Hassfest Validation](https://github.com/zookzon/Smart-Remote-Control/actions/workflows/hassfest.yml/badge.svg)](https://github.com/zookzon/Smart-Remote-Control/actions/workflows/hassfest.yml)
[![Tests](https://github.com/zookzon/Smart-Remote-Control/actions/workflows/tests.yml/badge.svg)](https://github.com/zookzon/Smart-Remote-Control/actions/workflows/tests.yml)

**Smart Remote Control** is a Home Assistant custom integration for turning IR transmitters into easy-to-use Home Assistant entities. Version **1.0.0** provides **Climate** for stateful air-conditioner control and **Remote** for sending existing IR codes through a normal Home Assistant `remote` entity.

The project is designed around a practical rule: **you should be able to reuse IR codes you already have**. A standalone Remote does not force you to relearn codes into another database.

## Features

### Climate

- Home Assistant `climate` entity with HVAC mode, temperature, fan mode, Swing and Preset support.
- Four transmitter paths: **Home Assistant Remote**, **Broadlink**, **Zigbee2MQTT**, and **LocalTuya Direct IR**.
- JSON IR profiles for Broadlink, Zigbee2MQTT and LocalTuya.
- Home Assistant Remote learned-command mode.
- Optional temperature, humidity and power-state sensors.
- Remembered state and tested power-on sequence: **ON → wait 0.8 s → current/remembered state**.
- Minimum ordinary send interval of **0.5 s** with latest-state-wins behavior.
- Profile validation before a Climate entity is created.
- Config Flow and Options Flow.

### Remote

- Creates a normal Home Assistant `remote` entity dedicated to raw/existing IR-code transmission.
- **MQTT** backend for Zigbee2MQTT and compatible MQTT IR transmitters.
- **LocalTuya Direct IR** backend.
- Optional user-defined IR-code prefix.
- LocalTuya device and DP discovery with manual DP fallback.
- Remote Options Flow for changing backend configuration later.

> **Fan is not included in v1.0.0.** It is planned as a later feature so the first public release can keep the tested Climate + Remote baseline stable.

## Supported transmitters and verification status

| Path | Climate | Remote | Verification |
|---|:---:|:---:|---|
| Home Assistant Remote / learned commands | ✅ | Use the existing HA remote directly | Hardware tested |
| Zigbee2MQTT / MQTT IR | ✅ | ✅ | Hardware tested |
| LocalTuya Direct IR | ✅ | ✅ | Hardware tested |
| Broadlink `remote.send_command` | ✅ | Use the Broadlink remote directly | Service/payload path verified; physical Broadlink hardware not yet tested by this project |

See [TEST_MATRIX.md](TEST_MATRIX.md) for the exact verification boundary.

## Installation

### HACS — recommended

If HACS is installed, use the button below to add this repository as a custom integration repository:

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=zookzon&repository=Smart-Remote-Control&category=integration)

Then:

1. Install **Smart Remote Control** in HACS.
2. Restart Home Assistant.
3. Open **Settings → Devices & services → Add Integration**.
4. Search for **Smart Remote Control**.

### Manual

1. Download the latest release from GitHub.
2. Copy `custom_components/smart_remote_control` into your Home Assistant configuration directory.
3. The final path must be `<config>/custom_components/smart_remote_control/`.
4. Restart Home Assistant.
5. Go to **Settings → Devices & services → Add Integration → Smart Remote Control**.

## Creating a Climate entity

Start with:

```text
Add Integration
→ Smart Remote Control
→ Device Name
→ Device Type: Climate
→ Choose Climate Transmitter
```

### Home Assistant Remote

Choose this when IR commands are already learned by a Home Assistant `remote` integration.

1. Select the existing Remote entity.
2. Enter the **Learn Device ID** used by that remote.
3. Configure grouping attributes. Attributes grouped together form one learned full-state command; Swing or Preset left outside the group can be sent as standalone commands.
4. Configure temperature, HVAC modes, fan modes, Swing and Preset.
5. Optionally select temperature, humidity and power sensors.
6. Finish the flow.

On OFF → ON, Smart Remote Control attempts the learned `on` command first and then, after **0.8 seconds**, sends the remembered/current Climate state. A missing required learned command is surfaced instead of silently inventing one.

### Broadlink

1. Select the Broadlink Home Assistant `remote` entity.
2. Upload a Climate JSON profile.
3. Review the profile summary.
4. Complete optional sensor selection and create the Climate entity.

Supported Broadlink profile encodings are `Base64`, `Hex`, and `Pronto`. At send time the integration calls Home Assistant `remote.send_command` with a Broadlink-compatible `b64:` token. Base64 is passed through; Hex and Pronto are converted before sending.

**Verification note:** the service-call/payload path has been exercised end-to-end through the project's Broadlink2SmartIR test bridge and real IR reception. A physical Broadlink transmitter has not yet been tested by this project.

### Zigbee2MQTT

1. Enter the MQTT command topic used by your device.
2. Upload a matching Zigbee2MQTT Climate JSON profile.
3. Review the profile summary.
4. Complete the remaining Climate options.

Climate profiles support `Raw` and `Base64` command encodings for this path.

### LocalTuya Direct IR

1. Smart Remote Control discovers LocalTuya devices already present in Home Assistant.
2. Select the IR device. Manual Device ID entry is available if discovery cannot provide it.
3. Select the **IR Send DP**. Known DPs are offered when LocalTuya exposes them; DP 201 is marked recommended only when actually present.
4. Upload a LocalTuya Climate profile using `Raw` encoding.
5. Review the profile and finish setup.

The tested send format is intentionally fixed:

```text
raw IR code
→ prefix with "1"
→ {"control":"send_ir","type":0,"head":"","key1":"1<raw>"}
→ encode as a JSON string
→ localtuya.set_dp
```

## Climate IR profile format

Profiles are JSON files. The validator checks the declared controller, encoding, modes, temperature range and command tree before setup is allowed to continue.

Important top-level fields include:

```json
{
  "manufacturer": "Example",
  "supportedModels": ["Example AC"],
  "supportedController": "Zigbee2MQTT",
  "commandsEncoding": "Raw",
  "minTemperature": 16,
  "maxTemperature": 30,
  "precision": 1,
  "operationModes": ["cool", "dry", "fan_only"],
  "fanModes": ["auto", "low", "medium", "high"],
  "commands": {"off": "IR_CODE_HERE"}
}
```

Use the examples in [`custom_components/smart_remote_control/profile_templates`](custom_components/smart_remote_control/profile_templates) as the starting point. `commands.on` is optional. When present, OFF → ON sends it, waits **0.8 s**, then sends the current/remembered full state. `commands.off` is required.

Swing and Preset can each be represented either as part of the full-state command tree or as standalone commands. The validator rejects mixed/ambiguous structures.

## Creating a standalone Remote entity

```text
Add Integration
→ Smart Remote Control
→ Device Name
→ Device Type: Remote
→ Choose Backend
```

### MQTT / Zigbee2MQTT

The Remote backend supports two topic forms.

A property-specific topic such as:

```text
zigbee2mqtt/ir_blaster/set/ir_code_to_send
zigbee2mqtt/ir_blaster/set/code_to_send
```

publishes the IR code itself as the payload. The property name is controlled by the topic you enter.

A base topic:

```text
zigbee2mqtt/ir_blaster/set
```

publishes automatically as:

```json
{"ir_code_to_send":"YOUR_IR_CODE"}
```

### Optional IR Code Prefix

If the configured prefix is `b64:`, a command such as `b64:JgAAAA...` is accepted and the prefix is removed before the backend sends the code. If Prefix is empty, the command is sent as-is. A configured prefix is strict: a command that does not start with it is rejected.

### LocalTuya Direct IR Remote

1. Choose **LocalTuya Direct IR**.
2. Select the discovered LocalTuya device.
3. Select or manually enter the IR Send DP.
4. Set an optional IR Code Prefix, or leave it blank.
5. Create the Remote entity.

This uses the same tested LocalTuya Direct IR payload format as Climate.

## Sending an IR code through the created Remote

```yaml
action: remote.send_command
target:
  entity_id: remote.your_smart_remote
data:
  command:
    - "YOUR_IR_CODE"
```

Unlike a learned-command-only remote, the Smart Remote Control Remote interprets the supplied command string as the IR code for its configured backend.

## Changing settings later

Open **Settings → Devices & services → Smart Remote Control → Configure**. Climate and Remote entries have separate Options Flows.

## Timing behavior

- **0.8 s power-on settle delay** between ON and the remembered/current state.
- **0.5 s minimum ordinary send interval** for Climate state changes.
- Rapid ordinary Climate changes use latest-state-wins behavior.

## Troubleshooting

**Integration does not appear after manual installation:** check that `manifest.json` is at `<config>/custom_components/smart_remote_control/manifest.json`, then restart Home Assistant.

**LocalTuya device is not discovered:** confirm the device already exists in LocalTuya. Manual Device ID / DP fallback is available where appropriate.

**LocalTuya sends but the appliance does not react:** verify the actual IR Send DP and that the Climate profile uses `Raw` encoding.

**MQTT Remote does not send:** the topic must end in `/set` or `/set/property`. `/set` automatically uses `ir_code_to_send`; `/set/property` publishes the code itself.

**Climate will not turn on from OFF:** for a learned HA Remote, make sure the required `on` learned command exists. For profile-based Climate, `commands.on` is optional. The tested follow-up delay is 0.8 seconds.

**Broadlink physical hardware issue:** include the Home Assistant Broadlink remote entity, profile encoding and logs in the issue report. Physical Broadlink hardware is outside the v1.0.0 hardware-tested boundary.

## Verification and tests

The development build used to create v1.0.0 passed **78 automated regression tests** before publication. GitHub Actions run the suite again on pushes and pull requests alongside HACS and Hassfest validation.

## Versioning

Public releases use Semantic Versioning beginning at **v1.0.0**. Patch releases are bug fixes, minor releases add backwards-compatible features, and major releases are reserved for breaking public changes. Internal development build numbers are not the public version history.

## License

Project-original portions are © 2026 zookzon and are provided under the repository's **Non-Commercial License**. Personal, educational, research and hobby use is allowed; commercial use requires prior written permission.

This is **not an OSI-approved open-source license** because commercial use is restricted. Third-party material remains under its own license. See [LICENSE](LICENSE) and [ACKNOWLEDGEMENTS.md](ACKNOWLEDGEMENTS.md).

## Support

Please use the [GitHub issue tracker](https://github.com/zookzon/Smart-Remote-Control/issues) for reproducible bugs. Include your Home Assistant version, selected backend/transmitter, relevant configuration with secrets removed, logs, and whether the behavior was tested on real IR hardware.
