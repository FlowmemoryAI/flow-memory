"""Export and verify an offline Flow Memory release evidence bundle."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from flow_memory.release import export_release_evidence, verify_release_evidence


def main() -> int:
    parser = argparse.ArgumentParser(description="Export Flow Memory release evidence bundle")
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="Repository root")
    parser.add_argument("--out", type=Path, default=Path("release_evidence/bundle"), help="Output directory")
    parser.add_argument("--verify-only", action="store_true", help="Verify an existing bundle instead of exporting")
    args = parser.parse_args()

    bundle = verify_release_evidence(args.out) if args.verify_only else export_release_evidence(args.root, args.out)
    print(json.dumps({"ok": True, **bundle.as_record()}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
