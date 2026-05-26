import unittest

from flow_memory.api.request_context import build_request_context
from flow_memory.api.scopes import (
    ADMIN_SCOPE,
    AUDIT_SCOPE,
    READ_SCOPE,
    WRITE_SCOPE,
    context_from_headers,
    parse_scope_header,
    require_scopes,
    required_scopes_for,
)


class ApiScopeTests(unittest.TestCase):
    def test_scope_header_accepts_space_and_comma_separated_values(self) -> None:
        self.assertEqual(parse_scope_header("api:write, api:read api:write"), (READ_SCOPE, WRITE_SCOPE))

    def test_required_scope_allows_granted_scope(self) -> None:
        context = build_request_context("POST", "/agents/a/run", scopes=(WRITE_SCOPE,))
        decision = require_scopes(context, (WRITE_SCOPE,))

        self.assertTrue(decision.ok)
        self.assertEqual(decision.missing, ())

    def test_admin_scope_satisfies_required_scope(self) -> None:
        context = build_request_context("POST", "/agents/a/run", scopes=(ADMIN_SCOPE,))
        decision = require_scopes(context, (WRITE_SCOPE,))

        self.assertTrue(decision.ok)


    def test_default_scope_model_maps_read_write_and_audit_routes(self) -> None:
        self.assertEqual(required_scopes_for("GET", "/agents"), (READ_SCOPE,))
        self.assertEqual(required_scopes_for("POST", "/agents/a/run"), (WRITE_SCOPE,))
        self.assertEqual(required_scopes_for("GET", "/audit"), (AUDIT_SCOPE,))

        context = build_request_context("GET", "/agents", scopes=(READ_SCOPE,))
        self.assertTrue(require_scopes(context).ok)

    def test_missing_scope_returns_forbidden_error(self) -> None:
        context = build_request_context("POST", "/agents/a/run", scopes=(READ_SCOPE,))
        decision = require_scopes(context, (WRITE_SCOPE,))

        self.assertFalse(decision.ok)
        self.assertEqual(decision.missing, (WRITE_SCOPE,))
        error = decision.error
        self.assertIsNotNone(error)
        assert error is not None
        self.assertEqual(error.status, 403)
        self.assertEqual(error.code, "auth.forbidden")

    def test_invalid_scope_returns_auth_error(self) -> None:
        context = build_request_context("GET", "/agents", scopes=("unknown", READ_SCOPE))
        decision = require_scopes(context, (READ_SCOPE,))

        self.assertFalse(decision.ok)
        self.assertEqual(decision.invalid, ("unknown",))
        error = decision.error
        self.assertIsNotNone(error)
        assert error is not None
        self.assertEqual(error.status, 401)
        self.assertEqual(error.code, "auth.invalid_scope")

    def test_context_from_headers_extracts_scopes(self) -> None:
        context = context_from_headers("GET", "agents", {"X-Flow-Memory-Scopes": "api:read"})

        self.assertEqual(context.path, "/agents")
        self.assertEqual(context.scopes, (READ_SCOPE,))


if __name__ == "__main__":
    unittest.main()
