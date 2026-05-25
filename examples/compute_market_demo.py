"""Demonstrate Flow Memory Compute Market planning without funds or network calls."""
from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from flow_memory.compute_market import build_compute_plan


def main() -> int:
    plan = build_compute_plan(
        {
            "task": "route a batch inference job with budget controls",
            "estimated_value": 4.0,
            "selection_strategy": "marketplace_preferred",
            "policy": {
                "marketplace_only": True,
                "allowed_assets": ("USDC",),
                "allowed_networks": ("solana",),
                "max_total_cost": 10.0,
                "dry_run_required": True,
            },
        }
    )
    payload = {
        "ok": plan.ok,
        "selected_route": plan.selected_route,
        "normalized_quote": plan.normalized_quote,
        "rejected_reasons": plan.rejected_reasons,
        "payment_plan": plan.payment_plan,
        "economic_memory_preview": plan.economic_memory_preview,
        "warnings": plan.warnings,
    }
    print(json.dumps(payload, indent=2, sort_keys=True, default=str))
    return 0 if plan.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
