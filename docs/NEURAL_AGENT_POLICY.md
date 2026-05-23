# Neural Agent Policy

The neural policy layer is advisory only.

Implemented:
- `TinyAgentPolicyNetwork` for optional torch scoring.
- `TinyPlanScorer` for expected success/cost/risk/memory similarity.
- `TinySkillRouter` for capability/history/reputation/risk/cost ranking.
- `TinyRiskModel` for unsafe/economic/failure likelihoods.
- `TinyNeuralEvaluator` for quality/compliance/novelty/memory/economic value scoring.

Neural scoring cannot override policy or approval gates. Tests enforce this.
