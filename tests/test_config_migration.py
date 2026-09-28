import importlib.util
from pathlib import Path

MODULE = Path(__file__).parents[1] / "custom_components" / "smart_remote_control" / "config_migration.py"
spec = importlib.util.spec_from_file_location("config_migration", MODULE)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def test_legacy_target_is_promoted_without_losing_target():
    old = {"target": {"entity_id": "remote.bedroom", "ha_device_id": "AC"}}
    new = mod.normalise_config(old)
    assert new["remote_entity"] == "remote.bedroom"
    assert new["ha_device_id"] == "AC"
    assert new["target"] == old["target"]


def test_existing_remote_entity_wins_over_nested_legacy_target():
    old = {"remote_entity": "remote.new", "target": {"entity_id": "remote.old"}}
    assert mod.normalise_config(old)["remote_entity"] == "remote.new"


def test_old_swing_mode_is_removed_but_modes_are_preserved():
    old = {"swing": {"mode": "state", "modes": ["off", "vertical"]}}
    assert mod.normalise_config(old)["swing"] == {"modes": ["off", "vertical"]}


def test_preset_none_becomes_internal_not_configured_mode():
    old = {"preset_modes": {"modes": ["none", "sleep", "turbo"]}}
    assert mod.normalise_config(old)["preset_modes"]["modes"] == ["sleep", "turbo"]


def test_legacy_grouping_aliases_are_normalised_in_order():
    old = {"grouping_attributes": ["mode", "fan", "temp", "swing", "preset"]}
    assert mod.normalise_config(old)["grouping_attributes"] == [
        "hvac_mode", "fan_mode", "temperature", "swing_mode", "preset_mode"
    ]


def test_grouping_duplicates_and_unknown_values_are_removed():
    old = {"grouping_attributes": ["hvac_mode", "mode", "bogus", "temperature"]}
    assert mod.normalise_config(old)["grouping_attributes"] == ["hvac_mode", "temperature"]


def test_hidden_localtuya_values_are_preserved():
    old = {"remote_type": "localtuya", "device_id": "abc", "dp": 201}
    assert mod.normalise_config(old) == old
