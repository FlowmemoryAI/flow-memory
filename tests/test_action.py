import unittest

from flow_memory.action import PythonSubprocessSandbox, Tool, ToolRegistry
from flow_memory.core.types import Plan, PlanStep
from flow_memory.action.executor import ActionExecutor


class ActionTests(unittest.TestCase):
    def test_tool_schema_validation(self) -> None:
        registry = ToolRegistry()
        registry.register(
            Tool(
                name="count",
                description="count",
                input_schema={"type": "object", "required": ["text"], "properties": {"text": {"type": "string"}}},
                handler=lambda args: {"n": len(args["text"].split())},
            )
        )
        self.assertEqual(registry.call("count", {"text": "a b"})["n"], 2)
        with self.assertRaises(ValueError):
            registry.call("count", {})

    def test_python_sandbox_runs(self) -> None:
        result = PythonSubprocessSandbox(timeout_seconds=2).run("print(2 + 2)")
        self.assertTrue(result.success)
        self.assertEqual(result.stdout.strip(), "4")

    def test_executor_blocks_code_by_default(self) -> None:
        executor = ActionExecutor()
        plan = Plan(goal="code", steps=(PlanStep(action="python_sandbox", args={"code": "print(1)"}, required_permission="code.execute"),))
        result = executor.execute(plan)
        self.assertFalse(result.success)
        self.assertIn("disabled", result.error or "")


if __name__ == "__main__":
    unittest.main()
