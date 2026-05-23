import unittest
from datetime import datetime, timezone

from flow_memory.skills import SkillManifest, SkillRegistry, SkillScheduler


class SkillSchedulerTests(unittest.TestCase):
    def test_due_skills_use_interval(self) -> None:
        registry = SkillRegistry()
        registry.register(SkillManifest(id="hourly", name="Hourly", description="hourly", schedule={"interval_seconds": 3600}))
        scheduler = SkillScheduler(registry=registry, now_fn=lambda: datetime(2026, 1, 1, tzinfo=timezone.utc))
        self.assertEqual(tuple(skill.skill_id for skill in scheduler.due_skills()), ("hourly",))
        scheduler.mark_run("hourly")
        self.assertEqual(scheduler.due_skills(), ())


if __name__ == "__main__":
    unittest.main()
