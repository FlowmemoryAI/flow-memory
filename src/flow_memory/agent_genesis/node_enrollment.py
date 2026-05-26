"""Optional local node enrollment metadata for the Human Compute Network."""
from __future__ import annotations

from typing import Any, Mapping


def node_enrollment_options() -> Mapping[str, Any]:
    return {
        "first_agent_requires_download": False,
        "optional_node_modes": ("private_local_tools", "private_compute", "compute_node_contributor"),
        "default_mode": "browser_or_local_replay",
        "safety": "node enrollment never enables funds, private keys, live settlement, or provider calls by default",
    }
