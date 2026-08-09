"""Source-locked partial A0/D0 P0.8 state-bank PLAN/RUN/REDUCE tool."""

from __future__ import annotations

import argparse
import math
import os
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

try:
    from ._v23_common import (
        REPO_ROOT,
        V23_ARTIFACT_PATHS,
        V23_LEGAL_PHYSICAL_GPUS,
        V23_WARM_START_PATH,
        V23Error,
        emit_payload,
        finite_number,
        read_json,
        require_file,
        write_json,
    )
    from .posture_intervention import V23_INTERVENTION_MODES, bind_state_bank_entries
    from .p0_rescue_probe import (
        materialize_d1_capability_bound_plain_manifest,
        _hydra_string,
    )
    from .capability_binding import validate_capability_source_freeze
except ImportError:
    repo_root = Path(__file__).resolve().parents[2]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))
    from scriptsFORhuman.v23._v23_common import (
        REPO_ROOT,
        V23_ARTIFACT_PATHS,
        V23_LEGAL_PHYSICAL_GPUS,
        V23_WARM_START_PATH,
        V23Error,
        emit_payload,
        finite_number,
        read_json,
        require_file,
        write_json,
    )
    from scriptsFORhuman.v23.posture_intervention import (
        V23_INTERVENTION_MODES,
        bind_state_bank_entries,
    )
    from scriptsFORhuman.v23.p0_rescue_probe import (
        materialize_d1_capability_bound_plain_manifest,
        _hydra_string,
    )
    from scriptsFORhuman.v23.capability_binding import validate_capability_source_freeze


RAW_SCHEMA = "a2_piper_v23_p08_state_bank_raw_v1"
ENTRY_SCHEMA = "a2_piper_v23_state_bank_entry_v1"
RECEIPT_SCHEMA = "a2_piper_v23_p08_partial_a0_d0_receipt_v1"
TARGET_STAGES = (2, 3, 4)
FORWARD_MODE = "FULL"
NUM_ENVS = 16
SEED = 0
EFFORT_NM = 40.0
CHECKPOINT_STEP = 1250
SOURCE_FREEZE_PATH = (
    "logs_eval/base_v23/p0/r50_p05_d1_source_20260809/a0_capability_source_freeze.json"
)
SOURCE_SCHEMA = "a2_piper_v23_capability_source_freeze_v1"
SOURCE_STATUS = "CAPABILITY_SOURCE_FROZEN"
SOURCE_CELL = "A0"
SELECTION_BASIS = "CURRENT_EASY_A0_STABLE_REFERENCE"
P05_PURPOSE = "D1_CAPABILITY_SOURCE"
P05_MODE = "FULL"
P05_TOPOLOGY = "canonical16"
P05_BOUND_MANIFEST_SCHEMA = "a2_piper_base_v23_d1_capability_bound_plain16_manifest_v1"
P05_BOUND_MANIFEST_STATUS = "BOUND_D1_CAPABILITY_SOURCE"
P05_BOUND_SELECTOR_MODE = "v23_d1_capability_source_plain16"
P05_BOUND_MANIFEST_FILENAME = "d1_capability_bound_plain_scenario_manifest.json"
P05_EFFORT_FREEZE_PATH = (
    "logs_eval/base_v23/p0/r33_p02_effort_freeze_20260809/effort_freeze.json"
)
P05_ATLAS_PATH = (
    "logs_eval/base_v23/p0/r26_p02_p04_p05_runtime_20260809/p04/door_atlas_raw.json"
)
P05_EXTERNAL_THRESHOLD_PATH = (
    "logs_eval/base_v23/p0/r26_p02_p04_p05_runtime_20260809/p04/door_external_torque_threshold.json"
)
P05_PLAIN_MANIFEST_PATH = (
    "logs_eval/base_v23/p0/r31_p02_temporal_runtime_20260809/torque/effort_40/canonical16/"
    "v23_p0_plain_scenario_manifest.json"
)
P05_CONFIG_ID = "logs_rl/a2_piper_full_stage_a2_base/base_v22/G1/config.yaml"
P05_REQUESTED_PARAMS = {
    "hinge_damping_native": 50.0,
    "hinge_stiffness_native": 2.0,
    "hinge_max_force_nm": 4.5,
    "door_weight_kg": 120.0,
}
P05_NATIVE_PARAMS = {
    "hinge_damping_native": 2864.7890625,
    "hinge_stiffness_native": 114.59156036376953,
    "hinge_effort_limit_nm": 4.5,
    "door_weight_kg": 119.99999237060547,
}
P05_READBACK_SCHEMA = "a2_piper_v23_p05_runtime_physical_readback_v1"
CONFIG_OVERRIDE = "wbmanip/base_v23_p08_a0_d0_state_bank"
RAW_FILENAME = "a2_v23_p08_state_bank_raw.json"
DEFAULT_OUTPUT = REPO_ROOT / V23_ARTIFACT_PATHS["state_bank"]
DEFAULT_RUN_ROOT = REPO_ROOT / "logs_eval/base_v23/p0/state_bank/run"


def _physical_gpu(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value not in V23_LEGAL_PHYSICAL_GPUS:
        raise V23Error(f"physical GPU must be one of {V23_LEGAL_PHYSICAL_GPUS}; got {value!r}")
    return value


def _source_freeze() -> dict[str, Any]:
    payload = read_json(REPO_ROOT / SOURCE_FREEZE_PATH)
    try:
        payload = validate_capability_source_freeze(payload)
    except (TypeError, ValueError) as exc:
        raise V23Error("R50 source freeze failed the registered capability-source validator") from exc
    return payload


def _source_identity() -> dict[str, Any]:
    payload = _source_freeze()
    geometry_id = payload["source_geometry_id"]
    return {
        "source_freeze_path": SOURCE_FREEZE_PATH,
        "schema": SOURCE_SCHEMA,
        "status": SOURCE_STATUS,
        "source_cell": SOURCE_CELL,
        "atlas_cell": SOURCE_CELL,
        "selection_basis": SELECTION_BASIS,
        "effort_nm": EFFORT_NM,
        "source_geometry_id": geometry_id,
    }


def _required_input_paths() -> dict[str, Path]:
    paths = {
        "source_freeze": REPO_ROOT / SOURCE_FREEZE_PATH,
        "effort_freeze": REPO_ROOT / P05_EFFORT_FREEZE_PATH,
        "atlas": REPO_ROOT / P05_ATLAS_PATH,
        "external_threshold": REPO_ROOT / P05_EXTERNAL_THRESHOLD_PATH,
        "plain_manifest": REPO_ROOT / P05_PLAIN_MANIFEST_PATH,
        "checkpoint": REPO_ROOT / V23_WARM_START_PATH,
        "config": REPO_ROOT / P05_CONFIG_ID,
    }
    for label, path in paths.items():
        require_file(path, label=f"R50/R54 {label}")
    return {label: path.resolve() for label, path in paths.items()}


def _validate_r50_r54_inputs(paths: Mapping[str, Path]) -> dict[str, Any]:
    source_freeze = _source_freeze()
    if source_freeze.get("purpose") != P05_PURPOSE or source_freeze.get("source_cell_id") != SOURCE_CELL:
        raise V23Error("R50 source freeze purpose/cell is not D1 capability-source A0")
    if source_freeze.get("requested_params") != P05_REQUESTED_PARAMS:
        raise V23Error("R50 requested A0 parameters disagree with the fixed P0.5 contract")
    if source_freeze.get("native_params") != P05_NATIVE_PARAMS:
        raise V23Error("R50 native A0 parameters disagree with the fixed P0.5 contract")
    if source_freeze.get("source_paths") != {
        "atlas": str(paths["atlas"]),
        "effort_freeze": str(paths["effort_freeze"]),
        "external_threshold": str(paths["external_threshold"]),
    }:
        raise V23Error("R50 source paths do not bind the exact R33/R26 inputs")
    effort = read_json(paths["effort_freeze"])
    if (
        effort.get("schema") != "a2_piper_v23_effort_freeze_v1"
        or effort.get("status") != "MEASURED_FREEZE"
        or effort.get("selected_effort_nm") != EFFORT_NM
        or effort.get("effort_profile") != {"effort_nm": EFFORT_NM, "name": "base_v23_p0_effort_40"}
    ):
        raise V23Error("R33 effort freeze is not the measured 40 N*m source")
    atlas = read_json(paths["atlas"])
    if atlas.get("schema") != "a2_piper_v23_door_atlas_raw_v1" or atlas.get("status") != "MEASURED_RAW":
        raise V23Error("R26 atlas input is not the measured raw atlas")
    atlas_rows = atlas.get("rows")
    if not isinstance(atlas_rows, list) or len(atlas_rows) != 9:
        raise V23Error("R26 atlas input must contain the measured A0-A8 rows")
    a0_rows = [row for row in atlas_rows if isinstance(row, Mapping) and row.get("cell_id") == SOURCE_CELL]
    if len(a0_rows) != 1 or a0_rows[0].get("geometry_id") != source_freeze["source_geometry_id"]:
        raise V23Error("R26 atlas A0 row does not match the R50 source geometry")
    external = read_json(paths["external_threshold"])
    if external.get("schema") != "a2_piper_v23_door_external_torque_threshold_v1" or external.get("status") != "MEASURED_RAW":
        raise V23Error("R26 external-threshold input is not the measured raw contract")
    if not isinstance(external.get("rows"), list) or len(external["rows"]) != 180:
        raise V23Error("R26 external-threshold input must contain 180 measured rows")
    plain = read_json(paths["plain_manifest"])
    if (
        plain.get("schema") != "a2_piper_base_v23_p0_plain_scenario_manifest_v1"
        or plain.get("status") != "STATIC_PLAIN"
        or plain.get("topology") != P05_TOPOLOGY
        or not isinstance(plain.get("rows"), list)
        or len(plain["rows"]) != NUM_ENVS
    ):
        raise V23Error("R31 canonical16 plain manifest is not the exact 16-row source")
    return {
        "source_freeze": source_freeze,
        "effort_freeze": effort,
        "atlas": atlas,
        "external_threshold": external,
        "plain_manifest": plain,
    }


def build_plan(*, output: Path = DEFAULT_OUTPUT, gpu: int | None = None) -> dict[str, Any]:
    """Build the source-locked single-process P0.8 plan without launching eval."""

    input_paths = _required_input_paths()
    inputs = _validate_r50_r54_inputs(input_paths)
    source = _source_identity()
    checkpoint = input_paths["checkpoint"]
    if gpu is not None:
        _physical_gpu(gpu)
    return {
        "schema": "a2_piper_v23_p08_state_bank_plan_v1",
        "status": "PLAN_ONLY",
        "config": CONFIG_OVERRIDE,
        "checkpoint": str(checkpoint),
        "checkpoint_step": CHECKPOINT_STEP,
        "checkpoint_load_mode": "policy_only",
        "warm_config": str(input_paths["config"]),
        "seed": SEED,
        "num_envs": NUM_ENVS,
        "target_stages": list(TARGET_STAGES),
        "forward_mode": FORWARD_MODE,
        "purpose": P05_PURPOSE,
        "topology": P05_TOPOLOGY,
        "bound_manifest_contract": {
            "schema": P05_BOUND_MANIFEST_SCHEMA,
            "status": P05_BOUND_MANIFEST_STATUS,
            "selector_mode": P05_BOUND_SELECTOR_MODE,
            "filename": P05_BOUND_MANIFEST_FILENAME,
        },
        "source_inputs": {
            "source_freeze": str(input_paths["source_freeze"]),
            "effort_freeze": str(input_paths["effort_freeze"]),
            "atlas": str(input_paths["atlas"]),
            "external_threshold": str(input_paths["external_threshold"]),
            "plain_manifest": str(input_paths["plain_manifest"]),
        },
        "requested_params": dict(inputs["source_freeze"]["requested_params"]),
        "native_params": dict(inputs["source_freeze"]["native_params"]),
        "physical_binding_required": True,
        "physical_readback_schema": P05_READBACK_SCHEMA,
        "intervention_modes": list(V23_INTERVENTION_MODES),
        "source_identity": source,
        "effort_nm": EFFORT_NM,
        "physical_gpu": gpu,
        "process_topology": "one fresh single-process evaluator; no retry",
        "normal_eval_finalization": True,
        "raw_output_filename": RAW_FILENAME,
        "canonical_output": str(Path(output).resolve()),
        "excluded_claims": [
            "NO_EXACT_STATE_CLONE",
            "NO_RECURRENT_STATE_RESTORE",
            "NO_INTERVENTION_EFFECT_OR_DELTA_J_CLAIM",
            "NO_D1_E_ZONE_OR_FORMAL_ADMISSION",
            "NO_RELEASE_RECEIPT",
        ],
    }


def materialize_bound_manifest(*, plan: Mapping[str, Any], output_root: Path) -> Path:
    """Materialize the exact D1 bound selector inside this fresh P0.8 root."""

    output_root = Path(output_root).resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    manifest_path = output_root / P05_BOUND_MANIFEST_FILENAME
    if manifest_path.exists():
        raise V23Error(f"refusing to overwrite a bound manifest: {manifest_path}")
    source_paths = plan.get("source_inputs")
    if not isinstance(source_paths, Mapping):
        raise V23Error("P0.8 plan has no source input paths for bound-manifest materialization")
    source_payload = read_json(source_paths["plain_manifest"])
    capability_source = read_json(source_paths["source_freeze"])
    bound = materialize_d1_capability_bound_plain_manifest(
        manifest_path,
        source_payload=source_payload,
        topology=P05_TOPOLOGY,
        capability_source_freeze=capability_source,
        capability_source_freeze_path=source_paths["source_freeze"],
    )
    if (
        bound.get("schema") != P05_BOUND_MANIFEST_SCHEMA
        or bound.get("status") != P05_BOUND_MANIFEST_STATUS
        or bound.get("purpose") != P05_PURPOSE
        or bound.get("selector_mode") != P05_BOUND_SELECTOR_MODE
        or bound.get("topology") != P05_TOPOLOGY
        or len(bound.get("rows", [])) != NUM_ENVS
    ):
        raise V23Error("fresh bound manifest failed the R54 D1 capability-source contract")
    return manifest_path


def build_run_command(
    *,
    plan: Mapping[str, Any],
    output_root: Path,
    gpu: int,
    bound_manifest_path: Path | None = None,
) -> tuple[list[str], dict[str, str]]:
    """Build exactly one source-locked evaluator process command."""

    physical_gpu = _physical_gpu(gpu)
    output_root = Path(output_root).resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    checkpoint = require_file(plan["checkpoint"], label="P0.8 warm checkpoint")
    if plan.get("purpose") != P05_PURPOSE or plan.get("topology") != P05_TOPOLOGY:
        raise V23Error("P0.8 RUN requires the D1 capability-source FULL canonical16 plan")
    if bound_manifest_path is None:
        bound_manifest_path = output_root / P05_BOUND_MANIFEST_FILENAME
    bound_manifest_path = Path(bound_manifest_path).resolve()
    if not bound_manifest_path.is_file():
        raise V23Error(f"P0.8 RUN requires the fresh bound manifest: {bound_manifest_path}")
    source_paths = plan.get("source_inputs")
    if not isinstance(source_paths, Mapping):
        raise V23Error("P0.8 plan has no R50/R54 source inputs")
    source = plan["source_identity"]
    native = plan["native_params"]
    requested = plan["requested_params"]
    argv = [
        sys.executable,
        "-m",
        "gr00t.rl.eval_agent_trl",
        f"+ablation={CONFIG_OVERRIDE}",
        f"++checkpoint={checkpoint}",
        "++checkpoint_load_mode=policy_only",
        "++auto_load_latest=false",
        "++num_envs=16",
        "++num_gpus=1",
        "++multi_gpu=false",
        "++seed=0",
        "++headless=true",
        "++use_wandb=false",
        "++algo.trl.report_to=none",
        "++algo.config.eval.eval_num_envs_episodes=true",
        "++algo.config.eval.num_eval_episodes=16",
        "++algo.config.eval.a2_v23_p08_state_bank_export=true",
        "++algo.config.eval.a2_v23_p08_target_stages=[2,3,4]",
        "++algo.config.eval.a2_v23_p08_forward_mode=FULL",
        "++algo.config.eval.a2_v23_p05_runtime_export=false",
        "++algo.config.eval.a2_v23_stationary_rent_export=false",
        "++env.config.a2_v20_R2_evidence_enabled=false",
        "++env.config.a2_v23_p0_plain_scenario_enabled=true",
        "++env.config.a2_v23_p0_bound_plain_scenario_enabled=true",
        "++env.config.a2_v23_p0_scenario_topology=canonical16",
        f"++env.config.a2_v23_p0_scenario_manifest_path={bound_manifest_path}",
        f"++env.config.a2_v23_p0_bound_plain_scenario_manifest_path={bound_manifest_path}",
        "++env.config.a2_v23_p05_checkpoint_load_mode=policy_only",
        "++env.config.a2_v23_p05_seed=0",
        "++env.config.a2_v23_p05_runtime_enabled=true",
        "++env.config.a2_v23_p05_purpose=D1_CAPABILITY_SOURCE",
        "++env.config.a2_v23_p05_mode=FULL",
        "++env.config.a2_v23_p05_topology=canonical16",
        "++env.config.a2_v23_p05_cell_id=A0",
        f"++env.config.a2_v23_p05_geometry_id={_hydra_string(source['source_geometry_id'])}",
        f"++env.config.a2_v23_p05_requested_hinge_damping_native={requested['hinge_damping_native']!r}",
        f"++env.config.a2_v23_p05_requested_hinge_stiffness_native={requested['hinge_stiffness_native']!r}",
        f"++env.config.a2_v23_p05_requested_hinge_max_force_nm={requested['hinge_max_force_nm']!r}",
        f"++env.config.a2_v23_p05_requested_door_weight_kg={requested['door_weight_kg']!r}",
        f"++env.config.a2_v23_p05_hinge_damping_native={native['hinge_damping_native']!r}",
        f"++env.config.a2_v23_p05_hinge_stiffness_native={native['hinge_stiffness_native']!r}",
        f"++env.config.a2_v23_p05_hinge_effort_limit_nm={native['hinge_effort_limit_nm']!r}",
        f"++env.config.a2_v23_p05_door_weight_kg={native['door_weight_kg']!r}",
        f"++env.config.a2_v23_p05_effort_freeze_path={source_paths['effort_freeze']}",
        f"++env.config.a2_v23_p05_atlas_manifest_path={source_paths['atlas']}",
        f"++env.config.a2_v23_p05_external_threshold_path={source_paths['external_threshold']}",
        f"++env.config.a2_v23_p05_plain_manifest_path={source_paths['plain_manifest']}",
        f"++env.config.a2_v23_p05_bound_plain_manifest_path={bound_manifest_path}",
        f"++env.config.a2_v23_p05_capability_source_freeze_path={source_paths['source_freeze']}",
        "++env.config.a2_v23_p05_effort_profile_nm=40.0",
        f"++env.config.a2_v23_p05_checkpoint={V23_WARM_START_PATH}",
        f"++env.config.a2_v23_p05_config_id={P05_CONFIG_ID}",
        "++env.config.a2_v23_stationary_rent_runtime_enabled=false",
        "++env.config.a2_v23_rp0_enabled=false",
        "++env.config.a2_v23_effort_profile_nm=40.0",
        "++simulator.config.cameras.enable_cameras=false",
        "++simulator.config.render_results=false",
        f"++eval_output_dir={output_root}",
    ]
    env = {
        "CUDA_VISIBLE_DEVICES": str(physical_gpu),
        "ACCELERATE_TORCH_DEVICE": "cuda:0",
        "WANDB_MODE": "disabled",
        "PYTHONPATH": str(REPO_ROOT),
    }
    return argv, env


def execute_plan(
    *,
    plan: Mapping[str, Any],
    gpu: int,
    output_root: Path,
    output: Path,
) -> dict[str, Any]:
    """Run one fresh process once, then reduce its raw capture exactly once."""

    output_root = Path(output_root).resolve()
    if output_root.exists() and any(output_root.iterdir()):
        raise V23Error(f"refusing to reuse non-empty P0.8 output directory: {output_root}")
    output_root.mkdir(parents=True, exist_ok=True)
    bound_manifest_path = materialize_bound_manifest(plan=plan, output_root=output_root)
    argv, env = build_run_command(
        plan=plan,
        output_root=output_root,
        gpu=gpu,
        bound_manifest_path=bound_manifest_path,
    )
    result = subprocess.run(argv, cwd=REPO_ROOT, env={**os.environ, **env}, check=False)
    if result.returncode != 0:
        raise V23Error(f"P0.8 evaluator process failed with returncode={result.returncode}")
    raw_path = output_root / RAW_FILENAME
    if not raw_path.is_file():
        raise V23Error(f"P0.8 evaluator exited without its raw capture: {raw_path}")
    receipt, reduction_exit_code = reduce_raw_capture(raw_path=raw_path, output=output)
    return {
        **dict(plan),
        "status": "RUN_COMPLETED",
        "physical_gpu": gpu,
        "logical_device": "cuda:0",
        "command": shlex.join(argv),
        "raw_capture_path": str(raw_path),
        "bound_manifest_path": str(bound_manifest_path),
        "returncode": int(result.returncode),
        "reduction_status": receipt["status"],
        "reduction_exit_code": int(reduction_exit_code),
        "receipt_path": str(Path(output).resolve()),
        "retry_policy": "none",
    }


def _validate_prefix_row(
    row: Mapping[str, Any],
    *,
    env_id: int,
    episode_index: int,
    episode_id: str,
    row_index: int,
    actor_width: int | None,
) -> int:
    if row.get("schema") != "a2_piper_v23_state_bank_prefix_row_v1":
        raise V23Error(f"state-bank prefix row {row_index} schema is unsupported")
    if (
        row.get("env_id") != env_id
        or row.get("episode_index") != episode_index
        or row.get("episode_id") != episode_id
    ):
        raise V23Error("state-bank prefix row env/episode identity disagrees")
    if row.get("control_step") != row_index or row.get("done_before_step") is not False:
        raise V23Error("state-bank prefix rows must be contiguous pre-step rows from control_step 0")
    actor_obs = row.get("actor_obs")
    action_mean = row.get("action_mean")
    applied = row.get("applied_high_level_action")
    if not isinstance(actor_obs, list) or not actor_obs:
        raise V23Error("state-bank actor_obs must be a non-empty list")
    if actor_width is not None and len(actor_obs) != actor_width:
        raise V23Error("state-bank actor_obs width disagrees across contiguous prefix rows")
    if not isinstance(action_mean, list) or not action_mean:
        raise V23Error("state-bank action_mean must be a non-empty list")
    if not isinstance(applied, list) or len(applied) != 12:
        raise V23Error("state-bank applied_high_level_action must be exactly 12-D")
    for name, values in (("actor_obs", actor_obs), ("action_mean", action_mean), ("applied_high_level_action", applied)):
        for index, value in enumerate(values):
            finite_number(value, name=f"prefix.{name}[{row_index}][{index}]")
    return len(actor_obs)


def _validate_physical_readback(
    readback: Mapping[str, Any],
    *,
    source: Mapping[str, Any],
    canonical_geometry: Mapping[str, Any],
    env_id: int,
) -> dict[str, Any]:
    if (
        readback.get("schema") != P05_READBACK_SCHEMA
        or readback.get("authority") != "P0.5_PUBLIC_TYPED_EPISODE_GETTER"
        or readback.get("env_id") != env_id
        or readback.get("episode_index") != 0
        or readback.get("episode_id") != f"a2-v23-p05-env{env_id}-episode0"
        or readback.get("purpose") != P05_PURPOSE
        or readback.get("mode") != P05_MODE
        or readback.get("topology") != P05_TOPOLOGY
        or readback.get("cell_id") != SOURCE_CELL
        or readback.get("geometry_id") != source["source_geometry_id"]
        or readback.get("canonical_geometry") != canonical_geometry
        or readback.get("requested_params") != P05_REQUESTED_PARAMS
        or readback.get("native_params") != P05_NATIVE_PARAMS
        or readback.get("applied_native_params") != P05_NATIVE_PARAMS
        or readback.get("readback_native_params") != P05_NATIVE_PARAMS
    ):
        raise V23Error(f"P0.5 physical readback env{env_id} disagrees with R50 native A0 identity")
    mass_inertia = readback.get("mass_inertia_receipt")
    if (
        not isinstance(mass_inertia, Mapping)
        or mass_inertia.get("schema") != "a2_piper_v23_p05_mass_inertia_receipt_v1"
        or mass_inertia.get("env_id") != env_id
        or mass_inertia.get("applied_once") is not True
    ):
        raise V23Error(f"P0.5 physical readback env{env_id} mass/inertia receipt is not authoritative")
    if not math.isclose(
        float(mass_inertia.get("applied_panel_mass_kg")),
        P05_NATIVE_PARAMS["door_weight_kg"],
        rel_tol=0.0,
        abs_tol=1.0e-5,
    ):
        raise V23Error(f"P0.5 physical readback env{env_id} mass disagrees with R50 native weight")
    for field in ("expected_scaled_panel_inertia", "readback_panel_inertia"):
        values = mass_inertia.get(field)
        if (
            not isinstance(values, list)
            or len(values) != 9
            or any(
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(float(value))
                for value in values
            )
        ):
            raise V23Error(f"P0.5 physical readback env{env_id} {field} is invalid")
    if any(
        not math.isclose(float(actual), float(expected), rel_tol=0.0, abs_tol=1.0e-5)
        for actual, expected in zip(
            mass_inertia["readback_panel_inertia"], mass_inertia["expected_scaled_panel_inertia"]
        )
    ):
        raise V23Error(f"P0.5 physical readback env{env_id} inertia disagrees with the applied write")
    return dict(readback)


def _validate_raw_payload(
    payload: Mapping[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]], list[int]]:
    if payload.get("schema") != RAW_SCHEMA:
        raise V23Error(f"raw state-bank payload must use {RAW_SCHEMA}")
    if payload.get("target_stages") != list(TARGET_STAGES):
        raise V23Error("raw state-bank target stages must be exactly [2, 3, 4]")
    if payload.get("forward_only") is not True or payload.get("state_clone_supported") is not False:
        raise V23Error("raw state-bank payload violates forward-only state contract")
    if payload.get("recurrent_state_restore_supported") is not False:
        raise V23Error("raw state-bank payload must not claim recurrent-state restore")
    if payload.get("normal_eval_finalization") is not True or payload.get("completed_episodes") != NUM_ENVS:
        raise V23Error("raw state-bank payload must preserve normal 16-first-episode finalization")
    if (
        payload.get("checkpoint") != V23_WARM_START_PATH
        or payload.get("checkpoint_load_mode") != "policy_only"
        or payload.get("checkpoint_step") != CHECKPOINT_STEP
    ):
        raise V23Error("raw state-bank policy anchor is not v22 G1 step1250 policy_only")
    if payload.get("seed") != SEED or payload.get("num_envs") != NUM_ENVS:
        raise V23Error("raw state-bank seed/num_envs identity disagrees")
    source = _source_identity()
    source_freeze = _source_freeze()
    physical_readback = payload.get("physical_readback")
    if not isinstance(physical_readback, list) or len(physical_readback) != NUM_ENVS:
        raise V23Error("raw state-bank payload requires one P0.5 physical readback per canonical16 env")
    by_env = {}
    for readback in physical_readback:
        if not isinstance(readback, Mapping):
            raise V23Error("raw state-bank physical readback rows must be mappings")
        env_id = readback.get("env_id")
        if env_id in by_env:
            raise V23Error("raw state-bank physical readback contains duplicate env ids")
        by_env[env_id] = _validate_physical_readback(
            readback,
            source=source,
            canonical_geometry=source_freeze["canonical_geometry"],
            env_id=env_id,
        )
    if set(by_env) != set(range(NUM_ENVS)):
        raise V23Error("raw state-bank physical readback must cover env ids 0..15")
    if payload.get("source_identity") != source:
        raise V23Error("raw state-bank source identity disagrees with the fixed R50 A0 freeze")
    status = payload.get("status")
    if status not in {"RAW_CAPTURE_COMPLETE", "PARTIAL_A0_D0_PREFIX_COVERAGE_INCOMPLETE"}:
        raise V23Error(f"raw state-bank status is unsupported: {status!r}")
    entries = payload.get("entries")
    if not isinstance(entries, list):
        raise V23Error("raw state-bank entries must be a list")
    seen_stages = set()
    actor_width = None
    normalized = []
    for index, entry in enumerate(entries):
        if not isinstance(entry, Mapping) or entry.get("schema") != ENTRY_SCHEMA:
            raise V23Error(f"raw state-bank entry {index} schema is unsupported")
        stage = entry.get("stage")
        if isinstance(stage, bool) or not isinstance(stage, int) or stage not in TARGET_STAGES:
            raise V23Error(f"raw state-bank entry {index} stage is not one of {TARGET_STAGES}")
        if stage in seen_stages:
            raise V23Error(f"raw state-bank contains duplicate stage {stage}")
        seen_stages.add(stage)
        for field in ("entry_id", "scenario_id", "episode_id", "replay_prefix_id"):
            if not isinstance(entry.get(field), str) or not entry[field]:
                raise V23Error(f"raw state-bank entry {index} {field} is missing/non-empty")
        if entry.get("source_identity") != source or entry.get("forward_mode") != FORWARD_MODE:
            raise V23Error(f"raw state-bank entry {index} source/mode identity disagrees")
        if (
            entry.get("state_clone_supported") is not False
            or entry.get("recurrent_state_restore_supported") is not False
            or entry.get("recurrent_prefix_status") != "CAPTURED_NOT_REEXECUTED"
            or entry.get("capture_selection") != "FIRST_TARGET_STEP_LOWEST_ENV_ID"
            or entry.get("reset_origin") != "evaluator.reset_all_first_episode_observation"
        ):
            raise V23Error(f"raw state-bank entry {index} violates the forward-only capture contract")
        env_id = entry.get("env_id")
        episode_index = entry.get("episode_index")
        if isinstance(env_id, bool) or not isinstance(env_id, int) or not 0 <= env_id < NUM_ENVS:
            raise V23Error(f"raw state-bank entry {index} env_id is invalid")
        if isinstance(episode_index, bool) or not isinstance(episode_index, int) or episode_index < 0:
            raise V23Error(f"raw state-bank entry {index} episode_index is invalid")
        if entry.get("atlas_cell") != SOURCE_CELL or entry.get("source_cell") != SOURCE_CELL:
            raise V23Error(f"raw state-bank entry {index} A0 labels were not gated by physical readback")
        if entry.get("physical_readback_env_id") != env_id or env_id not in by_env:
            raise V23Error(f"raw state-bank entry {index} lacks its authoritative physical readback identity")
        prefix = entry.get("replay_prefix")
        if not isinstance(prefix, list) or not prefix:
            raise V23Error(f"raw state-bank entry {index} replay_prefix is missing/non-empty")
        for row_index, row in enumerate(prefix):
            if not isinstance(row, Mapping):
                raise V23Error(f"raw state-bank entry {index} prefix row {row_index} is not a mapping")
            actor_width = _validate_prefix_row(
                row,
                env_id=env_id,
                episode_index=episode_index,
                episode_id=entry["episode_id"],
                row_index=row_index,
                actor_width=actor_width,
            )
        if prefix[-1].get("pre_stage") != stage:
            raise V23Error(f"raw state-bank entry {index} final pre-stage does not match its stage")
        if entry.get("reset_origin") != "evaluator.reset_all_first_episode_observation":
            raise V23Error(f"raw state-bank entry {index} reset origin is not the evaluator reset")
        normalized.append(dict(entry))
    missing = [stage for stage in TARGET_STAGES if stage not in seen_stages]
    if payload.get("captured_stages") != sorted(seen_stages):
        raise V23Error("raw state-bank captured_stages does not match its entries")
    if payload.get("missing_stages") != missing:
        raise V23Error("raw state-bank missing_stages does not match its entries")
    if missing and status != "PARTIAL_A0_D0_PREFIX_COVERAGE_INCOMPLETE":
        raise V23Error("raw state-bank missing coverage must use the typed incomplete status")
    if not missing and status != "RAW_CAPTURE_COMPLETE":
        raise V23Error("raw state-bank complete coverage must use RAW_CAPTURE_COMPLETE")
    return source, normalized, [by_env[env_id] for env_id in range(NUM_ENVS)], missing


def reduce_raw_capture(*, raw_path: Path, output: Path) -> tuple[dict[str, Any], int]:
    """Reduce one raw payload exactly once into the partial P0.8 receipt."""

    payload = read_json(raw_path)
    source, entries, physical_readback, missing = _validate_raw_payload(payload)
    bindings = []
    if not missing:
        bindings = bind_state_bank_entries(entries, source_identity=source)
    receipt_status = (
        "PARTIAL_A0_D0_PLUMBING_RUNTIME_VERIFIED"
        if not missing
        else "PARTIAL_A0_D0_PREFIX_COVERAGE_INCOMPLETE"
    )
    receipt = {
        "schema": RECEIPT_SCHEMA,
        "status": receipt_status,
        "p08_overall_status": "PARTIAL_INCOMPLETE",
        "p09_d0_smoke_admission": not missing,
        "formal_admission": False,
        "release_receipt": False,
        "forward_only": True,
        "state_clone_supported": False,
        "recurrent_state_restore_supported": False,
        "recurrent_prefix_status": "CAPTURED_NOT_REEXECUTED",
        "target_stages": list(TARGET_STAGES),
        "intervention_modes": list(V23_INTERVENTION_MODES),
        "captured_stages": [entry["stage"] for entry in entries],
        "missing_stages": missing,
        "source_identity": source,
        "physical_readback": physical_readback,
        "physical_readback_count": len(physical_readback),
        "checkpoint": payload["checkpoint"],
        "checkpoint_load_mode": "policy_only",
        "checkpoint_step": CHECKPOINT_STEP,
        "seed": SEED,
        "num_envs": NUM_ENVS,
        "entries": entries,
        "bindings": bindings,
        "binding_count": len(bindings),
        "excluded_claims": [
            "NO_EXACT_STATE_CLONE",
            "NO_RECURRENT_STATE_RESTORE",
            "NO_INTERVENTION_EFFECT_OR_DELTA_J_CLAIM",
            "NO_D1_E_ZONE_OR_FORMAL_ADMISSION",
            "NO_RELEASE_RECEIPT",
            "NO_ALTERNATE_MODE_EXECUTION",
        ],
        "typed_exit_code": 2 if missing else 0,
    }
    write_json(output, receipt)
    return receipt, (2 if missing else 0)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("PLAN", "RUN", "REDUCE"), required=True)
    parser.add_argument("--gpu", type=int, default=None)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_RUN_ROOT)
    parser.add_argument("--input", type=Path, default=None)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)

    if args.mode == "PLAN":
        payload = build_plan(output=args.output, gpu=args.gpu)
        emit_payload(payload, args.output)
        return 0
    if args.mode == "RUN":
        if args.gpu is None:
            raise V23Error("P0.8 RUN requires one explicitly selected physical GPU")
        plan = build_plan(output=args.output, gpu=args.gpu)
        payload = execute_plan(
            plan=plan,
            gpu=args.gpu,
            output_root=args.output_root,
            output=args.output,
        )
        emit_payload(payload)
        return int(payload["reduction_exit_code"])

    raw_path = args.input or (Path(args.output_root) / RAW_FILENAME)
    receipt, exit_code = reduce_raw_capture(raw_path=raw_path, output=args.output)
    emit_payload(receipt)
    return exit_code


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except V23Error as exc:
        raise SystemExit(f"V23 P0.8 STATE BANK FAIL: {exc}")
