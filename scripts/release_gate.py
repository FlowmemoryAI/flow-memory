"""Run offline release-readiness gates for Flow Memory."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from flow_memory.release import run_release_gates


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Flow Memory release-readiness gates")
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="Repository root")
    args = parser.parse_args()

    report = run_release_gates(args.root)
    print(json.dumps(report.as_record(), indent=2, sort_keys=True))
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
