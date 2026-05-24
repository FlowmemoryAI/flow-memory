"""Summarize imported Flow Memory GPU runs."""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
SRC=ROOT/"src"
if str(SRC) not in sys.path: sys.path.insert(0,str(SRC))
from flow_memory.neural.gpu_evidence import summarize_gpu_run, verify_gpu_run

def main(argv=None)->int:
    p=argparse.ArgumentParser(description="Summarize imported GPU run evidence")
    p.add_argument("path", type=Path, default=ROOT/"release_evidence"/"gpu_runs", nargs="?")
    args=p.parse_args(argv)
    if (args.path/"summary.json").exists():
        print(json.dumps(summarize_gpu_run(args.path).as_record(), indent=2, sort_keys=True))
    else:
        print(json.dumps(verify_gpu_run(args.path), indent=2, sort_keys=True))
    return 0
if __name__=="__main__": raise SystemExit(main())
