"""Local audit middleware wrapper that records request metadata without networking."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Mapping, MutableSequence

from flow_memory.api.errors import ApiError
from flow_memory.api.request_context import RequestContext


AuditHandler = Callable[[RequestContext, Mapping[str, Any]], Mapping[str, Any]]


@dataclass(frozen=True)
class AuditEvent:
    method: str
    path: str
    principal: str
    request_id: str
    ok: bool
    status: int
    error_code: str = ""

    def as_record(self) -> dict[str, Any]:
        return {
            "method": self.method,
            "path": self.path,
            "principal": self.principal,
            "request_id": self.request_id,
            "ok": self.ok,
            "status": self.status,
            "error_code": self.error_code,
        }


@dataclass
class LocalAuditSink:
    events: list[dict[str, Any]] = field(default_factory=list)

    def record(self, event: AuditEvent) -> None:
        self.events.append(event.as_record())

    def as_records(self) -> tuple[Mapping[str, Any], ...]:
        return tuple(dict(event) for event in self.events)


def audit_call(
    context: RequestContext,
    payload: Mapping[str, Any] | None,
    handler: AuditHandler,
    sink: LocalAuditSink | MutableSequence[Mapping[str, Any]],
) -> Mapping[str, Any]:
    try:
        result = handler(context, payload or {})
    except ApiError as exc:
        _record(sink, _event(context, ok=False, status=exc.status, error_code=exc.code))
        raise
    except Exception:
        _record(sink, _event(context, ok=False, status=500, error_code="internal.error"))
        raise
    _record(sink, _event(context, ok=True, status=200, error_code=""))
    return result


def audited(handler: AuditHandler, sink: LocalAuditSink | MutableSequence[Mapping[str, Any]]) -> AuditHandler:
    def wrapped(context: RequestContext, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        return audit_call(context, payload, handler, sink)

    return wrapped


def _event(context: RequestContext, *, ok: bool, status: int, error_code: str) -> AuditEvent:
    return AuditEvent(
        method=context.method,
        path=context.path,
        principal=context.principal,
        request_id=context.request_id,
        ok=ok,
        status=status,
        error_code=error_code,
    )


def _record(sink: LocalAuditSink | MutableSequence[Mapping[str, Any]], event: AuditEvent) -> None:
    if isinstance(sink, LocalAuditSink):
        sink.record(event)
        return
    sink.append(event.as_record())
