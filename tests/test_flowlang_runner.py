import unittest
from pathlib import Path

from flow_memory.flowlang import profile_from_flowlang, run_flowlang_agent


class FlowLangRunnerTests(unittest.TestCase):
    def test_flowlang_profile_and_run(self) -> None:
        path = Path("examples/flowlang_skill_agent.flow")
        profile = profile_from_flowlang(path)
        result = run_flowlang_agent(path, "Run a safe local skill")
        self.assertEqual(profile.name, "FlowSkillAgent")
        self.assertTrue(result["accepted"])


if __name__ == "__main__":
    unittest.main()
