# BYOK model keys

Flow Memory BYOK is an optional post-Genesis capability. The first agent does not require wallet/API key/funds.

BYOK lets an existing policy-gated agent reference a user-owned provider credential without storing or printing the raw key in Flow Memory artifacts.

## Public-alpha behavior

- Optional after Agent Genesis.
- Secret refs and stable fingerprints only.
- No raw API key in repo files, artifacts, logs, replay, memory, dashboard HTML, or release evidence.
- Simulated inference intents by default.
- No external provider call is performed by the local public-alpha path.
- Credentials can be revoked.
- Emergency stop disables future BYOK usage.

```mermaid
flowchart LR
  User[User] --> Agent[Existing Agent]
  Agent --> Bind[Bind Credential Ref]
  Bind --> Redact[Redact And Fingerprint]
  Redact --> Store[Store Metadata Only]
  Store --> Intent[Simulated BYOK Intent]
  Intent --> Policy[Policy Review]
  Policy --> Result[No Provider Call]
```

## CLI examples

```powershell
python -m flow_memory byok providers list --json
python -m flow_memory byok credentials bind --agent genesis_agent_11b7e7b435abc729711373b0 --provider openai --secret-ref env:OPENAI_API_KEY --json
python -m flow_memory byok credentials list --agent genesis_agent_11b7e7b435abc729711373b0 --json
python -m flow_memory byok intent simulate --agent genesis_agent_11b7e7b435abc729711373b0 --provider openai --model gpt-4.1-mini --purpose "research" --json
```

## Limitations

This is not production autonomous model execution. Provider calls remain disabled in the default public-alpha path until a reviewed executor is added.
