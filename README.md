# Smart Remote Control

[![Release](https://img.shields.io/github/v/release/zookzon/Smart-Remote-Control?label=release)](https://github.com/zookzon/Smart-Remote-Control/releases)
![Home Assistant](https://img.shields.io/badge/Home%20Assistant-2026.5%2B-41BDF5)
![HACS](https://img.shields.io/badge/HACS-Custom-41BDF5)
![License](https://img.shields.io/badge/License-PolyForm%20Noncommercial%201.0.0-orange)
[![HACS Validation](https://github.com/zookzon/Smart-Remote-Control/actions/workflows/hacs.yml/badge.svg)](https://github.com/zookzon/Smart-Remote-Control/actions/workflows/hacs.yml)
[![Hassfest Validation](https://github.com/zookzon/Smart-Remote-Control/actions/workflows/hassfest.yml/badge.svg)](https://github.com/zookzon/Smart-Remote-Control/actions/workflows/hassfest.yml)
[![Tests](https://github.com/zookzon/Smart-Remote-Control/actions/workflows/tests.yml/badge.svg)](https://github.com/zookzon/Smart-Remote-Control/actions/workflows/tests.yml)

**Smart Remote Control** is a Home Assistant custom integration for turning IR transmitters into easy-to-use Home Assistant entities. Version **1.0.0** provides two device types: **Climate** for stateful air-conditioner control and **Remote** for sending existing IR codes through a simple `remote` entity.

The project is designed around a practical rule: **you should be able to reuse IR codes you already have**. A standalone Remote does not force you to relearn codes into another database.

## Features

### Climate

- Home Assistant `climate` entity with HVAC mode, temperature, fan mode, Swing and Preset support.
- Four transmitter paths: **Home Assistant Remote**, **Broadlink**, **Zigbee2MQTT**, and **LocalTuya Direct IR**.
- JSON IR profiles for Broadlink, Zigbee2MQTT and LocalTuya.
- Home Assistant Remote learned-command mode for users who already use HA `remote` entities.
- Optional temperature, humidity and power-state sensors.
- Remembered state and tested power-on sequence: **ON → wait 0.8 s → current/remembered state**.
- Minimum ordinary send interval of **0.5 s** with latest-state-wins behavior.
- Profile validation before a Climate entity is created.
- Config Flow and Options Flow; no YAML configuration is required for the integration itself.

### Remote

- Creates a normal Home Assistant `remote` entity dedicated to raw/existing IR-code transmission.
- **MQTT** backend for Zigbee2MQTT and compatible MQTT IR transmitters.
- **LocalTuya Direct IR** backend.
- Optional user-defined IR-code prefix.
- LocalTuya device and DP discovery with manual DP fallback.
- Remote Options Flow for changing the backend configuration later.

> **Fan is not included in v1.0.0.** It is planned as a later feature so the first public release can keep the tested Climate + Remote baseline stable.

## Supported transmitters and verification status

| Path | Climate | Remote | Verification |
|---|:---:|:---:|---|
| Home Assistant Remote / learned commands | ✅ | Use the existing HA remote directly | Hardware tested |
| Zigbee2MQTT / MQTT IR | ✅ | ✅ | Hardware tested |
| LocalTuya Direct IR | ✅ | ✅ | Hardware tested |
| Broadlink `remote.send_command` | ✅ | Use the Broadlink remote directly | Smart Remote Control service/payload path verified; physical Broadlink hardware not yet tested by this project |

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
3. The final path must be:

   ```text
   <config>/custom_components/smart_remote_control/
   ```

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

The remaining steps depend on the transmitter.

### Climate with Home Assistant Remote

Choose **Home Assistant Remote** when the IR commands are already learned by a Home Assistant `remote` integration.

1. Select the existing Remote entity.
2. Enter the **Learn Device ID** used by that remote.
3. Configure grouping attributes. Attributes grouped together form one learned full-state command; Swing or Preset left outside the group can be sent as standalone commands.
4. Configure temperature, HVAC modes, fan modes, Swing and Preset.
5. Optionally select temperature, humidity and power sensors.
6. Finish the flow.

On OFF → ON, Smart Remote Control attempts the learned `on` command first and then, after **0.8 seconds**, sends the remembered/current Climate state. If a required learned command does not exist, the integration surfaces the missing-command condition instead of silently inventing a command.

### Climate with Broadlink

Choose **Broadlink** when your Climate profile contains Broadlink-compatible IR data.

1. Select the Broadlink Home Assistant `remote` entity.
2. Upload a Climate JSON profile.
3. Review the profile summary shown by the Config Flow.
4. Complete optional sensor selection and create the Climate entity.

Supported profile encodings for Broadlink are:

- `Base64`
- `Hex`
- `Pronto`

At send time the integration calls Home Assistant `remote.send_command` with a Broadlink-compatible `b64:` token. Base64 is passed through; Hex and Pronto profiles are converted before sending.

**Verification note:** the Broadlink service-call/payload path has been exercised end-to-end through the project's Broadlink2SmartIR test bridge and a real IR receiver/air conditioner. A physical Broadlink transmitter has not yet been tested by this project.

### Climate with Zigbee2MQTT

Choose **Zigbee2MQTT** for an MQTT IR transmitter.

1. Enter the MQTT command topic used by your device.
2. Upload a matching Zigbee2MQTT Climate JSON profile.
3. Review the profile summary.
4. Complete the remaining Climate options.

Climate profiles support `Raw` and `Base64` command encodings for this path.

### Climate with LocalTuya Direct IR

Choose **LocalTuya Direct IR** when the IR blaster is already configured in LocalTuya.

1. Smart Remote Control discovers LocalTuya devices already present in Home Assistant.
2. Select the IR device. Manual Device ID entry is available if discovery cannot provide it.
3. Select the **IR Send DP**. Known DPs are offered when LocalTuya exposes them; DP 201 is marked recommended only when it is actually present.
4. Upload a LocalTuya Climate profile using `Raw` encoding.
5. Review the profile and finish setup.

The tested LocalTuya send format is intentionally fixed:

```text
raw IR code
→ prefix with "1"
→ {"control":"send_ir","type":0,"head":"","key1":"1<raw>"}
→ encode as a JSON string
→ localtuya.set_dp
```

Do not change this payload format casually; it was selected after real hardware testing.

## Climate IR profile format

Profiles are JSON files. The validator checks the declared controller, encoding, modes, temperature range and the command tree before setup is allowed to continue.

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
  "commands": {
    "off": "IR_CODE_HERE"
  }
}
```

The complete command tree depends on the declared HVAC/fan/Swing/Preset modes. Use the examples in [`custom_components/smart_remote_control/profile_templates`](custom_components/smart_remote_control/profile_templates) as the starting point rather than building a large profile from memory.

The profile can optionally contain `commands.on`. When present, an OFF → ON transition sends that command, waits **0.8 s**, then sends the current/remembered full state. `commands.off` is required.

Swing and Preset can each be represented either as part of the full-state command tree or as standalone commands. The validator rejects mixed/ambiguous structures.

## Creating a standalone Remote entity

Choose Remote when you want a simple HA `remote` entity that accepts the IR codes you already have:

```text
Add Integration
→ Smart Remote Control
→ Device Name
→ Device Type: Remote
→ Choose Backend
```

### Remote with MQTT / Zigbee2MQTT

The Remote backend supports two topic forms.

#### Property-specific topic

Example:

```text
zigbee2mqtt/ir_blaster/set/ir_code_to_send
```

or another property supported by the device:

```text
zigbee2mqtt/ir_blaster/set/code_to_send
```

For a topic ending in `/set/property`, Smart Remote Control publishes the IR code itself as the payload. The property name is therefore controlled entirely by the topic you enter.

#### Base `/set` topic

Example:

```text
zigbee2mqtt/ir_blaster/set
```

For a topic ending exactly in `/set`, Smart Remote Control automatically publishes:

```json
{"ir_code_to_send":"YOUR_IR_CODE"}
```

This is useful for Zigbee2MQTT devices that accept the normal object payload on their base `set` topic.

### Optional IR Code Prefix

The Remote setup allows an optional prefix. This is useful when an existing caller sends codes in a Broadlink-like or otherwise prefixed representation.

If the configured prefix is:

```text
b64:
```

then a command such as:

```text
b64:JgAAAA...
```

is accepted and the configured prefix is removed before the backend sends the code. If the Prefix field is empty, the command is sent as-is.

A configured prefix is strict: a command that does not start with that prefix is rejected instead of being modified unpredictably.

### Remote with LocalTuya Direct IR

1. Choose **LocalTuya Direct IR** as the Remote backend.
2. Select the discovered LocalTuya device.
3. Select or manually enter the IR Send DP.
4. Set an optional IR Code Prefix, or leave it blank.
5. Create the Remote entity.

This Remote uses the same tested LocalTuya Direct IR payload format as the Climate path.

## Sending an IR code through the created Remote

The entity implements Home Assistant's normal `remote.send_command` behavior. A typical automation/action is conceptually:

```yaml
action: remote.send_command
target:
  entity_id: remote.your_smart_remote
data:
  command:
    - "YOUR_IR_CODE"
```

The important difference from a learned-command-only remote is that the Smart Remote Control Remote interprets the supplied command string as the IR code for its configured backend.

## Changing settings later

Open:

**Settings → Devices & services → Smart Remote Control → Configure**

Climate and Remote entries have separate Options Flows. Remote options allow the MQTT or LocalTuya backend settings to be changed without entering the Climate workflow.

## Timing behavior

Two timings are part of the tested Climate baseline:

- **0.8 s power-on settle delay** between the ON command and the remembered/current state.
- **0.5 s minimum ordinary send interval** for Climate state changes.

Rapid ordinary Climate changes use latest-state-wins behavior so an obsolete intermediate state does not need to be transmitted after a newer state has replaced it.

## Troubleshooting

**The integration does not appear after manual installation**  
Check that `manifest.json` is at `<config>/custom_components/smart_remote_control/manifest.json`, then restart Home Assistant.

**LocalTuya device is not discovered**  
Confirm the device already exists in the LocalTuya integration. The setup flow also provides manual Device ID / DP fallback where appropriate.

**LocalTuya sends but the appliance does not react**  
Verify that you selected the actual IR Send DP and that the IR code/profile is `Raw`. Do not use a Broadlink `b64:` code as a LocalTuya raw code unless you intentionally configured and understand the prefix conversion at the standalone Remote layer.

**MQTT Remote does not send**  
Check the topic carefully. It must end in `/set` or `/set/property`. For `/set`, the integration automatically uses `ir_code_to_send`; for `/set/property`, the code itself is published to that topic.

**Climate will not turn on from OFF**  
For a learned HA Remote, make sure the required `on` learned command exists. For profile-based Climate, `commands.on` is optional; when it exists it is used before the current state. The tested follow-up delay is 0.8 seconds.

**Broadlink does not work on physical hardware**  
Please report the exact Home Assistant Broadlink remote entity, profile encoding and logs. The service/payload pipeline is verified, but physical Broadlink hardware is explicitly outside the v1.0.0 hardware-tested boundary.

## Verification and tests

The development build used to create v1.0.0 passed **78 automated regression tests** before publication. GitHub Actions run the test suite again on pushes and pull requests, alongside HACS and Hassfest validation.

The repository deliberately distinguishes between **hardware tested** and **interface/pipeline verified** behavior. See [TEST_MATRIX.md](TEST_MATRIX.md).

## Versioning

Public releases use Semantic Versioning beginning at **v1.0.0**.

- Patch (`1.0.x`) — bug fixes.
- Minor (`1.x.0`) — backwards-compatible features, such as a new device type.
- Major (`x.0.0`) — breaking public changes.

Internal development build numbers used before the first public release are not the public version history.

## License

Project-original portions are © 2026 zookzon and are licensed under the **PolyForm Noncommercial License 1.0.0**. The license permits the software to be used for noncommercial purposes subject to its terms. Commercial use is not granted by this license and requires separate permission from the copyright holder.

PolyForm Noncommercial 1.0.0 is not an OSI-approved open-source license because it restricts use to noncommercial purposes. Third-party material remains under its own license. See [LICENSE](LICENSE) and [ACKNOWLEDGEMENTS.md](ACKNOWLEDGEMENTS.md).

## Credits

Smart Remote Control was developed with reference to the Home Assistant IR-control ecosystem and SmartIR-related projects. See [ACKNOWLEDGEMENTS.md](ACKNOWLEDGEMENTS.md) for details.

## Support

Please use the [GitHub issue tracker](https://github.com/zookzon/Smart-Remote-Control/issues) for reproducible bugs. Include your Home Assistant version, selected backend/transmitter, relevant configuration (with secrets removed), logs, and whether the behavior was tested on real IR hardware.
