"""Release evidence for Mission Control Live 3D Mode."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from flow_memory.visualization.embodiment import neural_embodiment_state


FIXTURE_PATH = "dashboard/src/mock-data/live-neural-embodiment.json"
LIVE_3D_COMPONENT = "dashboard/src/components/mission-control/Live3DModePanel.tsx"
MISSION_CONTROL_PAGE = "dashboard/src/app/mission-control/page.tsx"
MISSION_CONTROL_STYLES = "dashboard/src/styles/mission-control.css"
REQUIRED_DOCS = (
    "docs/MISSION_CONTROL_QUICKSTART.md",
    "docs/PUBLIC_ALPHA_READINESS.md",
    "docs/NEURAL_LIVE_AGENTS.md",
    "README.md",
)


def mission_control_live_3d_evidence(root: str | Path = ".") -> Mapping[str, Any]:
    """Return evidence that Mission Control exposes only safe read-only Live 3D telemetry."""

    root_path = Path(root).resolve()
    fixture = _read_json(root_path / FIXTURE_PATH)
    projected = neural_embodiment_state(root_path, "live-agent-supervisor")
    embodiment = dict(fixture.get("embodiment", {})) if isinstance(fixture.get("embodiment", {}), Mapping) else {}
    graph = dict(fixture.get("graph", {})) if isinstance(fixture.get("graph", {}), Mapping) else {}
    visual = dict(embodiment.get("visual", {})) if isinstance(embodiment.get("visual", {}), Mapping) else {}
    component = _read_text(root_path / LIVE_3D_COMPONENT)
    page = _read_text(root_path / MISSION_CONTROL_PAGE)
    styles = _read_text(root_path / MISSION_CONTROL_STYLES)
    docs = {relative: (root_path / relative).exists() for relative in REQUIRED_DOCS}
    docs_scan = _scan_docs(root_path)
    component_scan = _scan_text(component)
    fixture_scan = _scan_payload(fixture)
    data_ready = (
        fixture.get("ok") is True
        and projected.get("ok") is True
        and visual.get("three_ready") is True
        and graph.get("policy_gated") is True
        and embodiment.get("neural_advisory_only") is True
        and embodiment.get("policy_authority") == "policy_engine_and_approval_gate"
        and embodiment.get("local_only") is True
        and embodiment.get("no_live_provider_calls") is True
        and embodiment.get("no_funds_moved") is True
        and embodiment.get("no_live_settlement") is True
    )
    dashboard_ready = (
        "Live3DModePanel" in page
        and "Mission Control Live 3D Mode" in component
        and "data-live-3d-mode" in component
        and "no_live_provider_calls" in component
        and "live-3d-mode-panel" in styles
        and "preserve-3d" in styles
    )
    docs_ready = all(docs.values()) and docs_scan.get("ok") is True
    ok = data_ready and dashboard_ready and docs_ready and component_scan.get("ok") is True and fixture_scan.get("ok") is True
    return {
        "ok": ok,
        "mission_control_live_3d_mode_available": dashboard_ready,
        "mission_control_live_3d_data_ready": data_ready,
        "mission_control_live_3d_docs_ready": docs_ready,
        "mission_control_live_3d_no_overclaim_invariant": component_scan.get("ok") is True and fixture_scan.get("ok") is True and docs_scan.get("ok") is True,
        "component": LIVE_3D_COMPONENT,
        "page": MISSION_CONTROL_PAGE,
        "styles": MISSION_CONTROL_STYLES,
        "fixture_path": FIXTURE_PATH,
        "docs": docs,
        "docs_safety_scan": docs_scan,
        "component_safety_scan": component_scan,
        "fixture_safety_scan": fixture_scan,
        "sample": {
            "run_id": embodiment.get("run_id", ""),
            "agent_id": embodiment.get("agent_id", ""),
            "session_id": embodiment.get("session_id", ""),
            "phase": embodiment.get("current_loop_phase", ""),
            "gpu_evidence_status": embodiment.get("gpu_evidence_status", ""),
            "three_ready": visual.get("three_ready") is True,
            "policy_gated": graph.get("policy_gated") is True,
            "neural_advisory_only": embodiment.get("neural_advisory_only") is True,
            "local_only": embodiment.get("local_only") is True,
        },
    }


def _scan_payload(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    return _scan_text(json.dumps(payload, sort_keys=True, default=str))


def _scan_docs(root: Path) -> Mapping[str, Any]:
    missing_terms: list[str] = []
    hits: list[str] = []
    for relative in REQUIRED_DOCS:
        path = root / relative
        if not path.exists():
            missing_terms.append(f"{relative}:missing")
            continue
        text = path.read_text(encoding="utf-8", errors="ignore").lower()
        if "live 3d mode" not in text and "live 3d" not in text:
            missing_terms.append(f"{relative}:live 3d mode")
        for phrase in _unsafe_phrases():
            if phrase in text:
                hits.append(f"{relative}:{phrase}")
    return {"ok": not missing_terms and not hits, "missing": tuple(missing_terms), "hits": tuple(hits)}


def _scan_text(text: str) -> Mapping[str, Any]:
    lowered = text.lower()
    required = (
        "policy",
        "approval",
        "advisory",
        "no_live_provider_calls",
        "no_funds_moved",
        "no_live_settlement",
    )
    missing = tuple(item for item in required if item not in lowered)
    hits = tuple(item for item in _unsafe_phrases() if item in lowered)
    return {"ok": not missing and not hits, "missing": missing, "hits": hits}


def _unsafe_phrases() -> tuple[str, ...]:
    return (
        "production agi",
        "conscious agent",
        "unguarded autonomy",
        "live settlement enabled",
        "live provider calls enabled",
        "mainnet ready",
    )


def _read_json(path: Path) -> Mapping[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return dict(payload) if isinstance(payload, Mapping) else {}


def _read_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="ignore")
