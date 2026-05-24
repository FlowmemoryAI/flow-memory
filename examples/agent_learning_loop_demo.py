from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from flow_memory.learning import run_default_learning_loop


if __name__ == "__main__":
    print(json.dumps(run_default_learning_loop(), indent=2, sort_keys=True, default=str))
