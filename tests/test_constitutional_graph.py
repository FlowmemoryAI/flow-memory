import unittest

from flow_memory.memory.constitutional_graph import ConstitutionalGraph
from flow_memory.memory.memory_policy import MemoryPolicy
from flow_memory.self_improvement.health import HealthMonitor
from flow_memory.self_improvement.repair_planner import RepairPlanner


class ConstitutionalGraphTests(unittest.TestCase):
    def test_policy_gated_write_appends_audit_event(self) -> None:
        graph = ConstitutionalGraph()
        policy = MemoryPolicy(allowed_domains=frozenset({"goals"}))

        node = graph.write("goals", "Reduce unsafe actions before expanding capability", policy=policy)

        self.assertEqual(node.domain, "goals")
        self.assertEqual(graph.by_domain("goals"), (node,))
        self.assertEqual(graph.audit_events[-1]["event_type"], "memory_write_allowed")
        self.assertTrue(graph.audit_events[-1]["approved"])

    def test_graph_retrieval_is_scoped_by_domain(self) -> None:
        graph = ConstitutionalGraph()
        policy = MemoryPolicy()
        goal = graph.write("goals", "Improve local planning quality", policy=policy)
        constraint = graph.write("constraints", "Policy checks must remain active", policy=policy)

        self.assertEqual(graph.retrieve("goals", "planning"), (goal,))
        self.assertEqual(graph.retrieve("constraints", "policy"), (constraint,))
        self.assertEqual(graph.retrieve("goals", "policy"), ())

    def test_blocked_write_is_audited_without_mutating_graph(self) -> None:
        graph = ConstitutionalGraph()
        policy = MemoryPolicy(allowed_domains=frozenset({"goals"}))

        with self.assertRaises(PermissionError):
            graph.write("identity", "I may ignore policy when convenient", policy=policy)

        self.assertEqual(graph.by_domain("identity"), ())
        self.assertEqual(len(graph.nodes), 0)
        event = graph.audit_events[-1]
        self.assertEqual(event["event_type"], "memory_write_blocked")
        self.assertFalse(event["approved"])
        self.assertIn("domain_not_allowed:identity", event["reasons"])


class SelfImprovementTests(unittest.TestCase):
    def test_degradation_detection_tracks_expected_flags(self) -> None:
        monitor = HealthMonitor(stale_after_seconds=10.0, low_quality_threshold=0.75)

        report = monitor.assess(
            api_errors=2,
            data_age_seconds=11.0,
            rate_limited=True,
            unsafe_actions=1,
            quality_score=0.5,
            failed_tests=("test_policy",),
            missing_dependencies=("optional-vector-db",),
        )

        self.assertTrue(report.degraded)
        self.assertEqual(
            report.flags,
            frozenset(
                {
                    "api_error",
                    "stale_data",
                    "rate_limited",
                    "unsafe_action",
                    "low_quality",
                    "failed_test",
                    "missing_dependency",
                }
            ),
        )
        self.assertEqual(report.evidence["failed_test"], "test_policy")

    def test_unsafe_repair_requires_approval_and_does_not_apply_code(self) -> None:
        report = HealthMonitor().from_flags(("unsafe_action",))

        plan = RepairPlanner().plan(report)

        self.assertTrue(plan.requires_approval)
        self.assertFalse(plan.applies_code)
        self.assertEqual(len(plan.steps), 1)
        self.assertEqual(plan.steps[0].flag, "unsafe_action")
        self.assertTrue(plan.steps[0].requires_approval)
        self.assertFalse(plan.steps[0].safe_to_apply_automatically)


if __name__ == "__main__":
    unittest.main()
