"""Request context primitives for dependency-free API tests and local tools."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(frozen=True)
class RequestContext:
    method: str
    path: str
    request_id: str = ""
    principal: str = "anonymous"
    scopes: tuple[str, ...] = ()
    client_id: str = "local"
    tenant_id: str = ""
    workspace_id: str = ""

    def as_record(self) -> dict[str, Any]:
        return {
            "method": self.method,
            "path": self.path,
            "request_id": self.request_id,
            "principal": self.principal,
            "scopes": self.scopes,
            "client_id": self.client_id,
            "tenant_id": self.tenant_id,
            "workspace_id": self.workspace_id,
        }


def build_request_context(
    method: str,
    path: str,
    headers: Mapping[str, str] | None = None,
    *,
    request_id: str = "",
    principal: str = "",
    scopes: tuple[str, ...] = (),
    client_id: str = "",
    tenant_id: str = "",
    workspace_id: str = "",
) -> RequestContext:
    header_map = headers or {}
    resolved_request_id = request_id or _header(header_map, "x-request-id")
    resolved_principal = principal or _header(header_map, "x-flow-memory-principal") or "anonymous"
    resolved_client = client_id or _header(header_map, "x-flow-memory-client") or "local"
    resolved_tenant = tenant_id or _header(header_map, "x-flow-memory-tenant")
    resolved_workspace = workspace_id or _header(header_map, "x-flow-memory-workspace")
    return RequestContext(
        method=method.upper(),
        path=_normalize_path(path),
        request_id=resolved_request_id,
        principal=resolved_principal,
        scopes=tuple(sorted(set(scopes))),
        client_id=resolved_client,
        tenant_id=resolved_tenant,
        workspace_id=resolved_workspace,
    )


def _header(headers: Mapping[str, str], name: str) -> str:
    lowered = name.lower()
    for key, value in headers.items():
        if key.lower() == lowered:
            return value.strip()
    return ""


def _normalize_path(path: str) -> str:
    if not path:
        return "/"
    normalized = path if path.startswith("/") else f"/{path}"
    return normalized.rstrip("/") or "/"
