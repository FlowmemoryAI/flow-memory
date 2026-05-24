"""Agent binding for local Compute Market advisory planning."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from flow_memory.agents.planner import Plan
from flow_memory.agents.profile import AgentProfile
from flow_memory.compute_market.planner import compute_marketplace_plan


@dataclass(frozen=True)
class AgentComputeBinding:
    """Attach dry-run compute routing metadata to agent plans.

    This binding never calls live providers, reserves real capacity, moves funds,
    signs transactions, or broadcasts settlement. It is advisory and fail-closed.
    """

    def plan(self, profile: AgentProfile, goal: str, plan: Plan) -> Mapping[str, Any]:
        config = dict(profile.compute_config or {})
        if not config or config.get("enabled") is False:
            return {"enabled": False, "status": "disabled", "dry_run_only": True}
        if "budget_policy" not in config:
            return _fail_closed("compute budget policy missing")
        policy = dict(config.get("budget_policy", {}))
        if not bool(policy.get("dry_run_required", True)):
            return _fail_closed("compute market requires dry_run_required=true")
        task_config = dict(config.get("task_profile", {}))
        task_config.setdefault("goal_id", goal)
        task_config.setdefault("task_id", plan.plan_id)
        task_config.setdefault("model", config.get("model", "small-general"))
        task_config.setdefault("expected_input_tokens", config.get("expected_input_tokens", max(1, len(goal.split()) * 16)))
        task_config.setdefault("expected_output_tokens", config.get("expected_output_tokens", 256))
        task_config.setdefault("quality_sensitive", bool(config.get("quality_sensitive", False)))
        task_config.setdefault("requires_marketplace", bool(policy.get("marketplace_only", config.get("marketplace_only", False))))
        record = compute_marketplace_plan({"task": task_config, "policy": policy})
        if not record.get("ok"):
            return {
                "enabled": True,
                "status": "fail_closed",
                "reason": str(record.get("reason", "compute route denied")),
                "dry_run_only": True,
                "safety_authority": "policy_engine_and_approval_gate",
                "record": record,
            }
        return {
            "enabled": True,
            "status": "planned",
            "dry_run_only": True,
            "decision": record.get("decision", {}),
            "quote": record.get("quote", {}),
            "payment_intent": record.get("payment_intent", {}),
            "settlement_simulation": record.get("settlement_simulation", {}),
            "economic_memory": record.get("economic_memory", {}),
            "safety_authority": "policy_engine_and_approval_gate",
            "record": record,
        }


def _fail_closed(reason: str) -> Mapping[str, Any]:
    return {
        "enabled": True,
        "status": "fail_closed",
        "reason": reason,
        "dry_run_only": True,
        "safety_authority": "policy_engine_and_approval_gate",
    }
