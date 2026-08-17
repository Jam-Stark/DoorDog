"""Policy-only golden capture format.

The format intentionally mirrors the v24 P0 harness discipline: one ordered
row per capture point, explicit tensor names/shapes/dtypes, and deterministic
mean actions.  It has no dependency on Isaac or MuJoCo and can therefore be
replayed by the shadow policy adapter before any physics is claimed.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

import numpy as np


GOLDEN_IO_SCHEMA = "doordog.sim2sim.policy_golden_io.v1"
REQUIRED_ARRAYS = (
    "actor_obs",
    "vision_obs",
    "context_vision_obs",
    "camera_meta",
    "hidden_h_before",
    "hidden_c_before",
    "action_mean",
    "hidden_h_after",
    "hidden_c_after",
    "done",
)


def _as_array(name: str, value: Any) -> np.ndarray:
    array = np.asarray(value)
    if array.ndim < 1:
        raise ValueError(f"golden array {name!r} must carry a capture-row axis")
    if array.dtype == np.dtype("O"):
        raise TypeError(f"golden array {name!r} must not use object dtype")
    if np.issubdtype(array.dtype, np.floating) and not np.isfinite(array).all():
        raise ValueError(f"golden array {name!r} contains non-finite values")
    return array


def write_golden_capture(
    output_dir: Path,
    arrays: Mapping[str, Any],
    *,
    capture_points: list[str],
    policy_interface_id: str,
) -> dict[str, Any]:
    """Write an immutable policy replay input/output artifact.

    ``capture_points`` must name every row (normally reset, standing, and
    intermediate).  The caller obtains arrays from the production native
    loader; this helper deliberately does not invent frames or hidden state.
    """
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    npz_path = output_dir / "golden_io.npz"
    manifest_path = output_dir / "golden_manifest.json"
    if npz_path.exists() or manifest_path.exists():
        raise FileExistsError(f"refusing to overwrite golden capture in {output_dir}")
    if set(arrays) != set(REQUIRED_ARRAYS):
        raise ValueError(
            f"golden array names must be exactly {REQUIRED_ARRAYS}; got {tuple(arrays)}"
        )
    normalized = {name: _as_array(name, arrays[name]) for name in REQUIRED_ARRAYS}
    row_count = normalized["actor_obs"].shape[0]
    if row_count != len(capture_points):
        raise ValueError(
            f"capture point count {len(capture_points)} does not match row count {row_count}"
        )
    if any(array.shape[0] != row_count for array in normalized.values()):
        raise ValueError("all golden arrays must have identical capture-row counts")
    if len(set(capture_points)) != len(capture_points):
        raise ValueError("golden capture points must be unique and ordered")

    np.savez_compressed(npz_path, **normalized)
    manifest = {
        "schema": GOLDEN_IO_SCHEMA,
        "status": "CAPTURED",
        "policy_interface_id": policy_interface_id,
        "row_order": capture_points,
        "deterministic_output": "action_mean",
        "arrays": {
            name: {"shape": list(array.shape), "dtype": str(array.dtype)}
            for name, array in normalized.items()
        },
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest


def validate_golden_capture(output_dir: Path, manifest: Mapping[str, Any]) -> None:
    """Validate the serialized capture structurally and numerically."""
    if manifest.get("schema") != GOLDEN_IO_SCHEMA:
        raise ValueError(f"unsupported golden schema: {manifest.get('schema')!r}")
    npz_path = output_dir / "golden_io.npz"
    with np.load(npz_path, allow_pickle=False) as archive:
        if set(archive.files) != set(REQUIRED_ARRAYS):
            raise ValueError(f"golden archive arrays are {archive.files}, expected {REQUIRED_ARRAYS}")
        expected_rows = len(manifest["row_order"])
        for name in REQUIRED_ARRAYS:
            array = _as_array(name, archive[name])
            declared = manifest["arrays"][name]
            if list(array.shape) != declared["shape"] or str(array.dtype) != declared["dtype"]:
                raise ValueError(f"golden array declaration mismatch for {name!r}")
            if array.shape[0] != expected_rows:
                raise ValueError(f"golden array {name!r} row count differs from manifest")
