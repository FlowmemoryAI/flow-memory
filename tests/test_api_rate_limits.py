import unittest

from flow_memory.api.rate_limits import LocalRateLimiter, RateLimitRule
from flow_memory.api.request_context import build_request_context


class ApiRateLimitTests(unittest.TestCase):
    def test_allows_requests_until_limit(self) -> None:
        limiter = LocalRateLimiter(RateLimitRule(limit=2, window_seconds=60))
        context = build_request_context("GET", "/agents", principal="alice", client_id="test")

        first = limiter.check(context, now=10)
        second = limiter.check(context, now=20)

        self.assertTrue(first.ok)
        self.assertEqual(first.remaining, 1)
        self.assertTrue(second.ok)
        self.assertEqual(second.remaining, 0)

    def test_limit_exceeded_returns_structured_error(self) -> None:
        limiter = LocalRateLimiter(RateLimitRule(limit=1, window_seconds=60))
        context = build_request_context("GET", "/agents", principal="alice", client_id="test")

        self.assertTrue(limiter.check(context, now=10).ok)
        denied = limiter.check(context, now=11)

        self.assertFalse(denied.ok)
        self.assertEqual(denied.remaining, 0)
        self.assertEqual(denied.reset_at, 60)
        error = denied.error
        self.assertIsNotNone(error)
        assert error is not None
        self.assertEqual(error.status, 429)
        self.assertEqual(error.code, "rate_limit.exceeded")

    def test_tenants_have_isolated_rate_limit_buckets(self) -> None:
        limiter = LocalRateLimiter(RateLimitRule(limit=1, window_seconds=60))
        tenant_a = build_request_context("GET", "/agents", principal="alice", client_id="test", tenant_id="tenant_a")
        tenant_b = build_request_context("GET", "/agents", principal="alice", client_id="test", tenant_id="tenant_b")

        first_a = limiter.check(tenant_a, now=10)
        second_a = limiter.check(tenant_a, now=11)
        first_b = limiter.check(tenant_b, now=12)

        self.assertTrue(first_a.ok)
        self.assertFalse(second_a.ok)
        self.assertTrue(first_b.ok)
        self.assertNotEqual(first_a.key, first_b.key)

    def test_new_window_resets_count(self) -> None:
        limiter = LocalRateLimiter(RateLimitRule(limit=1, window_seconds=60))
        context = build_request_context("GET", "/agents", principal="alice", client_id="test")

        self.assertTrue(limiter.check(context, now=59).ok)
        self.assertTrue(limiter.check(context, now=60).ok)

    def test_route_rule_overrides_default_rule(self) -> None:
        limiter = LocalRateLimiter(
            RateLimitRule(limit=10, window_seconds=60),
            route_rules={"/agents": RateLimitRule(limit=1, window_seconds=30)},
        )
        context = build_request_context("GET", "/agents", principal="alice", client_id="test")

        self.assertTrue(limiter.check(context, now=1).ok)
        self.assertFalse(limiter.check(context, now=2).ok)


if __name__ == "__main__":
    unittest.main()
