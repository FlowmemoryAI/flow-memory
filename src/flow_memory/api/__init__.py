"""Dependency-free local API surface."""

from flow_memory.api.manifest import API_ENDPOINTS, EndpointSpec, endpoint_manifest
from flow_memory.api.http_server import HttpApiConfig, HttpApiGateway, HttpApiResponse, create_http_server
from flow_memory.api.router import LocalApiRouter, create_default_router
from flow_memory.api.snapshot import api_snapshot, validate_api_snapshot

__all__ = [
    "API_ENDPOINTS",
    "EndpointSpec",
    "HttpApiConfig",
    "HttpApiGateway",
    "HttpApiResponse",
    "LocalApiRouter",
    "api_snapshot",
    "create_default_router",
    "create_http_server",
    "endpoint_manifest",
    "validate_api_snapshot",
]
