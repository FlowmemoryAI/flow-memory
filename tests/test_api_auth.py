import unittest

from flow_memory.api.auth import ApiAuthConfig, api_key_hash, authorize_request, require_api_key
from flow_memory.api.signed_requests import sign_request
from flow_memory.crypto import generate_local_keypair


class ApiAuthTests(unittest.TestCase):
    def test_api_key_auth_seam(self) -> None:
        config = ApiAuthConfig(api_key="test")
        self.assertTrue(require_api_key({"x-flow-memory-api-key": "test"}, config))
        self.assertFalse(require_api_key({}, config))

    def test_api_key_headers_are_case_insensitive(self) -> None:
        config = ApiAuthConfig(api_key="test")
        self.assertTrue(require_api_key({"X-Flow-Memory-Api-Key": "test"}, config))

    def test_tenant_scoped_api_key_record_resolves_identity_and_scopes(self) -> None:
        config = ApiAuthConfig(
            api_key_records=(
                {
                    "key_id": "key_tenant_a_v1",
                    "key_prefix": "fmk_tenant_",
                    "key_hash": api_key_hash("fmk_tenant_secret"),
                    "tenant_id": "tenant_a",
                    "principal": "svc-tenant-a",
                    "scopes": ["compute:read", "compute:plan"],
                    "enabled": True,
                },
            )
        )

        decision = authorize_request({"x-flow-memory-api-key": "fmk_tenant_secret"}, config)

        self.assertTrue(decision.ok, decision.reasons)
        self.assertEqual(decision.tenant_id, "tenant_a")
        self.assertEqual(decision.principal, "svc-tenant-a")
        self.assertEqual(decision.scopes, ("compute:plan", "compute:read"))
        self.assertFalse(require_api_key({"x-flow-memory-api-key": "wrong"}, config))

    def test_authorize_request_accepts_valid_api_key_and_signature(self) -> None:
        key = generate_local_keypair("api-auth")
        payload = {"goal": "local"}
        signature = sign_request("POST", "/agents/a/run", payload, key)
        decision = authorize_request(
            {"x-flow-memory-api-key": "test"},
            ApiAuthConfig(api_key="test", require_signed_requests=True),
            method="POST",
            path="/agents/a/run",
            payload=payload,
            signature=signature,
            signature_key=key,
        )

        self.assertTrue(decision.ok, decision.reasons)

    def test_authorize_request_rejects_missing_signature(self) -> None:
        decision = authorize_request(
            {"x-flow-memory-api-key": "test"},
            ApiAuthConfig(api_key="test", require_signed_requests=True),
            method="POST",
            path="/agents/a/run",
            payload={"goal": "local"},
        )

        self.assertFalse(decision.ok)
        self.assertIn("signed request required", decision.reasons)

    def test_authorize_request_rejects_tampered_payload(self) -> None:
        key = generate_local_keypair("api-auth")
        signature = sign_request("POST", "/agents/a/run", {"goal": "local"}, key)
        decision = authorize_request(
            {"x-flow-memory-api-key": "test"},
            ApiAuthConfig(api_key="test", require_signed_requests=True),
            method="POST",
            path="/agents/a/run",
            payload={"goal": "changed"},
            signature=signature,
            signature_key=key,
        )

        self.assertFalse(decision.ok)
        self.assertIn("invalid request signature", decision.reasons)


if __name__ == "__main__":
    unittest.main()
