from flow_memory.action.sandbox import SandboxedPythonRunner

runner = SandboxedPythonRunner()
result = runner.run("import math\nprint(round(math.sqrt(81), 2))")
print(result.as_dict())
