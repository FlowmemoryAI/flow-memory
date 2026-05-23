"""Verify an offline Flow Memory release evidence bundle."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from flow_memory.release import verify_release_evidence


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify Flow Memory release evidence bundle")
    parser.add_argument("--out", type=Path, default=Path("release_evidence/bundle"), help="Evidence bundle directory")
    args = parser.parse_args()
    bundle = verify_release_evidence(args.out)
    print(json.dumps({"ok": True, **bundle.as_record()}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
