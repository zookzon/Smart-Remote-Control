import asyncio
import base64
import importlib.util
import json
from pathlib import Path

MODULE = Path(__file__).parents[1] / "custom_components" / "smart_remote_control" / "remote_control.py"
spec = importlib.util.spec_from_file_location("remote_control", MODULE)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
RemoteControl = mod.RemoteControl
RemoteConfigurationError = mod.RemoteConfigurationError
RemoteEncodingError = mod.RemoteEncodingError
RemoteTransportError = mod.RemoteTransportError


class FakeServices:
    def __init__(self):
        self.calls = []

    async def async_call(self, domain, service, data, **kwargs):
        self.calls.append((domain, service, data, kwargs))


class FakeHass:
    def __init__(self):
        self.services = FakeServices()


def run(coro):
    return asyncio.run(coro)


def test_ha_remote_learned_command_payload():
    hass = FakeHass()
    remote = RemoteControl(hass, "ha_remote", remote_entity="remote.test", ha_device_id="Bedroom_AC")
    run(remote._send_via_ha_remote("mode:cool_fan:medium_temp:24.0"))
    assert hass.services.calls[0][0:2] == ("remote", "send_command")
    assert hass.services.calls[0][2] == {
        "entity_id": "remote.test",
        "device": "Bedroom_AC",
        "command": "mode:cool_fan:medium_temp:24.0",
    }


def test_broadlink_base64_token_and_payload():
    hass = FakeHass()
    remote = RemoteControl(hass, "broadlink", remote_entity="remote.broadlink", commands_encoding="Base64")
    run(remote._send_via_broadlink("JgBQAA=="))
    assert hass.services.calls[0][2] == {
        "entity_id": "remote.broadlink",
        "command": ["b64:JgBQAA=="],
    }


def test_broadlink_hex_conversion():
    remote = RemoteControl(FakeHass(), "broadlink", remote_entity="remote.broadlink", commands_encoding="Hex")
    assert remote._broadlink_token("0102ff") == "b64:" + base64.b64encode(bytes.fromhex("0102ff")).decode()


def test_z2m_topic_with_ir_code_suffix():
    hass = FakeHass()
    remote = RemoteControl(
        hass, "zigbee2mqtt", mqtt_topic="zigbee2mqtt/SmartIR/set/ir_code_to_send", commands_encoding="Base64"
    )
    run(remote._send_via_mqtt_dynamic("JgBQAA=="))
    assert hass.services.calls[0][0:2] == ("mqtt", "publish")
    assert hass.services.calls[0][2]["topic"] == "zigbee2mqtt/SmartIR/set"
    assert json.loads(hass.services.calls[0][2]["payload"]) == {"ir_code_to_send": "JgBQAA=="}


def test_z2m_plain_set_topic_defaults_to_ir_code_to_send():
    hass = FakeHass()
    remote = RemoteControl(
        hass, "zigbee2mqtt", mqtt_topic="zigbee2mqtt/SmartIR/set", commands_encoding="raw"
    )
    run(remote._send_via_mqtt_dynamic("123,456,789"))
    assert hass.services.calls[0][2]["topic"] == "zigbee2mqtt/SmartIR/set"
    assert json.loads(hass.services.calls[0][2]["payload"]) == {"ir_code_to_send": "123,456,789"}


class FailingServices:
    async def async_call(self, domain, service, data, **kwargs):
        raise RuntimeError("service unavailable")


class FailingHass:
    def __init__(self):
        self.services = FailingServices()


def test_z2m_missing_topic_is_configuration_error():
    remote = RemoteControl(FakeHass(), "zigbee2mqtt", commands_encoding="Base64")
    try:
        run(remote.send_command("JgBQAA=="))
        assert False, "expected RemoteConfigurationError"
    except RemoteConfigurationError as err:
        assert "topic" in str(err).lower()


def test_z2m_invalid_encoding_is_encoding_error():
    remote = RemoteControl(FakeHass(), "zigbee2mqtt", mqtt_topic="zigbee2mqtt/SmartIR/set", commands_encoding="Hex")
    try:
        run(remote.send_command("0102"))
        assert False, "expected RemoteEncodingError"
    except RemoteEncodingError as err:
        assert "commandsEncoding" in str(err)


def test_broadlink_invalid_hex_is_encoding_error():
    remote = RemoteControl(FakeHass(), "broadlink", remote_entity="remote.broadlink", commands_encoding="Hex")
    try:
        run(remote.send_command("NOT-HEX"))
        assert False, "expected RemoteEncodingError"
    except RemoteEncodingError:
        pass


def test_broadlink_service_failure_is_transport_error():
    remote = RemoteControl(FailingHass(), "broadlink", remote_entity="remote.broadlink", commands_encoding="Base64")
    try:
        run(remote.send_command("JgBQAA=="))
        assert False, "expected RemoteTransportError"
    except RemoteTransportError as err:
        assert "service call failed" in str(err)


def test_z2m_publish_failure_is_transport_error():
    remote = RemoteControl(FailingHass(), "zigbee2mqtt", mqtt_topic="zigbee2mqtt/SmartIR/set", commands_encoding="Base64")
    try:
        run(remote.send_command("JgBQAA=="))
        assert False, "expected RemoteTransportError"
    except RemoteTransportError as err:
        assert "publish failed" in str(err)


def test_localtuya_raw_payload_is_json_string_and_locked_format():
    hass = FakeHass()
    remote = RemoteControl(
        hass, "localtuya", device_id="abc123", dp=201, commands_encoding="raw"
    )
    run(remote._send_via_localtuya("123,456,789"))
    domain, service, data, kwargs = hass.services.calls[0]
    assert (domain, service) == ("localtuya", "set_dp")
    assert data["device_id"] == "abc123"
    assert data["dp"] == 201
    assert isinstance(data["value"], str)
    assert json.loads(data["value"]) == {
        "control": "send_ir",
        "type": 0,
        "head": "",
        "key1": "1123,456,789",
    }
    assert kwargs.get("blocking") is True


def test_localtuya_rejects_non_raw_encoding():
    remote = RemoteControl(FakeHass(), "localtuya", device_id="abc123", dp=201, commands_encoding="Base64")
    try:
        run(remote.send_command("JgBQAA=="))
        assert False, "expected RemoteEncodingError"
    except RemoteEncodingError as err:
        assert "Raw" in str(err)


def test_localtuya_missing_device_or_dp_is_configuration_error():
    remote = RemoteControl(FakeHass(), "localtuya", commands_encoding="raw")
    try:
        run(remote.send_command("123,456"))
        assert False, "expected RemoteConfigurationError"
    except RemoteConfigurationError:
        pass
