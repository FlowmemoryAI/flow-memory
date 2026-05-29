# Inference Market risk notes

Inference resale may be constrained by provider terms, account-transfer rules, tax treatment, privacy obligations, and abuse controls. Flow Memory currently implements this as dry-run planning and deterministic local simulation only.

```mermaid
flowchart LR
    Credits[Unused credits] --> Terms[Provider terms review]
    Terms --> Policy[Flow Memory policy]
    Policy --> DryRun[Dry-run listing]
    DryRun --> Audit[Audit event]
```

No production resale should be enabled until provider terms, legal review, compliance review, and security review are complete.
