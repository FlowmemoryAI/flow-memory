"""Compare two imported neural GPU run summaries."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from flow_memory.neural.gpu_evidence import compare_gpu_runs  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Compare imported neural GPU run evidence")
    parser.add_argument("left", type=Path)
    parser.add_argument("right", type=Path)
    args = parser.parse_args(argv)
    result = compare_gpu_runs(args.left, args.right)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
