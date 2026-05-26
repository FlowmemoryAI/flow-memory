from pathlib import Path

from flow_memory.neural.artifacts import safe_member_name, sha256_file

def test_safe_member_name_rejects_weights_and_traversal(tmp_path: Path) -> None:
    file=tmp_path/"gpu_info.txt"
    file.write_text("gpu: test")
    assert len(sha256_file(file)) == 64
    assert safe_member_name("nested/gpu_info.txt")
    assert not safe_member_name("../secret.txt")
    assert not safe_member_name("model.safetensors")
