"""Export Mission Control replay JSON from a local network report."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
import sys
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from flow_memory.visualization import reduce_visual_events
from flow_memory.visualization.events import VISUAL_SCHEMA_VERSION

_DYNAMIC_ID = re.compile(r"(visual_event|taskv3|bidv3|work|receipt|network_receipt|agent)_[A-Za-z0-9]+")


def export_visual_replay(input_path: str | Path, output_path: str | Path) -> Mapping[str, Any]:
    source = Path(input_path)
    if not source.exists():
        raise FileNotFoundError(f"network report not found: {source}")
    report = json.loads(source.read_text(encoding="utf-8"))
    raw_events = tuple(dict(event) for event in report.get("visual_events", ()) if isinstance(event, Mapping))
    if not raw_events:
        raise ValueError("network report does not contain visual_events; rerun with --emit-visual-events")
    replacements: dict[str, str] = {}
    events = tuple(_stable_value(event, replacements) for event in raw_events)
    state = reduce_visual_events(events, provenance="replay").as_record()
    replay = {
        "ok": True,
        "schema_version": VISUAL_SCHEMA_VERSION,
        "generated_at": "1970-01-01T00:00:00+00:00",
        "source_report": str(source).replace("\\", "/"),
        "provenance": "replay",
        "events": events,
        "state": state,
        "metadata": {
            "scenario_count": len(report.get("scenarios", ())),
            "event_count": len(events),
            "agent_count": len(state.get("agents", ())),
            "task_count": len(state.get("tasks", ())),
        },
    }
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(replay, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    return replay


def _stable_value(value: Any, replacements: dict[str, str]) -> Any:
    if isinstance(value, Mapping):
        normalized: dict[str, Any] = {}
        for key, item in value.items():
            if key == "created_at":
                normalized[str(key)] = "1970-01-01T00:00:00+00:00"
            else:
                normalized[str(key)] = _stable_value(item, replacements)
        return normalized
    if isinstance(value, list):
        return [_stable_value(item, replacements) for item in value]
    if isinstance(value, tuple):
        return tuple(_stable_value(item, replacements) for item in value)
    if isinstance(value, str):
        return _stable_string(value, replacements)
    return value


def _stable_string(value: str, replacements: dict[str, str]) -> str:
    def replace(match: re.Match[str]) -> str:
        token = match.group(0)
        prefix = match.group(1)
        if token not in replacements:
            count = 1 + sum(1 for existing in replacements.values() if existing.startswith(prefix + "_"))
            replacements[token] = f"{prefix}_{count:04d}"
        return replacements[token]
    return _DYNAMIC_ID.sub(replace, value)


def main() -> int:
    parser = argparse.ArgumentParser(description="Export Mission Control replay JSON")
    parser.add_argument("input", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    replay = export_visual_replay(args.input, args.out)
    print(json.dumps(replay, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
