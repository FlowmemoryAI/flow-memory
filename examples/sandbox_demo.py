from flow_memory.action import PythonSandbox

sandbox = PythonSandbox()
print(sandbox.execute("x = sum(range(10))\nprint(x)").stdout)
print(sandbox.execute("open('/etc/passwd').read()").error)
