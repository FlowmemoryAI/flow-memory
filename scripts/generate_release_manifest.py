"""Generate an offline Flow Memory release manifest."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import sys
ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from flow_memory.crypto.keys import generate_local_keypair
from flow_memory.release import build_release_manifest


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate Flow Memory release manifest JSON")
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="Repository root")
    parser.add_argument("--out", type=Path, help="Write manifest JSON to this path")
    parser.add_argument("--sign-local", action="store_true", help="Sign with an ephemeral local development HMAC key")
    args = parser.parse_args()

    key = generate_local_keypair("release-manifest-local-dev") if args.sign_local else None
    manifest = build_release_manifest(args.root, signing_key=key)
    payload = dict(manifest.as_record())
    if key is not None:
        payload["signature_key"] = key.as_public_record()
        payload["signature_warning"] = "local development HMAC key is ephemeral; use production signing before relying on release signatures"
    text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8", newline="\n")
    else:
        print(text, end="")
    return 0 if payload["release_gates"]["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
