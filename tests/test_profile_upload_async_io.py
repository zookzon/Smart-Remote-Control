"""Regression coverage for non-blocking profile upload handling."""
import ast
import asyncio
import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT))

from custom_components.smart_remote_control import config_flow


MODULE = (
    Path(__file__).parents[1]
    / "custom_components"
    / "smart_remote_control"
    / "config_flow.py"
)


class _FakeHass:
    def __init__(self):
        self.executor_calls = []

    async def async_add_executor_job(self, target, *args):
        self.executor_calls.append((target, args))
        return target(*args)


def _flow(hass):
    flow = object.__new__(config_flow.ConfigFlow)
    flow.hass = hass
    flow._data = {}
    flow._profile_summary = {}
    flow._profile_warnings = ""
    return flow


def _profile_upload_method() -> ast.AsyncFunctionDef:
    tree = ast.parse(MODULE.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "async_step_profile_upload":
            return node
    raise AssertionError("async_step_profile_upload was not found")


def test_profile_upload_reads_file_in_home_assistant_executor():
    """Profile files must not be synchronously read in Home Assistant's event loop."""
    method = _profile_upload_method()
    source = ast.unparse(method)

    assert "await self.hass.async_add_executor_job(path.read_text, 'utf-8')" in source
    assert "json.loads(path.read_text(encoding='utf-8'))" not in source


def test_profile_upload_uses_executor_and_keeps_parsed_profile(tmp_path, monkeypatch):
    """A valid upload is read off-loop and continues with its parsed profile."""
    payload = {"commands": {"off": "code"}}
    path = tmp_path / "profile.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    hass = _FakeHass()
    flow = _flow(hass)
    expected = {"type": "form", "step_id": "profile_summary"}

    monkeypatch.setattr(config_flow, "process_uploaded_file", AsyncMock(return_value=path))
    monkeypatch.setattr(config_flow, "validate_climate_profile", lambda profile: None)
    monkeypatch.setattr(config_flow, "profile_summary", lambda profile: {"commands": "1"})
    flow.async_step_profile_summary = AsyncMock(return_value=expected)

    result = asyncio.run(flow.async_step_profile_upload({config_flow.CONF_PROFILE_FILE: object()}))

    assert result == expected
    assert flow._data[config_flow.CONF_DEVICE_PROFILE] == payload
    assert flow._profile_summary == {"commands": "1"}
    assert len(hass.executor_calls) == 1
    target, args = hass.executor_calls[0]
    assert target.__self__ == path
    assert target.__name__ == "read_text"
    assert args == ("utf-8",)


def test_profile_upload_rejects_invalid_json(tmp_path, monkeypatch):
    """Malformed uploads still report the existing invalid-profile error."""
    path = tmp_path / "invalid.json"
    path.write_text("{", encoding="utf-8")
    flow = _flow(_FakeHass())

    monkeypatch.setattr(config_flow, "process_uploaded_file", AsyncMock(return_value=path))
    flow.async_show_form = lambda **kwargs: kwargs

    result = asyncio.run(flow.async_step_profile_upload({config_flow.CONF_PROFILE_FILE: object()}))

    assert result["step_id"] == "profile_upload"
    assert result["errors"] == {"base": "invalid_profile"}
