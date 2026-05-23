"""Cognition package matching the public architecture tree."""

from flow_memory.core.loop import CognitiveLoop
from flow_memory.evaluation.evaluator import SurpriseEvaluator
from flow_memory.reasoning.planner import SimpleReasoner

RuleBasedReasoner = SimpleReasoner

__all__ = ["CognitiveLoop", "RuleBasedReasoner", "SimpleReasoner", "SurpriseEvaluator"]
