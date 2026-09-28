import importlib.util
from pathlib import Path

MODULE = Path(__file__).parents[1] / "custom_components" / "smart_remote_control" / "ha_command_builder.py"
spec = importlib.util.spec_from_file_location("ha_command_builder", MODULE)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

STATE = dict(hvac_mode="cool", fan_mode="medium", swing_mode="vertical", temperature=24, preset_mode="sleep")


def commands(grouping, changed, **overrides):
    state = STATE | overrides
    return mod.commands_for(changed, grouping, **state)


def test_mode_fan_temp_exact_name_and_decimal():
    assert commands(["hvac_mode", "fan_mode", "temperature"], "temperature") == [
        "mode:cool_fan:medium_temp:24.0"
    ]


def test_grouping_order_is_preserved():
    assert commands(["hvac_mode", "temperature", "fan_mode"], "fan_mode") == [
        "mode:cool_temp:24.0_fan:medium"
    ]


def test_swing_standalone_when_not_grouped():
    assert commands(["hvac_mode", "fan_mode", "temperature"], "swing_mode") == ["swing:vertical"]


def test_swing_full_state_when_grouped():
    assert commands(["hvac_mode", "fan_mode", "temperature", "swing_mode"], "swing_mode") == [
        "mode:cool_fan:medium_temp:24.0_swing:vertical"
    ]


def test_preset_standalone_when_not_grouped():
    assert commands(["hvac_mode", "fan_mode", "temperature"], "preset_mode") == ["preset:sleep"]


def test_preset_full_state_when_grouped():
    assert commands(["hvac_mode", "fan_mode", "temperature", "preset_mode"], "preset_mode") == [
        "mode:cool_fan:medium_temp:24.0_preset:sleep"
    ]


def test_preset_none_full_state_omits_preset_suffix():
    assert commands(
        ["hvac_mode", "fan_mode", "temperature", "preset_mode"],
        "preset_mode",
        preset_mode="none",
    ) == ["mode:cool_fan:medium_temp:24.0"]


def test_preset_none_standalone_sends_nothing():
    assert commands(
        ["hvac_mode", "fan_mode", "temperature"],
        "preset_mode",
        preset_mode="none",
    ) == []


def test_sequence_mode_preserves_component_order():
    state = STATE | {"grouping_as_sequence": True}
    assert mod.commands_for(
        "temperature", ["hvac_mode", "fan_mode", "temperature"], **state
    ) == ["mode:cool", "fan:medium", "temp:24.0"]
