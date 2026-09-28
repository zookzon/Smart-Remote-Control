# Climate Test Matrix

Public release baseline: Smart Remote Control v1.0.0 (derived from the hardware-tested development line through v3.4.17).

| Area | Automated | Real hardware / HA | Status |
|---|---:|---:|---|
| Config Flow / Options Flow | Yes | Yes | Verified |
| Profile validator | Yes | Yes | Verified |
| Profile resolver | Yes | Yes | Verified |
| Restore / migration | Yes | Yes | Verified |
| HVAC Action | Yes | Yes | Verified |
| Power binary sensor behavior | Regression coverage | Yes | Verified in use |
| Swing full-state / standalone | Yes | Yes | Verified |
| Preset full-state / standalone / none | Yes | Yes | Verified |
| HA Remote learned commands | Yes | Yes | Verified |
| Zigbee2MQTT Base64/raw | Yes | Yes | Verified |
| LocalTuya Direct IR raw | Yes | Yes | Verified |
| LocalTuya single-DP JSON-string payload | Yes | Yes | Verified |
| OFF → ON → 0.8 s → current state | Yes | Yes | Verified |
| 0.5 s send coordination / latest-state-wins | Yes | Yes | Verified in use |
| Broadlink Base64 service-call path | Yes | Via Broadlink2SmartIR bridge + real IR | Pipeline verified |
| Broadlink physical hardware | N/A | No | Not hardware verified |

## Broadlink verification boundary

The tested path is:

`IR profile → resolver → b64:<code> → remote.send_command → Broadlink2SmartIR test remote → Zigbee2MQTT IR blaster → real AC`

This validates the Smart Remote Control payload/service-call side and real IR code behavior. It does not validate the final Home Assistant Broadlink integration → physical Broadlink-device transport layer.

## Locked timing

- Ordinary minimum send interval: **0.5 seconds**
- Power-on settle delay: **0.8 seconds**

The 0.8-second value was selected after real-device testing and should not be changed casually.

## Release regression rule

Before changing Climate core, transmitter routing, profile resolution, or power sequencing:

1. Run the complete automated test suite.
2. Do not change the LocalTuya payload format without a hardware regression test.
3. Preserve the optional `on` behavior for database profiles.
4. Preserve OFF → ON sequencing and remembered/current-state follow-up.
5. Treat Broadlink physical hardware as unverified until tested on an actual Broadlink device.
