import unittest
from typing import Any, Mapping, cast

from flow_memory.api.openapi import openapi_schema


class ApiOpenApiGenerationTests(unittest.TestCase):
    def test_openapi_contains_flowlang_paths(self) -> None:
        schema = openapi_schema()
        self.assertIn("/flowlang/compile", cast(Mapping[str, Any], schema["paths"]))


if __name__ == "__main__":
    unittest.main()
