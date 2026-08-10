"""Physics-first v23 D1 bucket sampling.

The sampler is deliberately independent from the trainer.  It consumes the
owner-authorized R190 receipt and the measured atlas file named by that
receipt, then exposes deterministic, absolute-global-step bucket assignments.
No historical capability reducer or policy telemetry is consulted here.
"""

from __future__ import annotations

import copy
import json
import random
from dataclasses import dataclass
from numbers import Integral, Real
from pathlib import Path
from typing import Any, Mapping


REPO_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_RECEIPT_PATH = (
    REPO_ROOT
    / "logs_eval/base_v23/p0/p04_d1_physics_first_20260810/p04_d1_physics_first.json"
)

RECEIPT_SCHEMA = "a2_piper_v23_p04_d1_physics_first_v1"
RECEIPT_STATUS = "P0_4_D1_PHYSICS_FIRST_FREEZE_ADMITTED"
ATLAS_SCHEMA = "a2_piper_v23_door_external_torque_threshold_v1"
ATLAS_STATUS = "MEASURED_RAW"
CANONICAL_GEOMETRY_SCHEMA = "a2_piper_v23_canonical_geometry_v1"
BUCKET_NAMES = ("E0", "E1", "near-E2")
VARIANTS = ("normal", "lite")
SUPPORTED_TOTAL_STEPS = (10, 2500)

_CELL_IDS = tuple(f"A{index}" for index in range(9))
_REQUIRED_LOCAL_FACTS = (
    "door_width_m",
    "door_height_m",
    "handle_height_m",
    "handle_width_m",
    "handle_type",
    "door_open_lr",
    "door_open_io",
    "door_open_lr_sign",
    "door_open_io_sign",
    "hinge_axis_local",
    "hinge_anchor_local",
)
_REQUIRED_REALIZED_PARAMS = (
    "hinge_damping_native",
    "hinge_stiffness_native",
    "hinge_effort_limit_nm",
    "door_weight_kg",
)

# The step boundaries and counts are owner-frozen.  The integer counts are
# kept explicit instead of recomputed from percentages so 64x10 and
# 4096x2500 have the exact registered transition census.
_PHASES: dict[str, dict[int, tuple[tuple[int, tuple[int, int, int]], ...]]] = {
    "normal": {
        10: (
            (2, (64, 0, 0)),
            (5, (38, 26, 0)),
            (10, (19, 39, 6)),
        ),
        2500: (
            (500, (4096, 0, 0)),
            (1250, (2458, 1638, 0)),
            (2500, (1229, 2458, 409)),
        ),
    },
    "lite": {
        10: (
            (2, (64, 0, 0)),
            (5, (42, 22, 0)),
            (10, (26, 35, 3)),
        ),
        2500: (
            (500, (4096, 0, 0)),
            (1250, (2662, 1434, 0)),
            (2500, (1638, 2253, 205)),
        ),
    },
}

_NORMAL_BUCKET_CELLS = {
    "E0": ("A0", "A1"),
    "E1": ("A4", "A5", "A6", "A2", "A3", "A7"),
    "near-E2": ("A8",),
}
_LITE_BUCKET_CELLS = {
    "E0": ("A0", "A1"),
    "E1": ("A4", "A5", "A6"),
    "near-E2": ("A8",),
}


def _resolve_path(value: str | Path, *, base: Path = REPO_ROOT) -> Path:
    path = Path(value)
    if not path.is_absolute():
        path = base / path
    if path.is_symlink():
        raise ValueError(f"D1 source paths must not be symlinks: {path}")
    return path.resolve()


def _read_json(path: Path, *, label: str) -> dict[str, Any]:
    if not path.is_file() or path.is_symlink():
        raise FileNotFoundError(f"{label} must be a regular file: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"{label} is not valid JSON: {path}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"{label} root must be an object: {path}")
    return payload


def _finite(value: Any, *, label: str, positive: bool = False) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise TypeError(f"{label} must be a real number")
    number = float(value)
    if not number == number or number in (float("inf"), float("-inf")):
        raise ValueError(f"{label} must be finite")
    if positive and number <= 0.0:
        raise ValueError(f"{label} must be positive")
    return number


def _tuple_numbers(value: Any, *, label: str, length: int) -> tuple[float, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, (list, tuple)):
        raise TypeError(f"{label} must be a numeric sequence")
    if len(value) != length:
        raise ValueError(f"{label} must contain exactly {length} values")
    return tuple(_finite(item, label=f"{label}[{index}]") for index, item in enumerate(value))


@dataclass(frozen=True)
class RealizedParameters:
    """Immutable realized dynamic parameters for one atlas cell."""

    hinge_damping_native: float
    hinge_stiffness_native: float
    hinge_effort_limit_nm: float
    door_weight_kg: float

    def as_dict(self) -> dict[str, float]:
        return {
            "hinge_damping_native": self.hinge_damping_native,
            "hinge_stiffness_native": self.hinge_stiffness_native,
            "hinge_effort_limit_nm": self.hinge_effort_limit_nm,
            "door_weight_kg": self.door_weight_kg,
        }


@dataclass(frozen=True)
class CanonicalRealizedRow:
    """Immutable canonical geometry plus realized dynamic parameters."""

    cell_id: str
    geometry_id: str
    door_width_m: float
    door_height_m: float
    handle_height_m: float
    handle_width_m: float
    handle_type: str
    door_open_lr: str
    door_open_io: str
    door_open_lr_sign: int
    door_open_io_sign: int
    hinge_axis_local: tuple[float, float, float]
    hinge_anchor_local: tuple[float, float, float]
    realized_params: RealizedParameters
    normal_bucket: str
    lite_bucket: str | None

    def as_dict(self) -> dict[str, Any]:
        """Return a detached JSON-compatible row for telemetry/config use."""

        return {
            "cell_id": self.cell_id,
            "geometry_id": self.geometry_id,
            "local_facts": {
                "door_width_m": self.door_width_m,
                "door_height_m": self.door_height_m,
                "handle_height_m": self.handle_height_m,
                "handle_width_m": self.handle_width_m,
                "handle_type": self.handle_type,
                "door_open_lr": self.door_open_lr,
                "door_open_io": self.door_open_io,
                "door_open_lr_sign": self.door_open_lr_sign,
                "door_open_io_sign": self.door_open_io_sign,
                "hinge_axis_local": list(self.hinge_axis_local),
                "hinge_anchor_local": list(self.hinge_anchor_local),
            },
            "realized_params": self.realized_params.as_dict(),
            "normal_bucket": self.normal_bucket,
            "lite_bucket": self.lite_bucket,
        }


@dataclass(frozen=True)
class D1Assignment:
    """One deterministic intended bucket and realized row."""

    global_step: int
    env_index: int
    intended_bucket: str
    realized_row: CanonicalRealizedRow

    def as_dict(self) -> dict[str, Any]:
        row = self.realized_row.as_dict()
        return {
            "global_step": self.global_step,
            "env_index": self.env_index,
            "intended_bucket": self.intended_bucket,
            "cell_id": row["cell_id"],
            "geometry_id": row["geometry_id"],
            "realized_params": row["realized_params"],
            "local_facts": row["local_facts"],
        }


@dataclass(frozen=True)
class D1Transition:
    """Absolute-step curriculum transition; only phase boundaries reset all envs."""

    previous_global_step: int
    global_step: int
    previous_phase: int
    phase: int
    full_reset_boundary: bool

    def as_dict(self) -> dict[str, Any]:
        return {
            "previous_global_step": self.previous_global_step,
            "global_step": self.global_step,
            "previous_phase": self.previous_phase,
            "phase": self.phase,
            "full_reset_boundary": self.full_reset_boundary,
            "reset_scope": "full_environment" if self.full_reset_boundary else "none",
        }


@dataclass(frozen=True)
class D1Catalog:
    receipt_path: Path
    atlas_path: Path
    rows: tuple[CanonicalRealizedRow, ...]
    receipt: Mapping[str, Any]

    @property
    def rows_by_cell(self) -> Mapping[str, CanonicalRealizedRow]:
        return {row.cell_id: row for row in self.rows}

    def row(self, cell_id: str) -> CanonicalRealizedRow:
        try:
            return self.rows_by_cell[cell_id]
        except KeyError as exc:
            raise KeyError(f"unknown D1 atlas cell {cell_id!r}") from exc


def _validate_external_atlas(atlas: Mapping[str, Any], *, atlas_path: Path) -> dict[str, Any]:
    if atlas.get("plan_id") != "base_v23_force_feasibility_initialization_posture_R1":
        raise ValueError("D1 atlas plan_id is not the registered R1 plan")
    if atlas.get("interpolation") != "FORBIDDEN":
        raise ValueError("D1 atlas interpolation must remain FORBIDDEN")
    if atlas.get("external_torque_authority") != "MEASURED_EXTERNAL_GLOBAL_TORQUE_HIGH_LEVEL_WRENCH_COMPOSER":
        raise ValueError("D1 atlas authority is not the measured high-level probe")
    bracket = atlas.get("bracket")
    if not isinstance(bracket, Mapping) or bracket.get("threshold_rad") != 0.02:
        raise ValueError("D1 atlas must retain the measured 0.02 rad threshold")
    cells = bracket.get("cells")
    if not isinstance(cells, Mapping) or tuple(cells) != _CELL_IDS:
        raise ValueError("D1 atlas bracket cells must cover A0-A8 in order")
    rows = atlas.get("rows")
    if not isinstance(rows, list) or len(rows) != 180:
        raise ValueError("D1 atlas must contain the measured 180 rows")
    for index, row in enumerate(rows):
        if not isinstance(row, Mapping) or row.get("cell_id") not in _CELL_IDS:
            raise ValueError(f"D1 atlas row {index} has an invalid cell_id")
        row_status = row.get("status")
        if row_status is not None and row_status != ATLAS_STATUS:
            raise ValueError(f"D1 atlas row {index} status is not {ATLAS_STATUS}")
        geometry = row.get("canonical_geometry")
        if not isinstance(geometry, Mapping):
            raise ValueError(f"D1 atlas row {index} is missing canonical_geometry")
        if geometry.get("schema") != CANONICAL_GEOMETRY_SCHEMA:
            raise ValueError(f"D1 atlas row {index} canonical geometry schema is invalid")
        if geometry.get("cell_id") != row.get("cell_id"):
            raise ValueError(f"D1 atlas row {index} canonical geometry cell disagrees")
        if geometry.get("world_origin_excluded") is not True:
            raise ValueError(f"D1 atlas row {index} must exclude world origin")
    return dict(atlas)


def _validate_receipt(receipt: Mapping[str, Any], *, receipt_path: Path) -> Path:
    if receipt.get("schema") != RECEIPT_SCHEMA:
        raise ValueError(f"D1 receipt schema is not {RECEIPT_SCHEMA}: {receipt_path}")
    if receipt.get("status") != RECEIPT_STATUS:
        raise ValueError(f"D1 receipt status is not {RECEIPT_STATUS}: {receipt_path}")
    if receipt.get("affirmative_physics_first_freeze") is not True:
        raise ValueError("D1 receipt is not an affirmative physics-first freeze")
    if receipt.get("freeze_status") != "PHYSICS_FIRST_PROVISIONAL_FREEZE":
        raise ValueError("D1 receipt freeze status is invalid")
    if receipt.get("confirmed_E2") is not False:
        raise ValueError("D1 receipt must keep confirmed_E2=false")
    if receipt.get("labels_provisional") is not True:
        raise ValueError("D1 receipt must retain provisional labels")
    provenance = receipt.get("atlas_provenance")
    if not isinstance(provenance, Mapping):
        raise ValueError("D1 receipt is missing atlas_provenance")
    if provenance.get("schema") != ATLAS_SCHEMA or provenance.get("status") != ATLAS_STATUS:
        raise ValueError("D1 receipt atlas provenance schema/status is invalid")
    if provenance.get("interpolation") != "FORBIDDEN":
        raise ValueError("D1 receipt atlas provenance permits forbidden interpolation")
    source_value = provenance.get("source")
    if not isinstance(source_value, str) or not source_value:
        raise ValueError("D1 receipt atlas provenance requires a source path")
    return _resolve_path(source_value, base=REPO_ROOT)


def _row_from_geometry(
    cell_id: str,
    geometry: Mapping[str, Any],
    normal_zones: Mapping[str, list[str]],
    lite_zones: Mapping[str, list[str]],
) -> CanonicalRealizedRow:
    geometry_id = geometry.get("geometry_id")
    if not isinstance(geometry_id, str) or not geometry_id:
        raise ValueError(f"D1 {cell_id} geometry_id must be a non-empty string")
    local = geometry.get("local_facts")
    realized = geometry.get("realized_params")
    if not isinstance(local, Mapping) or set(local) != set(_REQUIRED_LOCAL_FACTS):
        raise ValueError(f"D1 {cell_id} local_facts fields are not canonical")
    if not isinstance(realized, Mapping) or set(realized) != set(_REQUIRED_REALIZED_PARAMS):
        raise ValueError(f"D1 {cell_id} realized_params fields are not canonical")
    for field in (
        "door_width_m",
        "door_height_m",
        "handle_height_m",
        "handle_width_m",
    ):
        _finite(local[field], label=f"{cell_id}.{field}", positive=True)
    axis = _tuple_numbers(local["hinge_axis_local"], label=f"{cell_id}.hinge_axis_local", length=3)
    anchor = _tuple_numbers(local["hinge_anchor_local"], label=f"{cell_id}.hinge_anchor_local", length=3)
    if axis != (0.0, 0.0, 1.0) or anchor != (0.02, 0.475, 0.0):
        raise ValueError(f"D1 {cell_id} local hinge facts disagree with the canonical atlas")
    if local["handle_type"] != "lever" or local["door_open_lr"] != "right" or local["door_open_io"] != "out":
        raise ValueError(f"D1 {cell_id} local door identity is not the canonical right-out lever")
    if local["door_open_lr_sign"] != -1 or local["door_open_io_sign"] != -1:
        raise ValueError(f"D1 {cell_id} local door signs are not canonical")
    for field in _REQUIRED_REALIZED_PARAMS:
        _finite(realized[field], label=f"{cell_id}.{field}", positive=field != "hinge_damping_native")
    normal_bucket = next((bucket for bucket, cells in normal_zones.items() if cell_id in cells), None)
    lite_bucket = next((bucket for bucket, cells in lite_zones.items() if cell_id in cells), None)
    if normal_bucket not in BUCKET_NAMES:
        raise ValueError(f"D1 {cell_id} has no normal bucket")
    return CanonicalRealizedRow(
        cell_id=cell_id,
        geometry_id=geometry_id,
        door_width_m=float(local["door_width_m"]),
        door_height_m=float(local["door_height_m"]),
        handle_height_m=float(local["handle_height_m"]),
        handle_width_m=float(local["handle_width_m"]),
        handle_type=str(local["handle_type"]),
        door_open_lr=str(local["door_open_lr"]),
        door_open_io=str(local["door_open_io"]),
        door_open_lr_sign=int(local["door_open_lr_sign"]),
        door_open_io_sign=int(local["door_open_io_sign"]),
        hinge_axis_local=axis,
        hinge_anchor_local=anchor,
        realized_params=RealizedParameters(
            hinge_damping_native=float(realized["hinge_damping_native"]),
            hinge_stiffness_native=float(realized["hinge_stiffness_native"]),
            hinge_effort_limit_nm=float(realized["hinge_effort_limit_nm"]),
            door_weight_kg=float(realized["door_weight_kg"]),
        ),
        normal_bucket=normal_bucket,
        lite_bucket=lite_bucket,
    )


def load_d1_catalog(receipt_path: str | Path = DEFAULT_RECEIPT_PATH) -> D1Catalog:
    """Load and strictly validate the owner-authorized R190 D1 source."""

    resolved_receipt = _resolve_path(receipt_path)
    receipt = _read_json(resolved_receipt, label="D1 physics receipt")
    atlas_path = _validate_receipt(receipt, receipt_path=resolved_receipt)
    atlas = _validate_external_atlas(
        _read_json(atlas_path, label="D1 referenced external atlas"),
        atlas_path=atlas_path,
    )
    zones = receipt.get("zones")
    if not isinstance(zones, Mapping):
        raise ValueError("D1 receipt is missing zones")
    normal_zones = zones.get("normal")
    lite_zones = zones.get("lite")
    if not isinstance(normal_zones, Mapping) or not isinstance(lite_zones, Mapping):
        raise ValueError("D1 receipt zones must contain normal and lite mappings")
    expected_normal = {
        "E0": ["A0", "A1"],
        "E1": ["A4", "A5", "A6", "A2", "A3", "A7"],
        "near-E2": ["A8"],
        "confirmed-E2": [],
    }
    expected_lite = {
        "E0": ["A0", "A1"],
        "E1": ["A4", "A5", "A6"],
        "near-E2": ["A8"],
        "confirmed-E2": [],
    }
    if normal_zones != expected_normal or lite_zones != expected_lite:
        raise ValueError("D1 receipt zones disagree with the R190 owner freeze")
    mixture = receipt.get("mixture")
    if not isinstance(mixture, Mapping):
        raise ValueError("D1 receipt is missing mixture schedules")
    normal_mixture = mixture.get("normal")
    lite_mixture = mixture.get("lite")
    if (
        not isinstance(normal_mixture, Mapping)
        or normal_mixture.get("schedule") != "100/0/0 -> 60/40/0 -> 30/60/10"
        or not isinstance(lite_mixture, Mapping)
        or lite_mixture.get("schedule") != "100/0/0 -> 65/35/0 -> 40/55/5"
    ):
        raise ValueError("D1 receipt mixture schedules disagree with the R190 owner freeze")
    atlas_rows: dict[str, Mapping[str, Any]] = {}
    for atlas_row in atlas["rows"]:
        cell_id = str(atlas_row["cell_id"])
        geometry = atlas_row["canonical_geometry"]
        previous = atlas_rows.get(cell_id)
        if previous is None:
            atlas_rows[cell_id] = geometry
        elif previous != geometry:
            raise ValueError(f"D1 atlas has inconsistent canonical geometry for {cell_id}")
    if tuple(atlas_rows) != _CELL_IDS:
        raise ValueError("D1 atlas must provide exactly one canonical geometry per A0-A8 cell")
    rows = tuple(
        _row_from_geometry(cell_id, atlas_rows[cell_id], expected_normal, expected_lite)
        for cell_id in _CELL_IDS
    )
    return D1Catalog(
        receipt_path=resolved_receipt,
        atlas_path=atlas_path,
        rows=rows,
        receipt=copy.deepcopy(receipt),
    )


class D1Sampler:
    """Deterministic curriculum sampler keyed only by absolute global step."""

    def __init__(
        self,
        *,
        variant: str = "normal",
        bucket_seed: int = 0,
        total_steps: int = 2500,
        catalog: D1Catalog | None = None,
    ) -> None:
        if variant not in VARIANTS:
            raise ValueError(f"D1 variant must be one of {VARIANTS}; got {variant!r}")
        if isinstance(bucket_seed, bool) or not isinstance(bucket_seed, Integral) or bucket_seed < 0:
            raise TypeError("D1 bucket seed must be a non-negative integer")
        if isinstance(total_steps, bool) or not isinstance(total_steps, Integral) or total_steps not in SUPPORTED_TOTAL_STEPS:
            raise ValueError(f"D1 total_steps must be one of {SUPPORTED_TOTAL_STEPS}")
        self.variant = variant
        self.bucket_seed = int(bucket_seed)
        self.total_steps = int(total_steps)
        self.catalog = load_d1_catalog() if catalog is None else catalog
        self._rows_by_cell = self.catalog.rows_by_cell
        self._assignments: dict[int, tuple[D1Assignment, ...]] = {}

    @classmethod
    def from_config(cls, env_config: Mapping[str, Any]) -> "D1Sampler":
        if env_config.get("a2_v23_d1_sampler_enabled") is not True:
            raise ValueError("D1 sampler requires a2_v23_d1_sampler_enabled=true")
        receipt_path = env_config.get("a2_v23_d1_receipt_path")
        if not isinstance(receipt_path, (str, Path)) or not str(receipt_path):
            raise ValueError("D1 sampler requires a2_v23_d1_receipt_path")
        variant = env_config.get("a2_v23_d1_variant")
        seed = env_config.get("a2_v23_d1_bucket_seed")
        total_steps = env_config.get("a2_v23_d1_total_steps")
        if variant not in VARIANTS or isinstance(seed, bool) or not isinstance(seed, Integral) or isinstance(total_steps, bool) or not isinstance(total_steps, Integral):
            raise ValueError("D1 sampler config variant/seed/total_steps is invalid")
        return cls(
            variant=str(variant),
            bucket_seed=int(seed),
            total_steps=int(total_steps),
            catalog=load_d1_catalog(receipt_path),
        )

    def phase_index(self, global_step: int) -> int:
        if isinstance(global_step, bool) or not isinstance(global_step, Integral):
            raise TypeError("global_step must be an integer")
        step = int(global_step)
        if step < 0 or step >= self.total_steps:
            raise ValueError(
                f"global_step must be in [0, {self.total_steps}); got {global_step!r}"
            )
        phases = _PHASES[self.variant][self.total_steps]
        for index, (end_step, _) in enumerate(phases):
            if step < end_step:
                return index
        raise RuntimeError("D1 phase table does not cover total_steps")

    def phase_counts(self, global_step: int) -> tuple[int, int, int]:
        return _PHASES[self.variant][self.total_steps][self.phase_index(global_step)][1]

    @property
    def canonical_rows(self) -> tuple[CanonicalRealizedRow, ...]:
        return self.catalog.rows

    def bucket_counts(self, global_step: int) -> dict[str, int]:
        counts = {bucket: count for bucket, count in zip(BUCKET_NAMES, self.phase_counts(global_step))}
        return counts

    def transition(self, previous_global_step: int, global_step: int) -> D1Transition:
        previous = self.phase_index(previous_global_step)
        current = self.phase_index(global_step)
        if global_step < previous_global_step:
            raise ValueError("D1 global_step must be monotonic when checking a transition")
        return D1Transition(
            previous_global_step=int(previous_global_step),
            global_step=int(global_step),
            previous_phase=previous,
            phase=current,
            full_reset_boundary=current != previous,
        )

    def _stage_assignments(self, phase: int) -> tuple[D1Assignment, ...]:
        if phase in self._assignments:
            return self._assignments[phase]
        counts = _PHASES[self.variant][self.total_steps][phase][1]
        bucket_cells = _NORMAL_BUCKET_CELLS if self.variant == "normal" else _LITE_BUCKET_CELLS
        cells: list[str] = []
        for bucket, count in zip(BUCKET_NAMES, counts):
            if count < 0:
                raise ValueError("D1 phase count cannot be negative")
            choices = bucket_cells[bucket]
            for index in range(count):
                cells.append(choices[index % len(choices)])
        if len(cells) != self.total_envs:
            raise ValueError("D1 phase count total does not match registered environment count")
        # A local, explicit seed controls assignment order.  It is intentionally
        # independent of process-global RNG state and does not use content-derived
        # selectors.
        order = list(range(len(cells)))
        random.Random(self.bucket_seed + phase).shuffle(order)
        assignments = []
        for env_index, source_index in enumerate(order):
            cell_id = cells[source_index]
            row = self._rows_by_cell[cell_id]
            bucket = row.normal_bucket if self.variant == "normal" else row.lite_bucket
            if bucket not in BUCKET_NAMES:
                raise ValueError(f"D1 cell {cell_id} is not in the selected {self.variant} curriculum")
            assignments.append(
                D1Assignment(
                    global_step=-1,
                    env_index=env_index,
                    intended_bucket=bucket,
                    realized_row=row,
                )
            )
        result = tuple(assignments)
        self._assignments[phase] = result
        return result

    @property
    def total_envs(self) -> int:
        return 64 if self.total_steps == 10 else 4096

    def assignments(self, global_step: int) -> tuple[D1Assignment, ...]:
        phase = self.phase_index(global_step)
        base = self._stage_assignments(phase)
        return tuple(
            D1Assignment(
                global_step=int(global_step),
                env_index=assignment.env_index,
                intended_bucket=assignment.intended_bucket,
                realized_row=assignment.realized_row,
            )
            for assignment in base
        )

    def assignment(self, global_step: int, env_index: int) -> D1Assignment:
        if isinstance(env_index, bool) or not isinstance(env_index, Integral):
            raise TypeError("env_index must be an integer")
        index = int(env_index)
        if index < 0 or index >= self.total_envs:
            raise ValueError(f"env_index must be in [0, {self.total_envs}); got {env_index!r}")
        return self.assignments(global_step)[index]

    def sample(self, global_step: int, *, num_envs: int | None = None) -> tuple[D1Assignment, ...]:
        """Alias used by runtime consumers; sampling remains absolute-step keyed."""

        if num_envs is not None and num_envs != self.total_envs:
            raise ValueError(f"D1 sampler requires num_envs={self.total_envs}")
        return self.assignments(global_step)

    def telemetry(self, global_step: int) -> list[dict[str, Any]]:
        """Return detached intended-bucket plus realized-parameter telemetry."""

        return [assignment.as_dict() for assignment in self.assignments(global_step)]


def canonical_realized_rows(receipt_path: str | Path = DEFAULT_RECEIPT_PATH) -> tuple[CanonicalRealizedRow, ...]:
    """Convenience loader for the immutable A0-A8 canonical rows."""

    return load_d1_catalog(receipt_path).rows


__all__ = [
    "ATLAS_SCHEMA",
    "ATLAS_STATUS",
    "BUCKET_NAMES",
    "CANONICAL_GEOMETRY_SCHEMA",
    "CanonicalRealizedRow",
    "DEFAULT_RECEIPT_PATH",
    "D1Assignment",
    "D1Catalog",
    "D1Sampler",
    "D1Transition",
    "RealizedParameters",
    "RECEIPT_SCHEMA",
    "RECEIPT_STATUS",
    "canonical_realized_rows",
    "load_d1_catalog",
]
