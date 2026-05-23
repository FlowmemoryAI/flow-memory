import json
import unittest

from flow_memory.ir import (
    AgentSpec,
    EconomicSpec,
    MemorySpec,
    PermissionSpec,
    PlanSpec,
    PolicySpec,
    RiskLevel,
    SkillSpec,
    compile_agent,
    manifest_json,
)


class FlowIRTests(unittest.TestCase):
    def test_valid_agent_compiles_to_json_manifest(self) -> None:
        agent = AgentSpec(
            name="FlowResearcher",
            identity="did:flow:researcher",
            memory=MemorySpec(economic=True),
            policies=(PolicySpec(id="wallet-policy", permissions=("wallet.sign",), risk_level=RiskLevel.HIGH.value),),
            skills=(
                SkillSpec(
                    id="settle",
                    permissions=(PermissionSpec(name="wallet.sign"),),
                    risk_level=RiskLevel.HIGH.value,
                ),
            ),
            plans=(PlanSpec(id="settle-plan", steps=("settle",)),),
            economy=EconomicSpec(settlement="local", budget=1),
        )

        result = compile_agent(agent)

        self.assertTrue(result.ok)
        manifest = json.loads(manifest_json(agent))
        self.assertEqual(manifest["name"], "FlowResearcher")
        self.assertEqual(manifest["plans"][0]["steps"], ["settle"])

    def test_rejects_missing_agent_name(self) -> None:
        result = compile_agent(AgentSpec(name=""))

        self.assertFalse(result.ok)
        self.assertIn("agent name is required", result.errors)

    def test_rejects_unsafe_permission_without_policy(self) -> None:
        agent = AgentSpec(
            name="Unsafe",
            skills=(SkillSpec(id="writer", permissions=(PermissionSpec(name="memory.write"),), risk_level="high"),),
        )

        result = compile_agent(agent)

        self.assertFalse(result.ok)
        self.assertIn("unsafe skill permission 'memory.write' requires a policy", result.errors)

    def test_rejects_economy_without_identity(self) -> None:
        result = compile_agent(AgentSpec(name="Economic", economy=EconomicSpec(settlement="local")))

        self.assertFalse(result.ok)
        self.assertIn("economic settlement requires identity", result.errors)

    def test_rejects_plan_referencing_missing_skill(self) -> None:
        result = compile_agent(AgentSpec(name="Planner", plans=(PlanSpec(id="bad", steps=("missing",)),)))

        self.assertFalse(result.ok)
        self.assertIn("plan 'bad' references missing skill 'missing'", result.errors)


if __name__ == "__main__":
    unittest.main()
