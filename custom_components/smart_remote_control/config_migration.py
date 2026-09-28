"""Compatibility helpers for legacy Smart Remote Control config entries."""
from __future__ import annotations
from typing import Any
from .const import CONF_CURRENT_HUMIDITY_SENSOR_ENTITY_ID, CONF_CURRENT_TEMPERATURE_SENSOR_ENTITY_ID, CONF_DEVICE_CODE, CONF_DEVICE_PROFILE, CONF_DEVICE_TYPE, CONF_HUMIDITY_SENSOR, CONF_REMOTE_ENTITY, CONF_REMOTE_TYPE, CONF_TEMPERATURE_SENSOR

LEGACY_ALIASES = {
    CONF_TEMPERATURE_SENSOR: CONF_CURRENT_TEMPERATURE_SENSOR_ENTITY_ID,
    CONF_HUMIDITY_SENSOR: CONF_CURRENT_HUMIDITY_SENSOR_ENTITY_ID,
}

def normalise_config(config: dict[str, Any]) -> dict[str, Any]:
    """Return a non-destructive normalised copy of entry data/options."""
    result = dict(config)
    for old_key, new_key in LEGACY_ALIASES.items():
        if new_key not in result and result.get(old_key) not in (None, ""):
            result[new_key] = result[old_key]
    if CONF_DEVICE_TYPE not in result:
        result[CONF_DEVICE_TYPE] = "climate"
    if CONF_DEVICE_PROFILE not in result and result.get(CONF_DEVICE_CODE) not in (None, ""):
        result[CONF_DEVICE_PROFILE] = str(result[CONF_DEVICE_CODE])
    if CONF_REMOTE_TYPE not in result:
        if result.get(CONF_REMOTE_ENTITY): result[CONF_REMOTE_TYPE] = "ha_remote"
        else: result[CONF_REMOTE_TYPE] = "ha_remote"
    return result

def merged_config(data: dict[str, Any], options: dict[str, Any]) -> dict[str, Any]:
    """Merge config entry data/options, preferring options, then normalise."""
    merged = dict(data); merged.update(options); return normalise_config(merged)
