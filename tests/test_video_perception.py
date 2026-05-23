from flow_memory.perception import DualStreamPerception


def _motion_signature(perception):
    return perception.motion_geometry.spatial_relations[0]["appearance_invariant_signature"]


def _moving_dot_video(foreground, background):
    frames = []
    for x in (0, 1, 2):
        frame = [[background for _ in range(4)] for _ in range(4)]
        frame[1][x] = foreground
        frames.append(frame)
    return frames


def test_numeric_video_motion_is_appearance_invariant() -> None:
    frames = [
        [[0, 0, 0], [0, 1, 0]],
        [[0, 0, 0], [0, 2, 0]],
        [[0, 0, 0], [0, 4, 0]],
    ]
    perception = DualStreamPerception().process({"frames": frames, "affordances": ["track"]})
    assert perception.latent_state["modality"] == "video"
    assert perception.motion_geometry.trajectories
    assert "optical_flow_invariance" in perception.motion_geometry.invariances
    assert "appearance_suppression" in perception.motion_geometry.invariances
    assert "track" in perception.motion_geometry.affordances


def test_motion_signature_ignores_texture_intensity_and_color() -> None:
    grayscale = DualStreamPerception().process({"frames": _moving_dot_video(1.0, 0.0)})
    color_shifted = DualStreamPerception().process(
        {"frames": _moving_dot_video([240.0, 40.0, 120.0], [5.0, 5.0, 5.0])}
    )

    grayscale_signature = _motion_signature(grayscale)
    color_shifted_signature = _motion_signature(color_shifted)

    assert grayscale_signature == color_shifted_signature
    assert grayscale_signature["appearance_free"] is True
    assert grayscale_signature["trajectory"]["step_count"] == 2
    assert grayscale.motion_geometry.spatial_relations[0]["trajectory_summary"] == grayscale_signature["trajectory"]
