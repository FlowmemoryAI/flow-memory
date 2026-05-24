"""Export the deterministic Flow Memory API snapshot."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import sys
ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from flow_memory.api.snapshot import api_snapshot


def main() -> int:
    parser = argparse.ArgumentParser(description="Export Flow Memory API snapshot JSON")
    parser.add_argument("--write", type=Path, help="Write snapshot to this path instead of stdout")
    args = parser.parse_args()

    text = json.dumps(api_snapshot(), indent=2, sort_keys=True) + "\n"
    if args.write:
        args.write.parent.mkdir(parents=True, exist_ok=True)
        args.write.write_text(text, encoding="utf-8", newline="\n")
    else:
        print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
