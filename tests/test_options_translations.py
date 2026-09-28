import json
from pathlib import Path

ROOT = Path(__file__).parents[1] / "custom_components" / "smart_remote_control"

EXPECTED = {
    "remote_backend": {"remote_backend": "IR Backend"},
    "remote_mqtt": {
        "mqtt_topic": "MQTT Topic",
        "ir_prefix": "IR Code Prefix (Optional)",
    },
    "remote_localtuya": {"device_id": "LocalTuya Device"},
    "remote_localtuya_dp": {"dp": "IR Send DP"},
    "remote_localtuya_prefix": {
        "ir_prefix": "IR Code Prefix (Optional)",
    },
}

def _check(path):
    data = json.loads(path.read_text(encoding="utf-8"))
    options = data["options"]
    for step, labels in EXPECTED.items():
        assert step in options["step"]
        assert options["step"][step]["title"]
        assert options["step"][step]["description"]
        for key, label in labels.items():
            assert options["step"][step]["data"][key] == label
            assert options["step"][step]["data"][key] != key
    assert options["step"]["remote_finish"]["title"]
    assert options["error"]["invalid_mqtt_ir_topic"]
    assert options["error"]["invalid_dp"]

def test_strings_options_are_human_readable():
    _check(ROOT / "translations" / "en.json")

def test_english_options_are_human_readable():
    _check(ROOT / "translations" / "en.json")
