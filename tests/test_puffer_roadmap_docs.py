from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_puffer_plan_keeps_puffer_optional_and_non_vendored():
    text = (ROOT / "experiments" / "pufferlib" / "FLOW_ARENA_TO_PUFFER_PLAN.md").read_text(encoding="utf-8")
    assert "not installed, vendored, or required" in text
    assert "No PufferLib performance claims" in text
    assert "RL policy outputs remain suggestions" in text


def test_native_backend_roadmap_preserves_safety_authority():
    text = (ROOT / "docs" / "FLOW_ARENA_NATIVE_BACKEND_ROADMAP.md").read_text(encoding="utf-8")
    assert "PolicyEngine" in text
    assert "ApprovalGate" in text
    assert "Public alpha does not include PufferLib-level throughput" in text
