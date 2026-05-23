# Contributing

Flow Memory is intentionally modular. Contributions should preserve the cognitive-loop boundary between perception, memory, reasoning, action, evaluation, learning, and economic settlement.

## Development flow

1. Fork the repository.
2. Create a feature branch.
3. Add tests for behavior changes.
4. Run:

```bash
python -m unittest discover -s tests
```

5. Open a pull request with a concise description of the architecture impact.

## Design rules

- Keep high-risk execution behind typed permissions.
- Do not introduce hidden network calls into the core loop.
- Keep external systems behind adapters.
- Prefer deterministic tests for kernel components.
- Mark experimental neural, blockchain, or robotics integrations as optional extras.
