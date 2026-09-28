import importlib.util
from pathlib import Path

MODULE = Path(__file__).parents[1] / "custom_components" / "smart_remote_control" / "state_logic.py"
spec = importlib.util.spec_from_file_location("state_logic", MODULE)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def test_hvac_action_off():
    assert mod.estimate_hvac_action("off", 30, 24, has_temperature_sensor=True) == "off"


def test_hvac_action_cool_with_feedback():
    assert mod.estimate_hvac_action("cool", 26, 24, has_temperature_sensor=True) == "cooling"
    assert mod.estimate_hvac_action("cool", 24, 24, has_temperature_sensor=True) == "idle"
    assert mod.estimate_hvac_action("cool", 22, 24, has_temperature_sensor=True) == "idle"


def test_hvac_action_heat_with_feedback():
    assert mod.estimate_hvac_action("heat", 20, 24, has_temperature_sensor=True) == "heating"
    assert mod.estimate_hvac_action("heat", 24, 24, has_temperature_sensor=True) == "idle"
    assert mod.estimate_hvac_action("heat", 26, 24, has_temperature_sensor=True) == "idle"


def test_hvac_action_auto_with_feedback():
    assert mod.estimate_hvac_action("auto", 26, 24, has_temperature_sensor=True) == "cooling"
    assert mod.estimate_hvac_action("auto", 22, 24, has_temperature_sensor=True) == "heating"
    assert mod.estimate_hvac_action("auto", 24, 24, has_temperature_sensor=True) == "idle"


def test_hvac_action_without_temperature_sensor_falls_back_to_mode():
    assert mod.estimate_hvac_action("cool", None, 24, has_temperature_sensor=False) == "cooling"
    assert mod.estimate_hvac_action("heat", None, 24, has_temperature_sensor=False) == "heating"
    assert mod.estimate_hvac_action("auto", None, 24, has_temperature_sensor=False) == "idle"
    assert mod.estimate_hvac_action("dry", None, 24, has_temperature_sensor=False) == "drying"
    assert mod.estimate_hvac_action("fan_only", None, 24, has_temperature_sensor=False) == "fan"


def test_restore_choice_rejects_removed_option():
    assert mod.restore_choice("turbo", ["auto", "medium"], "auto") == "auto"
    assert mod.restore_choice("medium", ["auto", "medium"], "auto") == "medium"


def test_restore_hvac_mode_rejects_removed_mode():
    assert mod.restore_hvac_mode("heat", ["off", "cool"]) == "off"
    assert mod.restore_hvac_mode("cool", ["off", "cool"]) == "cool"


def test_temperature_restore_clamps_and_aligns():
    assert mod.normalize_temperature(35, 18, 30, 1, 24) == 30
    assert mod.normalize_temperature(17, 18, 30, 1, 24) == 18
    assert mod.normalize_temperature(24.49, 18, 30, 0.5, 24) == 24.5


def test_temperature_grid_is_anchored_at_minimum():
    assert mod.normalize_temperature(18.4, 16.5, 30.5, 1.0, 24.5) == 18.5
