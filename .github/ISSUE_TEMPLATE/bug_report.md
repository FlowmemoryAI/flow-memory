---
name: Bug report
about: Report a reproducible Flow Memory defect
title: "bug: "
labels: bug
assignees: ""
---

## Summary

Describe the defect and the expected behavior.

## Reproduction

1.
2.
3.

## Observed result

Paste the exact error or unexpected output.

## Expected result

Describe the behavior that should have happened.

## Environment

- OS:
- Python version:
- Flow Memory version or commit:
- Optional services enabled, if any:

## Validation already run

```bash
python -m pytest -q
python -m flow_memory --json "Explore and report"
bash scripts/verify.sh
```

## Safety/security impact

Does this affect policy gating, sandboxing, audit logs, wallets, marketplace settlement, contracts, or private data?
