from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone

from flow_memory.safety.approval import HumanApprovalGate
from flow_memory.safety.system import SafetySystem
from flow_memory.skills.manifest import SkillManifest
from flow_memory.skills.registry import SkillRegistry
from flow_memory.skills.runner import SkillRunner
from flow_memory.skills.scheduler import SkillScheduler


class SkillsRunnerTests(unittest.TestCase):
    def test_validate_register_list_run_and_audit(self) -> None:
        safety = SafetySystem()
        registry = SkillRegistry(audit=safety.audit)
        manifest = SkillManifest(
            skill_id="echo",
            name="Echo",
            description="Echoes a message.",
            input_schema={
                "type": "object",
                "required": ["message"],
                "properties": {"message": {"type": "string"}},
                "additionalProperties": False,
            },
            output_schema={
                "type": "object",
                "required": ["message"],
                "properties": {"message": {"type": "string"}},
                "additionalProperties": False,
            },
            permissions=("respond",),
        )

        self.assertEqual(manifest.validate(), ())
        registry.register(manifest)
        self.assertEqual([skill.skill_id for skill in registry.list()], ["echo"])

        runner = SkillRunner(registry=registry, safety=safety)
        runner.register_handler("echo", lambda payload: {"message": payload["message"]})
        result = runner.run("echo", {"message": "ok"})

        self.assertTrue(result.success)
        self.assertEqual(result.output, {"message": "ok"})
        self.assertTrue(safety.audit.verify())
        self.assertIn("skill_registered", [event["kind"] for event in safety.audit.events()])
        self.assertIn("skill_run_completed", [event["kind"] for event in safety.audit.events()])

    def test_rejects_invalid_input_before_handler(self) -> None:
        registry = SkillRegistry()
        registry.register(
            SkillManifest(
                skill_id="strict",
                name="Strict",
                description="Requires a number.",
                input_schema={"type": "object", "required": ["count"], "properties": {"count": {"type": "integer"}}},
            )
        )
        runner = SkillRunner(registry=registry)
        runner.register_handler("strict", lambda _payload: {"unreachable": True})

        with self.assertRaises(ValueError):
            runner.run("strict", {"count": "1"})

    def test_unsafe_skill_requires_approval_and_is_audited(self) -> None:
        safety = SafetySystem()
        registry = SkillRegistry(audit=safety.audit)
        registry.register(
            SkillManifest(
                skill_id="write_file",
                name="Write File",
                description="Writes local state.",
                permissions=("filesystem.write",),
                risk_level="high",
            )
        )
        runner = SkillRunner(registry=registry, safety=safety)
        runner.register_handler("write_file", lambda _payload: {"written": True})

        denied = runner.run("write_file", {})

        self.assertFalse(denied.success)
        decision = denied.policy_decision
        self.assertIsNotNone(decision)
        assert decision is not None
        self.assertTrue(decision.requires_human)
        self.assertIn("Human approval defer", denied.error or "")
        self.assertTrue(safety.audit.verify())

    def test_approved_unsafe_skill_can_run_locally(self) -> None:
        safety = SafetySystem(approval=HumanApprovalGate(lambda _plan, _decision: True))
        registry = SkillRegistry(audit=safety.audit)
        registry.register(
            SkillManifest(
                skill_id="approved_write",
                name="Approved Write",
                description="Writes only after approval.",
                permissions=("filesystem.write",),
                risk_level="high",
            )
        )
        runner = SkillRunner(registry=registry, safety=safety)
        runner.register_handler("approved_write", lambda _payload: {"written": True})

        result = runner.run("approved_write", {})

        self.assertTrue(result.success)
        self.assertEqual(result.output, {"written": True})
        decision = result.policy_decision
        self.assertIsNotNone(decision)
        assert decision is not None
        self.assertTrue(decision.requires_human)

    def test_economic_value_skill_metadata_triggers_review(self) -> None:
        safety = SafetySystem()
        registry = SkillRegistry(audit=safety.audit)
        manifest = SkillManifest(
            skill_id="bid",
            name="Bid",
            description="Places a local marketplace bid envelope.",
            permissions=("marketplace.bid",),
            economic_value=2.5,
            required_capabilities=("economy.marketplace",),
            risk_level="medium",
        )
        registry.register(manifest)
        runner = SkillRunner(registry=registry, safety=safety)
        runner.register_handler("bid", lambda _payload: {"bid": "local"})

        result = runner.run("bid", {})

        self.assertFalse(result.success)
        self.assertEqual(registry.get("bid").economic_value, 2.5)
        self.assertEqual(registry.get("bid").required_capabilities, ("economy.marketplace",))
        self.assertIn("Economic value 2.5 exceeds automatic limit 0.0", result.error or "")

    def test_scheduler_due_selection_is_deterministic(self) -> None:
        registry = SkillRegistry()
        now = datetime(2026, 5, 23, 12, 0, tzinfo=timezone.utc)
        registry.register(
            SkillManifest(
                skill_id="z_due",
                name="Z Due",
                description="Due last alphabetically.",
                schedule={"interval_seconds": 60, "start_at": (now - timedelta(seconds=1)).isoformat()},
            )
        )
        registry.register(
            SkillManifest(
                skill_id="a_due",
                name="A Due",
                description="Due first alphabetically.",
                schedule={"interval_seconds": 60, "start_at": now.isoformat()},
            )
        )
        registry.register(
            SkillManifest(
                skill_id="disabled",
                name="Disabled",
                description="Never due.",
                schedule={"enabled": False, "interval_seconds": 0},
            )
        )
        scheduler = SkillScheduler(registry=registry)

        self.assertEqual([skill.skill_id for skill in scheduler.list_due(now)], ["a_due", "z_due"])
        scheduler.mark_run("a_due", now)
        self.assertEqual([skill.skill_id for skill in scheduler.list_due(now + timedelta(seconds=30))], ["z_due"])
        self.assertEqual([skill.skill_id for skill in scheduler.list_due(now + timedelta(seconds=60))], ["a_due", "z_due"])


if __name__ == "__main__":
    unittest.main()
