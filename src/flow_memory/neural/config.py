"""Neural backend configuration."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping


SUPPORTED_BACKENDS = frozenset({"none", "tiny_torch", "vjepa2", "videomae"})


@dataclass(frozen=True)
class NeuralBackendConfig:
    backend: str = "none"
    device: str = "cpu"
    perception: str = "dual_stream"
    world_model: str = "tiny_jepa"
    plan_scorer: str = "tiny"
    checkpoint_path: str = ""
    allow_remote: bool = False
    options: Mapping[str, Any] = field(default_factory=dict)

    def validate(self) -> tuple[str, ...]:
        errors: list[str] = []
        if self.backend not in SUPPORTED_BACKENDS:
            errors.append(f"unknown neural backend: {self.backend}")
        if self.device not in {"cpu", "cuda", "mps"}:
            errors.append(f"unknown neural device: {self.device}")
        if self.checkpoint_path:
            path = Path(self.checkpoint_path)
            looks_remote = "://" in self.checkpoint_path or self.checkpoint_path.startswith("hf://")
            if looks_remote and not self.allow_remote:
                errors.append("remote checkpoint identifiers are disabled by default")
            if not looks_remote and not path.exists():
                errors.append(f"checkpoint path does not exist: {self.checkpoint_path}")
        return tuple(errors)

    def as_record(self) -> Mapping[str, Any]:
        return {
            "backend": self.backend,
            "device": self.device,
            "perception": self.perception,
            "world_model": self.world_model,
            "plan_scorer": self.plan_scorer,
            "checkpoint_path": self.checkpoint_path,
            "allow_remote": self.allow_remote,
            "options": dict(self.options),
        }


def neural_config_from_mapping(data: Mapping[str, Any] | None) -> NeuralBackendConfig:
    if not data:
        return NeuralBackendConfig()
    return NeuralBackendConfig(
        backend=str(data.get("backend", "none")),
        device=str(data.get("device", "cpu")),
        perception=str(data.get("perception", "dual_stream")),
        world_model=str(data.get("world_model", "tiny_jepa")),
        plan_scorer=str(data.get("plan_scorer", "tiny")),
        checkpoint_path=str(data.get("checkpoint_path", "")),
        allow_remote=bool(data.get("allow_remote", False)),
        options=dict(data.get("options", {})) if isinstance(data.get("options", {}), Mapping) else {},
    )
