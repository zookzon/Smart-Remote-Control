"""Regression tests: climate entity must survive None-valued config keys.

Options Flow masks stale transmitter settings by writing ``None`` for the keys
of the backend being left behind (see ``_clear_transmitter_specific``).  A plain
``config.get(KEY, {})`` returns ``None`` in that case -- not the default -- so
the constructor used to raise ``AttributeError: 'NoneType' object has no
attribute 'get'`` when the profile was missing or the backend was HA Remote.
"""
from __future__ import annotations

import sys
import types
from types import SimpleNamespace

import pytest

if "aiofiles" not in sys.modules:
    sys.modules["aiofiles"] = types.ModuleType("aiofiles")

from custom_components.smart_remote_control import climate as climate_module  # noqa: E402
from custom_components.smart_remote_control.const import (  # noqa: E402
    CONF_FAN_MODES,
    CONF_HVAC_MODES,
    CONF_PRESET_MODES,
    CONF_REMOTE_TYPE,
    CONF_SWING,
    CONF_TEMPERATURE,
)

TEMP = {
    "mode": "target",
    "min": 16.0,
    "max": 30.0,
    "temperature_unit": "c",
    "temperature_step": 1.0,
}
MODES = {"modes": ["cool"]}
EMPTY = {"modes": []}


class _FakeHass:
    def __init__(self) -> None:
        self.config = SimpleNamespace(units=SimpleNamespace(temperature_unit="C"))
        self.states = SimpleNamespace(get=lambda entity_id: None)
        self.data = {}
        self.services = SimpleNamespace(async_call=None)


def _build(remote_type: str, config: dict, data: dict | None = None):
    return climate_module.SmartRemoteClimate(
        _FakeHass(), "Test", "uid", data or {}, remote_type, config
    )


def test_ha_remote_with_none_climate_keys() -> None:
    """Legacy HA Remote options that still carry None must not crash setup."""
    entity = _build(
        "ha_remote",
        {
            CONF_REMOTE_TYPE: "ha_remote",
            CONF_TEMPERATURE: None,
            CONF_HVAC_MODES: None,
            CONF_FAN_MODES: None,
            CONF_SWING: None,
            CONF_PRESET_MODES: None,
        },
    )
    assert entity._attr_min_temp == 16.0
    assert entity._attr_max_temp == 30.0
    assert entity._attr_target_temperature == 24.0
    assert entity._attr_hvac_modes == [climate_module.HVACMode.OFF]
    assert entity._attr_fan_modes == []
    assert entity._attr_preset_modes == []


def test_ir_backend_without_profile_and_none_keys() -> None:
    """Database backend whose profile is gone keeps working with defaults."""
    entity = _build(
        "broadlink",
        {CONF_REMOTE_TYPE: "broadlink", CONF_TEMPERATURE: None},
    )
    assert entity._attr_target_temperature == 24.0
    assert entity._attr_target_temperature_step == 1.0


def test_ir_backend_with_profile_still_uses_profile() -> None:
    """Profile stays the source of truth when present (behaviour unchanged)."""
    entity = _build(
        "broadlink",
        {
            CONF_REMOTE_TYPE: "broadlink",
            CONF_TEMPERATURE: None,
            CONF_HVAC_MODES: None,
        },
        {"precision": 0.5, "minTemperature": 18, "maxTemperature": 32,
         "operationModes": ["cool"], "fanModes": ["auto"]},
    )
    assert entity._attr_target_temperature_step == 0.5
    assert entity._attr_min_temp == 18.0
    assert entity._attr_max_temp == 32.0
    assert entity._attr_fan_modes == ["auto"]


def test_healthy_ha_remote_uses_configured_values() -> None:
    entity = _build(
        "ha_remote",
        {
            CONF_REMOTE_TYPE: "ha_remote",
            CONF_TEMPERATURE: TEMP,
            CONF_HVAC_MODES: MODES,
            CONF_FAN_MODES: {"modes": ["auto"]},
            CONF_SWING: EMPTY,
            CONF_PRESET_MODES: EMPTY,
        },
    )
    assert entity._attr_min_temp == 16.0
    assert entity._attr_max_temp == 30.0
    assert entity._attr_target_temperature_step == 1.0
