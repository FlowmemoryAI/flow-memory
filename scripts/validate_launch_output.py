"""Validate JSON emitted by Flow Memory launch scripts."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping

KNOWN_MODES = {"cli", "flowlang", "neural", "local_agent_network"}


def validate_launch_output(path: str | Path) -> dict[str, object]:
    launch_path = Path(path)
    if not launch_path.exists():
        return {"ok": False, "blockers": ("launch_output_missing",), "path": str(launch_path)}
    try:
        payload = json.loads(launch_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"ok": False, "blockers": ("launch_output_invalid_json",), "path": str(launch_path)}
    if not isinstance(payload, Mapping):
        return {"ok": False, "blockers": ("launch_output_not_object",), "path": str(launch_path)}
    blockers: list[str] = []
    mode = str(payload.get("launch_mode", ""))
    if payload.get("ok") is not True:
        blockers.append("launch_output_not_ok")
    if mode not in KNOWN_MODES:
        blockers.append("launch_mode_unknown")
    if mode != "local_agent_network" and "safety_authority" not in payload:
        blockers.append("safety_authority_missing")
    if mode == "neural" and "neural" not in payload:
        blockers.append("neural_metadata_missing")
    if mode == "local_agent_network" and "report" not in payload:
        blockers.append("network_report_missing")
    return {"ok": not blockers, "blockers": tuple(dict.fromkeys(blockers)), "path": str(launch_path), "launch_mode": mode}


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate Flow Memory launch JSON output")
    parser.add_argument("path", type=Path)
    args = parser.parse_args()
    result = validate_launch_output(args.path)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
