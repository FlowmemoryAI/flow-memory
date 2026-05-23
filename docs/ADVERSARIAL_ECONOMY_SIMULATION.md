# Adversarial Economy Simulation

The public-alpha simulation models local abuse patterns without real funds:

- honest baseline
- low-quality/underpriced work
- colluding verifier
- spam/overpriced bids
- reputation farming
- repeated disputes
- sybil-like duplicate agents

Run:

```bash
python examples/agent_economy_adversarial_sim_demo.py
```

Metrics include task success rate, dispute rate, slashing rate, verifier disagreement, reputation changes, economic loss proxy, and sybil risk flags. This is a deterministic prototype, not formal economic security proof.
