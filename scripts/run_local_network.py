"""Run local Flow Memory network scenarios."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from flow_memory.network import LocalNetworkOrchestrator


def run_local_network(scenario: str = "all") -> dict[str, object]:
    return dict(LocalNetworkOrchestrator().run(scenario).as_record())


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Flow Memory local network scenarios")
    parser.add_argument("--scenario", default="all", choices=("basic-economy", "neural-agent", "rl-training", "dispute-slashing", "all"))
    parser.add_argument("--json-out", type=Path, default=None)
    args = parser.parse_args()
    record = run_local_network(args.scenario)
    text = json.dumps(record, indent=2, sort_keys=True, default=str)
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0 if record.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
