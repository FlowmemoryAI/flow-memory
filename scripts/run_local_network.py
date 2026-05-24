"""Run local Flow Memory network scenarios."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from flow_memory.network import LocalNetworkOrchestrator

SCENARIOS = ("basic-economy", "neural-agent", "rl-training", "dispute-slashing", "memory-learning", "safety-approval", "all")


def run_local_network(scenario: str = "all", *, emit_visual_events: bool = False) -> dict[str, object]:
    return dict(LocalNetworkOrchestrator().run(scenario, emit_visual_events=emit_visual_events).as_record())


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Flow Memory local network scenarios")
    parser.add_argument("--scenario", default="all", choices=SCENARIOS)
    parser.add_argument("--json-out", type=Path, default=None)
    parser.add_argument("--emit-visual-events", action="store_true", help="Include Mission Control visual events and reduced visual state")
    parser.add_argument("--visual-out", type=Path, default=None, help="Optional path for visual event replay JSON")
    args = parser.parse_args()
    record = run_local_network(args.scenario, emit_visual_events=args.emit_visual_events)
    text = json.dumps(record, indent=2, sort_keys=True, default=str)
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(text + "\n", encoding="utf-8")
    if args.visual_out:
        args.visual_out.parent.mkdir(parents=True, exist_ok=True)
        visual_payload = {
            "ok": bool(record.get("ok")),
            "scenario": args.scenario,
            "events": record.get("visual_events", ()),
            "state": record.get("visual_state", {}),
            "provenance": "live",
        }
        args.visual_out.write_text(json.dumps(visual_payload, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    print(text)
    return 0 if record.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
