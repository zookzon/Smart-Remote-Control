"""Options flow must build without a config_entry argument.

Home Assistant sets ``hass`` and ``handler`` on the flow after construction and
exposes the entry through the read-only ``config_entry`` property, so staging has
to happen in ``async_step_init`` instead of ``__init__``.
"""
import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT))

from custom_components.smart_remote_control import config_flow


def _entry(**options):
    data = {"name": "Living Room AC", "device_type": "climate"}
    return SimpleNamespace(title=data["name"], data=data, options=dict(options))


class _Hass:
    """Minimal Home Assistant stand-in: entry lookup + inline executor."""

    def __init__(self, entry):
        self.data = {}
        self.config_entries = SimpleNamespace(
            async_get_known_entry=lambda entry_id: entry
        )

    async def async_add_executor_job(self, target, *args):
        return target(*args)


def _flow(entry):
    flow = config_flow.OptionsFlowHandler()
    flow.hass = _Hass(entry)
    flow.handler = "entry-id"
    return flow


def test_factory_returns_a_flow_with_no_entry_argument():
    flow = config_flow.ConfigFlow.async_get_options_flow(_entry())

    assert isinstance(flow, config_flow.OptionsFlowHandler)
    # The handler must not define its own __init__: HA assigns hass/handler after
    # construction, and config_entry only resolves once that has happened.
    assert "__init__" not in config_flow.OptionsFlowHandler.__dict__


def test_first_step_stages_the_entry_and_opens_the_form():
    entry = _entry(remote_type="broadlink")
    flow = _flow(entry)

    result = asyncio.run(flow.async_step_init())

    assert result["step_id"] == "init"
    assert flow.result == entry.options
    assert flow._working["name"] == "Living Room AC"


def test_switching_transmitter_clears_stale_values():
    # Switching to Zigbee2MQTT drops the Broadlink/HA-Remote entity, which those
    # backends share.
    flow = _flow(_entry(remote_type="broadlink", remote_entity="remote.old"))

    result = asyncio.run(flow.async_step_init({"remote_type": "zigbee2mqtt"}))

    assert result["step_id"] == "zigbee2mqtt"
    assert flow.result["remote_entity"] is None


def test_climate_path_saves_through_the_entry_title():
    flow = _flow(_entry(remote_type="ha_remote"))

    asyncio.run(flow.async_step_init({"remote_type": "broadlink"}))
    asyncio.run(flow.async_step_broadlink({"entity_id": "remote.ac"}))
    flow._profile_summary = {"hvac": "1 mode(s): cool"}
    asyncio.run(flow.async_step_profile_review({}))
    asyncio.run(flow.async_step_sensors({}))

    saved = asyncio.run(flow.async_step_finish({}))

    assert saved["type"] == "create_entry"
    assert saved["title"] == "Living Room AC"
