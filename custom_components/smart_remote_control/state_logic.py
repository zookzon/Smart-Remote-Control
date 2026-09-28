"""Pure Climate state helpers used by runtime and regression tests."""
from __future__ import annotations
from numbers import Number

def estimate_hvac_action(mode,current,target,*,has_temperature_sensor:bool):
    mode=str(mode); has_feedback=has_temperature_sensor and current is not None and target is not None
    if mode=="off": return "off"
    if mode=="cool": return "cooling" if (not has_feedback or current>target) else "idle"
    if mode=="heat": return "heating" if (not has_feedback or current<target) else "idle"
    if mode=="auto":
        if not has_feedback or current==target: return "idle"
        return "cooling" if current>target else "heating"
    if mode=="dry": return "drying"
    if mode=="fan_only": return "fan"
    return "idle"

def restore_choice(value,supported,default=None):
    supported=list(supported or [])
    if value in supported:return value
    if default in supported:return default
    return supported[0] if supported else None

def restore_hvac_mode(value,supported):
    supported_values=[str(item) for item in (supported or [])]; value=str(value) if value is not None else "off"
    return value if value in supported_values else "off"

def normalize_temperature(value,minimum,maximum,step,default):
    if not isinstance(value,Number): value=default
    value=float(value); minimum=float(minimum); maximum=float(maximum); step=float(step or 1.0); value=min(max(value,minimum),maximum)
    steps=round((value-minimum)/step); aligned=minimum+steps*step; aligned=min(max(aligned,minimum),maximum)
    return round(aligned,6)
