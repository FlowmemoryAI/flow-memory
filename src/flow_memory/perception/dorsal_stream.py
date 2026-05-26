"""Dorsal stream: motion, spatial structure, depth proxies, and affordances.

The default implementation is deterministic and dependency-light. It provides a testable
appearance-invariant contract for future V-JEPA/VideoMAE/optical-flow/depth backends:
outputs depend on motion and geometry rather than texture, color, or object labels.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field, replace
from typing import Any, Mapping, Protocol, Sequence, cast

from flow_memory.core.types import MotionGeometry, Observation

_WORD_RE = re.compile(r"[A-Za-z][A-Za-z0-9_-]*")
_MOTION_TERMS = {
    "move", "moving", "motion", "navigate", "navigation", "walk", "run", "explore",
    "track", "trajectory", "avoid", "grasp", "manipulate", "rotate", "translate",
    "flow", "approach", "retreat",
}
_ACTION_AFFORDANCES = {
    "explore": "navigate",
    "report": "communicate",
    "find": "search",
    "search": "search",
    "grasp": "manipulate",
    "manipulate": "manipulate",
    "avoid": "collision_avoidance",
    "move": "locomote",
    "moving": "track_motion",
    "navigate": "locomote",
    "track": "track_motion",
}


class InvarianceConstraint(Protocol):
    name: str

    def enforce(self, motion: MotionGeometry) -> MotionGeometry:
        ...


def _add_invariance(motion: MotionGeometry, name: str) -> MotionGeometry:
    invariances = list(motion.invariances)
    if name not in invariances:
        invariances.append(name)
    return replace(motion, invariances=tuple(invariances))


@dataclass(frozen=True)
class TemporalConsistency:
    name: str = "temporal_consistency"

    def enforce(self, motion: MotionGeometry) -> MotionGeometry:
        return _add_invariance(motion, self.name)


@dataclass(frozen=True)
class OpticalFlowInvariance:
    name: str = "optical_flow_invariance"

    def enforce(self, motion: MotionGeometry) -> MotionGeometry:
        return _add_invariance(motion, self.name)


@dataclass(frozen=True)
class DepthConsistency:
    name: str = "depth_consistency"

    def enforce(self, motion: MotionGeometry) -> MotionGeometry:
        return _add_invariance(motion, self.name)


@dataclass(frozen=True)
class EgomotionCompensation:
    name: str = "egomotion_compensation"

    def enforce(self, motion: MotionGeometry) -> MotionGeometry:
        return _add_invariance(motion, self.name)


@dataclass(frozen=True)
class AppearanceSuppression:
    name: str = "appearance_suppression"

    def enforce(self, motion: MotionGeometry) -> MotionGeometry:
        return _add_invariance(motion, self.name)


@dataclass
class MotionEncoder:
    """Dependency-light motion encoder with a future optical-flow adapter seam."""

    min_motion_energy: float = 0.03

    def encode_frames(self, frames: Sequence[Any]) -> MotionGeometry:
        raw_grids = [_to_grayscale_grid(frame) for frame in frames]
        raw_grids = [grid for grid in raw_grids if grid]
        if len(raw_grids) < 2:
            return MotionGeometry(confidence=0.05)
        normalized = [_normalize_grid(grid) for grid in raw_grids]

        trajectories: list[Mapping[str, Any]] = []
        energies: list[float] = []
        centroids: list[tuple[float, float]] = []
        signature_steps: list[Mapping[str, Any]] = []
        for idx in range(1, len(normalized)):
            energy, centroid = _motion_energy_and_centroid(normalized[idx - 1], normalized[idx])
            signature_centroid = _appearance_invariant_delta_centroid(normalized[idx - 1], normalized[idx])
            if energy < self.min_motion_energy:
                raw_energy, raw_centroid = _relative_raw_motion_energy(raw_grids[idx - 1], raw_grids[idx])
                if raw_energy > energy:
                    energy, centroid = raw_energy, raw_centroid
            energies.append(energy)
            centroids.append(centroid)
            if energy >= self.min_motion_energy:
                appearance_free_centroid = signature_centroid or centroid
                signature_steps.append(
                    {
                        "frame_from": idx - 1,
                        "frame_to": idx,
                        "centroid_yx": (round(appearance_free_centroid[0], 4), round(appearance_free_centroid[1], 4)),
                    }
                )
                trajectories.append(
                    {
                        "source": "frame_delta_proxy",
                        "method": "appearance_suppressed_or_relative_frame_delta",
                        "frame_from": idx - 1,
                        "frame_to": idx,
                        "motion_energy": round(energy, 6),
                        "centroid_yx": (round(centroid[0], 4), round(centroid[1], 4)),
                        "appearance_invariant_centroid_yx": (
                            round(appearance_free_centroid[0], 4),
                            round(appearance_free_centroid[1], 4),
                        ),
                        "appearance_free": True,
                        "confidence": 0.8,
                    }
                )

        mean_energy = sum(energies) / len(energies) if energies else 0.0
        translation = _centroid_translation(centroids)
        affordances: list[str] = []
        motion_signature = _motion_signature(signature_steps)
        if trajectories:
            affordances.append("track_motion")
        if translation > 0.05 or mean_energy > 0.15:
            affordances.append("navigate")
        if mean_energy > 0.35:
            affordances.append("collision_avoidance")
        confidence = min(0.95, 0.25 + mean_energy * 0.6 + 0.08 * len(trajectories))
        return MotionGeometry(
            trajectories=tuple(trajectories),
            affordances=tuple(dict.fromkeys(affordances)),
            spatial_relations=(
                {
                    "source": "frame_delta_proxy",
                    "mean_motion_energy": round(mean_energy, 6),
                    "centroid_translation": round(translation, 6),
                    "appearance_invariant_signature": motion_signature,
                    "trajectory_summary": motion_signature["trajectory"],
                },
            ),
            confidence=round(confidence, 6),
        )

    def encode_object_positions(self, objects: Sequence[Mapping[str, Any]]) -> MotionGeometry:
        trajectories: list[Mapping[str, Any]] = []
        total_distance = 0.0
        for idx, obj in enumerate(objects):
            positions = obj.get("positions") or obj.get("trajectory")
            points = _clean_points(positions)
            if len(points) < 2:
                continue
            path_length = sum(_point_distance(a, b) for a, b in zip(points, points[1:]))
            displacement = _point_distance(points[0], points[-1])
            total_distance += path_length
            signature_steps = _signature_steps_from_points(points)
            trajectories.append(
                {
                    "source": "structured_object_positions",
                    "entity_id": str(obj.get("id") or obj.get("label") or f"object_{idx}"),
                    "start": points[0],
                    "end": points[-1],
                    "frame_delta": len(points) - 1,
                    "path_length": round(path_length, 6),
                    "displacement": round(displacement, 6),
                    "appearance_free": True,
                    "appearance_invariant_signature": _motion_signature(signature_steps),
                    "confidence": 0.8,
                }
            )
        if not trajectories:
            return MotionGeometry(confidence=0.05)
        affordances = ["track_motion", "predict_motion"]
        if total_distance > 1.0:
            affordances.append("navigate")
        return MotionGeometry(
            trajectories=tuple(trajectories),
            affordances=tuple(affordances),
            spatial_relations=(
                {
                    "source": "structured_object_positions",
                    "moving_entities": tuple(item["entity_id"] for item in trajectories),
                    "total_path_length": round(total_distance, 6),
                    "appearance_invariant_signature": _motion_signature(
                        tuple(step for item in trajectories for step in item["appearance_invariant_signature"]["steps"])
                    ),
                },
            ),
            confidence=round(min(0.95, 0.55 + 0.08 * len(trajectories) + min(0.2, total_distance * 0.03)), 6),
        )

    def encode_text(self, text: str) -> MotionGeometry:
        tokens = [token.lower() for token in _WORD_RE.findall(text)]
        motion_hits = [token for token in tokens if token in _MOTION_TERMS]
        affordances: list[str] = []
        for token in tokens:
            affordance = _ACTION_AFFORDANCES.get(token)
            if affordance and affordance not in affordances:
                affordances.append(affordance)
        trajectories = tuple(
            {
                "source": "lexical_motion_prior",
                "motion_cue": token,
                "appearance_free": True,
                "confidence": 0.55,
            }
            for token in motion_hits[:8]
        )
        confidence = 0.2 + min(0.7, len(motion_hits) * 0.12 + len(affordances) * 0.08)
        return MotionGeometry(
            trajectories=trajectories,
            affordances=tuple(affordances),
            spatial_relations=(),
            confidence=round(confidence, 6),
        )


def _default_invariance_constraints() -> tuple[InvarianceConstraint, ...]:
    return cast(
        tuple[InvarianceConstraint, ...],
        (
            TemporalConsistency(),
            OpticalFlowInvariance(),
            DepthConsistency(),
            EgomotionCompensation(),
            AppearanceSuppression(),
        ),
    )


@dataclass
class AppearanceInvariantDorsalStream:
    """Motion/spatial encoder that enforces dorsal-stream invariance constraints."""

    motion_encoder: MotionEncoder = field(default_factory=MotionEncoder)
    invariance_constraints: Sequence[InvarianceConstraint] = field(default_factory=_default_invariance_constraints)

    def encode(self, observation: Observation | str | Mapping[str, Any]) -> MotionGeometry:
        if isinstance(observation, str):
            observation = Observation(content=observation)
        elif isinstance(observation, Mapping):
            modality = str(observation.get("modality") or ("video" if "frames" in observation else "structured"))
            observation = Observation(content=observation, modality=modality)

        objects = _extract_objects_with_positions(observation.content)
        frames = _extract_frames(observation.content)
        if objects:
            motion = self.motion_encoder.encode_object_positions(objects)
        elif frames:
            motion = self.motion_encoder.encode_frames(frames)
        else:
            motion = self.motion_encoder.encode_text(observation.as_text().lower())

        requested = _extract_requested_affordances(observation.content)
        if requested:
            motion = replace(motion, affordances=tuple(dict.fromkeys([*motion.affordances, *requested])))

        for constraint in self.invariance_constraints:
            motion = constraint.enforce(motion)
        return motion


DorsalStream = AppearanceInvariantDorsalStream


def _extract_objects_with_positions(content: Any) -> list[Mapping[str, Any]]:
    if not isinstance(content, Mapping):
        return []
    objects = content.get("objects") or content.get("entities") or []
    if not isinstance(objects, Sequence) or isinstance(objects, (str, bytes)):
        return []
    return [obj for obj in objects if isinstance(obj, Mapping) and ("positions" in obj or "trajectory" in obj)]


def _extract_requested_affordances(content: Any) -> list[str]:
    if not isinstance(content, Mapping):
        return []
    raw = content.get("affordances", [])
    if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes)):
        return []
    return [str(item) for item in raw]


def _extract_frames(content: Any) -> list[Any]:
    if isinstance(content, Mapping):
        frames = content.get("frames")
        if isinstance(frames, Sequence) and not isinstance(frames, (str, bytes)):
            return list(frames)
    if isinstance(content, Sequence) and not isinstance(content, (str, bytes)) and content:
        first = content[0]
        if isinstance(first, Sequence) and not isinstance(first, (str, bytes)):
            return list(content)
    return []


def _to_grayscale_grid(frame: Any) -> list[list[float]]:
    if hasattr(frame, "tolist"):
        frame = frame.tolist()
    if not isinstance(frame, Sequence) or isinstance(frame, (str, bytes)):
        return []
    grid: list[list[float]] = []
    for row in frame:
        if hasattr(row, "tolist"):
            row = row.tolist()
        if not isinstance(row, Sequence) or isinstance(row, (str, bytes)):
            continue
        out_row = [_numeric_cell(cell) for cell in row]
        if out_row:
            grid.append(out_row)
    width = min((len(row) for row in grid), default=0)
    return [row[:width] for row in grid if width > 0 and len(row) >= width]


def _numeric_cell(cell: Any) -> float:
    if hasattr(cell, "tolist"):
        cell = cell.tolist()
    if isinstance(cell, (int, float)) and not isinstance(cell, bool):
        return float(cell)
    if isinstance(cell, Sequence) and not isinstance(cell, (str, bytes)):
        values = [_numeric_cell(value) for value in cell]
        values = [value for value in values if math.isfinite(value)]
        return sum(values) / len(values) if values else 0.0
    return 0.0


def _normalize_grid(grid: list[list[float]]) -> list[list[float]]:
    values = [value for row in grid for value in row]
    if not values:
        return []
    mean = sum(values) / len(values)
    variance = sum((value - mean) ** 2 for value in values) / len(values)
    std = math.sqrt(variance) or 1.0
    return [[(value - mean) / std for value in row] for row in grid]


def _appearance_invariant_delta_centroid(
    previous: list[list[float]], current: list[list[float]]
) -> tuple[float, float] | None:
    height = min(len(previous), len(current))
    width = min((len(previous[0]) if previous else 0), (len(current[0]) if current else 0))
    if height == 0 or width == 0:
        return None
    diffs = [abs(current[y][x] - previous[y][x]) for y in range(height) for x in range(width)]
    max_diff = max(diffs, default=0.0)
    if max_diff == 0.0:
        return None
    threshold = max(0.25, max_diff * 0.2)
    count = 0
    weighted_y = 0.0
    weighted_x = 0.0
    for y in range(height):
        for x in range(width):
            if abs(current[y][x] - previous[y][x]) >= threshold:
                count += 1
                weighted_y += y
                weighted_x += x
    if count == 0:
        return None
    return weighted_y / count / max(1, height - 1), weighted_x / count / max(1, width - 1)


def _signature_steps_from_points(points: Sequence[Sequence[float]]) -> tuple[Mapping[str, Any], ...]:
    if len(points) < 2:
        return ()
    return tuple(
        {
            "frame_from": idx,
            "frame_to": idx + 1,
            "centroid_yx": (round(float(end[0]), 4), round(float(end[1] if len(end) > 1 else 0.0), 4)),
        }
        for idx, end in enumerate(points[1:])
    )


def _motion_signature(steps: Sequence[Mapping[str, Any]]) -> Mapping[str, Any]:
    path = tuple(step["centroid_yx"] for step in steps if "centroid_yx" in step)
    displacement = _point_distance(path[0], path[-1]) if len(path) >= 2 else 0.0
    mean_step = 0.0
    if len(path) >= 2:
        distances = [_point_distance(a, b) for a, b in zip(path, path[1:])]
        mean_step = sum(distances) / len(distances)
    return {
        "version": "appearance-invariant-motion-v1",
        "appearance_free": True,
        "steps": tuple(steps),
        "trajectory": {
            "path_yx": path,
            "step_count": len(path),
            "displacement": round(displacement, 6),
            "mean_step": round(mean_step, 6),
        },
    }


def _motion_energy_and_centroid(
    previous: list[list[float]], current: list[list[float]]
) -> tuple[float, tuple[float, float]]:
    height = min(len(previous), len(current))
    width = min((len(previous[0]) if previous else 0), (len(current[0]) if current else 0))
    if height == 0 or width == 0:
        return 0.0, (0.0, 0.0)
    total = 0.0
    weighted_y = 0.0
    weighted_x = 0.0
    for y in range(height):
        for x in range(width):
            diff = abs(current[y][x] - previous[y][x])
            total += diff
            weighted_y += y * diff
            weighted_x += x * diff
    denom = height * width
    energy = total / denom if denom else 0.0
    if total == 0:
        return 0.0, (0.0, 0.0)
    return energy, (weighted_y / total / max(1, height - 1), weighted_x / total / max(1, width - 1))


def _relative_raw_motion_energy(
    previous: list[list[float]], current: list[list[float]]
) -> tuple[float, tuple[float, float]]:
    height = min(len(previous), len(current))
    width = min((len(previous[0]) if previous else 0), (len(current[0]) if current else 0))
    if height == 0 or width == 0:
        return 0.0, (0.0, 0.0)
    values: list[float] = []
    for row in previous[:height] + current[:height]:
        values.extend(row[:width])
    scale = max(values) - min(values) if values else 0.0
    if scale == 0:
        scale = max(1.0, max((abs(v) for v in values), default=1.0))
    total = 0.0
    weighted_y = 0.0
    weighted_x = 0.0
    for y in range(height):
        for x in range(width):
            diff = abs(current[y][x] - previous[y][x]) / scale
            total += diff
            weighted_y += y * diff
            weighted_x += x * diff
    denom = height * width
    energy = total / denom if denom else 0.0
    if total == 0:
        return 0.0, (0.0, 0.0)
    return energy, (weighted_y / total / max(1, height - 1), weighted_x / total / max(1, width - 1))


def _centroid_translation(centroids: Sequence[tuple[float, float]]) -> float:
    if len(centroids) < 2:
        return 0.0
    distances = [
        math.sqrt((b[0] - a[0]) ** 2 + (b[1] - a[1]) ** 2)
        for a, b in zip(centroids, centroids[1:])
    ]
    return sum(distances) / len(distances) if distances else 0.0


def _clean_points(positions: Any) -> list[tuple[float, ...]]:
    if not isinstance(positions, Sequence) or isinstance(positions, (str, bytes)):
        return []
    points: list[tuple[float, ...]] = []
    for point in positions:
        if isinstance(point, Sequence) and not isinstance(point, (str, bytes)):
            nums = [float(v) for v in point if isinstance(v, (int, float)) and not isinstance(v, bool)]
            if nums:
                points.append(tuple(nums))
    return points


def _point_distance(a: Sequence[float], b: Sequence[float]) -> float:
    dims = min(len(a), len(b))
    return math.sqrt(sum((float(b[i]) - float(a[i])) ** 2 for i in range(dims))) if dims else 0.0
