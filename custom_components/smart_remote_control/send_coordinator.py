"""Pure policy helpers for Climate IR transmission sequencing."""
from __future__ import annotations

MIN_SEND_INTERVAL = 0.5
POWER_ON_SETTLE_DELAY = 0.8


def is_power_transition(previous_mode, new_mode) -> bool:
    """Return True when a request crosses the OFF boundary."""
    return (str(previous_mode) == "off") != (str(new_mode) == "off")


def should_drop_as_superseded(*, power_transition: bool, generation: int, latest_generation: int) -> bool:
    """Latest ordinary state wins; ON/OFF transitions are never coalesced away."""
    return (not power_transition) and generation != latest_generation


def optional_profile_on(profile: dict | None):
    """Return an optional database-profile ON command without requiring it."""
    if not isinstance(profile, dict):
        return None
    commands = profile.get("commands")
    if not isinstance(commands, dict):
        return None
    return commands.get("on")
