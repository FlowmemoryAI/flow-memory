"""Run FlowLang-declared agents."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from flow_memory.agents.runner import AgentRunner
from flow_memory.flowlang.parser import parse_flowlang_file
from flow_memory.ir.agent_adapter import agent_profile_from_ir


def profile_from_flowlang(path: str | Path):
    return agent_profile_from_ir(parse_flowlang_file(path))


def run_flowlang_agent(path: str | Path, user_input: str) -> Mapping[str, Any]:
    profile = profile_from_flowlang(path)
    return AgentRunner(profile).run_cycle(user_input).as_record()
