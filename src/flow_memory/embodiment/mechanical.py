"""Physical embodiment inspiration layer."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping


@dataclass
class TunableStiffness:
    values: dict[str, float] = field(default_factory=dict)

    def set_stiffness(self, config: Mapping[str, float]) -> None:
        for key, value in config.items():
            self.values[key] = max(0.0, min(1.0, float(value)))


@dataclass
class MechanicalNeuralNetwork:
    """Local proxy for material-control policies."""

    material_properties: TunableStiffness = field(default_factory=TunableStiffness)

    def execute(self, command: Mapping[str, float]) -> Mapping[str, float]:
        self.material_properties.set_stiffness(command)
        return dict(self.material_properties.values)
