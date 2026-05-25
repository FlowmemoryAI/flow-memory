"""Source-tree package shim for local Flow Memory commands and tests.

The project uses a ``src/`` layout. This shim makes ``python -m flow_memory``
resolve to the checkout under ``src/flow_memory`` even if another editable
worktree is installed in the interpreter.
"""
from __future__ import annotations

from pathlib import Path

_SRC_PACKAGE = Path(__file__).resolve().parents[1] / "src" / "flow_memory"
_SRC_INIT = _SRC_PACKAGE / "__init__.py"

__path__ = [str(_SRC_PACKAGE)]
__file__ = str(_SRC_INIT)

_code = compile(_SRC_INIT.read_text(encoding="utf-8"), str(_SRC_INIT), "exec")
exec(_code, globals(), globals())
