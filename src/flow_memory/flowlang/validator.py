"""FlowLang validation and compile entrypoints."""

from __future__ import annotations

from pathlib import Path

from flow_memory.flowlang.parser import FlowLangParseError, parse_flowlang, parse_flowlang_file
from flow_memory.ir import AgentSpec, CompileResult, compile_agent


def validate_agent_spec(agent: AgentSpec) -> tuple[str, ...]:
    """Validate a parsed AgentSpec against FlowLang v0 semantic rules."""

    return agent.validate()


def validate_flowlang(source: str) -> tuple[str, ...]:
    try:
        return validate_agent_spec(parse_flowlang(source))
    except FlowLangParseError as exc:
        return (str(exc),)


def compile_flowlang(source: str) -> CompileResult:
    """Compile FlowLang source into FlowIR and a JSON-serializable manifest."""

    try:
        agent = parse_flowlang(source)
    except FlowLangParseError as exc:
        return CompileResult(agent=None, errors=(str(exc),))
    return compile_agent(agent)


def compile_flowlang_file(path: str | Path) -> CompileResult:
    try:
        agent = parse_flowlang_file(path)
    except FlowLangParseError as exc:
        return CompileResult(agent=None, errors=(str(exc),))
    return compile_agent(agent)
