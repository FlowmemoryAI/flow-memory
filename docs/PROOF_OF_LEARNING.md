# Proof of Learning

Proof of Learning is Flow Memory's evidence record for prediction-driven improvement.

A proof record exists when the system can show:

1. A state and goal existed.
2. The agent made a prediction before acting.
3. A policy-approved action or simulation was selected.
4. The actual outcome was observed.
5. Prediction error was computed.
6. A lesson was written or reused.
7. Private payloads stayed excluded.

This is different from proof of work. The value is not raw compute alone; it is structured experience that reduces repeated mistakes in observable local domains.

## What is scored

Learning reputation uses local proof records to report:

- prediction accuracy
- confidence calibration
- policy compliance
- lesson usefulness
- repeated mistake reduction
- safe contribution behavior
- proof count

Policy compliance remains a first-class metric. Neural and cognition scores are advisory; PolicyEngine and ApprovalGate remain authoritative.

## Commands

```powershell
python -m flow_memory graph build --json
python -m flow_memory graph proofs list --json
python -m flow_memory graph proofs show <proof_id> --json
python -m flow_memory graph reputation list --json
python -m flow_memory graph reputation show <agent_id> --json
```

## Release evidence

The public-alpha evidence bundle includes `release_evidence/bundle/experience_graph_proof_of_learning.json` after export.

Release decision:

```powershell
python scripts/release_decision.py --target public-alpha-proof-of-learning
```

## Privacy and safety

Proof of Learning records are built from sanitized structured fields. Raw private payload, private keys, secrets, tokens, private memory, live provider calls, funds movement, and live settlement are not part of this public-alpha ledger.

This does not claim AGI, consciousness, production autonomy, or arbitrary real-world future prediction. It is an inspectable learning-evidence mechanism for local Flow Memory traces.
