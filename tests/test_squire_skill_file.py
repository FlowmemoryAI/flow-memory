from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_squire_goal_skill_manifest_is_front_loaded():
    text = (ROOT / "skills" / "squire-goal" / "SKILL.md").read_text(encoding="utf-8")

    assert "name: squire-goal" in text
    description_line = next(line for line in text.splitlines() if line.startswith("description:"))
    for token in ("SQUIRE", "Level5", "UsePod", "Solana", "budget", "routing", "402", "MPP", "provider", "marketplace"):
        assert token in description_line
    assert "Never fabricate balances" in text
    assert "phase alpha = treasury + proxy integration" in text
    assert "hard enforcement belongs in Flow Memory policy" in text
