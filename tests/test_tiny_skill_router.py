from flow_memory.neural.agent.skill_router import TinySkillRouter


def test_tiny_skill_router_uses_capability_history_reputation() -> None:
    scores = TinySkillRouter().rank_skills("research brief", ({"id": "research-brief", "description": "research brief", "risk": 0.1}, {"id": "other", "description": "settlement", "risk": 0.5}), history={"research-brief": 1.0}, reputation={"research-brief": 1.0})
    assert scores[0].skill_id == "research-brief"
