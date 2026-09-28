import ast
from pathlib import Path

PATH = Path(__file__).parents[1] / "custom_components" / "smart_remote_control" / "config_flow.py"
TREE = ast.parse(PATH.read_text(encoding="utf-8"))

def _class(name):
    return next(n for n in TREE.body if isinstance(n, ast.ClassDef) and n.name == name)

def _methods(cls, name):
    return [n for n in cls.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == name]

def test_config_flow_has_one_remote_backend_step():
    cls = _class("ConfigFlow")
    methods = _methods(cls, "async_step_remote_backend")
    assert len(methods) == 1
    source = ast.unparse(methods[0])
    assert "self._defs()" not in source
    assert "self._data" in source

def test_options_flow_has_one_remote_backend_step():
    cls = _class("OptionsFlowHandler")
    methods = _methods(cls, "async_step_remote_backend")
    assert len(methods) == 1
    source = ast.unparse(methods[0])
    assert "self._defs()" in source
    assert "self._set" in source

def test_remote_options_steps_are_in_options_class():
    cls = _class("OptionsFlowHandler")
    names = {n.name for n in cls.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
    assert {
        "async_step_remote_backend",
        "async_step_remote_mqtt",
        "async_step_remote_localtuya",
        "async_step_remote_localtuya_dp",
        "async_step_remote_localtuya_prefix",
        "async_step_remote_finish",
    } <= names
