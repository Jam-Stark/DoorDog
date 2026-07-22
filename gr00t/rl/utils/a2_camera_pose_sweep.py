"""Pure helpers for the A2 Gemini 335L single-camera pose sweep."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence


STAGE_NAMES = {
    0: "stage0_approach",
    1: "stage1_pregrasp",
    2: "stage2_grasp",
    3: "stage3_open",
    4: "stage4_swing",
    5: "stage5_through",
    6: "all_stages",
}
TARGET_NAMES = ("handle", "finger7", "finger8", "door_panel")


def derive_center_crop_intrinsics(
    *,
    native_width: int,
    native_height: int,
    horizontal_fov_deg: float,
    vertical_fov_deg: float,
    crop_width: int,
    crop_height: int,
    output_width: int,
    output_height: int,
) -> dict[str, object]:
    """Derive centered pinhole intrinsics from nominal native FoV values."""
    dimensions = {
        "native_width": native_width,
        "native_height": native_height,
        "crop_width": crop_width,
        "crop_height": crop_height,
        "output_width": output_width,
        "output_height": output_height,
    }
    for name, value in dimensions.items():
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise ValueError(f"{name} must be a positive int; got {value!r}")
    if crop_width > native_width or crop_height > native_height:
        raise ValueError("center crop must fit inside the native image")
    if not (0.0 < horizontal_fov_deg < 180.0 and 0.0 < vertical_fov_deg < 180.0):
        raise ValueError("nominal FoV values must be finite degrees in (0, 180)")
    scale_x = output_width / crop_width
    scale_y = output_height / crop_height
    if not math.isclose(scale_x, scale_y, rel_tol=0.0, abs_tol=1.0e-12):
        raise ValueError(
            "crop-to-policy resize must preserve aspect ratio; "
            f"scale_x={scale_x}, scale_y={scale_y}"
        )

    fx_native = native_width / (2.0 * math.tan(math.radians(horizontal_fov_deg) / 2.0))
    fy_native = native_height / (2.0 * math.tan(math.radians(vertical_fov_deg) / 2.0))
    crop_left = (native_width - crop_width) / 2.0
    crop_top = (native_height - crop_height) / 2.0
    cx_crop = native_width / 2.0 - crop_left
    cy_crop = native_height / 2.0 - crop_top
    fx_output = fx_native * scale_x
    fy_output = fy_native * scale_y
    cx_output = cx_crop * scale_x
    cy_output = cy_crop * scale_y
    effective_vertical_fov_deg = math.degrees(
        2.0 * math.atan(crop_height / (2.0 * fy_native))
    )
    return {
        "native": {
            "width": native_width,
            "height": native_height,
            "fx": fx_native,
            "fy": fy_native,
            "cx": native_width / 2.0,
            "cy": native_height / 2.0,
        },
        "crop": {
            "width": crop_width,
            "height": crop_height,
            "left": crop_left,
            "top": crop_top,
            "fx": fx_native,
            "fy": fy_native,
            "cx": cx_crop,
            "cy": cy_crop,
        },
        "output": {
            "width": output_width,
            "height": output_height,
            "fx": fx_output,
            "fy": fy_output,
            "cx": cx_output,
            "cy": cy_output,
            "matrix": [
                [fx_output, 0.0, cx_output],
                [0.0, fy_output, cy_output],
                [0.0, 0.0, 1.0],
            ],
        },
        "effective_fov_deg": {
            "horizontal": horizontal_fov_deg,
            "vertical": effective_vertical_fov_deg,
        },
        "spec_derived_not_calibrated": True,
    }


def validate_pose_candidates(
    candidates: Sequence[Mapping[str, object]],
) -> list[dict[str, object]]:
    if not isinstance(candidates, Sequence) or isinstance(candidates, (str, bytes)):
        raise TypeError("camera pose candidates must be a sequence")
    if len(candidates) < 2:
        raise ValueError("camera pose sweep requires at least two candidates")
    normalized: list[dict[str, object]] = []
    names: set[str] = set()
    expected_keys = {"name", "role", "position_m", "rotation_wxyz", "rpy_deg"}
    for index, candidate in enumerate(candidates):
        if not isinstance(candidate, Mapping) or set(candidate) != expected_keys:
            keys = None if not isinstance(candidate, Mapping) else sorted(candidate)
            raise ValueError(
                f"candidate {index} must have exact keys {sorted(expected_keys)}; got {keys}"
            )
        name = candidate["name"]
        role = candidate["role"]
        if not isinstance(name, str) or not name or name in names:
            raise ValueError(f"candidate name must be unique and non-empty; got {name!r}")
        if role not in ("control", "search"):
            raise ValueError(f"candidate {name} role must be control or search; got {role!r}")
        position = _finite_vector(candidate["position_m"], 3, f"candidate {name} position_m")
        rotation = _finite_vector(
            candidate["rotation_wxyz"], 4, f"candidate {name} rotation_wxyz"
        )
        rpy = _finite_vector(candidate["rpy_deg"], 3, f"candidate {name} rpy_deg")
        norm = math.sqrt(sum(value * value for value in rotation))
        if not math.isclose(norm, 1.0, rel_tol=0.0, abs_tol=1.0e-6):
            raise ValueError(f"candidate {name} quaternion must be normalized; norm={norm}")
        if role == "search" and (position[1] != 0.0 or rpy[0] != 0.0 or rpy[2] != 0.0):
            raise ValueError(
                f"search candidate {name} must stay on centerline with roll=yaw=0; "
                f"position={position}, rpy={rpy}"
            )
        names.add(name)
        normalized.append(
            {
                "name": name,
                "role": role,
                "position_m": position,
                "rotation_wxyz": rotation,
                "rpy_deg": rpy,
            }
        )
    return normalized


def instance_target_ids_by_env(
    info: Mapping[str, object],
    *,
    num_envs: int,
    target_path_tokens: Mapping[str, str],
) -> dict[str, list[list[int]]]:
    """Resolve raw instance IDs for target prim-path groups in each cloned env."""
    if set(target_path_tokens) != set(TARGET_NAMES):
        raise ValueError(
            f"target_path_tokens must have exact keys {list(TARGET_NAMES)}; "
            f"got {sorted(target_path_tokens)}"
        )
    id_to_labels = info.get("idToLabels")
    if not isinstance(id_to_labels, Mapping):
        raise ValueError("instance segmentation info requires an idToLabels mapping")
    result = {target: [[] for _ in range(num_envs)] for target in TARGET_NAMES}
    for raw_id, label in id_to_labels.items():
        try:
            instance_id = int(raw_id)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"instance ID key must be int-like; got {raw_id!r}") from exc
        if not isinstance(label, str):
            raise ValueError(
                "raw instance id label must be a USD prim-path string; "
                f"id={instance_id}, label={label!r}"
            )
        for env_id in range(num_envs):
            env_prefix = f"/World/envs/env_{env_id}/"
            if not label.startswith(env_prefix):
                continue
            for target, token in target_path_tokens.items():
                if token in label:
                    result[target][env_id].append(instance_id)
            break
    return result


def rank_camera_candidates(
    candidate_summaries: Sequence[Mapping[str, object]],
    *,
    ranking_stage_indices: Sequence[int] = (1, 2, 3, 4),
) -> dict[str, object]:
    """Rank diagnostics without promoting them to a behavior or hardware hard gate."""
    if not candidate_summaries:
        raise ValueError("candidate_summaries must not be empty")
    if (
        not isinstance(ranking_stage_indices, Sequence)
        or isinstance(ranking_stage_indices, (str, bytes))
        or not ranking_stage_indices
    ):
        raise ValueError("ranking_stage_indices must be a non-empty sequence")
    normalized_stage_indices = []
    for stage_index in ranking_stage_indices:
        if isinstance(stage_index, bool) or not isinstance(stage_index, int):
            raise ValueError("ranking_stage_indices values must be ints")
        if stage_index not in range(1, 6) or stage_index in normalized_stage_indices:
            raise ValueError(
                "ranking_stage_indices must contain unique stage indices in [1, 5]"
            )
        normalized_stage_indices.append(stage_index)
    stage_label = "stage" + "-".join(str(index) for index in normalized_stage_indices)
    ranked = []
    for candidate in candidate_summaries:
        name = candidate.get("name")
        stages = candidate.get("stages")
        if not isinstance(name, str) or not isinstance(stages, Mapping):
            raise ValueError("each candidate summary requires name and stages")
        critical = [stages[STAGE_NAMES[index]] for index in normalized_stage_indices]
        missing_stage_indices = [
            stage_index
            for stage_index, stage in zip(normalized_stage_indices, critical, strict=True)
            if int(stage["sampled_frames"]) <= 0
        ]
        if missing_stage_indices:
            raise ValueError(
                f"candidate {name} has no samples for ranking stages "
                f"{missing_stage_indices}"
            )
        sampled = sum(int(stage["sampled_frames"]) for stage in critical)
        if sampled <= 0:
            raise ValueError(
                f"candidate {name} has no samples for ranking stages {normalized_stage_indices}"
            )

        def rate(key: str) -> float:
            return sum(int(stage[key]) for stage in critical) / sampled

        handle_rate = rate("handle_visible_frames")
        trio_rate = rate("handle_and_both_fingers_visible_frames")
        panel_rate = rate("door_panel_visible_frames")
        centered_rate = rate("handle_centered_frames")
        score = 0.35 * handle_rate + 0.35 * trio_rate + 0.15 * panel_rate + 0.15 * centered_rate
        ranked.append(
            {
                "name": name,
                "score": score,
                "ranked_handle_visible_rate": handle_rate,
                "ranked_handle_and_both_fingers_visible_rate": trio_rate,
                "ranked_door_panel_visible_rate": panel_rate,
                "ranked_handle_centered_rate": centered_rate,
            }
        )
    ranked.sort(key=lambda item: (-item["score"], item["name"]))
    diagnostic_vectors = {
        (
            item["score"],
            item["ranked_handle_visible_rate"],
            item["ranked_handle_and_both_fingers_visible_rate"],
            item["ranked_door_panel_visible_rate"],
            item["ranked_handle_centered_rate"],
        )
        for item in ranked
    }
    if len(ranked) > 1 and len(diagnostic_vectors) == 1:
        raise ValueError(
            "all camera candidates have identical diagnostic metrics for "
            f"{stage_label}; refusing an arbitrary recommendation"
        )
    return {
        "recommended_candidate": ranked[0]["name"],
        "ranking_stage_indices": normalized_stage_indices,
        "ranking_stage_label": stage_label,
        "ranking": ranked,
        "score_contract": (
            f"diagnostic-only weighted {stage_label} visibility: handle 0.35, "
            "handle+both fingers 0.35, door panel 0.15, centered handle 0.15"
        ),
    }


def _finite_vector(value: object, length: int, context: str) -> list[float]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)) or len(value) != length:
        raise ValueError(f"{context} must contain exactly {length} values; got {value!r}")
    vector = []
    for item in value:
        if isinstance(item, bool) or not isinstance(item, (int, float)):
            raise ValueError(f"{context} values must be numeric; got {item!r}")
        item = float(item)
        if not math.isfinite(item):
            raise ValueError(f"{context} values must be finite; got {item!r}")
        vector.append(item)
    return vector
