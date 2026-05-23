from __future__ import annotations

import json

from flow_memory.agents.profile import AgentProfile
from flow_memory.agents.runner import AgentRunner


profile = AgentProfile(name="NeuralDemo", allowed_tools=("respond",), neural_config={"backend": "none"})
result = AgentRunner(profile).run_cycle("Explore and report with neural advisory metadata")
print(json.dumps(result.output["neural"], indent=2))
