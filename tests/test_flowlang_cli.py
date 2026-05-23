import io
import json
import unittest
from contextlib import redirect_stdout

from flow_memory.cli import main


class FlowLangCliTests(unittest.TestCase):
    def test_flow_cli_runs_declared_agent(self) -> None:
        out = io.StringIO()
        with redirect_stdout(out):
            code = main(["--flow", "examples/flowlang_agent.flow", "--json", "Run the declared agent"])
        self.assertEqual(code, 0)
        self.assertIn("accepted", json.loads(out.getvalue()))


if __name__ == "__main__":
    unittest.main()
