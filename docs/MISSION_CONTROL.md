# Flow Memory Mission Control

Mission Control is the first visual operating layer for the Flow Memory human compute network.

It is connected to local Flow Memory state through:

1. local network scenario reports,
2. visual event adapters,
3. a reducer that builds `VisualNetworkState`,
4. replay export JSON,
5. dependency-free local API endpoints,
6. dashboard TypeScript components.

## What is real today

- Local agents are real `AgentProfile` / `AgentRunner` objects.
- Economy flows use local simulated accounting and Economy V3 receipts.
- Neural signals come from the current advisory metadata path and clearly skip when Torch is absent.
- RL signals come from Flow Arena local training/evaluation metadata.
- Safety gates come from policy/approval decisions or approval-required scenario records.
- Audit events come from network receipts and API/router audit events.

## What remains public-alpha scaffold

- The frontend is a dependency-light TypeScript scaffold, not a hosted production app.
- Live mode uses polling endpoints; SSE/WebSocket streaming is future work.
- The 3D components are structural and data-mapped; a full Three.js render shell is future work.

## Safety claim

Mission Control visualizes decisions. It does not authorize action. PolicyEngine and ApprovalGate remain authoritative.
