"""Deterministic local world model for prediction-driven agents."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from flow_memory.cognition.counterfactuals import CounterfactualSet, build_counterfactual_set
from flow_memory.cognition.consolidation import retrieve_similar_lessons
from flow_memory.cognition.experience import ExperienceRecord, build_experience, retrieve_similar_experiences, write_experience
from flow_memory.cognition.learning import learning_update_from_experience
from flow_memory.cognition.prediction import CandidateAction, PredictionRecord, candidate_action
from flow_memory.cognition.prediction_error import PredictionErrorRecord, compute_prediction_error
from flow_memory.cognition.scoring import CandidateScore, score_candidates
from flow_memory.cognition.state import WorldState, build_world_state, stable_id


class DeterministicWorldModel:
    """Rule-based, artifact-backed world model scoped to observable local domains."""

    def encode_state(self, payload: Mapping[str, Any] | None = None, *, root: str | Path = ".") -> WorldState:
        data = dict(payload or {})
        goal = str(data.get("goal", "Explore and report"))
        memory_context = tuple(dict(item) for item in data.get("memory_context", ()) if isinstance(item, Mapping)) if isinstance(data.get("memory_context", ()), (list, tuple)) else ()
        similar = retrieve_similar_experiences({"agent_id": str(data.get("agent_id", "agent")), "goal": goal}, root=root, limit=3)
        lessons = retrieve_similar_lessons({"goal": goal, "memory_tags": _tags_for_goal(goal)}, root=root, limit=3)
        if not memory_context:
            memory_context = _dedup_memories(tuple(similar) + tuple(lessons))
        return build_world_state(
            agent_id=str(data.get("agent_id", data.get("agent", "agent"))),
            goal=goal,
            run_id=str(data.get("run_id", "")),
            session_id=str(data.get("session_id", "")),
            current_phase=str(data.get("current_phase", "observed")),
            repo_state=_mapping(data.get("repo_state")),
            dashboard_state=_mapping(data.get("dashboard_state")),
            release_state=_mapping(data.get("release_state")),
            policy_state=_mapping(data.get("policy_state", {"mode": "supervised"})),
            memory_context=memory_context,
            recent_errors=tuple(str(item) for item in data.get("recent_errors", ()) if str(item).strip()) if isinstance(data.get("recent_errors", ()), (list, tuple)) else (),
            available_tools=tuple(str(item) for item in data.get("available_tools", ("pytest", "npm", "git", "release_decision"))),
            gpu_evidence_status=str(data.get("gpu_evidence_status", "verified")),
            uncertainty_score=float(data.get("uncertainty_score", 0.42) or 0.42),
        )

    def generate_candidate_actions(self, state: WorldState, requested_action: str = "", *, max_actions: int = 4) -> tuple[CandidateAction, ...]:
        goal = state.goal.lower()
        actions: list[CandidateAction] = []
        if requested_action:
            sensitive = _policy_sensitive_text(f"{goal} {requested_action}")
            actions.append(candidate_action(requested_action, action_type="requested", expected_domain=_domain(f"{goal} {requested_action}"), command_preview=requested_action, requires_approval=sensitive, policy_sensitive=sensitive))
        if "dashboard" in goal or "mission" in goal:
            actions.extend((
                candidate_action("verify served Mission Control HTML before claiming success", action_type="diagnostic", expected_domain="dashboard", command_preview="Invoke-WebRequest /mission-control"),
                candidate_action("restart stale local dashboard server before verification", action_type="command_sequence", expected_domain="dashboard", command_preview="stop stale port; npm run dev"),
                candidate_action("run dashboard build and render tests", action_type="diagnostic", expected_domain="dashboard", command_preview="npm test && npm run build"),
            ))
        elif "release" in goal or "public-alpha" in goal:
            actions.extend((
                candidate_action("run release decision for target", action_type="diagnostic", expected_domain="release", command_preview="python scripts/release_decision.py"),
                candidate_action("export and verify release evidence", action_type="diagnostic", expected_domain="release", command_preview="python scripts/export_release_evidence.py"),
                candidate_action("import GPU evidence artifact then verify release gates", action_type="diagnostic", expected_domain="release", command_preview="python scripts/verify_release_evidence.py"),
                candidate_action("inspect missing release blocker evidence", action_type="code_inspection", expected_domain="release"),
            ))
        elif "policy" in goal or "delete" in goal or "fund" in goal:
            actions.extend((
                candidate_action("request approval before policy-sensitive action", action_type="approval", expected_domain="policy", requires_approval=True, policy_sensitive=True),
                candidate_action("simulate policy-sensitive action without side effects", action_type="simulation", expected_domain="policy"),
                candidate_action("inspect policy gate reason", action_type="diagnostic", expected_domain="policy"),
            ))
        elif "compute" in goal or "market" in goal:
            actions.extend((
                candidate_action("build dry-run compute market route", action_type="simulation", expected_domain="compute", command_preview="python -m flow_memory compute plan"),
                candidate_action("inspect compute policy before route selection", action_type="diagnostic", expected_domain="compute"),
                candidate_action("avoid live provider settlement in local public-alpha", action_type="simulation", expected_domain="compute"),
            ))
        elif "git" in goal or "commit" in goal or "push" in goal:
            actions.extend((
                candidate_action("run tests/checks before commit", action_type="diagnostic", expected_domain="git", command_preview="pytest; npm test; git diff --check"),
                candidate_action("stage requested paths, commit, and push", action_type="command_sequence", expected_domain="git", command_preview="git add; git commit; git push"),
                candidate_action("confirm clean working tree after push", action_type="diagnostic", expected_domain="git", command_preview="git status --short"),
            ))
        else:
            actions.extend((
                candidate_action("inspect current state before acting", action_type="diagnostic", expected_domain="general"),
                candidate_action("execute current policy-gated plan", action_type="plan", expected_domain="agent"),
                candidate_action("retrieve similar experience memories", action_type="memory_query", expected_domain="memory"),
            ))
        dedup: dict[str, CandidateAction] = {}
        for action in actions:
            dedup.setdefault(action.action_id, action)
        return tuple(dedup.values())[:max_actions]

    def predict_outcome(self, state: WorldState, action: CandidateAction, memories: tuple[Mapping[str, Any], ...] = ()) -> PredictionRecord:
        domain = action.expected_domain or _domain(state.goal)
        memory_support = min(1.0, len(memories) / 5.0)
        risk = _risk_for(action, state)
        confidence = _confidence_for(action, state, memory_support, risk)
        reward = _reward_for(action, state, memory_support)
        patch = _state_patch(domain, action, confidence)
        prediction_id = stable_id("prediction_record", state.state_id, action.action_id, confidence, risk, reward)
        return PredictionRecord(
            prediction_id=prediction_id,
            agent_id=state.agent_id,
            run_id=state.run_id,
            state_id=state.state_id,
            candidate_action_id=action.action_id,
            predicted_result=_predicted_result(action, domain, confidence),
            predicted_state_patch=patch,
            confidence=round(confidence, 6),
            risk=round(risk, 6),
            expected_reward=round(reward, 6),
            expected_cost=action.estimated_cost,
            expected_time_ms=int(float(action.estimated_cost.get("time_seconds", 30) or 30) * 1000),
            possible_failure_modes=_failure_modes(domain, action),
            reasoning_summary=_reasoning(action, state, memories, confidence, risk),
            memory_support_ids=tuple(str(item.get("experience_id", item.get("memory_id", item.get("lesson_id", "")))) for item in memories if item.get("experience_id") or item.get("memory_id") or item.get("lesson_id")),
        )

    def generate_counterfactuals(self, state: WorldState, actions: tuple[CandidateAction, ...], memories: tuple[Mapping[str, Any], ...] = ()) -> CounterfactualSet:
        predictions = tuple(self.predict_outcome(state, action, memories) for action in actions)
        return build_counterfactual_set(state.state_id, state.goal, predictions)

    def score_candidates(self, actions: tuple[CandidateAction, ...], counterfactuals: CounterfactualSet, memories: tuple[Mapping[str, Any], ...] = ()) -> tuple[CandidateScore, ...]:
        return _apply_lesson_adjustments(actions, score_candidates(actions, counterfactuals.candidate_predictions, memory_support=min(1.0, len(memories) / 5.0)), memories)

    def observe_outcome(self, prediction: PredictionRecord, actual_outcome: Mapping[str, Any]) -> PredictionErrorRecord:
        return compute_prediction_error(prediction, actual_outcome)

    def learn_from_experience(self, experience: ExperienceRecord | Mapping[str, Any]) -> Mapping[str, Any]:
        return learning_update_from_experience(experience.as_record() if isinstance(experience, ExperienceRecord) else experience)

    def tick(self, payload: Mapping[str, Any] | None = None, *, root: str | Path = ".") -> Mapping[str, Any]:
        data = dict(payload or {})
        state = self.encode_state(data, root=root)
        memories = _dedup_memories(tuple(state.memory_context) + tuple(retrieve_similar_experiences(state, root=root, limit=5)) + tuple(retrieve_similar_lessons(state.as_record(), root=root, limit=5)))
        actions = self.generate_candidate_actions(state, str(data.get("action", "")), max_actions=int(data.get("max_counterfactuals", 4) or 4))
        counterfactuals = self.generate_counterfactuals(state, actions, memories)
        scores = self.score_candidates(actions, counterfactuals, memories)
        recommended_id = next((score.candidate_action_id for score in scores if score.recommended), counterfactuals.recommended_action_id)
        selected_action = next(action for action in actions if action.action_id == recommended_id)
        selected_prediction = next(prediction for prediction in counterfactuals.candidate_predictions if prediction.candidate_action_id == recommended_id)
        policy_decision = _policy_decision(selected_action, state)
        actual = dict(data.get("actual_outcome", {})) if isinstance(data.get("actual_outcome", {}), Mapping) else {}
        if not actual:
            actual = {"success": policy_decision["allowed"], "state_patch": dict(selected_prediction.predicted_state_patch), "simulated": True}
        if not policy_decision["allowed"]:
            actual = {**actual, "success": False, "policy_denied": True, "reason": policy_decision["reason"]}
        error = self.observe_outcome(selected_prediction, actual)
        learning = learning_update_from_experience({"experience_id": stable_id("experience_preview", selected_prediction.prediction_id), "prediction_error": error.as_record()})
        experience = build_experience(
            state=state,
            retrieved_memory_ids=tuple(str(item.get("experience_id", item.get("lesson_id", ""))) for item in memories if item.get("experience_id") or item.get("lesson_id")),
            candidate_actions=actions,
            counterfactuals=counterfactuals,
            selected_action=selected_action,
            prediction=selected_prediction,
            policy_decision=policy_decision,
            actual_outcome=actual,
            prediction_error=error,
            learning_update=learning,
        )
        written = write_experience(experience, root=root) if bool(data.get("write_experience", True)) else {"ok": True, "record": experience.as_record(), "path": ""}
        lesson_reuse = _lesson_reuse(memories)
        return {
            "ok": True,
            "state": state.as_record(),
            "retrieved_memories": memories,
            "candidate_actions": tuple(action.as_record() for action in actions),
            "counterfactuals": counterfactuals.as_record(),
            "scores": tuple(score.as_record() for score in scores),
            "selected_action": selected_action.as_record(),
            "prediction": selected_prediction.as_record(),
            "policy_decision": policy_decision,
            "actual_outcome": actual,
            "prediction_error": error.as_record(),
            "experience": experience.as_record(),
            "experience_path": written.get("path", ""),
            "learning_update": learning,
            "lesson_reuse": lesson_reuse,
            "local_only": True,
            "safety_authority": "policy_engine_and_approval_gate",
        }


def _mapping(value: Any) -> Mapping[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _domain(goal: str) -> str:
    if "dashboard" in goal or "mission" in goal:
        return "dashboard"
    if "release" in goal or "public-alpha" in goal or "gpu" in goal:
        return "release"
    if "compute" in goal or "market" in goal:
        return "compute"
    if "git" in goal or "commit" in goal or "push" in goal:
        return "git"
    if _policy_sensitive_text(goal):
        return "policy"
    return "agent"


def _policy_sensitive_text(text: str) -> bool:
    lowered = text.lower()
    return any(token in lowered for token in ("policy", "delete", "fund", "private key", "settlement", "broadcast", "provider", "backup folder"))


def _risk_for(action: CandidateAction, state: WorldState) -> float:
    base = 0.12
    if action.requires_approval or action.policy_sensitive:
        base += 0.45
    if action.action_type == "command_sequence":
        base += 0.16
    if state.uncertainty_score > 0.6:
        base += 0.08
    return min(1.0, base)


def _confidence_for(action: CandidateAction, state: WorldState, memory_support: float, risk: float) -> float:
    return max(0.05, min(0.98, 0.62 + memory_support * 0.18 - risk * 0.22 + (0.08 if action.action_type == "diagnostic" else 0.0) - state.uncertainty_score * 0.08))


def _reward_for(action: CandidateAction, state: WorldState, memory_support: float) -> float:
    reward = 0.50 + memory_support * 0.18
    if action.action_type in {"diagnostic", "simulation"}:
        reward += 0.10
    if action.expected_domain in {"dashboard", "release", "compute", "git"}:
        reward += 0.08
    if state.current_phase == "blocked":
        reward += 0.05
    return min(1.0, reward)


def _state_patch(domain: str, action: CandidateAction, confidence: float) -> Mapping[str, Any]:
    if domain == "dashboard":
        return {"dashboard_checked": True, "mission_control_visible": confidence > 0.55, "placeholder_removed": confidence > 0.55}
    if domain == "release":
        return {"release_decision_checked": True, "required_evidence_present": confidence > 0.55}
    if domain == "policy":
        return {"policy_gate_checked": True, "approval_required": action.requires_approval}
    if domain == "compute":
        return {"compute_route_checked": True, "dry_run_route_selected": confidence > 0.55, "no_funds_moved": True}
    if domain == "git":
        return {"git_checked": True, "tests_passed": confidence > 0.55, "working_tree_clean": confidence > 0.55}
    return {"agent_step_observed": True, "goal_progress": confidence > 0.5}


def _failure_modes(domain: str, action: CandidateAction) -> tuple[str, ...]:
    if domain == "dashboard":
        return ("stale local server", "wrong port", "browser cache", "static placeholder route")
    if domain == "release":
        return ("missing evidence artifact", "release gate failed", "stale bundle index")
    if domain == "compute":
        return ("live provider route requested", "budget policy missing", "dry-run route not selected")
    if domain == "git":
        return ("tests not run", "working tree not clean", "push result unverified")
    if action.requires_approval:
        return ("policy gate denial", "operator approval missing")
    return ("insufficient observation", "memory mismatch")


def _predicted_result(action: CandidateAction, domain: str, confidence: float) -> str:
    if domain == "dashboard":
        return "served dashboard should contain Mission Control panels and no placeholder text" if confidence > 0.55 else "dashboard verification may expose stale server or placeholder output"
    if domain == "release":
        return "release decision should identify missing or passing evidence without side effects"
    if domain == "policy":
        return "policy gate remains authoritative and may deny unsafe recommendations"
    if domain == "compute":
        return "dry-run compute route should be selected without live providers or funds"
    if domain == "git":
        return "tests/checks should predict a clean commit and push outcome"
    return f"{action.description} should advance the goal if the observed state matches memory."


def _reasoning(action: CandidateAction, state: WorldState, memories: tuple[Mapping[str, Any], ...], confidence: float, risk: float) -> str:
    return f"Action {action.description!r} scored with confidence {confidence:.2f}, risk {risk:.2f}, memories {len(memories)}, phase {state.current_phase}."


def _dedup_memories(memories: tuple[Mapping[str, Any], ...]) -> tuple[Mapping[str, Any], ...]:
    seen: set[str] = set()
    deduped: list[Mapping[str, Any]] = []
    for memory in memories:
        key = str(memory.get("experience_id") or memory.get("lesson_id") or memory.get("memory_id") or memory)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(memory)
    return tuple(deduped)


def _tags_for_goal(goal: str) -> tuple[str, ...]:
    tags = ["cognition"]
    lowered = goal.lower()
    for tag in ("dashboard", "mission-control", "release", "gpu", "policy", "compute", "market", "git", "commit", "neural"):
        if tag in lowered:
            tags.append("compute" if tag == "market" else "git" if tag == "commit" else tag)
    return tuple(dict.fromkeys(tags))


def _lesson_reuse(memories: tuple[Mapping[str, Any], ...]) -> Mapping[str, Any]:
    lessons = tuple(memory for memory in memories if memory.get("lesson_id"))
    return {
        "reused": bool(lessons),
        "lesson_ids": tuple(str(lesson.get("lesson_id", "")) for lesson in lessons if lesson.get("lesson_id")),
        "recommended_actions": tuple(str(lesson.get("recommended_future_action", "")) for lesson in lessons if lesson.get("recommended_future_action")),
    }


def _apply_lesson_adjustments(actions: tuple[CandidateAction, ...], scores: tuple[CandidateScore, ...], memories: tuple[Mapping[str, Any], ...]) -> tuple[CandidateScore, ...]:
    if not scores:
        return ()
    lessons = tuple(memory for memory in memories if memory.get("lesson_id"))
    if not lessons:
        return scores
    action_by_id = {action.action_id: action for action in actions}
    adjusted: list[CandidateScore] = []
    for score in scores:
        action = action_by_id.get(score.candidate_action_id)
        bonus = _lesson_bonus(action, lessons) if action is not None else 0.0
        penalty = 0.22 if action is not None and (action.requires_approval or action.policy_sensitive) and _policy_lesson_present(lessons) else 0.0
        record = score.as_record()
        record["overall_score"] = round(max(0.0, min(1.0, float(score.overall_score) + bonus - penalty)), 6)
        record["memory_support"] = round(max(float(score.memory_support), min(1.0, len(lessons) / 5.0)), 6)
        adjusted.append(CandidateScore(**{**record, "recommended": False}))
    best_id = max(adjusted, key=lambda item: item.overall_score).candidate_action_id
    return tuple(CandidateScore(**{**score.as_record(), "recommended": score.candidate_action_id == best_id}) for score in adjusted)


def _lesson_bonus(action: CandidateAction, lessons: tuple[Mapping[str, Any], ...]) -> float:
    text = f"{action.description} {action.command_preview} {action.expected_domain}".lower()
    bonus = 0.0
    for lesson in lessons:
        recommended = str(lesson.get("recommended_future_action", "")).lower()
        if not recommended:
            continue
        tokens = tuple(token for token in recommended.replace("-", " ").split() if len(token) > 4)
        overlap = sum(1 for token in tokens if token in text)
        if overlap:
            bonus = max(bonus, min(0.24, overlap * 0.055 + float(lesson.get("usefulness_score", 0.0) or 0.0) * 0.08))
    return bonus


def _policy_lesson_present(lessons: tuple[Mapping[str, Any], ...]) -> bool:
    return any(str(lesson.get("domain", "")).lower() == "policy" or "policy" in str(lesson.get("recommended_future_action", "")).lower() for lesson in lessons)

def _policy_decision(action: CandidateAction, state: WorldState) -> Mapping[str, Any]:
    if action.requires_approval or action.policy_sensitive:
        mode = str(state.policy_state.get("mode", "supervised"))
        allowed = mode == "manual_approved"
        return {"allowed": allowed, "requires_approval": True, "mode": mode, "reason": "approval required for policy-sensitive action", "authority": "policy_engine_and_approval_gate"}
    return {"allowed": True, "requires_approval": False, "mode": str(state.policy_state.get("mode", "supervised")), "reason": "local diagnostic or simulation action", "authority": "policy_engine_and_approval_gate"}
