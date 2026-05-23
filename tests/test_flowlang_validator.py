import unittest

from flow_memory.flowlang import EXAMPLE_FLOWLANG, INVALID_MISSING_POLICY, compile_flowlang, validate_flowlang


class FlowLangValidatorTests(unittest.TestCase):
    def test_compile_example(self) -> None:
        result = compile_flowlang(EXAMPLE_FLOWLANG)

        self.assertTrue(result.ok)
        self.assertEqual(result.manifest["name"], "FlowResearcher")
        self.assertEqual(result.manifest["economy"]["settlement"], "local")

    def test_rejects_unknown_risk_level(self) -> None:
        errors = validate_flowlang(
            """agent Risky
skill odd:
  description: unknown risk
  permissions: [respond]
  risk: extreme
"""
        )

        self.assertTrue(any("unknown risk level" in error for error in errors))

    def test_rejects_unsafe_skill_permission_without_policy(self) -> None:
        errors = validate_flowlang(INVALID_MISSING_POLICY)

        self.assertIn("unsafe skill permission 'memory.write' requires a policy", errors)

    def test_rejects_economic_settlement_without_identity(self) -> None:
        errors = validate_flowlang(
            """agent Economic
skill research:
  description: safe
  permissions: [memory.read]
  risk: low
plan p:
  steps: [research]
economy:
  settlement: local
"""
        )

        self.assertIn("economic settlement requires identity", errors)

    def test_rejects_plan_referencing_missing_skill(self) -> None:
        errors = validate_flowlang(
            """agent Planner
plan p:
  steps: [missing]
"""
        )

        self.assertIn("plan 'p' references missing skill 'missing'", errors)


if __name__ == "__main__":
    unittest.main()
