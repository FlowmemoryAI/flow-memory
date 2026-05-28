# Agent Collaboration Protocol

The Agent Collaboration Protocol records local, policy-gated collaboration proposals and sessions between Flow Memory agent nodes.

It does not allow agents to bypass approval. Shared workspaces store structured summaries and audit events, not hidden reasoning or raw private memory.

## Lifecycle

```mermaid
stateDiagram-v2
  [*] --> Proposed
  Proposed --> PolicyReview
  PolicyReview --> Accepted: policy approved
  PolicyReview --> Denied: policy denied
  Accepted --> WorkspaceOpen
  WorkspaceOpen --> Completed: artifacts and lessons recorded
  WorkspaceOpen --> Failed: task failed or canceled
  Denied --> [*]
  Completed --> [*]
  Failed --> [*]
```

## Collaboration sequence

```mermaid
sequenceDiagram
  participant A as Requester agent
  participant M as Skill matcher
  participant P as Policy gate
  participant B as Candidate agent
  participant W as Shared workspace
  participant G as Project graph

  A->>M: find collaborator for task
  M-->>A: recommended candidate
  A->>P: propose collaboration
  P-->>A: approval required and safe fields
  A->>B: structured proposal summary
  B-->>W: accepted session metadata
  W->>G: project, skill, artifact, lesson edges
```

## Records

`CollaborationRequest` contains requester, candidate, task, required skills, proposed role, workspace id, policy requirements, optional dry-run payment intent, status, and creation time.

`CollaborationSession` contains participating agents, roles, workspace id, task id, project id, policy state, messages summary, artifacts, experience references, reputation events, and completion time.

## CLI

```bash
python -m flow_memory internet collaborations propose --from internet-alpha --to internet-beta --task "build skill matcher" --required-skill coding --json
python -m flow_memory internet collaborations list --json
python -m flow_memory internet workspace show <workspace_id> --json
```
