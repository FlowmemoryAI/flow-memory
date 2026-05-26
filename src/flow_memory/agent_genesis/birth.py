"""Agent Birth Flow for Agent Genesis."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

from flow_memory.cognition.state import stable_id, utc_now
from flow_memory.cognition.world_model import DeterministicWorldModel
from flow_memory.agent_genesis.archetypes import get_archetype
from flow_memory.agent_genesis.consent import create_consent, write_consent
from flow_memory.agent_genesis.genome import create_genome, genome_to_agent_profile, write_genome
from flow_memory.agent_genesis.memory_seed import create_memory_seed, write_memory_seed
from flow_memory.agent_genesis.mirror import build_mirror, write_mirror
from flow_memory.agent_genesis.passport import build_passport, write_passport

DEFAULT_BIRTH_DIR = Path("artifacts/genesis/births")


@dataclass(frozen=True)
class CreateAgentBirthRequest:
    user_id: str
    agent_name: str
    archetype_id: str = "research-builder"
    purpose: str = ""
    instincts: tuple[str, ...] = ()
    boundaries: tuple[str, ...] = ()
    memory_seed: Mapping[str, Any] = field(default_factory=dict)
    consent_mode: str = "private_only"
    launch_immediately: bool = False
    open_mission_control: bool = True

    def as_record(self) -> dict[str, Any]:
        return {
            "user_id": self.user_id,
            "agent_name": self.agent_name,
            "archetype_id": self.archetype_id,
            "purpose": self.purpose,
            "instincts": self.instincts,
            "boundaries": self.boundaries,
            "memory_seed": dict(self.memory_seed),
            "consent_mode": self.consent_mode,
            "launch_immediately": self.launch_immediately,
            "open_mission_control": self.open_mission_control,
        }


@dataclass(frozen=True)
class AgentBirthCertificate:
    birth_id: str
    agent_id: str
    genome_id: str
    memory_seed_id: str
    consent_id: str
    name: str
    purpose: str
    archetype: str
    instincts: tuple[str, ...]
    boundaries: tuple[str, ...]
    privacy: Mapping[str, Any]
    network_learning_status: str
    first_prediction: Mapping[str, Any]
    created_at: str = field(default_factory=utc_now)

    def as_record(self) -> dict[str, Any]:
        return {
            "birth_id": self.birth_id,
            "agent_id": self.agent_id,
            "genome_id": self.genome_id,
            "memory_seed_id": self.memory_seed_id,
            "consent_id": self.consent_id,
            "name": self.name,
            "purpose": self.purpose,
            "archetype": self.archetype,
            "instincts": self.instincts,
            "boundaries": self.boundaries,
            "privacy": dict(self.privacy),
            "network_learning_status": self.network_learning_status,
            "first_prediction": dict(self.first_prediction),
            "created_at": self.created_at,
        }


def first_prediction_ceremony(agent_name: str, purpose: str, archetype_prediction: str, boundaries: tuple[str, ...]) -> Mapping[str, Any]:
    risk = 0.10 if "never_spend_money" in boundaries else 0.16
    confidence = 0.72 if purpose else 0.64
    return {
        "prediction": archetype_prediction,
        "confidence": confidence,
        "risk": risk,
        "policy": "supervised; approval required",
        "verification_plan": "Compare predicted state to the observed first run and write a lesson if the result differs.",
        "agent_name": agent_name,
        "local_only": True,
    }


def birth_agent(request: CreateAgentBirthRequest | Mapping[str, Any], *, root: str | Path = ".") -> Mapping[str, Any]:
    req = request if isinstance(request, CreateAgentBirthRequest) else CreateAgentBirthRequest(
        user_id=str(request.get("user_id", request.get("user", "local-user"))),
        agent_name=str(request.get("agent_name", request.get("name", "Mira"))),
        archetype_id=str(request.get("archetype_id", request.get("archetype", "research-builder"))),
        purpose=str(request.get("purpose", "")),
        instincts=tuple(str(item) for item in request.get("instincts", ()) if str(item).strip()),
        boundaries=tuple(str(item) for item in request.get("boundaries", ()) if str(item).strip()),
        memory_seed=dict(request.get("memory_seed", {})) if isinstance(request.get("memory_seed", {}), Mapping) else {},
        consent_mode=str(request.get("consent_mode", request.get("consent", "private_only"))),
        launch_immediately=bool(request.get("launch_immediately", request.get("launch", False))),
        open_mission_control=bool(request.get("open_mission_control", True)),
    )
    archetype = get_archetype(req.archetype_id)
    purpose = req.purpose.strip() or archetype.default_purpose
    instincts = tuple(dict.fromkeys(req.instincts or archetype.default_instincts))
    boundaries = tuple(dict.fromkeys(req.boundaries or archetype.default_boundaries))
    agent_id = stable_id("genesis_agent", req.user_id, req.agent_name, req.archetype_id, purpose)
    seed_payload = _seed_payload(req.memory_seed, archetype.default_memory_seed_template)
    seed = create_memory_seed(agent_id=agent_id, privacy_mode=req.consent_mode, **seed_payload)
    consent = create_consent(user_id=req.user_id, agent_id=agent_id, mode=req.consent_mode)
    genome = create_genome(
        agent_id=agent_id,
        archetype_id=req.archetype_id,
        purpose=purpose,
        instincts=instincts,
        boundaries=boundaries,
        neural_profile=archetype.default_neural_config,
        cognition_profile=archetype.default_cognition_config,
        memory_profile={"private_memory": True, "memory_seed_id": seed.seed_id, "experience_memory": True},
        privacy_profile={"consent_mode": req.consent_mode, "private_memory_allowed": False, "raw_payload_allowed": False},
        contribution_profile={"mode": req.consent_mode, "allowed_record_types": consent.allowed_record_types, "raw_private_payload_excluded": True},
        public_shareable=req.consent_mode == "public_agent_genome",
    )
    first_prediction = first_prediction_ceremony(req.agent_name, purpose, archetype.first_prediction_template, boundaries)
    birth_id = stable_id("agent_birth", agent_id, genome.genome_id, seed.seed_id, consent.consent_id)
    certificate = AgentBirthCertificate(
        birth_id=birth_id,
        agent_id=agent_id,
        genome_id=genome.genome_id,
        memory_seed_id=seed.seed_id,
        consent_id=consent.consent_id,
        name=req.agent_name,
        purpose=purpose,
        archetype=req.archetype_id,
        instincts=instincts,
        boundaries=boundaries,
        privacy={"mode": req.consent_mode, "raw_private_payload_excluded": True, "private_memory_shared": False},
        network_learning_status="disabled" if req.consent_mode == "private_only" else "opted_in_sanitized",
        first_prediction=first_prediction,
    )
    profile = genome_to_agent_profile(genome, name=req.agent_name)
    launch_summary = _launch_first_tick(agent_id, purpose, first_prediction, req.launch_immediately, root)
    mirror = build_mirror(agent_id, first_prediction, launch_summary.get("actual_outcome", {"success": True, "simulated": True}), archetype.first_lesson_template, contribution_mode=req.consent_mode)
    passport = build_passport(agent_id, {**genome.as_record(), "limitations": archetype.limitations}, {"runs_completed": 1 if req.launch_immediately else 0, "policy_compliance": 1.0})

    writes = {
        "genome": write_genome(genome, root=root),
        "memory_seed": write_memory_seed(seed, root=root),
        "consent": write_consent(consent, root=root),
        "mirror": write_mirror(mirror, root=root),
        "passport": write_passport(passport, root=root),
        "birth_certificate": write_birth_certificate(certificate, root=root),
    }
    return {
        "ok": True,
        "birth_id": birth_id,
        "agent_id": agent_id,
        "genome_id": genome.genome_id,
        "memory_seed_id": seed.seed_id,
        "consent_id": consent.consent_id,
        "birth_certificate": certificate.as_record(),
        "first_prediction": first_prediction,
        "agent_profile": profile.as_record(),
        "launch_summary": launch_summary,
        "mission_control_url": f"/mission-control#genesis-{agent_id}" if req.open_mission_control else "",
        "passport": passport.as_record(),
        "mirror": mirror.as_record(),
        "writes": writes,
        "safety_authority": "policy_engine_and_approval_gate",
        "local_only": True,
    }


def write_birth_certificate(certificate: AgentBirthCertificate | Mapping[str, Any], root: str | Path = ".", directory: str | Path = DEFAULT_BIRTH_DIR) -> Mapping[str, Any]:
    payload = certificate.as_record() if isinstance(certificate, AgentBirthCertificate) else dict(certificate)
    path = _path(root, directory, str(payload["agent_id"]))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {"ok": True, "agent_id": payload["agent_id"], "birth_id": payload["birth_id"], "path": _rel(Path(root).resolve(), path), "record": payload}


def get_birth_certificate(agent_id: str, root: str | Path = ".", directory: str | Path = DEFAULT_BIRTH_DIR) -> Mapping[str, Any]:
    path = _path(root, directory, agent_id)
    if not path.exists():
        raise KeyError(f"unknown birth certificate: {agent_id}")
    return json.loads(path.read_text(encoding="utf-8"))


def _launch_first_tick(agent_id: str, purpose: str, first_prediction: Mapping[str, Any], launch: bool, root: str | Path) -> Mapping[str, Any]:
    if not launch:
        return {"launched": False, "actual_outcome": {"success": True, "simulated": True, "reason": "agent born as seed profile; first run not requested"}}
    tick = DeterministicWorldModel().tick({"agent_id": agent_id, "goal": purpose, "action": "map project state and verify first safe step"}, root=root)
    return {"launched": True, "tick": tick, "actual_outcome": tick.get("actual_outcome", {})}


def _seed_payload(memory_seed: Mapping[str, Any], defaults: Mapping[str, tuple[str, ...]]) -> Mapping[str, Any]:
    return {
        "user_preferences": _tuple(memory_seed.get("user_preferences", defaults.get("user_preferences", ()))),
        "project_context": _tuple(memory_seed.get("project_context", defaults.get("project_context", ()))),
        "behavior_rules": _tuple(memory_seed.get("behavior_rules", defaults.get("behavior_rules", ()))),
        "initial_lessons": _tuple(memory_seed.get("initial_lessons", ())),
        "raw_private_content": str(memory_seed.get("raw_private_content", "")),
    }


def _tuple(value: Any) -> tuple[str, ...]:
    if isinstance(value, str):
        return (value,) if value.strip() else ()
    if isinstance(value, (list, tuple, set, frozenset)):
        return tuple(str(item) for item in value if str(item).strip())
    return ()


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
