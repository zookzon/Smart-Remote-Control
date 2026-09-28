import importlib.util
from pathlib import Path

MODULE = Path(__file__).parents[1] / "custom_components" / "smart_remote_control" / "send_coordinator.py"
spec = importlib.util.spec_from_file_location("send_coordinator", MODULE)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def test_default_minimum_interval_is_half_second():
    assert mod.MIN_SEND_INTERVAL == 0.5


def test_power_on_settle_delay_is_eight_tenths_second():
    assert mod.POWER_ON_SETTLE_DELAY == 0.8


def test_power_transitions_are_detected_both_directions():
    assert mod.is_power_transition("off", "cool")
    assert mod.is_power_transition("heat", "off")
    assert not mod.is_power_transition("cool", "heat")


def test_latest_ordinary_state_wins():
    assert mod.should_drop_as_superseded(power_transition=False, generation=2, latest_generation=3)
    assert not mod.should_drop_as_superseded(power_transition=False, generation=3, latest_generation=3)


def test_power_transition_is_never_coalesced():
    assert not mod.should_drop_as_superseded(power_transition=True, generation=2, latest_generation=3)


def test_profile_on_is_optional():
    assert mod.optional_profile_on({"commands": {"off": "OFF"}}) is None
    assert mod.optional_profile_on({"commands": {"on": "ON", "off": "OFF"}}) == "ON"
