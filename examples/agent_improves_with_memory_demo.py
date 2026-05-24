from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from flow_memory.agents import AgentProfile, AgentRunner
from flow_memory.learning.memory_learning import MemoryLearningStore
from flow_memory.learning.trace_collector import TraceCollector


def run_demo() -> dict[str, object]:
    profile = AgentProfile(name="Memory Learning Demo", identity="did:flow:memory-learning", allowed_tools=("observe_environment", "respond"), autonomy_mode="autonomous_local")
    collector = TraceCollector()
    store = MemoryLearningStore()
    first = AgentRunner(profile).run_cycle("Investigate safety incident")
    trace = collector.collect(agent_id=profile.agent_id, goal="Investigate safety incident", result_record=first.as_record(), rl_reward=1.0)
    store.add_trace(trace)
    retrieved = store.retrieve("safety incident")
    return {"ok": bool(retrieved), "before_memory_count": 0, "after_memory_count": len(store.traces), "retrieved": retrieved}


if __name__ == "__main__":
    print(json.dumps(run_demo(), indent=2, sort_keys=True, default=str))
