"""Start a local neural live session for TouchDesigner visualization tests.

Run this while the local Flow Memory API server and TouchDesigner UDP bridge are
running. It creates one read/write local neural session, then repeatedly sends
step and learn ticks so the TouchDesigner neural loom has changing telemetry.

This script only calls the local neural runtime endpoints. It does not touch
marketplace settlement, provider calls, funds, or external model APIs.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import dataclass
from typing import Any, Mapping
from urllib.error import HTTPError, URLError
from urllib.request import ProxyHandler, Request, build_opener

DEFAULT_API = "http://127.0.0.1:8765"
DEFAULT_AGENT_ID = "touchdesigner-neural-worker"
DEFAULT_GOAL = "Stream a local neural memory loop into TouchDesigner"

LOCAL_OPENER = build_opener(ProxyHandler({}))


@dataclass(frozen=True)
class StarterConfig:
    api: str = DEFAULT_API
    agent_id: str = DEFAULT_AGENT_ID
    goal: str = DEFAULT_GOAL
    backend: str = "tiny_torch"
    ticks: int = 240
    interval: float = 0.35
    learn_every: int = 2
    learning_rate: float = 0.12


def post_json(base_url: str, path: str, payload: Mapping[str, Any], *, timeout: float = 5.0) -> Mapping[str, Any]:
    request = Request(
        f"{base_url.rstrip('/')}{path}",
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
        headers={"content-type": "application/json", "accept": "application/json"},
    )
    with LOCAL_OPENER.open(request, timeout=timeout) as response:  # noqa: S310 - local operator API only
        body = json.loads(response.read().decode("utf-8"))
    if not isinstance(body, Mapping):
        raise ValueError("API returned non-object JSON")
    data = body.get("data")
    return data if isinstance(data, Mapping) else body


def build_session_payload(config: StarterConfig) -> dict[str, Any]:
    return {
        "agent_id": config.agent_id,
        "config": {
            "enabled": True,
            "backend": config.backend,
            "live_mode": True,
            "learning_enabled": True,
            "learning_rate": config.learning_rate,
            "policy_fallback": "allow_non_neural",
            "telemetry_enabled": True,
            "perception_streams": ("events", "memory", "policy"),
            "model_profile": "touchdesigner-local-loom",
        },
    }


def build_step_payload(config: StarterConfig, tick: int) -> dict[str, Any]:
    phase = ("perceive", "predict", "remember", "braid", "learn", "stabilize")[tick % 6]
    return {
        "context": {
            "goal": config.goal,
            "tick": tick,
            "phase": phase,
            "source": "touchdesigner-live-test",
            "signal_density": round(0.25 + ((tick * 17) % 70) / 100, 3),
            "memory_pressure": round(0.15 + ((tick * 11) % 80) / 100, 3),
            "operator_intent": "show live agent telemetry in the neural loom",
        }
    }


def build_learning_payload(config: StarterConfig, tick: int) -> dict[str, Any]:
    return {
        "sample": {
            "goal": config.goal,
            "tick": tick,
            "source": "touchdesigner-live-test",
            "positive_signal": True,
            "memory_trace_id": f"td-memory-trace-{tick:04d}",
            "target": "increase coherent strand convergence without bypassing policy gates",
        }
    }


def create_session(config: StarterConfig) -> str:
    data = post_json(config.api, "/neural/live/sessions", build_session_payload(config))
    session = data.get("session")
    if not isinstance(session, Mapping):
        raise ValueError("API response did not include session")
    session_id = str(session.get("session_id", ""))
    if not session_id:
        raise ValueError("API response did not include session_id")
    print(f"Created neural live session: {session_id}")
    print(f"Agent id: {config.agent_id}")
    print("TouchDesigner bridge should switch to connected=true and source=live_api.")
    return session_id


def pump_session(config: StarterConfig, session_id: str) -> None:
    for tick in range(1, config.ticks + 1):
        step = post_json(config.api, f"/neural/live/sessions/{session_id}/step", build_step_payload(config, tick))
        step_record = step.get("step") if isinstance(step.get("step"), Mapping) else {}
        learning_record: Mapping[str, Any] = {}
        if config.learn_every > 0 and tick % config.learn_every == 0:
            learning = post_json(config.api, f"/neural/live/sessions/{session_id}/learn", build_learning_payload(config, tick))
            learning_record = learning.get("learning") if isinstance(learning.get("learning"), Mapping) else {}
        confidence = _number(step_record.get("prediction_confidence"), step_record.get("confidence"), 0.0)
        risk = _number(step_record.get("risk_score"), 0.0)
        memory = int(_number(step_record.get("memory_activation_count"), 0.0))
        learned = learning_record.get("status", "")
        suffix = f" learn={learned}" if learned else ""
        print(f"tick={tick:04d} confidence={confidence:.3f} risk={risk:.3f} memory={memory}{suffix}")
        time.sleep(config.interval)


def parse_args(argv: list[str] | None = None) -> StarterConfig:
    parser = argparse.ArgumentParser(description="Create a local neural live session and stream ticks for TouchDesigner")
    parser.add_argument("--api", default=DEFAULT_API, help="Flow Memory local API base URL")
    parser.add_argument("--agent-id", default=DEFAULT_AGENT_ID, help="Agent id shown in telemetry")
    parser.add_argument("--goal", default=DEFAULT_GOAL, help="Goal/context sent through the neural session")
    parser.add_argument("--backend", default="tiny_torch", help="Neural backend name")
    parser.add_argument("--ticks", type=int, default=240, help="Number of step ticks to send")
    parser.add_argument("--interval", type=float, default=0.35, help="Seconds between ticks")
    parser.add_argument("--learn-every", type=int, default=2, help="Send a learn tick every N steps; 0 disables learning ticks")
    parser.add_argument("--learning-rate", type=float, default=0.12, help="Local deterministic learning-rate metadata")
    args = parser.parse_args(argv)
    if args.ticks < 1:
        raise ValueError("--ticks must be positive")
    if args.interval < 0:
        raise ValueError("--interval must be non-negative")
    if args.learn_every < 0:
        raise ValueError("--learn-every must be non-negative")
    if args.learning_rate < 0:
        raise ValueError("--learning-rate must be non-negative")
    return StarterConfig(
        api=args.api,
        agent_id=args.agent_id,
        goal=args.goal,
        backend=args.backend,
        ticks=args.ticks,
        interval=args.interval,
        learn_every=args.learn_every,
        learning_rate=args.learning_rate,
    )


def _number(*values: Any) -> float:
    for value in values:
        try:
            if value is not None and value != "":
                return float(value)
        except (TypeError, ValueError):
            continue
    return 0.0


def main(argv: list[str] | None = None) -> int:
    config = parse_args(argv)
    try:
        session_id = create_session(config)
        pump_session(config, session_id)
    except (ConnectionError, HTTPError, TimeoutError, URLError) as exc:
        print(f"Could not reach Flow Memory local API at {config.api}: {exc}", file=sys.stderr)
        print("Start it first with: python scripts/run_local_api_server.py", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("Stopped live neural agent pump.")
        return 130
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
