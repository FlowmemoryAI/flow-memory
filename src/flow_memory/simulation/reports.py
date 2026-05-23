"""JSON reports for deterministic offline simulation results."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from flow_memory.simulation.scenarios import run_adversarial_scenarios


def metrics_report() -> Mapping[str, Any]:
    """Return a JSON-serializable local prototype metrics report."""

    return run_adversarial_scenarios()


def write_metrics_json(path: str | Path) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(metrics_report(), indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    return output
