"""FlowIR economy adapters."""

from __future__ import annotations

from typing import Any, Mapping

from flow_memory.ir.economy import EconomicSpec


def economy_config_from_ir(economy: EconomicSpec) -> Mapping[str, Any]:
    return economy.as_manifest()
