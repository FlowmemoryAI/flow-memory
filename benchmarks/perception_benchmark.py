"""Minimal benchmark scaffold for dorsal-stream invariance regression checks."""

from __future__ import annotations

from flow_memory.core.types import Observation
from flow_memory.perception import DualStreamPerception


def run() -> dict[str, float]:
    perception = DualStreamPerception()
    text = perception.process("Track moving dots without texture and infer motion geometry")
    frames = perception.process(
        Observation(
            content={"frames": [[[0, 0, 0]], [[0, 1, 0]], [[0, 0, 1]]]},
            modality="video",
        )
    )
    return {
        "text_motion_confidence": text.motion_geometry.confidence,
        "frame_motion_confidence": frames.motion_geometry.confidence,
        "invariance_count": float(len(frames.motion_geometry.invariances)),
    }


if __name__ == "__main__":
    print(run())
