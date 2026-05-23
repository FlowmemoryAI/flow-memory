"""Dual-stream perception composition."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from flow_memory.core.types import Observation, PerceptionOutput
from flow_memory.perception.dorsal_stream import DorsalStream
from flow_memory.perception.foveation import FoveatedAttention
from flow_memory.perception.ventral_stream import VentralStreamEncoder


@dataclass
class DualStreamPerception:
    ventral: VentralStreamEncoder = field(default_factory=VentralStreamEncoder)
    dorsal: DorsalStream = field(default_factory=DorsalStream)
    foveation: FoveatedAttention = field(default_factory=FoveatedAttention)

    def process(self, observation: Observation | str | Mapping[str, Any]) -> PerceptionOutput:
        if isinstance(observation, str):
            observation = Observation(content=observation)
        elif isinstance(observation, Mapping):
            modality = str(observation.get("modality") or ("video" if "frames" in observation or "video" in observation else "structured"))
            observation = Observation(content=observation, modality=modality)
        foveated = self.foveation.apply(observation)
        entities = self.ventral.encode(observation)
        motion_geometry = self.dorsal.encode(observation)
        salience = {entity.label: round(entity.confidence * self.foveation.center_weight, 4) for entity in entities}
        latent_state = {"modality": observation.modality, "entity_count": len(entities), "motion_confidence": motion_geometry.confidence, "foveation": foveated, "stream_contract": "ventral_semantics+dorsal_motion_geometry"}
        return PerceptionOutput(entities=entities, motion_geometry=motion_geometry, salience=salience, latent_state=latent_state)
