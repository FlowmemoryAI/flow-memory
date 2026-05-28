"""Release evidence for Flow Memory Agent Builder browser agent builder."""
from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Mapping

from flow_memory.api.manifest import endpoint_manifest
from flow_memory.api.router import create_default_router
from flow_memory.api.scopes import AGENT_BUILDER_CREATE_SCOPE, AGENT_BUILDER_READ_SCOPE, AGENT_BUILDER_SIMULATE_SCOPE, required_scopes_for
from flow_memory.agent_builder import birth_agent_from_builder, create_agent_builder_assembly_plan, agent_builder_defaults, simulate_agent_builder_upgrades

_OVERCLAIMS = (
    "is agi",
    "achieves agi",
    "artificial general intelligence",
    "is conscious",
    "has consciousness",
    "subjective desire",
    "unbounded autonomy enabled",
    "wallet required for first agent",
    "api key required for first agent",
    "funds required for first agent",
    "transaction broadcast enabled",
    "mainnet writes enabled",
    "private key stored",
    "seed phrase stored",
)

_REQUIRED_ROUTES = {
    "GET /agent-builder/defaults",
    "POST /agent-builder/assembly-plan",
    "POST /agent-builder/birth",
    "POST /agent-builder/simulate-upgrades",
}


def agent_builder_evidence(root: str | Path = ".") -> Mapping[str, object]:
    root_path = Path(root).resolve()
    with TemporaryDirectory() as tmp:
        defaults = agent_builder_defaults()
        plan = create_agent_builder_assembly_plan({"name": "Mira", "purpose": "Help me build Flow Memory"}, root=tmp)
        birth = birth_agent_from_builder({"name": "Mira", "purpose": "Help me build Flow Memory"}, root=tmp)
        upgrades = simulate_agent_builder_upgrades(str(birth["agent_id"]), byok=True, wallet=True, onchain_dry_run=True, x402=True, root=tmp)
    manifest_routes = {f"{endpoint['method']} {endpoint['path']}" for endpoint in endpoint_manifest().get("endpoints", ())}
    registered_routes = {f"{route.method} {route.path}" for route in create_default_router().routes}
    docs_text = _docs_text(root_path)
    dashboard_server = root_path / "dashboard" / "scripts" / "dev-server.mjs"
    dashboard_fixture = root_path / "dashboard" / "src" / "mock-data" / "agent-builder.json"
    plan_record = dict(plan.get("plan", {}))
    evidence = {
        "agent_builder_available": _file_contains(root_path / "src" / "flow_memory" / "agent_builder" / "core.py", "AgentBuilderAssemblyPlan"),
        "agent_builder_browser_route_available": _file_contains(dashboard_server, "id=\"agent-builder\"") and _file_contains(dashboard_server, "url.pathname === '/agents/new'"),
        "agent_builder_first_agent_simple_mode_available": defaults.get("simple_mode_default") is True and plan_record.get("first_agent_mode") is True,
        "agent_builder_advanced_mode_available": any(card.get("optional") for card in defaults.get("capability_cards", ())),
        "no_wallet_first_agent_visible": defaults.get("first_agent_requires_wallet") is False and _file_contains(dashboard_server, "no wallet/API key/funds"),
        "no_api_key_first_agent_visible": defaults.get("first_agent_requires_api_key") is False,
        "no_funds_first_agent_visible": defaults.get("first_agent_requires_funds") is False,
        "private_default_visible": defaults.get("private_default") is True and _file_contains(dashboard_server, "Private by default"),
        "network_learning_opt_in_visible": defaults.get("network_learning_opt_in") is True and _file_contains(dashboard_server, "Network learning is opt-in"),
        "capability_composer_available": len(defaults.get("capability_cards", ())) >= 10 and _file_contains(dashboard_server, "Capability Composer"),
        "byok_optional_upgrade_visible": _card_optional(defaults, "byok_model_key") and _file_contains(dashboard_server, "BYOK model key"),
        "wallet_optional_upgrade_visible": _card_optional(defaults, "wallet_identity") and _file_contains(dashboard_server, "Wallet identity"),
        "onchain_dry_run_optional_upgrade_visible": _card_optional(defaults, "onchain_dry_run") and _file_contains(dashboard_server, "On-chain dry run"),
        "x402_dry_run_optional_upgrade_visible": _card_optional(defaults, "x402_dry_run_route") and _file_contains(dashboard_server, "x402 dry-run route"),
        "agent_internet_publish_optional_visible": _file_contains(dashboard_server, "Publish Agent Internet identity"),
        "skill_matcher_from_agent_builder_available": bool(upgrades.get("ok")) and _file_contains(dashboard_server, "Find collaborators"),
        "mission_control_handoff_available": str(birth.get("mission_control_url", "")).startswith("/mission-control#agent-builder"),
        "read_only_demo_mode_available": dashboard_fixture.exists() and _file_contains(dashboard_server, "read-only demo mode"),
        "cli_agent_builder_available": _file_contains(root_path / "src" / "flow_memory" / "cli.py", "def _agent_builder") and _file_contains(root_path / "src" / "flow_memory" / "cli.py", '"agent-builder"'),
        "api_agent_builder_available": _REQUIRED_ROUTES.issubset(manifest_routes) and _REQUIRED_ROUTES.issubset(registered_routes) and _scope_checks_ok(),
        "mermaid_agent_builder_docs_available": "```mermaid" in docs_text and "agent builder architecture" in docs_text,
        "no_private_key_invariant": upgrades.get("no_private_key_required") is True,
        "no_seed_phrase_invariant": upgrades.get("no_seed_phrase_required") is True,
        "no_funds_moved_invariant": upgrades.get("no_funds_moved") is True,
        "no_broadcast_invariant": upgrades.get("no_broadcast") is True,
        "no_first_agent_wallet_api_key_requirement": birth.get("first_agent_requires_wallet") is False and birth.get("first_agent_requires_api_key") is False and birth.get("first_agent_requires_funds") is False,
        "public_alpha_docs_updated": all((root_path / path).exists() for path in ("docs/AGENT_BUILDER.md", "docs/AGENT_GENESIS.md", "docs/AGENT_INTERNET.md")) and "first agent requires no wallet/api key/funds" in docs_text,
        "no_overclaim_invariant": _no_overclaims(docs_text),
    }
    return {
        "ok": all(evidence.values()),
        **evidence,
        "defaults": defaults,
        "plan": plan,
        "birth": birth,
        "upgrades": upgrades,
        "api_routes": tuple(sorted(_REQUIRED_ROUTES)),
        "artifact_paths": {
            "agent_builder_plans": "artifacts/agents/new/plans/",
            "births": "artifacts/genesis/births/",
            "capability_upgrades": "artifacts/capability_upgrades/",
            "dashboard_fixture": "dashboard/src/mock-data/agent-builder.json",
        },
    }


def verify_agent_builder_evidence(record: Mapping[str, object]) -> Mapping[str, object]:
    blockers: list[str] = []
    required = (
        "agent_builder_available",
        "agent_builder_browser_route_available",
        "agent_builder_first_agent_simple_mode_available",
        "agent_builder_advanced_mode_available",
        "no_wallet_first_agent_visible",
        "no_api_key_first_agent_visible",
        "no_funds_first_agent_visible",
        "private_default_visible",
        "network_learning_opt_in_visible",
        "capability_composer_available",
        "byok_optional_upgrade_visible",
        "wallet_optional_upgrade_visible",
        "onchain_dry_run_optional_upgrade_visible",
        "x402_dry_run_optional_upgrade_visible",
        "agent_internet_publish_optional_visible",
        "skill_matcher_from_agent_builder_available",
        "mission_control_handoff_available",
        "read_only_demo_mode_available",
        "cli_agent_builder_available",
        "api_agent_builder_available",
        "mermaid_agent_builder_docs_available",
        "no_private_key_invariant",
        "no_seed_phrase_invariant",
        "no_funds_moved_invariant",
        "no_broadcast_invariant",
        "no_first_agent_wallet_api_key_requirement",
        "public_alpha_docs_updated",
        "no_overclaim_invariant",
    )
    if record.get("ok") is not True:
        blockers.append("agent_builder_evidence_not_ok")
    for key in required:
        if record.get(key) is not True:
            blockers.append(f"{key}_missing")
    birth = record.get("birth", {}) if isinstance(record.get("birth", {}), Mapping) else {}
    upgrades = record.get("upgrades", {}) if isinstance(record.get("upgrades", {}), Mapping) else {}
    if birth.get("first_agent_requires_wallet") is not False or birth.get("first_agent_requires_api_key") is not False:
        blockers.append("first_agent_requires_wallet_or_key")
    if upgrades.get("no_broadcast") is not True or upgrades.get("no_funds_moved") is not True:
        blockers.append("optional_upgrade_side_effect_invariant_failed")
    return {"ok": not blockers, "blockers": tuple(dict.fromkeys(blockers)), "record_ok": record.get("ok") is True}


def _card_optional(defaults: Mapping[str, object], capability_id: str) -> bool:
    cards = defaults.get("capability_cards", ())
    if not isinstance(cards, (list, tuple)):
        return False
    return any(isinstance(card, Mapping) and card.get("capability_id") == capability_id and card.get("optional") is True for card in cards)


def _scope_checks_ok() -> bool:
    return (
        required_scopes_for("GET", "/agent-builder/defaults") == (AGENT_BUILDER_READ_SCOPE,)
        and required_scopes_for("POST", "/agent-builder/assembly-plan") == (AGENT_BUILDER_CREATE_SCOPE,)
        and required_scopes_for("POST", "/agent-builder/birth") == (AGENT_BUILDER_CREATE_SCOPE,)
        and required_scopes_for("POST", "/agent-builder/simulate-upgrades") == (AGENT_BUILDER_SIMULATE_SCOPE,)
    )


def _docs_text(root: Path) -> str:
    parts: list[str] = []
    for path in (
        "docs/AGENT_BUILDER.md",
        "docs/START_HERE.md",
        "docs/AGENT_GENESIS.md",
        "docs/AGENT_INTERNET.md",
        "docs/BYOK_MODEL_KEYS.md",
        "docs/ONCHAIN_AGENT_UPGRADES.md",
        "docs/MISSION_CONTROL_QUICKSTART.md",
        "docs/PUBLIC_ALPHA_READINESS.md",
        "README.md",
        "BUILD_REPORT.md",
        "FLOW_MEMORY_STATUS.md",
    ):
        file_path = root / path
        if file_path.exists():
            parts.append(file_path.read_text(encoding="utf-8", errors="ignore").lower())
    return "\n".join(parts)


def _file_contains(path: Path, needle: str) -> bool:
    return path.exists() and needle.lower() in path.read_text(encoding="utf-8", errors="ignore").lower()


def _no_overclaims(text: str) -> bool:
    return not any(term in text for term in _OVERCLAIMS)
