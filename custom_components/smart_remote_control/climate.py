"""Climate platform for Smart Remote Control (ConfigFlow only)."""
import os, json, logging, aiofiles, asyncio
from numbers import Number
from dataclasses import dataclass
from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import HVACMode, HVACAction, ClimateEntityFeature
from homeassistant.const import ATTR_TEMPERATURE, STATE_UNKNOWN, STATE_UNAVAILABLE
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.restore_state import RestoreEntity, ExtraStoredData
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.core import Event, EventStateChangedData, callback
from typing import Optional

from .const import (
    DOMAIN,
    CONF_DEVICE_CODE,
    CONF_DEVICE_PROFILE,
    CONF_MQTT_TOPIC,
    CONF_REMOTE_ENTITY,
    CONF_TEMPERATURE_SENSOR,
    CONF_HUMIDITY_SENSOR,
    CONF_POWER_SENSOR,
    CONF_REMOTE_TYPE,
    CONF_DEVICE_ID,
    CONF_DP,
    CONF_HA_DEVICE_ID,
    CONF_HVAC_MODES,
    CONF_FAN_MODES,
    CONF_SWING,
    CONF_TEMPERATURE,
    CONF_TEMPERATURE_STEP,
    CONF_GROUPING_ATTRIBUTES,
    CONF_GROUPING_ATTRIBUTES_AS_SEQUENCE,
    CONF_DEVICE_TYPE,
)

from .remote_control import (
    RemoteControl,
    RemoteConfigurationError,
    RemoteEncodingError,
    RemoteTransportError,
)
from .profile_resolver import resolve_command
from .ha_command_builder import attr_command as build_ha_attr_command, commands_for as build_ha_commands
from .state_logic import estimate_hvac_action, restore_choice, restore_hvac_mode, normalize_temperature
from .send_coordinator import MIN_SEND_INTERVAL, POWER_ON_SETTLE_DELAY, is_power_transition, should_drop_as_superseded, optional_profile_on

_LOGGER = logging.getLogger(__name__)
NOTI_TITLE = "Smart Remote Control"


async def _notify(hass, message, nid=None):
    """Persistent notification helper."""
    try:
        await hass.services.async_call(
            "persistent_notification",
            "create",
            {
                "message": message,
                "title": NOTI_TITLE,
                "notification_id": nid,
            },
            blocking=False,
        )
    except Exception as e:
        _LOGGER.error("Notification failed: %s (message=%s)", e, message)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up Smart Remote Control from a config entry."""
    config = entry.data.copy()
    config.update(entry.options)

    if config.get(CONF_DEVICE_TYPE, "climate") != "climate":
        return

    device_code = config.get(CONF_DEVICE_CODE)
    name = config.get("name")
    unique_id = config.get("unique_id")
    remote_type = config.get(CONF_REMOTE_TYPE, "ha_remote")

    # Validate required config
    missing = []
    if remote_type == "ha_remote":
        if not config.get(CONF_REMOTE_ENTITY):
            missing.append(CONF_REMOTE_ENTITY)
        if not config.get(CONF_HA_DEVICE_ID):
            missing.append(CONF_HA_DEVICE_ID)
    elif remote_type == "localtuya":
        if not config.get(CONF_DEVICE_ID):
            missing.append(CONF_DEVICE_ID)
        if config.get(CONF_DP) is None:
            missing.append(CONF_DP)
    elif remote_type == "zigbee2mqtt":
        if not config.get(CONF_MQTT_TOPIC):
            missing.append(CONF_MQTT_TOPIC)

    if missing:
        await _notify(
            hass,
            f"❌ Config incomplete for {name or unique_id} (remote_type={remote_type}). Missing: {', '.join(missing)}",
            nid=f"{DOMAIN}_cfg_{unique_id}",
        )
        return

    # Climate Profile v2 is stored directly in the config entry. Legacy file paths remain supported for LocalTuya.
    data = config.get(CONF_DEVICE_PROFILE, {}) or {}
    if not data and remote_type == "localtuya":
        if not device_code or not os.path.isfile(device_code):
            await _notify(
                hass,
                f"❌ JSON file not found: {device_code}",
                nid=f"{DOMAIN}_json_{unique_id}",
            )
        else:
            try:
                async with aiofiles.open(device_code, "r", encoding="utf-8") as f:
                    data = json.loads(await f.read())
            except Exception as e:
                await _notify(
                    hass,
                    f"❌ Failed to parse JSON {device_code}: {e}",
                    nid=f"{DOMAIN}_jsonparse_{unique_id}",
                )

    async_add_entities(
        [
            SmartRemoteClimate(
                hass,
                name,
                unique_id,
                data,
                remote_type,
                config,
            )
        ],
        True,
    )


# ---------------------- ExtraStoredData สำหรับ persist/restore ----------------------

@dataclass
class SmartRemoteExtraStoredData(ExtraStoredData):
    hvac_mode: str
    hvac_action: str
    target_temperature: float | None
    fan_mode: str | None
    swing_mode: str | None
    preset_mode: str | None

    def as_dict(self) -> dict[str, any]:
        return {
            "hvac_mode": self.hvac_mode,
            "hvac_action": self.hvac_action,
            "temperature": self.target_temperature,
            "fan_mode": self.fan_mode,
            "swing_mode": self.swing_mode,
            "preset_mode": self.preset_mode,
        }

    @classmethod
    def from_dict(cls, restored: dict[str, any]) -> Optional["SmartRemoteExtraStoredData"]:
        if not restored:
            return None
        return cls(
            restored.get("hvac_mode", "off"),
            restored.get("hvac_action", "off"),
            restored.get("temperature"),
            restored.get("fan_mode"),
            restored.get("swing_mode"),
            restored.get("preset_mode"),
        )

# ---------------------- Entity หลัก ----------------------

class SmartRemoteClimate(ClimateEntity, RestoreEntity):
    _attr_should_poll = False

    def __init__(self, hass, name, unique_id, data, remote_type, config):
        self.hass = hass
        self._attr_name = name
        self._attr_unique_id = unique_id
        self._data = data  # IR profile for database-backed transmitters
        self._remote = RemoteControl(
            hass,
            remote_type,
            config.get(CONF_MQTT_TOPIC),
            config.get(CONF_REMOTE_ENTITY),
            config.get(CONF_DEVICE_ID),
            config.get(CONF_DP),
            config.get(CONF_HA_DEVICE_ID),
            (data or {}).get("commandsEncoding") if isinstance(data, dict) else None,
        )
        self._remote_type = remote_type
        self._ha_device_id = config.get(CONF_HA_DEVICE_ID)
        # HA Remote learned-command grouping (same semantics as upstream climate-remote-control)
        self._grouping_attributes = list(config.get(CONF_GROUPING_ATTRIBUTES, []) or [])
        self._grouping_attributes_as_sequence = bool(config.get(CONF_GROUPING_ATTRIBUTES_AS_SEQUENCE, False))

        # Home Assistant display temperature unit.
        self._attr_temperature_unit = hass.config.units.temperature_unit

        # ----- Climate settings -----
        # HA Remote uses ConfigFlow values. Database transmitters use the uploaded profile as source of truth.
        temp_conf = config.get(CONF_TEMPERATURE, {})
        if self._data and remote_type in ("broadlink", "zigbee2mqtt", "localtuya"):
            self._attr_target_temperature_step = float(self._data.get("precision", 1.0))
            self._attr_min_temp = float(self._data.get("minTemperature", 16.0))
            self._attr_max_temp = float(self._data.get("maxTemperature", 30.0))
            self._attr_target_temperature = max(self._attr_min_temp, min(24.0, self._attr_max_temp))
        else:
            self._attr_target_temperature_step = float(temp_conf.get(CONF_TEMPERATURE_STEP, 1.0))
            self._attr_min_temp = temp_conf.get("min", 16.0)
            self._attr_max_temp = temp_conf.get("max", 30.0)
            self._attr_target_temperature = temp_conf.get("default", 24.0)

        # Supported features
        self._attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE

        # Fan modes
        self._attr_fan_modes = []
        fan_conf = config.get(CONF_FAN_MODES, {})
        if self._data and remote_type in ("broadlink", "zigbee2mqtt", "localtuya"):
            self._attr_fan_modes = list(self._data.get("fanModes", []))
        elif fan_conf:
            self._attr_fan_modes = fan_conf.get("modes", [])
        if self._attr_fan_modes:
            self._attr_supported_features |= ClimateEntityFeature.FAN_MODE
            self._attr_fan_mode = self._attr_fan_modes[0]
        else:
            self._attr_fan_mode = None

        # Swing modes
        swing_conf = config.get(CONF_SWING, {})
        if self._data and remote_type in ("broadlink", "zigbee2mqtt", "localtuya"):
            self._attr_swing_modes = list(self._data.get("swingModes", []))
        else:
            self._attr_swing_modes = swing_conf.get("modes", []) if swing_conf else []
        if self._attr_swing_modes:
            self._attr_supported_features |= ClimateEntityFeature.SWING_MODE
            self._attr_swing_mode = self._attr_swing_modes[0]
        else:
            self._attr_swing_mode = None

        # HVAC modes
        hvac_conf = config.get(CONF_HVAC_MODES, {})
        if self._data and remote_type in ("broadlink", "zigbee2mqtt", "localtuya"):
            hvac_modes = list(self._data.get("operationModes", []))
        else:
            hvac_modes = hvac_conf.get("modes", [])
        self._attr_hvac_modes = [HVACMode.OFF] + hvac_modes
        self._hvac_mode = HVACMode.OFF
        self._hvac_action = HVACAction.OFF

        # Preset modes configured by Config Flow / Options Flow.
        preset_conf = config.get("preset_modes", {})
        if self._data and remote_type in ("broadlink", "zigbee2mqtt", "localtuya"):
            configured_preset_modes = list(self._data.get("presetModes", []))
        else:
            configured_preset_modes = preset_conf.get("modes", []) if preset_conf else []

        # "none" is the Climate entity's neutral/default preset state.  Users
        # configure only real device presets; when at least one exists, expose
        # "none" automatically without requiring an IR command for it.
        if configured_preset_modes:
            self._attr_preset_modes = [
                "none", *[mode for mode in configured_preset_modes if mode != "none"]
            ]
            self._attr_supported_features |= ClimateEntityFeature.PRESET_MODE
            self._attr_preset_mode = "none"
        else:
            self._attr_preset_modes = []
            self._attr_preset_mode = None

        # Sensors
        self._attr_current_temperature = None
        self._attr_current_humidity = None
        self._temp_sensor = config.get(CONF_TEMPERATURE_SENSOR)
        self._hum_sensor = config.get(CONF_HUMIDITY_SENSOR)
        self._power_sensor = config.get(CONF_POWER_SENSOR)

        # Initial sensor read
        if self._temp_sensor:
            state = hass.states.get(self._temp_sensor)
            if state and state.state not in (STATE_UNKNOWN, STATE_UNAVAILABLE):
                try:
                    self._attr_current_temperature = float(state.state)
                except ValueError:
                    pass
        if self._hum_sensor:
            state = hass.states.get(self._hum_sensor)
            if state and state.state not in (STATE_UNKNOWN, STATE_UNAVAILABLE):
                try:
                    self._attr_current_humidity = float(state.state)
                except ValueError:
                    pass

        self._send_lock = asyncio.Lock()
        # IR transmit coordinator: keep physical transmissions apart and let the
        # newest pending state win when users change Climate controls rapidly.
        self._min_send_interval = MIN_SEND_INTERVAL
        self._last_tx_time = None
        self._send_generation = 0

    async def async_added_to_hass(self):
        last = await self.async_get_last_state()
        if last:
            self._hvac_mode = restore_hvac_mode(
                last.attributes.get("hvac_mode", HVACMode.OFF), self._attr_hvac_modes
            )
            self._attr_target_temperature = normalize_temperature(
                last.attributes.get("temperature"), self._attr_min_temp, self._attr_max_temp,
                self._attr_target_temperature_step, self._attr_target_temperature
            )
            self._attr_fan_mode = restore_choice(
                last.attributes.get("fan_mode"), self._attr_fan_modes, self._attr_fan_mode
            )
            self._attr_swing_mode = restore_choice(
                last.attributes.get("swing_mode"), self._attr_swing_modes, self._attr_swing_mode
            )

        # restore จาก ExtraStoredData
        last_extra = await self.async_get_last_extra_data()
        if last_extra:
            data = SmartRemoteExtraStoredData.from_dict(last_extra.as_dict())
            if data:
                self._hvac_mode = restore_hvac_mode(data.hvac_mode, self._attr_hvac_modes)
                self._attr_target_temperature = normalize_temperature(
                    data.target_temperature, self._attr_min_temp, self._attr_max_temp,
                    self._attr_target_temperature_step, self._attr_target_temperature
                )
                self._attr_fan_mode = restore_choice(data.fan_mode, self._attr_fan_modes, self._attr_fan_mode)
                self._attr_swing_mode = restore_choice(data.swing_mode, self._attr_swing_modes, self._attr_swing_mode)
                self._attr_preset_mode = restore_choice(data.preset_mode, self._attr_preset_modes, self._attr_preset_mode)

        if self._temp_sensor:
            self.async_on_remove(async_track_state_change_event(
                self.hass, self._temp_sensor, self._async_temp_sensor_changed
            ))
        if self._hum_sensor:
            self.async_on_remove(async_track_state_change_event(
                self.hass, self._hum_sensor, self._async_humidity_sensor_changed
            ))
        if self._power_sensor:
            self.async_on_remove(async_track_state_change_event(
                self.hass, self._power_sensor, self._async_power_sensor_changed
            ))

        self._update_hvac_action()
        self.async_write_ha_state()


    @property
    def extra_restore_state_data(self):
        """Persist extra data across restarts (hvac_action, temp, fan, swing)."""
        return SmartRemoteExtraStoredData(
            self._hvac_mode,
            self._hvac_action,
            self._attr_target_temperature,
            self._attr_fan_mode,
            self._attr_swing_mode,
            self._attr_preset_mode,
        )

    # ---------------- (ที่เหลือของ class SmartRemoteClimate เดิมคงไว้) ----------------
    def _update_hvac_action(self):
        """Estimate HVAC action from mode and optional temperature feedback."""
        previous_action = self._hvac_action
        action = estimate_hvac_action(
            self._hvac_mode,
            self._attr_current_temperature,
            self._attr_target_temperature,
            has_temperature_sensor=self._temp_sensor is not None,
        )
        self._hvac_action = HVACAction(action)
        if previous_action != self._hvac_action:
            _LOGGER.debug(
                "[HVAC Action] %s: %s -> %s (mode=%s, current=%s, target=%s)",
                self._attr_name, previous_action, self._hvac_action, self._hvac_mode,
                self._attr_current_temperature, self._attr_target_temperature,
            )

    # --------- HA Remote learned-command naming (upstream-compatible) ---------
    def _ha_attr_command(self, key: str) -> str:
        """Return one learned-command component for the current climate state."""
        return build_ha_attr_command(
            key,
            hvac_mode=self._hvac_mode,
            fan_mode=self._attr_fan_mode,
            swing_mode=self._attr_swing_mode,
            temperature=self._attr_target_temperature,
            preset_mode=self._attr_preset_mode,
        )

    def _ha_commands_for(self, changed_key: str) -> list[str]:
        """Build command(s) exactly from Grouping Attributes."""
        return build_ha_commands(
            changed_key,
            self._grouping_attributes,
            grouping_as_sequence=self._grouping_attributes_as_sequence,
            hvac_mode=self._hvac_mode,
            fan_mode=self._attr_fan_mode,
            swing_mode=self._attr_swing_mode,
            temperature=self._attr_target_temperature,
            preset_mode=self._attr_preset_mode,
        )

    async def _wait_tx_slot(self):
        """Enforce the minimum gap between physical IR transmissions."""
        loop = asyncio.get_running_loop()
        now = loop.time()
        if self._last_tx_time is not None:
            remaining = self._min_send_interval - (now - self._last_tx_time)
            if remaining > 0:
                await asyncio.sleep(remaining)
        # Reserve the slot before the service call. Even a missing HA learned
        # command counts as an attempted ON, so the following full-state command
        # is still delayed instead of being fired immediately.
        self._last_tx_time = loop.time()

    async def _send_ha_learned_command(self, command):
        """Send a learned HA Remote command and report missing device/command errors."""
        await self._wait_tx_slot()
        try:
            await self.hass.services.async_call(
                "remote",
                "send_command",
                {
                    "entity_id": self._remote.remote_entity,
                    "device": self._ha_device_id,
                    "command": command,
                },
                blocking=True,
            )
            return True
        except Exception as err:
            command_text = ", ".join(command) if isinstance(command, list) else str(command)
            _LOGGER.warning(
                'Command "%s" for device "%s" could not be sent via %s. '
                'Check that the device and command have been learned. Error: %s',
                command_text,
                self._ha_device_id,
                self._remote.remote_entity,
                err,
            )
            await _notify(
                self.hass,
                (
                    f'IR command `{command_text}` for device `{self._ha_device_id}` '
                    f'could not be sent via `{self._remote.remote_entity}`.\n\n'
                    'Check that the device and command have been learned in Home Assistant.'
                ),
                nid=f"{DOMAIN}_ha_command_{self._attr_unique_id}",
            )
            return False

    # --------- ด้านล่างนี่คือ logic เดิมทั้งหมด (คงไว้ครบ) ---------
    async def _send_ir(self, mode, fan_mode, temp, prev_mode, changed_key="hvac_mode"):
        # Each request gets a generation number. While one transmission is in
        # progress, newer ordinary state changes supersede older queued ones.
        # Power transitions are never discarded.
        self._send_generation += 1
        generation = self._send_generation
        power_transition = is_power_transition(prev_mode, mode)

        async with self._send_lock:
            if should_drop_as_superseded(
                power_transition=power_transition,
                generation=generation,
                latest_generation=self._send_generation,
            ):
                _LOGGER.debug(
                    "Skipping superseded IR state for %s (changed=%s)",
                    self._attr_name, changed_key,
                )
                return
            try:
                if self._remote_type == "ha_remote":
                    # ha_remote: ใช้ HA remote entity ไม่แตะ JSON
                    if not self._ha_device_id or not self._remote.remote_entity:
                        await _notify(
                            self.hass,
                            f"❌ ha_remote missing ha_device_id or remote_entity for {self._attr_name}",
                            nid=f"{DOMAIN}_ha_cfg_{self._attr_unique_id}",
                        )
                        return
                    # OFF -> ON: always attempt the learned "on" command first.
                    # If it was never learned, _send_ha_learned_command notifies
                    # the user, but we still continue with the remembered/current
                    # full-state command because that IR command may power on the AC.
                    if prev_mode == HVACMode.OFF and mode != HVACMode.OFF:
                        await self._send_ha_learned_command("on")
                        await asyncio.sleep(POWER_ON_SETTLE_DELAY)

                    if mode == HVACMode.OFF:
                        commands = ["off"]
                    else:
                        # Grouping Attributes defines the learned-command name.
                        # Example: mode_fan_temp -> mode:cool_fan:high_temp:24.0
                        commands = self._ha_commands_for(changed_key)
                        if not commands:
                            # Standalone Preset "none" intentionally has no
                            # learned command; it only clears the Climate state.
                            if changed_key == "preset_mode" and self._attr_preset_mode == "none":
                                return
                            _LOGGER.warning("No HA learned command could be built for %s", changed_key)
                            return

                    command_to_send = (
                        commands
                        if self._grouping_attributes_as_sequence and len(commands) > 1
                        else commands[0]
                    )
                    if not await self._send_ha_learned_command(command_to_send):
                        return

                else:
                    # Broadlink/Zigbee2MQTT/LocalTuya → use uploaded JSON IR profile
                    cmd = None

                    # OFF -> ON: an explicit profile commands.on is optional.
                    # When present, send it first; the coordinator guarantees the
                    # power-on settle gap before the remembered/current full-state command.
                    if prev_mode == HVACMode.OFF and mode != HVACMode.OFF:
                        on_cmd = optional_profile_on(self._data)
                        if on_cmd:
                            await self._wait_tx_slot()
                            await self._remote.send_command(on_cmd)
                            await asyncio.sleep(POWER_ON_SETTLE_DELAY)

                    # Resolve standalone/full-state Swing/Preset and the full-state
                    # HVAC/Fan/Temperature tree through one pure, regression-tested helper.
                    cmd, resolve_error = resolve_command(
                        self._data,
                        hvac_mode=str(mode),
                        fan_mode=fan_mode,
                        temperature=temp,
                        swing_mode=self._attr_swing_mode,
                        preset_mode=self._attr_preset_mode,
                        changed_key=changed_key,
                        temperature_step=self._attr_target_temperature_step or 1,
                    )
                    if resolve_error:
                        await _notify(
                            self.hass,
                            f"❌ {resolve_error}",
                            nid=f"{DOMAIN}_json_resolve_{self._attr_unique_id}",
                        )
                        return
                    # A neutral standalone preset `none` may intentionally have no IR command.
                    if cmd is None:
                        return

                    # ✅ ตรวจว่า JSON ระบุ protocol หรือไม่
                    if isinstance(self._data, dict):
                        proto = self._data.get("protocol")
                        encoding = self._data.get("commandsEncoding")
                    else:
                        proto = None
                        encoding = None

                    # ✅ ถ้ามี protocol → สร้าง payload ให้ตรงกับ ESP32/IR Gateway
                    await self._wait_tx_slot()
                    if proto and encoding and encoding.upper() == "HEX":
                        payload = {"protocol": proto, "code": cmd}
                        await self._remote.send_command(payload)
                    else:
                    # fallback: ส่งแบบเดิม (เช่น zigbee2mqtt base64/raw)
                        await self._remote.send_command(cmd)

            except RemoteConfigurationError as err:
                _LOGGER.error("IR transmitter configuration error: %s", err)
                await _notify(
                    self.hass,
                    f"Transmitter configuration error: {err}",
                    nid=f"{DOMAIN}_senderr_{self._attr_unique_id}",
                )
            except RemoteEncodingError as err:
                _LOGGER.error("IR command encoding error: %s", err)
                await _notify(
                    self.hass,
                    f"IR command encoding error: {err}",
                    nid=f"{DOMAIN}_senderr_{self._attr_unique_id}",
                )
            except RemoteTransportError as err:
                _LOGGER.error("IR transmitter communication error: %s", err)
                await _notify(
                    self.hass,
                    f"Transmitter communication error: {err}",
                    nid=f"{DOMAIN}_senderr_{self._attr_unique_id}",
                )
            except Exception as err:
                # Last-resort guard: a Climate entity must not crash because of an
                # unexpected transmitter failure. Keep the traceback for diagnostics.
                _LOGGER.exception("Unexpected error while sending IR command")
                await _notify(
                    self.hass,
                    f"Unexpected error while sending IR command: {err}",
                    nid=f"{DOMAIN}_senderr_{self._attr_unique_id}",
                )

    @callback
    def _async_temp_sensor_changed(self, event: Event[EventStateChangedData]):
        new = event.data.get("new_state")
        if new and new.state not in (STATE_UNKNOWN, STATE_UNAVAILABLE):
            try:
                self._attr_current_temperature = float(new.state)
            except ValueError:
                return
            self._update_hvac_action()
            self.async_write_ha_state()

    @callback
    def _async_humidity_sensor_changed(self, event: Event[EventStateChangedData]):
        new = event.data.get("new_state")
        if new and new.state not in (STATE_UNKNOWN, STATE_UNAVAILABLE):
            try:
                self._attr_current_humidity = float(new.state)
            except ValueError:
                return
            self.async_write_ha_state()

    @callback
    def _async_power_sensor_changed(self, event: Event[EventStateChangedData]):
        """Sync climate with external power sensor (optional, delay before off)."""
        # ถ้าไม่ได้ตั้งค่า power sensor → ทำงานปกติ ไม่บังคับ override
        if not self._power_sensor:
            return

        new = event.data.get("new_state")
        if not new or new.state in (STATE_UNKNOWN, STATE_UNAVAILABLE):
            return

        power_state = new.state.lower()
        prev_mode = getattr(self, "_hvac_mode", HVACMode.OFF)

        # 🟢 Power ON → ถ้า climate เดิมคือ OFF → restore mode เดิม (หรือ COOL)
        if power_state == "on":
            if prev_mode == HVACMode.OFF:
                restore_mode = getattr(self, "_last_active_mode", HVACMode.COOL)
                self._hvac_mode = restore_mode
                self._attr_hvac_mode = restore_mode
                self._update_hvac_action()
                _LOGGER.info(
                    "🟢 [Power Sync] %s Power sensor ON → restore climate to %s",
                    self._attr_name,
                    restore_mode,
                )
                self.async_write_ha_state()
            return

        # 🔴 Power OFF → รอดู 5 วิ ก่อนปิดจริง (กันกรณี sensor ส่งค่าผิด)
        if power_state == "off":
            async def _delayed_off_check():
                await asyncio.sleep(5)
                state = self.hass.states.get(self._power_sensor)
                if state and state.state.lower() == "off":
                    self._hvac_mode = HVACMode.OFF
                    self._attr_hvac_mode = HVACMode.OFF
                    self._hvac_action = HVACAction.OFF
                    self._update_hvac_action()
                    self.async_write_ha_state()
                    _LOGGER.warning(
                        "🔴 [Power Sync] %s Power sensor OFF confirmed after 5s → force climate OFF",
                        self._attr_name,
                    )
                else:
                    _LOGGER.debug(
                        "🟡 [Power Sync] %s Power OFF canceled (sensor back ON)",
                        self._attr_name,
                    )

            self.hass.async_create_task(_delayed_off_check())

        # 📝 บันทึก mode ล่าสุดไว้ใช้ตอนกลับมาเปิดใหม่
        if self._hvac_mode != HVACMode.OFF:
            self._last_active_mode = self._hvac_mode

        self._update_hvac_action()
        self.async_write_ha_state()

    async def async_set_hvac_mode(self, hvac_mode):
        """Handle change of HVAC mode (user or automation)."""
        prev = self._hvac_mode
        self._hvac_mode = hvac_mode

        # อัปเดต action ภายในก่อน
        self._update_hvac_action()
        self.async_write_ha_state()

        try:
            # ส่ง IR ตามโหมดที่เลือก
            await self._send_ir(
                hvac_mode, self._attr_fan_mode, self._attr_target_temperature, prev, "hvac_mode"
            )

            # ✅ หลังส่ง IR แล้ว → ตั้ง watchdog 5 วิ เช็ค power sensor
            if self._power_sensor and hvac_mode != HVACMode.OFF:
                async def _check_power_sensor_later():
                    await asyncio.sleep(5)
                    state = self.hass.states.get(self._power_sensor)
                    if not state or state.state.lower() != "off":
                        _LOGGER.debug("🟢 [Power Watchdog] %s OK: power sensor=%s", self._attr_name, state.state if state else "unknown")
                        return

                    # 🔁 double-check อีกทีหลัง 2 วิ กันกรณี sensor delay
                    await asyncio.sleep(2)
                    state2 = self.hass.states.get(self._power_sensor)
                    if state2 and state2.state.lower() == "off":
                        _LOGGER.warning(
                            "⚠️ [Power Watchdog] %s Power sensor still OFF after 7s → forcing climate OFF",
                            self._attr_name,
                        )
                        self._hvac_mode = HVACMode.OFF
                        self._attr_hvac_mode = HVACMode.OFF
                        self._hvac_action = HVACAction.OFF
                        self.async_write_ha_state()
                    else:
                        _LOGGER.info("🟢 [Power Watchdog] %s Power ON detected late → keep running", self._attr_name)

                self.hass.async_create_task(_check_power_sensor_later())

            # ✅ หลังส่งเสร็จ อัปเดตสถานะใหม่อีกครั้ง เพื่อกัน revert
            self._update_hvac_action()
            self.async_write_ha_state()

            _LOGGER.info(
                "🔁 HVAC mode changed → %s (prev=%s) for %s",
                hvac_mode,
                prev,
                self._attr_name,
            )
        except Exception as e:
            _LOGGER.error("❌ Failed to change HVAC mode %s: %s", hvac_mode, e)

    async def async_set_fan_mode(self, fan_mode):
        self._attr_fan_mode = fan_mode
        self._update_hvac_action()
        self.async_write_ha_state()
        self.hass.async_create_task(
            self._send_ir(
                self._hvac_mode, fan_mode, self._attr_target_temperature, self._hvac_mode, "fan_mode"
            )
        )

    async def async_set_swing_mode(self, swing_mode):
        self._attr_swing_mode = swing_mode
        self._update_hvac_action()
        self.async_write_ha_state()
        self.hass.async_create_task(
            self._send_ir(
                self._hvac_mode, self._attr_fan_mode, self._attr_target_temperature, self._hvac_mode, "swing_mode"
            )
        )

    async def async_set_temperature(self, **kwargs):
        t = kwargs.get(ATTR_TEMPERATURE)
        if isinstance(t, Number):
            t = normalize_temperature(
                t, self._attr_min_temp, self._attr_max_temp,
                self._attr_target_temperature_step, self._attr_target_temperature
            )
            prev = self._hvac_mode
            self._attr_target_temperature = t
            self._update_hvac_action()
            self.async_write_ha_state()
            self.hass.async_create_task(
                self._send_ir(self._hvac_mode, self._attr_fan_mode, t, prev, "temperature")
            )

    async def async_set_preset_mode(self, preset_mode):
        """Handle preset mode changes."""
        if preset_mode not in self._attr_preset_modes:
            await _notify(
                self.hass,
                f"⚠️ Unsupported preset mode: {preset_mode}",
                nid=f"{DOMAIN}_preset_{self._attr_unique_id}",
            )
            return

        self._attr_preset_mode = preset_mode
        self.async_write_ha_state()

        if self._remote_type == "ha_remote":
            # Grouping Attributes decides whether Preset is part of the
            # full-state learned command or a standalone preset:<mode> command.
            self.hass.async_create_task(
                self._send_ir(
                    self._hvac_mode,
                    self._attr_fan_mode,
                    self._attr_target_temperature,
                    self._hvac_mode,
                    "preset_mode",
                )
            )
        else:
            # Broadlink/Zigbee2MQTT profiles decide whether Preset is a
            # full-state branch or an independent standalone IR command.
            self.hass.async_create_task(
                self._send_ir(
                    self._hvac_mode,
                    self._attr_fan_mode,
                    self._attr_target_temperature,
                    self._hvac_mode,
                    "preset_mode",
                )
            )

    @property
    def hvac_mode(self):
        return self._hvac_mode

    @property
    def hvac_action(self):
        return self._hvac_action

    @property
    def current_temperature(self):
        return self._attr_current_temperature

    @property
    def current_humidity(self):
        return self._attr_current_humidity

    @property
    def device_info(self):
        return DeviceInfo(
            identifiers={(DOMAIN, self._attr_unique_id)},
            name=self._attr_name,
            manufacturer="Smart Remote Control",
        )

    @property
    def extra_state_attributes(self):
        """Expose extra attributes to HA so they get stored in last_state."""
        return {
            "hvac_action": self._hvac_action,
        }
