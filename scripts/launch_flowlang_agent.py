"""Launch a FlowLang-defined Flow Memory agent."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from flow_memory.flowlang.runner import run_flowlang_agent


def launch_flowlang_agent(path: Path, goal: str, neural_backend: str | None = None) -> dict[str, object]:
    result = dict(run_flowlang_agent(path, goal, neural_backend=neural_backend))
    return {
        "ok": bool(result.get("accepted") or result.get("requires_approval")),
        "launch_mode": "flowlang",
        "flow_file": str(path),
        "goal": goal,
        "result": result,
        "safety_authority": "policy_engine_and_approval_gate",
    }


def write_payload(payload: dict[str, object], path: Path | None) -> None:
    if path is not None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Launch a FlowLang agent")
    parser.add_argument("flow_file", type=Path)
    parser.add_argument("--goal", default="Run the declared agent")
    parser.add_argument("--neural", default=None, help="Optional neural backend override")
    parser.add_argument("--json-out", type=Path, default=None)
    args = parser.parse_args()
    payload = launch_flowlang_agent(args.flow_file, args.goal, args.neural)
    write_payload(payload, args.json_out)
    print(json.dumps(payload, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
