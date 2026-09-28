"""Config flow for Smart Remote Control."""
from __future__ import annotations

import json
from typing import Any
from uuid import uuid4

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.components.file_upload import process_uploaded_file
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import selector

from .const import (
    DOMAIN, CONF_DEVICE_PROFILE, CONF_PROFILE_FILE, CONF_REMOTE_TYPE, CONF_TARGET,
    CONF_TEMPERATURE, CONF_TEMPERATURE_STEP, CONF_FAN_MODES, CONF_PRESET_MODES,
    CONF_SWING, CONF_HVAC_MODES, CONF_GROUPING_ATTRIBUTES,
    CONF_GROUPING_ATTRIBUTES_AS_SEQUENCE, CONF_TEMPERATURE_SENSOR,
    CONF_HUMIDITY_SENSOR, CONF_POWER_SENSOR, CONF_REMOTE_ENTITY,
    CONF_HA_DEVICE_ID, CONF_MQTT_TOPIC, CONF_DEVICE_ID, CONF_DP,
    CONF_DEVICE_TYPE, CONF_REMOTE_BACKEND, CONF_IR_PREFIX,
)
from .localtuya_discovery import discover_localtuya_devices, recommended_dp
from .profile_validator import profile_summary, validate_climate_profile

FAN_OPTIONS = ["auto", "low", "medium", "high", "quiet", "turbo", "strong", "on", "off"]


def _opt_with_suggest(key: Any, value: Any | None):
    if value is None or value == "":
        return vol.Optional(key)
    return vol.Optional(key, description={"suggested_value": value})


def _schema_user(defaults=None):
    d = defaults or {}
    return vol.Schema({
        vol.Required("name", default=d.get("name", "")): cv.string,
        vol.Required(CONF_DEVICE_TYPE, default=d.get(CONF_DEVICE_TYPE, "climate")): selector.SelectSelector(
            selector.SelectSelectorConfig(options=[
                selector.SelectOptionDict(value="climate", label="Climate"),
                selector.SelectOptionDict(value="remote", label="Remote"),
            ], mode=selector.SelectSelectorMode.DROPDOWN)
        ),
    })


def _schema_climate_transmitter(defaults=None):
    d = defaults or {}
    return vol.Schema({
        vol.Required(CONF_REMOTE_TYPE, default=d.get(CONF_REMOTE_TYPE, "ha_remote")): selector.SelectSelector(
            selector.SelectSelectorConfig(options=[
                selector.SelectOptionDict(value="ha_remote", label="Home Assistant Remote"),
                selector.SelectOptionDict(value="broadlink", label="Broadlink"),
                selector.SelectOptionDict(value="zigbee2mqtt", label="Zigbee2MQTT"),
                selector.SelectOptionDict(value="localtuya", label="LocalTuya Direct IR"),
            ], mode=selector.SelectSelectorMode.DROPDOWN)
        ),
    })


def _schema_remote_backend(defaults=None):
    d = defaults or {}
    return vol.Schema({
        vol.Required(CONF_REMOTE_BACKEND, default=d.get(CONF_REMOTE_BACKEND, "mqtt")): selector.SelectSelector(
            selector.SelectSelectorConfig(options=[
                selector.SelectOptionDict(value="mqtt", label="MQTT"),
                selector.SelectOptionDict(value="localtuya", label="LocalTuya Direct IR"),
            ], mode=selector.SelectSelectorMode.DROPDOWN)
        ),
    })


def _schema_remote_mqtt(defaults=None):
    d=defaults or {}
    return vol.Schema({vol.Required(CONF_MQTT_TOPIC,default=d.get(CONF_MQTT_TOPIC,"")):cv.string, vol.Optional(CONF_IR_PREFIX,default=d.get(CONF_IR_PREFIX,"")):cv.string})

def _schema_remote_prefix(defaults=None):
    d=defaults or {}
    return vol.Schema({vol.Optional(CONF_IR_PREFIX,default=d.get(CONF_IR_PREFIX,"")):cv.string})


def _schema_target(defaults=None):
    d = defaults or {}
    return vol.Schema({
        vol.Required("entity_id", default=d.get("entity_id") or d.get(CONF_REMOTE_ENTITY, "")): selector.EntitySelector(selector.EntitySelectorConfig(domain="remote")),
        vol.Required("ha_device_id", default=d.get("ha_device_id") or d.get(CONF_HA_DEVICE_ID, "")): cv.string,
    })


def _schema_broadlink(defaults=None):
    d = defaults or {}
    return vol.Schema({
        vol.Required("entity_id", default=d.get("entity_id", "")): selector.EntitySelector(selector.EntitySelectorConfig(domain="remote")),
    })


def _schema_z2m(defaults=None):
    d = defaults or {}
    return vol.Schema({vol.Required(CONF_MQTT_TOPIC, default=d.get(CONF_MQTT_TOPIC, "")): cv.string})


def _schema_localtuya_device(devices, defaults=None):
    d = defaults or {}
    options = [selector.SelectOptionDict(value=x.device_id, label=f"{x.name} ({x.device_id})") for x in devices]
    current = d.get(CONF_DEVICE_ID, "")
    if current and current not in {x.device_id for x in devices}:
        options.append(selector.SelectOptionDict(value=current, label=f"Current device ({current})"))
    if options:
        return vol.Schema({
            vol.Required(CONF_DEVICE_ID, default=current or devices[0].device_id): selector.SelectSelector(
                selector.SelectSelectorConfig(options=options, mode=selector.SelectSelectorMode.DROPDOWN)
            )
        })
    return vol.Schema({vol.Required(CONF_DEVICE_ID, default=current): cv.string})


def _schema_localtuya_dp(device, defaults=None):
    d = defaults or {}
    known = list(device.dps) if device else []
    current = d.get(CONF_DP)
    default_dp = int(current) if current not in (None, "") else (recommended_dp(known) or (known[0] if known else 201))
    options = []
    for dp in known:
        label = f"{dp} (Recommended)" if dp == 201 else str(dp)
        options.append(selector.SelectOptionDict(value=str(dp), label=label))
    if str(default_dp) not in {str(x) for x in known}:
        options.append(selector.SelectOptionDict(value=str(default_dp), label=f"{default_dp} (Manual)"))
    return vol.Schema({
        vol.Required(CONF_DP, default=str(default_dp)): selector.SelectSelector(
            selector.SelectSelectorConfig(options=options, custom_value=True, mode=selector.SelectSelectorMode.DROPDOWN)
        )
    })

def _schema_profile_upload():
    return vol.Schema({
        vol.Required(CONF_PROFILE_FILE): selector.FileSelector(selector.FileSelectorConfig(accept=".json,application/json"))
    })


def _schema_temperature(defaults=None):
    d = defaults or {}
    return vol.Schema({
        vol.Required("mode", default=d.get("mode", "target")): selector.SelectSelector(selector.SelectSelectorConfig(options=[selector.SelectOptionDict(value="none", label="None"), selector.SelectOptionDict(value="target", label="Target"), selector.SelectOptionDict(value="range", label="Range")], multiple=False, mode=selector.SelectSelectorMode.DROPDOWN)),
        vol.Required("min", default=d.get("min", 16.0)): vol.Coerce(float),
        vol.Required("max", default=d.get("max", 30.0)): vol.Coerce(float),
        vol.Required("temperature_unit", default=d.get("temperature_unit", "c")): selector.SelectSelector(selector.SelectSelectorConfig(options=[selector.SelectOptionDict(value="c", label="Celsius"), selector.SelectOptionDict(value="f", label="Fahrenheit")], multiple=False, mode=selector.SelectSelectorMode.DROPDOWN)),
        vol.Required(CONF_TEMPERATURE_STEP, default=d.get(CONF_TEMPERATURE_STEP, 1.0)): vol.Coerce(float),
    })

def _schema_swing(defaults=None):
    """Select the Swing modes exposed by the Climate entity.

    HA Remote command grouping is configured separately on the Grouping
    Attributes step. An empty list means that Swing is not supported.
    """
    d = defaults or {}
    return vol.Schema({
        vol.Optional("modes", default=d.get("modes", [])): selector.SelectSelector(selector.SelectSelectorConfig(options=[selector.SelectOptionDict(value="on", label="On"), selector.SelectOptionDict(value="off", label="Off"), selector.SelectOptionDict(value="both", label="Both"), selector.SelectOptionDict(value="vertical", label="Vertical"), selector.SelectOptionDict(value="horizontal", label="Horizontal")], multiple=True, mode=selector.SelectSelectorMode.DROPDOWN)),
    })

def _schema_hvac(defaults=None):
    d = defaults or {}
    return vol.Schema({vol.Required("modes", default=d.get("modes", [])): selector.SelectSelector(selector.SelectSelectorConfig(options=[selector.SelectOptionDict(value="heat", label="Heat"), selector.SelectOptionDict(value="cool", label="Cool"), selector.SelectOptionDict(value="heat_cool", label="Heat/Cool"), selector.SelectOptionDict(value="auto", label="Auto"), selector.SelectOptionDict(value="dry", label="Dry"), selector.SelectOptionDict(value="fan_only", label="Fan Only")], multiple=True, mode=selector.SelectSelectorMode.DROPDOWN))})

def _schema_fan(defaults=None):
    d = defaults or {}
    return vol.Schema({vol.Optional("modes", default=d.get("modes", [])): selector.SelectSelector(selector.SelectSelectorConfig(options=[selector.SelectOptionDict(value="auto", label="Auto"), selector.SelectOptionDict(value="low", label="Low"), selector.SelectOptionDict(value="medium", label="Medium"), selector.SelectOptionDict(value="high", label="High"), selector.SelectOptionDict(value="quiet", label="Quiet"), selector.SelectOptionDict(value="turbo", label="Turbo"), selector.SelectOptionDict(value="strong", label="Strong"), selector.SelectOptionDict(value="on", label="On"), selector.SelectOptionDict(value="off", label="Off")], multiple=True, mode=selector.SelectSelectorMode.DROPDOWN))})

def _schema_grouping(defaults=None):
    """Build HA learned-command names, e.g. mode:cool_fan:high_temp:24.0."""
    d = defaults or {}
    return vol.Schema({
        vol.Optional(CONF_GROUPING_ATTRIBUTES, default=d.get(CONF_GROUPING_ATTRIBUTES, [])): selector.SelectSelector(selector.SelectSelectorConfig(options=[selector.SelectOptionDict(value="hvac_mode", label="HVAC mode"), selector.SelectOptionDict(value="fan_mode", label="Fan mode"), selector.SelectOptionDict(value="swing_mode", label="Swing mode"), selector.SelectOptionDict(value="temperature", label="Temperature"), selector.SelectOptionDict(value="preset_mode", label="Preset mode")], multiple=True, mode=selector.SelectSelectorMode.DROPDOWN)),
        vol.Optional(CONF_GROUPING_ATTRIBUTES_AS_SEQUENCE, default=d.get(CONF_GROUPING_ATTRIBUTES_AS_SEQUENCE, False)): selector.BooleanSelector(),
    })

def _schema_sensors(defaults=None):
    d = defaults or {}
    schema = {}
    schema[_opt_with_suggest(CONF_TEMPERATURE_SENSOR, d.get(CONF_TEMPERATURE_SENSOR))] = selector.EntitySelector(selector.EntitySelectorConfig(domain="sensor", device_class="temperature"))
    schema[_opt_with_suggest(CONF_HUMIDITY_SENSOR, d.get(CONF_HUMIDITY_SENSOR))] = selector.EntitySelector(selector.EntitySelectorConfig(domain="sensor", device_class="humidity"))
    schema[_opt_with_suggest(CONF_POWER_SENSOR, d.get(CONF_POWER_SENSOR))] = selector.EntitySelector(selector.EntitySelectorConfig(domain="binary_sensor"))
    return vol.Schema(schema)


def _schema_preset(defaults=None):
    d = defaults or {}
    return vol.Schema({vol.Optional("modes", default=d.get("modes", [])): selector.SelectSelector(selector.SelectSelectorConfig(options=[selector.SelectOptionDict(value="eco", label="Eco"), selector.SelectOptionDict(value="away", label="Away"), selector.SelectOptionDict(value="boost", label="Boost"), selector.SelectOptionDict(value="comfort", label="Comfort"), selector.SelectOptionDict(value="sleep", label="Sleep"), selector.SelectOptionDict(value="activity", label="Activity"), selector.SelectOptionDict(value="silent", label="Silent"), selector.SelectOptionDict(value="turbo", label="Turbo"), selector.SelectOptionDict(value="home", label="Home"), selector.SelectOptionDict(value="auto", label="Auto")], multiple=True, mode=selector.SelectSelectorMode.DROPDOWN))})

class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 3

    def __init__(self):
        self._data: dict[str, Any] = {}
        self._profile_summary: dict[str, str] = {}
        self._profile_warnings = ""

    async def async_step_user(self, user_input=None):
        if user_input is not None:
            self._data = dict(user_input)
            self._data["unique_id"] = uuid4().hex
            if user_input[CONF_DEVICE_TYPE] == "remote":
                return await self.async_step_remote_backend()
            return await self.async_step_climate_transmitter()
        return self.async_show_form(step_id="user", data_schema=_schema_user())

    async def async_step_climate_transmitter(self, user_input=None):
        if user_input is not None:
            self._data[CONF_REMOTE_TYPE] = user_input[CONF_REMOTE_TYPE]
            rt = user_input[CONF_REMOTE_TYPE]
            if rt == "ha_remote": return await self.async_step_target()
            if rt == "broadlink": return await self.async_step_broadlink()
            if rt == "zigbee2mqtt": return await self.async_step_zigbee2mqtt()
            if rt == "localtuya": return await self.async_step_localtuya()
        return self.async_show_form(step_id="climate_transmitter", data_schema=_schema_climate_transmitter(self._data))

    async def async_step_remote_backend(self, user_input=None):
        if user_input is not None:
            self._data[CONF_REMOTE_BACKEND] = user_input[CONF_REMOTE_BACKEND]
            if user_input[CONF_REMOTE_BACKEND] == "mqtt":
                return await self.async_step_remote_mqtt()
            return await self.async_step_remote_localtuya()
        return self.async_show_form(step_id="remote_backend", data_schema=_schema_remote_backend(self._data))

    async def async_step_remote_mqtt(self, user_input=None):
        errors={}
        if user_input is not None:
            topic=str(user_input[CONF_MQTT_TOPIC]).strip().rstrip("/")
            if not (topic.endswith("/set") or "/set/" in topic): errors["base"]="invalid_mqtt_ir_topic"
            else:
                self._data[CONF_MQTT_TOPIC]=topic; self._data[CONF_IR_PREFIX]=user_input.get(CONF_IR_PREFIX,"")
                return self.async_create_entry(title=self._data["name"],data=self._data)
        return self.async_show_form(step_id="remote_mqtt",data_schema=_schema_remote_mqtt(self._data),errors=errors)

    async def async_step_remote_localtuya(self, user_input=None):
        devices = discover_localtuya_devices(self.hass)
        if user_input is not None:
            self._data[CONF_DEVICE_ID] = user_input[CONF_DEVICE_ID]
            return await self.async_step_remote_localtuya_dp()
        return self.async_show_form(step_id="remote_localtuya", data_schema=_schema_localtuya_device(devices, self._data))

    async def async_step_remote_localtuya_dp(self, user_input=None):
        devices = discover_localtuya_devices(self.hass)
        selected = next((x for x in devices if x.device_id == self._data.get(CONF_DEVICE_ID)), None)
        if user_input is not None:
            try:
                dp = int(user_input[CONF_DP])
                if not 1 <= dp <= 999:
                    raise ValueError
            except (TypeError, ValueError):
                return self.async_show_form(step_id="remote_localtuya_dp", data_schema=_schema_localtuya_dp(selected, self._data), errors={"base": "invalid_dp"})
            self._data[CONF_DP] = dp
            return await self.async_step_remote_localtuya_prefix()
        return self.async_show_form(step_id="remote_localtuya_dp", data_schema=_schema_localtuya_dp(selected, self._data))

    async def async_step_remote_localtuya_prefix(self, user_input=None):
        if user_input is not None:
            self._data[CONF_IR_PREFIX]=user_input.get(CONF_IR_PREFIX,"")
            return self.async_create_entry(title=self._data["name"],data=self._data)
        return self.async_show_form(step_id="remote_localtuya_prefix",data_schema=_schema_remote_prefix(self._data))

    async def async_step_target(self, user_input=None):
        if user_input is not None:
            self._data[CONF_REMOTE_ENTITY] = user_input["entity_id"]
            self._data[CONF_HA_DEVICE_ID] = user_input["ha_device_id"]
            self._data[CONF_TARGET] = dict(user_input)
            return await self.async_step_grouping_attributes()
        return self.async_show_form(step_id="target", data_schema=_schema_target())

    async def async_step_grouping_attributes(self, user_input=None):
        if user_input is not None:
            self._data[CONF_GROUPING_ATTRIBUTES] = user_input.get(CONF_GROUPING_ATTRIBUTES, [])
            self._data[CONF_GROUPING_ATTRIBUTES_AS_SEQUENCE] = user_input.get(CONF_GROUPING_ATTRIBUTES_AS_SEQUENCE, False)
            return await self.async_step_temperature()
        return self.async_show_form(step_id="grouping_attributes", data_schema=_schema_grouping(self._data))

    async def async_step_broadlink(self, user_input=None):
        if user_input is not None:
            self._data[CONF_REMOTE_ENTITY] = user_input["entity_id"]
            return await self.async_step_profile_upload()
        return self.async_show_form(step_id="broadlink", data_schema=_schema_broadlink())

    async def async_step_zigbee2mqtt(self, user_input=None):
        if user_input is not None:
            self._data[CONF_MQTT_TOPIC] = user_input[CONF_MQTT_TOPIC]
            return await self.async_step_profile_upload()
        return self.async_show_form(step_id="zigbee2mqtt", data_schema=_schema_z2m())

    async def async_step_localtuya(self, user_input=None):
        devices = discover_localtuya_devices(self.hass)
        if user_input is not None:
            self._data[CONF_DEVICE_ID] = user_input[CONF_DEVICE_ID]
            return await self.async_step_localtuya_dp()
        return self.async_show_form(step_id="localtuya", data_schema=_schema_localtuya_device(devices, self._data))

    async def async_step_localtuya_dp(self, user_input=None):
        devices = discover_localtuya_devices(self.hass)
        selected = next((x for x in devices if x.device_id == self._data.get(CONF_DEVICE_ID)), None)
        if user_input is not None:
            try:
                dp = int(user_input[CONF_DP])
                if not 1 <= dp <= 999:
                    raise ValueError
            except (TypeError, ValueError):
                return self.async_show_form(step_id="localtuya_dp", data_schema=_schema_localtuya_dp(selected, self._data), errors={"base": "invalid_dp"})
            self._data[CONF_DP] = dp
            return await self.async_step_profile_upload()
        return self.async_show_form(step_id="localtuya_dp", data_schema=_schema_localtuya_dp(selected, self._data))

    async def async_step_profile_upload(self, user_input=None):
        errors = {}
        # This text is shown in the form description so users can see the actual
        # reason a profile was rejected instead of only an error key.
        details = (
            "Upload a Climate Profile JSON file. HVAC, Fan and Temperature "
            "are required; Swing and Preset are optional."
        )
        if user_input is not None:
            try:
                upload_id = user_input[CONF_PROFILE_FILE]

                def _read_upload():
                    with process_uploaded_file(self.hass, upload_id) as path:
                        text = path.read_text(encoding="utf-8")
                        return json.loads(text)

                profile = await self.hass.async_add_executor_job(_read_upload)
                result = validate_climate_profile(profile, self._data[CONF_REMOTE_TYPE])
                if not result.valid:
                    errors["base"] = "profile_validation_failed"
                    details = "Profile cannot be used because:\n• " + "\n• ".join(result.errors)
                    if result.warnings:
                        details += "\n\nWarnings:\n• " + "\n• ".join(result.warnings)
                else:
                    self._data[CONF_DEVICE_PROFILE] = profile
                    self._profile_summary = profile_summary(profile)
                    self._profile_warnings = "; ".join(result.warnings) or "None"
                    return await self.async_step_profile_review()
            except json.JSONDecodeError as err:
                errors["base"] = "invalid_json"
                details = f"The file is not valid JSON: line {err.lineno}, column {err.colno}: {err.msg}."
            except UnicodeDecodeError:
                errors["base"] = "invalid_encoding"
                details = "The file is not UTF-8 text. Save the JSON file as UTF-8 and upload it again."
            except (OSError, ValueError, KeyError) as err:
                errors["base"] = "profile_read_failed"
                details = f"The uploaded profile could not be read: {err}."

        self._profile_warnings = details
        return self.async_show_form(
            step_id="profile_upload",
            data_schema=_schema_profile_upload(),
            errors=errors,
            description_placeholders={"details": details},
        )

    async def async_step_profile_review(self, user_input=None):
        if user_input is not None:
            return await self.async_step_sensors()
        ph = dict(self._profile_summary)
        ph["warnings"] = self._profile_warnings
        return self.async_show_form(step_id="profile_review", data_schema=vol.Schema({}), description_placeholders=ph)

    async def async_step_temperature(self, user_input=None):
        if user_input is not None:
            self._data[CONF_TEMPERATURE] = user_input
            return await self.async_step_hvac_modes()
        return self.async_show_form(step_id="temperature", data_schema=_schema_temperature(self._data.get(CONF_TEMPERATURE, {})))

    async def async_step_hvac_modes(self, user_input=None):
        if user_input is not None:
            self._data[CONF_HVAC_MODES] = user_input
            return await self.async_step_fan_modes()
        return self.async_show_form(step_id="hvac_modes", data_schema=_schema_hvac(self._data.get(CONF_HVAC_MODES, {})))

    async def async_step_fan_modes(self, user_input=None):
        if user_input is not None:
            self._data[CONF_FAN_MODES] = user_input
            return await self.async_step_swing()
        return self.async_show_form(step_id="fan_modes", data_schema=_schema_fan(self._data.get(CONF_FAN_MODES, {})))

    async def async_step_swing(self, user_input=None):
        if user_input is not None:
            self._data[CONF_SWING] = user_input
            return await self.async_step_preset_modes()
        return self.async_show_form(step_id="swing", data_schema=_schema_swing(self._data.get(CONF_SWING, {})))

    async def async_step_preset_modes(self, user_input=None):
        if user_input is not None:
            self._data[CONF_PRESET_MODES] = user_input
            return await self.async_step_sensors()
        return self.async_show_form(step_id="preset_modes", data_schema=_schema_preset(self._data.get(CONF_PRESET_MODES, {})))

    async def async_step_sensors(self, user_input=None):
        if user_input is not None:
            for key in (CONF_TEMPERATURE_SENSOR, CONF_HUMIDITY_SENSOR, CONF_POWER_SENSOR):
                self._data[key] = user_input.get(key) or None
            return self.async_create_entry(title=self._data.get("name", "Smart Remote"), data=self._data)
        return self.async_show_form(step_id="sensors", data_schema=_schema_sensors(self._data))

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return OptionsFlowHandler(config_entry)


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Edit runtime configuration without changing the device/name."""

    def __init__(self, config_entry):
        self._entry = config_entry
        # Stage all changes here. Nothing is committed until the final Save.
        self.result = dict(config_entry.options)
        self._working = {**config_entry.data, **config_entry.options}
        self._profile_summary: dict[str, str] = {}
        self._profile_warnings = "None"

    def _defs(self):
        return {**self._working, **self.result}

    def _set(self, key, value):
        self.result[key] = value
        self._working[key] = value

    def _clear_transmitter_specific(self, keep_type: str):
        """Remove stale values belonging to a different transmitter."""
        # options override entry.data, so None deliberately masks legacy data.
        if keep_type != "ha_remote":
            for key in (
                CONF_HA_DEVICE_ID, CONF_TARGET, CONF_GROUPING_ATTRIBUTES,
                CONF_GROUPING_ATTRIBUTES_AS_SEQUENCE, CONF_TEMPERATURE,
                CONF_HVAC_MODES, CONF_FAN_MODES, CONF_SWING, CONF_PRESET_MODES,
            ):
                self._set(key, None)
        if keep_type != "broadlink":
            # Broadlink's remote entity is also used by HA Remote, so only clear
            # it when switching to Z2M.
            if keep_type == "zigbee2mqtt":
                self._set(CONF_REMOTE_ENTITY, None)
        if keep_type != "zigbee2mqtt":
            self._set(CONF_MQTT_TOPIC, None)
        if keep_type != "localtuya":
            self._set(CONF_DEVICE_ID, None)
            self._set(CONF_DP, None)
        if keep_type == "ha_remote":
            self._set(CONF_DEVICE_PROFILE, None)

    async def async_step_init(self, user_input=None):
        """Route Options Flow to the correct independent device type."""
        if self._defs().get(CONF_DEVICE_TYPE, "climate") == "remote":
            return await self.async_step_remote_backend()

        current = self._defs().get(CONF_REMOTE_TYPE, "ha_remote")
        if user_input is not None:
            remote_type = user_input[CONF_REMOTE_TYPE]
            self._set(CONF_REMOTE_TYPE, remote_type)
            self._clear_transmitter_specific(remote_type)
            if remote_type == "ha_remote":
                return await self.async_step_target()
            if remote_type == "broadlink":
                return await self.async_step_broadlink()
            if remote_type == "localtuya":
                return await self.async_step_localtuya()
            return await self.async_step_zigbee2mqtt()

        schema = vol.Schema({
            vol.Required(CONF_REMOTE_TYPE, default=current): selector.SelectSelector(
                selector.SelectSelectorConfig(options=[
                    selector.SelectOptionDict(value="ha_remote", label="Home Assistant Remote"),
                    selector.SelectOptionDict(value="broadlink", label="Broadlink"),
                    selector.SelectOptionDict(value="zigbee2mqtt", label="Zigbee2MQTT"),
                    selector.SelectOptionDict(value="localtuya", label="LocalTuya Direct IR"),
                ], mode=selector.SelectSelectorMode.DROPDOWN)
            )
        })
        return self.async_show_form(step_id="init", data_schema=schema)

    async def async_step_remote_backend(self, user_input=None):
        current = self._defs().get(CONF_REMOTE_BACKEND, "mqtt")
        if user_input is not None:
            backend = user_input[CONF_REMOTE_BACKEND]
            self._set(CONF_REMOTE_BACKEND, backend)
            if backend == "mqtt":
                self._set(CONF_DEVICE_ID, None)
                self._set(CONF_DP, None)
                return await self.async_step_remote_mqtt()
            self._set(CONF_MQTT_TOPIC, None)
            return await self.async_step_remote_localtuya()

        return self.async_show_form(
            step_id="remote_backend",
            data_schema=_schema_remote_backend({CONF_REMOTE_BACKEND: current}),
        )

    async def async_step_remote_mqtt(self, user_input=None):
        errors = {}
        if user_input is not None:
            topic = str(user_input[CONF_MQTT_TOPIC]).strip().rstrip("/")
            if not (topic.endswith("/set") or "/set/" in topic):
                errors["base"] = "invalid_mqtt_ir_topic"
            else:
                self._set(CONF_MQTT_TOPIC, topic)
                self._set(CONF_IR_PREFIX, user_input.get(CONF_IR_PREFIX, ""))
                return await self.async_step_remote_finish()
        return self.async_show_form(
            step_id="remote_mqtt",
            data_schema=_schema_remote_mqtt(self._defs()),
            errors=errors,
        )

    async def async_step_remote_localtuya(self, user_input=None):
        devices = discover_localtuya_devices(self.hass)
        if user_input is not None:
            self._set(CONF_DEVICE_ID, user_input[CONF_DEVICE_ID])
            return await self.async_step_remote_localtuya_dp()
        return self.async_show_form(
            step_id="remote_localtuya",
            data_schema=_schema_localtuya_device(devices, self._defs()),
        )

    async def async_step_remote_localtuya_dp(self, user_input=None):
        devices = discover_localtuya_devices(self.hass)
        selected = next(
            (x for x in devices if x.device_id == self._defs().get(CONF_DEVICE_ID)),
            None,
        )
        if user_input is not None:
            try:
                dp = int(user_input[CONF_DP])
                if not 1 <= dp <= 999:
                    raise ValueError
            except (TypeError, ValueError):
                return self.async_show_form(
                    step_id="remote_localtuya_dp",
                    data_schema=_schema_localtuya_dp(selected, self._defs()),
                    errors={"base": "invalid_dp"},
                )
            self._set(CONF_DP, dp)
            return await self.async_step_remote_localtuya_prefix()
        return self.async_show_form(
            step_id="remote_localtuya_dp",
            data_schema=_schema_localtuya_dp(selected, self._defs()),
        )

    async def async_step_remote_localtuya_prefix(self, user_input=None):
        if user_input is not None:
            self._set(CONF_IR_PREFIX, user_input.get(CONF_IR_PREFIX, ""))
            return await self.async_step_remote_finish()
        return self.async_show_form(
            step_id="remote_localtuya_prefix",
            data_schema=_schema_remote_prefix(self._defs()),
        )

    async def async_step_remote_finish(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(title=self._entry.title, data=self.result)
        return self.async_show_form(
            step_id="remote_finish",
            data_schema=vol.Schema({}),
        )

    async def async_step_target(self, user_input=None):
        if user_input is not None:
            self._set(CONF_REMOTE_ENTITY, user_input["entity_id"])
            self._set(CONF_HA_DEVICE_ID, user_input["ha_device_id"])
            self._set(CONF_TARGET, dict(user_input))
            return await self.async_step_grouping_attributes()
        return self.async_show_form(step_id="target", data_schema=_schema_target(self._defs()))

    async def async_step_grouping_attributes(self, user_input=None):
        if user_input is not None:
            self._set(CONF_GROUPING_ATTRIBUTES, user_input.get(CONF_GROUPING_ATTRIBUTES, []))
            self._set(CONF_GROUPING_ATTRIBUTES_AS_SEQUENCE, user_input.get(CONF_GROUPING_ATTRIBUTES_AS_SEQUENCE, False))
            return await self.async_step_temperature()
        return self.async_show_form(step_id="grouping_attributes", data_schema=_schema_grouping(self._defs()))

    async def async_step_temperature(self, user_input=None):
        if user_input is not None:
            self._set(CONF_TEMPERATURE, user_input)
            return await self.async_step_hvac_modes()
        return self.async_show_form(step_id="temperature", data_schema=_schema_temperature(self._defs().get(CONF_TEMPERATURE, {}) or {}))

    async def async_step_hvac_modes(self, user_input=None):
        if user_input is not None:
            self._set(CONF_HVAC_MODES, user_input)
            return await self.async_step_fan_modes()
        return self.async_show_form(step_id="hvac_modes", data_schema=_schema_hvac(self._defs().get(CONF_HVAC_MODES, {}) or {}))

    async def async_step_fan_modes(self, user_input=None):
        if user_input is not None:
            self._set(CONF_FAN_MODES, user_input)
            return await self.async_step_swing()
        return self.async_show_form(step_id="fan_modes", data_schema=_schema_fan(self._defs().get(CONF_FAN_MODES, {}) or {}))

    async def async_step_swing(self, user_input=None):
        if user_input is not None:
            self._set(CONF_SWING, user_input)
            return await self.async_step_preset_modes()
        return self.async_show_form(step_id="swing", data_schema=_schema_swing(self._defs().get(CONF_SWING, {}) or {}))

    async def async_step_preset_modes(self, user_input=None):
        if user_input is not None:
            self._set(CONF_PRESET_MODES, user_input)
            return await self.async_step_sensors()
        return self.async_show_form(step_id="preset_modes", data_schema=_schema_preset(self._defs().get(CONF_PRESET_MODES, {}) or {}))

    async def async_step_broadlink(self, user_input=None):
        if user_input is not None:
            self._set(CONF_REMOTE_ENTITY, user_input["entity_id"])
            return await self.async_step_profile_upload()
        return self.async_show_form(step_id="broadlink", data_schema=_schema_broadlink(self._defs()))

    async def async_step_zigbee2mqtt(self, user_input=None):
        if user_input is not None:
            self._set(CONF_MQTT_TOPIC, user_input[CONF_MQTT_TOPIC])
            return await self.async_step_profile_upload()
        return self.async_show_form(step_id="zigbee2mqtt", data_schema=_schema_z2m(self._defs()))

    async def async_step_localtuya(self, user_input=None):
        devices = discover_localtuya_devices(self.hass)
        if user_input is not None:
            self._set(CONF_DEVICE_ID, user_input[CONF_DEVICE_ID])
            return await self.async_step_localtuya_dp()
        return self.async_show_form(step_id="localtuya", data_schema=_schema_localtuya_device(devices, self._defs()))

    async def async_step_localtuya_dp(self, user_input=None):
        devices = discover_localtuya_devices(self.hass)
        selected = next((x for x in devices if x.device_id == self._defs().get(CONF_DEVICE_ID)), None)
        if user_input is not None:
            try:
                dp = int(user_input[CONF_DP])
                if not 1 <= dp <= 999:
                    raise ValueError
            except (TypeError, ValueError):
                return self.async_show_form(step_id="localtuya_dp", data_schema=_schema_localtuya_dp(selected, self._defs()), errors={"base": "invalid_dp"})
            self._set(CONF_DP, dp)
            return await self.async_step_profile_upload()
        return self.async_show_form(step_id="localtuya_dp", data_schema=_schema_localtuya_dp(selected, self._defs()))

    async def async_step_profile_upload(self, user_input=None):
        errors = {}
        details = (
            "Upload a Climate Profile JSON file. HVAC, Fan and Temperature "
            "are required; Swing and Preset are optional."
        )
        if user_input is not None:
            try:
                upload_id = user_input[CONF_PROFILE_FILE]

                def _read_upload():
                    with process_uploaded_file(self.hass, upload_id) as path:
                        return json.loads(path.read_text(encoding="utf-8"))

                profile = await self.hass.async_add_executor_job(_read_upload)
                result = validate_climate_profile(profile, self._defs()[CONF_REMOTE_TYPE])
                if not result.valid:
                    errors["base"] = "profile_validation_failed"
                    details = "Profile cannot be used because:\n• " + "\n• ".join(result.errors)
                    if result.warnings:
                        details += "\n\nWarnings:\n• " + "\n• ".join(result.warnings)
                else:
                    self._set(CONF_DEVICE_PROFILE, profile)
                    self._profile_summary = profile_summary(profile)
                    self._profile_warnings = "; ".join(result.warnings) or "None"
                    return await self.async_step_profile_review()
            except json.JSONDecodeError as err:
                errors["base"] = "invalid_json"
                details = f"The file is not valid JSON: line {err.lineno}, column {err.colno}: {err.msg}."
            except UnicodeDecodeError:
                errors["base"] = "invalid_encoding"
                details = "The file is not UTF-8 text. Save the JSON file as UTF-8 and upload it again."
            except (OSError, ValueError, KeyError) as err:
                errors["base"] = "profile_read_failed"
                details = f"The uploaded profile could not be read: {err}."

        return self.async_show_form(
            step_id="profile_upload", data_schema=_schema_profile_upload(), errors=errors,
            description_placeholders={"details": details},
        )

    async def async_step_profile_review(self, user_input=None):
        if user_input is not None:
            return await self.async_step_sensors()
        ph = dict(self._profile_summary)
        ph["warnings"] = self._profile_warnings
        return self.async_show_form(
            step_id="profile_review", data_schema=vol.Schema({}),
            description_placeholders=ph,
        )

    async def async_step_sensors(self, user_input=None):
        if user_input is not None:
            for key in (CONF_TEMPERATURE_SENSOR, CONF_HUMIDITY_SENSOR, CONF_POWER_SENSOR):
                self._set(key, user_input.get(key) or None)
            return await self.async_step_finish()
        return self.async_show_form(step_id="sensors", data_schema=_schema_sensors(self._defs()))

    async def async_step_finish(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(title=self._entry.title, data=self.result)
        return self.async_show_form(step_id="finish", data_schema=vol.Schema({}))

