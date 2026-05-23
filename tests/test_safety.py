import unittest

from flow_memory.core.types import Plan, PlanStep, PolicyDecision
from flow_memory.safety.approval import ApprovalStatus, HumanApprovalGate
from flow_memory.safety.system import SafetySystem


class SafetyTests(unittest.TestCase):
    def test_denies_unknown_permission(self) -> None:
        safety = SafetySystem()
        plan = Plan(goal="execute raw code", steps=(PlanStep(action="code.execute.raw", required_permission="code.execute"),))
        decision = safety.approve(plan)
        self.assertFalse(decision.approved)
        self.assertTrue(decision.requires_human)

    def test_allows_read_only_plan(self) -> None:
        safety = SafetySystem()
        plan = Plan(goal="observe", steps=(PlanStep(action="observe_environment", required_permission="environment.observe"),))
        decision = safety.approve(plan)
        self.assertTrue(decision.approved)

    def test_rate_limiter_blocks(self) -> None:
        safety = SafetySystem()
        safety.rate_limiter.max_events = 1
        plan = Plan(goal="respond", steps=(PlanStep(action="respond"),))
        self.assertTrue(safety.approve(plan).approved)
        self.assertFalse(safety.approve(plan).approved)


    def test_circuit_breaker_opens_after_repeated_unsafe_plans(self) -> None:
        safety = SafetySystem()
        safety.circuit_breaker.max_failures = 2
        unsafe_plan = Plan(
            goal="execute raw code",
            steps=(PlanStep(action="code.execute.raw", required_permission="code.execute"),),
        )
        safe_plan = Plan(goal="observe", steps=(PlanStep(action="observe_environment", required_permission="environment.observe"),))

        self.assertFalse(safety.approve(unsafe_plan).approved)
        self.assertFalse(safety.circuit_breaker.opened)
        self.assertFalse(safety.approve(unsafe_plan).approved)
        self.assertTrue(safety.circuit_breaker.opened)

        blocked = safety.approve(safe_plan)
        self.assertFalse(blocked.approved)
        self.assertEqual(tuple(blocked.reasons), ("Circuit breaker open after repeated unsafe or failed outcomes",))

    def test_successful_action_result_resets_circuit_breaker_failures(self) -> None:
        safety = SafetySystem()
        safety.circuit_breaker.max_failures = 2
        unsafe_plan = Plan(
            goal="execute raw code",
            steps=(PlanStep(action="code.execute.raw", required_permission="code.execute"),),
        )
        safe_plan = Plan(goal="respond", steps=(PlanStep(action="respond"),))

        self.assertFalse(safety.approve(unsafe_plan).approved)
        self.assertEqual(safety.circuit_breaker.failures, 1)
        safety.record_action_result(safe_plan, {"success": True})
        self.assertEqual(safety.circuit_breaker.failures, 0)
        self.assertFalse(safety.circuit_breaker.opened)

        self.assertFalse(safety.approve(unsafe_plan).approved)
        self.assertEqual(safety.circuit_breaker.failures, 1)
        self.assertFalse(safety.circuit_breaker.opened)

    def test_failed_action_results_can_open_circuit_breaker(self) -> None:
        safety = SafetySystem()
        safety.circuit_breaker.max_failures = 2
        plan = Plan(goal="respond", steps=(PlanStep(action="respond"),))

        safety.record_action_result(plan, {"success": False, "error": "tool timeout"})
        self.assertFalse(safety.circuit_breaker.opened)
        safety.record_action_result(plan, {"success": False, "error": "tool timeout"})
        self.assertTrue(safety.circuit_breaker.opened)
        self.assertFalse(safety.approve(plan).approved)

    def test_approval_gate_exposes_allow_deny_defer(self) -> None:
        plan = Plan(goal="write", steps=(PlanStep(action="write_file", required_permission="filesystem.write"),))
        decision = PolicyDecision(approved=True)

        self.assertIs(HumanApprovalGate().request_approval(plan, decision), ApprovalStatus.DEFER)
        self.assertIs(HumanApprovalGate(lambda _plan, _decision: True).request_approval(plan, decision), ApprovalStatus.ALLOW)
        self.assertIs(HumanApprovalGate(lambda _plan, _decision: False).request_approval(plan, decision), ApprovalStatus.DENY)
        self.assertIs(
            HumanApprovalGate(lambda _plan, _decision: "defer").request_approval(plan, decision),
            ApprovalStatus.DEFER,
        )

    def test_audit_hash_chain_detects_tamper(self) -> None:
        safety = SafetySystem()
        plan = Plan(goal="respond", steps=(PlanStep(action="respond"),))
        safety.approve(plan)
        self.assertTrue(safety.audit.verify())
        safety.audit._events[0] = dict(safety.audit._events[0], plan_id="tampered")  # test internal tamper path
        self.assertFalse(safety.audit.verify())


if __name__ == "__main__":
    unittest.main()
