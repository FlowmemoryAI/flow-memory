import json

from flow_memory.visualization import VisualAgentNode, visual_event
from flow_memory.visualization.schemas import visual_schema


def test_visual_schema_is_versioned_and_json_serializable() -> None:
    schema = visual_schema()
    assert schema["schema_version"] == "visual.telemetry.v1"
    assert "agent" in schema["event_types"]
    json.dumps(schema)


def test_visual_event_requires_valid_provenance() -> None:
    event = visual_event("agent", "did:flow:test", {"agent_id": "did:flow:test"}, provenance="live")
    assert event.as_record()["source_event_id"] == ""
    try:
        visual_event("agent", "did:flow:test", provenance="invalid")
    except ValueError as exc:
        assert "provenance" in str(exc)
    else:
        raise AssertionError("invalid provenance accepted")


def test_visual_agent_node_serializes() -> None:
    node = VisualAgentNode("did:flow:test", "Test Agent", "worker", reputation=1.5)
    assert node.as_record()["agent_id"] == "did:flow:test"
    json.dumps(node.as_record())
