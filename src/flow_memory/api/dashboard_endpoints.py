"""Dashboard snapshot endpoint handlers for the local API router."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[3]
MOCK_DATA_NAMES = (
    "runtime.json",
    "neural-status.json",
    "rl-benchmarks.json",
    "agent-launch.json",
    "local-network.json",
    "payments.json",
)


def dashboard_snapshot(root: str | Path = ROOT) -> Mapping[str, Any]:
    root_path = Path(root)
    mock_dir = root_path / "dashboard" / "src" / "mock-data"
    records: dict[str, Any] = {}
    missing: list[str] = []
    for name in MOCK_DATA_NAMES:
        path = mock_dir / name
        key = name.removesuffix(".json").replace("-", "_")
        if not path.exists():
            missing.append(name)
            continue
        records[key] = json.loads(path.read_text(encoding="utf-8"))
    return {
        "ok": not missing,
        "source": "dashboard_mock_data",
        "mock_data_only": True,
        "missing": tuple(missing),
        "records": records,
        "raw_artifacts_exposed": False,
    }
