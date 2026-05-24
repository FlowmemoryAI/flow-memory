"""Command-line interface."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from typing import Any

from flow_memory import Agent
from flow_memory.protocols import CapabilityManifest
from flow_memory.flowlang import run_flowlang_agent
from flow_memory.agents.runner import AgentRunner
from flow_memory.agents.profile import AgentProfile
from flow_memory.compute_market.planner import compute_marketplace_plan
from flow_memory.compute_market.registry import default_policies, default_providers, default_routes
from flow_memory.neural.live import GLOBAL_NEURAL_RUNTIME


def _json_default(value: Any) -> str:
    try:
        return value.isoformat()
    except AttributeError:
        return repr(value)


def _run(prompt_parts: list[str], name: str, json_output: bool, neural_backend: str = "none", neural_live: bool = False) -> int:
    prompt = " ".join(prompt_parts)
    if neural_backend != "none":
        neural_config: dict[str, Any] = {"backend": neural_backend}
        if neural_live:
            neural_config.update({"enabled": True, "live_mode": True, "learning_enabled": True, "policy_fallback": "allow_non_neural", "telemetry_enabled": True})
        profile = AgentProfile(name=name, capabilities=("perception", "memory", "reasoning"), allowed_tools=("respond",), neural_config=neural_config)
        result = AgentRunner(profile).run_cycle(prompt)
        record = result.as_record()
        if json_output:
            print(json.dumps(record, indent=2, default=_json_default))
        else:
            print(record.get("output", {}).get("execution", {}).get("output", record.get("output", {})))
        return 0
    agent = Agent.create(name=name, capabilities=["perception", "memory", "reasoning"])
    cycle = agent.run_cycle(prompt)
    if json_output:
        print(json.dumps(asdict(cycle), indent=2, default=_json_default))
    else:
        print(cycle.final_output)
    return 0


def _run_flow(flow_path: str, prompt_parts: list[str], json_output: bool, neural_backend: str = "none") -> int:
    prompt = " ".join(prompt_parts)
    result = run_flowlang_agent(flow_path, prompt, neural_backend=neural_backend)
    if json_output:
        print(json.dumps(result, indent=2, default=_json_default))
    else:
        print(result.get("output", {}).get("execution", {}).get("output", result))
    return 0

def _manifest(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="flow-memory manifest")
    parser.add_argument("--name", default="alpha")
    parser.add_argument("--capability", action="append", default=[])
    parser.add_argument("--permission", action="append", default=["respond"])
    args = parser.parse_args(argv)
    agent = Agent.create(name=args.name, capabilities=args.capability)
    manifest = CapabilityManifest(
        agent_did=agent.did,
        name=args.name,
        capabilities=tuple(args.capability),
        permissions=tuple(args.permission),
    )
    print(json.dumps(asdict(manifest), indent=2, default=_json_default))
    return 0

def _compute(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="flow-memory compute", description="Inspect and simulate the local Compute Market")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("providers")
    sub.add_parser("routes")
    sub.add_parser("policies")

    plan = sub.add_parser("plan")
    plan.add_argument("--goal", default="Explore and report")
    plan.add_argument("--budget", type=float, default=0.01)
    plan.add_argument("--max-quote", type=float, default=0.01)
    plan.add_argument("--strategy", default="cheapest_eligible", choices=["cheapest_eligible", "lowest_latency", "highest_quality"])
    plan.add_argument("--marketplace-only", action="store_true")
    plan.add_argument("--model", default="small-general")
    plan.add_argument("--tokens-in", type=int, default=1000)
    plan.add_argument("--tokens-out", type=int, default=500)
    plan.add_argument("--payment-rail", default="local_credits", choices=["local_credits", "dry_run_usdc", "noop"])

    args = parser.parse_args(argv)
    if args.command == "providers":
        payload = {"ok": True, "providers": tuple(provider.as_record() for provider in default_providers()), "dry_run_only": True}
    elif args.command == "routes":
        payload = {"ok": True, "routes": tuple(route.as_record() for route in default_routes()), "dry_run_only": True}
    elif args.command == "policies":
        payload = {"ok": True, "policies": tuple(policy.as_record() for policy in default_policies()), "dry_run_required": True}
    else:
        payload = compute_marketplace_plan(
            {
                "task": {
                    "goal_id": args.goal,
                    "task_id": "cli-compute-task",
                    "model": args.model,
                    "expected_input_tokens": args.tokens_in,
                    "expected_output_tokens": args.tokens_out,
                    "requires_marketplace": args.marketplace_only,
                },
                "policy": {
                    "max_total_cost": args.budget,
                    "max_quote": args.max_quote,
                    "strategy": args.strategy,
                    "marketplace_only": args.marketplace_only,
                    "payment_rail": args.payment_rail,
                    "dry_run_required": True,
                },
            }
        )
    print(json.dumps(payload, indent=2, default=_json_default, sort_keys=True))
    return 0


def _neural(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="flow-memory neural", description="Inspect and run local neural live sessions")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("status")
    live = sub.add_parser("live")
    live_sub = live.add_subparsers(dest="live_command", required=True)
    create = live_sub.add_parser("create")
    create.add_argument("--agent-id", default="cli-neural-agent")
    create.add_argument("--backend", default="tiny_torch", choices=["none", "tiny_torch", "vjepa2", "videomae"])
    create.add_argument("--seed", type=int, default=0)
    create.add_argument("--policy-fallback", default="allow_non_neural", choices=["fail_closed", "allow_non_neural"])
    create.add_argument("--learning-enabled", action="store_true")
    live_sub.add_parser("list")
    step = live_sub.add_parser("step")
    step.add_argument("--session-id", default="")
    step.add_argument("--agent-id", default="cli-neural-agent")
    step.add_argument("--backend", default="tiny_torch", choices=["none", "tiny_torch", "vjepa2", "videomae"])
    step.add_argument("--goal", default="Explore and report")
    step.add_argument("--seed", type=int, default=0)
    step.add_argument("--policy-fallback", default="allow_non_neural", choices=["fail_closed", "allow_non_neural"])
    learn = live_sub.add_parser("learn")
    learn.add_argument("--session-id", default="")
    learn.add_argument("--agent-id", default="cli-neural-agent")
    learn.add_argument("--backend", default="tiny_torch", choices=["none", "tiny_torch", "vjepa2", "videomae"])
    learn.add_argument("--goal", default="Explore and report")
    checkpoint = live_sub.add_parser("checkpoint")
    checkpoint.add_argument("--session-id", default="")
    checkpoint.add_argument("--agent-id", default="cli-neural-agent")
    checkpoint.add_argument("--checkpoint-ref", default="")
    stop = live_sub.add_parser("stop")
    stop.add_argument("--session-id", default="")
    stop.add_argument("--agent-id", default="cli-neural-agent")
    args = parser.parse_args(argv)

    if args.command == "status":
        from flow_memory.neural import is_torch_available

        payload = {"ok": True, "torch_available": is_torch_available(), "sessions": tuple(session.as_record() for session in GLOBAL_NEURAL_RUNTIME.sessions()), "local_only": True}
    elif args.live_command == "create":
        session = GLOBAL_NEURAL_RUNTIME.create_session(
            args.agent_id,
            {
                "enabled": True,
                "backend": args.backend,
                "live_mode": True,
                "seed": args.seed,
                "policy_fallback": args.policy_fallback,
                "learning_enabled": args.learning_enabled,
            },
        )
        payload = {"ok": True, "session": session.as_record()}
    elif args.live_command == "list":
        payload = {"ok": True, "sessions": tuple(session.as_record() for session in GLOBAL_NEURAL_RUNTIME.sessions())}
    elif args.live_command == "step":
        session = GLOBAL_NEURAL_RUNTIME.get_session(args.session_id) if args.session_id else GLOBAL_NEURAL_RUNTIME.create_session(
            args.agent_id,
            {"enabled": True, "backend": args.backend, "live_mode": True, "seed": args.seed, "policy_fallback": args.policy_fallback},
        )
        payload = {"ok": True, "step": GLOBAL_NEURAL_RUNTIME.run_step(session.session_id, {"goal": args.goal, "source": "cli"}), "session": GLOBAL_NEURAL_RUNTIME.get_session(session.session_id).as_record()}
    elif args.live_command == "learn":
        session = GLOBAL_NEURAL_RUNTIME.get_session(args.session_id) if args.session_id else GLOBAL_NEURAL_RUNTIME.create_session(
            args.agent_id,
            {"enabled": True, "backend": args.backend, "live_mode": True, "learning_enabled": True, "policy_fallback": "allow_non_neural"},
        )
        payload = {"ok": True, "learning": GLOBAL_NEURAL_RUNTIME.learn(session.session_id, {"goal": args.goal, "source": "cli"}), "session": GLOBAL_NEURAL_RUNTIME.get_session(session.session_id).as_record()}
    elif args.live_command == "checkpoint":
        session = GLOBAL_NEURAL_RUNTIME.get_session(args.session_id) if args.session_id else GLOBAL_NEURAL_RUNTIME.create_session(
            args.agent_id,
            {"enabled": True, "backend": "none", "live_mode": True, "policy_fallback": "allow_non_neural"},
        )
        payload = {"ok": True, "checkpoint": GLOBAL_NEURAL_RUNTIME.checkpoint(session.session_id, args.checkpoint_ref), "session": GLOBAL_NEURAL_RUNTIME.get_session(session.session_id).as_record(), "raw_weights_written": False}
    else:
        session = GLOBAL_NEURAL_RUNTIME.get_session(args.session_id) if args.session_id else GLOBAL_NEURAL_RUNTIME.create_session(
            args.agent_id,
            {"enabled": True, "backend": "none", "live_mode": True, "policy_fallback": "allow_non_neural"},
        )
        payload = {"ok": True, "stop": GLOBAL_NEURAL_RUNTIME.stop(session.session_id), "session": GLOBAL_NEURAL_RUNTIME.get_session(session.session_id).as_record()}
    print(json.dumps(payload, indent=2, default=_json_default, sort_keys=True))
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == "manifest":
        return _manifest(argv[1:])
    if argv and argv[0] == "compute":
        return _compute(argv[1:])
    if argv and argv[0] == "neural":
        return _neural(argv[1:])
    if argv and argv[0] == "run":
        argv = argv[1:]

    parser = argparse.ArgumentParser(prog="flow-memory", description="Run a local Flow Memory agent")
    parser.add_argument("prompt", nargs="+", help="Observation/goal for the agent")
    parser.add_argument("--name", default="alpha", help="Agent name")
    parser.add_argument("--flow", default="", help="FlowLang .flow file to compile and run")
    parser.add_argument("--json", action="store_true", help="Print full cognitive-cycle trace as JSON")
    parser.add_argument("--neural", default="none", choices=["none", "tiny_torch", "vjepa2", "videomae"], help="Optional neural advisory backend")
    parser.add_argument("--neural-live", action="store_true", help="Attach a local neural live runtime session when --neural is set")
    args = parser.parse_args(argv)
    if args.flow:
        return _run_flow(args.flow, args.prompt, args.json, args.neural)
    return _run(args.prompt, args.name, args.json, args.neural, args.neural_live)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
