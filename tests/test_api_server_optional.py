import unittest

from flow_memory.api.server import create_app


class ApiServerOptionalTests(unittest.TestCase):
    def test_fastapi_server_is_optional(self) -> None:
        try:
            app = create_app()
        except RuntimeError as exc:
            self.assertIn("optional", str(exc))
        else:
            self.assertIsNotNone(app)


if __name__ == "__main__":
    unittest.main()
