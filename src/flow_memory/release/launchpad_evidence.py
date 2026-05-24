"""Release evidence for the Live Agent Launchpad."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from flow_memory.api.manifest import API_ENDPOINTS
from flow_memory.launchpad import LAUNCH_TEMPLATES, run_live_agent_launch


REQUIRED_LAUNCH_ENDPOINTS = (
    "POST /launch/agent",
    "POST /launch/agent/from-flow",
)

REQUIRED_FLOW_EXAMPLES = (
    "examples/live_research_agent.flow",
    "examples/memory_scout_agent.flow",
    "examples/market_observer_agent.flow",
    "examples/mission_control_demo_agent.flow",
)

REQUIRED_DOCS = (
    "docs/LIVE_AGENT_LAUNCHPAD.md",
    "docs/NEURAL_LIVE_AGENTS.md",
    "docs/LAUNCH_NEURAL_AGENTS.md",
    "docs/MISSION_CONTROL_QUICKSTART.md",
)


def live_agent_launchpad_evidence(root: str | Path = ".") -> Mapping[str, Any]:
    root_path = Path(root).resolve()
    operations = {f"{endpoint.method} {endpoint.path}" for endpoint in API_ENDPOINTS}
    missing_endpoints = tuple(endpoint for endpoint in REQUIRED_LAUNCH_ENDPOINTS if endpoint not in operations)
    launch = run_live_agent_launch(template="live-research", backend="tiny_torch", ticks=2, emit_visual=True, root=root_path, write_artifact=False, write_checkpoint=False)
    summary = dict(launch.get("summary", {}))
    state = dict(launch.get("state", {}))
    docs = {relative: (root_path / relative).exists() for relative in REQUIRED_DOCS}
    flow_examples = {relative: (root_path / relative).exists() for relative in REQUIRED_FLOW_EXAMPLES}
    cli_path = root_path / "src" / "flow_memory" / "cli.py"
    cli_text = cli_path.read_text(encoding="utf-8") if cli_path.exists() else ""
    docs_safe = _docs_safe(root_path)
    ok = (
        not missing_endpoints
        and bool(LAUNCH_TEMPLATES)
        and summary.get("loop_ticks_completed") == 2
        and summary.get("perceptions_encoded") == 2
        and summary.get("plans_scored") == 2
        and summary.get("risks_scored") == 2
        and summary.get("memory_records_written", 0) >= 4
        and summary.get("visual_events_emitted", 0) >= 8
        and summary.get("no_external_calls") is True
        and summary.get("no_funds_moved") is True
        and summary.get("safety_authority") == "policy_engine_and_approval_gate"
        and bool(dict(state).get("neural"))
        and all(docs.values())
        and all(flow_examples.values())
        and _cli_has_launchpad(cli_text)
        and docs_safe["ok"] is True
    )
    return {
        "ok": ok,
        "launchpad_cli_available": _cli_has_launchpad(cli_text),
        "launchpad_api_available": not missing_endpoints,
        "missing_endpoints": missing_endpoints,
        "launch_templates_available": tuple(sorted(LAUNCH_TEMPLATES)),
        "flowlang_launch_examples_available": flow_examples,
        "live_agent_launch_tiny_torch_validated": summary.get("loop_ticks_completed") == 2,
        "launch_visual_replay_validated": bool(dict(state).get("neural")),
        "launch_memory_records_validated": summary.get("memory_records_written", 0) >= 4,
        "launch_policy_gate_validated": summary.get("safety_authority") == "policy_engine_and_approval_gate",
        "launch_no_external_calls_invariant": summary.get("no_external_calls") is True,
        "launch_no_live_provider_calls_invariant": summary.get("no_live_provider_calls") is True,
        "launch_no_private_keys_invariant": summary.get("no_private_keys") is True,
        "launch_no_funds_moved_invariant": summary.get("no_funds_moved") is True,
        "launch_gpu_status_honest": summary.get("gpu_evidence_status") in {"blocked_missing_artifact", "artifact_present_not_verified", "verified"},
        "launch_public_alpha_docs_updated": docs,
        "docs_safety_scan": docs_safe,
        "sample_summary": summary,
    }

def _cli_has_launchpad(cli_text: str) -> bool:
    return "def _launch" in cli_text and 'add_parser("agent"' in cli_text and '"launch"' in cli_text


def _docs_safe(root: Path) -> Mapping[str, Any]:
    unsafe_phrases = (
        "production agi",
        "conscious",
        "mainnet-ready",
        "audited contracts",
        "live settlement",
        "vjepa 2 implemented",
        "videomae implemented",
    )
    scanned = tuple(path for path in (root / "docs").glob("*.md") if path.name in {Path(item).name for item in REQUIRED_DOCS})
    hits: list[str] = []
    for path in scanned:
        text = path.read_text(encoding="utf-8", errors="ignore").lower()
        for phrase in unsafe_phrases:
            if phrase in text:
                hits.append(f"{path.name}:{phrase}")
    return {"ok": not hits, "hits": tuple(hits), "scanned": tuple(path.name for path in scanned)}
