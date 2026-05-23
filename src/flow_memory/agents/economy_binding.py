"""Agent economy binding."""

from __future__ import annotations

from typing import Any, Mapping

from flow_memory.economy.economy_v3 import EconomyV3


class AgentEconomyBinding:
    def __init__(self, economy: EconomyV3 | None = None) -> None:
        self.economy = economy or EconomyV3()

    def maybe_settle(self, requester: str, worker: str, goal: str, amount: float) -> Mapping[str, Any] | None:
        if amount <= 0:
            return None
        return self.economy.run_success_lifecycle(requester=requester, worker=worker, title=goal, reward=amount)
