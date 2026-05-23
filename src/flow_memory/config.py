"""Runtime configuration."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class RuntimeConfig:
    """Local runtime config for an agent process."""

    data_dir: Path = Path(".flow_memory")
    audit_log_path: Path | None = None
    allow_network_tools: bool = False
    allow_code_execution: bool = False
    max_working_memory_items: int = 7
    default_agent_budget: float = 0.0
    human_approval_required_permissions: frozenset[str] = field(
        default_factory=lambda: frozenset({
            "code.execute",
            "wallet.transfer",
            "browser.automation",
            "marketplace.bid",
            "marketplace.settle",
            "filesystem.write",
            "network.request",
        })
    )
