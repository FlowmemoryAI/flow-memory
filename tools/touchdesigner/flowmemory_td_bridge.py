"""Read-only Flow Memory telemetry bridge for TouchDesigner.

This process polls the local Flow Memory API or a replay artifact and sends compact
newline-delimited JSON frames to TouchDesigner over UDP. In TouchDesigner, add a
UDP In DAT on the same port with Row/Callback Format set to One Per Line, then
feed it into a JSON DAT.

Default data path is intentionally read-only: only GET requests are issued. It
never starts agents, advances neural sessions, moves funds, or writes control
endpoints.
"""
from __future__ import annotations

import argparse
import json
import socket
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping
from urllib.error import URLError
from urllib.request import ProxyHandler, Request, build_opener

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_API = "http://127.0.0.1:8765"
DEFAULT_REPLAY = ROOT / "dashboard" / "src" / "mock-data" / "live-neural-embodiment.json"
DEFAULT_NETWORK_REPLAY = ROOT / "dashboard" / "src" / "mock-data" / "local-network-replay.json"
READ_ONLY_ENDPOINTS = (
    "/visual/state",
    "/visual/events",
    "/neural/live/sessions",
    "/neural/status",
)

LOCAL_OPENER = build_opener(ProxyHandler({}))


@dataclass(frozen=True)
class BridgeConfig:
    api: str = DEFAULT_API
    replay: Path = DEFAULT_REPLAY
    network_replay: Path = DEFAULT_NETWORK_REPLAY
    udp_host: str = "127.0.0.1"
    udp_port: int = 7000
    interval: float = 0.25
    timeout: float = 0.75
    max_events: int = 12
    once: bool = False
    stdout: bool = False


def api_get(base_url: str, path: str, *, timeout: float) -> Mapping[str, Any]:
    """Fetch a local API route and unwrap the router envelope."""
    url = f"{base_url.rstrip('/')}{path}"
    request = Request(url, method="GET", headers={"accept": "application/json"})
    with LOCAL_OPENER.open(request, timeout=timeout) as response:  # noqa: S310 - local operator API only
        payload = json.loads(response.read().decode("utf-8"))
    if not isinstance(payload, Mapping):
        raise ValueError(f"API returned non-object payload for {path}")
    data = payload.get("data")
    return data if isinstance(data, Mapping) else payload


def read_live_snapshot(config: BridgeConfig) -> tuple[dict[str, Any], list[Mapping[str, Any]], list[Mapping[str, Any]], Mapping[str, Any]]:
    """Read live local telemetry. Only GET endpoints are touched."""
    state_payload = api_get(config.api, "/visual/state", timeout=config.timeout)
    events_payload = api_get(config.api, "/visual/events", timeout=config.timeout)
    sessions_payload = api_get(config.api, "/neural/live/sessions", timeout=config.timeout)
    neural_status = api_get(config.api, "/neural/status", timeout=config.timeout)
    state = _mapping(state_payload.get("state"))
    events = list(_sequence(events_payload.get("events")))
    sessions = [_mapping(item) for item in _sequence(sessions_payload.get("sessions"))]
    return state, events, sessions, neural_status


def read_replay_snapshot(config: BridgeConfig) -> tuple[dict[str, Any], list[Mapping[str, Any]], list[Mapping[str, Any]], Mapping[str, Any]]:
    """Read deterministic replay telemetry when the local API is not running."""
    replay = _read_json(config.replay)
    network = _read_json(config.network_replay) if config.network_replay.exists() else {}

    state = _mapping(network.get("state"))
    events = list(_sequence(replay.get("events"))) or list(_sequence(network.get("events")))
    embodiment = _mapping(replay.get("embodiment"))
    session = {
        "session_id": embodiment.get("session_id", "replay-session"),
        "agent_id": embodiment.get("agent_id", "replay-agent"),
        "status": embodiment.get("neural_runtime_status", "replay"),
        "step_count": embodiment.get("replay_event_index", len(events)),
        "learning_tick_count": embodiment.get("learning_tick_count", 0),
        "last_record": {
            "risk_score": embodiment.get("risk_score", 0.0),
            "prediction_confidence": embodiment.get("confidence_score", 0.0),
            "memory_activation_count": embodiment.get("memory_activation_count", 0),
            "phase": embodiment.get("current_loop_phase", "replay"),
            "local_only": True,
        },
        "local_only": True,
    }
    neural_status = {"ok": True, "source": "replay", "local_only": True}
    return state, events, [session], neural_status


def build_touchdesigner_frame(
    *,
    seq: int,
    source: str,
    connected: bool,
    state: Mapping[str, Any],
    events: Iterable[Mapping[str, Any]],
    sessions: Iterable[Mapping[str, Any]],
    neural_status: Mapping[str, Any] | None = None,
    max_events: int = 12,
    timestamp: float | None = None,
) -> dict[str, Any]:
    """Convert Flow Memory telemetry into a compact frame for DAT/JSON use."""
    event_list = list(events)
    session_list = [_mapping(item) for item in sessions]
    latest_session = _latest_session(session_list)
    latest_record = _mapping(latest_session.get("last_record"))
    state_neural = _first_mapping(state.get("neural"))
    runtime = _mapping(state.get("runtime"))
    agents = [_agent_record(agent) for agent in _sequence(state.get("agents"))]

    memory_count = _number(
        latest_record.get("memory_activation_count"),
        state_neural.get("memory_activation_count"),
        0.0,
    )
    learning_ticks = _number(
        latest_session.get("learning_tick_count"),
        state_neural.get("learning_tick_count"),
        0.0,
    )
    step_count = _number(latest_session.get("step_count"), 0.0)
    confidence = _number(
        latest_record.get("prediction_confidence"),
        latest_record.get("confidence"),
        state_neural.get("prediction_confidence"),
        0.0,
    )
    risk = _number(latest_record.get("risk_score"), state_neural.get("risk_score"), 0.0)
    event_count = len(event_list) or int(_number(runtime.get("events"), 0.0))
    agent_count = len(agents) or int(_number(runtime.get("agents"), 0.0))
    event_rate = min(1.0, event_count / 64.0)
    signal = min(1.0, (memory_count / 12.0) + (learning_ticks / 16.0) + (confidence * 0.28))

    recent_events = [_event_record(event) for event in event_list[-max_events:]]
    return {
        "kind": "flowmemory.telemetry.frame",
        "schema": 1,
        "seq": seq,
        "timestamp": timestamp if timestamp is not None else time.time(),
        "source": source,
        "connected": connected,
        "read_only": True,
        "metrics": {
            "agent_count": agent_count,
            "event_count": event_count,
            "event_rate": round(event_rate, 6),
            "memory_activation_count": int(memory_count),
            "learning_tick_count": int(learning_ticks),
            "step_count": int(step_count),
            "confidence": round(confidence, 6),
            "risk": round(risk, 6),
            "signal": round(signal, 6),
        },
        "agents": agents[:16],
        "events": recent_events,
        "neural_sessions": [_session_record(session) for session in session_list[:8]],
        "neural_status": dict(neural_status or {}),
    }


def run_bridge(config: BridgeConfig) -> None:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    seq = 0
    while True:
        try:
            state, events, sessions, neural_status = read_live_snapshot(config)
            source = "live_api"
            connected = True
        except (OSError, TimeoutError, URLError, ValueError, json.JSONDecodeError, KeyError):
            state, events, sessions, neural_status = read_replay_snapshot(config)
            source = "replay_fallback"
            connected = False

        frame = build_touchdesigner_frame(
            seq=seq,
            source=source,
            connected=connected,
            state=state,
            events=events,
            sessions=sessions,
            neural_status=neural_status,
            max_events=config.max_events,
        )
        payload = json.dumps(frame, separators=(",", ":"), sort_keys=True).encode("utf-8") + b"\n"
        sock.sendto(payload, (config.udp_host, config.udp_port))
        if config.stdout:
            print(payload.decode("utf-8"), end="")
        seq += 1
        if config.once:
            return
        time.sleep(config.interval)


def parse_args(argv: list[str] | None = None) -> BridgeConfig:
    parser = argparse.ArgumentParser(description="Stream Flow Memory read-only telemetry frames to TouchDesigner over UDP")
    parser.add_argument("--api", default=DEFAULT_API, help="Flow Memory local API base URL")
    parser.add_argument("--replay", type=Path, default=DEFAULT_REPLAY, help="Fallback neural embodiment replay JSON")
    parser.add_argument("--network-replay", type=Path, default=DEFAULT_NETWORK_REPLAY, help="Fallback visual network replay JSON")
    parser.add_argument("--udp-host", default="127.0.0.1", help="TouchDesigner UDP In DAT host")
    parser.add_argument("--udp-port", type=int, default=7000, help="TouchDesigner UDP In DAT port")
    parser.add_argument("--interval", type=float, default=0.25, help="Polling interval in seconds")
    parser.add_argument("--timeout", type=float, default=0.75, help="Local API timeout in seconds")
    parser.add_argument("--max-events", type=int, default=12, help="Recent events per frame")
    parser.add_argument("--once", action="store_true", help="Emit one frame and exit")
    parser.add_argument("--stdout", action="store_true", help="Also print frames to stdout")
    args = parser.parse_args(argv)
    if args.interval <= 0:
        raise ValueError("--interval must be positive")
    if args.timeout <= 0:
        raise ValueError("--timeout must be positive")
    if not (0 < args.udp_port <= 65535):
        raise ValueError("--udp-port must be 1..65535")
    return BridgeConfig(
        api=args.api,
        replay=args.replay,
        network_replay=args.network_replay,
        udp_host=args.udp_host,
        udp_port=args.udp_port,
        interval=args.interval,
        timeout=args.timeout,
        max_events=max(0, args.max_events),
        once=args.once,
        stdout=args.stdout,
    )


def _read_json(path: Path) -> Mapping[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, Mapping):
        raise ValueError(f"JSON root must be an object: {path}")
    return data


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _sequence(value: Any) -> tuple[Any, ...]:
    if isinstance(value, (list, tuple)):
        return tuple(value)
    return ()


def _first_mapping(value: Any) -> dict[str, Any]:
    sequence = _sequence(value)
    return _mapping(sequence[-1]) if sequence else _mapping(value)


def _latest_session(sessions: list[Mapping[str, Any]]) -> Mapping[str, Any]:
    if not sessions:
        return {}
    return max(sessions, key=lambda item: int(_number(item.get("step_count"), item.get("learning_tick_count"), 0.0)))


def _number(*values: Any) -> float:
    for value in values:
        try:
            if value is not None and value != "":
                return float(value)
        except (TypeError, ValueError):
            continue
    return 0.0


def _agent_record(agent: Any) -> dict[str, Any]:
    record = _mapping(agent)
    return {
        "id": str(record.get("agent_id", record.get("did", ""))),
        "label": str(record.get("label", record.get("name", "agent"))),
        "role": str(record.get("role", "agent")),
        "status": str(record.get("status", "unknown")),
        "reputation": _number(record.get("reputation"), 0.0),
        "position": tuple(_number(item, 0.0) for item in _sequence(record.get("position"))[:3]),
    }


def _event_record(event: Mapping[str, Any]) -> dict[str, Any]:
    payload = _mapping(event.get("payload"))
    return {
        "id": str(event.get("event_id", "")),
        "type": str(event.get("event_type", "event")),
        "source": str(event.get("source", payload.get("agent_id", ""))),
        "created_at": str(event.get("created_at", "")),
    }


def _session_record(session: Mapping[str, Any]) -> dict[str, Any]:
    last_record = _mapping(session.get("last_record"))
    return {
        "session_id": str(session.get("session_id", "")),
        "agent_id": str(session.get("agent_id", "")),
        "status": str(session.get("status", "unknown")),
        "step_count": int(_number(session.get("step_count"), 0.0)),
        "learning_tick_count": int(_number(session.get("learning_tick_count"), 0.0)),
        "phase": str(last_record.get("phase", last_record.get("status", ""))),
    }


def main(argv: list[str] | None = None) -> int:
    config = parse_args(argv)
    run_bridge(config)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
