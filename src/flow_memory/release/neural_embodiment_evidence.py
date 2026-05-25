"""Release evidence for Mission Control neural embodiment visibility."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from flow_memory.api.manifest import API_ENDPOINTS
from flow_memory.visualization.embodiment import build_neural_embodiment_fixture, neural_embodiment_state

REQUIRED_ENDPOINTS = (
    "GET /visual/embodiment/{run_id}",
    "GET /launch/console/runs/{run_id}/embodiment",
)

REQUIRED_DOCS = (
    "docs/MISSION_CONTROL_QUICKSTART.md",
    "docs/NEURAL_LIVE_AGENTS.md",
    "docs/LIVE_AGENT_LAUNCHPAD.md",
    "docs/PUBLIC_ALPHA_READINESS.md",
    "README.md",
)

FIXTURE_PATH = "dashboard/src/mock-data/live-neural-embodiment.json"


def neural_embodiment_evidence(root: str | Path = ".") -> Mapping[str, Any]:
    root_path = Path(root).resolve()
    endpoints = {f"{endpoint.method} {endpoint.path}" for endpoint in API_ENDPOINTS}
    missing_endpoints = tuple(endpoint for endpoint in REQUIRED_ENDPOINTS if endpoint not in endpoints)
    fixture_path = root_path / FIXTURE_PATH
    fixture = _read_json(fixture_path)
    state = neural_embodiment_state(root_path, "live-agent-supervisor")
    cli_text = _read_text(root_path / "src" / "flow_memory" / "cli.py")
    page_text = _read_text(root_path / "dashboard" / "src" / "app" / "mission-control" / "page.tsx")
    panel_text = _read_text(root_path / "dashboard" / "src" / "components" / "mission-control" / "NeuralEmbodimentPanel.tsx")
    config_text = _read_text(root_path / "dashboard" / "src" / "lib" / "mission-control-config.ts")
    docs = {relative: (root_path / relative).exists() for relative in REQUIRED_DOCS}
    docs_scan = _scan_safe_docs(root_path)
    fixture_scan = _scan_payload(fixture)
    generated_ok = False
    try:
        generated = build_neural_embodiment_fixture(root_path, "live-agent-supervisor", fixture_path)
        generated_ok = generated.get("ok") is True and generated.get("embodiment", {}).get("gpu_evidence_status") == "verified"
    except Exception:
        generated_ok = False
    embodiment = dict(fixture.get("embodiment", {})) if isinstance(fixture.get("embodiment", {}), Mapping) else {}
    graph = dict(fixture.get("graph", {})) if isinstance(fixture.get("graph", {}), Mapping) else {}
    node_status = {
        str(node.get("id")): str(node.get("status"))
        for node in graph.get("nodes", ())
        if isinstance(node, Mapping)
    }
    dashboard_available = "NeuralEmbodimentPanel" in page_text and "Visible neural embodiment" in panel_text
    cli_available = "build_neural_embodiment_fixture" in cli_text and "embodiment" in cli_text
    api_available = not missing_endpoints
    fixture_valid = (
        fixture_path.exists()
        and fixture.get("ok") is True
        and embodiment.get("gpu_evidence_status") == "verified"
        and embodiment.get("neural_advisory_only") is True
        and embodiment.get("policy_authority") == "policy_engine_and_approval_gate"
        and graph.get("policy_gated") is True
        and node_status.get("gpu") == "verified"
    )
    ok = (
        state.get("ok") is True
        and fixture_valid
        and dashboard_available
        and cli_available
        and api_available
        and generated_ok
        and all(docs.values())
        and docs_scan.get("ok") is True
        and fixture_scan.get("ok") is True
        and "live-neural-embodiment" in config_text
    )
    return {
        "ok": ok,
        "neural_embodiment_contract_available": state.get("ok") is True,
        "neural_embodiment_dashboard_available": dashboard_available,
        "neural_embodiment_replay_fixture_available": fixture_valid,
        "neural_embodiment_gpu_status_visible": embodiment.get("gpu_evidence_status") == "verified" and node_status.get("gpu") == "verified",
        "neural_embodiment_policy_gate_visible": embodiment.get("policy_gate_state") in {"applied", "allowed", "pending_policy_gate"} and graph.get("policy_gated") is True,
        "neural_embodiment_memory_activation_visible": int(embodiment.get("memory_activation_count", 0) or 0) > 0,
        "neural_embodiment_learning_tick_visible": int(embodiment.get("learning_tick_count", 0) or 0) > 0,
        "neural_embodiment_cli_available": cli_available,
        "neural_embodiment_api_available": api_available,
        "neural_embodiment_no_overclaim_invariant": fixture_scan.get("ok") is True and docs_scan.get("ok") is True,
        "neural_embodiment_public_alpha_docs_updated": all(docs.values()) and docs_scan.get("ok") is True,
        "missing_endpoints": missing_endpoints,
        "fixture_path": FIXTURE_PATH,
        "fixture_valid": fixture_valid,
        "generated_fixture_valid": generated_ok,
        "dashboard_component": "dashboard/src/components/mission-control/NeuralEmbodimentPanel.tsx",
        "docs": docs,
        "docs_safety_scan": docs_scan,
        "fixture_safety_scan": fixture_scan,
        "sample": {
            "run_id": embodiment.get("run_id", ""),
            "agent_id": embodiment.get("agent_id", ""),
            "session_id": embodiment.get("session_id", ""),
            "phase": embodiment.get("current_loop_phase", ""),
            "gpu_evidence_status": embodiment.get("gpu_evidence_status", ""),
            "memory_activation_count": embodiment.get("memory_activation_count", 0),
            "learning_tick_count": embodiment.get("learning_tick_count", 0),
        },
    }


def _scan_payload(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    text = json.dumps(payload, sort_keys=True, default=str).lower()
    required = (
        "neural_advisory_only",
        "policy_engine_and_approval_gate",
        "gpu_evidence_status",
        "no_live_provider_calls",
        "no_funds_moved",
        "no_live_settlement",
    )
    unsafe = _unsafe_phrases()
    missing = tuple(item for item in required if item not in text)
    hits = tuple(item for item in unsafe if item in text)
    return {"ok": not missing and not hits, "missing": missing, "hits": hits}


def _scan_safe_docs(root: Path) -> Mapping[str, Any]:
    hits: list[str] = []
    for relative in REQUIRED_DOCS:
        path = root / relative
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8", errors="ignore").lower()
        for phrase in _unsafe_phrases():
            if phrase in text:
                hits.append(f"{relative}:{phrase}")
    return {"ok": not hits, "hits": tuple(hits)}


def _unsafe_phrases() -> tuple[str, ...]:
    return (
        "production agi",
        "conscious agent",
        "unguarded autonomy",
        "live settlement enabled",
        "live provider calls enabled",
        "mainnet ready",
        "vjepa 2 implemented",
        "videomae implemented",
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
