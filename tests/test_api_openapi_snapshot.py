import json
import unittest
from pathlib import Path

from flow_memory.api.openapi import openapi_schema


class ApiOpenApiSnapshotTests(unittest.TestCase):
    def test_committed_openapi_snapshot_matches_generator(self) -> None:
        root = Path(__file__).resolve().parents[1]
        snapshot = json.loads((root / "docs/openapi/flow-memory.openapi.json").read_text(encoding="utf-8"))
        self.assertEqual(
            json.loads(json.dumps(snapshot, sort_keys=True)),
            json.loads(json.dumps(openapi_schema(), sort_keys=True)),
        )
        self.assertIn("/flowlang/run", snapshot["paths"])


if __name__ == "__main__":
    unittest.main()
