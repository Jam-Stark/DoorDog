"""Receipt-bound helpers for the executable R2 artifact DAG.

The workflow modules deliberately share one executor and one artifact reader.
A command plan is never runtime evidence: a producer must consume its attempt,
spawn the requested child, and write a receipt whose parent/config/device
identities are independently checkable by a consumer.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from ._r2_common import (
    ADJUDICATOR_STATES,
    ADMISSION_PLAN_ID,
    PRODUCER_STATES,
    R1_URDF_PATH,
    R2Error,
    SCIENTIFIC_PLAN_ID,
    canonical_json,
    device_env,
    file_identity,
    hash_command_env,
    load_json,
    process_identity,
    require_adjudicator_state,
    require_producer_state,
    sha256_file,
    utc_now,
    validate_device_contract,
    validate_raw_producer_payload,
    validate_regular_file,
    validate_gpu,
    write_json_exclusive,
)

R2_SOURCE = "scriptsFORhuman/v20_R2"
SCHEMA_DIR = Path(__file__).with_name("schemas")
GROUPS = tuple(f"G{i}" for i in range(1, 8))
M22_STEPS = (250, 500, 750, 1000, 1250, 1500, 1750, 2000, 2250, 2500)
CONFIG_FILENAMES = {
    "G1": "base_v20_R2_G1_g2_continuation.yaml",
    "G2": "base_v20_R2_G2_economics_only.yaml",
    "G3": "base_v20_R2_G3_send_curriculum_only.yaml",
    "G4": "base_v20_R2_G4_send_curriculum_economics.yaml",
    "G5": "base_v20_R2_G5_send_curriculum_arm_tie.yaml",
    "G6": "base_v20_R2_G6_full.yaml",
    "G7": "base_v20_R2_G7_full_seed1.yaml",
}
SCHEMA_PREFIX = "a2_piper_base_v20_R2_"


def r2_config_path(config_root: Path | str, group: str) -> Path:
    ensure_group(group)
    return Path(config_root) / CONFIG_FILENAMES[group]


def root_path(repo_root: Path | str, value: Path | str) -> Path:
    root = Path(repo_root).resolve()
    target = Path(value)
    if not target.is_absolute():
        target = root / target
    target = target.absolute()
    try:
        target.relative_to(root)
    except ValueError as exc:
        raise R2Error(f"path escapes repository root: {value}") from exc
    # Do not call resolve() here: a missing path may be created later, while a
    # present symlink must still be rejected by validate_regular_file/parent.
    if target.exists() and target.is_symlink():
        raise R2Error(f"symlink path is forbidden: {value}")
    return target


def artifact_hash(path: Path | str) -> str:
    return sha256_file(validate_regular_file(path, label="R2 artifact"))


def _schema_file(schema: str) -> Path:
    if not isinstance(schema, str) or not schema:
        raise R2Error("artifact schema must be a non-empty string")
    name = schema if schema.endswith(".schema.json") else schema.removeprefix(SCHEMA_PREFIX) + ".schema.json"
    target = SCHEMA_DIR / name
    if not target.is_file() or target.is_symlink():
        raise R2Error(f"unknown R2 schema: {schema}")
    return target


def _schema_store() -> dict[str, Any]:
    """Build a local Draft 2020-12 resolver store for sibling schemas."""

    store: dict[str, Any] = {}
    for path in sorted(SCHEMA_DIR.glob("*.schema.json")):
        payload = load_json(path)
        if not isinstance(payload, Mapping):
            raise R2Error(f"schema is not an object: {path}")
        store[path.as_uri()] = payload
        store[path.name] = payload
        schema_id = payload.get("$id")
        if isinstance(schema_id, str):
            store[schema_id] = payload
    return store


def validate_schema(payload: Any, schema: str) -> None:
    """Validate an artifact against the exact local Draft 2020-12 schema."""

    target = _schema_file(schema)
    schema_payload = load_json(target)
    try:
        from jsonschema import Draft202012Validator, FormatChecker, RefResolver
    except ImportError as exc:  # pragma: no cover - runtime dependency in repo
        raise R2Error("jsonschema is required for R2 artifact validation") from exc
    if schema_payload.get("$schema") != "https://json-schema.org/draft/2020-12/schema":
        raise R2Error(f"R2 schema is not Draft 2020-12: {target}")
    try:
        validator = Draft202012Validator(
            schema_payload,
            resolver=RefResolver(target.as_uri(), schema_payload, store=_schema_store()),
            format_checker=FormatChecker(),
        )
        error = next(iter(sorted(validator.iter_errors(payload), key=lambda item: list(item.path))), None)
    except Exception as exc:
        raise R2Error(f"R2 schema validation failed for {target.name}") from exc
    if error is not None:
        location = "$" + "".join(f"[{item!r}]" for item in error.path)
        raise R2Error(f"{target.name} violation at {location}: {error.message}")


def _validate_parent_bindings(
    payload: Mapping[str, Any],
    *,
    expected_source_lock_sha256: str | None = None,
    parent_hashes: Mapping[str, str] | None = None,
    mode: str | None = None,
) -> None:
    if mode is not None and payload.get("mode") != mode:
        raise R2Error(f"artifact mode mismatch: expected {mode!r}, got {payload.get('mode')!r}")
    if expected_source_lock_sha256 is not None:
        actual = payload.get("source_lock_sha256")
        if actual != expected_source_lock_sha256:
            raise R2Error("artifact source-lock hash does not match expected parent")
    if parent_hashes:
        parents = payload.get("parents", payload.get("parent_hashes"))
        if not isinstance(parents, Mapping):
            raise R2Error("artifact is missing required parent hash mapping")
        for name, expected in parent_hashes.items():
            if parents.get(name) != expected:
                raise R2Error(f"artifact parent hash mismatch for {name}")


def read_artifact(
    path: Path | str,
    *,
    schema: str | None = None,
    producer_state: str | None = None,
    adjudicator_state: str | None = None,
    expected_source_lock_sha256: str | None = None,
    parent_hashes: Mapping[str, str] | None = None,
    mode: str | None = None,
) -> dict[str, Any]:
    """Load and strictly validate one raw or adjudicated artifact.

    State mode is intentionally exclusive.  A raw producer cannot smuggle an
    adjudicator state, and a caller-authored generic status field is rejected
    before any consumer sees it.
    """

    if producer_state is not None and adjudicator_state is not None:
        raise R2Error("producer_state and adjudicator_state are mutually exclusive")
    payload = load_json(validate_regular_file(path, label="R2 artifact"))
    if not isinstance(payload, Mapping):
        raise R2Error(f"R2 artifact must be an object: {path}")
    actual_schema = payload.get("schema")
    if schema is None:
        schema = actual_schema if isinstance(actual_schema, str) else None
    if schema is None:
        raise R2Error(f"R2 artifact schema is required: {path}")
    if actual_schema != schema:
        raise R2Error(f"R2 artifact schema mismatch: expected {schema}, got {actual_schema}")
    validate_schema(payload, schema)
    has_producer = "producer_state" in payload
    has_adjudicator = "adjudicator_state" in payload
    if has_producer and has_adjudicator:
        raise R2Error("artifact cannot contain both producer_state and adjudicator_state")
    if producer_state is not None:
        if has_adjudicator:
            raise R2Error("adjudicator artifact supplied where raw producer was required")
        require_producer_state(payload, producer_state)
    elif adjudicator_state is not None:
        if has_producer:
            raise R2Error("raw producer artifact supplied where adjudication was required")
        require_adjudicator_state(payload, adjudicator_state)
    elif has_producer:
        validate_raw_producer_payload(payload)
    elif has_adjudicator:
        require_adjudicator_state(payload, str(payload["adjudicator_state"]))
    else:
        raise R2Error("artifact has neither producer nor adjudicator state")
    _validate_parent_bindings(
        payload,
        expected_source_lock_sha256=expected_source_lock_sha256,
        parent_hashes=parent_hashes,
        mode=mode,
    )
    return dict(payload)


def write_raw(path: Path | str, payload: Mapping[str, Any], *, producer_state: str | None = None) -> str:
    validate_raw_producer_payload(payload, producer_state=producer_state)
    return write_json_exclusive(path, payload)


def write_adjudication(path: Path | str, payload: Mapping[str, Any], state: str) -> str:
    if state not in ADJUDICATOR_STATES:
        raise R2Error(f"unknown adjudicator state: {state}")
    if payload.get("adjudicator_state") != state or "producer_state" in payload:
        raise R2Error("adjudication payload must carry only the computed adjudicator state")
    require_adjudicator_state(payload, state)
    return write_json_exclusive(path, payload)


def parse_gpus(value: str | Sequence[int | str], *, expected: int | None = None) -> tuple[int, ...]:
    if isinstance(value, str):
        tokens = [item.strip() for item in value.split(",") if item.strip()]
    else:
        tokens = list(value)
    if not tokens:
        raise R2Error("at least one physical GPU is required")
    result = tuple(validate_gpu(item) for item in tokens)
    if len(set(result)) != len(result):
        raise R2Error("physical GPU list contains duplicates")
    if expected is not None and len(result) != expected:
        raise R2Error(f"expected exactly {expected} physical GPUs, got {len(result)}")
    return result


def runtime_command(*, module: str, repo_root: Path | str, gpu: int,
                    render: bool = False, extra: Sequence[str] = ()) -> tuple[list[str], dict[str, str], dict[str, Any]]:
    physical = validate_gpu(gpu)
    argv = [sys.executable, "-B", "-m", module, *map(str, extra)]
    env = device_env(physical, render=render)
    expected = "cuda:0" if render else f"cuda:{physical}"
    binding = validate_device_contract(
        gpu=physical, render=render, argv=argv, env=env,
        app_launcher_device=expected, accelerator_device=expected,
    )
    return argv, env, binding


def train_command(
    *, repo_root: Path | str, config: Path, gpu: int, group: str, seed: int,
    num_envs: int, batches: int, save_frequency: int, output_root: Path,
    checkpoint: Path | None = None, formal: bool = False,
) -> tuple[list[str], dict[str, str], dict[str, Any]]:
    """Build the sibling train entrypoint's supported Hydra override command."""

    ensure_group(group)
    if isinstance(seed, bool) or not isinstance(seed, int) or seed < 0:
        raise R2Error("training seed must be a non-negative integer")
    if min(num_envs, batches, save_frequency) <= 0:
        raise R2Error("training dimensions must be positive")
    config = validate_regular_file(config, label="R2 training config")
    overrides = [
        "+exp=wbmanip/door_open_a2_base_lstm",
        f"+ablation=wbmanip/{config.stem}",
        f"num_envs={num_envs}", f"seed={seed}",
        f"algo.trl.num_total_batches={batches}",
        f"callbacks.model_save.save_frequency={save_frequency}",
        "headless=true", "simulator.config.cameras.enable_cameras=false",
        "checkpoint_load_mode=policy_only", "auto_load_latest=false",
        f"experiment_dir={output_root}",
        f"env.config.a2_v20_R2_trace_root={output_root / 'traces'}",
        f"env.config.a2_v20_R2_record_set_staging_path={output_root / 'record_set.staging.jsonl'}",
        f"env.config.a2_v20_R2_provenance={{run_uuid:{group}-seed{seed},scientific_plan_id:base_v20_R1_policy_behavior_v1,admission_plan_id:base_v20_R2_admission_execution_v1}}",
        f"env.config.a2_v20_R2_formal_launch={'true' if formal else 'false'}",
    ]
    if checkpoint is not None:
        checkpoint = validate_regular_file(checkpoint, label="R2 training checkpoint")
        overrides.append(f"checkpoint={checkpoint}")
    argv, env, binding = runtime_command(
        module="gr00t.rl.train_agent_trl", repo_root=repo_root, gpu=gpu,
        render=False, extra=overrides,
    )
    env = {**env, "WANDB_MODE": "offline"}
    validate_device_contract(gpu=gpu, render=False, argv=argv, env=env,
                             app_launcher_device=f"cuda:{gpu}", accelerator_device=f"cuda:{gpu}")
    return argv, env, {**binding, "group": group, "seed": seed,
                       "num_envs": num_envs, "batches": batches,
                       "save_frequency": save_frequency, "config_sha256": artifact_hash(config)}


def eval_command(
    *, repo_root: Path | str, checkpoint: Path, config: Path, gpu: int,
    seed: int, num_envs: int, output_root: Path, mode: str, group: str | None = None,
) -> tuple[list[str], dict[str, str], dict[str, Any]]:
    """Build supported Hydra eval overrides and bind all evidence destinations."""

    if mode not in {"b0", "forced", "zero-shot", "canonical16", "pooled", "holdout", "m22"}:
        raise R2Error(f"unsupported R2 eval mode: {mode}")
    if group is not None:
        ensure_group(group)
    checkpoint = validate_regular_file(checkpoint, label="R2 evaluation checkpoint")
    config_identity_payload = config_identity(config)
    config = Path(str(config_identity_payload["path"]))
    checkpoint_sha256 = artifact_hash(checkpoint)
    config_sha256 = str(config_identity_payload["sha256"])
    source_lock = _source_lock_provenance(repo_root, str(config_identity_payload["text"]))
    topology_names = {
        "b0": "canonical16",
        "zero-shot": "canonical16",
        "canonical16": "canonical16",
        "m22": "canonical16",
        "forced": "forced1",
        "pooled": "pooled_seed16",
        "holdout": "holdout_seed16",
    }
    provenance = {
        "run_uuid": _eval_run_uuid(mode=mode, group=group, seed=seed),
        "scientific_plan_id": SCIENTIFIC_PLAN_ID,
        "admission_plan_id": ADMISSION_PLAN_ID,
        **source_lock,
        "checkpoint_path": str(checkpoint),
        "checkpoint_sha256": checkpoint_sha256,
        "checkpoint_step": _checkpoint_step(checkpoint),
        "source_config_path": str(config),
        "source_config_sha256": config_sha256,
        "resolved_config_sha256": config_sha256,
        "seed": seed,
        "topology": {
            "name": topology_names[mode],
            "environment_count": num_envs,
            "expected_episode_count": num_envs,
            "first_episode_only": True,
            "single_process": True,
            "physical_gpu": gpu,
            "render": False,
        },
    }
    overrides = [
        f"+checkpoint={checkpoint}", f"+num_envs={num_envs}", f"+seed={seed}",
        "+headless=true", "+r2_evidence_enabled=true",
        f"+r2_bound_config_path={config}",
        f"+r2_bound_config_sha256={config_sha256}",
        f"+r2_resolved_config_sha256={config_sha256}",
        f"+env.config.a2_v20_R2_trace_root={output_root / 'traces'}",
        f"+env.config.a2_v20_R2_record_set_staging_path={output_root / 'record_set.staging.jsonl'}",
        f"+env.config.a2_v20_R2_provenance={_hydra_mapping(provenance)}",
    ]
    if group is not None:
        overrides.append(f"+env.config.a2_v20_R2_group={group}")
    argv, env, binding = runtime_command(
        module="gr00t.rl.eval_agent_trl", repo_root=repo_root, gpu=gpu,
        render=False, extra=overrides,
    )
    argv.append(f"+r2_command_sha256={hash_command_env(argv, env)}")
    return argv, env, {**binding, "mode": mode, "group": group, "seed": seed,
                       "num_envs": num_envs, "checkpoint_sha256": checkpoint_sha256,
                       "config_sha256": config_sha256}


def parent_sha(path: Path | str, *, schema: str | None = None,
               adjudicator_state: str | None = None,
               producer_state: str | None = None) -> tuple[dict[str, Any], str]:
    payload = read_artifact(path, schema=schema, producer_state=producer_state, adjudicator_state=adjudicator_state)
    return payload, artifact_hash(path)


def require_parents(paths: Mapping[str, Path | str], *, schema: str | None = None,
                    state: str | None = None) -> dict[str, str]:
    result: dict[str, str] = {}
    for name, path in paths.items():
        if state in ADJUDICATOR_STATES:
            read_artifact(path, schema=schema, adjudicator_state=state)
        else:
            read_artifact(path, schema=schema, producer_state=state)
        result[name] = artifact_hash(path)
    return result


def config_identity(path: Path | str) -> dict[str, Any]:
    target = validate_regular_file(path, label="R2 config")
    text = target.read_text(encoding="utf-8")
    if "scriptsFORhuman.v20_R1" in text:
        raise R2Error("R2 executable config may not import an R1 tool")
    required = ("scientific_plan_id: base_v20_R1_policy_behavior_v1", "admission_plan_id: base_v20_R2_admission_execution_v1")
    if not all(key in text for key in required):
        raise R2Error(f"R2 config is missing dual identity fields: {target}")
    return {"path": str(target), "sha256": artifact_hash(target), "text": text}


def _checkpoint_step(checkpoint: Path) -> int:
    prefix = "model_step_"
    suffix = ".pt"
    name = checkpoint.name
    if not name.startswith(prefix) or not name.endswith(suffix):
        raise R2Error(f"R2 evaluation checkpoint name does not bind a model step: {checkpoint}")
    step = name[len(prefix):-len(suffix)]
    if not step.isdecimal():
        raise R2Error(f"R2 evaluation checkpoint step is not decimal: {checkpoint}")
    return int(step)


def _source_lock_provenance(repo_root: Path | str, config_text: str) -> dict[str, str]:
    _lock_path = root_path(repo_root, _source_lock_path_from_config(config_text))
    source_lock = load_json(validate_regular_file(_lock_path, label="R2 active source lock"))
    # ACTIVE_SOURCE_LOCK.json wraps the frozen source lock under "source_lock";
    # unwrap so provenance binds the actual SOURCE_FROZEN lock P0 adjudicated.
    if isinstance(source_lock, Mapping) and source_lock.get("schema") == "a2_piper_base_v20_R2_active_source_lock_v1":
        source_lock = source_lock.get("source_lock")
    if not isinstance(source_lock, Mapping) or source_lock.get("schema") != "a2_piper_base_v20_R2_source_lock_v1":
        raise R2Error("R2 active source lock does not embed a valid source lock")
    if source_lock.get("producer_state") != "SOURCE_FROZEN":
        raise R2Error("R2 source lock is not SOURCE_FROZEN")
    immutable = source_lock.get("immutable_inputs")
    git = source_lock.get("git")
    if not isinstance(immutable, Mapping):
        raise R2Error("R2 source lock is missing immutable_inputs")
    if not isinstance(git, Mapping) or not isinstance(git.get("commit"), str):
        raise R2Error("R2 source lock is missing git.commit")
    return {
        "source_lock_sha256": artifact_hash(root_path(repo_root, _source_lock_path_from_config(config_text))),
        "plan_sha256": _immutable_sha(immutable, "r2_plan"),
        "r1_plan_sha256": _immutable_sha(immutable, "r1_plan"),
        "b0_json_sha256": _immutable_sha(immutable, "b0_json"),
        "b0_csv_sha256": _immutable_sha(immutable, "b0_csv"),
        "urdf_path": _immutable_path(immutable, "urdf", R1_URDF_PATH),
        "urdf_sha256": _immutable_sha(immutable, "urdf"),
        "git_commit": git["commit"],
    }


def _source_lock_path_from_config(config_text: str) -> str:
    matches = []
    for line in config_text.splitlines():
        stripped = line.strip()
        if stripped.startswith("r2_source_lock_path:"):
            matches.append(stripped.split(":", 1)[1].strip().strip("'\""))
    if len(matches) != 1 or not matches[0]:
        raise R2Error("R2 eval config must bind exactly one r2_source_lock_path")
    return matches[0]


def _immutable_sha(immutable: Mapping[str, Any], name: str) -> str:
    value = immutable.get(f"{name}_sha256")
    if not isinstance(value, str) or len(value) != 64:
        raise R2Error(f"R2 source lock immutable {name}_sha256 is missing")
    return value


def _immutable_path(immutable: Mapping[str, Any], name: str, expected: str) -> str:
    value = immutable.get(f"{name}_path")
    if value != expected:
        raise R2Error(f"R2 source lock immutable {name}_path mismatch")
    return expected


def _eval_run_uuid(*, mode: str, group: str | None, seed: int) -> str:
    if mode == "b0":
        return f"b0-B0-seed{seed}"
    if mode in {"zero-shot", "pooled"}:
        if group is None:
            raise R2Error(f"{mode} evaluation requires a group-bound run UUID")
        return f"{mode}-{group}-seed{seed}"
    if mode == "holdout":
        return f"holdout-seed{seed}"
    return f"{mode}-seed{seed}"


def _hydra_value(value: Any) -> str:
    if isinstance(value, Mapping):
        return _hydra_mapping(value)
    if isinstance(value, str):
        return json.dumps(value)
    if isinstance(value, bool):
        return str(value).lower()
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        if not math.isfinite(value):
            raise R2Error("Hydra provenance values must be finite")
        return repr(value)
    raise R2Error(f"unsupported Hydra provenance value: {type(value).__name__}")


def _hydra_mapping(payload: Mapping[str, Any]) -> str:
    if not payload:
        raise R2Error("Hydra provenance mappings must not be empty")
    entries = []
    for key, value in payload.items():
        if not isinstance(key, str) or not key:
            raise R2Error("Hydra provenance mapping keys must be non-empty strings")
        entries.append(f"{json.dumps(key)}:{_hydra_value(value)}")
    return "{" + ",".join(entries) + "}"


def ensure_group(group: str) -> str:
    if group not in GROUPS:
        raise R2Error(f"group must be one of {GROUPS}, got {group!r}")
    return group


def ensure_r2_ids(payload: Mapping[str, Any]) -> None:
    if payload.get("scientific_plan_id") != "base_v20_R1_policy_behavior_v1":
        raise R2Error("scientific_plan_id mismatch")
    if payload.get("admission_plan_id") != ADMISSION_PLAN_ID:
        raise R2Error("admission_plan_id mismatch")


def canonical_digest(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _git_commit(repo_root: Path) -> str:
    try:
        commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo_root, text=True).strip()
    except (OSError, subprocess.CalledProcessError) as exc:
        raise R2Error("cannot bind process receipt to a Git commit") from exc
    if len(commit) != 40 or any(c not in "0123456789abcdef" for c in commit):
        raise R2Error(f"invalid observed commit: {commit!r}")
    return commit


def _git_tree(repo_root: Path) -> str:
    try:
        tree = subprocess.check_output(["git", "rev-parse", "HEAD^{tree}"], cwd=repo_root, text=True).strip()
    except (OSError, subprocess.CalledProcessError) as exc:
        raise R2Error("cannot bind process receipt to a Git tree") from exc
    if len(tree) != 40 or any(c not in "0123456789abcdef" for c in tree):
        raise R2Error(f"invalid observed tree: {tree!r}")
    return tree


def _exclusive_attempt_marker(
    marker: Path, *, name: str, argv: Sequence[str], env: Mapping[str, str],
    physical_gpu: int | None, render: bool, active_source_lock: Path | None,
    parents: Mapping[str, Path] | None, extra: Mapping[str, Any] | None,
) -> dict[str, Any]:
    marker_payload: dict[str, Any] = {
        "schema": "a2_piper_base_v20_R2_attempt_marker_v1",
        "producer_state": "ATTEMPT_CONSUMED",
        "name": name,
        "argv": list(argv), "env": dict(sorted(env.items())),
        "command_sha256": hash_command_env(argv, env),
        "launcher_pid": os.getpid(), "created_at_utc": utc_now(),
        "pid_intent": "pending_spawn", "physical_gpu": physical_gpu,
        "render": render,
    }
    if active_source_lock is not None:
        marker_payload["active_source_lock"] = file_identity(active_source_lock, label="active source lock")
    if parents:
        marker_payload["parents"] = {name: file_identity(path, label=f"parent {name}") for name, path in sorted(parents.items())}
    if extra:
        marker_payload.update(dict(extra))
    write_json_exclusive(marker, marker_payload)
    return marker_payload


def spawn_once(
    *, argv: Sequence[str], repo_root: Path, output_root: Path,
    env: Mapping[str, str], name: str, render: bool = False,
    physical_gpu: int | None = None, attempt_marker: Path | None = None,
    active_source_lock: Path | None = None, parents: Mapping[str, Path] | None = None,
    parent_hashes: Mapping[str, str] | None = None,
    marker_payload: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Execute exactly one child and emit a complete immutable process receipt.

    The attempt marker is created before ``Popen``.  A failed spawn/non-zero
    child is therefore terminal evidence and never silently retried.
    """

    root = Path(repo_root).absolute()
    if not root.is_dir() or root.is_symlink():
        raise R2Error(f"repo_root must be a regular directory: {repo_root}")
    if not argv or not all(isinstance(item, str) and item for item in argv):
        raise R2Error("argv must contain non-empty strings")
    if not isinstance(env, Mapping) or not all(isinstance(k, str) and isinstance(v, str) for k, v in env.items()):
        raise R2Error("env must map strings to strings")
    if physical_gpu is not None:
        validate_device_contract(
            gpu=physical_gpu, render=render, argv=argv, env=env,
            app_launcher_device="cuda:0" if render else f"cuda:{physical_gpu}",
            accelerator_device="cuda:0" if render else f"cuda:{physical_gpu}",
        )
    if output_root.exists():
        raise R2Error(f"output root already exists; retry is forbidden: {output_root}")
    output_root.parent.mkdir(parents=True, exist_ok=True)
    output_root.mkdir()
    marker = attempt_marker or output_root / "ATTEMPT_CONSUMED.json"
    marker_preconsumed = marker.exists()
    if marker_preconsumed:
        existing = load_json(marker)
        if not isinstance(existing, Mapping) or existing.get("producer_state") != "ATTEMPT_CONSUMED":
            raise R2Error(f"attempt marker already exists with invalid state: {marker}")
    parent_hash_map: dict[str, str] = {}
    if parents:
        for key, path in sorted(parents.items()):
            parent_hash_map[key] = artifact_hash(path)
    if parent_hashes is not None and parent_hash_map and parent_hash_map != dict(parent_hashes):
        raise R2Error("caller parent hashes disagree with actual parent files")
    parent_hash_map = dict(parent_hashes or parent_hash_map)
    active_hash = artifact_hash(active_source_lock) if active_source_lock is not None else None
    if not marker_preconsumed:
        _exclusive_attempt_marker(
            marker, name=name, argv=argv, env=env, physical_gpu=physical_gpu,
            render=render, active_source_lock=active_source_lock, parents=parents,
            extra={"active_source_lock_sha256": active_hash, "parent_hashes": parent_hash_map, **dict(marker_payload or {})},
        )
    stdout_path = output_root / f"{name}.stdout.log"
    stderr_path = output_root / f"{name}.stderr.log"
    process_env = os.environ.copy()
    process_env.update(env)
    parent_pid = os.getpid()
    parent_identity = process_identity(parent_pid)
    started_at = utc_now()
    child_pid: int | None = None
    returncode: int | None = None
    launch_error: BaseException | None = None
    try:
        with stdout_path.open("xb") as stdout, stderr_path.open("xb") as stderr:
            try:
                child = subprocess.Popen(list(argv), cwd=root, env=process_env, stdout=stdout, stderr=stderr)
            except OSError as exc:
                launch_error = exc
            else:
                child_pid = int(child.pid)
                child_identity = process_identity(child_pid)
                if child_identity["ppid"] != parent_pid:
                    raise R2Error("spawned child parent identity does not match launcher")
                returncode = child.wait()
    finally:
        if not stdout_path.exists():
            stdout_path.touch(mode=0o600, exist_ok=False)
        if not stderr_path.exists():
            stderr_path.touch(mode=0o600, exist_ok=False)
    ended_at = utc_now()
    while ended_at == started_at:
        time.sleep(0.000001)
        ended_at = utc_now()
    stdout_identity = file_identity(stdout_path, label="stdout log")
    stderr_identity = file_identity(stderr_path, label="stderr log")
    commit = _git_commit(root)
    tree = _git_tree(root)
    receipt: dict[str, Any] = {
        "schema": "a2_piper_base_v20_R2_process_receipt_v1",
        "producer_state": "PROCESS_COMPLETED",
        "name": name, "argv": list(argv), "env": dict(sorted(env.items())),
        "pid": child_pid or 0, "parent_pid": parent_pid,
        "parent_identity": parent_identity,
        "child_identity": ({"pid": child_pid, "ppid": parent_pid} if child_pid is not None else None),
        "started_at_utc": started_at, "ended_at_utc": ended_at,
        "exit_code": returncode, "stdout_path": str(stdout_path), "stderr_path": str(stderr_path),
        "stdout_sha256": stdout_identity["sha256"], "stderr_sha256": stderr_identity["sha256"],
        "stdout_size": stdout_identity["size"], "stderr_size": stderr_identity["size"],
        "command_sha256": hash_command_env(argv, env), "env_sha256": canonical_digest(dict(sorted(env.items()))),
        "observed_commit": commit, "observed_tree": tree, "active_source_lock_sha256": active_hash,
        "parent_hashes": parent_hash_map, "physical_gpu": physical_gpu, "render": render,
        "natural_exit": launch_error is None and returncode == 0,
    }
    write_raw(output_root / "process_receipt.json", receipt, producer_state="PROCESS_COMPLETED")
    if launch_error is not None:
        raise R2Error(f"R2 process {name} failed to spawn after attempt consumption") from launch_error
    if returncode != 0:
        raise R2Error(f"R2 process {name} exited nonzero: {returncode}")
    return receipt


# Explicit names make the one executor discoverable to downstream runners/tests.
execute_once = spawn_once
run_process_once = spawn_once


def require_exact_set(actual: Sequence[Any], expected: Sequence[Any], *, label: str) -> None:
    if len(actual) != len(expected) or len(set(actual)) != len(actual) or set(actual) != set(expected):
        raise R2Error(f"{label} is not an exact set")
