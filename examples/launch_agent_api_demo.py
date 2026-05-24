from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from flow_memory.api.http_server import HttpApiConfig, HttpApiGateway
from flow_memory.swarm.agent_card import AgentCard


def run_demo() -> dict[str, object]:
    gateway = HttpApiGateway(config=HttpApiConfig(api_key="dev-local-only", require_scopes=True, enable_rate_limit=True))
    gateway.router.register_agent(AgentCard(did="did:flow:api-demo", name="API Demo Agent", capabilities=("local_reasoning",), reputation=1.0))
    headers = {"x-flow-memory-api-key": "dev-local-only", "x-flow-memory-scopes": "api:read api:write"}
    health = gateway.handle("GET", "/health", headers=headers)
    agents = gateway.handle("GET", "/agents", headers=headers)
    run = gateway.handle("POST", "/agents/did:flow:api-demo/run", headers=headers, body=json.dumps({"goal": "Explore and report"}).encode("utf-8"))
    return {
        "ok": health.status == 200 and agents.status == 200 and run.status == 200,
        "launch_mode": "api",
        "health": health.body,
        "agents": agents.body,
        "run": run.body,
        "audit_events": len(gateway.audit_sink.events),
    }


if __name__ == "__main__":
    print(json.dumps(run_demo(), indent=2, sort_keys=True, default=str))
