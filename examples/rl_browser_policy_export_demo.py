from __future__ import annotations

from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


import json
from pathlib import Path
from flow_memory.rl.policies import TabularQPolicy
from flow_memory.rl.wasm_export import export_tabular_policy

if __name__ == "__main__":
    out = export_tabular_policy(TabularQPolicy(q={"demo": [0.0, 1.0]}), Path("artifacts/rl/browser_policy.json"))
    print(json.dumps({"ok": True, "policy": str(out)}, indent=2, sort_keys=True))
