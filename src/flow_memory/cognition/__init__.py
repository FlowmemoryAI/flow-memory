"""Predictive cognitive core package."""
from flow_memory.cognition.evaluator import SurpriseEvaluator
from flow_memory.cognition.loop import CognitiveLoop
from flow_memory.cognition.counterfactuals import CounterfactualSet, build_counterfactual_set
from flow_memory.cognition.benchmarks import benchmark_scenarios, get_benchmark, list_benchmarks, run_predictive_learning_benchmark
from flow_memory.cognition.consolidation import ConsolidatedLesson, consolidate_experiences, get_lesson, list_lessons, query_lessons, retrieve_similar_lessons
from flow_memory.cognition.metrics import cognition_metrics
from flow_memory.cognition.experience import ExperienceRecord, get_experience, list_experiences, query_experiences, retrieve_similar_experiences, write_experience
from flow_memory.cognition.prediction import CandidateAction, PredictionRecord
from flow_memory.cognition.prediction_error import PredictionErrorRecord, compute_prediction_error
from flow_memory.cognition.state import WorldState, build_world_state
from flow_memory.cognition.reasoner import RuleBasedReasoner, SimpleReasoner
from flow_memory.cognition.world_model import DeterministicWorldModel

__all__ = [
    "CandidateAction",
    "CognitiveLoop",
    "ConsolidatedLesson",
    "CounterfactualSet",
    "DeterministicWorldModel",
    "ExperienceRecord",
    "PredictionErrorRecord",
    "PredictionRecord",
    "RuleBasedReasoner",
    "SimpleReasoner",
    "SurpriseEvaluator",
    "WorldState",
    "build_counterfactual_set",
    "benchmark_scenarios",
    "build_world_state",
    "compute_prediction_error",
    "cognition_metrics",
    "consolidate_experiences",
    "get_experience",
    "get_benchmark",
    "list_experiences",
    "get_lesson",
    "list_benchmarks",
    "query_experiences",
    "list_lessons",
    "retrieve_similar_experiences",
    "write_experience",
    "query_lessons",
    "retrieve_similar_lessons",
    "run_predictive_learning_benchmark",
]
