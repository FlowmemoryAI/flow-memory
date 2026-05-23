"""Dependency-free local API surface."""

from flow_memory.api.manifest import API_ENDPOINTS, EndpointSpec, endpoint_manifest
from flow_memory.api.router import LocalApiRouter, create_default_router
from flow_memory.api.snapshot import api_snapshot, validate_api_snapshot

__all__ = [
    "API_ENDPOINTS",
    "EndpointSpec",
    "LocalApiRouter",
    "api_snapshot",
    "create_default_router",
    "endpoint_manifest",
    "validate_api_snapshot",
]
