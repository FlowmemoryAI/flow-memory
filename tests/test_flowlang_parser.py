import unittest

from flow_memory.flowlang import EXAMPLE_FLOWLANG, FlowLangParseError, parse_flowlang


class FlowLangParserTests(unittest.TestCase):
    def test_parse_example_agent(self) -> None:
        agent = parse_flowlang(EXAMPLE_FLOWLANG)

        self.assertEqual(agent.name, "FlowResearcher")
        self.assertEqual(agent.identity, "did:flow:researcher-001")
        self.assertEqual(agent.memory.working_capacity, 7)
        self.assertTrue(agent.memory.economic)
        self.assertEqual(agent.policies[1].id, "economic-approval")
        self.assertEqual(agent.skills[0].id, "research-brief")
        self.assertEqual(agent.plans[0].steps, ("research-brief",))
        self.assertEqual(agent.economy.settlement, "local")

    def test_parser_rejects_indented_field_without_block(self) -> None:
        with self.assertRaises(FlowLangParseError):
            parse_flowlang("agent Broken\n  risk: high\n")


if __name__ == "__main__":
    unittest.main()
