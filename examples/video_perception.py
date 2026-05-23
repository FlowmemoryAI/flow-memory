from flow_memory.perception import DualStreamPerception

frames = [
    [[0, 0, 0], [0, 10, 0], [0, 0, 0]],
    [[0, 0, 0], [0, 0, 10], [0, 0, 0]],
    [[0, 0, 0], [0, 0, 0], [0, 10, 0]],
]

perception = DualStreamPerception().process({"frames": frames})
print(perception.summary())
print(perception.motion_geometry)
