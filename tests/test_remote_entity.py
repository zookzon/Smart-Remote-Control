import ast, pathlib
REMOTE=pathlib.Path(__file__).parents[1]/"custom_components"/"smart_remote_control"/"remote.py"
tree=ast.parse(REMOTE.read_text())
def f(name):
 n=next(x for x in tree.body if isinstance(x,ast.FunctionDef) and x.name==name); ns={"json":__import__("json")}; exec(compile(ast.Module(body=[n],type_ignores=[]),str(REMOTE),"exec"),ns); return ns[name]
strip_optional_prefix=f("strip_optional_prefix"); mqtt_payload_for_topic=f("mqtt_payload_for_topic")
def test_no_prefix(): assert strip_optional_prefix("ABC","")=="ABC"
def test_prefix(): assert strip_optional_prefix("b64:ABC","b64:")=="ABC"
def test_direct(): assert mqtt_payload_for_topic("zigbee2mqtt/SmartIR/set/ir_code_to_send","ABC")=="ABC"
def test_alt(): assert mqtt_payload_for_topic("zigbee2mqtt/SmartIR/set/code_to_send","ABC")=="ABC"
def test_set(): assert mqtt_payload_for_topic("zigbee2mqtt/SmartIR/set","ABC")=='{"ir_code_to_send":"ABC"}'
