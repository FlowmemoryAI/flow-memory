import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LAUNCHER_PATH = ROOT / "tools" / "touchdesigner" / "run_touchdesigner_live_stack.py"


def load_launcher():
    spec = importlib.util.spec_from_file_location("run_touchdesigner_live_stack", LAUNCHER_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_live_stack_builds_three_local_commands():
    launcher = load_launcher()
    config = launcher.StackConfig(ticks=12, interval=0.1, udp_port=7010, show_bridge_frames=True)

    api = launcher.api_server_command(config)
    bridge = launcher.bridge_command(config)
    agent = launcher.agent_command(config)

    assert api[1].endswith("scripts\\run_local_api_server.py") or api[1].endswith("scripts/run_local_api_server.py")
    assert "--port" in api
    assert "8766" in api
    assert bridge[1].endswith("flowmemory_td_bridge.py")
    assert "--stdout" in bridge
    assert "--udp-port" in bridge
    assert "7010" in bridge
    assert agent[1].endswith("start_live_neural_agent.py")
    assert "--ticks" in agent
    assert "12" in agent
    assert "--interval" in agent
    assert "0.1" in agent


def test_live_stack_dry_run_exits_without_starting_processes(capsys):
    launcher = load_launcher()
    code = launcher.run_stack(launcher.StackConfig(dry_run=True, ticks=3))

    captured = capsys.readouterr()
    assert code == 0
    assert "Dry run commands" in captured.out
    assert "flowmemory_td_bridge.py" in captured.out
    assert "start_live_neural_agent.py" in captured.out
    assert "create_flowmemory_neural_loom.py" in captured.out


def test_live_stack_rejects_invalid_ports():
    launcher = load_launcher()
    try:
        launcher.parse_args(["--api-port", "70000"])
    except ValueError as exc:
        assert "api-port" in str(exc)
    else:
        raise AssertionError("invalid port accepted")
