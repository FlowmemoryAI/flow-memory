"""Sandbox backend selection helpers."""

from __future__ import annotations

from dataclasses import dataclass

from flow_memory.action.container_sandbox import ContainerSandbox
from flow_memory.action.docker_sandbox import DockerSandbox, DockerSandboxConfig, docker_available


@dataclass(frozen=True)
class SandboxBackendSelection:
    backend: str
    reason: str

    def as_record(self) -> dict[str, object]:
        return {"backend": self.backend, "reason": self.reason}


def select_sandbox_backend(prefer_docker: bool = False, *, docker_enabled: bool = False):
    if prefer_docker and docker_enabled and docker_available():
        return DockerSandbox(DockerSandboxConfig(enabled=True))
    return ContainerSandbox(enabled=False)


def describe_sandbox_backend(prefer_docker: bool = False, *, docker_enabled: bool = False) -> SandboxBackendSelection:
    if prefer_docker and not docker_enabled:
        return SandboxBackendSelection("container-seam", "docker requested but not explicitly enabled")
    if prefer_docker and docker_enabled and not docker_available():
        return SandboxBackendSelection("container-seam", "docker executable unavailable")
    if prefer_docker and docker_enabled:
        return SandboxBackendSelection("docker", "docker backend available and explicitly enabled")
    return SandboxBackendSelection("container-seam", "local/container seam remains default")
