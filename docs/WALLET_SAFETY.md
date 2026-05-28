# Wallet safety

Flow Memory wallet support is an optional identity binding for existing agents. The first agent does not require wallet/API key/funds.

## Safety rules

- No private keys.
- No seed phrases.
- No funds movement.
- No transaction broadcast.
- Mainnet writes disabled.
- Token approvals disabled.
- Signing is an external wallet/user action only.
- Relay is disabled by default.
- PolicyEngine and ApprovalGate remain authoritative.
- Emergency stop can disable BYOK, wallet, on-chain, provider, and future execution modes.

```mermaid
flowchart LR
  Agent[Existing Agent] --> Wallet[Address Only Wallet Binding]
  Wallet --> Policy[Policy Gate]
  Policy --> Sim[Simulation]
  Sim --> Sign[External Sign Request]
  Sign --> Relay[Relay Disabled]
  Stop[Emergency Stop] --> Wallet
  Stop --> Sign
  Stop --> Relay
```

## Emergency stop

```mermaid
sequenceDiagram
  participant U as User
  participant A as Agent
  participant C as CapabilityRegistry
  participant O as OnchainIntent
  U->>C: Activate emergency stop
  C->>A: Mark upgrades stopped
  C->>O: Block signing and relay paths
  O-->>U: Future execution disabled
```

## Dashboard

Mission Control shows a capability panel with:

- BYOK provider registry and fingerprinted credential status.
- Wallet binding status.
- Base Sepolia default and mainnet write disabled state.
- On-chain dry-run prepare/simulate/approval/sign-request/relay stages.
- Emergency stop status.
- Agent Internet capability projection.
