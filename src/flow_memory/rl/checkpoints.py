"""JSON-only policy checkpoints."""
from __future__ import annotations
import json
from pathlib import Path
from flow_memory.rl.policies import TabularQPolicy

class CheckpointStore:
    def __init__(self, root: str|Path="artifacts/rl/checkpoints"):
        self.root=Path(root); self.root.mkdir(parents=True, exist_ok=True)
    def save_policy(self, name:str, policy:TabularQPolicy)->Path:
        path=self.root/f"{name}.json"; path.write_text(json.dumps(policy.as_record(), indent=2, sort_keys=True), encoding='utf-8'); return path
    def load_policy(self, name:str)->TabularQPolicy:
        return TabularQPolicy.from_record(json.loads((self.root/f"{name}.json").read_text(encoding='utf-8')))
