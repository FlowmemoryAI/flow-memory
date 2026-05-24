from flow_memory.compute_market import compute_marketplace_plan, default_routes
from flow_memory.compute_market.planner import budget_policy_from_mapping, deterministic_route_decision, task_profile_from_mapping


def test_compute_models_serialize_and_plan_is_dry_run():
    plan = compute_marketplace_plan({"task": {"task_id": "t1", "expected_input_tokens": 1000, "expected_output_tokens": 500}, "policy": {"max_total_cost": 0.01, "max_quote": 0.01, "dry_run_required": True}})

    assert plan["ok"] is True
    assert plan["dry_run_only"] is True
    assert plan["no_private_keys"] is True
    assert plan["no_funds_moved"] is True
    assert plan["no_broadcast"] is True
    assert plan["payment_intent"]["status"] == "dry_run_planned"
    assert plan["settlement_simulation"]["no_live_settlement"] is True


def test_compute_policy_fails_closed_without_policy():
    task = task_profile_from_mapping({"task_id": "missing-policy"})
    decision = deterministic_route_decision(task, None, default_routes())

    assert decision.ok is False
    assert decision.status == "fail_closed"
    assert "policy missing" in decision.reason


def test_compute_policy_fails_closed_when_over_budget():
    task = task_profile_from_mapping({"task_id": "over-budget", "expected_input_tokens": 10_000_000, "expected_output_tokens": 10_000_000})
    policy = budget_policy_from_mapping({"max_total_cost": 0.001, "max_quote": 0.001, "dry_run_required": True})
    decision = deterministic_route_decision(task, policy, default_routes())

    assert decision.ok is False
    assert decision.status == "fail_closed"
    assert "exceeds budget" in decision.reason


def test_route_selection_strategies_are_deterministic():
    task = task_profile_from_mapping({"task_id": "quality", "quality_sensitive": True})
    policy = budget_policy_from_mapping({"max_total_cost": 1.0, "max_quote": 1.0, "strategy": "cheapest_eligible", "dry_run_required": True})
    quality = deterministic_route_decision(task, policy, default_routes())

    task_latency = task_profile_from_mapping({"task_id": "latency", "latency_sensitive": True})
    latency = deterministic_route_decision(task_latency, policy, default_routes())

    assert quality.selected_route is not None
    assert quality.selected_route.route_id == "central-frontier"
    assert latency.selected_route is not None
    assert latency.selected_route.route_id == "central-frontier"


def test_marketplace_only_excludes_centralized_fallback():
    task = task_profile_from_mapping({"task_id": "market", "requires_marketplace": True})
    policy = budget_policy_from_mapping({"max_total_cost": 1.0, "max_quote": 1.0, "marketplace_only": True, "dry_run_required": True})
    decision = deterministic_route_decision(task, policy, default_routes())

    assert decision.ok is True
    assert decision.selected_route is not None
    assert decision.selected_route.provider_class == "marketplace"
