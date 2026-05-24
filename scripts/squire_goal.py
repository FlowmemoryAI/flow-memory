"""Plan a Squire/UsePod/Level5 compute route for a Flow Memory goal."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from flow_memory.squire import build_squire_goal_plan, inspect_squire_environment


def run_squire_goal(goal: str) -> dict[str, object]:
    plan = build_squire_goal_plan(goal, environment=inspect_squire_environment())
    return {"ok": True, "skill": "squire-goal", "plan": plan.as_record()}


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a Squire compute treasury/routing plan")
    parser.add_argument("--goal", default="Use cheap agentic inference with explicit budget controls")
    parser.add_argument("--json-out", type=Path, default=None)
    args = parser.parse_args()
    payload = run_squire_goal(args.goal)
    text = json.dumps(payload, indent=2, sort_keys=True, default=str)
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
