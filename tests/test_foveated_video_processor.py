from flow_memory.neural.perception.foveation import FoveatedVideoProcessor


def test_foveated_video_processor_lists():
    video = [[[[[0.0 for _ in range(8)] for _ in range(8)] for _ in range(3)] for _ in range(2)] for _ in range(1)]
    result = FoveatedVideoProcessor(center_fraction=0.5, peripheral_stride=2).process(video)
    assert result.as_record()["center_shape"] == (1, 2, 3, 4, 4)
    assert result.as_record()["peripheral_shape"] == (1, 2, 3, 4, 4)
