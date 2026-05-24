"""Export public-alpha launch evidence."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from flow_memory.release.launch_evidence import export_launch_evidence


def main() -> int:
    parser = argparse.ArgumentParser(description="Export public-alpha launch evidence")
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--out", type=Path, default=Path("release_evidence/public_alpha_launch.json"))
    args = parser.parse_args()
    evidence = export_launch_evidence(args.root, args.out)
    print(json.dumps({"ok": True, "path": str(args.out), "hash": evidence.get("hash")}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
