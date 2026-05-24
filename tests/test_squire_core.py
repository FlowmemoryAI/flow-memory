import json
import subprocess
import sys
from pathlib import Path

import pytest

from flow_memory.squire import build_squire_goal_plan, classify_squire_goal, inspect_squire_environment
from flow_memory.squire.memory import build_economic_memory_record, economic_memory_schema
from flow_memory.squire.models import AgentTreasury, RouteCandidate, SquireMode, SquireRoutingPolicy
from flow_memory.squire.routing import choose_route, level5_proxy_base_url, parse_usepod_response_headers, usepod_proxy_base_url
from flow_memory.squire.tool_commerce import build_agent_wallet_payment_plan
from flow_memory.squire.provider import build_provider_setup_plan
from flow_memory.squire.docs_sync import docs_sync_plan

ROOT = Path(__file__).resolve().parents[1]


def test_squire_goal_classification_is_multi_mode():
    modes = classify_squire_goal("UsePod routing with wallet budget and 402 paid DNS tool, then monetize GPU")

    assert modes[0] == SquireMode.HYBRID
    assert SquireMode.BUYER in modes
    assert SquireMode.TREASURY in modes
    assert SquireMode.PAID_TOOL in modes
    assert SquireMode.PROVIDER in modes


def test_squire_environment_does_not_fabricate_tokens():
    env = inspect_squire_environment({})

    assert env.has_level5_token is False
    assert env.has_usepod_token is False
    assert env.funded_balance is False
    assert "real_funds_enabled" in env.constraints


def test_squire_plan_contains_required_sections_and_memory_fields():
    plan = build_squire_goal_plan("Use cheap marketplace-only inference and record route ROI", environment=inspect_squire_environment({}))
    record = plan.as_record()

    assert record["goal_summary"].startswith("Use cheap")
    assert "UsePod proxy/routing" in record["live_stack_to_use_now"]
    assert "TEE attestation" in record["optional_roadmap_extensions"]
    assert "treasury_layer" in record["system_architecture"]
    assert "routing_layer" in record["system_architecture"]
    assert "tool_commerce_layer" in record["system_architecture"]
    assert "fallback_behavior" in record["system_architecture"]
    memory = record["memory_writes"][0]
    for key in ("goal_id", "wallet_pubkey", "route_mode", "provider_class", "tokens_in", "tokens_out", "balance_before", "balance_after", "latency_ms", "fallback_used", "quality_signal", "live_or_roadmap"):
        assert key in memory


def test_squire_route_selection_respects_marketplace_only():
    policy = SquireRoutingPolicy(marketplace_only=True, max_input_price_per_million=0.10, max_output_price_per_million=0.20)
    selected = choose_route(policy, (
        RouteCandidate("centralized", "fallback", "frontier", 0.01, 0.01),
        RouteCandidate("marketplace", "market", "small", 0.05, 0.15),
    ))

    assert selected.provider_class == "marketplace"
    with pytest.raises(ValueError):
        choose_route(policy, (RouteCandidate("centralized", "fallback", "frontier", 0.01, 0.01),))


def test_proxy_url_builders_and_headers():
    assert usepod_proxy_base_url("token-123") == "https://api.usepod.ai/proxy/token-123/v1"
    assert level5_proxy_base_url("level-123") == "https://api.level5.cloud/proxy/level-123"
    parsed = parse_usepod_response_headers({"X-Balance-Remaining": "12.5", "X-Pod-Route": "centralized-fallback"})
    assert parsed["balance_remaining"] == 12.5
    assert parsed["fallback_used"] is True
    assert parsed["provider_class"] == "centralized"


def test_economic_memory_record_estimates_cost_and_schema():
    treasury = AgentTreasury(wallet_pubkey="wallet", usepod_token_present=True, usepod_token_id="pod-token", usdc_balance=2.0)
    record = build_economic_memory_record(
        goal_id="goal-1",
        treasury=treasury,
        headers={"X-Pod-Route": "marketplace"},
        tokens_in=1000,
        tokens_out=2000,
        price_input_per_million=1.0,
        price_output_per_million=2.0,
        quality_signal=0.8,
    )

    assert record.total_cost == 0.005
    assert record.balance_after == 1.995
    assert record.provider_class == "marketplace"
    assert "provider_model_id" in economic_memory_schema()


def test_tool_provider_and_docs_seams_are_offline_safe():
    payment = build_agent_wallet_payment_plan(service="agent-dns", url="https://example.invalid/dns", wallet_pubkey="wallet", max_payment_usdc=0.25)
    provider = build_provider_setup_plan(gpu_available=False)
    sync = docs_sync_plan(enabled=False)

    assert payment.command[:2] == ("agent-wallet", "request")
    assert provider.provider_mode_recommended is False
    assert sync["base_tests_fetch_network"] is False


def test_squire_goal_script_outputs_json(tmp_path):
    out = tmp_path / "squire.json"
    completed = subprocess.run(
        [sys.executable, "scripts/squire_goal.py", "--goal", "UsePod route with budget", "--json-out", str(out)],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(completed.stdout)
    assert payload["ok"] is True
    assert payload["plan"]["budget_and_routing_policy"]["selected_route"]
    assert json.loads(out.read_text(encoding="utf-8")) == payload


def test_squire_goal_demo_runs():
    completed = subprocess.run([sys.executable, "examples/squire_goal_demo.py"], cwd=ROOT, check=True, capture_output=True, text=True)
    payload = json.loads(completed.stdout)
    assert payload["ok"] is True
    assert "UsePod proxy/routing" in payload["live_stack"]
