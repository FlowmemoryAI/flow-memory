from flow_memory.neural.training.appearance_free_dataset import AppearanceFreeMotionDataset


def test_appearance_free_pairs_preserve_labels():
    sample = AppearanceFreeMotionDataset(size=1, seed=3)[0]
    assert sample.direction
    assert sample.trajectory
    assert len(sample.rgb) == len(sample.randomized) == len(sample.silhouette)
