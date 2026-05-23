"""Embodiment adapters."""

from flow_memory.embodiment.adapters import EmbodimentCommand, EmbodimentResult, LocalEmbodimentAdapter, LocalGridAdapter
from flow_memory.embodiment.mechanical import MechanicalNeuralNetwork, TunableStiffness

__all__ = [
    "EmbodimentCommand",
    "EmbodimentResult",
    "LocalEmbodimentAdapter",
    "LocalGridAdapter",
    "MechanicalNeuralNetwork",
    "TunableStiffness",
]
