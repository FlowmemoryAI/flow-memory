# ruff: noqa: F821
"""
Run this inside TouchDesigner Textport:
exec(open(r"E:\\FlowMemory\\flow-memory\\tools\\touchdesigner\\create_flowmemory_neural_loom.py").read())

It creates /project1/flowmemory_neural_loom with a GLSL TOP neural-network/strand shader.
"""

from pathlib import Path

SCRIPT_PATH = Path(__file__).resolve() if "__file__" in globals() else Path(r"E:\FlowMemory\flow-memory\tools\touchdesigner\create_flowmemory_neural_loom.py")
SHADER_PATH = SCRIPT_PATH.with_name("flowmemory_neural_loom.frag")
SHADER_TEXT = SHADER_PATH.read_text(encoding="utf-8")

root = op("/project1")
if root is None:
    raise RuntimeError("/project1 was not found. Open a normal TouchDesigner project first.")

existing = root.op("flowmemory_neural_loom")
if existing is not None:
    existing.destroy()

base = root.create(baseCOMP, "flowmemory_neural_loom")
base.nodeX = 0
base.nodeY = 0
base.par.w = 960
base.par.h = 540

shader_dat = base.create(textDAT, "neural_loom_pixel")
shader_dat.text = SHADER_TEXT
shader_dat.nodeX = -300
shader_dat.nodeY = 120

glsl = base.create(glslTOP, "neural_loom_glsl")
glsl.nodeX = -40
glsl.nodeY = 120

# Parameter names can vary slightly by TouchDesigner build; set only when present.
def set_par(comp, name, value=None, expr=None):
    par = getattr(comp.par, name, None)
    if par is None:
        return False
    if expr is not None:
        par.expr = expr
    else:
        par.val = value
    return True

set_par(glsl, "glslversion", "glsl460")
set_par(glsl, "pixeldat", shader_dat.path)
set_par(glsl, "outputresolution", "custom")
set_par(glsl, "resolutionw", 1920)
set_par(glsl, "resolutionh", 1080)
set_par(glsl, "vec0name", "uTime")
set_par(glsl, "vec0valuex", expr="absTime.seconds")

telemetry_json = None
udp_dat_type = globals().get("udpinDAT")
json_dat_type = globals().get("jsonDAT")
if udp_dat_type is not None and json_dat_type is not None:
    udp_in = base.create(udp_dat_type, "flowmemory_udp_in")
    udp_in.nodeX = -300
    udp_in.nodeY = -110
    set_par(udp_in, "port", 7000)
    set_par(udp_in, "format", "perline")
    set_par(udp_in, "maxlines", 1)
    set_par(udp_in, "active", True)

    telemetry_json = base.create(json_dat_type, "flowmemory_telemetry_json")
    telemetry_json.nodeX = -40
    telemetry_json.nodeY = -110
    telemetry_json.setInput(0, udp_in)

def metric_expr(name, default="0"):
    if telemetry_json is None:
        return default
    telemetry_path = telemetry_json.path
    return (
        f"(op('{telemetry_path}').result or {{}})"
        f".get('metrics', {{}}).get('{name}', {default})"
    )

def frame_expr(name, default="0"):
    if telemetry_json is None:
        return default
    return f"1 if (op('{telemetry_json.path}').result or {{}}).get('{name}', False) else {default}"

set_par(glsl, "vec1name", "uTelemetry0")
set_par(glsl, "vec1valuex", expr=metric_expr("signal"))
set_par(glsl, "vec1valuey", expr=metric_expr("learning_tick_count"))
set_par(glsl, "vec1valuez", expr=metric_expr("agent_count"))
set_par(glsl, "vec1valuew", expr=metric_expr("event_rate"))

set_par(glsl, "vec2name", "uTelemetry1")
set_par(glsl, "vec2valuex", expr=metric_expr("memory_activation_count"))
set_par(glsl, "vec2valuey", expr=metric_expr("risk"))
set_par(glsl, "vec2valuez", expr=metric_expr("confidence"))
set_par(glsl, "vec2valuew", expr=frame_expr("connected", "0"))

level = base.create(levelTOP, "contrast_and_bloom_bias")
level.nodeX = 200
level.nodeY = 120
level.setInput(0, glsl)
set_par(level, "brightness1", 1.05)
set_par(level, "gamma1", 0.92)
set_par(level, "opacity", 1)

out = base.create(nullTOP, "out1")
out.nodeX = 430
out.nodeY = 120
out.setInput(0, level)
out.viewer = True
out.display = True
out.render = True

note = base.create(textDAT, "README_run_notes")
note.nodeX = -300
note.nodeY = -80
note.text = """FlowMemory Neural Loom

View /project1/flowmemory_neural_loom/out1.

Live data bridge:
1. Start the local API when you want live telemetry:
   python scripts/run_local_api_server.py
2. Start the read-only TouchDesigner UDP bridge from the repo root:
   python tools/touchdesigner/flowmemory_td_bridge.py --stdout
3. This TouchDesigner component listens on UDP port 7000 when the installed build exposes udpinDAT/jsonDAT.
   If those DAT classes were not created automatically, add a UDP In DAT manually:
   - Port: 7000
   - Row/Callback Format: One Per Line
   - Clamp/max lines: 1
   Then feed it into a JSON DAT and map metrics.signal, metrics.learning_tick_count,
   metrics.agent_count, metrics.event_rate, metrics.memory_activation_count, metrics.risk,
   and metrics.confidence into neural_loom_glsl uniforms uTelemetry0/uTelemetry1.

The bridge is visualization-only: it only reads GET telemetry endpoints and never starts,
stops, learns, settles, or controls agents.
If the GLSL TOP is black, open neural_loom_glsl and press Load Uniform Names.
Use the GLSL TOP Info DAT to inspect compile errors.
"""

base.viewer = True
base.display = True
print("Created", base.path, "->", out.path)
