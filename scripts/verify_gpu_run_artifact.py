"""Verify imported Flow Memory GPU run evidence."""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
SRC=ROOT/"src"
if str(SRC) not in sys.path: sys.path.insert(0,str(SRC))
from flow_memory.neural.gpu_evidence import verify_gpu_run

def main(argv=None)->int:
    p=argparse.ArgumentParser(description="Verify imported GPU run evidence")
    p.add_argument("path", type=Path, default=ROOT/"release_evidence"/"gpu_runs", nargs="?")
    args=p.parse_args(argv)
    result=verify_gpu_run(args.path)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result.get("ok") else 1
if __name__=="__main__": raise SystemExit(main())
