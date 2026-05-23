# Appearance-Invariant Dorsal Stream

The dorsal stream contract is implemented in `flow_memory.perception.dorsal_stream.DorsalStream`.

The encoder applies five constraints:

1. `TemporalConsistency`
2. `OpticalFlowInvariance`
3. `DepthConsistency`
4. `EgomotionCompensation`
5. `AppearanceSuppression`

The local implementation uses lexical motion cues and structured frame-delta proxies. It marks generated trajectories as `appearance_free=True` and emits `MotionGeometry.invariances` so downstream tests and adapters can enforce the requirement that motion geometry does not depend solely on static texture, color, or object appearance.

Production adapters should replace the local `MotionEncoder` with:

- optical-flow estimation
- monocular or stereo depth consistency
- camera-pose/egomotion compensation
- temporal predictive objectives
- V-JEPA/VideoMAE-style latent prediction
- appearance ablations and evaluation datasets
