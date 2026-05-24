"""Generate a small Mission Control visual replay from real local network scenarios."""
from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from flow_memory.network import LocalNetworkOrchestrator
from flow_memory.visualization import reduce_visual_events


def run_demo() -> dict[str, object]:
    report = LocalNetworkOrchestrator().run("all", emit_visual_events=True).as_record()
    state = reduce_visual_events(report["visual_events"], provenance="replay").as_record()
    return {
        "ok": bool(report["ok"]),
        "event_count": len(report["visual_events"]),
        "agent_count": len(state["agents"]),
        "task_count": len(state["tasks"]),
        "neural_signal_count": len(state["neural"]),
        "rl_episode_count": len(state["rl"]),
        "safety_gate_count": len(state["safety"]),
        "provenance": state["provenance"],
    }


if __name__ == "__main__":
    print(json.dumps(run_demo(), indent=2, sort_keys=True))
