import unittest
import time

from flow_memory.api.auth import (
    ApiAuthConfig,
    api_key_hash,
    authorize_request,
    disable_api_key_record,
    issue_api_key_record,
    public_api_key_record,
    require_api_key,
    rotate_api_key_record,
)
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


    def test_authorize_request_rejects_replayed_nonce_when_enabled(self) -> None:
        timestamp = str(time.time())
        headers = {
            "x-flow-memory-api-key": "test",
            "x-flow-memory-timestamp": timestamp,
            "x-flow-memory-nonce": "nonce-auth-test-1",
        }
        config = ApiAuthConfig(api_key="test", enable_nonce_check=True, max_request_age_seconds=30)

        first = authorize_request(headers, config)
        replay = authorize_request(headers, config)
        stale = authorize_request(
            {
                "x-flow-memory-api-key": "test",
                "x-flow-memory-timestamp": str(time.time() - 120),
                "x-flow-memory-nonce": "nonce-auth-test-2",
            },
            config,
        )

        self.assertTrue(first.ok, first.reasons)
        self.assertFalse(replay.ok)
        self.assertIn("replayed request nonce", replay.reasons)
        self.assertFalse(stale.ok)
        self.assertIn("stale request timestamp", stale.reasons)

    def test_api_key_issue_rotate_disable_records_never_expose_hash_publicly(self) -> None:
        issued = issue_api_key_record(
            {
                "key_id": "key_tenant_rotation_v1",
                "tenant_id": "tenant_rotation",
                "principal": "svc-rotation",
                "scopes": ["compute:read"],
                "key_prefix": "fmk_rot_",
            },
            api_key="fmk_rot_secret_v1",
        )
        record = issued["record"]
        self.assertEqual(issued["api_key"], "fmk_rot_secret_v1")
        self.assertNotIn("api_key", record)
        self.assertEqual(record["key_hash"], api_key_hash("fmk_rot_secret_v1"))
        self.assertTrue(
            authorize_request({"x-flow-memory-api-key": "fmk_rot_secret_v1"}, ApiAuthConfig(api_key_records=(record,))).ok
        )

        rotated = rotate_api_key_record(record, {"key_id": "key_tenant_rotation_v2"}, api_key="fmk_rot_secret_v2")
        previous = rotated["previous_record"]
        next_record = rotated["record"]
        self.assertFalse(previous["enabled"])
        self.assertEqual(previous["status"], "rotated")
        self.assertEqual(next_record["previous_key_id"], "key_tenant_rotation_v1")
        config = ApiAuthConfig(api_key_records=(previous, next_record))
        self.assertFalse(authorize_request({"x-flow-memory-api-key": "fmk_rot_secret_v1"}, config).ok)
        self.assertTrue(authorize_request({"x-flow-memory-api-key": "fmk_rot_secret_v2"}, config).ok)

        disabled = disable_api_key_record(next_record, reason="compromised")
        public = public_api_key_record(disabled)
        self.assertFalse(disabled["enabled"])
        self.assertNotIn("key_hash", public)
        self.assertTrue(public["key_hash_configured"])
        self.assertEqual(public["disabled_reason"], "compromised")

    def test_issue_api_key_record_rejects_unknown_scopes(self) -> None:
        with self.assertRaisesRegex(ValueError, "unknown API scopes"):
            issue_api_key_record(
                {
                    "key_id": "key_bad_scope",
                    "tenant_id": "tenant_bad_scope",
                    "scopes": ["compute:read", "compute:typo"],
                    "key_prefix": "fmk_bad_",
                },
                api_key="fmk_bad_secret",
            )

if __name__ == "__main__":
    unittest.main()
