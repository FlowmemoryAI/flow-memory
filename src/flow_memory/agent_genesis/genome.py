"""Portable Agent Genome records for Agent Genesis."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

from flow_memory.agents.profile import AgentProfile, RiskBudget
from flow_memory.cognition.state import stable_id, utc_now
from flow_memory.agent_genesis.boundaries import compile_boundaries
from flow_memory.agent_genesis.instincts import merge_instinct_profiles

DEFAULT_GENOME_DIR = Path("artifacts/genesis/genomes")


@dataclass(frozen=True)
class AgentGenome:
    genome_id: str
    agent_id: str
    archetype_id: str
    version: str
    purpose: str
    instincts: tuple[str, ...]
    boundaries: tuple[str, ...]
    drive_profile: Mapping[str, Any]
    cognition_profile: Mapping[str, Any]
    neural_profile: Mapping[str, Any]
    memory_profile: Mapping[str, Any]
    policy_profile: Mapping[str, Any]
    privacy_profile: Mapping[str, Any]
    contribution_profile: Mapping[str, Any]
    benchmark_refs: tuple[str, ...] = field(default_factory=tuple)
    parent_genome_id: str = ""
    forked_from: str = ""
    public_shareable: bool = False
    private_memory_excluded: bool = True
    created_at: str = field(default_factory=utc_now)

    def as_record(self) -> dict[str, Any]:
        return {
            "genome_id": self.genome_id,
            "agent_id": self.agent_id,
            "archetype_id": self.archetype_id,
            "version": self.version,
            "purpose": self.purpose,
            "instincts": self.instincts,
            "boundaries": self.boundaries,
            "drive_profile": dict(self.drive_profile),
            "cognition_profile": dict(self.cognition_profile),
            "neural_profile": dict(self.neural_profile),
            "memory_profile": dict(self.memory_profile),
            "policy_profile": dict(self.policy_profile),
            "privacy_profile": dict(self.privacy_profile),
            "contribution_profile": dict(self.contribution_profile),
            "benchmark_refs": self.benchmark_refs,
            "parent_genome_id": self.parent_genome_id,
            "forked_from": self.forked_from,
            "public_shareable": self.public_shareable,
            "private_memory_excluded": self.private_memory_excluded,
            "created_at": self.created_at,
        }


def create_genome(
    *,
    agent_id: str,
    archetype_id: str,
    purpose: str,
    instincts: tuple[str, ...],
    boundaries: tuple[str, ...],
    neural_profile: Mapping[str, Any],
    cognition_profile: Mapping[str, Any],
    memory_profile: Mapping[str, Any] | None = None,
    privacy_profile: Mapping[str, Any] | None = None,
    contribution_profile: Mapping[str, Any] | None = None,
    parent_genome_id: str = "",
    forked_from: str = "",
    public_shareable: bool = False,
) -> AgentGenome:
    policy = compile_boundaries(boundaries)
    privacy = {"consent_mode": "private_only", "raw_payload_allowed": False, "private_memory_allowed": False, **dict(privacy_profile or {})}
    contribution = {"network_learning": privacy.get("consent_mode", "private_only"), "raw_private_payload_excluded": True, **dict(contribution_profile or {})}
    genome_id = stable_id("agent_genome", agent_id, archetype_id, purpose, "|".join(instincts), "|".join(boundaries), parent_genome_id)
    return AgentGenome(
        genome_id=genome_id,
        agent_id=agent_id,
        archetype_id=archetype_id,
        version="agent-genome-v1",
        purpose=purpose,
        instincts=instincts,
        boundaries=boundaries,
        drive_profile=merge_instinct_profiles(instincts),
        cognition_profile=dict(cognition_profile),
        neural_profile=dict(neural_profile),
        memory_profile=dict(memory_profile or {"private_memory": True, "experience_memory": True}),
        policy_profile=policy,
        privacy_profile=privacy,
        contribution_profile=contribution,
        parent_genome_id=parent_genome_id,
        forked_from=forked_from,
        public_shareable=public_shareable,
        private_memory_excluded=True,
    )


def validate_genome(genome: AgentGenome | Mapping[str, Any]) -> tuple[str, ...]:
    record = genome.as_record() if isinstance(genome, AgentGenome) else dict(genome)
    errors: list[str] = []
    for key in ("genome_id", "agent_id", "archetype_id", "purpose"):
        if not str(record.get(key, "")).strip():
            errors.append(f"{key} is required")
    if record.get("private_memory_excluded") is not True:
        errors.append("private memory must be excluded from portable genome")
    privacy = dict(record.get("privacy_profile", {})) if isinstance(record.get("privacy_profile", {}), Mapping) else {}
    if privacy.get("raw_payload_allowed") is True or privacy.get("private_memory_allowed") is True:
        errors.append("genome privacy profile must not allow raw private payloads by default")
    return tuple(errors)


def genome_to_agent_profile(genome: AgentGenome | Mapping[str, Any], *, name: str = "") -> AgentProfile:
    record = genome.as_record() if isinstance(genome, AgentGenome) else dict(genome)
    policy = dict(record.get("policy_profile", {}))
    max_spend = float(policy.get("max_spend", 0.0) or 0.0)
    profile = AgentProfile(
        agent_id=str(record.get("agent_id", "")),
        name=name or str(record.get("agent_id", "genesis-agent")),
        description=str(record.get("purpose", "")),
        persona="Policy-gated Flow Memory agent born through Agent Genesis.",
        goals=(str(record.get("purpose", "Explore and report")),),
        constraints=tuple(str(item) for item in record.get("boundaries", ())),
        capabilities=("predictive_cognition", "memory_consolidation", "safe_local_tools"),
        allowed_tools=("observe_environment", "respond"),
        memory_config=dict(record.get("memory_profile", {})),
        neural_config=dict(record.get("neural_profile", {})),
        cognition_config=dict(record.get("cognition_profile", {})),
        autonomy_mode=str(policy.get("autonomy", "supervised")),
        risk_budget=RiskBudget(max_spend=max_spend, max_escrow_exposure=max_spend, max_slashing_exposure=max_spend),
        metadata={"agent_genome": record},
    )
    errors = profile.validate()
    if errors:
        raise ValueError("; ".join(errors))
    return profile


def fork_genome(genome: AgentGenome | Mapping[str, Any], *, new_agent_id: str, purpose: str = "") -> AgentGenome:
    record = genome.as_record() if isinstance(genome, AgentGenome) else dict(genome)
    return create_genome(
        agent_id=new_agent_id,
        archetype_id=str(record.get("archetype_id", "research-builder")),
        purpose=purpose or str(record.get("purpose", "Explore and report")),
        instincts=tuple(str(item) for item in record.get("instincts", ())),
        boundaries=tuple(str(item) for item in record.get("boundaries", ())),
        neural_profile=dict(record.get("neural_profile", {})),
        cognition_profile=dict(record.get("cognition_profile", {})),
        memory_profile=dict(record.get("memory_profile", {})),
        privacy_profile=dict(record.get("privacy_profile", {})),
        contribution_profile=dict(record.get("contribution_profile", {})),
        parent_genome_id=str(record.get("genome_id", "")),
        forked_from=str(record.get("agent_id", "")),
        public_shareable=bool(record.get("public_shareable", False)),
    )


def write_genome(genome: AgentGenome | Mapping[str, Any], root: str | Path = ".", directory: str | Path = DEFAULT_GENOME_DIR) -> Mapping[str, Any]:
    payload = genome.as_record() if isinstance(genome, AgentGenome) else dict(genome)
    errors = validate_genome(payload)
    if errors:
        raise ValueError("; ".join(errors))
    path = _path(root, directory, str(payload["agent_id"]))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {"ok": True, "agent_id": payload["agent_id"], "genome_id": payload["genome_id"], "path": _rel(Path(root).resolve(), path), "record": payload}


def get_genome(agent_id: str, root: str | Path = ".", directory: str | Path = DEFAULT_GENOME_DIR) -> Mapping[str, Any]:
    path = _path(root, directory, agent_id)
    if not path.exists():
        raise KeyError(f"unknown agent genome: {agent_id}")
    return json.loads(path.read_text(encoding="utf-8"))


def export_genome(agent_id: str, out: str | Path, root: str | Path = ".") -> Mapping[str, Any]:
    record = get_genome(agent_id, root=root)
    path = Path(out)
    if not path.is_absolute():
        path = Path(root).resolve() / path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {"ok": True, "agent_id": agent_id, "path": _rel(Path(root).resolve(), path), "genome": record}


def import_genome(path: str | Path) -> Mapping[str, Any]:
    record = json.loads(Path(path).read_text(encoding="utf-8"))
    errors = validate_genome(record)
    return {"ok": not errors, "errors": errors, "genome": record}


def _path(root: str | Path, directory: str | Path, agent_id: str) -> Path:
    safe = "".join(ch for ch in agent_id if ch.isalnum() or ch in {"-", "_", "."}).strip(".")
    if not safe:
        raise ValueError("agent_id is required")
    return Path(root).resolve() / directory / f"{safe}.json"


def _rel(root: Path, path: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)
