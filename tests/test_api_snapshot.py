import unittest
import json
from pathlib import Path

from flow_memory.api.openapi import openapi_schema
from flow_memory.api.snapshot import api_snapshot, validate_api_snapshot


class ApiSnapshotTests(unittest.TestCase):
    def test_current_snapshot_validates(self) -> None:
        snapshot = api_snapshot()
        validation = validate_api_snapshot(snapshot)

        self.assertTrue(validation.ok)
        self.assertGreater(snapshot["endpoint_count"], 20)
        self.assertIn("POST /flowlang/run", snapshot["operations"])


    def test_committed_json_snapshot_validates(self) -> None:
        snapshot_path = Path(__file__).resolve().parents[1] / "docs" / "API_SNAPSHOT.json"
        snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))

        validation = validate_api_snapshot(snapshot)

        self.assertTrue(validation.ok, validation.errors)

    def test_snapshot_validation_detects_manifest_drift(self) -> None:
        snapshot = dict(api_snapshot())
        snapshot["endpoint_count"] = int(snapshot["endpoint_count"]) - 1

        validation = validate_api_snapshot(snapshot)

        self.assertFalse(validation.ok)
        self.assertIn("endpoint_count mismatch", " ".join(validation.errors))

    def test_openapi_includes_request_bodies_and_path_parameters(self) -> None:
        schema = openapi_schema()
        flowlang_compile = schema["paths"]["/flowlang/compile"]["post"]
        agent_get = schema["paths"]["/agents/{did}"]["get"]

        self.assertIn("requestBody", flowlang_compile)
        self.assertEqual("flowlang", flowlang_compile["tags"][0])
        self.assertEqual("did", agent_get["parameters"][0]["name"])


if __name__ == "__main__":
    unittest.main()
