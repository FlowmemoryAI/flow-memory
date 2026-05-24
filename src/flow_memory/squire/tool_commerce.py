"""HTTP 402 / MPP machine-payment planning seams.

The module produces auditable execution plans for agent-wallet style paid tools.
It does not execute wallet commands or move funds.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(frozen=True)
class MachinePaymentPlan:
    service: str
    url: str
    method: str = "GET"
    wallet_pubkey: str = ""
    max_payment_usdc: float = 0.0
    command: tuple[str, ...] = ()
    live_or_roadmap: str = "live"
    safety_notes: tuple[str, ...] = (
        "Do not execute without explicit wallet funding and approval.",
        "Record HTTP 402 challenge, payment amount, and receipt before continuing.",
    )

    def as_record(self) -> Mapping[str, Any]:
        return dict(self.__dict__)


def build_agent_wallet_payment_plan(
    *,
    service: str,
    url: str,
    wallet_pubkey: str = "",
    max_payment_usdc: float = 0.0,
    method: str = "GET",
) -> MachinePaymentPlan:
    if not url.startswith(("https://", "http://")):
        raise ValueError("paid tool URL must be HTTP(S)")
    command = (
        "agent-wallet",
        "request",
        "--method",
        method.upper(),
        "--max-usdc",
        f"{max(0.0, max_payment_usdc):.6f}",
        url,
    )
    return MachinePaymentPlan(service=service, url=url, method=method.upper(), wallet_pubkey=wallet_pubkey, max_payment_usdc=max(0.0, max_payment_usdc), command=command)


def mpp_memory_fields() -> tuple[str, ...]:
    return ("service", "url", "method", "wallet_pubkey", "max_payment_usdc", "receipt", "http_402_challenge", "live_or_roadmap")
