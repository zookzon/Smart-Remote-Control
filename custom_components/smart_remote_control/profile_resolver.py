"""Pure IR-profile resolver helpers for Smart Remote Control.

Kept free of Home Assistant imports so resolver behaviour can be regression-tested.
"""
from __future__ import annotations


def _temp_key(temperature: float, step: float = 1.0) -> str:
    step = float(step or 1.0)
    normalized = round(float(temperature) / step) * step
    return str(int(normalized)) if float(normalized).is_integer() else str(normalized)


def resolve_command(
    profile: dict,
    *,
    hvac_mode: str,
    fan_mode: str,
    temperature: float,
    swing_mode: str | None = None,
    preset_mode: str | None = None,
    changed_key: str = "hvac_mode",
    temperature_step: float = 1.0,
):
    """Return (command, error).

    Swing/Preset standalone commands are resolved only when that feature changes.
    Full-state dimensions are included in the tree only when configured as full_state.
    Preset ``none`` is neutral: full-state skips the preset layer; standalone sends an
    optional presetCommands["none"] command when one exists, otherwise no command.
    """
    swing_type = str(profile.get("swingType", "full_state")).lower()
    preset_type = str(profile.get("presetType", "full_state")).lower()

    if changed_key == "swing_mode" and swing_type == "standalone":
        cmd = profile.get("swingCommands", {}).get(swing_mode)
        return (cmd, None) if cmd else (None, f"Missing standalone swing command '{swing_mode}'")

    if changed_key == "preset_mode" and preset_type == "standalone":
        cmd = profile.get("presetCommands", {}).get(preset_mode)
        if preset_mode == "none" and not cmd:
            return None, None
        return (cmd, None) if cmd else (None, f"Missing standalone preset command '{preset_mode}'")

    commands = profile.get("commands", {})
    if hvac_mode == "off":
        cmd = commands.get("off")
        return (cmd, None) if cmd else (None, "No 'off' IR code in JSON")

    node = commands.get(hvac_mode)
    if not isinstance(node, dict):
        return None, f"Missing mode section '{hvac_mode}' in JSON"

    if profile.get("presetModes") and preset_mode not in (None, "none") and preset_type == "full_state":
        node = node.get(preset_mode)
        if not isinstance(node, dict):
            return None, f"Missing preset mode '{preset_mode}' in JSON"

    node = node.get(fan_mode)
    if not isinstance(node, dict):
        return None, f"Missing fan mode '{fan_mode}' for mode '{hvac_mode}'"

    if profile.get("swingModes") and swing_type == "full_state":
        node = node.get(swing_mode)
        if not isinstance(node, dict):
            return None, f"Missing swing mode '{swing_mode}' in JSON"

    key = _temp_key(temperature, temperature_step)
    cmd = node.get(key)
    if not cmd:
        return None, f"Missing temperature '{key}' for current climate state"
    return cmd, None
