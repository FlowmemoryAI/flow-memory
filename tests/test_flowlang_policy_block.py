import unittest
from pathlib import Path

from flow_memory.flowlang import compile_flowlang_file


class FlowLangPolicyBlockTests(unittest.TestCase):
    def test_unsafe_flowlang_plan_rejected_at_compile(self) -> None:
        result = compile_flowlang_file(Path("examples/flowlang_policy_block_demo.flow"))
        self.assertFalse(result.ok)
        self.assertTrue(any("unsafe skill permission" in error for error in result.errors))


if __name__ == "__main__":
    unittest.main()
