from pathlib import Path

from flow_memory.api.manifest import API_ENDPOINTS

ROOT = Path(__file__).resolve().parents[1]


def test_public_api_uses_compute_not_squire():
    paths = {endpoint.path for endpoint in API_ENDPOINTS}

    assert any(path.startswith("/compute/") for path in paths)
    assert not any(path.startswith("/squire/") for path in paths)


def test_public_cli_and_skill_use_compute_market():
    cli = (ROOT / "src" / "flow_memory" / "cli.py").read_text(encoding="utf-8")
    skill = ROOT / "skills" / "compute-market" / "SKILL.md"

    assert "flow-memory compute" in cli
    assert skill.exists()
    assert not (ROOT / "scripts" / "squire_goal.py").exists()
    assert not (ROOT / "skills" / "squire-goal" / "SKILL.md").exists()


def test_public_docs_position_compute_market_not_squire_surface():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    compute_doc = (ROOT / "docs" / "COMPUTE_MARKET.md").read_text(encoding="utf-8")
    migration = (ROOT / "docs" / "SQUIRE_GOAL.md").read_text(encoding="utf-8")

    assert "Flow Memory Compute Market" in readme
    assert "Flow Memory Compute Market" in compute_doc
    assert "migration context" in migration.lower()
    assert "scripts/squire_goal.py" not in readme
