"""Validate a Flow Memory local network scenario report."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping

REQUIRED_SCENARIOS = ("basic-economy", "neural-agent", "rl-training", "dispute-slashing")


def validate_local_network_report(path: str | Path) -> dict[str, object]:
    report_path = Path(path)
    if not report_path.exists():
        return {"ok": False, "blockers": ("report_missing",), "path": str(report_path)}
    try:
        payload = json.loads(report_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"ok": False, "blockers": ("report_invalid_json",), "path": str(report_path)}
    if not isinstance(payload, Mapping):
        return {"ok": False, "blockers": ("report_not_object",), "path": str(report_path)}
    blockers: list[str] = []
    scenarios = tuple(payload.get("scenarios", ()))
    scenario_names = tuple(str(item.get("scenario", "")) for item in scenarios if isinstance(item, Mapping))
    if payload.get("ok") is not True:
        blockers.append("network_report_not_ok")
    missing = tuple(name for name in REQUIRED_SCENARIOS if name not in scenario_names)
    if missing:
        blockers.append("network_scenarios_missing")
    failed = tuple(str(item.get("scenario", "")) for item in scenarios if isinstance(item, Mapping) and item.get("ok") is not True)
    if failed:
        blockers.append("network_scenarios_failed")
    topology = payload.get("topology", {}) if isinstance(payload.get("topology", {}), Mapping) else {}
    participants = tuple(topology.get("participants", ()))
    if len(participants) < 3:
        blockers.append("network_participants_missing")
    return {
        "ok": not blockers,
        "blockers": tuple(dict.fromkeys(blockers)),
        "path": str(report_path),
        "scenario_count": len(scenarios),
        "scenarios": scenario_names,
        "failed_scenarios": failed,
        "participant_count": len(participants),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate Flow Memory local network report")
    parser.add_argument("path", nargs="?", default="artifacts/network/local_network_report.json")
    args = parser.parse_args()
    result = validate_local_network_report(args.path)
    print(json.dumps(result, indent=2, sort_keys=True, default=str))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
