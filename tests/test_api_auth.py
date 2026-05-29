import base64
import hashlib
import hmac
import json
import unittest
import time

from flow_memory.api.auth import (
    ApiAuthConfig,
    RedisNonceReplayStore,
    api_key_hash,
    authorize_request,
    disable_api_key_record,
    is_valid_role,
    issue_api_key_record,
    public_api_key_record,
    require_api_key,
    rotate_api_key_record,
    validate_role_name,
)
from flow_memory.api.signed_requests import sign_request
from flow_memory.api.router import create_default_router
from flow_memory.api.scopes import required_scopes_for
from flow_memory.crypto import generate_local_keypair


def _jwt(secret: str, claims: dict[str, object], header: dict[str, object] | None = None) -> str:
    jwt_header = {"alg": "HS256", "typ": "JWT", **(header or {})}
    encoded_header = _b64url(json.dumps(jwt_header, separators=(",", ":"), sort_keys=True).encode("utf-8"))
    encoded_claims = _b64url(json.dumps(claims, separators=(",", ":"), sort_keys=True).encode("utf-8"))
    signed = f"{encoded_header}.{encoded_claims}".encode("ascii")
    signature = hmac.new(secret.encode("utf-8"), signed, hashlib.sha256).digest()
    return f"{encoded_header}.{encoded_claims}.{_b64url(signature)}"


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


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

    def test_authorize_request_rejects_api_key_record_with_unknown_scope(self) -> None:
        config = ApiAuthConfig(
            api_key_records=(
                {
                    "key_id": "key_invalid_scope",
                    "key_prefix": "fmk_invalid_",
                    "key_hash": api_key_hash("fmk_invalid_secret"),
                    "tenant_id": "tenant_invalid_scope",
                    "principal": "svc-invalid-scope",
                    "scopes": ["compute:read", "compute:not-a-real-scope"],
                    "enabled": True,
                },
            )
        )

        decision = authorize_request({"x-flow-memory-api-key": "fmk_invalid_secret"}, config)

        self.assertFalse(decision.ok)
        self.assertEqual(
            decision.reasons,
            ("api key record contains unknown scope: compute:not-a-real-scope",),
        )
        self.assertEqual(decision.key_id, "")

    def test_authorize_request_rejects_api_key_record_with_unknown_role(self) -> None:
        config = ApiAuthConfig(
            api_key_records=(
                {
                    "key_id": "key_invalid_role",
                    "key_prefix": "fmk_invalid_role_",
                    "key_hash": api_key_hash("fmk_invalid_role_secret"),
                    "tenant_id": "tenant_invalid_role",
                    "principal": "svc-invalid-role",
                    "roles": ["viewer", "superuser"],
                    "enabled": True,
                },
            )
        )

        decision = authorize_request({"x-flow-memory-api-key": "fmk_invalid_role_secret"}, config)

        self.assertFalse(decision.ok)
        self.assertEqual(decision.reasons, ("api key record invalid: unknown role: superuser",))
        self.assertEqual(decision.key_id, "")

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

    def test_authorize_request_binds_signature_to_nonce_and_timestamp(self) -> None:
        key = generate_local_keypair("api-auth-bound-nonce")
        payload = {"goal": "bound"}
        timestamp = str(time.time())
        changed_timestamp_value = str(float(timestamp) + 1.0)
        nonce = "nonce-auth-bound-1"
        signature = sign_request(
            "POST",
            "/agents/a/run",
            payload,
            key,
            nonce=nonce,
            timestamp=timestamp,
        )
        config = ApiAuthConfig(
            api_key="test",
            require_signed_requests=True,
            enable_nonce_check=True,
            max_request_age_seconds=30,
        )

        accepted = authorize_request(
            {
                "x-flow-memory-api-key": "test",
                "x-flow-memory-timestamp": timestamp,
                "x-flow-memory-nonce": nonce,
            },
            config,
            method="POST",
            path="/agents/a/run",
            payload=payload,
            signature=signature,
            signature_key=key,
        )
        changed_nonce = authorize_request(
            {
                "x-flow-memory-api-key": "test",
                "x-flow-memory-timestamp": timestamp,
                "x-flow-memory-nonce": "nonce-auth-bound-2",
            },
            config,
            method="POST",
            path="/agents/a/run",
            payload=payload,
            signature=signature,
            signature_key=key,
        )
        changed_timestamp = authorize_request(
            {
                "x-flow-memory-api-key": "test",
                "x-flow-memory-timestamp": changed_timestamp_value,
                "x-flow-memory-nonce": "nonce-auth-bound-3",
            },
            config,
            method="POST",
            path="/agents/a/run",
            payload=payload,
            signature=signature,
            signature_key=key,
        )

        self.assertTrue(accepted.ok, accepted.reasons)
        self.assertFalse(changed_nonce.ok)
        self.assertIn("invalid request signature", changed_nonce.reasons)
        self.assertFalse(changed_timestamp.ok)
        self.assertIn("invalid request signature", changed_timestamp.reasons)

    def test_invalid_signed_request_does_not_claim_nonce(self) -> None:
        key = generate_local_keypair("api-auth-no-nonce-burn")
        payload = {"goal": "no nonce burn"}
        timestamp = str(time.time())
        nonce = "nonce-auth-no-burn-1"
        headers = {
            "x-flow-memory-api-key": "test",
            "x-flow-memory-timestamp": timestamp,
            "x-flow-memory-nonce": nonce,
        }
        config = ApiAuthConfig(
            api_key="test",
            require_signed_requests=True,
            enable_nonce_check=True,
            max_request_age_seconds=30,
        )
        invalid_signature = sign_request(
            "POST",
            "/agents/a/run",
            payload,
            key,
            nonce="different-nonce",
            timestamp=timestamp,
        )
        valid_signature = sign_request(
            "POST",
            "/agents/a/run",
            payload,
            key,
            nonce=nonce,
            timestamp=timestamp,
        )

        rejected = authorize_request(
            headers,
            config,
            method="POST",
            path="/agents/a/run",
            payload=payload,
            signature=invalid_signature,
            signature_key=key,
        )
        accepted = authorize_request(
            headers,
            config,
            method="POST",
            path="/agents/a/run",
            payload=payload,
            signature=valid_signature,
            signature_key=key,
        )

        self.assertFalse(rejected.ok)
        self.assertIn("invalid request signature", rejected.reasons)
        self.assertTrue(accepted.ok, accepted.reasons)

    def test_authorize_request_uses_distributed_nonce_store(self) -> None:
        class FakeRedis:
            def __init__(self) -> None:
                self.values: dict[str, str] = {}

            def set(self, key: str, value: str, *, nx: bool, ex: int) -> bool:
                if nx and key in self.values:
                    return False
                self.values[key] = value
                assert ex == 30
                return True

        redis_client = FakeRedis()
        store_a = RedisNonceReplayStore("rediss://cache.example:6379/0", client=redis_client, require_tls=True)
        store_b = RedisNonceReplayStore("rediss://cache.example:6379/0", client=redis_client, require_tls=True)
        timestamp = str(time.time())
        headers = {
            "x-flow-memory-api-key": "test",
            "x-flow-memory-timestamp": timestamp,
            "x-flow-memory-nonce": "nonce-auth-distributed-1",
        }

        first = authorize_request(
            headers,
            ApiAuthConfig(api_key="test", enable_nonce_check=True, max_request_age_seconds=30, nonce_replay_store=store_a),
        )
        replay = authorize_request(
            headers,
            ApiAuthConfig(api_key="test", enable_nonce_check=True, max_request_age_seconds=30, nonce_replay_store=store_b),
        )

        self.assertTrue(first.ok, first.reasons)
        self.assertFalse(replay.ok)
        self.assertIn("replayed request nonce", replay.reasons)
        self.assertEqual(len(redis_client.values), 1)
        self.assertNotIn("nonce-auth-distributed-1", next(iter(redis_client.values)))

    def test_authorize_request_fails_closed_when_nonce_backend_unavailable(self) -> None:
        class BrokenRedis:
            def set(self, key: str, value: str, *, nx: bool, ex: int) -> bool:
                raise ConnectionError("down")

        decision = authorize_request(
            {
                "x-flow-memory-api-key": "test",
                "x-flow-memory-timestamp": str(time.time()),
                "x-flow-memory-nonce": "nonce-auth-backend-down",
            },
            ApiAuthConfig(
                api_key="test",
                enable_nonce_check=True,
                max_request_age_seconds=30,
                nonce_replay_store=RedisNonceReplayStore(
                    "rediss://cache.example:6379/0",
                    client=BrokenRedis(),
                    require_tls=True,
                ),
            ),
        )

        self.assertFalse(decision.ok)
        self.assertIn("nonce replay backend unavailable", decision.reasons)

    def test_authorize_request_accepts_valid_hs256_bearer_jwt(self) -> None:
        token = _jwt(
            "jwt-secret",
            {
                "sub": "user-123",
                "tenant_id": "tenant_jwt",
                "scope": "compute:read compute:plan",
                "iss": "https://issuer.example",
                "aud": "flow-memory-api",
                "exp": time.time() + 300,
                "iat": time.time(),
            },
            {"kid": "gateway-key-1"},
        )

        decision = authorize_request(
            {"authorization": f"Bearer {token}"},
            ApiAuthConfig(
                jwt_hs256_secret="jwt-secret",
                jwt_issuer="https://issuer.example",
                jwt_audience="flow-memory-api",
            ),
        )

        self.assertTrue(decision.ok, decision.reasons)
        self.assertEqual(decision.key_id, "gateway-key-1")
        self.assertEqual(decision.principal, "user-123")
        self.assertEqual(decision.tenant_id, "tenant_jwt")
        self.assertEqual(decision.scopes, ("compute:plan", "compute:read"))
        self.assertTrue(require_api_key({"authorization": f"Bearer {token}"}, ApiAuthConfig(jwt_hs256_secret="jwt-secret")))

    def test_authorize_request_rejects_tenantless_jwt_when_required(self) -> None:
        token = _jwt(
            "jwt-secret",
            {
                "sub": "user-no-tenant",
                "scope": "compute:read",
                "aud": "flow-memory-api",
                "exp": time.time() + 300,
                "iat": time.time(),
            },
        )

        decision = authorize_request(
            {"authorization": f"Bearer {token}"},
            ApiAuthConfig(
                jwt_hs256_secret="jwt-secret",
                jwt_audience="flow-memory-api",
                jwt_require_tenant=True,
            ),
        )

        self.assertFalse(decision.ok)
        self.assertEqual(decision.reasons, ("jwt tenant required",))
        self.assertEqual(decision.tenant_id, "")

    def test_authorize_request_maps_jwt_roles_to_scopes(self) -> None:
        token = _jwt(
            "jwt-secret",
            {
                "sub": "provider-admin-user",
                "tenant_id": "tenant_roles",
                "roles": ["provider-admin", "billing", "settlement-admin"],
                "aud": "flow-memory-api",
                "exp": time.time() + 300,
                "iat": time.time(),
            },
            {"kid": "gateway-role-key"},
        )

        decision = authorize_request(
            {"authorization": f"Bearer {token}"},
            ApiAuthConfig(jwt_hs256_secret="jwt-secret", jwt_audience="flow-memory-api"),
        )

        self.assertTrue(decision.ok, decision.reasons)
        self.assertEqual(decision.key_id, "gateway-role-key")
        self.assertEqual(decision.tenant_id, "tenant_roles")
        self.assertEqual(
            decision.scopes,
            (
                "compute:billing",
                "compute:provider-admin",
                "compute:read",
                "compute:settlement-admin",
            ),
        )

    def test_authorize_request_maps_jwt_inference_admin_role_to_scopes(self) -> None:
        token = _jwt(
            "jwt-secret",
            {
                "sub": "inference-admin-user",
                "tenant_id": "tenant_inference_roles",
                "roles": ["inference-admin"],
                "aud": "flow-memory-api",
                "exp": time.time() + 300,
                "iat": time.time(),
            },
            {"kid": "gateway-inference-role-key"},
        )

        decision = authorize_request(
            {"authorization": f"Bearer {token}"},
            ApiAuthConfig(jwt_hs256_secret="jwt-secret", jwt_audience="flow-memory-api"),
        )

        self.assertTrue(decision.ok, decision.reasons)
        self.assertEqual(decision.key_id, "gateway-inference-role-key")
        self.assertEqual(decision.tenant_id, "tenant_inference_roles")
        self.assertEqual(
            decision.scopes,
            (
                "inference:admin",
                "inference:audit",
                "inference:buy",
                "inference:plan",
                "inference:proxy",
                "inference:read",
                "inference:sell",
            ),
        )

    def test_authorize_request_rejects_jwt_unknown_scope_or_role(self) -> None:
        now = time.time()
        unknown_scope = _jwt(
            "jwt-secret",
            {
                "sub": "user-unknown-scope",
                "tenant_id": "tenant_unknown_scope",
                "scope": "compute:read compute:super-admin",
                "aud": "flow-memory-api",
                "exp": now + 300,
                "iat": now,
            },
        )
        unknown_role = _jwt(
            "jwt-secret",
            {
                "sub": "user-unknown-role",
                "tenant_id": "tenant_unknown_role",
                "roles": ["provider-admin", "owner"],
                "aud": "flow-memory-api",
                "exp": now + 300,
                "iat": now,
            },
        )

        scope_decision = authorize_request(
            {"authorization": f"Bearer {unknown_scope}"},
            ApiAuthConfig(jwt_hs256_secret="jwt-secret", jwt_audience="flow-memory-api"),
        )
        role_decision = authorize_request(
            {"authorization": f"Bearer {unknown_role}"},
            ApiAuthConfig(jwt_hs256_secret="jwt-secret", jwt_audience="flow-memory-api"),
        )

        self.assertFalse(scope_decision.ok)
        self.assertEqual(scope_decision.reasons, ("jwt contains unknown scope: compute:super-admin",))
        self.assertFalse(role_decision.ok)
        self.assertEqual(role_decision.reasons, ("jwt role invalid: unknown role: owner",))

    def test_authorize_request_accepts_valid_bearer_jwt_and_signature_when_required(self) -> None:
        key = generate_local_keypair("api-auth-jwt-signed")
        payload = {"goal": "local"}
        token = _jwt(
            "jwt-secret",
            {
                "sub": "user-signed",
                "tenant_id": "tenant_signed",
                "scope": "compute:execute compute:read",
                "iss": "https://issuer.example",
                "aud": "flow-memory-api",
                "exp": time.time() + 300,
                "iat": time.time(),
            },
            {"kid": "gateway-key-signed"},
        )
        signature = sign_request("POST", "/compute/jobs", payload, key)

        decision = authorize_request(
            {"authorization": f"Bearer {token}"},
            ApiAuthConfig(
                require_signed_requests=True,
                jwt_hs256_secret="jwt-secret",
                jwt_issuer="https://issuer.example",
                jwt_audience="flow-memory-api",
            ),
            method="POST",
            path="/compute/jobs",
            payload=payload,
            signature=signature,
            signature_key=key,
        )

        self.assertTrue(decision.ok, decision.reasons)
        self.assertEqual(decision.key_id, "gateway-key-signed")
        self.assertEqual(decision.principal, "user-signed")
        self.assertEqual(decision.tenant_id, "tenant_signed")
        self.assertEqual(decision.scopes, ("compute:execute", "compute:read"))

    def test_authorize_request_rejects_expired_or_wrong_audience_jwt(self) -> None:
        now = time.time()
        expired = _jwt("jwt-secret", {"sub": "user-123", "aud": "flow-memory-api", "iat": now - 600, "exp": now - 300})
        wrong_audience = _jwt("jwt-secret", {"sub": "user-123", "aud": "other-api", "iat": now, "exp": now + 300})

        expired_decision = authorize_request(
            {"authorization": f"Bearer {expired}"},
            ApiAuthConfig(jwt_hs256_secret="jwt-secret", jwt_audience="flow-memory-api", jwt_leeway_seconds=0),
        )
        wrong_audience_decision = authorize_request(
            {"authorization": f"Bearer {wrong_audience}"},
            ApiAuthConfig(jwt_hs256_secret="jwt-secret", jwt_audience="flow-memory-api"),
        )

        self.assertFalse(expired_decision.ok)
        self.assertIn("expired bearer token", expired_decision.reasons)
        self.assertFalse(wrong_audience_decision.ok)
        self.assertIn("jwt audience mismatch", wrong_audience_decision.reasons)


    def test_authorize_request_rejects_wrong_issuer_jwt(self) -> None:
        now = time.time()
        token = _jwt(
            "jwt-secret",
            {
                "sub": "user-wrong-issuer",
                "aud": "flow-memory-api",
                "iss": "https://issuer.invalid",
                "iat": now,
                "exp": now + 300,
            },
        )

        decision = authorize_request(
            {"authorization": f"Bearer {token}"},
            ApiAuthConfig(
                jwt_hs256_secret="jwt-secret",
                jwt_issuer="https://issuer.example",
                jwt_audience="flow-memory-api",
            ),
        )

        self.assertFalse(decision.ok)
        self.assertIn("jwt issuer mismatch", decision.reasons)

    def test_authorize_request_rejects_future_not_before_jwt(self) -> None:
        now = time.time()
        token = _jwt(
            "jwt-secret",
            {
                "sub": "user-future-nbf",
                "aud": "flow-memory-api",
                "iat": now,
                "nbf": now + 300,
                "exp": now + 600,
            },
        )

        decision = authorize_request(
            {"authorization": f"Bearer {token}"},
            ApiAuthConfig(
                jwt_hs256_secret="jwt-secret",
                jwt_audience="flow-memory-api",
                jwt_leeway_seconds=0,
            ),
        )

        self.assertFalse(decision.ok)
        self.assertIn("bearer token not yet valid", decision.reasons)

    def test_authorize_request_rejects_missing_or_future_iat_jwt(self) -> None:
        now = time.time()
        missing_iat = _jwt("jwt-secret", {"sub": "user-123", "aud": "flow-memory-api", "exp": now + 300})
        future_iat = _jwt(
            "jwt-secret",
            {"sub": "user-123", "aud": "flow-memory-api", "iat": now + 300, "exp": now + 600},
        )

        missing_decision = authorize_request(
            {"authorization": f"Bearer {missing_iat}"},
            ApiAuthConfig(jwt_hs256_secret="jwt-secret", jwt_audience="flow-memory-api", jwt_leeway_seconds=0),
        )
        future_decision = authorize_request(
            {"authorization": f"Bearer {future_iat}"},
            ApiAuthConfig(jwt_hs256_secret="jwt-secret", jwt_audience="flow-memory-api", jwt_leeway_seconds=0),
        )

        self.assertFalse(missing_decision.ok)
        self.assertIn("jwt iat required", missing_decision.reasons)
        self.assertFalse(future_decision.ok)
        self.assertIn("bearer token issued in the future", future_decision.reasons)

    def test_authorize_request_uses_jwt_jti_for_nonce_replay_protection(self) -> None:
        now = time.time()
        token = _jwt(
            "jwt-secret",
            {
                "sub": "user-replay",
                "tenant_id": "tenant_jwt_replay",
                "scope": "compute:read",
                "aud": "flow-memory-api",
                "iat": now,
                "exp": now + 300,
                "jti": "jwt-replay-token-1",
            },
            {"kid": "gateway-key-replay"},
        )
        config = ApiAuthConfig(
            jwt_hs256_secret="jwt-secret",
            jwt_audience="flow-memory-api",
            enable_nonce_check=True,
            max_request_age_seconds=30,
        )

        first = authorize_request({"authorization": f"Bearer {token}"}, config)
        replay = authorize_request({"authorization": f"Bearer {token}"}, config)

        self.assertTrue(first.ok, first.reasons)
        self.assertFalse(replay.ok)
        self.assertIn("replayed request nonce", replay.reasons)

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

    def test_api_key_roles_expand_to_scopes(self) -> None:
        issued = issue_api_key_record(
            {
                "key_id": "key_role_scoped_v1",
                "tenant_id": "tenant_role_scoped",
                "principal": "svc-role-scoped",
                "scopes": ["compute:plan"],
                "roles": ["provider-admin", "billing"],
                "key_prefix": "fmk_role_",
            },
            api_key="fmk_role_secret_v1",
        )
        record = issued["record"]

        self.assertEqual(record["explicit_scopes"], ("compute:plan",))
        self.assertEqual(record["roles"], ("billing", "provider-admin"))
        self.assertEqual(
            record["scopes"],
            ("compute:billing", "compute:plan", "compute:provider-admin", "compute:read"),
        )
        decision = authorize_request({"x-flow-memory-api-key": "fmk_role_secret_v1"}, ApiAuthConfig(api_key_records=(record,)))
        self.assertTrue(decision.ok, decision.reasons)
        self.assertEqual(decision.tenant_id, "tenant_role_scoped")
        self.assertEqual(
            decision.scopes,
            ("compute:billing", "compute:plan", "compute:provider-admin", "compute:read"),
        )
        public = public_api_key_record(record)
        self.assertEqual(public["roles"], ("billing", "provider-admin"))
        self.assertNotIn("key_hash", public)

    def test_api_key_inference_roles_expand_to_marketplace_scopes(self) -> None:
        issued = issue_api_key_record(
            {
                "key_id": "key_inference_roles_v1",
                "tenant_id": "tenant_inference_roles",
                "principal": "svc-inference-roles",
                "roles": ["inference-proxy", "inference-buyer", "inference-seller"],
                "key_prefix": "fmk_inf_role_",
            },
            api_key="fmk_inf_role_secret_v1",
        )
        record = issued["record"]

        self.assertEqual(record["roles"], ("inference-buyer", "inference-proxy", "inference-seller"))
        self.assertEqual(
            record["scopes"],
            ("inference:buy", "inference:proxy", "inference:read", "inference:sell"),
        )
        decision = authorize_request(
            {"x-flow-memory-api-key": "fmk_inf_role_secret_v1"},
            ApiAuthConfig(api_key_records=(record,)),
        )
        self.assertTrue(decision.ok, decision.reasons)
        self.assertEqual(decision.tenant_id, "tenant_inference_roles")
        self.assertEqual(
            decision.scopes,
            ("inference:buy", "inference:proxy", "inference:read", "inference:sell"),
        )
        self.assertTrue(is_valid_role("inference-proxy"))


    def test_api_key_config_records_can_grant_role_scopes_without_precomputed_scopes(self) -> None:
        config = ApiAuthConfig(
            api_key_records=(
                {
                    "key_id": "key_env_role",
                    "key_prefix": "fmk_env_role_",
                    "key_hash": api_key_hash("fmk_env_role_secret"),
                    "tenant_id": "tenant_env_role",
                    "principal": "svc-env-role",
                    "roles": ["auditor"],
                    "enabled": True,
                },
            )
        )

        decision = authorize_request({"x-flow-memory-api-key": "fmk_env_role_secret"}, config)

        self.assertTrue(decision.ok, decision.reasons)
        self.assertEqual(decision.tenant_id, "tenant_env_role")
        self.assertEqual(decision.scopes, ("api:audit", "compute:audit", "compute:read"))

    def test_api_key_rotation_preserves_explicit_scopes_and_recomputes_roles(self) -> None:
        issued = issue_api_key_record(
            {
                "key_id": "key_role_rotation_v1",
                "tenant_id": "tenant_role_rotation",
                "principal": "svc-role-rotation",
                "scopes": ["compute:plan"],
                "roles": ["provider-admin"],
                "key_prefix": "fmk_role_rot_",
            },
            api_key="fmk_role_rot_secret_v1",
        )
        rotated = rotate_api_key_record(
            issued["record"],
            {"key_id": "key_role_rotation_v2", "roles": ["billing"]},
            api_key="fmk_role_rot_secret_v2",
        )
        next_record = rotated["record"]

        self.assertEqual(next_record["explicit_scopes"], ("compute:plan",))
        self.assertEqual(next_record["roles"], ("billing",))
        self.assertEqual(next_record["scopes"], ("compute:billing", "compute:plan", "compute:read"))
        decision = authorize_request(
            {"x-flow-memory-api-key": "fmk_role_rot_secret_v2"},
            ApiAuthConfig(api_key_records=(rotated["previous_record"], next_record)),
        )
        self.assertTrue(decision.ok, decision.reasons)
        self.assertEqual(decision.scopes, ("compute:billing", "compute:plan", "compute:read"))
        self.assertNotIn("compute:provider-admin", decision.scopes)


    def test_api_key_record_expiration_is_enforced(self) -> None:
        now = int(time.time())
        expired = issue_api_key_record(
            {
                "key_id": "key_expired",
                "key_prefix": "fmk_expired_",
                "tenant_id": "tenant_expiry",
                "scopes": ["compute:read"],
                "expires_at_epoch": now - 1,
            },
            api_key="fmk_expired_secret",
        )
        active = issue_api_key_record(
            {
                "key_id": "key_active",
                "key_prefix": "fmk_active_",
                "tenant_id": "tenant_expiry",
                "scopes": ["compute:read"],
                "expires_in_seconds": 60,
            },
            api_key="fmk_active_secret",
        )

        expired_decision = authorize_request(
            {"x-flow-memory-api-key": "fmk_expired_secret"},
            ApiAuthConfig(api_key_records=(expired["record"],)),
        )
        active_decision = authorize_request(
            {"x-flow-memory-api-key": "fmk_active_secret"},
            ApiAuthConfig(api_key_records=(active["record"],)),
        )

        self.assertFalse(expired_decision.ok)
        self.assertIn("api key expired", expired_decision.reasons)
        self.assertTrue(active_decision.ok, active_decision.reasons)
        self.assertGreater(active["record"]["expires_at_epoch"], now)

    def test_api_key_rotation_and_disable_emit_lifecycle_audit_without_secret(self) -> None:
        router = create_default_router()

        created = router.dispatch(
            "POST",
            "/auth/api-keys",
            {
                "key_id": "key_audit_v1",
                "key_prefix": "fmk_audit_",
                "tenant_id": "tenant_audit",
                "scopes": ["compute:read"],
                "expires_in_seconds": 600,
            },
        )
        rotated = router.dispatch(
            "POST",
            "/auth/api-keys/key_audit_v1/rotate",
            {"key_id": "key_audit_v2", "reason": "scheduled_rotation"},
        )
        disabled = router.dispatch(
            "POST",
            "/auth/api-keys/key_audit_v2/disable",
            {"reason": "compromised"},
        )

        lifecycle_events = tuple(event for event in router.audit_events if str(event.get("event_type", "")).startswith("auth.api_key."))
        lifecycle_event_types = {event["event_type"] for event in lifecycle_events}
        audit_text = json.dumps(lifecycle_events, sort_keys=True)

        self.assertEqual(created["record"]["expires_at_epoch"], rotated["record"]["expires_at_epoch"])
        self.assertEqual(disabled["record"]["status"], "disabled")
        self.assertEqual(lifecycle_event_types, {"auth.api_key.created", "auth.api_key.rotated", "auth.api_key.disabled"})
        self.assertIn("key_audit_v1", audit_text)
        self.assertIn("key_audit_v2", audit_text)
        self.assertNotIn(str(created["api_key"]), audit_text)
        self.assertNotIn(str(rotated["api_key"]), audit_text)

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
        with self.assertRaisesRegex(ValueError, "unknown role"):
            issue_api_key_record(
                {
                    "key_id": "key_bad_role",
                    "tenant_id": "tenant_bad_role",
                    "roles": ["owner"],
                    "key_prefix": "fmk_bad_role_",
                },
                api_key="fmk_bad_role_secret",
            )

    def test_auth_user_workspace_and_membership_management(self) -> None:
        router = create_default_router()

        user = router.dispatch(
            "POST",
            "/auth/users",
            {"user_id": "user_alpha", "email": "ALPHA@example.com", "display_name": "Alpha", "roles": ["admin", "auditor"]},
        )
        workspace = router.dispatch(
            "POST",
            "/auth/workspaces",
            {"workspace_id": "ws_alpha", "org_name": "Alpha Org", "display_name": "Alpha Workspace"},
        )
        membership = router.dispatch("POST", "/auth/workspaces/ws_alpha/members", {"user_id": "user_alpha", "role": "auditor"})
        members = router.dispatch("GET", "/auth/workspaces/ws_alpha/members")
        updated = router.dispatch("PATCH", "/auth/users/user_alpha", {"display_name": "Alpha Admin", "roles": ["admin"]})
        removed = router.dispatch("POST", "/auth/workspaces/ws_alpha/members/user_alpha/remove", {"reason": "left"})
        disabled_user = router.dispatch("POST", "/auth/users/user_alpha/disable", {"reason": "offboarded"})
        disabled_workspace = router.dispatch("POST", "/auth/workspaces/ws_alpha/disable", {"reason": "closed"})

        self.assertEqual(user["user"]["email"], "alpha@example.com")
        self.assertEqual(user["management"], "local_in_memory")
        self.assertEqual(workspace["workspace"]["org_name"], "Alpha Org")
        self.assertEqual(membership["membership"]["role"], "auditor")
        self.assertEqual(members["members"][0]["user_id"], "user_alpha")
        self.assertEqual(updated["user"]["display_name"], "Alpha Admin")
        self.assertFalse(removed["membership"]["enabled"])
        self.assertFalse(disabled_user["user"]["enabled"])
        self.assertFalse(disabled_workspace["workspace"]["enabled"])
        self.assertNotIn("key_hash", user["user"])
        with self.assertRaisesRegex(ValueError, "already disabled"):
            router.dispatch("POST", "/auth/users/user_alpha/disable", {"reason": "again"})
        with self.assertRaisesRegex(KeyError, "Unknown workspace member"):
            router.dispatch("POST", "/auth/workspaces/ws_alpha/members/user_alpha/remove", {"reason": "again"})

    def test_auth_role_name_validation_and_scopes(self) -> None:
        self.assertEqual(validate_role_name("admin"), "admin")
        self.assertTrue(is_valid_role("provider-admin"))
        self.assertTrue(is_valid_role("settlement-admin"))
        for role in ("", "Admin", "billing manager", "unknown"):
            with self.assertRaises(ValueError):
                validate_role_name(role)

        self.assertEqual(required_scopes_for("GET", "/auth/users"), ("api:admin",))
        self.assertEqual(required_scopes_for("POST", "/auth/workspaces/ws_alpha/members"), ("api:admin",))

if __name__ == "__main__":
    unittest.main()
