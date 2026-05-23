"""Structured dual-stream perception example."""

from flow_memory.perception import DualStreamPerception

observation = {
    "entities": [{"label": "robot", "confidence": 0.92}, {"label": "box", "confidence": 0.88}],
    "motion_cues": ["approach", "grasp"],
    "motion_vectors": [(0.1, 0.0), (0.2, 0.0)],
    "depth_cues": ["box_nearer"],
    "egomotion": {"dx": 0.1, "dy": 0.0},
    "affordances": ["manipulate", "navigate"],
}

print(DualStreamPerception().process(observation).summary())
