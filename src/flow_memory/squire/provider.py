"""usepod-agent provider-side monetization planning seam."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(frozen=True)
class UsePodProviderPlan:
    provider_mode_recommended: bool
    gpu_available: bool
    required_steps: tuple[str, ...]
    required_capabilities: tuple[str, ...]
    bond_notice: str = "$50 USDC bond is described by public UsePod provider docs; verify current docs before acting."
    payout_notice: str = "Live docs describe provider/treasury split; verify current terms before hosting."
    live_or_roadmap: str = "live public provider runtime; coordinator internals private"

    def as_record(self) -> Mapping[str, Any]:
        return dict(self.__dict__)


def build_provider_setup_plan(*, gpu_available: bool, wants_monetization: bool = True) -> UsePodProviderPlan:
    steps = [
        "Verify local GPU, VRAM, disk, and uptime expectations.",
        "Install usepod-agent from the public provider runtime instructions; do not vendor coordinator code.",
        "Generate or load provider Ed25519 identity through usepod-agent.",
        "Configure model backend: vLLM, llama.cpp server, LM Studio, or Ollama.",
        "Set advertised model capabilities and USDC microunit prices.",
        "Enroll with coordinator and satisfy bond requirement only after explicit operator approval.",
        "Run as a managed service with outbound WebSocket only.",
        "Record jobs, payouts, canaries, reputation changes, and downtime in Flow Memory economic memory.",
    ]
    if not gpu_available:
        steps = ["GPU not detected; keep provider mode as a roadmap/setup plan until hardware is available.", *steps]
    return UsePodProviderPlan(
        provider_mode_recommended=bool(wants_monetization and gpu_available),
        gpu_available=gpu_available,
        required_steps=tuple(steps),
        required_capabilities=("eligible GPU", "model server", "operator identity", "USDC bond approval", "network egress"),
    )
