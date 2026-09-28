import importlib.util
from pathlib import Path

MODULE = Path(__file__).parents[1] / "custom_components" / "smart_remote_control" / "profile_resolver.py"
spec = importlib.util.spec_from_file_location("profile_resolver", MODULE)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def base_profile(swing_type="full_state", preset_type="full_state"):
    p = {
        "swingModes": ["off", "vertical"],
        "swingType": swing_type,
        "presetModes": ["sleep", "turbo"],
        "presetType": preset_type,
        "swingCommands": {"off": "SW_OFF", "vertical": "SW_VERT"},
        "presetCommands": {"sleep": "P_SLEEP", "turbo": "P_TURBO"},
        "commands": {"off": "POWER_OFF"},
    }
    # Build full-state tree using only dimensions declared full_state.
    temp = {"24": "STATE_IR"}
    if swing_type == "full_state":
        temp = {"vertical": temp}
    fan = {"medium": temp}
    if preset_type == "full_state":
        fan = {"sleep": fan, "turbo": fan}
    p["commands"]["cool"] = fan
    return p


def resolve(p, changed="temperature", preset="sleep", swing="vertical"):
    return mod.resolve_command(p, hvac_mode="cool", fan_mode="medium", temperature=24,
                               swing_mode=swing, preset_mode=preset, changed_key=changed)


def test_both_full_state():
    assert resolve(base_profile())[0] == "STATE_IR"


def test_swing_standalone_preset_full_state():
    p = base_profile("standalone", "full_state")
    assert resolve(p)[0] == "STATE_IR"
    assert resolve(p, changed="swing_mode")[0] == "SW_VERT"


def test_swing_full_state_preset_standalone():
    p = base_profile("full_state", "standalone")
    assert resolve(p)[0] == "STATE_IR"
    assert resolve(p, changed="preset_mode")[0] == "P_SLEEP"


def test_both_standalone():
    p = base_profile("standalone", "standalone")
    assert resolve(p)[0] == "STATE_IR"
    assert resolve(p, changed="swing_mode")[0] == "SW_VERT"
    assert resolve(p, changed="preset_mode")[0] == "P_SLEEP"


def test_full_state_none_skips_preset_layer():
    p = base_profile("standalone", "full_state")
    # neutral/base full-state branch has no preset layer
    p["commands"]["cool"] = {"medium": {"24": "NORMAL_IR"}}
    assert resolve(p, preset="none")[0] == "NORMAL_IR"


def test_standalone_preset_transition_none_sleep_turbo_none_without_none_command():
    p = base_profile("standalone", "standalone")
    assert resolve(p, changed="preset_mode", preset="none") == (None, None)
    assert resolve(p, changed="preset_mode", preset="sleep")[0] == "P_SLEEP"
    assert resolve(p, changed="preset_mode", preset="turbo")[0] == "P_TURBO"
    assert resolve(p, changed="preset_mode", preset="none") == (None, None)


def test_standalone_none_optional_real_command():
    p = base_profile("standalone", "standalone")
    p["presetCommands"]["none"] = "P_CANCEL"
    assert resolve(p, changed="preset_mode", preset="none")[0] == "P_CANCEL"


def test_temperature_step_normalization():
    p = base_profile("standalone", "standalone")
    p["commands"]["cool"] = {"medium": {"24.5": "HALF_IR"}}
    cmd, err = mod.resolve_command(p, hvac_mode="cool", fan_mode="medium", temperature=24.49,
                                   swing_mode="vertical", preset_mode="none",
                                   temperature_step=0.5)
    assert err is None and cmd == "HALF_IR"


def test_missing_branch_returns_specific_error():
    p = base_profile()
    cmd, err = resolve(p, swing="horizontal")
    assert cmd is None
    assert "Missing swing mode 'horizontal'" in err
