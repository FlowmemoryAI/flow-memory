"""Summarize imported Flow Memory GPU runs."""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
SRC=ROOT/"src"
if str(SRC) not in sys.path: sys.path.insert(0,str(SRC))
from flow_memory.neural.artifacts import load_json_if_present
from flow_memory.neural.gpu_evidence import verify_gpu_run

def main(argv: list[str] | None = None) -> int:
    p=argparse.ArgumentParser(description="Summarize imported GPU run evidence")
    p.add_argument("path", type=Path, default=ROOT/"release_evidence"/"gpu_runs", nargs="?")
    args=p.parse_args(argv)
    path = args.path
    if not path.exists() and not path.is_absolute():
        candidate = ROOT / "release_evidence" / "gpu_runs" / path
        if candidate.exists():
            path = candidate
    if (path/"summary.json").exists():
        print(json.dumps(load_json_if_present(path/"summary.json"), indent=2, sort_keys=True))
    else:
        print(json.dumps(verify_gpu_run(path), indent=2, sort_keys=True))
    return 0
if __name__=="__main__": raise SystemExit(main())
