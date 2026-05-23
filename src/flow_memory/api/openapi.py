"""Minimal OpenAPI document generation for the local endpoint manifest."""
from __future__ import annotations

from typing import Mapping

from flow_memory.api.manifest import API_ENDPOINTS


def openapi_schema() -> Mapping[str, object]:
    paths: dict[str, object] = {}
    for endpoint in API_ENDPOINTS:
        path_item = paths.setdefault(endpoint.path, {})
        assert isinstance(path_item, dict)
        path_item[endpoint.method.lower()] = {
            "operationId": endpoint.name,
            "summary": endpoint.description,
            "responses": {"200": {"description": "Local response"}},
        }
    return {"openapi": "3.1.0", "info": {"title": "Flow Memory Local API", "version": "0.3.0"}, "paths": paths}
