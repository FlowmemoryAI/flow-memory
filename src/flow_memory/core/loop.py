"""Cognitive loop implementation."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

from flow_memory.action.executor import ActionExecutor
from flow_memory.core.types import ActionResult, CognitiveCycleResult, Observation
from flow_memory.economy.layer import EconomicLayer
from flow_memory.evaluation.evaluator import SurpriseEvaluator
from flow_memory.learning.learner import OnlineLearner
from flow_memory.memory.system import MemorySystem
from flow_memory.perception.dual_stream import DualStreamPerception
from flow_memory.reasoning.planner import SimpleReasoner
from flow_memory.safety.system import SafetySystem
from flow_memory.world_model.predictive import PredictiveWorldModel


@dataclass
class CognitiveLoop:
    """perceive → predict → remember → reason → act → evaluate → learn → transact."""

    perception: DualStreamPerception = field(default_factory=DualStreamPerception)
    world_model: PredictiveWorldModel = field(default_factory=PredictiveWorldModel)
    memory: MemorySystem = field(default_factory=MemorySystem)
    reasoner: SimpleReasoner = field(default_factory=SimpleReasoner)
    safety: SafetySystem = field(default_factory=SafetySystem)
    executor: ActionExecutor = field(default_factory=ActionExecutor)
    evaluator: SurpriseEvaluator = field(default_factory=SurpriseEvaluator)
    learner: OnlineLearner = field(default_factory=OnlineLearner)
    economy: EconomicLayer = field(default_factory=EconomicLayer)

    def run(self, observation: Observation | str) -> CognitiveCycleResult:
        if isinstance(observation, str):
            observation = Observation(content=observation)

        perception = self.perception.process(observation)
        self.memory.consolidate_perception(perception)

        prediction = self.world_model.forecast(perception)

        self.memory.observe(
            text=observation.as_text(),
            kind="observation",
            payload={"modality": observation.modality, "source": observation.source},
        )
        memories = self.memory.retrieve_relevant(perception, prediction)

        plan = self.reasoner.generate_plan(observation, perception, prediction, memories)

        decision = self.safety.approve(plan)
        if decision.approved:
            self.executor.memory_snapshot = self.memory.working.snapshot()
            result = self.executor.execute(plan)
        else:
            result = ActionResult(
                success=False,
                output="Plan rejected by safety policy",
                error="; ".join(decision.reasons),
            )
        self.safety.record_action_result(plan, asdict(result))

        evaluation = self.evaluator.measure(prediction, result)

        learned = self.learner.update(evaluation, plan, result)
        self.memory.observe(
            text=f"Cycle result success={result.success} surprise={evaluation.surprise_score}",
            kind="evaluation",
            payload={"plan_id": plan.plan_id, "result_id": result.result_id},
        )

        economic_settlement = None
        if plan.has_economic_value:
            economic_settlement = self.economy.settle(plan, result)
            self.memory.economic.record_transaction(economic_settlement)

        return CognitiveCycleResult(
            observation=observation,
            perception=perception,
            prediction=prediction,
            retrieved_memories=memories,
            plan=plan,
            policy_decision=decision,
            action_result=result,
            evaluation=evaluation,
            learned=learned,
            economic_settlement=economic_settlement,
        )
