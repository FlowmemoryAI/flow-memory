from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from flow_memory.learning.rl_learning import run_safety_gate_learning


if __name__ == "__main__":
    report = run_safety_gate_learning(episodes=20).as_record()
    print(json.dumps({"ok": report["improved"], "rl_learning": report, "advisory_only": True, "safety_authority": "policy_engine_and_approval_gate"}, indent=2, sort_keys=True, default=str))
