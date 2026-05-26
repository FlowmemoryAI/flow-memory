import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BRIDGE_PATH = ROOT / "tools" / "touchdesigner" / "flowmemory_td_bridge.py"


def load_bridge():
    spec = importlib.util.spec_from_file_location("flowmemory_td_bridge", BRIDGE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_touchdesigner_bridge_frame_exposes_live_learning_metrics():
    bridge = load_bridge()
    frame = bridge.build_touchdesigner_frame(
        seq=7,
        source="live_api",
        connected=True,
        timestamp=123.0,
        max_events=2,
        state={
            "agents": [
                {"agent_id": "did:flow:worker", "label": "Worker", "role": "worker", "status": "learning", "reputation": 7.2, "position": [0, 1, 2]},
                {"agent_id": "did:flow:verifier", "label": "Verifier", "role": "verifier", "status": "idle", "reputation": 8.4, "position": [3, 4, 5]},
            ],
            "runtime": {"events": 9, "agents": 2},
            "neural": [{"learning_tick_count": 1, "memory_activation_count": 3, "prediction_confidence": 0.61, "risk_score": 0.32}],
        },
        events=[
            {"event_id": "e1", "event_type": "agent", "source": "did:flow:worker"},
            {"event_id": "e2", "event_type": "neural", "source": "did:flow:worker"},
            {"event_id": "e3", "event_type": "memory", "source": "did:flow:worker"},
        ],
        sessions=[
            {
                "session_id": "neural_session_live",
                "agent_id": "did:flow:worker",
                "status": "ok",
                "step_count": 5,
                "learning_tick_count": 4,
                "last_record": {
                    "phase": "learning",
                    "memory_activation_count": 11,
                    "prediction_confidence": 0.82,
                    "risk_score": 0.18,
                },
            }
        ],
        neural_status={"ok": True},
    )

    assert frame["kind"] == "flowmemory.telemetry.frame"
    assert frame["read_only"] is True
    assert frame["connected"] is True
    assert frame["seq"] == 7
    assert frame["metrics"]["agent_count"] == 2
    assert frame["metrics"]["event_count"] == 3
    assert frame["metrics"]["memory_activation_count"] == 11
    assert frame["metrics"]["learning_tick_count"] == 4
    assert frame["metrics"]["step_count"] == 5
    assert frame["metrics"]["confidence"] == 0.82
    assert frame["metrics"]["risk"] == 0.18
    assert frame["events"][0]["id"] == "e2"
    assert frame["events"][1]["id"] == "e3"
    assert frame["neural_sessions"][0]["phase"] == "learning"
    json.dumps(frame)


def test_touchdesigner_bridge_read_only_endpoint_contract():
    bridge = load_bridge()
    assert bridge.READ_ONLY_ENDPOINTS == (
        "/visual/state",
        "/visual/events",
        "/neural/live/sessions",
        "/neural/status",
    )
    unsafe_terms = ("/start", "/stop", "/learn", "/step", "/settle", "/launch", "/run")
    assert not any(term in endpoint for endpoint in bridge.READ_ONLY_ENDPOINTS for term in unsafe_terms)


def test_touchdesigner_bridge_replay_fallback_has_neural_signal():
    bridge = load_bridge()
    config = bridge.BridgeConfig()
    state, events, sessions, neural_status = bridge.read_replay_snapshot(config)
    frame = bridge.build_touchdesigner_frame(
        seq=0,
        source="replay_fallback",
        connected=False,
        state=state,
        events=events,
        sessions=sessions,
        neural_status=neural_status,
        timestamp=0.0,
    )

    assert frame["connected"] is False
    assert frame["source"] == "replay_fallback"
    assert frame["metrics"]["memory_activation_count"] > 0
    assert frame["metrics"]["learning_tick_count"] > 0
    assert frame["metrics"]["signal"] > 0
