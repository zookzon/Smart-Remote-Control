"""Standalone IR-code Remote entities for Smart Remote Control."""
from __future__ import annotations
import asyncio, json, logging
from typing import Any, Iterable
from homeassistant.components.remote import RemoteEntity
from homeassistant.helpers.entity import DeviceInfo
from .const import DOMAIN, CONF_DEVICE_TYPE, CONF_REMOTE_BACKEND, CONF_MQTT_TOPIC, CONF_DEVICE_ID, CONF_DP, CONF_IR_PREFIX
_LOGGER=logging.getLogger(__name__)

def strip_optional_prefix(command: str, prefix: str) -> str:
    code=str(command).strip(); prefix=str(prefix or "")
    if not code: raise ValueError("IR code cannot be empty")
    if not prefix: return code
    if not code.startswith(prefix): raise ValueError(f"IR command must start with configured prefix: {prefix}")
    code=code[len(prefix):]
    if not code: raise ValueError("IR code cannot be empty after removing prefix")
    return code

def mqtt_payload_for_topic(topic: str, code: str) -> str:
    topic=str(topic).strip().rstrip("/")
    if not topic: raise ValueError("MQTT topic is not configured")
    if topic.endswith("/set"): return json.dumps({"ir_code_to_send":code}, separators=(",",":"))
    if "/set/" in topic:
        prop=topic.rsplit("/set/",1)[1]
        if not prop or "/" in prop: raise ValueError("MQTT topic must end with /set or /set/<property>")
        return code
    raise ValueError("MQTT topic must end with /set or /set/<property>")

async def async_setup_entry(hass, entry, async_add_entities):
    config=dict(entry.data); config.update(entry.options)
    if config.get(CONF_DEVICE_TYPE,"climate") != "remote": return
    async_add_entities([SmartRemoteIREntity(hass,entry.entry_id,config)],True)

class SmartRemoteIREntity(RemoteEntity):
    _attr_should_poll=False; _attr_is_on=True
    def __init__(self,hass,entry_id,config):
        self.hass=hass; self._config=config; self._backend=config[CONF_REMOTE_BACKEND]
        self._attr_name=config.get("name") or "Smart Remote"; self._attr_unique_id=config.get("unique_id") or entry_id
        self._attr_device_info=DeviceInfo(identifiers={(DOMAIN,self._attr_unique_id)},name=self._attr_name,manufacturer="Smart Remote Control",model="IR Remote Blaster")
    async def async_turn_on(self,**kwargs): self._attr_is_on=True; self.async_write_ha_state()
    async def async_turn_off(self,**kwargs): self._attr_is_on=False; self.async_write_ha_state()
    async def async_send_command(self,command: Iterable[str],**kwargs: Any):
        commands=[str(x) for x in command]; delay=max(0.0,float(kwargs.get("delay_secs",0) or 0)); repeats=max(1,int(kwargs.get("num_repeats",1) or 1))
        for r in range(repeats):
            for i,val in enumerate(commands):
                code=strip_optional_prefix(val,self._config.get(CONF_IR_PREFIX,""))
                if self._backend=="mqtt": await self._send_mqtt(code)
                elif self._backend=="localtuya": await self._send_localtuya(code)
                else: raise ValueError(f"Unsupported Remote backend: {self._backend}")
                if delay and (r != repeats-1 or i != len(commands)-1): await asyncio.sleep(delay)
    async def _send_mqtt(self,code):
        topic=str(self._config.get(CONF_MQTT_TOPIC,"")).strip().rstrip("/"); payload=mqtt_payload_for_topic(topic,code)
        await self.hass.services.async_call("mqtt","publish",{"topic":topic,"payload":payload,"qos":0,"retain":False},blocking=True)
    async def _send_localtuya(self,code):
        device_id=self._config.get(CONF_DEVICE_ID); dp=self._config.get(CONF_DP)
        if not device_id or dp is None: raise ValueError("LocalTuya Device ID / DP is not configured")
        ir_code=f"1{code}"; payload=json.dumps({"control":"send_ir","type":0,"head":"","key1":ir_code})
        await self.hass.services.async_call("localtuya","set_dp",{"device_id":device_id,"dp":int(dp),"value":payload},blocking=True)
