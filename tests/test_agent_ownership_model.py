from flow_memory.economy.agent_ownership import AgentOwnership, AgentOwnershipRegistry


def test_agent_ownership_permissions() -> None:
    ownership = AgentOwnership("agent-1", "owner-1", operator_id="operator-1", governance_id="dao-1")
    assert ownership.can_request_payment("owner-1") is True
    assert ownership.can_request_payment("operator-1") is True
    assert ownership.can_change_policy("dao-1") is True
    assert ownership.can_change_policy("operator-1") is False


def test_agent_ownership_registry() -> None:
    registry = AgentOwnershipRegistry()
    registry.register(AgentOwnership("agent-1", "owner-1"))
    assert registry.owner_of("agent-1") == "owner-1"
    assert registry.as_record()["ownership"][0]["agent_id"] == "agent-1"
