"""Agent binding for optional neural advisory metadata.

Neural scores never approve or execute actions. PolicyEngine/ApprovalGate remain
authoritative; this binding only annotates plans, skills, memory retrieval, and
risk with advisory metadata.
"""

from __future__ import annotations

from typing import Any, Mapping

from flow_memory.neural.agent.evaluator import TinyNeuralEvaluator
from flow_memory.neural.agent.plan_scorer import TinyPlanScorer
from flow_memory.neural.agent.risk_model import TinyRiskModel
from flow_memory.neural.agent.skill_router import TinySkillRouter
from flow_memory.neural.config import neural_config_from_mapping
from flow_memory.neural.memory.retriever import NeuralMemoryRetriever
from flow_memory.neural.torch_optional import OptionalDependencyError, is_torch_available


class AgentNeuralBinding:
    def __init__(self) -> None:
        self.plan_scorer = TinyPlanScorer()
        self.skill_router = TinySkillRouter()
        self.risk_model = TinyRiskModel()
        self.evaluator = TinyNeuralEvaluator()
        self.retriever = NeuralMemoryRetriever()

    def annotate_plan(self, profile: Any, goal: str, plan: Any, context: tuple[Any, ...] = ()) -> Mapping[str, Any]:
        config = neural_config_from_mapping(getattr(profile, "neural_config", {}))
        records = tuple(context)
        for record in records:
            self.retriever.add(record)
        memory_hits = self.retriever.search(goal, top_k=3) if records else ()
        plan_score = self.plan_scorer.score_plan(plan, successful_memory_similarity=(memory_hits[0].score if memory_hits else 0.0))
        skills = ({"id": skill, "description": skill, "risk": 0.1} for skill in getattr(profile, "allowed_skills", ()))
        skill_scores = self.skill_router.rank_skills(goal, tuple(skills))
        risk_score = self.risk_model.score(plan.as_record() if hasattr(plan, "as_record") else plan)
        evaluation = self.evaluator.evaluate(goal, policy_allowed=True, memory_hits=len(memory_hits), economic_value=float(getattr(plan, "economic_value", 0.0)))
        record: dict[str, Any] = {
            "backend": config.backend,
            "status": "disabled" if config.backend == "none" else "available",
            "plan_scores": (plan_score.as_record(),),
            "skill_scores": tuple(score.as_record() for score in skill_scores),
            "risk_scores": risk_score.as_record(),
            "memory_retrieval_scores": tuple(hit.as_record() for hit in memory_hits),
            "evaluation_score": evaluation.as_record(),
            "safety_authority": "policy_engine_and_approval_gate",
        }
        if config.backend == "tiny_torch" and not is_torch_available():
            record["status"] = "skipped"
            record["reason"] = "tiny_torch requested but torch is not installed"
        elif config.backend in {"vjepa2", "videomae"}:
            record["status"] = "adapter_seam"
            record["reason"] = f"{config.backend} requires local dependencies and checkpoint_path"
        return record

    def attach_perception_metadata(self, profile: Any, video: Any | None = None) -> Mapping[str, Any]:
        config = neural_config_from_mapping(getattr(profile, "neural_config", {}))
        if config.backend == "none" or video is None:
            return {"backend": config.backend, "perception_features": None, "prediction": None, "surprise_score": None}
        if config.backend == "tiny_torch":
            try:
                from flow_memory.neural.backends.tiny_torch import TinyTorchBackend
                from flow_memory.neural.world_model.jepa import TinyJEPAWorldModel

                backend = TinyTorchBackend(config)
                features = backend.encode_video(video)
                prediction = TinyJEPAWorldModel().predict(features)
                return {"backend": config.backend, "perception_features": features.as_record(), "prediction": prediction.as_record(), "surprise_score": None}
            except OptionalDependencyError as exc:
                return {"backend": config.backend, "status": "skipped", "reason": str(exc), "perception_features": None, "prediction": None, "surprise_score": None}
        return {"backend": config.backend, "status": "adapter_seam", "perception_features": None, "prediction": None, "surprise_score": None}
