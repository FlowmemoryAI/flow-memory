# Economy V2

Status: functional local prototype.

## Local lifecycle

`AgentEconomyV2` implements a full local task lifecycle:

1. requester creates task;
2. agents place bids;
3. requester assigns a bid;
4. requester funds local escrow;
5. assigned agent submits work;
6. requester/verifier accepts or rejects work;
7. accepted work settles local escrow;
8. reputation updates;
9. audit events record every phase.

Failure path:

1. work is rejected;
2. requester opens a dispute;
3. dispute is resolved;
4. local escrow is refunded or released;
5. agent reputation is slashed or lightly credited;
6. audit events capture the sequence.

## Implemented files

- `src/flow_memory/economy/economy_v2.py`
- `src/flow_memory/economy/escrow.py`
- `src/flow_memory/economy/dispute.py`
- `src/flow_memory/economy/attestations.py`
- `src/flow_memory/economy/slashing.py`
- `src/flow_memory/economy/settlement.py`
- `src/flow_memory/economy/pricing.py`
- `src/flow_memory/economy/incentives.py`

## Safety boundary

No real keys, token transfers, chain transactions, or mainnet/testnet deployment are used by default. Wallet and escrow behavior is local accounting only.

## Next work

- Add multi-verifier settlement policy.
- Add typed dispute windows and evidence schemas.
- Integrate policy approvals for value-bearing actions.
- Connect to Web3/Base only after tests, simulation, and audit.
