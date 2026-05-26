"""Local live neural runtime sessions for Flow Memory agents.

The live runtime is intentionally local and deterministic. It exposes neural
advisory metadata to agent loops and Mission Control without making external
model calls, downloading checkpoints, moving funds, or claiming GPU validation.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from typing import Any, Mapping

from flow_memory.core.types import new_id
from flow_memory.neural.config import SUPPORTED_BACKENDS
from flow_memory.neural.torch_optional import is_torch_available


LIVE_POLICY_FALLBACKS = frozenset({"fail_closed", "allow_non_neural"})


@dataclass(frozen=True)
class NeuralLiveConfig:
    enabled: bool = False
    backend: str = "tiny_torch"
    live_mode: bool = False
    learning_enabled: bool = False
    learning_rate: float = 0.01
    seed: int = 0
    model_profile: str = "local-small"
    checkpoint_ref: str = ""
    perception_streams: tuple[str, ...] = ("text", "events", "memory")
    plan_scoring_enabled: bool = True
    risk_scoring_enabled: bool = True
    memory_retrieval_enabled: bool = True
    policy_fallback: str = "fail_closed"
    max_step_ms: int = 0
    telemetry_enabled: bool = True
    inference_mode: str = "local_deterministic"

    def validate(self) -> tuple[str, ...]:
        errors: list[str] = []
        if self.backend not in SUPPORTED_BACKENDS:
            errors.append(f"unknown neural backend: {self.backend}")
        if self.policy_fallback not in LIVE_POLICY_FALLBACKS:
            errors.append(f"unknown neural policy_fallback: {self.policy_fallback}")
        if self.learning_rate < 0:
            errors.append("neural learning_rate must be non-negative")
        if self.max_step_ms < 0:
            errors.append("neural max_step_ms must be non-negative")
        return tuple(errors)

    def as_record(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "backend": self.backend,
            "live_mode": self.live_mode,
            "learning_enabled": self.learning_enabled,
            "learning_rate": self.learning_rate,
            "seed": self.seed,
            "model_profile": self.model_profile,
            "checkpoint_ref": self.checkpoint_ref,
            "perception_streams": self.perception_streams,
            "plan_scoring_enabled": self.plan_scoring_enabled,
            "risk_scoring_enabled": self.risk_scoring_enabled,
            "memory_retrieval_enabled": self.memory_retrieval_enabled,
            "policy_fallback": self.policy_fallback,
            "max_step_ms": self.max_step_ms,
            "telemetry_enabled": self.telemetry_enabled,
            "inference_mode": self.inference_mode,
        }


@dataclass(frozen=True)
class NeuralRuntimeSession:
    session_id: str
    agent_id: str
    config: NeuralLiveConfig
    status: str
    backend_available: bool
    device: str = "cpu"
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    step_count: int = 0
    learning_tick_count: int = 0
    stopped: bool = False
    last_record: Mapping[str, Any] = field(default_factory=dict)
    checkpoint_metadata: Mapping[str, Any] = field(default_factory=dict)

    def as_record(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "agent_id": self.agent_id,
            "config": self.config.as_record(),
            "status": self.status,
            "backend_available": self.backend_available,
            "device": self.device,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "step_count": self.step_count,
            "learning_tick_count": self.learning_tick_count,
            "stopped": self.stopped,
            "last_record": dict(self.last_record),
            "checkpoint_metadata": dict(self.checkpoint_metadata),
            "safety_authority": "policy_engine_and_approval_gate",
        }


class NeuralRuntimeManager:
    """In-process local neural runtime session registry."""

    def __init__(self) -> None:
        self._sessions: dict[str, NeuralRuntimeSession] = {}

    def create_session(self, agent_id: str, config: Mapping[str, Any] | NeuralLiveConfig | None = None) -> NeuralRuntimeSession:
        requested_session_id = ""
        if isinstance(config, Mapping):
            requested_session_id = str(config.get("session_id", "")).strip()
        live_config = neural_live_config_from_mapping(config)
        errors = live_config.validate()
        if errors:
            status = "invalid_config"
            backend_available = False
        else:
            status, backend_available = _backend_status(live_config)
        session = NeuralRuntimeSession(
            session_id=requested_session_id or new_id("neural_session"),
            agent_id=agent_id,
            config=live_config,
            status=status,
            backend_available=backend_available,
            device="cpu",
            last_record={"errors": errors, "local_only": True} if errors else {"local_only": True},
        )
        self._sessions[session.session_id] = session
        return session

    def attach_agent(self, session_id: str, agent_id: str) -> NeuralRuntimeSession:
        session = self.get_session(session_id)
        updated = replace(session, agent_id=agent_id, updated_at=_now())
        self._sessions[session_id] = updated
        return updated

    def get_session(self, session_id: str) -> NeuralRuntimeSession:
        try:
            return self._sessions[session_id]
        except KeyError as exc:
            raise KeyError(f"unknown neural session: {session_id}") from exc

    def sessions(self) -> tuple[NeuralRuntimeSession, ...]:
        return tuple(self._sessions.values())

    def encode_perception(self, session_id: str, context: Mapping[str, Any] | None = None) -> Mapping[str, Any]:
        """Encode local perception metadata for the current session without side effects."""
        session = self.get_session(session_id)
        context_record = dict(context or {})
        return {
            "ok": True,
            "session_id": session.session_id,
            "agent_id": session.agent_id,
            "encoded": True,
            "streams": session.config.perception_streams,
            "embedding_id": _stable_id("neural_embedding", session.session_id, str(session.step_count), str(context_record.get("goal", ""))),
            "local_only": True,
            "external_model_calls": False,
        }

    def predict_next_state(self, session_id: str, context: Mapping[str, Any] | None = None) -> Mapping[str, Any]:
        """Predict the next local latent/world state using deterministic metadata."""
        session = self.get_session(session_id)
        signal = _deterministic_signal(session, dict(context or {}))
        fallback_active = session.status in {"unavailable", "invalid_config", "adapter_seam", "disabled"}
        return {
            "ok": True,
            "session_id": session.session_id,
            "agent_id": session.agent_id,
            "prediction_id": _stable_id("neural_prediction", session.session_id, str(signal["prediction_confidence"])),
            "confidence": signal["prediction_confidence"],
            "world_model": "tiny_jepa_local" if session.config.backend == "tiny_torch" and not fallback_active else "deterministic_metadata",
            "surprise_score": signal["surprise_score"],
            "local_only": True,
            "external_model_calls": False,
        }

    def score_plan(self, session_id: str, context: Mapping[str, Any] | None = None) -> Mapping[str, Any]:
        """Score the current plan/action candidate as advisory metadata only."""
        session = self.get_session(session_id)
        signal = _deterministic_signal(session, dict(context or {}))
        score = signal["plan_score"] if session.config.plan_scoring_enabled else 0.0
        return {
            "ok": True,
            "session_id": session.session_id,
            "agent_id": session.agent_id,
            "plan_score": score,
            "action_score": score,
            "recommended_action": "respond" if signal["risk_score"] < 0.5 else "request_approval",
            "advisory_only": True,
            "safety_authority": "policy_engine_and_approval_gate",
            "local_only": True,
        }

    def score_risk(self, session_id: str, context: Mapping[str, Any] | None = None) -> Mapping[str, Any]:
        """Score risk as advisory metadata only."""
        session = self.get_session(session_id)
        signal = _deterministic_signal(session, dict(context or {}))
        risk_score = signal["risk_score"] if session.config.risk_scoring_enabled else 0.0
        return {
            "ok": True,
            "session_id": session.session_id,
            "agent_id": session.agent_id,
            "risk_score": risk_score,
            "approval_recommended": risk_score >= 0.5,
            "advisory_only": True,
            "safety_authority": "policy_engine_and_approval_gate",
            "local_only": True,
        }

    def retrieve_memory_candidates(self, session_id: str, context: Mapping[str, Any] | None = None) -> Mapping[str, Any]:
        """Return deterministic local neural memory candidates."""
        session = self.get_session(session_id)
        candidates = _memory_candidates(session, dict(context or {})) if session.config.memory_retrieval_enabled else ()
        return {
            "ok": True,
            "session_id": session.session_id,
            "agent_id": session.agent_id,
            "memory_candidates": candidates,
            "memory_activation_count": len(candidates),
            "local_only": True,
        }

    def run_step(self, session_id: str, context: Mapping[str, Any] | None = None) -> Mapping[str, Any]:
        session = self.get_session(session_id)
        if session.stopped:
            record = _base_record(session, context, phase="stopped", ok=False, status="stopped")
            self._update(session, record, increment_step=False)
            return record
        context_record = dict(context or {})
        unavailable = session.status in {"unavailable", "invalid_config", "adapter_seam", "disabled"}
        if unavailable and session.config.policy_fallback == "fail_closed":
            record = _base_record(session, context_record, phase="fail_closed", ok=False, status="fail_closed")
            record.update({
                "reason": _unavailable_reason(session),
                "policy_gate_state": "denied",
                "action_state": "denied",
                "safety_authority": "policy_engine_and_approval_gate",
            })
            self._update(session, record, increment_step=True)
            return record

        fallback_active = unavailable
        perception = self.encode_perception(session.session_id, context_record)
        prediction = self.predict_next_state(session.session_id, context_record)
        plan_score = self.score_plan(session.session_id, context_record)
        risk_score = self.score_risk(session.session_id, context_record)
        memory = self.retrieve_memory_candidates(session.session_id, context_record)
        record = _base_record(session, context_record, phase="learning" if session.config.learning_enabled else "evaluated", ok=True, status="fallback_non_neural" if fallback_active else "ok")
        record.update({
            "backend_available": session.backend_available,
            "fallback_active": fallback_active,
            "perception": {
                "encoded": perception["encoded"],
                "streams": perception["streams"],
                "embedding_id": perception["embedding_id"],
            },
            "prediction": {
                "prediction_id": prediction["prediction_id"],
                "confidence": prediction["confidence"],
                "world_model": prediction["world_model"],
            },
            "plan_score": plan_score["plan_score"],
            "risk_score": risk_score["risk_score"],
            "memory_candidates": memory["memory_candidates"],
            "memory_activation_count": memory["memory_activation_count"],
            "prediction_confidence": prediction["confidence"],
            "surprise_score": prediction["surprise_score"],
            "uncertainty": round(1.0 - prediction["confidence"], 6),
            "recommended_action": plan_score["recommended_action"],
            "action_state": "recommended",
            "policy_gate_state": "pending_policy_gate",
            "safety_authority": "policy_engine_and_approval_gate",
        })
        self._update(session, record, increment_step=True)
        return record

    def learn(self, session_id: str, sample: Mapping[str, Any] | None = None) -> Mapping[str, Any]:
        session = self.get_session(session_id)
        sample_record = dict(sample or {})
        if not session.config.learning_enabled:
            record = {
                "ok": True,
                "status": "skipped",
                "reason": "learning disabled",
                "session_id": session.session_id,
                "agent_id": session.agent_id,
                "learning_tick_count": session.learning_tick_count,
                "local_only": True,
            }
            self._update(session, record, increment_step=False)
            return record
        before = _unit_hash(session.session_id, str(session.learning_tick_count), "before", str(sample_record))
        after = max(0.0, round(before * (1.0 - min(session.config.learning_rate, 1.0)), 6))
        record = {
            "ok": True,
            "status": "learned",
            "session_id": session.session_id,
            "agent_id": session.agent_id,
            "before_metric": before,
            "after_metric": after,
            "loss": after,
            "step_count": session.step_count,
            "learning_tick_count": session.learning_tick_count + 1,
            "sample_id": _stable_id("neural_sample", session.session_id, str(sample_record)),
            "local_only": True,
            "safety_authority": "policy_engine_and_approval_gate",
        }
        updated = replace(session, learning_tick_count=session.learning_tick_count + 1, last_record=record, updated_at=_now())
        self._sessions[session_id] = updated
        return record

    def learn_from_prediction_error(self, session_id: str, experience: Mapping[str, Any]) -> Mapping[str, Any]:
        """Convert prediction-error experience into a local learning sample."""
        sample = dict(experience.get("neural_learning_sample", experience))
        prediction_error = _safe_float(sample.get("prediction_error", experience.get("prediction_error", 0.0)))
        sample["prediction_error"] = prediction_error
        sample["learning_signal"] = "prediction_error"
        record = dict(self.learn(session_id, sample))
        record["prediction_error"] = prediction_error
        record["learning_signal"] = "prediction_error"
        record["advisory_only"] = True
        record["raw_weights_written"] = False
        return record

    def checkpoint(self, session_id: str, checkpoint_ref: str = "") -> Mapping[str, Any]:
        session = self.get_session(session_id)
        ref = checkpoint_ref or session.config.checkpoint_ref or f"artifacts/neural/live/{session.session_id}.metadata.json"
        metadata = {
            "checkpoint_id": _stable_id("neural_checkpoint", session.session_id, ref, str(session.step_count), str(session.learning_tick_count)),
            "checkpoint_ref": ref,
            "metadata_only": True,
            "raw_weights_written": False,
            "session_id": session.session_id,
            "agent_id": session.agent_id,
            "step_count": session.step_count,
            "learning_tick_count": session.learning_tick_count,
            "local_only": True,
        }
        updated = replace(session, checkpoint_metadata=metadata, last_record=metadata, updated_at=_now())
        self._sessions[session_id] = updated
        return metadata

    def save_checkpoint_metadata(self, session_id: str, checkpoint_ref: str = "") -> Mapping[str, Any]:
        """Write metadata-only checkpoint JSON; never writes model weights."""
        metadata = dict(self.checkpoint(session_id, checkpoint_ref))
        path = Path(str(metadata["checkpoint_ref"]))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(metadata, indent=2, sort_keys=True), encoding="utf-8")
        saved = {**metadata, "checkpoint_written": True, "checkpoint_bytes": path.stat().st_size}
        session = self.get_session(session_id)
        self._sessions[session_id] = replace(session, checkpoint_metadata=saved, last_record=saved, updated_at=_now())
        return saved

    def load_checkpoint_metadata(self, checkpoint_ref: str) -> Mapping[str, Any]:
        """Load metadata-only checkpoint JSON and reject anything shaped like weights."""
        path = Path(checkpoint_ref)
        data = json.loads(path.read_text(encoding="utf-8"))
        metadata_only = data.get("metadata_only") is True and data.get("raw_weights_written") is False
        return {
            "ok": metadata_only,
            "checkpoint": data,
            "checkpoint_ref": str(path),
            "metadata_only": metadata_only,
            "raw_weights_loaded": False,
            "local_only": True,
        }

    def stop(self, session_id: str) -> Mapping[str, Any]:
        session = self.get_session(session_id)
        record = {"ok": True, "status": "stopped", "session_id": session.session_id, "agent_id": session.agent_id, "local_only": True}
        self._sessions[session_id] = replace(session, status="stopped", stopped=True, last_record=record, updated_at=_now())
        return record

    def _update(self, session: NeuralRuntimeSession, record: Mapping[str, Any], *, increment_step: bool) -> None:
        self._sessions[session.session_id] = replace(
            session,
            step_count=session.step_count + (1 if increment_step else 0),
            last_record=dict(record),
            updated_at=_now(),
        )


GLOBAL_NEURAL_RUNTIME = NeuralRuntimeManager()


def neural_live_config_from_mapping(data: Mapping[str, Any] | NeuralLiveConfig | None) -> NeuralLiveConfig:
    if isinstance(data, NeuralLiveConfig):
        return data
    mapping = dict(data or {})
    options = dict(mapping.get("options", {})) if isinstance(mapping.get("options", {}), Mapping) else {}
    def _get(name: str, default: Any) -> Any:
        return mapping.get(name, options.get(name, default))
    return NeuralLiveConfig(
        enabled=bool(_get("enabled", mapping.get("backend", "none") != "none")),
        backend=str(_get("backend", "tiny_torch")),
        live_mode=bool(_get("live_mode", False)),
        learning_enabled=bool(_get("learning_enabled", False)),
        learning_rate=float(_get("learning_rate", 0.01) or 0.0),
        seed=int(_get("seed", 0) or 0),
        model_profile=str(_get("model_profile", "local-small")),
        checkpoint_ref=str(_get("checkpoint_ref", _get("checkpoint_path", ""))),
        perception_streams=_as_tuple(_get("perception_streams", ("text", "events", "memory"))),
        plan_scoring_enabled=bool(_get("plan_scoring_enabled", True)),
        risk_scoring_enabled=bool(_get("risk_scoring_enabled", True)),
        memory_retrieval_enabled=bool(_get("memory_retrieval_enabled", True)),
        policy_fallback=str(_get("policy_fallback", "fail_closed")),
        max_step_ms=int(_get("max_step_ms", 0) or 0),
        telemetry_enabled=bool(_get("telemetry_enabled", True)),
        inference_mode=str(_get("inference_mode", "local_deterministic")),
    )


def _backend_status(config: NeuralLiveConfig) -> tuple[str, bool]:
    if not config.enabled or config.backend == "none":
        return "disabled", False
    if config.backend == "tiny_torch":
        return ("available", True) if is_torch_available() else ("unavailable", False)
    if config.backend in {"vjepa2", "videomae"}:
        return "adapter_seam", False
    return "invalid_config", False


def _base_record(session: NeuralRuntimeSession, context: Mapping[str, Any] | None, *, phase: str, ok: bool, status: str) -> dict[str, Any]:
    return {
        "ok": ok,
        "status": status,
        "phase": phase,
        "session_id": session.session_id,
        "agent_id": session.agent_id,
        "backend": session.config.backend,
        "model_profile": session.config.model_profile,
        "step_count": session.step_count + 1,
        "learning_tick_count": session.learning_tick_count,
        "context": dict(context or {}),
        "local_only": True,
        "external_model_calls": False,
        "gpu_evidence_claimed": False,
    }


def _deterministic_signal(session: NeuralRuntimeSession, context: Mapping[str, Any]) -> dict[str, float]:
    base = f"{session.config.seed}|{session.step_count}|{context.get('goal', '')}|{context.get('plan_id', '')}"
    plan_score = round(0.45 + _unit_hash(base, "plan") * 0.5, 6)
    risk_score = round(_unit_hash(base, "risk") * 0.4, 6)
    prediction_confidence = round(0.5 + _unit_hash(base, "prediction") * 0.45, 6)
    surprise_score = round(max(0.0, 1.0 - prediction_confidence), 6)
    return {
        "plan_score": plan_score,
        "risk_score": risk_score,
        "prediction_confidence": prediction_confidence,
        "surprise_score": surprise_score,
    }


def _memory_candidates(session: NeuralRuntimeSession, context: Mapping[str, Any]) -> tuple[dict[str, Any], ...]:
    goal = str(context.get("goal", ""))
    if not goal:
        return ()
    return ({
        "memory_id": _stable_id("neural_memory", session.agent_id, goal),
        "agent_id": session.agent_id,
        "score": round(0.5 + _unit_hash(goal, session.session_id) * 0.4, 6),
        "summary": f"local neural memory candidate for {goal[:48]}",
    },)


def _unavailable_reason(session: NeuralRuntimeSession) -> str:
    if session.status == "invalid_config":
        return "neural live config invalid"
    if session.config.backend == "tiny_torch":
        return "tiny_torch requested but torch is not installed"
    if session.config.backend in {"vjepa2", "videomae"}:
        return f"{session.config.backend} remains an adapter seam requiring local checkpoint integration"
    return f"neural backend unavailable: {session.status}"


def _unit_hash(*parts: str) -> float:
    digest = hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:12]
    return int(digest, 16) / float(0xFFFFFFFFFFFF)


def _stable_id(prefix: str, *parts: str) -> str:
    digest = hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:16]
    return f"{prefix}_{digest}"


def _safe_float(value: Any) -> float:
    try:
        if value is not None and value != "":
            return float(value)
    except (TypeError, ValueError):
        return 0.0
    return 0.0

def _as_tuple(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return tuple(part.strip() for part in value.split(",") if part.strip())
    if isinstance(value, (list, tuple, set, frozenset)):
        return tuple(str(item).strip() for item in value if str(item).strip())
    return (str(value),)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
