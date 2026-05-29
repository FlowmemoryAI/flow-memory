# Flow Memory Inference Proxy

The inference proxy is the one-line base URL adoption path. It exposes OpenAI-compatible local endpoints backed by a deterministic fake provider until external provider credentials are configured.

```mermaid
flowchart TD
    SDK[OpenAI-compatible SDK] --> BaseURL[Flow Memory base URL]
    BaseURL --> Auth[Flow Memory auth and scopes]
    Auth --> Policy[Spend, quality, and safety policy]
    Policy --> Market[Inference Market quote selection]
    Market --> Fake[Local fake provider]
    Market -. later .-> External[Allowlisted external provider]
    Fake --> Ledger[Usage ledger]
    Ledger --> Response[Compatible response]
```

## Endpoints

- `GET /v1/models`
- `POST /v1/chat/completions`
- `POST /inference/proxy`

## Credential boundary

```mermaid
flowchart LR
    Buyer[Buyer agent] --> Proxy[Flow Memory proxy]
    Proxy --> SecretRef[Provider credential reference]
    SecretRef --> Provider[Provider API]
    Buyer -. never sees .-> SecretRef
```

Raw provider credentials, private keys, seed phrases, live settlement flags, and broadcast flags are rejected.

## Local smoke

```bash
flow-memory inference proxy-smoke --model flow-local-small --task "hello" --json
```
