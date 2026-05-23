import unittest
from typing import Mapping

from flow_memory.api.audit_middleware import LocalAuditSink, audit_call, audited
from flow_memory.api.errors import ApiError
from flow_memory.api.request_context import RequestContext, build_request_context


class ApiAuditMiddlewareTests(unittest.TestCase):
    def test_audit_call_records_success_metadata(self) -> None:
        sink = LocalAuditSink()
        context = build_request_context(
            "POST",
            "/agents/a/run",
            request_id="req-1",
            principal="alice",
            client_id="test",
        )

        def handler(received_context: RequestContext, payload: Mapping[str, object]) -> Mapping[str, object]:
            return {"principal": received_context.principal, "goal": payload["goal"]}

        result = audit_call(context, {"goal": "local"}, handler, sink)

        self.assertEqual(result, {"principal": "alice", "goal": "local"})
        self.assertEqual(
            sink.events,
            [
                {
                    "method": "POST",
                    "path": "/agents/a/run",
                    "principal": "alice",
                    "request_id": "req-1",
                    "ok": True,
                    "status": 200,
                    "error_code": "",
                }
            ],
        )

    def test_audit_call_records_api_error_then_reraises(self) -> None:
        sink = LocalAuditSink()
        context = build_request_context("GET", "/agents", request_id="req-2", principal="alice")

        def handler(_context: RequestContext, _payload: Mapping[str, object]) -> Mapping[str, object]:
            raise ApiError(code="auth.forbidden", message="Missing required API scope", status=403)

        with self.assertRaises(ApiError):
            audit_call(context, {}, handler, sink)

        self.assertEqual(sink.events[0]["ok"], False)
        self.assertEqual(sink.events[0]["status"], 403)
        self.assertEqual(sink.events[0]["error_code"], "auth.forbidden")

    def test_audited_wrapper_emits_to_plain_list_sink(self) -> None:
        events: list[Mapping[str, object]] = []
        context = build_request_context("GET", "/health", request_id="req-3")

        def handler(_context: RequestContext, _payload: Mapping[str, object]) -> Mapping[str, object]:
            return {"ok": True}

        wrapped = audited(handler, events)
        self.assertEqual(wrapped(context, {}), {"ok": True})
        self.assertEqual(events[0]["path"], "/health")
        self.assertEqual(events[0]["ok"], True)


if __name__ == "__main__":
    unittest.main()
