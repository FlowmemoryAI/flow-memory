"""Demonstrate the Squire Goal Orchestrator without network calls or funds."""
from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from flow_memory.squire import build_squire_goal_plan
from flow_memory.squire.models import SquireEnvironment


def main() -> int:
    environment = SquireEnvironment(
        has_solana_wallet=False,
        has_level5_token=False,
        has_usepod_token=False,
        funded_balance=False,
        gpu_available=False,
        constraints={"network_calls_enabled": False, "real_funds_enabled": False},
    )
    plan = build_squire_goal_plan(
        "Use SQUIRE ecosystem tools to route cheap inference, keep a budget ceiling, and prepare provider monetization later",
        environment=environment,
    )
    payload = {
        "ok": True,
        "mode": plan.recommended_operating_mode,
        "live_stack": plan.live_stack_to_use_now,
        "selected_route": plan.budget_and_routing_policy["selected_route"],
        "memory_fields": tuple(plan.memory_writes[0].keys()),
        "roadmap_items": plan.optional_roadmap_extensions,
        "safety": "no real funds, no network calls, no fabricated balances",
    }
    print(json.dumps(payload, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
