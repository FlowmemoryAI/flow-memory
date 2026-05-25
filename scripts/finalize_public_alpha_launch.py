"""Finalize public-alpha launch handoff evidence."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from flow_memory.release.launch_finalizer import finalize_public_alpha_launch  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Finalize public-alpha launch handoff evidence")
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--out", type=Path, default=Path("release_evidence/public_alpha_launch_finalizer.json"))
    args = parser.parse_args()
    finalizer = finalize_public_alpha_launch(args.root, args.out)
    print(
        json.dumps(
            {
                "ok": finalizer.get("ok") is True,
                "path": str(args.out),
                "hash": finalizer.get("hash"),
                "blockers": finalizer.get("blockers", ()),
            },
            indent=2,
            sort_keys=True,
            default=str,
        )
    )
    return 0 if finalizer.get("ok") is True else 1


if __name__ == "__main__":
    raise SystemExit(main())
