"""Run the local Flow Memory agent learning loop."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from flow_memory.learning import run_default_learning_loop


def main() -> int:
    parser = argparse.ArgumentParser(description="Run local Flow Memory learning loop")
    parser.add_argument("--json-out", type=Path, default=None)
    args = parser.parse_args()
    record = dict(run_default_learning_loop())
    text = json.dumps(record, indent=2, sort_keys=True, default=str)
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0 if record.get("success_rate", 0.0) > 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
