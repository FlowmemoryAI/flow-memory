"""Release evidence for Mission Control run console and public-alpha demo bundle."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any, Mapping

from flow_memory.api.manifest import API_ENDPOINTS
from flow_memory.visualization.run_console import build_public_alpha_demo_bundle, list_run_console_runs, run_console_fixtures

REQUIRED_CONSOLE_ENDPOINTS = (
    "GET /launch/console/runs",
    "GET /launch/console/runs/{run_id}",
    "GET /launch/console/fixtures",
    "POST /launch/bundles/public-alpha",
)

REQUIRED_FIXTURES = (
    "dashboard/src/mock-data/live-neural-agent-launch.json",
    "dashboard/src/mock-data/live-agent-operations.json",
    "dashboard/src/mock-data/live-agent-supervisor.json",
    "dashboard/src/mock-data/local-network-replay.json",
)

REQUIRED_DOCS = (
    "docs/LIVE_AGENT_LAUNCHPAD.md",
    "docs/NEURAL_LIVE_AGENTS.md",
    "docs/MISSION_CONTROL_QUICKSTART.md",
    "docs/PUBLIC_ALPHA_READINESS.md",
    "docs/START_HERE.md",
)


def mission_control_run_console_evidence(root: str | Path = ".") -> Mapping[str, Any]:
    root_path = Path(root).resolve()
    endpoints = {f"{endpoint.method} {endpoint.path}" for endpoint in API_ENDPOINTS}
    missing_endpoints = tuple(endpoint for endpoint in REQUIRED_CONSOLE_ENDPOINTS if endpoint not in endpoints)
    cli_text = _read_text(root_path / "src" / "flow_memory" / "cli.py")
    dashboard_page = _read_text(root_path / "dashboard" / "src" / "app" / "mission-control" / "page.tsx")
    dashboard_config = _read_text(root_path / "dashboard" / "src" / "lib" / "mission-control-config.ts")
    run_console_ts = _read_text(root_path / "dashboard" / "src" / "lib" / "run-console.ts")
    run_selector_component = _read_text(root_path / "dashboard" / "src" / "components" / "mission-control" / "RunSelector.tsx")
    docs = {relative: (root_path / relative).exists() for relative in REQUIRED_DOCS}
    fixtures = _fixtures_status(root_path)
    docs_safe = _docs_safe(root_path)
    console = list_run_console_runs(root_path)
    fixture_manifest = run_console_fixtures(root_path)
    with tempfile.TemporaryDirectory() as tmp:
        bundle_path = Path(tmp) / "public-alpha-local-demo.json"
        bundle = build_public_alpha_demo_bundle(root_path, bundle_path)
        bundle_loaded = json.loads(bundle_path.read_text(encoding="utf-8"))
    bundle_safe = _bundle_safe(bundle_loaded)
    selector_available = "RunSelector" in dashboard_page and "Mission Control Run Selector" in run_selector_component and "missionControlRunFixtures" in dashboard_config
    status_card_available = "run-status-card" in dashboard_page or "run-status-card" in run_selector_component
    replay_selector_valid = fixtures.get("ok") is True and fixture_manifest.get("ok") is True
    ok = (
        not missing_endpoints
        and _cli_has_bundle(cli_text)
        and _api_available(missing_endpoints)
        and selector_available
        and status_card_available
        and replay_selector_valid
        and bundle.get("ok") is True
        and bundle_loaded.get("gpu_evidence_status") in {"blocked_missing_artifact", "artifact_present_not_verified", "verified"}
        and bundle_safe.get("ok") is True
        and all(docs.values())
        and docs_safe.get("ok") is True
        and "eventCategoryCounts" in run_console_ts
        and console.get("ok") is True
    )
    return {
        "ok": ok,
        "mission_control_run_console_available": console.get("ok") is True,
        "mission_control_run_selector_available": selector_available,
        "mission_control_run_status_card_available": status_card_available,
        "mission_control_replay_fixture_selector_validated": replay_selector_valid,
        "mission_control_supervisor_fixture_validated": fixtures["files"].get("dashboard/src/mock-data/live-agent-supervisor.json", {}).get("ok") is True,
        "mission_control_operations_fixture_validated": fixtures["files"].get("dashboard/src/mock-data/live-agent-operations.json", {}).get("ok") is True,
        "mission_control_launch_fixture_validated": fixtures["files"].get("dashboard/src/mock-data/live-neural-agent-launch.json", {}).get("ok") is True,
        "mission_control_local_network_fixture_validated": fixtures["files"].get("dashboard/src/mock-data/local-network-replay.json", {}).get("ok") is True,
        "public_alpha_demo_bundle_cli_available": _cli_has_bundle(cli_text),
        "public_alpha_demo_bundle_api_available": _api_available(missing_endpoints),
        "public_alpha_demo_bundle_validated": bundle.get("ok") is True and bundle_safe.get("ok") is True,
        "public_alpha_demo_bundle_gpu_status_honest": bundle_loaded.get("gpu_evidence_status") in {"blocked_missing_artifact", "artifact_present_not_verified", "verified"},
        "public_alpha_demo_bundle_no_external_calls": dict(bundle_loaded.get("invariants", {})).get("no_external_model_calls") is True,
        "public_alpha_demo_bundle_no_live_provider_calls": dict(bundle_loaded.get("invariants", {})).get("no_live_provider_calls") is True,
        "public_alpha_demo_bundle_no_funds_moved": dict(bundle_loaded.get("invariants", {})).get("no_funds_moved") is True,
        "public_alpha_demo_bundle_docs_updated": all(docs.values()) and docs_safe.get("ok") is True,
        "missing_endpoints": missing_endpoints,
        "dashboard_fixtures": fixtures,
        "docs": docs,
        "docs_safety_scan": docs_safe,
        "bundle_safety_scan": bundle_safe,
        "sample_bundle": {
            "bundle_path": bundle.get("bundle_path", ""),
            "fixture_count": len(bundle.get("mission_control_fixtures", ())),
            "command_count": len(bundle.get("commands", ())),
            "gpu_evidence_status": bundle.get("gpu_evidence_status", ""),
        },
    }


def _cli_has_bundle(cli_text: str) -> bool:
    return "build_public_alpha_demo_bundle" in cli_text and "bundle_command" in cli_text and "public-alpha" in cli_text


def _api_available(missing_endpoints: tuple[str, ...]) -> bool:
    return not missing_endpoints


def _fixtures_status(root: Path) -> Mapping[str, Any]:
    records: dict[str, Mapping[str, Any]] = {}
    for relative in REQUIRED_FIXTURES:
        path = root / relative
        payload = _read_json(path)
        events = payload.get("events", payload.get("visual_events", ()))
        state = payload.get("state", {})
        records[relative] = {
            "ok": path.exists() and isinstance(payload, Mapping) and bool(events or state),
            "exists": path.exists(),
            "event_count": len(events) if isinstance(events, (list, tuple)) else 0,
            "has_state": isinstance(state, Mapping) and bool(state),
        }
    return {"ok": all(record["ok"] for record in records.values()), "files": records}


def _bundle_safe(bundle: Mapping[str, Any]) -> Mapping[str, Any]:
    text = json.dumps(bundle, sort_keys=True, default=str).lower()
    required = (
        "gpu_evidence_status",
        "neural_advisory_only",
        "policy_gated",
        "no_live_provider_calls",
        "no_funds_moved",
        "no_live_settlement",
    )
    unsafe = (
        "production agi",
        "unguarded autonomy",
        "gpu validated",
        "live settlement enabled",
        "live provider calls enabled",
        "mainnet ready",
        "vjepa 2 implemented",
        "videomae implemented",
    )
    missing = tuple(item for item in required if item not in text)
    hits = tuple(item for item in unsafe if item in text)
    return {"ok": not missing and not hits, "missing": missing, "hits": hits}


def _docs_safe(root: Path) -> Mapping[str, Any]:
    unsafe_phrases = (
        "production agi",
        "unguarded autonomy",
        "gpu validated",
        "live settlement enabled",
        "live provider calls enabled",
        "mainnet ready",
        "vjepa 2 implemented",
        "videomae implemented",
    )
    hits: list[str] = []
    for relative in REQUIRED_DOCS:
        path = root / relative
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8", errors="ignore").lower()
        for phrase in unsafe_phrases:
            if phrase in text:
                hits.append(f"{relative}:{phrase}")
    return {"ok": not hits, "hits": tuple(hits)}


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
