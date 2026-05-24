"""Summarize imported neural GPU evidence runs."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from flow_memory.neural.gpu_evidence import summary_markdown  # noqa: E402
from flow_memory.neural.run_records import get_gpu_run, list_gpu_runs  # noqa: E402

DEFAULT_ROOT = Path("release_evidence/gpu_runs")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Summarize imported neural GPU run evidence")
    parser.add_argument("run", nargs="?", help="Run id or run directory. Omit to list runs.")
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    if not args.run:
        runs = list_gpu_runs(_repo_root_from_runs_root(args.root))
        print(json.dumps({"ok": True, "runs": runs}, indent=2, sort_keys=True))
        return 0
    run_path = Path(args.run)
    if run_path.exists():
        summary_path = run_path / "summary.json"
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
    else:
        summary = dict(get_gpu_run(_repo_root_from_runs_root(args.root), args.run))
    if args.json:
        print(json.dumps({"ok": True, "summary": summary}, indent=2, sort_keys=True))
    else:
        print(summary_markdown(summary))
    return 0


def _repo_root_from_runs_root(runs_root: Path) -> Path:
    parts = runs_root.parts
    if len(parts) >= 2 and parts[-2:] == ("release_evidence", "gpu_runs"):
        return Path(*parts[:-2]) if parts[:-2] else Path(".")
    return Path(".")


if __name__ == "__main__":
    raise SystemExit(main())
