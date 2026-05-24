"""RL metric aggregation."""
from __future__ import annotations
from typing import Mapping, Sequence

def aggregate_episode_metrics(episodes: Sequence[Mapping[str, float]]) -> dict[str, float]:
    if not episodes: return {"episode_count":0.0}
    keys=sorted({key for ep in episodes for key in ep})
    out={"episode_count":float(len(episodes))}
    for key in keys:
        out[f"mean_{key}"]=sum(float(ep.get(key,0.0)) for ep in episodes)/len(episodes)
    return out
