"""Defense-in-depth safety facade."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Mapping

from flow_memory.core.types import Plan, PolicyDecision
from flow_memory.safety.approval import ApprovalStatus, HumanApprovalGate
from flow_memory.safety.audit import ImmutableAuditLog
from flow_memory.safety.circuit_breaker import CircuitBreaker
from flow_memory.safety.policies import OPAPolicyEngine
from flow_memory.safety.rate_limit import RateLimiter
from flow_memory.safety.slashing import EconomicSlashing


@dataclass
class SafetySystem:
    """Policy evaluation, approval, audit, rate limiting, and slashing hooks."""

    policies: OPAPolicyEngine = field(default_factory=OPAPolicyEngine)
    approval: HumanApprovalGate = field(default_factory=HumanApprovalGate)
    audit: ImmutableAuditLog = field(default_factory=ImmutableAuditLog)
    rate_limiter: RateLimiter = field(default_factory=RateLimiter)
    slashing: EconomicSlashing = field(default_factory=EconomicSlashing)
    circuit_breaker: CircuitBreaker = field(default_factory=CircuitBreaker)

    def approve(self, plan: Plan) -> PolicyDecision:
        if not self.circuit_breaker.allow():
            decision = PolicyDecision(
                approved=False,
                reasons=("Circuit breaker open after repeated unsafe or failed outcomes",),
                requires_human=True,
                risk_level="high",
            )
            self.audit.append(
                {
                    "kind": "policy_decision",
                    "plan_id": plan.plan_id,
                    "required_permissions": sorted(plan.required_permissions),
                    "decision": asdict(decision),
                    "circuit_breaker": {
                        "opened": self.circuit_breaker.opened,
                        "failures": self.circuit_breaker.failures,
                        "reasons": tuple(self.circuit_breaker.reasons),
                    },
                }
            )
            return decision

        if not self.rate_limiter.allow():
            decision = PolicyDecision(
                approved=False,
                reasons=("Rate limit exceeded",),
                requires_human=True,
                risk_level="high",
            )
            self.circuit_breaker.record_failure("Rate limit exceeded")
            self.audit.append({"kind": "policy_decision", "decision": asdict(decision)})
            return decision

        decision = self.policies.evaluate(plan)
        if decision.approved and self.approval.requires_approval(plan, decision):
            approval_status = self.approval.request_approval(plan, decision)
            if approval_status is not ApprovalStatus.ALLOW:
                decision = PolicyDecision(
                    approved=False,
                    reasons=tuple(decision.reasons) + (f"Human approval {approval_status.value}",),
                    requires_human=True,
                    risk_level=decision.risk_level,
                )
        if not decision.approved:
            self.circuit_breaker.record_failure("; ".join(decision.reasons) or "Safety decision denied")
        self.audit.append(
            {
                "kind": "policy_decision",
                "plan_id": plan.plan_id,
                "required_permissions": sorted(plan.required_permissions),
                "decision": asdict(decision),
            }
        )
        return decision

    def record_action_result(self, plan: Plan, result: Mapping[str, Any]) -> None:
        self.audit.append({"kind": "action_result", "plan_id": plan.plan_id, "result": result})
        if result.get("success") is True:
            self.circuit_breaker.record_success()
        elif result.get("success") is False:
            self.circuit_breaker.record_failure(str(result.get("error") or "Action failed"))
