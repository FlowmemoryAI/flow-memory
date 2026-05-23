import json
import unittest

from flow_memory.api.errors import ApiError, error_response, forbidden_error, rate_limited_error, validation_error


class ApiErrorContractTests(unittest.TestCase):
    def test_error_response_has_deterministic_json_shape(self) -> None:
        response = error_response(
            ApiError(
                code="request.invalid",
                message="Invalid request",
                status=400,
                details={"z": 2, "a": {"b": ["c"]}},
            ),
            request_id="req-1",
        )

        self.assertEqual(
            response,
            {
                "ok": False,
                "error": {
                    "code": "request.invalid",
                    "message": "Invalid request",
                    "status": 400,
                    "details": {"a": {"b": ("c",)}, "z": 2},
                    "request_id": "req-1",
                },
            },
        )
        json.dumps(response, sort_keys=True)

    def test_forbidden_error_shape(self) -> None:
        response = forbidden_error("Missing required API scope", details={"missing": ("api:write",)}).as_record()

        self.assertEqual(response["error"]["status"], 403)
        self.assertEqual(response["error"]["code"], "auth.forbidden")
        self.assertEqual(response["error"]["details"], {"missing": ("api:write",)})

    def test_rate_limited_error_shape(self) -> None:
        response = rate_limited_error(details={"reset_at": 60, "limit": 1}).as_record()

        self.assertEqual(response["error"]["status"], 429)
        self.assertEqual(response["error"]["code"], "rate_limit.exceeded")
        self.assertEqual(tuple(response["error"]["details"].keys()), ("limit", "reset_at"))

    def test_validation_error_shape(self) -> None:
        response = validation_error("Bad payload").as_record()

        self.assertEqual(response, {"ok": False, "error": {"code": "request.invalid", "message": "Bad payload", "status": 400}})


if __name__ == "__main__":
    unittest.main()
