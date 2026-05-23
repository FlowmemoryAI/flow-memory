# Neural Architecture

Flow Memory Neural Agent Layer v1 adds optional PyTorch-backed prototypes around the existing agent OS:

```
FlowLang neural config -> AgentProfile.neural_config -> AgentNeuralBinding
    -> neural memory retrieval
    -> plan scoring / skill routing / risk scoring
    -> optional tiny_torch perception and world model
    -> audit-friendly neural metadata
```

Tensor conventions:
- video: `[B, T, C, H, W]`
- latent tokens: `[B, N, D]`
- trajectory: `[B, T, 2]`
- flow proxy: `[B, T-1, 2, H, W]`

Ventral features are appearance/semantic-oriented. Dorsal features suppress appearance and emphasize silhouette, centroid trajectory, frame deltas, flow proxy, depth proxy, and egomotion proxy.
