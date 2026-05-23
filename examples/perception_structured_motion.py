from flow_memory.perception import DualStreamPerception

observation = {
    "modality": "video",
    "objects": [
        {"id": "cube", "label": "Cube", "positions": [(0, 0), (1, 0), (2, 1)]},
        {"id": "sphere", "label": "Sphere", "positions": [(4, 4), (4, 3), (4, 2)]},
    ],
}

perception = DualStreamPerception().process(observation)
print(perception.motion_geometry)
