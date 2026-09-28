"""Best-effort discovery helpers for LocalTuya Direct IR."""
from __future__ import annotations
from typing import Any

class LocalTuyaDevice:
    def __init__(self, device_id: str, name: str, dps: tuple[int, ...] = ()):
        self.device_id = device_id; self.name = name; self.dps = dps

def _dp_values(value: Any) -> set[int]:
    found: set[int] = set()
    if isinstance(value, dict):
        for key, child in value.items():
            if str(key).lower() in {"dp", "id", "dp_id", "dpid"}:
                try:
                    dp = int(child)
                    if 1 <= dp <= 999: found.add(dp)
                except (TypeError, ValueError): pass
            found.update(_dp_values(child))
    elif isinstance(value, (list, tuple)):
        for child in value: found.update(_dp_values(child))
    return found

def _device_records_from_entry(entry: Any) -> list[LocalTuyaDevice]:
    data = getattr(entry, "data", {}) or {}; title = getattr(entry, "title", "LocalTuya") or "LocalTuya"; records=[]
    devices=data.get("devices")
    if isinstance(devices, dict):
        for dev_id,cfg in devices.items():
            if not dev_id: continue
            cfg=cfg if isinstance(cfg,dict) else {}; name=cfg.get("friendly_name") or cfg.get("name") or str(dev_id)
            records.append(LocalTuyaDevice(str(dev_id),str(name),tuple(sorted(_dp_values(cfg)))))
        return records
    dev_id=data.get("device_id") or data.get("id")
    if dev_id:
        name=data.get("friendly_name") or data.get("name") or title
        records.append(LocalTuyaDevice(str(dev_id),str(name),tuple(sorted(_dp_values(data)))))
    return records

def discover_localtuya_devices(hass: Any) -> list[LocalTuyaDevice]:
    merged={}
    try: entries=hass.config_entries.async_entries("localtuya")
    except Exception: entries=[]
    for entry in entries:
        for rec in _device_records_from_entry(entry): merged[rec.device_id]=rec
    domain_data=getattr(hass,"data",{}).get("localtuya",{}); runtime_maps=[]
    if isinstance(domain_data,dict):
        for value in domain_data.values():
            if isinstance(value,dict): runtime_maps.append(value)
        runtime_maps.append(domain_data)
    for mapping in runtime_maps:
        for dev_id,obj in mapping.items():
            if not isinstance(dev_id,str) or len(dev_id)<4 or dev_id in merged: continue
            name=getattr(obj,"name",None) or getattr(obj,"friendly_name",None) or dev_id
            merged[dev_id]=LocalTuyaDevice(dev_id,str(name),())
    return sorted(merged.values(),key=lambda x:(x.name.lower(),x.device_id))

def recommended_dp(dps: tuple[int, ...] | list[int]) -> int | None:
    values={int(x) for x in dps}; return 201 if 201 in values else None
