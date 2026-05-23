"""Run the deterministic offline adversarial economy simulation demo."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from flow_memory.simulation.reports import metrics_report, write_metrics_json


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Flow Memory local adversarial economy simulation")
    parser.add_argument("--out", type=Path, help="Optional metrics JSON output path")
    args = parser.parse_args()

    if args.out is not None:
        write_metrics_json(args.out)
        payload = json.loads(args.out.read_text(encoding="utf-8"))
    else:
        payload = metrics_report()
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
