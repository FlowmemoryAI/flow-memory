"""Release evidence for the local Flow Memory Compute Market."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from flow_memory.api.manifest import API_ENDPOINTS
from flow_memory.compute_market.planner import compute_marketplace_plan, deterministic_route_decision, task_profile_from_mapping
from flow_memory.compute_market.registry import default_routes

REQUIRED_COMPUTE_ENDPOINTS = (
    "POST /compute/plan",
    "POST /compute/marketplace-plan",
    "POST /compute/quote",
    "POST /compute/route",
    "POST /compute/payment-plan",
    "POST /compute/simulate-settlement",
    "GET /compute/providers",
    "GET /compute/routes",
    "GET /compute/policies",
    "GET /compute/economic-memory",
    "POST /compute/economic-memory/query",
)


def compute_market_evidence(root: str | Path = ".") -> Mapping[str, Any]:
    root_path = Path(root).resolve()
    operations = {f"{endpoint.method} {endpoint.path}" for endpoint in API_ENDPOINTS}
    sample = compute_marketplace_plan(
        {
            "task": {"task_id": "release-evidence-compute", "goal_id": "release-evidence", "expected_input_tokens": 1000, "expected_output_tokens": 500},
            "policy": {"max_total_cost": 0.01, "max_quote": 0.01, "dry_run_required": True, "strategy": "cheapest_eligible"},
        }
    )
    denied = deterministic_route_decision(
        task_profile_from_mapping({"task_id": "over-budget", "expected_input_tokens": 10_000_000, "expected_output_tokens": 10_000_000}),
        None,
        default_routes(),
    )
    files = {
        "domain": root_path / "src" / "flow_memory" / "compute_market" / "models.py",
        "api": root_path / "src" / "flow_memory" / "api" / "compute_endpoints.py",
        "agent_binding": root_path / "src" / "flow_memory" / "agents" / "compute_binding.py",
        "docs": root_path / "docs" / "COMPUTE_MARKET.md",
        "skill": root_path / "skills" / "compute-market" / "SKILL.md",
    }
    tests = tuple(sorted(path.name for path in (root_path / "tests").glob("test_compute*.py"))) if (root_path / "tests").exists() else ()
    missing_endpoints = tuple(endpoint for endpoint in REQUIRED_COMPUTE_ENDPOINTS if endpoint not in operations)
    return {
        "ok": not missing_endpoints and all(path.exists() for path in files.values()) and sample.get("ok") is True and denied.ok is False,
        "api_endpoints_present": not missing_endpoints,
        "missing_endpoints": missing_endpoints,
        "cli_commands_present": _cli_has_compute(root_path),
        "domain_files_present": {name: path.exists() for name, path in files.items()},
        "dry_run_only_settlement_invariant": bool(sample.get("dry_run_only")) and bool(sample.get("settlement_simulation", {}).get("no_live_settlement")),
        "no_private_keys_funds_broadcast_invariant": bool(sample.get("no_private_keys")) and bool(sample.get("no_funds_moved")) and bool(sample.get("no_broadcast")),
        "policy_fail_closed_sample": denied.as_record(),
        "policy_fail_closed_tests_present": "test_compute_market_agent_integration.py" in tests or "test_compute_market_core.py" in tests,
        "deterministic_simulation_tests_present": "test_compute_market_core.py" in tests,
        "flowlang_agent_integration_tests_present": "test_compute_market_flowlang.py" in tests,
        "visual_telemetry_tests_present": "test_compute_market_visual.py" in tests,
        "naming_cleanup_tests_present": "test_compute_market_naming_cleanup.py" in tests,
        "sample_plan": sample,
    }


def _cli_has_compute(root: Path) -> bool:
    cli = root / "src" / "flow_memory" / "cli.py"
    if not cli.exists():
        return False
    text = cli.read_text(encoding="utf-8")
    return "flow-memory compute" in text and "compute_marketplace_plan" in text
