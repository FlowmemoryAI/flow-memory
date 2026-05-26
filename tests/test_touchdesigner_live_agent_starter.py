import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STARTER_PATH = ROOT / "tools" / "touchdesigner" / "start_live_neural_agent.py"


def load_starter():
    spec = importlib.util.spec_from_file_location("start_live_neural_agent", STARTER_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_start_live_neural_agent_payload_enables_live_learning_safely():
    starter = load_starter()
    config = starter.StarterConfig(agent_id="td-agent", backend="tiny_torch", learning_rate=0.2)
    payload = starter.build_session_payload(config)

    assert payload["agent_id"] == "td-agent"
    assert payload["config"]["enabled"] is True
    assert payload["config"]["live_mode"] is True
    assert payload["config"]["learning_enabled"] is True
    assert payload["config"]["policy_fallback"] == "allow_non_neural"
    assert payload["config"]["telemetry_enabled"] is True
    assert payload["config"]["backend"] == "tiny_torch"
    assert "settlement" not in str(payload).lower()


def test_start_live_neural_agent_step_payload_changes_with_tick():
    starter = load_starter()
    config = starter.StarterConfig(goal="Visualize memory formation")
    first = starter.build_step_payload(config, 1)
    second = starter.build_step_payload(config, 2)

    assert first["context"]["goal"] == "Visualize memory formation"
    assert first["context"]["tick"] == 1
    assert second["context"]["tick"] == 2
    assert first["context"]["phase"] != second["context"]["phase"]
    assert first["context"]["source"] == "touchdesigner-live-test"


def test_start_live_neural_agent_learning_payload_is_local_trace():
    starter = load_starter()
    config = starter.StarterConfig()
    payload = starter.build_learning_payload(config, 12)

    assert payload["sample"]["memory_trace_id"] == "td-memory-trace-0012"
    assert payload["sample"]["positive_signal"] is True
    assert "policy gates" in payload["sample"]["target"]
