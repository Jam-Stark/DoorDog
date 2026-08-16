"""P0/P1 runtime compatibility and production-reset receipt harness.

The harness runs the same selected policy through the current checkout and a
detached, clean baseline checkout.  The trainer's opt-in trace is compared on
the canonical 16-environment, first-episode contract.  A third current-only
run enables the native v24 hinge-friction backend and checks the production
reset readback receipt, including staged-reset provenance.

No IsaacSim modules are imported by this producer.  ``--plan`` therefore
prints the exact runtime commands without starting a simulator.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import shutil
import subprocess
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any


SCHEMA = "a2_piper_v24_p0_p1_runtime_compatibility_receipt_v1"
TRACE_SCHEMA = "a2_piper_v24_p0_compatibility_trace_v1"
TRACE_ENV_COUNT = 16
ACTOR_OBS_DIM = 133
ACTION_DIM = 12
FINAL_ACTION_DIM = 24
TRACE_ATOL = 1.0e-6
SOURCE_BASELINE_COMMIT = "5227a9b57a5ec6198fd7bf2c9f3d323005d18c02"
TRAINER_TRACE_PATH = "gr00t/rl/trl/trainer/ppo_trainer_a2_base_api.py"
SELECTED_CHECKPOINT = Path(
    "logs_rl/a2_piper_full_stage_a2_base/base_v23/seed0/G7/model_step_001500.pt"
)
FRICTION_BACKEND = "native_joint_friction_v1"
FRICTION_FIELDS = (
    "joint_friction_coeff",
    "joint_dynamic_friction_coeff",
    "joint_viscous_friction_coeff",
)
DEFAULT_STATIC_EFFORT = 1.0
DEFAULT_DYNAMIC_EFFORT = 0.75
DEFAULT_VISCOUS_COEFFICIENT = 0.0


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _regular_file(path: Path, *, label: str) -> Path:
    path = path.expanduser().resolve()
    if path.is_symlink() or not path.is_file():
        raise RuntimeError(f"{label} must be a regular file: {path}")
    return path


def _directory(path: Path, *, label: str) -> Path:
    path = path.expanduser().resolve()
    if path.is_symlink() or not path.is_dir():
        raise RuntimeError(f"{label} must be a regular directory: {path}")
    return path


def _git(root: Path, *args: str) -> str:
    try:
        return subprocess.check_output(
            ["git", "-C", str(root), *args],
            text=True,
            stderr=subprocess.STDOUT,
        ).strip()
    except (OSError, subprocess.CalledProcessError) as exc:
        output = getattr(exc, "output", "")
        raise RuntimeError(f"git identity check failed for {root}: {output}") from exc


def _validate_baseline(root: Path) -> dict[str, str]:
    root = _directory(root, label="baseline root")
    current = _repo_root()
    if root == current:
        raise RuntimeError("baseline root must be distinct from the current checkout")
    status = _git(root, "status", "--porcelain")
    if status:
        raise RuntimeError("baseline checkout must be clean; refusing to run on dirty paths")
    try:
        branch = _git(root, "symbolic-ref", "--quiet", "--short", "HEAD")
    except RuntimeError:
        branch = "DETACHED"
    if branch != "DETACHED":
        raise RuntimeError(f"baseline checkout must be detached; got branch {branch!r}")
    instrumentation_commit = _git(root, "rev-parse", "HEAD")
    try:
        source_commit = _git(root, "rev-parse", "HEAD^")
    except RuntimeError as exc:
        raise RuntimeError("baseline must contain one detached instrumentation commit") from exc
    if source_commit != SOURCE_BASELINE_COMMIT:
        raise RuntimeError(
            "baseline instrumentation commit must have exact source baseline parent "
            f"{SOURCE_BASELINE_COMMIT}; got {source_commit}."
        )
    changed_paths = _git(root, "diff", "--name-only", f"{source_commit}..{instrumentation_commit}").splitlines()
    if changed_paths != [TRAINER_TRACE_PATH]:
        raise RuntimeError(
            "baseline instrumentation commit must change exactly the trainer trace path; "
            f"got {changed_paths!r}."
        )
    trainer_path = root / TRAINER_TRACE_PATH
    trainer_text = trainer_path.read_text(encoding="utf-8")
    required_symbols = (
        "_A2_P0_COMPAT_TRACE_SCHEMA",
        "_read_a2_p0_compatibility_trace_config",
        "a2_p0_compatibility_trace_enabled",
    )
    if any(symbol not in trainer_text for symbol in required_symbols):
        raise RuntimeError("baseline instrumentation commit is missing the compatibility trace symbols")
    if "a2_v24_friction" in trainer_text or "a2_v24_friction.py" in trainer_text:
        raise RuntimeError("baseline instrumentation must not include friction module/import/config changes")
    return {
        "path": str(root),
        "source_git_commit": source_commit,
        "instrumentation_git_commit": instrumentation_commit,
        "instrumentation_path": str(trainer_path),
        "config_identity": {
            "changed_paths": changed_paths,
            "friction_changes": False,
            "trace_symbols": list(required_symbols),
        },
    }


def _finite(value: Any, *, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise RuntimeError(f"{label} must be numeric; got {value!r}")
    value = float(value)
    if not math.isfinite(value):
        raise RuntimeError(f"{label} must be finite")
    return value


def _finite_vector(value: Any, *, length: int, label: str) -> list[float]:
    if not isinstance(value, list) or len(value) != length:
        raise RuntimeError(f"{label} must be a list of length {length}")
    return [_finite(item, label=f"{label}[{index}]") for index, item in enumerate(value)]


def _validate_foot_feature(feature: Any, *, label: str) -> dict[str, Any]:
    if not isinstance(feature, Mapping):
        raise RuntimeError(f"{label} must be a mapping")
    if feature.get("schema") != "a2_piper_v24_foot_force_feature_v1":
        raise RuntimeError(f"{label} has an unexpected schema")
    status = feature.get("status")
    if status == "FOOT_FORCE_SOURCE_UNAVAILABLE":
        if "normal_force_z" in feature or "normal_force_tensor" in feature:
            raise RuntimeError(f"{label} unavailable status must not carry numeric force data")
        return dict(feature)
    if status != "FOOT_FORCE_SOURCE_AVAILABLE":
        raise RuntimeError(f"{label} has unknown status {status!r}")
    if feature.get("body_names") != ["FL_foot", "RL_foot", "FR_foot", "RR_foot"]:
        raise RuntimeError(f"{label} body names are not canonical")
    body_ids = feature.get("body_ids")
    if (
        not isinstance(body_ids, list)
        or len(body_ids) != 4
        or any(isinstance(value, bool) or not isinstance(value, int) for value in body_ids)
        or feature.get("normal_axis") != 2
    ):
        raise RuntimeError(f"{label} body ids/normal axis are invalid")
    normal_force_z = feature.get("normal_force_z")
    if not isinstance(normal_force_z, list) or len(normal_force_z) != TRACE_ENV_COUNT:
        raise RuntimeError(f"{label} normal_force_z must contain 16 environment rows")
    for env_id, row in enumerate(normal_force_z):
        _finite_vector(row, length=4, label=f"{label}.normal_force_z[{env_id}]")
    return dict(feature)


def _load_json(path: Path, *, label: str) -> dict[str, Any]:
    path = _regular_file(path, label=label)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"{label} is not valid JSON: {path}") from exc
    if not isinstance(payload, dict):
        raise RuntimeError(f"{label} root must be a mapping")
    return payload


def _validate_trace(path: Path, *, label: str) -> dict[str, Any]:
    payload = _load_json(path, label=label)
    if payload.get("schema") != TRACE_SCHEMA or payload.get("status") != "RUNTIME_VERIFIED":
        raise RuntimeError(f"{label} has an unexpected schema/status")
    topology = payload.get("topology")
    if not isinstance(topology, Mapping) or topology.get("name") != "canonical16":
        raise RuntimeError(f"{label} must declare canonical16 topology")
    if topology.get("episode_count") != TRACE_ENV_COUNT or topology.get("first_episode_only") is not True:
        raise RuntimeError(f"{label} must contain exactly one first episode for each of 16 environments")
    if (
        payload.get("actor_obs_dim") != ACTOR_OBS_DIM
        or payload.get("raw_action_dim") != ACTION_DIM
        or payload.get("final_action_dim") != FINAL_ACTION_DIM
    ):
        raise RuntimeError(f"{label} has an unexpected actor/action dimension")
    foot_feature = _validate_foot_feature(payload.get("foot_force_feature"), label=f"{label}.foot_force_feature")
    rows_by_env = payload.get("rows_by_env")
    if not isinstance(rows_by_env, list) or len(rows_by_env) != TRACE_ENV_COUNT:
        raise RuntimeError(f"{label} rows_by_env must contain 16 environment rows")
    for env_id, rows in enumerate(rows_by_env):
        if not isinstance(rows, list) or not rows:
            raise RuntimeError(f"{label} env_id={env_id} has no trace rows")
        for row_index, row in enumerate(rows):
            if not isinstance(row, Mapping):
                raise RuntimeError(f"{label} env_id={env_id} row={row_index} is not a mapping")
            if row.get("env_id") != env_id or row.get("episode_index") != 0:
                raise RuntimeError(f"{label} has a non-canonical environment/episode identity")
            if isinstance(row.get("control_step"), bool) or not isinstance(row.get("control_step"), int):
                raise RuntimeError(f"{label} control_step must be an integer")
            _finite_vector(row.get("actor_obs"), length=ACTOR_OBS_DIM, label=f"{label}.actor_obs")
            for key in ("raw_action_mean", "post_env_action"):
                _finite_vector(row.get(key), length=ACTION_DIM, label=f"{label}.{key}")
            final_action = row.get("final_action")
            _finite_vector(final_action, length=FINAL_ACTION_DIM, label=f"{label}.final_action")
            if not isinstance(row.get("done"), bool):
                raise RuntimeError(f"{label}.done must be bool")
        terminal = rows[-1].get("terminal_facts")
        if rows[-1].get("done") is not True or not isinstance(terminal, Mapping):
            raise RuntimeError(f"{label} env_id={env_id} lacks terminal facts on its final done row")
        if not isinstance(terminal.get("terminal_reasons"), str) or not terminal["terminal_reasons"]:
            raise RuntimeError(f"{label} env_id={env_id} has no typed terminal reason")
        if not isinstance(terminal.get("goal_reached"), bool):
            raise RuntimeError(f"{label} goal_reached must be bool")
        if isinstance(terminal.get("max_stage_reached"), bool) or not isinstance(terminal.get("max_stage_reached"), int):
            raise RuntimeError(f"{label} max_stage_reached must be int")
        if isinstance(terminal.get("episode_length"), bool) or not isinstance(terminal.get("episode_length"), int):
            raise RuntimeError(f"{label} episode_length must be int")
    payload = dict(payload)
    payload["foot_force_feature"] = foot_feature
    return payload


def _compare_scalar(left: Any, right: Any, *, label: str) -> None:
    if abs(float(left) - float(right)) > TRACE_ATOL:
        raise RuntimeError(f"compatibility mismatch at {label}: {left!r} != {right!r}")


def _compare_vectors(left: Sequence[Any], right: Sequence[Any], *, label: str) -> None:
    if len(left) != len(right):
        raise RuntimeError(f"compatibility length mismatch at {label}")
    for index, (left_value, right_value) in enumerate(zip(left, right)):
        _compare_scalar(left_value, right_value, label=f"{label}[{index}]")


def _compare_traces(current: Mapping[str, Any], baseline: Mapping[str, Any]) -> dict[str, Any]:
    current_rows = current["rows_by_env"]
    baseline_rows = baseline["rows_by_env"]
    compared_rows = 0
    for env_id, (current_env, baseline_env) in enumerate(zip(current_rows, baseline_rows)):
        if len(current_env) != len(baseline_env):
            raise RuntimeError(f"compatibility row-count mismatch for env_id={env_id}")
        for row_index, (current_row, baseline_row) in enumerate(zip(current_env, baseline_env)):
            compared_rows += 1
            for key in ("env_id", "episode_index", "control_step", "done"):
                if current_row[key] != baseline_row[key]:
                    raise RuntimeError(f"compatibility mismatch at env={env_id}, row={row_index}, key={key}")
            for key in ("actor_obs", "raw_action_mean", "post_env_action", "final_action"):
                _compare_vectors(current_row[key], baseline_row[key], label=f"env={env_id},row={row_index},{key}")
            current_terminal = current_row.get("terminal_facts")
            baseline_terminal = baseline_row.get("terminal_facts")
            if isinstance(current_terminal, Mapping) or isinstance(baseline_terminal, Mapping):
                if not isinstance(current_terminal, Mapping) or not isinstance(baseline_terminal, Mapping):
                    raise RuntimeError(f"terminal fact presence mismatch for env_id={env_id}, row={row_index}")
                for key in ("terminal_reasons", "goal_reached", "max_stage_reached", "episode_length"):
                    if current_terminal.get(key) != baseline_terminal.get(key):
                        raise RuntimeError(f"terminal fact mismatch for env_id={env_id}, key={key}")
    return {"status": "PASS", "compared_rows": compared_rows, "atol": TRACE_ATOL}


def _validate_off_trace(payload: Mapping[str, Any], *, label: str) -> dict[str, Any]:
    disabled_receipts = 0
    for rows in payload["rows_by_env"]:
        for row in rows:
            receipt = row.get("reset_friction_receipt")
            if receipt is not None:
                if not isinstance(receipt, Mapping) or receipt.get("status") != "FRICTION_BACKEND_DISABLED":
                    raise RuntimeError(f"{label} contains a non-disabled reset receipt")
                disabled_receipts += 1
    return {"status": "PASS", "disabled_reset_receipts": disabled_receipts}


def _validate_h_trace(
    payload: Mapping[str, Any],
    *,
    static_effort: float,
    dynamic_effort: float,
    viscous_coefficient: float,
) -> dict[str, Any]:
    def validate_profile_block(block: Any, *, label: str, expected: Mapping[str, float] | None = None) -> None:
        if not isinstance(block, Mapping):
            raise RuntimeError(f"{label} must be a mapping")
        requested = block.get("requested")
        readback = block.get("readback")
        matches = block.get("matches")
        if not isinstance(requested, Mapping) or not isinstance(readback, Mapping) or not isinstance(matches, Mapping):
            raise RuntimeError(f"{label} lacks requested/readback/matches")
        if not all(matches.get(field) is True for field in FRICTION_FIELDS):
            raise RuntimeError(f"{label} has a failed readback match")
        for field in FRICTION_FIELDS:
            requested_row = requested.get(field)
            readback_row = readback.get(field)
            if (
                not isinstance(requested_row, list)
                or not isinstance(readback_row, list)
                or len(requested_row) != 1
                or len(readback_row) != 1
                or not isinstance(requested_row[0], list)
                or not isinstance(readback_row[0], list)
                or len(requested_row[0]) != 1
                or len(readback_row[0]) != 1
            ):
                raise RuntimeError(f"{label}.{field} must be a single bound profile row")
            _compare_scalar(
                requested_row[0][0],
                readback_row[0][0],
                label=f"{label}.{field}.readback",
            )
            if expected is not None:
                _compare_scalar(
                    requested_row[0][0], expected[field], label=f"{label}.{field}.requested"
                )

    terminal_receipts = 0
    ordinary_receipts = 0
    staged_receipts = 0
    for env_id, rows in enumerate(payload["rows_by_env"]):
        receipt = rows[-1].get("reset_friction_receipt")
        if not isinstance(receipt, Mapping):
            raise RuntimeError(f"H trace env_id={env_id} has no production reset receipt")
        if receipt.get("status") == "FRICTION_BACKEND_DISABLED":
            raise RuntimeError(f"H trace env_id={env_id} reports disabled friction")
        backend = receipt.get("backend")
        if not isinstance(backend, Mapping) or backend.get("backend") != FRICTION_BACKEND:
            raise RuntimeError(f"H trace env_id={env_id} lacks native friction backend identity")
        receipt_env_ids = receipt.get("env_ids")
        if (
            not isinstance(receipt_env_ids, list)
            or any(isinstance(value, bool) or not isinstance(value, int) for value in receipt_env_ids)
            or set(receipt_env_ids) - set(range(TRACE_ENV_COUNT))
            or env_id not in receipt_env_ids
        ):
            raise RuntimeError(f"H trace env_id={env_id} has no matching reset env id")
        per_env = receipt.get("per_env")
        if not isinstance(per_env, list) or len(per_env) != len(receipt_env_ids):
            raise RuntimeError(f"H trace env_id={env_id} lacks one per-env reset receipt row")
        per_env_by_id = {}
        for record in per_env:
            if not isinstance(record, Mapping) or record.get("env_id") in per_env_by_id:
                raise RuntimeError(f"H trace env_id={env_id} has duplicate/malformed per-env receipt rows")
            record_id = record.get("env_id")
            if isinstance(record_id, bool) or not isinstance(record_id, int):
                raise RuntimeError(f"H trace env_id={env_id} has a non-integer receipt env id")
            per_env_by_id[record_id] = record
        if set(per_env_by_id) != set(receipt_env_ids) or env_id not in per_env_by_id:
            raise RuntimeError(f"H trace env_id={env_id} per-env receipt ids do not match reset env ids")
        sentinel_keys = set()
        for record_id, record in per_env_by_id.items():
            sentinel = record.get("sentinel")
            validate_profile_block(sentinel, label=f"H env={record_id} sentinel")
            sentinel_requested = sentinel["requested"]
            sentinel_key = tuple(
                float(sentinel_requested[field][0][0]) for field in FRICTION_FIELDS
            )
            if sentinel_key in sentinel_keys:
                raise RuntimeError(f"H receipt sentinel profile is not distinct for env_id={record_id}")
            sentinel_keys.add(sentinel_key)
        record = per_env_by_id[env_id]
        expected = {
            "joint_friction_coeff": static_effort,
            "joint_dynamic_friction_coeff": dynamic_effort,
            "joint_viscous_friction_coeff": viscous_coefficient,
        }
        validate_profile_block(record.get("configured"), label=f"H env={env_id} configured", expected=expected)
        if record.get("env_id") != env_id:
            raise RuntimeError(f"H trace env_id={env_id} is bound to the wrong receipt row")
        reset_kind = record.get("reset_kind")
        stage = record.get("production_stage")
        sample_index = record.get("production_sample_index")
        sample_count = record.get("production_sample_count")
        snapshot = receipt.get("staged_snapshot")
        provenance = record.get("staged_provenance")
        if reset_kind == "staged":
            if not isinstance(snapshot, Mapping):
                raise RuntimeError(f"H trace env_id={env_id} lacks staged_snapshot reset provenance")
            snapshot_status = snapshot.get("status")
            if not isinstance(provenance, Mapping):
                raise RuntimeError(f"H trace env_id={env_id} lacks per-env staged provenance")
            if snapshot_status != "LEGITIMATE_NONZERO_PRODUCTION_SNAPSHOT":
                raise RuntimeError(f"H trace env_id={env_id} staged reset is not a production snapshot")
            if isinstance(stage, bool) or not isinstance(stage, int) or stage <= 0:
                raise RuntimeError(f"H trace env_id={env_id} staged reset does not bind stage>0")
            if isinstance(sample_index, bool) or not isinstance(sample_index, int) or sample_index < 0:
                raise RuntimeError(f"H trace env_id={env_id} staged reset lacks selected sample index")
            if isinstance(sample_count, bool) or not isinstance(sample_count, int) or sample_count <= 0:
                raise RuntimeError(f"H trace env_id={env_id} staged reset lacks populated sample count")
            if provenance.get("status") != snapshot_status:
                raise RuntimeError(f"H trace env_id={env_id} staged provenance status mismatch")
            for key, expected_value in (
                ("env_ids", [env_id]),
                ("stages", [stage]),
                ("sample_indices", [sample_index]),
                ("sample_counts", [sample_count]),
            ):
                if provenance.get(key) != expected_value:
                    raise RuntimeError(f"H trace env_id={env_id} staged provenance mismatch at {key}")
            snapshot_env_ids = snapshot.get("env_ids")
            if not isinstance(snapshot_env_ids, list) or env_id not in snapshot_env_ids:
                raise RuntimeError(f"H trace env_id={env_id} lacks outer staged env mapping")
            snapshot_position = snapshot_env_ids.index(env_id)
            for key, expected_value in (
                ("stages", stage),
                ("sample_indices", sample_index),
                ("sample_counts", sample_count),
            ):
                values = snapshot.get(key)
                if (
                    not isinstance(values, list)
                    or len(values) != len(snapshot_env_ids)
                    or values[snapshot_position] != expected_value
                ):
                    raise RuntimeError(f"H trace env_id={env_id} lacks outer staged mapping at {key}")
            staged_receipts += 1
        elif reset_kind == "ordinary":
            ordinary_receipts += 1
            if not isinstance(snapshot, Mapping) or snapshot.get("status") != "ORDINARY_RESET":
                raise RuntimeError(f"H trace env_id={env_id} ordinary reset provenance mismatch")
            if not isinstance(provenance, Mapping):
                raise RuntimeError(f"H trace env_id={env_id} lacks per-env ordinary provenance")
            if isinstance(stage, bool) or not isinstance(stage, int) or stage != 0:
                raise RuntimeError(f"H trace env_id={env_id} ordinary reset has invalid stage/sample mapping")
            if provenance.get("status") != "ORDINARY_RESET" or provenance.get("env_ids") != [env_id]:
                raise RuntimeError(f"H trace env_id={env_id} ordinary provenance mismatch")
            if sample_index is not None or sample_count is not None:
                raise RuntimeError(f"H trace env_id={env_id} ordinary reset has staged sample data")
            if any(provenance.get(key) != [] for key in ("stages", "sample_indices", "sample_counts")):
                raise RuntimeError(f"H trace env_id={env_id} ordinary reset has non-empty staged mapping")
        elif reset_kind == "stage0_ordinary":
            ordinary_receipts += 1
            if isinstance(stage, bool) or not isinstance(stage, int) or stage != 0:
                raise RuntimeError(f"H trace env_id={env_id} stage0 ordinary reset has invalid stage")
            if sample_index is not None or sample_count is not None:
                raise RuntimeError(f"H trace env_id={env_id} stage0 ordinary reset has staged sample data")
        else:
            raise RuntimeError(f"H trace env_id={env_id} has unknown reset kind {reset_kind!r}")
        terminal_receipts += 1
    if ordinary_receipts <= 0 or staged_receipts <= 0:
        raise RuntimeError(
            "H trace requires both ordinary and legitimate stage>0 staged reset receipts; "
            f"ordinary={ordinary_receipts}, staged={staged_receipts}."
        )
    return {
        "status": "PASS",
        "terminal_receipts": terminal_receipts,
        "ordinary_receipts": ordinary_receipts,
        "staged_receipts": staged_receipts,
    }


def _fixture_checkpoint(source: Path, work_root: Path, label: str) -> Path:
    source = _regular_file(source, label="selected checkpoint")
    source_config = _regular_file(source.parent / "config.yaml", label="checkpoint config")
    checkpoint_dir = work_root / label / source.parent.name
    checkpoint_dir.mkdir(parents=True, exist_ok=False)
    destination = checkpoint_dir / source.name
    try:
        os.link(source, destination)
    except OSError as exc:
        raise RuntimeError("runtime fixture requires a same-filesystem hardlink for the checkpoint") from exc
    shutil.copyfile(source_config, checkpoint_dir / "config.yaml")
    return destination


def _runner_command(
    *,
    root: Path,
    checkpoint: Path,
    trace: Path,
    eval_dir: Path,
    friction_enabled: bool,
    static_effort: float,
    dynamic_effort: float,
    viscous_coefficient: float,
) -> list[str]:
    command = [
        sys.executable,
        "-m",
        "gr00t.rl.eval_agent_trl",
        f"++checkpoint={checkpoint}",
        "++checkpoint_load_mode=policy_only",
        "++algo.config.eval.a2_v23_p06_policy_only=true",
        "++auto_load_latest=false",
        "++num_envs=16",
        "++seed=0",
        "++headless=true",
        "++use_wandb=false",
        "++algo.trl.report_to=none",
        "++algo.config.eval.num_eval_episodes=16",
        "++algo.config.eval.eval_num_envs_episodes=true",
        "++algo.config.eval.a2_p0_compatibility_trace_enabled=true",
        f"++algo.config.eval.a2_p0_compatibility_trace_path={trace}",
        "++algo.config.eval.save_videos=false",
        "++algo.config.eval.save_trajectories=false",
        "++algo.config.eval.save_goal_reached_only=false",
        "++algo.config.eval.num_save_episodes=16",
        "++env.config.a2_v23_d1_sampler_enabled=false",
        "++env.config.a2_v23_warm_head_reset_enabled=false",
        "++env.config.a2_v20_R2_evidence_enabled=false",
        "++env.config.a2_v24_gate_enabled=false",
        f"++env.config.a2_v24_friction_enabled={'true' if friction_enabled else 'false'}",
        f"++env.config.a2_v24_friction_backend={FRICTION_BACKEND}",
        f"++env.config.a2_p0_h_reset_audit_enabled={'true' if friction_enabled else 'false'}",
        "++simulator.config.render_results=false",
        "++simulator.config.cameras.enable_cameras=false",
        f"++eval_output_dir={eval_dir}",
        f"++output_dir={eval_dir}",
        f"hydra.run.dir={eval_dir / 'hydra'}",
    ]
    if friction_enabled:
        command.extend(
            [
                f"++env.config.a2_v24_friction_static_effort={static_effort}",
                f"++env.config.a2_v24_friction_dynamic_effort={dynamic_effort}",
                f"++env.config.a2_v24_friction_viscous_coefficient={viscous_coefficient}",
            ]
        )
    return command


def _run(command: Sequence[str], *, cwd: Path, timeout_seconds: int) -> None:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(cwd)
    try:
        completed = subprocess.run(
            list(command),
            cwd=cwd,
            env=env,
            check=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=None if timeout_seconds <= 0 else timeout_seconds,
        )
    except subprocess.CalledProcessError as exc:
        output = (exc.stdout or "").splitlines()[-40:]
        raise RuntimeError(f"runtime command failed with exit code {exc.returncode}:\n" + "\n".join(output)) from exc
    except subprocess.TimeoutExpired as exc:
        output = (exc.stdout or b"").decode(errors="replace") if isinstance(exc.stdout, bytes) else (exc.stdout or "")
        raise RuntimeError(f"runtime command timed out:\n{output[-4000:]}") from exc
    if completed.returncode != 0:
        raise RuntimeError("runtime command returned a non-zero status")


def _write_receipt(path: Path, payload: Mapping[str, Any]) -> None:
    path = path.expanduser().resolve()
    if path.exists() or path.is_symlink():
        raise RuntimeError(f"receipt output already exists: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(path.name + ".tmp")
    if temp_path.exists() or temp_path.is_symlink():
        raise RuntimeError(f"receipt temporary output already exists: {temp_path}")
    with temp_path.open("w", encoding="utf-8") as stream:
        json.dump(payload, stream, indent=2, allow_nan=False)
    os.replace(temp_path, path)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline-root", type=Path, required=True)
    parser.add_argument("--checkpoint", type=Path, default=SELECTED_CHECKPOINT)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("logs_eval/base_v24/p0_p1/runtime_compatibility_receipt.json"),
    )
    parser.add_argument("--work-root", type=Path, default=None)
    parser.add_argument("--timeout-seconds", type=int, default=0)
    parser.add_argument("--static-effort", type=float, default=DEFAULT_STATIC_EFFORT)
    parser.add_argument("--dynamic-effort", type=float, default=DEFAULT_DYNAMIC_EFFORT)
    parser.add_argument("--viscous-coefficient", type=float, default=DEFAULT_VISCOUS_COEFFICIENT)
    parser.add_argument("--plan", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    current_root = _repo_root()
    baseline_identity = None if args.plan else _validate_baseline(args.baseline_root)
    if args.plan:
        _directory(args.baseline_root, label="baseline root")
    checkpoint = _regular_file(
        args.checkpoint if args.checkpoint.is_absolute() else current_root / args.checkpoint,
        label="selected checkpoint",
    )
    for value, label in (
        (args.static_effort, "static effort"),
        (args.dynamic_effort, "dynamic effort"),
        (args.viscous_coefficient, "viscous coefficient"),
    ):
        if _finite(value, label=label) < 0.0:
            raise RuntimeError(f"{label} must be non-negative")
    if args.dynamic_effort > args.static_effort:
        raise RuntimeError("dynamic effort must be <= static effort")

    output = args.output if args.output.is_absolute() else current_root / args.output
    if output.exists() or output.is_symlink():
        raise RuntimeError(f"receipt output already exists: {output.resolve()}")

    if args.plan:
        print("CURRENT:")
        print(" ".join(_runner_command(
            root=current_root,
            checkpoint=Path("<current-fixture-checkpoint>"),
            trace=Path("<current-off-trace.json>"),
            eval_dir=Path("<current-off-eval>"),
            friction_enabled=False,
            static_effort=args.static_effort,
            dynamic_effort=args.dynamic_effort,
            viscous_coefficient=args.viscous_coefficient,
        )))
        print("BASELINE:")
        print(
            "BASELINE_PREFLIGHT: detached clean temporary instrumentation commit; "
            f"parent={SOURCE_BASELINE_COMMIT}; changed_paths=[{TRAINER_TRACE_PATH}]; "
            "friction module/import/config changes forbidden; trace symbols required"
        )
        print(" ".join(_runner_command(
            root=args.baseline_root,
            checkpoint=Path("<baseline-fixture-checkpoint>"),
            trace=Path("<baseline-trace.json>"),
            eval_dir=Path("<baseline-eval>"),
            friction_enabled=False,
            static_effort=args.static_effort,
            dynamic_effort=args.dynamic_effort,
            viscous_coefficient=args.viscous_coefficient,
        )))
        print("CURRENT_H:")
        print(" ".join(_runner_command(
            root=current_root,
            checkpoint=Path("<current-fixture-checkpoint>"),
            trace=Path("<current-h-trace.json>"),
            eval_dir=Path("<current-h-eval>"),
            friction_enabled=True,
            static_effort=args.static_effort,
            dynamic_effort=args.dynamic_effort,
            viscous_coefficient=args.viscous_coefficient,
        )))
        return

    work_root = args.work_root
    if work_root is None:
        work_root = output.with_name(output.stem + ".runtime")
    work_root = work_root if work_root.is_absolute() else current_root / work_root
    work_root = work_root.expanduser().resolve()
    if work_root.exists() or work_root.is_symlink():
        raise RuntimeError(f"runtime work root already exists: {work_root}")
    work_root.mkdir(parents=True, exist_ok=False)
    current_checkpoint = _fixture_checkpoint(checkpoint, work_root, "current")
    baseline_checkpoint = _fixture_checkpoint(checkpoint, work_root, "baseline")
    current_off_trace = work_root / "current-off-trace.json"
    baseline_trace = work_root / "baseline-trace.json"
    current_h_trace = work_root / "current-h-trace.json"
    run_specs = (
        (
            "current_off",
            current_root,
            current_checkpoint,
            current_off_trace,
            False,
            args.static_effort,
            args.dynamic_effort,
            args.viscous_coefficient,
        ),
        (
            "baseline_off",
            args.baseline_root.resolve(),
            baseline_checkpoint,
            baseline_trace,
            False,
            args.static_effort,
            args.dynamic_effort,
            args.viscous_coefficient,
        ),
        (
            "current_h",
            current_root,
            current_checkpoint,
            current_h_trace,
            True,
            args.static_effort,
            args.dynamic_effort,
            args.viscous_coefficient,
        ),
    )
    for name, root, fixture, trace, friction_enabled, static_effort, dynamic_effort, viscous in run_specs:
        command = _runner_command(
            root=root,
            checkpoint=fixture,
            trace=trace,
            eval_dir=work_root / name / "eval",
            friction_enabled=friction_enabled,
            static_effort=static_effort,
            dynamic_effort=dynamic_effort,
            viscous_coefficient=viscous,
        )
        print(f"RUN {name}")
        _run(command, cwd=root, timeout_seconds=args.timeout_seconds)

    current_off = _validate_trace(current_off_trace, label="current off trace")
    baseline_off = _validate_trace(baseline_trace, label="baseline off trace")
    current_h = _validate_trace(current_h_trace, label="current H trace")
    off_result = _validate_off_trace(current_off, label="current off trace")
    parity_result = _compare_traces(current_off, baseline_off)
    h_result = _validate_h_trace(
        current_h,
        static_effort=args.static_effort,
        dynamic_effort=args.dynamic_effort,
        viscous_coefficient=args.viscous_coefficient,
    )
    receipt = {
        "schema": SCHEMA,
        "status": "RUNTIME_VERIFIED",
            "source_identity": {
                "current_path": str(current_root),
                "current_git_commit": _git(current_root, "rev-parse", "HEAD"),
                "baseline_path": baseline_identity["path"],
                "baseline_source_git_commit": baseline_identity["source_git_commit"],
                "baseline_instrumentation_git_commit": baseline_identity[
                    "instrumentation_git_commit"
                ],
                "baseline_instrumentation_path": baseline_identity["instrumentation_path"],
                "baseline_instrumentation_config_identity": baseline_identity["config_identity"],
                "checkpoint_path": str(checkpoint),
            "checkpoint_config_path": str(checkpoint.parent / "config.yaml"),
            "seed": 0,
            "num_envs": TRACE_ENV_COUNT,
            "checkpoint_load_mode": "policy_only",
        },
            "p0_default_off": {
                "status": "PASS",
                "current_off_trace": str(current_off_trace),
                "baseline_trace": str(baseline_trace),
                "current_foot_force_feature": current_off["foot_force_feature"],
                "baseline_foot_force_feature": baseline_off["foot_force_feature"],
                "off_receipt": off_result,
                "parity": parity_result,
            },
        "p1_h_production_reset": {
            "status": "PASS",
            "trace": str(current_h_trace),
            "friction_backend": FRICTION_BACKEND,
                "requested_profile": {
                "static_effort": args.static_effort,
                "dynamic_effort": args.dynamic_effort,
                "viscous_coefficient": args.viscous_coefficient,
                },
                "foot_force_feature": current_h["foot_force_feature"],
                "validation": h_result,
        },
            "comparison": {
                "actor_obs_dim": ACTOR_OBS_DIM,
                "raw_action_dim": ACTION_DIM,
                "final_action_dim": FINAL_ACTION_DIM,
                "atol": TRACE_ATOL,
            "discrete_fields": ["env_id", "episode_index", "control_step", "done", "terminal_facts"],
        },
    }
    _write_receipt(output, receipt)
    print(f"WROTE {output.resolve()}")


if __name__ == "__main__":
    main()
