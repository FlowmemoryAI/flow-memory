"""Sandboxed Python execution primitives.

The local sandbox validates user code with an AST pass, then executes it in an isolated
Python interpreter with restricted builtins, a timeout, and no network/filesystem helper
APIs exposed through builtins. Production deployments should still place this inside a
container or microVM boundary.
"""

from __future__ import annotations

import ast
import json
import subprocess
import sys
from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence


class SandboxViolation(ValueError):
    """Raised when code violates the sandbox policy."""


@dataclass(frozen=True)
class SandboxResult:
    success: bool
    stdout: str = ""
    stderr: str = ""
    globals: Mapping[str, Any] = field(default_factory=dict)
    error: str | None = None
    returncode: int | None = None
    timed_out: bool = False

    def as_dict(self) -> Mapping[str, Any]:
        return {
            "success": self.success,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "globals": dict(self.globals),
            "error": self.error,
            "returncode": self.returncode,
            "timed_out": self.timed_out,
        }


@dataclass(frozen=True)
class SandboxConfig:
    timeout_seconds: float = 2.0
    memory_limit_mb: int = 0
    max_output_chars: int = 8_000
    allowed_imports: frozenset[str] = frozenset(
        {"math", "statistics", "random", "json", "re", "decimal", "fractions"}
    )
    allowed_builtins: Sequence[str] = (
        "abs",
        "all",
        "any",
        "bool",
        "dict",
        "enumerate",
        "float",
        "int",
        "len",
        "list",
        "max",
        "min",
        "pow",
        "range",
        "round",
        "set",
        "sorted",
        "str",
        "sum",
        "tuple",
        "zip",
        "print",
    )
    blocked_names: Sequence[str] = (
        "eval",
        "exec",
        "compile",
        "open",
        "input",
        "globals",
        "locals",
        "vars",
        "dir",
        "getattr",
        "setattr",
        "delattr",
        "breakpoint",
        "help",
    )


SandboxPolicy = SandboxConfig
PythonSandboxResult = SandboxResult


class _SafetyVisitor(ast.NodeVisitor):
    def __init__(self, config: SandboxConfig) -> None:
        self.config = config

    def visit_Import(self, node: ast.Import) -> None:  # noqa: N802
        for alias in node.names:
            root = alias.name.split(".", 1)[0]
            if root not in self.config.allowed_imports:
                raise SandboxViolation("Imports are disabled")

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:  # noqa: N802
        root = (node.module or "").split(".", 1)[0]
        if root not in self.config.allowed_imports:
            raise SandboxViolation("Imports are disabled")

    def visit_Attribute(self, node: ast.Attribute) -> None:  # noqa: N802
        if node.attr.startswith("__"):
            raise SandboxViolation("Private/dunder attributes are not allowed")
        self.generic_visit(node)

    def visit_Name(self, node: ast.Name) -> None:  # noqa: N802
        if node.id.startswith("__") or node.id in self.config.blocked_names:
            raise SandboxViolation(f"Blocked name in sandbox: {node.id}")
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:  # noqa: N802
        if isinstance(node.func, ast.Name) and node.func.id in self.config.blocked_names:
            raise SandboxViolation(f"Blocked call in sandbox: {node.func.id}")
        self.generic_visit(node)


@dataclass
class SandboxedPythonRunner:
    config: SandboxConfig = field(default_factory=SandboxConfig)

    def validate(self, code: str) -> ast.AST:
        try:
            tree = ast.parse(code, mode="exec")
        except SyntaxError as exc:
            raise SandboxViolation(str(exc)) from exc
        _SafetyVisitor(self.config).visit(tree)
        return tree

    def run(self, code: str, input_data: str = "") -> SandboxResult:
        try:
            self.validate(code)
        except SandboxViolation as exc:
            return SandboxResult(False, stderr=str(exc), error=str(exc), returncode=2)

        marker = "__FLOW_MEMORY_SANDBOX_RESULT__"
        wrapper = f"""
import builtins as _builtins
import contextlib as _contextlib
import io as _io
import json as _json
import sys as _sys
import traceback as _traceback
_allowed_imports = set({_json_dumps(sorted(self.config.allowed_imports))})
_allowed_builtins = {_json_dumps(list(self.config.allowed_builtins))}
_user_code = {_json_dumps(code)}
_max_output = {int(self.config.max_output_chars)}

def _safe_import(name, globals=None, locals=None, fromlist=(), level=0):
    root = name.split('.', 1)[0]
    if root not in _allowed_imports:
        raise ImportError('Import not allowed: ' + root)
    return __import__(name, globals, locals, fromlist, level)

_safe_builtins = {{name: getattr(_builtins, name) for name in _allowed_builtins}}
_safe_builtins['__import__'] = _safe_import
_globals = {{'__builtins__': _safe_builtins}}
_stdout = _io.StringIO()
_stderr = _io.StringIO()
try:
    with _contextlib.redirect_stdout(_stdout), _contextlib.redirect_stderr(_stderr):
        exec(compile(_user_code, '<flow-memory-sandbox>', 'exec'), _globals, _globals)
    _visible = {{
        k: v for k, v in _globals.items()
        if not k.startswith('__') and isinstance(v, (str, int, float, bool, list, tuple, dict, set, type(None)))
    }}
    _payload = {{'success': True, 'stdout': _stdout.getvalue()[:_max_output], 'stderr': _stderr.getvalue()[:_max_output], 'globals': _visible, 'error': None, 'returncode': 0, 'timed_out': False}}
except BaseException as exc:
    _payload = {{'success': False, 'stdout': _stdout.getvalue()[:_max_output], 'stderr': _traceback.format_exc()[:_max_output], 'globals': {{}}, 'error': str(exc), 'returncode': 1, 'timed_out': False}}
print({marker!r} + _json.dumps(_payload, sort_keys=True, default=str))
"""
        try:
            proc = subprocess.run(
                [sys.executable, "-I", "-S", "-c", wrapper],
                input=input_data,
                text=True,
                capture_output=True,
                timeout=self.config.timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return SandboxResult(False, error="Sandbox execution timed out", returncode=-9, timed_out=True)

        result_line = None
        for line in reversed(proc.stdout.splitlines()):
            if line.startswith(marker):
                result_line = line[len(marker) :]
                break
        if result_line is None:
            return SandboxResult(
                False,
                stdout=proc.stdout[: self.config.max_output_chars],
                stderr=proc.stderr[: self.config.max_output_chars],
                error="Sandbox wrapper did not return a result",
                returncode=proc.returncode,
            )
        payload = json.loads(result_line)
        return SandboxResult(**payload)


class PythonSubprocessSandbox(SandboxedPythonRunner):
    """Compatibility wrapper with resource keyword arguments."""

    def __init__(self, timeout_seconds: float = 2.0, memory_limit_mb: int = 0) -> None:
        super().__init__(config=SandboxConfig(timeout_seconds=timeout_seconds, memory_limit_mb=memory_limit_mb))


class PythonSandbox:
    """Convenience sandbox exposing both execute() and run()."""

    def __init__(self, timeout_seconds: float = 2.0, memory_limit_mb: int = 0) -> None:
        self.runner = SandboxedPythonRunner(
            SandboxConfig(
                timeout_seconds=timeout_seconds,
                memory_limit_mb=memory_limit_mb,
                allowed_imports=frozenset(),
            )
        )

    def execute(self, code: str) -> SandboxResult:
        return self.runner.run(code)

    def run(self, code: str, inputs: Mapping[str, object] | None = None) -> SandboxResult:
        prefix = "inputs = " + json.dumps(dict(inputs or {}), sort_keys=True) + "\n"
        return self.execute(prefix + code)


@dataclass(frozen=True)
class ContainerSandboxSpec:
    """Deployment-time container/microVM sandbox configuration seam."""

    image: str = "python:3.12-slim"
    network: str = "none"
    read_only_rootfs: bool = True
    memory_limit_mb: int = 256
    cpu_limit: float = 1.0


def _json_dumps(value: Any) -> str:
    return json.dumps(value, sort_keys=True)
