"""Simulation, robotics, and physical embodiment adapter seams."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping


@dataclass(frozen=True)
class EmbodimentCommand:
    command: str
    args: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class EmbodimentResult:
    success: bool
    observation: Mapping[str, Any]
    error: str | None = None


@dataclass
class LocalEmbodimentAdapter:
    """Safe local adapter for Habitat/MineDojo/Isaac/MuJoCo-style backends."""

    backend: str = "local_simulation"

    def execute(self, command: EmbodimentCommand) -> EmbodimentResult:
        return EmbodimentResult(
            success=True,
            observation={"backend": self.backend, "command": command.command, "args": dict(command.args)},
        )


@dataclass
class LocalGridAdapter:
    """Tiny bounded grid-world adapter for embodiment tests."""

    width: int = 5
    height: int = 5
    position: tuple[int, int] = (0, 0)

    def reset(self) -> Mapping[str, Any]:
        self.position = (0, 0)
        return {"position": self.position}

    def step(self, action: Mapping[str, Any]) -> Mapping[str, Any]:
        dx = int(action.get("dx", 0))
        dy = int(action.get("dy", 0))
        x = max(0, min(self.width - 1, self.position[0] + dx))
        y = max(0, min(self.height - 1, self.position[1] + dy))
        self.position = (x, y)
        return {"position": self.position}


@dataclass
class MechanicalNeuralNetwork:
    """Proxy inspired by tunable mechanical neural networks.

    It clamps stiffness/control coefficients into a physically meaningful [0, 1] range.
    """

    def execute(self, stiffness_config: Mapping[str, Any]) -> Mapping[str, float]:
        return {
            str(key): max(0.0, min(1.0, float(value)))
            for key, value in stiffness_config.items()
        }
