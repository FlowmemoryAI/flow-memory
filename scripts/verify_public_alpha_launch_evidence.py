"""Verify public-alpha launch evidence."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from flow_memory.release.launch_evidence import verify_launch_evidence


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify public-alpha launch evidence")
    parser.add_argument("path", type=Path, nargs="?", default=Path("release_evidence/public_alpha_launch.json"))
    args = parser.parse_args()
    decision = verify_launch_evidence(args.path)
    print(json.dumps(decision.as_record(), indent=2, sort_keys=True, default=str))
    return 0 if decision.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
