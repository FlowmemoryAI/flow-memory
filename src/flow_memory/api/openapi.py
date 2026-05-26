"""Minimal OpenAPI document generation for the local endpoint manifest."""
from __future__ import annotations

from collections.abc import Iterable
from typing import Mapping

from flow_memory.api.manifest import API_ENDPOINTS


def openapi_schema() -> Mapping[str, object]:
    paths: dict[str, object] = {}
    for endpoint in API_ENDPOINTS:
        path_item = paths.setdefault(endpoint.path, {})
        assert isinstance(path_item, dict)
        operation: dict[str, object] = {
            "operationId": endpoint.name,
            "summary": endpoint.description,
            "tags": [_tag_for_path(endpoint.path)],
            "responses": {
                "200": {
                    "description": "Local response",
                    "content": {"application/json": {"schema": _object_schema(endpoint.response_fields)}},
                }
            },
        }
        parameters = _path_parameters(endpoint.path)
        if parameters:
            operation["parameters"] = parameters
        if endpoint.request_fields and endpoint.method.upper() not in {"GET", "DELETE"}:
            operation["requestBody"] = {
                "required": True,
                "content": {"application/json": {"schema": _object_schema(endpoint.request_fields)}},
            }
        path_item[endpoint.method.lower()] = operation
    return {"openapi": "3.1.0", "info": {"title": "Flow Memory Local API", "version": "0.3.0"}, "paths": paths}


def _object_schema(fields: object) -> Mapping[str, object]:
    field_names: tuple[str, ...]
    if fields is None:
        field_names = ()
    elif isinstance(fields, str):
        field_names = (fields,)
    elif isinstance(fields, Iterable):
        field_names = tuple(str(item) for item in fields)
    else:
        field_names = (str(fields),)
    properties: dict[str, Mapping[str, str]] = {field: {"type": "string"} for field in field_names}
    schema: dict[str, object] = {"type": "object", "additionalProperties": True}
    if properties:
        schema["properties"] = properties
    return schema


def _path_parameters(path: str) -> list[Mapping[str, object]]:
    parameters: list[Mapping[str, object]] = []
    for segment in path.split("/"):
        if segment.startswith("{") and segment.endswith("}"):
            name = segment[1:-1]
            parameters.append({"name": name, "in": "path", "required": True, "schema": {"type": "string"}})
    return parameters


def _tag_for_path(path: str) -> str:
    parts = [part for part in path.split("/") if part]
    return parts[0] if parts else "root"
