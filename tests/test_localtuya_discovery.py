import importlib.util
from pathlib import Path

MODULE = Path(__file__).parents[1] / "custom_components" / "smart_remote_control" / "localtuya_discovery.py"
spec = importlib.util.spec_from_file_location("localtuya_discovery", MODULE)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class Entry:
    title = "LocalTuya"
    data = {
        "devices": {
            "dev-a": {
                "friendly_name": "Living Room IR",
                "entities": [{"dp": 201}, {"dp": 202}],
            }
        }
    }


class ConfigEntries:
    def async_entries(self, domain):
        assert domain == "localtuya"
        return [Entry()]


class Hass:
    config_entries = ConfigEntries()
    data = {}


def test_discovers_device_name_id_and_known_dps():
    devices = mod.discover_localtuya_devices(Hass())
    assert len(devices) == 1
    assert devices[0].device_id == "dev-a"
    assert devices[0].name == "Living Room IR"
    assert devices[0].dps == (201, 202)


def test_dp_201_is_only_recommended_when_known():
    assert mod.recommended_dp((1, 201, 202)) == 201
    assert mod.recommended_dp((1, 2, 3)) is None
