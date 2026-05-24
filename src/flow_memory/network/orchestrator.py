"""Scenario orchestrator for the local Flow Memory network."""
from __future__ import annotations

from dataclasses import dataclass, field

from flow_memory.network.local_network import LocalFlowMemoryNetwork
from flow_memory.network.reports import LocalNetworkReport


@dataclass
class LocalNetworkOrchestrator:
    network: LocalFlowMemoryNetwork = field(default_factory=LocalFlowMemoryNetwork)

    def run(self, scenario: str = "all") -> LocalNetworkReport:
        return self.network.run(scenario)
