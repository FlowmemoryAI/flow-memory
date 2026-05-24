"""Squire ecosystem control-plane seams for Flow Memory.

This package models Squire as an agentic compute treasury/routing substrate.
It deliberately implements local planning, policy, telemetry, and adapter seams only:
no real funds, private keys, token redemptions, or live network calls are performed by
base code or tests.
"""
from __future__ import annotations

from flow_memory.squire.models import (
    AgentTreasury,
    EconomicMemoryRecord,
    SquireEnvironment,
    SquireMode,
    SquirePlan,
    SquireRoutingPolicy,
)
from flow_memory.squire.orchestrator import build_squire_goal_plan, classify_squire_goal, inspect_squire_environment
from flow_memory.squire.routing import choose_route, level5_proxy_base_url, parse_usepod_response_headers, usepod_proxy_base_url

__all__ = [
    "AgentTreasury",
    "EconomicMemoryRecord",
    "SquireEnvironment",
    "SquireMode",
    "SquirePlan",
    "SquireRoutingPolicy",
    "build_squire_goal_plan",
    "choose_route",
    "classify_squire_goal",
    "inspect_squire_environment",
    "level5_proxy_base_url",
    "parse_usepod_response_headers",
    "usepod_proxy_base_url",
]
