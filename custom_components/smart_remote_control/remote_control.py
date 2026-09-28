"""Remote control handler for Smart Remote Control (unified MQTT logic)."""
import json
import logging
import binascii
import struct
from base64 import b64decode, b64encode

_LOGGER = logging.getLogger(__name__)

class RemoteControlError(Exception):
    """Base error raised when a transmitter cannot send a command."""


class RemoteConfigurationError(RemoteControlError):
    """The selected transmitter is missing required configuration."""


class RemoteEncodingError(RemoteControlError):
    """The IR command or commandsEncoding is invalid for the transmitter."""


class RemoteTransportError(RemoteControlError):
    """Home Assistant could not deliver the command to the transmitter."""



class RemoteControl:
    """Universal IR transmitter handler."""

    def __init__(self, hass, remote_type, mqtt_topic=None, remote_entity=None, device_id=None, dp=None, ha_device_id=None, commands_encoding=None):
        self.hass = hass
        self.remote_type = remote_type
        self.mqtt_topic = mqtt_topic or ""
        self.remote_entity = remote_entity
        self.device_id = device_id
        self.dp = dp
        self.ha_device_id = ha_device_id
        self.commands_encoding = (commands_encoding or "Base64").strip()

    # ----------------------------------------------------------------
    # 🔸 Utility: heuristic detectors
    # ----------------------------------------------------------------
    @staticmethod
    def _looks_like_b64(s: str) -> bool:
        """Check if string looks like base64 IR data."""
        if not isinstance(s, str) or len(s) < 16:
            return False
        if " " in s or "\n" in s:
            return False
        try:
            _ = b64decode(s + "==", validate=False)
            return True
        except Exception:
            return False

    @staticmethod
    def _looks_like_hex(s: str) -> bool:
        """Check if looks like hex code e.g. 0x8808B03."""
        try:
            s2 = s[2:] if s.startswith("0x") else s
            int(s2, 16)
            return True
        except Exception:
            return False

    # ----------------------------------------------------------------
    # 🔸 MQTT topic parser — dynamic suffix detector
    # ----------------------------------------------------------------
    def _split_mqtt_topic_and_key(self):
        """
        ตรวจ suffix จาก topic ที่ user ใส่มา
        ตัวอย่าง:
          zigbee2mqtt/ir_blaster/set/protocol  → (zigbee2mqtt/ir_blaster/set, 'protocol')
          esp32/air_lg_me/set/ir_code_to_send  → (esp32/air_lg_me/set, 'ir_code_to_send')
          mydevice/set                         → (mydevice/set, 'ir_code_to_send')
        """
        topic = (self.mqtt_topic or "").strip().rstrip("/")
        parts = topic.split("/")
        key = None

        # pattern ปกติ .../set/<suffix>
        if len(parts) >= 2 and parts[-2] == "set":
            key = parts[-1]
            base_topic = "/".join(parts[:-1])
        elif parts[-1] == "set":
            # ไม่มี suffix
            key = "ir_code_to_send"
            base_topic = topic
        else:
            # fallback
            key = "ir_code_to_send"
            base_topic = topic

        return base_topic, key

    # ----------------------------------------------------------------
    # 🔸 Main send_command dispatcher
    # ----------------------------------------------------------------
    async def send_command(self, cmd: str | dict):
        """Send an IR command and surface a classified error to the caller."""
        try:
            if self.remote_type == "ha_remote":
                await self._send_via_ha_remote(cmd)
            elif self.remote_type == "broadlink":
                await self._send_via_broadlink(cmd)
            elif self.remote_type == "zigbee2mqtt":
                await self._send_via_mqtt_dynamic(cmd)
            elif self.remote_type == "localtuya":
                await self._send_via_localtuya(cmd)
            else:
                raise RemoteConfigurationError(
                    f"Unsupported transmitter type: {self.remote_type}"
                )
        except RemoteControlError:
            raise
        except Exception as err:
            raise RemoteTransportError(
                f"{self.remote_type} failed to send the IR command: {err}"
            ) from err

    # ----------------------------------------------------------------
    # 🔹 HA Remote (Home Assistant Remote)
    # ----------------------------------------------------------------
    async def _send_via_ha_remote(self, cmd: str | dict):
        """Handle ha_remote — supports Learn-Device or Broadlink-like."""
        if not self.remote_entity:
            raise RemoteConfigurationError("Home Assistant Remote entity is not configured")

        # --- Mode 1: Learn-device ---
        if self.ha_device_id:
            if isinstance(cmd, dict):
                cmd = json.dumps(cmd)
            await self.hass.services.async_call(
                "remote",
                "send_command",
                {
                    "entity_id": self.remote_entity,
                    "device": self.ha_device_id,
                    "command": cmd,
                },
            )
            _LOGGER.debug("✅ ha_remote sent (learn-device) → device=%s cmd=%s", self.ha_device_id, cmd)
            return

        # --- Mode 2: Broadlink-like (SmartIR style) ---
        # รองรับ base64 (b64:<data>), หรือ pure base64
        send_token = None
        if isinstance(cmd, dict):
            cmd = cmd.get("command") or cmd.get("code") or ""

        if isinstance(cmd, str):
            if cmd.startswith("b64:"):
                send_token = cmd
            elif self._looks_like_b64(cmd):
                send_token = "b64:" + cmd
            else:
                raise RemoteEncodingError("Home Assistant Remote command is not valid Base64")
        else:
            raise RemoteEncodingError(
                f"Invalid Home Assistant Remote command type: {type(cmd).__name__}"
            )

        await self.hass.services.async_call(
            "remote",
            "send_command",
            {
                "entity_id": self.remote_entity,
                "command": [send_token],
            },
        )
        _LOGGER.debug("✅ ha_remote(broadlink) sent command=%s", send_token)


    @staticmethod
    def _pronto_to_lirc(pronto: bytearray) -> list[int]:
        """Convert Pronto to LIRC pulse timings using SmartIR's algorithm."""
        codes = [
            int(binascii.hexlify(pronto[i : i + 2]), 16)
            for i in range(0, len(pronto), 2)
        ]

        if not codes or codes[0]:
            raise ValueError("Pronto code should start with 0000")
        if len(codes) < 4 or codes[1] == 0:
            raise ValueError("Invalid Pronto code preamble")
        if len(codes) != 4 + 2 * (codes[2] + codes[3]):
            raise ValueError("Number of pulse widths does not match the preamble")

        frequency = 1 / (codes[1] * 0.241246)
        return [int(round(code / frequency)) for code in codes[4:]]

    @staticmethod
    def _lirc_to_broadlink(pulses: list[int]) -> bytes:
        """Convert LIRC pulse timings to a Broadlink packet using SmartIR's algorithm."""
        array = bytearray()

        for pulse in pulses:
            pulse = int(pulse * 269 / 8192)
            if pulse < 256:
                array += bytearray(struct.pack(">B", pulse))
            else:
                array += bytearray([0x00])
                array += bytearray(struct.pack(">H", pulse))

        packet = bytearray([0x26, 0x00])
        packet += bytearray(struct.pack("<H", len(array)))
        packet += array
        packet += bytearray([0x0D, 0x05])

        # SmartIR pads the packet for Broadlink's 128-bit AES block size.
        remainder = (len(packet) + 4) % 16
        if remainder:
            packet += bytearray(16 - remainder)
        return bytes(packet)

    def _broadlink_token(self, cmd: str) -> str:
        """Convert Base64, Hex, or Pronto profile data to a Broadlink b64: token."""
        encoding = self.commands_encoding.lower()

        if encoding == "base64":
            # Profiles normally store pure Base64. Accept b64: too so an existing
            # profile is not double-prefixed.
            data = cmd[4:] if cmd.startswith("b64:") else cmd
            return "b64:" + data

        if encoding == "hex":
            try:
                clean = cmd[2:] if cmd.lower().startswith("0x") else cmd
                raw = binascii.unhexlify(clean.replace(" ", ""))
                return "b64:" + b64encode(raw).decode("utf-8")
            except Exception as err:
                raise RemoteEncodingError("Error while converting Hex to Base64 encoding") from err

        if encoding == "pronto":
            try:
                clean = cmd.replace(" ", "")
                pronto = bytearray.fromhex(clean)
                pulses = self._pronto_to_lirc(pronto)
                packet = self._lirc_to_broadlink(pulses)
                return "b64:" + b64encode(packet).decode("utf-8")
            except Exception as err:
                raise RemoteEncodingError("Error while converting Pronto to Base64 encoding") from err

        raise RemoteEncodingError(
            f"Broadlink does not support commandsEncoding '{self.commands_encoding}'"
        )

    async def _send_via_broadlink(self, cmd: str | dict | list):
        """Send Broadlink commands using the SmartIR send format."""
        if not self.remote_entity:
            raise RemoteConfigurationError("Broadlink remote entity is not configured")

        if isinstance(cmd, dict):
            cmd = cmd.get("command") or cmd.get("code") or ""

        source_commands = cmd if isinstance(cmd, list) else [cmd]
        commands = []
        for item in source_commands:
            if not isinstance(item, str):
                raise RemoteEncodingError(
                    f"Invalid Broadlink command type: {type(item).__name__}"
                )
            commands.append(self._broadlink_token(item))

        service_data = {
            "entity_id": self.remote_entity,
            "command": commands,
        }
        try:
            await self.hass.services.async_call(
                "remote", "send_command", service_data, blocking=True
            )
        except Exception as err:
            raise RemoteTransportError(
                f"Broadlink remote service call failed: {err}"
            ) from err
        _LOGGER.debug(
            "✅ broadlink sent %s command(s), encoding=%s",
            len(commands),
            self.commands_encoding,
        )

    # ----------------------------------------------------------------
    # 🔹 MQTT (unified — for Zigbee2MQTT, ESP32, Broadlink MQTT)
    # ----------------------------------------------------------------
    async def _send_via_mqtt_dynamic(self, cmd: str | dict):
        """Send Zigbee2MQTT IR command. Profile encoding may be Base64 or Raw."""
        if self.commands_encoding.lower() not in {"base64", "raw"}:
            raise RemoteEncodingError(
                f"Zigbee2MQTT does not support commandsEncoding '{self.commands_encoding}'"
            )
        if not self.mqtt_topic:
            raise RemoteConfigurationError("Zigbee2MQTT MQTT topic is not configured")

        base_topic, key = self._split_mqtt_topic_and_key()
        _LOGGER.debug("🧭 MQTT detect: base_topic=%s, key=%s, orig=%s", base_topic, key, self.mqtt_topic)

        # --- build payload ---
        if isinstance(cmd, dict):
            payload = json.dumps(cmd)

        elif key == "protocol":
            # Protocol mode → {"protocol": "LG2", "code": "0x8808B03"}
            # If code looks like HEX, wrap it
            proto = "LG2"
            payload = json.dumps({"protocol": proto, "code": cmd})

        elif key in ("ir_code_to_send", "send_ir"):
            # Regular Zigbee/Tuya/Broadlink MQTT style
            payload = json.dumps({key: cmd})

        else:
            # Unknown suffix → fallback
            payload = json.dumps({"ir_code_to_send": cmd})

        # --- publish ---
        try:
            await self.hass.services.async_call(
                "mqtt",
                "publish",
                {
                    "topic": base_topic,
                    "payload": payload,
                },
                blocking=True,
            )
        except Exception as err:
            raise RemoteTransportError(
                f"Zigbee2MQTT MQTT publish failed for topic '{base_topic}': {err}"
            ) from err
        _LOGGER.debug("✅ MQTT published → topic=%s, key=%s, payload=%s", base_topic, key, payload)

    # ----------------------------------------------------------------
    # 🔹 LocalTuya
    # ----------------------------------------------------------------
    async def _send_via_localtuya(self, cmd: str | dict):
        """Send a raw Tuya IR command through LocalTuya single-DP transport.

        The JSON-string payload format is intentionally locked to the format
        proven to work with Tuya single-DP IR blasters.
        """
        if not self.device_id or self.dp is None:
            raise RemoteConfigurationError("LocalTuya Direct IR requires a Device ID and IR Send DP.")
        if self.commands_encoding.strip().lower() != "raw":
            raise RemoteEncodingError("LocalTuya Direct IR requires commandsEncoding Raw.")
        if not isinstance(cmd, str) or not cmd.strip():
            raise RemoteEncodingError("LocalTuya Direct IR requires a non-empty raw IR code string.")

        ir_code = f"1{cmd.strip()}"
        payload = json.dumps({
            "control": "send_ir",
            "type": 0,
            "head": "",
            "key1": ir_code
        })
        try:
            await self.hass.services.async_call(
                "localtuya",
                "set_dp",
                {
                    "device_id": self.device_id,
                    "dp": self.dp,
                    "value": payload,
                },
                blocking=True,
            )
        except Exception as err:
            raise RemoteTransportError(
                f"LocalTuya set_dp failed for device '{self.device_id}', DP {self.dp}: {err}"
            ) from err
        _LOGGER.debug("✅ localtuya sent → dp=%s, payload=%s", self.dp, payload)
