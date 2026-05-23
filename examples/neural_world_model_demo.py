from __future__ import annotations

import json

from flow_memory.neural import is_torch_available

if not is_torch_available():
    print(json.dumps({"ok": True, "skipped": True, "reason": "torch not installed"}, indent=2))
else:
    from flow_memory.neural.perception.dual_stream import TinyDualStreamEncoder
    from flow_memory.neural.training.synthetic_motion_dataset import SyntheticMotionDataset
    from flow_memory.neural.world_model.jepa import TinyJEPAWorldModel

    video, _sample = SyntheticMotionDataset(size=1).as_torch(0)
    features = TinyDualStreamEncoder()(video)
    prediction = TinyJEPAWorldModel().predict(features)
    print(json.dumps(prediction.as_record(), indent=2))
