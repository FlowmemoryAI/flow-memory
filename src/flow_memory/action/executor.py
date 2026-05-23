"""Policy-gated action executor."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from flow_memory.action.sandbox import PythonSandbox, SandboxViolation
from flow_memory.action.tools import ToolRegistry, default_tool_registry
from flow_memory.core.types import ActionResult, MemoryRecord, Plan

_CODE_ACTIONS = {"python_sandbox", "python.eval", "code.execute.python", "sandbox_python", "sandbox.python"}


@dataclass
class ActionExecutor:
    """Executes approved plans through a constrained action surface.

    Code execution is disabled by default as defense in depth. The cognitive loop can
    create an executor with ``allow_code_execution=True`` only after safety approval.
    """

    tool_registry: ToolRegistry = field(default_factory=default_tool_registry)
    python_sandbox: PythonSandbox = field(default_factory=PythonSandbox)
    memory_snapshot: tuple[MemoryRecord, ...] = ()
    allow_code_execution: bool = False

    def execute(self, plan: Plan) -> ActionResult:
        step_results: list[Mapping[str, Any]] = []
        final_output: Any = None
        side_effects: list[Mapping[str, Any]] = []

        try:
            for step in plan.steps:
                if step.action == "respond":
                    final_output = step.args.get("message", "")
                    step_results.append({"step_id": step.step_id, "action": step.action, "success": True})
                elif step.action == "observe_environment":
                    output = self.tool_registry.call("observe_environment", step.args)
                    final_output = output if final_output is None else final_output
                    step_results.append({"step_id": step.step_id, "action": step.action, "success": True, "output": output})
                    side_effects.append({"kind": "read_only_observation", "tool": "observe_environment"})
                elif step.action == "summarize_memories":
                    limit = int(step.args.get("limit", 5))
                    output = [record.text for record in self.memory_snapshot[-limit:]]
                    final_output = output if final_output is None else final_output
                    step_results.append({"step_id": step.step_id, "action": step.action, "success": True, "output": output})
                elif step.action == "code.execute":
                    if not self.allow_code_execution:
                        raise ValueError("code.execute execution disabled by executor configuration")
                    inputs = step.args.get("inputs", {})
                    prefix = "inputs = " + repr(dict(inputs if isinstance(inputs, Mapping) else {})) + "\n"
                    sandbox_result = self.python_sandbox.run(prefix + str(step.args.get("code", "")))
                    final_output = sandbox_result.as_dict()
                    step_results.append({"step_id": step.step_id, "action": step.action, "success": sandbox_result.success, "output": final_output})
                    if not sandbox_result.success:
                        raise ValueError(sandbox_result.stderr or "Sandbox execution failed")
                elif step.action == "tool":
                    name = str(step.args["name"])
                    args = step.args.get("args", {})
                    if not isinstance(args, Mapping):
                        raise ValueError("Tool args must be a mapping")
                    output = self.tool_registry.call(name, args)
                    final_output = output
                    step_results.append({"step_id": step.step_id, "action": step.action, "tool": name, "success": True, "output": output})
                elif step.action in _CODE_ACTIONS:
                    if not self.allow_code_execution:
                        raise ValueError("python_sandbox execution disabled by executor configuration")
                    sandbox_result = self.python_sandbox.run(str(step.args.get("code", "")))
                    value = sandbox_result.as_dict()
                    final_output = value
                    step_results.append({"step_id": step.step_id, "action": step.action, "success": sandbox_result.success, "output": value})
                    side_effects.append({"kind": "sandboxed_subprocess", "permission": step.required_permission})
                    if not sandbox_result.success:
                        raise RuntimeError(sandbox_result.stderr or f"return code {sandbox_result.returncode}")
                else:
                    raise ValueError(f"Unsupported action: {step.action}")
        except (SandboxViolation, Exception) as exc:  # noqa: BLE001 - executor returns structured failures.
            return ActionResult(
                success=False,
                output=final_output,
                step_results=tuple(step_results),
                side_effects=tuple(side_effects),
                error=str(exc),
            )

        return ActionResult(success=True, output=final_output, step_results=tuple(step_results), side_effects=tuple(side_effects))


@dataclass
class SandboxedExecutor(ActionExecutor):
    """Executor used after safety approval; enables sandboxed code actions."""

    allow_code_execution: bool = True
