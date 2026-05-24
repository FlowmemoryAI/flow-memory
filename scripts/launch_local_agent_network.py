"""Launch the local multi-agent Flow Memory network demo."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from flow_memory.network import LocalNetworkOrchestrator
from scripts.run_local_network import SCENARIOS


def launch_local_agent_network(scenario: str = "all", *, emit_visual_events: bool = False) -> dict[str, object]:
    report = LocalNetworkOrchestrator().run(scenario, emit_visual_events=emit_visual_events).as_record()
    visual = {
        "event_count": len(tuple(report.get("visual_events", ()))),
        "state_present": bool(report.get("visual_state")),
    }
    return {"ok": bool(report.get("ok")), "launch_mode": "local_agent_network", "scenario": scenario, "visual": visual, "report": report}


def write_payload(payload: dict[str, object], path: Path | None) -> None:
    if path is not None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Launch a local Flow Memory multi-agent network")
    parser.add_argument("--scenario", default="all", choices=SCENARIOS)
    parser.add_argument("--json-out", type=Path, default=None)
    parser.add_argument("--emit-visual-events", action="store_true", help="Include Mission Control visual events/state in the launch report")
    parser.add_argument("--visual-out", type=Path, default=None, help="Optional path for visual events/state only")
    args = parser.parse_args()
    payload = launch_local_agent_network(args.scenario, emit_visual_events=args.emit_visual_events)
    if args.visual_out:
        args.visual_out.parent.mkdir(parents=True, exist_ok=True)
        args.visual_out.write_text(json.dumps({
            "ok": payload["ok"],
            "scenario": payload["scenario"],
            "events": payload["report"].get("visual_events", ()),
            "state": payload["report"].get("visual_state", {}),
            "provenance": "live",
        }, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    write_payload(payload, args.json_out)
    print(json.dumps(payload, indent=2, sort_keys=True, default=str))
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
