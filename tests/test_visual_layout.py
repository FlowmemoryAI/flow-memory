from flow_memory.visualization.layout import apply_layout_to_state, deterministic_agent_layout


def test_visual_layout_is_deterministic_and_role_grouped():
    agents = (
        {"agent_id": "did:flow:worker", "role": "worker"},
        {"agent_id": "did:flow:requester", "role": "requester"},
        {"agent_id": "did:flow:verifier", "role": "verifier"},
    )
    first = deterministic_agent_layout(agents, seed=7).as_record()
    second = deterministic_agent_layout(tuple(reversed(agents)), seed=7).as_record()
    assert first == second
    assert first["positions"]["did:flow:requester"][0] < first["positions"]["did:flow:worker"][0]
    assert first["positions"]["did:flow:verifier"][0] > first["positions"]["did:flow:worker"][0]


def test_apply_layout_to_state_adds_positions():
    state = {"agents": ({"agent_id": "did:flow:a", "role": "agent"},)}
    positioned = apply_layout_to_state(state)
    assert positioned["agents"][0]["position"] == positioned["layout"]["positions"]["did:flow:a"]
