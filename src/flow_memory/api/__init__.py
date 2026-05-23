"""Dependency-free local API surface."""

from flow_memory.api.manifest import API_ENDPOINTS, EndpointSpec, endpoint_manifest
from flow_memory.api.router import LocalApiRouter, create_default_router

__all__ = ["API_ENDPOINTS", "EndpointSpec", "LocalApiRouter", "create_default_router", "endpoint_manifest"]
