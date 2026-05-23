import unittest

from flow_memory.api.auth import ApiAuthConfig, require_api_key


class ApiAuthTests(unittest.TestCase):
    def test_api_key_auth_seam(self) -> None:
        config = ApiAuthConfig(api_key="test")
        self.assertTrue(require_api_key({"x-flow-memory-api-key": "test"}, config))
        self.assertFalse(require_api_key({}, config))


if __name__ == "__main__":
    unittest.main()
