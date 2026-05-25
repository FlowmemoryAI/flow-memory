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
If the GLSL TOP is black, open neural_loom_glsl and press Load Uniform Names, then set vector uniform uTime to absTime.seconds.
Use the GLSL TOP Info DAT to inspect compile errors.
"""

base.viewer = True
base.display = True
print("Created", base.path, "->", out.path)
