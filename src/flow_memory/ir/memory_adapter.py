"""FlowIR memory adapters."""

from __future__ import annotations

from typing import Any, Mapping

from flow_memory.ir.memory import MemorySpec


def memory_config_from_ir(memory: MemorySpec) -> Mapping[str, Any]:
    return memory.as_manifest()
