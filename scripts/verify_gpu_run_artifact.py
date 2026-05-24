"""Verify imported neural GPU artifact metadata and hashes."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from flow_memory.neural.gpu_evidence import verify_gpu_run  # noqa: E402

DEFAULT_ROOT = Path("release_evidence/gpu_runs")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify neural GPU run evidence hashes")
    parser.add_argument("run", nargs="?", help="Run id or run directory. Omit to verify all runs.")
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    args = parser.parse_args(argv)
    if args.run:
        run_path = Path(args.run)
        directory = run_path if run_path.exists() else args.root / args.run
        result = verify_gpu_run(directory)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0 if result["ok"] else 1
    results = []
    if args.root.exists():
        for summary_path in sorted(args.root.glob("*/summary.json")):
            results.append(verify_gpu_run(summary_path.parent))
    ok = all(bool(result.get("ok")) for result in results)
    payload = {"ok": ok, "run_count": len(results), "results": tuple(results)}
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
