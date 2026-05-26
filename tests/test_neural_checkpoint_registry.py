from pathlib import Path

import pytest

from flow_memory.neural.checkpoints import CheckpointRegistry


def test_checkpoint_registry_local_only(tmp_path: Path) -> None:
    checkpoint = tmp_path / "model.pt"
    checkpoint.write_text("stub", encoding="utf-8")
    registry = CheckpointRegistry()
    ref = registry.register("tiny", str(checkpoint))
    assert registry.resolve("tiny") == ref
    assert ref.exists()
    with pytest.raises(ValueError):
        registry.register("remote", "https://example.com/model.pt")
