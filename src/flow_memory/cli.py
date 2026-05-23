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
from flow_memory.agents.neural_binding import AgentNeuralBinding
from flow_memory.agents.profile import AgentProfile


def _json_default(value: Any) -> str:
    try:
        return value.isoformat()
    except AttributeError:
        return repr(value)


def _run(prompt_parts: list[str], name: str, json_output: bool, neural_backend: str = "none") -> int:
    prompt = " ".join(prompt_parts)
    if neural_backend != "none":
        profile = AgentProfile(name=name, capabilities=("perception", "memory", "reasoning"), allowed_tools=("respond",), neural_config={"backend": neural_backend})
        neural = AgentNeuralBinding().annotate_plan(profile, prompt, type("PromptPlan", (), {"plan_id": "cli_prompt", "risk_level": "low", "economic_value": 0.0, "steps": (), "as_record": lambda self: {"plan_id": "cli_prompt", "risk_level": "low"}})())
        agent = Agent.create(name=name, capabilities=["perception", "memory", "reasoning"])
        cycle = agent.run_cycle(prompt)
        record = asdict(cycle)
        record["neural"] = neural
        if json_output:
            print(json.dumps(record, indent=2, default=_json_default))
        else:
            print(cycle.final_output)
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


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == "manifest":
        return _manifest(argv[1:])
    if argv and argv[0] == "run":
        argv = argv[1:]

    parser = argparse.ArgumentParser(prog="flow-memory", description="Run a local Flow Memory agent")
    parser.add_argument("prompt", nargs="+", help="Observation/goal for the agent")
    parser.add_argument("--name", default="alpha", help="Agent name")
    parser.add_argument("--flow", default="", help="FlowLang .flow file to compile and run")
    parser.add_argument("--json", action="store_true", help="Print full cognitive-cycle trace as JSON")
    parser.add_argument("--neural", default="none", choices=["none", "tiny_torch", "vjepa2", "videomae"], help="Optional neural advisory backend")
    args = parser.parse_args(argv)
    if args.flow:
        return _run_flow(args.flow, args.prompt, args.json, args.neural)
    return _run(args.prompt, args.name, args.json, args.neural)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
