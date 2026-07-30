"""Depth-aware cylindrical RGB fusion for the C-B2 diagnostic camera pair."""

from __future__ import annotations

import math

import torch


def _finite_matrix(
    value: torch.Tensor,
    shape: tuple[int, ...],
    name: str,
) -> torch.Tensor:
    if not torch.is_tensor(value) or tuple(value.shape) != shape:
        raise ValueError(f"{name} must be a tensor with shape {shape}; got {value!r}")
    if not torch.is_floating_point(value) or not torch.all(torch.isfinite(value)):
        raise ValueError(f"{name} must be a finite floating-point tensor")
    return value


def _validate_source(
    *,
    name: str,
    rgb: torch.Tensor,
    depth: torch.Tensor,
    intrinsics: torch.Tensor,
    rotation_virtual_from_source: torch.Tensor,
    translation_virtual_from_source: torch.Tensor,
) -> None:
    if not torch.is_tensor(rgb) or rgb.ndim != 3 or rgb.shape[-1] != 3:
        raise ValueError(f"{name} RGB must be HWC with three channels")
    if rgb.dtype != torch.uint8:
        raise ValueError(f"{name} RGB must use torch.uint8; got {rgb.dtype}")
    if not torch.is_tensor(depth) or tuple(depth.shape) not in {
        tuple(rgb.shape[:2]),
        (*tuple(rgb.shape[:2]), 1),
    }:
        raise ValueError(
            f"{name} depth must match RGB height/width; "
            f"rgb={tuple(rgb.shape)}, depth={getattr(depth, 'shape', None)}"
        )
    if not torch.is_floating_point(depth):
        raise ValueError(f"{name} depth must be floating point; got {depth.dtype}")
    if rgb.device != depth.device:
        raise ValueError(f"{name} RGB/depth device mismatch")
    _finite_matrix(intrinsics, (3, 3), f"{name} intrinsics")
    _finite_matrix(
        rotation_virtual_from_source,
        (3, 3),
        f"{name} rotation_virtual_from_source",
    )
    _finite_matrix(
        translation_virtual_from_source,
        (3,),
        f"{name} translation_virtual_from_source",
    )
    if not (
        intrinsics.device
        == rotation_virtual_from_source.device
        == translation_virtual_from_source.device
        == rgb.device
    ):
        raise ValueError(f"{name} camera tensors must share one device")
    expected_identity = torch.eye(
        3,
        dtype=intrinsics.dtype,
        device=rgb.device,
    )
    rotation_error = torch.max(
        torch.abs(
            rotation_virtual_from_source
            @ rotation_virtual_from_source.transpose(0, 1)
            - expected_identity
        )
    )
    determinant = torch.det(rotation_virtual_from_source)
    if float(rotation_error.detach().cpu().item()) > 1.0e-5 or not math.isclose(
        float(determinant.detach().cpu().item()),
        1.0,
        rel_tol=0.0,
        abs_tol=1.0e-5,
    ):
        raise ValueError(f"{name} rotation must be a proper orthonormal matrix")
    fx = float(intrinsics[0, 0].detach().cpu().item())
    fy = float(intrinsics[1, 1].detach().cpu().item())
    if fx <= 0.0 or fy <= 0.0:
        raise ValueError(f"{name} focal lengths must be positive")


def _unproject(
    depth: torch.Tensor,
    intrinsics: torch.Tensor,
) -> torch.Tensor:
    if depth.ndim == 3:
        depth = depth[..., 0]
    height, width = depth.shape
    rows, columns = torch.meshgrid(
        torch.arange(height, device=depth.device, dtype=depth.dtype),
        torch.arange(width, device=depth.device, dtype=depth.dtype),
        indexing="ij",
    )
    fx = intrinsics[0, 0]
    fy = intrinsics[1, 1]
    cx = intrinsics[0, 2]
    cy = intrinsics[1, 2]
    return torch.stack(
        [
            (columns - cx) * depth / fx,
            (rows - cy) * depth / fy,
            depth,
        ],
        dim=-1,
    ).reshape(-1, 3)


def _project_cylindrical(
    points_virtual: torch.Tensor,
    *,
    output_height: int,
    output_width: int,
    horizontal_fov_rad: float,
    vertical_fov_rad: float,
) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    horizontal_radius = torch.linalg.vector_norm(points_virtual[:, (0, 2)], dim=1)
    theta = torch.atan2(points_virtual[:, 0], points_virtual[:, 2])
    phi = torch.atan2(points_virtual[:, 1], horizontal_radius)
    columns = torch.floor(
        (theta + horizontal_fov_rad / 2.0)
        * output_width
        / horizontal_fov_rad
    ).to(torch.int64)
    rows = torch.floor(
        (phi + vertical_fov_rad / 2.0)
        * output_height
        / vertical_fov_rad
    ).to(torch.int64)
    inside = (
        (points_virtual[:, 2] > 0.0)
        & (columns >= 0)
        & (columns < output_width)
        & (rows >= 0)
        & (rows < output_height)
    )
    return rows, columns, inside


def _fixed_geometry_fallback(
    *,
    left_rgb: torch.Tensor,
    left_intrinsics: torch.Tensor,
    left_rotation_virtual_from_source: torch.Tensor,
    right_rgb: torch.Tensor,
    right_intrinsics: torch.Tensor,
    right_rotation_virtual_from_source: torch.Tensor,
    output_height: int,
    output_width: int,
    horizontal_fov_rad: float,
    vertical_fov_rad: float,
) -> tuple[torch.Tensor, torch.Tensor]:
    dtype = left_intrinsics.dtype
    device = left_rgb.device
    rows, columns = torch.meshgrid(
        torch.arange(output_height, device=device, dtype=dtype),
        torch.arange(output_width, device=device, dtype=dtype),
        indexing="ij",
    )
    theta = (columns + 0.5) * horizontal_fov_rad / output_width - horizontal_fov_rad / 2.0
    phi = (rows + 0.5) * vertical_fov_rad / output_height - vertical_fov_rad / 2.0
    cos_phi = torch.cos(phi)
    virtual_rays = torch.stack(
        [
            torch.sin(theta) * cos_phi,
            torch.sin(phi),
            torch.cos(theta) * cos_phi,
        ],
        dim=-1,
    ).reshape(-1, 3)

    def sample_source(
        rgb: torch.Tensor,
        intrinsics: torch.Tensor,
        rotation_virtual_from_source: torch.Tensor,
    ) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        source_rays = virtual_rays @ rotation_virtual_from_source
        source_z = source_rays[:, 2]
        source_columns = torch.round(
            intrinsics[0, 0] * source_rays[:, 0] / source_z + intrinsics[0, 2]
        ).to(torch.int64)
        source_rows = torch.round(
            intrinsics[1, 1] * source_rays[:, 1] / source_z + intrinsics[1, 2]
        ).to(torch.int64)
        valid = (
            (source_z > 0.0)
            & (source_columns >= 0)
            & (source_columns < rgb.shape[1])
            & (source_rows >= 0)
            & (source_rows < rgb.shape[0])
        )
        clipped_rows = source_rows.clamp(0, rgb.shape[0] - 1)
        clipped_columns = source_columns.clamp(0, rgb.shape[1] - 1)
        colors = rgb[clipped_rows, clipped_columns]
        return colors, valid, source_z

    left_colors, left_valid, left_score = sample_source(
        left_rgb,
        left_intrinsics,
        left_rotation_virtual_from_source,
    )
    right_colors, right_valid, right_score = sample_source(
        right_rgb,
        right_intrinsics,
        right_rotation_virtual_from_source,
    )
    choose_left = left_valid & (~right_valid | (left_score >= right_score))
    choose_right = right_valid & ~choose_left
    output = torch.zeros(
        (output_height * output_width, 3),
        dtype=torch.uint8,
        device=device,
    )
    output[choose_left] = left_colors[choose_left]
    output[choose_right] = right_colors[choose_right]
    valid = choose_left | choose_right
    return output.reshape(output_height, output_width, 3), valid.reshape(
        output_height, output_width
    )


def depth_aware_cylindrical_panorama(
    *,
    left_rgb: torch.Tensor,
    left_depth: torch.Tensor,
    left_intrinsics: torch.Tensor,
    left_rotation_virtual_from_source: torch.Tensor,
    left_translation_virtual_from_source: torch.Tensor,
    right_rgb: torch.Tensor,
    right_depth: torch.Tensor,
    right_intrinsics: torch.Tensor,
    right_rotation_virtual_from_source: torch.Tensor,
    right_translation_virtual_from_source: torch.Tensor,
    output_height: int,
    output_width: int,
    horizontal_fov_deg: float,
    vertical_fov_deg: float,
    minimum_depth_m: float,
    maximum_depth_m: float,
) -> dict[str, torch.Tensor | int]:
    """Fuse two RGB-D views into one virtual cylindrical camera image.

    Finite in-range depth samples are transformed into the virtual camera and
    resolved by a deterministic micrometre-quantized Z-buffer. Output pixels
    without valid depth use one geometrically best raw view; RGB values are
    never averaged across cameras.
    """

    _validate_source(
        name="left",
        rgb=left_rgb,
        depth=left_depth,
        intrinsics=left_intrinsics,
        rotation_virtual_from_source=left_rotation_virtual_from_source,
        translation_virtual_from_source=left_translation_virtual_from_source,
    )
    _validate_source(
        name="right",
        rgb=right_rgb,
        depth=right_depth,
        intrinsics=right_intrinsics,
        rotation_virtual_from_source=right_rotation_virtual_from_source,
        translation_virtual_from_source=right_translation_virtual_from_source,
    )
    if left_rgb.device != right_rgb.device or left_intrinsics.dtype != right_intrinsics.dtype:
        raise ValueError("left/right panorama inputs must share device and floating dtype")
    if isinstance(output_height, bool) or not isinstance(output_height, int) or output_height < 2:
        raise ValueError("output_height must be an int >= 2")
    if isinstance(output_width, bool) or not isinstance(output_width, int) or output_width < 2:
        raise ValueError("output_width must be an int >= 2")
    for name, value in (
        ("horizontal_fov_deg", horizontal_fov_deg),
        ("vertical_fov_deg", vertical_fov_deg),
        ("minimum_depth_m", minimum_depth_m),
        ("maximum_depth_m", maximum_depth_m),
    ):
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
            raise ValueError(f"{name} must be finite")
    if not (0.0 < horizontal_fov_deg < 180.0 and 0.0 < vertical_fov_deg < 180.0):
        raise ValueError("panorama FoV values must be in (0, 180) degrees")
    if not (0.0 < minimum_depth_m < maximum_depth_m):
        raise ValueError("panorama depth range must satisfy 0 < min < max")

    horizontal_fov_rad = math.radians(horizontal_fov_deg)
    vertical_fov_rad = math.radians(vertical_fov_deg)
    projected_linear_indices = []
    projected_depths = []
    projected_colors = []
    valid_input_pixels = 0
    for rgb, depth, intrinsics, rotation, translation in (
        (
            left_rgb,
            left_depth,
            left_intrinsics,
            left_rotation_virtual_from_source,
            left_translation_virtual_from_source,
        ),
        (
            right_rgb,
            right_depth,
            right_intrinsics,
            right_rotation_virtual_from_source,
            right_translation_virtual_from_source,
        ),
    ):
        flat_depth = depth[..., 0].reshape(-1) if depth.ndim == 3 else depth.reshape(-1)
        valid_depth = (
            torch.isfinite(flat_depth)
            & (flat_depth >= minimum_depth_m)
            & (flat_depth <= maximum_depth_m)
        )
        valid_input_pixels += int(valid_depth.sum().detach().cpu().item())
        points_source = _unproject(depth, intrinsics)
        points_virtual = points_source @ rotation.transpose(0, 1) + translation
        rows, columns, inside = _project_cylindrical(
            points_virtual,
            output_height=output_height,
            output_width=output_width,
            horizontal_fov_rad=horizontal_fov_rad,
            vertical_fov_rad=vertical_fov_rad,
        )
        keep = valid_depth & inside
        projected_linear_indices.append(rows[keep] * output_width + columns[keep])
        projected_depths.append(torch.linalg.vector_norm(points_virtual[keep], dim=1))
        projected_colors.append(rgb.reshape(-1, 3)[keep])
    linear_indices = torch.cat(projected_linear_indices)
    radial_depths = torch.cat(projected_depths)
    colors = torch.cat(projected_colors)
    output_size = output_height * output_width
    point_count = int(linear_indices.numel())
    maximum_key = torch.iinfo(torch.int64).max
    winner_keys = torch.full(
        (output_size,),
        maximum_key,
        dtype=torch.int64,
        device=linear_indices.device,
    )
    panorama = torch.zeros(
        (output_size, 3),
        dtype=torch.uint8,
        device=left_rgb.device,
    )
    if point_count > 0:
        point_indices = torch.arange(
            point_count,
            device=linear_indices.device,
            dtype=torch.int64,
        )
        depth_micrometres = torch.round(radial_depths * 1_000_000.0).to(
            torch.int64
        )
        keys = depth_micrometres * (point_count + 1) + point_indices
        winner_keys.scatter_reduce_(
            0,
            linear_indices,
            keys,
            reduce="amin",
            include_self=True,
        )
        winners = keys == winner_keys[linear_indices]
        winner_linear_indices = linear_indices[winners]
        if (
            torch.unique(winner_linear_indices).numel()
            != winner_linear_indices.numel()
        ):
            raise RuntimeError(
                "C-B2 Z-buffer did not resolve a unique source per output pixel"
            )
        panorama[winner_linear_indices] = colors[winners]
    depth_valid_mask = (winner_keys != maximum_key).reshape(output_height, output_width)

    fallback, fallback_available = _fixed_geometry_fallback(
        left_rgb=left_rgb,
        left_intrinsics=left_intrinsics,
        left_rotation_virtual_from_source=left_rotation_virtual_from_source,
        right_rgb=right_rgb,
        right_intrinsics=right_intrinsics,
        right_rotation_virtual_from_source=right_rotation_virtual_from_source,
        output_height=output_height,
        output_width=output_width,
        horizontal_fov_rad=horizontal_fov_rad,
        vertical_fov_rad=vertical_fov_rad,
    )
    fallback_mask = ~depth_valid_mask & fallback_available
    panorama = panorama.reshape(output_height, output_width, 3)
    panorama[fallback_mask] = fallback[fallback_mask]
    output_valid_mask = depth_valid_mask | fallback_mask
    return {
        "rgb": panorama,
        "depth_valid_mask": depth_valid_mask,
        "fallback_mask": fallback_mask,
        "output_valid_mask": output_valid_mask,
        "valid_input_depth_pixels": valid_input_pixels,
        "projected_depth_samples": point_count,
        "depth_fused_output_pixels": int(depth_valid_mask.sum().detach().cpu().item()),
        "fallback_output_pixels": int(fallback_mask.sum().detach().cpu().item()),
        "empty_output_pixels": int((~output_valid_mask).sum().detach().cpu().item()),
    }
