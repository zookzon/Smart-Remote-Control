import importlib.util
import sys
from pathlib import Path

MODULE = Path(__file__).parents[1] / "custom_components" / "smart_remote_control" / "profile_validator.py"
spec = importlib.util.spec_from_file_location("profile_validator", MODULE)
pv = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = pv
spec.loader.exec_module(pv)

CODE = "JgAAAAAAAAAAAAAAAAAAAA=="

def profile(*, swing_type=None, preset_type=None):
    p = {
        "supportedController": "Zigbee2MQTT", "commandsEncoding": "Base64",
        "minTemperature": 24, "maxTemperature": 25, "precision": 1,
        "operationModes": ["cool"], "fanModes": ["auto", "medium"],
        "commands": {"off": CODE},
    }
    def base():
        return {fan: {"24": CODE, "25": CODE} for fan in p["fanModes"]}
    tree = base()
    if swing_type:
        p.update(swingModes=["off", "vertical"], swingType=swing_type)
        if swing_type == "standalone":
            p["swingCommands"] = {"off": CODE, "vertical": CODE}
        else:
            tree = {fan: {sw: {"24": CODE, "25": CODE} for sw in p["swingModes"]} for fan in p["fanModes"]}
    if preset_type:
        p.update(presetModes=["sleep"], presetType=preset_type)
        if preset_type == "standalone":
            p["presetCommands"] = {"sleep": CODE}
        else:
            p["commands"]["cool"] = tree.copy()
            p["commands"]["cool"]["sleep"] = tree.copy()
            return p
    p["commands"]["cool"] = tree
    return p

def test_complete_profile_passes():
    assert pv.validate_climate_profile(profile(), "zigbee2mqtt").valid

def test_missing_temperature_is_error():
    p = profile(); del p["commands"]["cool"]["auto"]["25"]
    r = pv.validate_climate_profile(p, "zigbee2mqtt")
    assert not r.valid and any("temperature" in e.lower() and "25" in e for e in r.errors)

def test_missing_fan_branch_is_error():
    p = profile(); del p["commands"]["cool"]["medium"]
    assert not pv.validate_climate_profile(p, "zigbee2mqtt").valid

def test_standalone_swing_passes():
    assert pv.validate_climate_profile(profile(swing_type="standalone"), "zigbee2mqtt").valid

def test_full_state_swing_passes():
    assert pv.validate_climate_profile(profile(swing_type="full_state"), "zigbee2mqtt").valid

def test_full_state_preset_requires_neutral_base_and_preset_branch():
    p = profile(preset_type="full_state")
    assert pv.validate_climate_profile(p, "zigbee2mqtt").valid
    del p["commands"]["cool"]["auto"]
    assert not pv.validate_climate_profile(p, "zigbee2mqtt").valid

def test_duplicate_modes_are_rejected():
    p=profile(); p["fanModes"]=["auto","auto"]
    r=pv.validate_climate_profile(p,"zigbee2mqtt")
    assert not r.valid and any("duplicate" in e.lower() for e in r.errors)

def test_all_shipped_profile_templates_validate():
    import json
    templates = MODULE.parent / "profile_templates"
    for path in templates.glob("*.json"):
        p = json.loads(path.read_text())
        tx = "broadlink" if p["supportedController"].lower() == "broadlink" else "zigbee2mqtt"
        result = pv.validate_climate_profile(p, tx)
        assert result.valid, f"{path.name}: {result.errors}"


def test_localtuya_requires_raw_encoding():
    p = profile()
    p["supportedController"] = "LocalTuya"
    p["commandsEncoding"] = "raw"
    assert pv.validate_climate_profile(p, "localtuya").valid
    p["commandsEncoding"] = "Base64"
    result = pv.validate_climate_profile(p, "localtuya")
    assert not result.valid
    assert any("requires commandsEncoding Raw" in x for x in result.errors)
