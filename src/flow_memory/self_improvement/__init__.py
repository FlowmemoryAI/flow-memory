"""Safety-gated self-improvement primitives."""

from flow_memory.self_improvement.diagnostics import DiagnosticFinding, DiagnosticsEngine
from flow_memory.self_improvement.evaluator import OutputScore, SelfEvaluator
from flow_memory.self_improvement.health import DEGRADATION_FLAGS, HealthMonitor, HealthReport
from flow_memory.self_improvement.repair_planner import RepairPlan, RepairPlanner, RepairStep

__all__ = [
    "DEGRADATION_FLAGS",
    "DiagnosticFinding",
    "DiagnosticsEngine",
    "HealthMonitor",
    "HealthReport",
    "OutputScore",
    "RepairPlan",
    "RepairPlanner",
    "RepairStep",
    "SelfEvaluator",
]
