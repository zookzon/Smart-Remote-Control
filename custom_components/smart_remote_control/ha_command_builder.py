"""Pure helpers for Home Assistant Remote learned-command names.

Kept independent from Home Assistant so command naming can be regression-tested
without a running HA instance.
"""
from __future__ import annotations


def attr_command(
    key: str,
    *,
    hvac_mode=None,
    fan_mode=None,
    swing_mode=None,
    temperature=None,
    preset_mode=None,
) -> str:
    """Return one learned-command component for the supplied climate state."""
    if key == "hvac_mode":
        return f"mode:{hvac_mode}" if hvac_mode is not None else ""
    if key == "fan_mode":
        return f"fan:{fan_mode}" if fan_mode is not None else ""
    if key == "swing_mode":
        return f"swing:{swing_mode}" if swing_mode is not None else ""
    if key == "temperature":
        return f"temp:{float(temperature):.1f}" if temperature is not None else ""
    if key == "preset_mode":
        # none is the neutral Climate state, not a learned-command component.
        if preset_mode in (None, "none"):
            return ""
        return f"preset:{preset_mode}"
    return ""


def commands_for(
    changed_key: str,
    grouping_attributes,
    *,
    grouping_as_sequence: bool = False,
    hvac_mode=None,
    fan_mode=None,
    swing_mode=None,
    temperature=None,
    preset_mode=None,
) -> list[str]:
    """Build HA Remote command(s) from Grouping Attributes in exact user order."""
    state = {
        "hvac_mode": hvac_mode,
        "fan_mode": fan_mode,
        "swing_mode": swing_mode,
        "temperature": temperature,
        "preset_mode": preset_mode,
    }

    def component(key: str) -> str:
        return attr_command(key, **state)

    grouping_attributes = list(grouping_attributes or [])
    grouping = [key for key in grouping_attributes if component(key)]

    # Clearing a full-state preset sends the normal full-state command with the
    # preset component omitted. A standalone preset has no implicit preset:none.
    if changed_key == "preset_mode" and preset_mode == "none":
        if "preset_mode" in grouping_attributes:
            components = [component(key) for key in grouping_attributes]
            components = [item for item in components if item]
            if grouping_as_sequence:
                return components
            return ["_".join(components)] if components else []
        return []

    if changed_key not in grouping:
        standalone = component(changed_key)
        return [standalone] if standalone else []

    components = [component(key) for key in grouping]
    components = [item for item in components if item]
    if grouping_as_sequence:
        return components
    return ["_".join(components)] if components else []
