"""Compare imported Flow Memory GPU run evidence records."""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
SRC=ROOT/"src"
if str(SRC) not in sys.path: sys.path.insert(0,str(SRC))
from flow_memory.neural.gpu_evidence import compare_gpu_runs

def main(argv=None)->int:
    p=argparse.ArgumentParser(description="Compare GPU run evidence")
    p.add_argument("path", type=Path, default=ROOT/"release_evidence"/"gpu_runs", nargs="?")
    args=p.parse_args(argv)
    print(json.dumps(compare_gpu_runs(args.path), indent=2, sort_keys=True))
    return 0
if __name__=="__main__": raise SystemExit(main())
