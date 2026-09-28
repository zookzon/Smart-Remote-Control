"""Config-entry compatibility helpers for Smart Remote Control."""
from __future__ import annotations

from copy import deepcopy
from typing import Any

_GROUPING_ALIASES = {
    "mode": "hvac_mode",
    "hvac": "hvac_mode",
    "fan": "fan_mode",
    "swing": "swing_mode",
    "temp": "temperature",
    "preset": "preset_mode",
}
_VALID_GROUPING = {"hvac_mode", "fan_mode", "swing_mode", "temperature", "preset_mode"}


def _normalise_grouping(value: Any) -> list[str]:
    if not isinstance(value, (list, tuple)):
        return []
    result: list[str] = []
    for item in value:
        key = _GROUPING_ALIASES.get(str(item), str(item))
        if key in _VALID_GROUPING and key not in result:
            result.append(key)
    return result


def normalise_config(values: dict[str, Any] | None) -> dict[str, Any]:
    """Return current-format config while preserving unknown legacy keys.

    This is intentionally conservative: it only migrates shapes that older
    Smart Remote Control releases actually used and leaves hidden LocalTuya
    data untouched.
    """
    out = deepcopy(values or {})

    # Older HA Remote entries stored the target as a nested mapping.
    target = out.get("target")
    if isinstance(target, dict):
        if not out.get("remote_entity") and target.get("entity_id"):
            out["remote_entity"] = target["entity_id"]
        if not out.get("ha_device_id") and target.get("ha_device_id"):
            out["ha_device_id"] = target["ha_device_id"]

    # Pre-v3.3.6 Swing stored an unused mode (none/toggle/state).  Current
    # behavior is determined solely by the selected Swing modes.
    swing = out.get("swing")
    if isinstance(swing, dict):
        modes = swing.get("modes")
        out["swing"] = {"modes": list(modes) if isinstance(modes, (list, tuple)) else []}

    # "none" is now an internal neutral Climate state, not a user-configured
    # device preset.  Keep only real device presets in config.
    preset = out.get("preset_modes")
    if isinstance(preset, dict) and isinstance(preset.get("modes"), (list, tuple)):
        out["preset_modes"] = {
            **preset,
            "modes": [mode for mode in preset["modes"] if mode != "none"],
        }

    if "grouping_attributes" in out:
        out["grouping_attributes"] = _normalise_grouping(out.get("grouping_attributes"))

    return out
