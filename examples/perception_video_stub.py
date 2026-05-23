from flow_memory.perception import DualStreamPerception

# Two tiny numeric frames; the local dorsal stream uses a frame-delta proxy.
video = {
    "modality": "video",
    "frames": [
        [[0, 0], [0, 1]],
        [[0, 1], [1, 1]],
        [[1, 1], [1, 2]],
    ],
    "objects": ["agent", "target"],
    "text": "agent moving toward target",
}

output = DualStreamPerception().process(video)
print(output.summary())
print(output.motion_geometry)
