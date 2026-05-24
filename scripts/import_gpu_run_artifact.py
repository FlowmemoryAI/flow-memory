"""Import a cloud GPU run artifact into release-safe neural evidence."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from flow_memory.neural.gpu_evidence import import_gpu_run_artifact  # noqa: E402

DEFAULT_ARTIFACT = Path("artifacts/incoming/flow-memory-cloud-gpu-run-001.tar.gz")
DEFAULT_OUT = Path("release_evidence/gpu_runs")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Import Flow Memory GPU run artifact metadata")
    parser.add_argument("--artifact", type=Path, default=DEFAULT_ARTIFACT)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--run-id", default="")
    args = parser.parse_args(argv)
    summary = import_gpu_run_artifact(args.artifact, args.out, run_id=args.run_id or None)
    print(json.dumps({"ok": True, "summary": summary}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
