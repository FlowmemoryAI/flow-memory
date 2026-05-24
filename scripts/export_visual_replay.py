"""Export Mission Control replay JSON from a local network report."""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
import sys
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from flow_memory.visualization import reduce_visual_events
from flow_memory.visualization.events import VISUAL_SCHEMA_VERSION


def export_visual_replay(input_path: str | Path, output_path: str | Path) -> Mapping[str, Any]:
    source = Path(input_path)
    if not source.exists():
        raise FileNotFoundError(f"network report not found: {source}")
    report = json.loads(source.read_text(encoding="utf-8"))
    events = tuple(dict(event) for event in report.get("visual_events", ()) if isinstance(event, Mapping))
    if not events:
        raise ValueError("network report does not contain visual_events; rerun with --emit-visual-events")
    state = reduce_visual_events(events, provenance="replay").as_record()
    replay = {
        "ok": True,
        "schema_version": VISUAL_SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_report": str(source),
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
