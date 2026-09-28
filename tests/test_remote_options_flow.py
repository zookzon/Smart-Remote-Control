from pathlib import Path

SOURCE = (Path(__file__).parents[1] / "custom_components" / "smart_remote_control" / "config_flow.py").read_text()

def test_options_routes_remote_entries_away_from_climate():
    assert 'get(CONF_DEVICE_TYPE, "climate") == "remote"' in SOURCE
    assert "return await self.async_step_remote_backend()" in SOURCE

def test_remote_options_support_both_backends():
    assert "async def async_step_remote_mqtt" in SOURCE
    assert "async def async_step_remote_localtuya" in SOURCE
    assert "async def async_step_remote_localtuya_dp" in SOURCE
    assert "async def async_step_remote_localtuya_prefix" in SOURCE

def test_remote_options_preserve_simple_prefix_contract():
    assert "_schema_remote_mqtt(self._defs())" in SOURCE
    assert "_schema_remote_prefix(self._defs())" in SOURCE
