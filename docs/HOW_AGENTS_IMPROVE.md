# How Agents Improve

Flow Memory uses several improvement layers today:

1. Immediate cycle learning: each run records outcome, evaluation, surprise, audit events, and memory writes.
2. Memory learning: prior traces become retrievable context for future runs.
3. Procedural learning: successful plans and skill outcomes are stored as local records.
4. RL Arena learning: tabular/Q-learning policies improve in simulated Flow Arena environments.
5. Neural training lane: tiny PyTorch models can be trained on synthetic/local traces when optional ML dependencies are installed.

What this is not:

- It is not autonomous unsafe self-modification.
- It is not production ML quality.
- It is not a claim that agents are biologically equivalent to humans.
- It does not override safety policy or human approvals.
