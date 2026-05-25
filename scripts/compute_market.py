"""Build a Flow Memory compute-market plan without live settlement."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from flow_memory.compute_market import build_compute_plan


def run_compute_market_plan(args: argparse.Namespace) -> dict[str, object]:
    payload = {
        "task": args.task,
        "selection_strategy": args.selection_strategy,
        "scenario": args.scenario,
        "dry_run": True,
        "policy": {
            "marketplace_only": args.marketplace_only,
            "allowed_assets": tuple(args.asset),
            "allowed_networks": tuple(args.network),
            "max_total_cost": args.max_total_cost,
            "fallback_allowed": not args.fallback_denied,
            "dry_run_required": True,
            "allow_unknown_price": args.allow_unknown_price,
        },
    }
    return {"ok": True, "compute_plan": build_compute_plan(payload).as_record()}


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a Flow Memory compute-market plan")
    parser.add_argument("--task", default="run agent batch inference")
    parser.add_argument("--selection-strategy", default="balanced")
    parser.add_argument("--scenario", default="provider_quote_available")
    parser.add_argument("--marketplace-only", action="store_true")
    parser.add_argument("--asset", action="append", default=[])
    parser.add_argument("--network", action="append", default=[])
    parser.add_argument("--max-total-cost", type=float, default=0.0)
    parser.add_argument("--fallback-denied", action="store_true")
    parser.add_argument("--allow-unknown-price", action="store_true")
    parser.add_argument("--json-out", type=Path, default=None)
    args = parser.parse_args()
    payload = run_compute_market_plan(args)
    text = json.dumps(payload, indent=2, sort_keys=True, default=str)
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
