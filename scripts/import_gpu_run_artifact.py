"""Import a cloud GPU run artifact into release evidence."""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
SRC=ROOT/"src"
if str(SRC) not in sys.path: sys.path.insert(0,str(SRC))
from flow_memory.neural.gpu_evidence import DEFAULT_RUN_ID, import_gpu_run_artifact

def main(argv: list[str] | None = None) -> int:
    p=argparse.ArgumentParser(description="Import Flow Memory GPU run artifact")
    p.add_argument("artifact", nargs="?", type=Path, default=ROOT/"artifacts"/"incoming"/"flow-memory-cloud-gpu-run-001.tar.gz")
    p.add_argument("--out", type=Path, default=ROOT/"release_evidence"/"gpu_runs")
    p.add_argument("--run-id", default=DEFAULT_RUN_ID)
    args=p.parse_args(argv)
    summary=import_gpu_run_artifact(args.artifact, args.out, run_id=args.run_id)
    print(json.dumps(summary.as_record(), indent=2, sort_keys=True))
    return 0
if __name__=="__main__": raise SystemExit(main())
