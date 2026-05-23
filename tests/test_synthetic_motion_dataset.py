from flow_memory.neural.training.synthetic_motion_dataset import SyntheticMotionDataset


def test_synthetic_motion_dataset_deterministic():
    a = SyntheticMotionDataset(size=2, seed=7)[0]
    b = SyntheticMotionDataset(size=2, seed=7)[0]
    assert a.direction == b.direction
    assert a.trajectory == b.trajectory
    assert a.as_record()["shape"] == (6, 3, 16, 16)
