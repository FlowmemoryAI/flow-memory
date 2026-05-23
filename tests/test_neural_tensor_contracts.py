import pytest

from flow_memory.neural.features import VideoTensorSpec
from flow_memory.neural.tensor_types import validate_video_tensor


def test_video_tensor_spec_from_nested_list():
    video = [[[[[0.0 for _ in range(4)] for _ in range(4)] for _ in range(3)] for _ in range(2)] for _ in range(1)]
    assert validate_video_tensor(video) == ()
    spec = VideoTensorSpec.from_value(video)
    assert spec.as_record()["frames"] == 2


def test_invalid_video_shape_rejected():
    with pytest.raises(ValueError):
        VideoTensorSpec.from_value([[0.0]])
