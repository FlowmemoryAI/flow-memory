# Flow arena mapping for future PufferLib work

| Flow Memory environment | Puffer/Ocean mapping | Native C candidate | Notes |
| --- | --- | --- | --- |
| FlowEnv | Single-agent environment | Later | General cognitive-loop RL harness. |
| EconomyMarketEnv | Multi-agent marketplace env | Yes | Stress bidding, settlement, disputes, slashing. |
| SafetyGateEnv | Policy gate env | Yes | Learn safe routing while policy remains authoritative. |
| SwarmDelegationEnv | Multi-agent env | Yes | Delegation, verifier selection, coalition formation. |

No Puffer code is vendored here.
