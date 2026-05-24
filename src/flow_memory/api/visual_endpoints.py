"""Visual telemetry endpoints for the dependency-free API router."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from flow_memory.network import LocalNetworkOrchestrator
from flow_memory.visualization.replay import load_visual_events
from flow_memory.visualization.schemas import visual_schema
from flow_memory.visualization.snapshots import build_visual_snapshot

ROOT = Path(__file__).resolve().parents[3]


def current_visual_state() -> Mapping[str, Any]:
    report = LocalNetworkOrchestrator().run("all", emit_visual_events=True).as_record()
    return {"ok": True, "state": report.get("visual_state", {}), "source": "local_network", "provenance": "live"}


def current_visual_events() -> Mapping[str, Any]:
    report = LocalNetworkOrchestrator().run("all", emit_visual_events=True).as_record()
    return {"ok": True, "events": tuple(report.get("visual_events", ())), "source": "local_network", "provenance": "live"}


def network_state() -> Mapping[str, Any]:
    report = LocalNetworkOrchestrator().run("all", emit_visual_events=True).as_record()
    return {"ok": bool(report.get("ok")), "network": report, "visual_state": report.get("visual_state", {})}


def visual_schema_endpoint() -> Mapping[str, Any]:
    return {"ok": True, "schema": visual_schema()}


def visual_replay(run_id: str) -> Mapping[str, Any]:
    safe = _safe_run_id(run_id)
    candidates = (
        ROOT / "artifacts" / "visual" / f"{safe}.json",
        ROOT / "dashboard" / "src" / "mock-data" / f"{safe}.json",
        ROOT / "artifacts" / "network" / f"{safe}.json",
    )
    for path in candidates:
        if path.exists():
            events = load_visual_events(path)
            snapshot = build_visual_snapshot(events, provenance="replay")
            return {"ok": True, "run_id": safe, "path": str(path.relative_to(ROOT)), **snapshot}
    raise KeyError(f"visual replay not found: {safe}")


def start_visual_replay(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    scenario = str(payload.get("scenario", "all"))
    report = LocalNetworkOrchestrator().run(scenario, emit_visual_events=True).as_record()
    run_id = _safe_run_id(str(payload.get("run_id", f"{scenario}-latest")))
    out = ROOT / "artifacts" / "visual" / f"{run_id}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    replay = {
        "ok": bool(report.get("ok")),
        "run_id": run_id,
        "scenario": scenario,
        "events": report.get("visual_events", ()),
        "state": report.get("visual_state", {}),
        "provenance": "replay",
    }
    out.write_text(json.dumps(replay, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    return {"ok": bool(report.get("ok")), "run_id": run_id, "path": str(out.relative_to(ROOT)), "state": report.get("visual_state", {})}


def _safe_run_id(value: str) -> str:
    cleaned = "".join(ch for ch in value if ch.isalnum() or ch in {"-", "_", "."}).strip(".")
    if not cleaned:
        raise ValueError("run_id is required")
    return cleaned
