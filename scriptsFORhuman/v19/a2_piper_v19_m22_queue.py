"""Mechanical v19 M22 checkpoint discovery and strict-eval queue planning.

This tool is intentionally offline by default.  It discovers only numbered
``model_step_*.pt`` files, hashes each candidate, records explicit artifact
provenance, and prints the exact serial module invocation needed for a missing
artifact.  It never treats ``last.pt`` as a checkpoint candidate.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

import yaml


ISAACLAB_PYTHON = Path("/home/baoquanc/anaconda3/envs/isaaclab/bin/python")
SCHEMA = "a2_piper_v19_m22_candidate_manifest_v1"
QUEUE_SCHEMA = "a2_piper_v19_m22_queue_v1"
CHECKPOINT_RE = re.compile(r"^model_step_(?P<step>[0-9]+)\.pt$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
CANONICAL_TOPOLOGY = "canonical16"
CANONICAL_EPISODES = 16
EXPECTED_HEIGHT_BOUNDS = (0.80, 1.10)
TOPOLOGY_COUNTS = {CANONICAL_TOPOLOGY: CANONICAL_EPISODES}
P0_DIAGNOSTIC_REWARD_TERMS = (
    "gripper_handle_orientation",
    "grasp_target_distance",
    "grasp",
    "penalty_not_standing_still",
    "a2_stage3_unlatch_hold",
    "a2_stage3_stage4_hold_and_drive",
    "push_door_hinge",
    "dont_push_door_handle",
    "target_root_distance",
    "penalty_standing_still",
    "stage",
    "penalty_door_frame_contact",
    "penalty_door_panel_contact",
    "penalty_a2_door_body_contact",
    "penalty_undesired_contact",
    "penalty_base_roll_pitch_l2",
    "a2_corridor_door_wide",
    "a2_corridor_clean_passage",
    "penalty_a2_posture_command_l1",
    "complete",
)


class M22QueueError(ValueError):
    """Raised when checkpoint or artifact provenance is not strict-valid."""


def _validate_gpu(gpu: str | None) -> str | None:
    if gpu is None:
        return None
    if not isinstance(gpu, str) or re.fullmatch(r"(?:0|[1-9][0-9]*)", gpu) is None:
        raise M22QueueError(
            "gpu must be an exact non-negative decimal physical id, e.g. '0' or '7'; "
            f"got {gpu!r}"
        )
    return gpu


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical_path(value: Any, name: str) -> Path:
    if not isinstance(value, str) or not value.strip():
        raise M22QueueError(f"{name} must be a non-empty path string")
    return Path(value).expanduser().resolve()


def _validate_manifest(manifest: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    if not isinstance(manifest, Mapping) or manifest.get("schema") != SCHEMA:
        raise M22QueueError("candidate manifest schema is invalid")
    candidates = manifest.get("candidates")
    if not isinstance(candidates, list) or not candidates:
        raise M22QueueError("candidate manifest must contain a non-empty candidates list")
    seen_ids: set[str] = set()
    seen_steps: set[int] = set()
    seen_paths: set[str] = set()
    for candidate in candidates:
        if not isinstance(candidate, Mapping):
            raise M22QueueError("manifest candidate must be a mapping")
        candidate_id = candidate.get("candidate_id")
        step = candidate.get("step")
        if not isinstance(candidate_id, str) or not candidate_id:
            raise M22QueueError("manifest candidate_id must be non-empty")
        if isinstance(step, bool) or not isinstance(step, int) or step < 0:
            raise M22QueueError(f"manifest step is invalid for {candidate_id!r}")
        match = CHECKPOINT_RE.fullmatch(candidate_id)
        if match is None or int(match.group("step")) != step:
            raise M22QueueError(f"manifest candidate_id/step mismatch for {candidate_id!r}")
        path = _canonical_path(candidate.get("path"), f"manifest {candidate_id} path")
        if path.name != candidate_id or not path.is_file():
            raise M22QueueError(f"manifest checkpoint path is invalid for {candidate_id!r}")
        sha = candidate.get("sha256")
        if not isinstance(sha, str) or SHA256_RE.fullmatch(sha) is None:
            raise M22QueueError(f"manifest SHA-256 is invalid for {candidate_id!r}")
        if candidate_id in seen_ids or step in seen_steps or str(path) in seen_paths:
            raise M22QueueError("manifest candidate identity topology contains duplicates")
        actual_sha = _sha256(path)
        if actual_sha != sha:
            raise M22QueueError(
                f"manifest checkpoint SHA-256 mismatch for {candidate_id}: expected {sha}, got {actual_sha}"
            )
        seen_ids.add(candidate_id)
        seen_steps.add(step)
        seen_paths.add(str(path))
    return candidates


def _validate_exact_height_bounds(config: Mapping[str, Any]) -> None:
    try:
        env_config = config["env"]["config"]
    except (KeyError, TypeError):
        raise M22QueueError("artifact config is missing env.config")
    if not isinstance(env_config, Mapping):
        raise M22QueueError("artifact config env.config must be a mapping")
    bounds = env_config.get("a2_eval_door_handle_height_linspace")
    if (
        not isinstance(bounds, (list, tuple))
        or len(bounds) != 2
        or any(isinstance(value, bool) or not isinstance(value, (int, float)) for value in bounds)
        or tuple(float(value) for value in bounds) != EXPECTED_HEIGHT_BOUNDS
    ):
        raise M22QueueError("artifact config height linspace must be exactly [0.80,1.10]")


def _validate_artifact_config(
    config: Mapping[str, Any], candidate_path: Path, expected_seed: int
) -> None:
    config_checkpoint = _canonical_path(config.get("checkpoint"), "artifact config checkpoint")
    if config_checkpoint != candidate_path:
        raise M22QueueError("artifact config checkpoint conflicts with manifest")
    if config.get("checkpoint_load_mode") != "full":
        raise M22QueueError("artifact config checkpoint_load_mode must be full")
    config_seed = config.get("seed")
    if isinstance(config_seed, bool) or not isinstance(config_seed, int) or config_seed != expected_seed:
        raise M22QueueError(f"artifact config seed must equal requested seed {expected_seed}")
    if config.get("num_envs") != CANONICAL_EPISODES:
        raise M22QueueError("artifact config num_envs must be 16")
    try:
        evaluation = config["algo"]["config"]["eval"]
    except (KeyError, TypeError):
        raise M22QueueError("artifact config is missing algo.config.eval")
    if not isinstance(evaluation, Mapping):
        raise M22QueueError("artifact config algo.config.eval must be a mapping")
    if evaluation.get("num_eval_episodes") != CANONICAL_EPISODES:
        raise M22QueueError("artifact config eval.num_eval_episodes must be 16")
    if evaluation.get("eval_num_envs_episodes") is not True:
        raise M22QueueError("artifact config eval_num_envs_episodes must be true")
    for key in ("save_goal_reached_only", "save_videos", "save_trajectories"):
        if evaluation.get(key) is not False:
            raise M22QueueError(f"artifact config eval.{key} must be false")
    if evaluation.get("a2_eval_m41_strict_telemetry") is not True:
        raise M22QueueError("artifact config must enable M41 strict telemetry")
    if evaluation.get("a2_diagnostic_trace_enabled") is not True:
        raise M22QueueError("artifact config must enable diagnostic tracing")
    if evaluation.get("a2_eval_p2_posture_axis") != "none":
        raise M22QueueError("artifact config P2 posture axis must be none")
    if evaluation.get("a2_forced_gripper_close_enabled") is not False:
        raise M22QueueError("artifact config forced gripper close must be false")
    if evaluation.get("a2_hold_oracle_enabled") is not False:
        raise M22QueueError("artifact config hold oracle must be false")
    if evaluation.get("a2_diagnostic_reward_terms") != list(P0_DIAGNOSTIC_REWARD_TERMS):
        raise M22QueueError("artifact config diagnostic reward terms do not match exact P0 list")
    _validate_exact_height_bounds(config)


def _validate_artifact_admission(
    candidate: Mapping[str, Any], mapping: Mapping[str, Any], requested_seed: int
) -> Path:
    required = (
        "checkpoint_path",
        "checkpoint_sha256",
        "evaluation_topology",
        "evaluation_seed",
    )
    missing = [name for name in required if name not in mapping]
    if missing:
        raise M22QueueError(f"explicit artifact mapping is missing provenance fields {missing}")
    candidate_path = _canonical_path(candidate.get("path"), "manifest checkpoint path")
    mapping_path = _canonical_path(mapping["checkpoint_path"], "artifact checkpoint_path")
    if mapping_path != candidate_path:
        raise M22QueueError("artifact checkpoint_path conflicts with manifest")
    if mapping["checkpoint_sha256"] != candidate.get("sha256"):
        raise M22QueueError("artifact checkpoint_sha256 conflicts with manifest")
    if mapping["evaluation_topology"] != CANONICAL_TOPOLOGY:
        raise M22QueueError("queue evaluation_topology must be canonical16")
    evaluation_seed = mapping["evaluation_seed"]
    if isinstance(evaluation_seed, bool) or not isinstance(evaluation_seed, int):
        raise M22QueueError("queue evaluation_seed must be an integer")
    if evaluation_seed != requested_seed:
        raise M22QueueError("queue evaluation_seed must equal requested seed")
    artifact_value = mapping.get("artifact", mapping.get("artifact_dir"))
    artifact = _canonical_path(artifact_value, "artifact")
    if not artifact.exists():
        return artifact
    if not artifact.is_dir():
        raise M22QueueError(f"artifact must be a directory: {artifact}")
    config_path = artifact / ".hydra" / "config.yaml"
    if not config_path.is_file():
        raise M22QueueError(f"artifact lacks .hydra/config.yaml: {config_path}")
    try:
        config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise M22QueueError(f"cannot read artifact config {config_path}") from exc
    if not isinstance(config, Mapping):
        raise M22QueueError("artifact config must be a mapping")
    _validate_artifact_config(config, candidate_path, requested_seed)
    return artifact


def discover_checkpoints(run_dir: Path) -> list[dict[str, Any]]:
    """Return numerically ordered immutable candidate identities."""
    run_dir = Path(run_dir).expanduser().resolve()
    if not run_dir.is_dir():
        raise M22QueueError(f"checkpoint run directory does not exist: {run_dir}")
    candidates: list[dict[str, Any]] = []
    for path in run_dir.iterdir():
        match = CHECKPOINT_RE.fullmatch(path.name)
        if match is None:
            continue
        if not path.is_file():
            raise M22QueueError(f"checkpoint candidate is not a regular file: {path}")
        step = int(match.group("step"))
        candidates.append(
            {
                "candidate_id": path.name,
                "step": step,
                "path": str(path),
                "sha256": _sha256(path),
            }
        )
    if not candidates:
        raise M22QueueError(f"no numbered model_step_*.pt candidates found in {run_dir}")
    candidates.sort(key=lambda row: (int(row["step"]), str(row["candidate_id"])))
    if len({int(row["step"]) for row in candidates}) != len(candidates):
        raise M22QueueError("checkpoint candidates contain duplicate numeric steps")
    return candidates


def build_manifest(run_dir: Path) -> dict[str, Any]:
    run_dir = Path(run_dir).expanduser().resolve()
    candidates = discover_checkpoints(run_dir)
    last_path = run_dir / "last.pt"
    return {
        "schema": SCHEMA,
        "run_dir": str(run_dir),
        "candidate_discovery": "numeric model_step_*.pt only; last.pt excluded",
        "last_pt_present_but_excluded": last_path.is_file(),
        "candidates": candidates,
    }


def write_immutable_manifest(manifest: Mapping[str, Any], output_path: Path) -> Path:
    """Create an immutable manifest, rejecting any attempted replacement."""
    output_path = Path(output_path).expanduser()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = dict(manifest)
    if output_path.exists():
        try:
            existing = json.loads(output_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise M22QueueError(f"existing manifest is unreadable: {output_path}") from exc
        if _canonical_json(existing) != _canonical_json(payload):
            raise M22QueueError(f"immutable candidate manifest differs: {output_path}")
        return output_path
    output_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output_path


def load_manifest(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise M22QueueError(f"cannot read candidate manifest: {path}") from exc
    _validate_manifest(payload)
    return payload


def load_artifact_mapping(path: Path | None) -> dict[str, Any]:
    if path is None:
        return {}
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise M22QueueError(f"cannot read explicit artifact mapping: {path}") from exc
    if isinstance(payload, dict) and "candidates" in payload:
        payload = payload["candidates"]
    if isinstance(payload, list):
        rows = payload
    elif isinstance(payload, dict):
        rows = []
        for key, value in payload.items():
            row = dict(value) if isinstance(value, Mapping) else {"artifact": value}
            row.setdefault("candidate_id", key)
            rows.append(row)
    else:
        raise M22QueueError("artifact mapping must be a mapping or list")
    result: dict[str, Any] = {}
    for row in rows:
        if not isinstance(row, Mapping):
            raise M22QueueError("artifact mapping rows must be mappings")
        key = row.get("candidate_id", row.get("path", row.get("step")))
        if key is None:
            raise M22QueueError("artifact mapping row lacks candidate_id/path/step")
        normalized = dict(row)
        normalized.setdefault("candidate_id", key)
        identity = str(normalized["candidate_id"])
        if identity in result:
            raise M22QueueError(f"duplicate explicit artifact mapping for {identity!r}")
        result[identity] = normalized
    return result


def _candidate_mapping_keys(candidate: Mapping[str, Any]) -> tuple[str, ...]:
    return (
        str(candidate["candidate_id"]),
        str(candidate["path"]),
        str(candidate["step"]),
        f"step{candidate['step']}",
    )


def _find_mapping(candidate: Mapping[str, Any], mapping: Mapping[str, Any]) -> Mapping[str, Any] | None:
    matches = [key for key in _candidate_mapping_keys(candidate) if key in mapping]
    if len(matches) > 1:
        raise M22QueueError(
            f"explicit artifact mapping has conflicting aliases for {candidate['candidate_id']}: {matches}"
        )
    if not matches:
        return None
    value = mapping[matches[0]]
    return value if isinstance(value, Mapping) else {"artifact": value}


def build_eval_command(
    checkpoint: Mapping[str, Any] | Path | str,
    output_dir: Path,
    *,
    seed: int = 0,
    gpu: str | None = None,
    topology: str = CANONICAL_TOPOLOGY,
) -> dict[str, Any]:
    """Build the exact canonical16 strict M41 one-GPU module invocation.

    eval_agent_trl is a Hydra entrypoint. Its nested AppLauncher parser is
    created only after Hydra has consumed the process arguments, so a leading
    --device argument is rejected before AppLauncher can see it. The exact
    ACCELERATE_TORCH_DEVICE value is also passed to AppLauncher by the eval
    entrypoint, keeping simulation and policy on the same physical GPU without
    a CUDA visibility mask.
    """
    if topology != CANONICAL_TOPOLOGY:
        raise M22QueueError("queue evaluation_topology must be canonical16")
    checkpoint_path = (
        Path(checkpoint["path"]) if isinstance(checkpoint, Mapping) else Path(checkpoint)
    ).expanduser().resolve()
    output_dir = Path(output_dir).expanduser().resolve()
    if isinstance(seed, bool) or not isinstance(seed, int) or seed < 0:
        raise M22QueueError(f"seed must be a non-negative int; got {seed!r}")
    gpu = _validate_gpu(gpu)
    diagnostic_terms = "[" + ",".join(P0_DIAGNOSTIC_REWARD_TERMS) + "]"
    if not ISAACLAB_PYTHON.is_file():
        raise M22QueueError(f"IsaacLab Python does not exist: {ISAACLAB_PYTHON}")
    argv = [
        str(ISAACLAB_PYTHON),
        "-m",
        "gr00t.rl.eval_agent_trl",
    ]
    argv.extend(
        [
        f"+checkpoint={checkpoint_path}",
        "++checkpoint_load_mode=full",
        "++auto_load_latest=false",
        "++headless=true",
        "++num_envs=16",
        f"++seed={seed}",
        "++use_wandb=false",
        "++simulator.config.cameras.enable_cameras=false",
        "++simulator.config.render_results=false",
        "++env.config.a2_eval_door_handle_height_linspace=[0.80,1.10]",
        "++algo.config.eval.num_eval_episodes=16",
        "++algo.config.eval.eval_num_envs_episodes=true",
        "++algo.config.eval.dump_to_log_metrics=true",
        "++algo.config.eval.a2_diagnostic_trace_enabled=true",
        f"++algo.config.eval.a2_diagnostic_reward_terms={diagnostic_terms}",
        "++algo.config.eval.a2_eval_p2_posture_axis=none",
        "++algo.config.eval.a2_forced_gripper_close_enabled=false",
        "++algo.config.eval.a2_hold_oracle_enabled=false",
        "++algo.config.eval.save_goal_reached_only=false",
        "++algo.config.eval.save_videos=false",
        "++algo.config.eval.save_trajectories=false",
        "++algo.config.eval.a2_eval_m41_strict_telemetry=true",
        f"++eval_name=v19_m22_step{checkpoint_path.stem.removeprefix('model_step_')}_seed{seed}",
        f"++eval_output_dir={output_dir}",
        ]
    )
    env = (
        {
            "ACCELERATE_TORCH_DEVICE": f"cuda:{gpu}",
            "VK_ICD_FILENAMES": "/usr/share/vulkan/icd.d/nvidia_icd.json",
        }
        if gpu is not None
        else {}
    )
    return {
        "argv": argv,
        "env": env,
        "execution": "serial one-GPU; no implicit retry or artifact reuse",
    }


def build_queue(
    manifest: Mapping[str, Any],
    artifact_mapping: Mapping[str, Any],
    output_root: Path,
    *,
    seed: int = 0,
    gpu: str | None = None,
) -> dict[str, Any]:
    if isinstance(seed, bool) or not isinstance(seed, int) or seed < 0:
        raise M22QueueError(f"seed must be a non-negative int; got {seed!r}")
    candidates = _validate_manifest(manifest)
    rows: list[dict[str, Any]] = []
    output_root = Path(output_root).expanduser().resolve()
    for candidate in candidates:
        mapping = _find_mapping(candidate, artifact_mapping)
        if mapping is not None and mapping.get("candidate_id") not in (None, candidate["candidate_id"]):
            raise M22QueueError("explicit artifact mapping candidate_id conflicts with manifest")
        artifact_value = None if mapping is None else mapping.get("artifact", mapping.get("artifact_dir"))
        if mapping is not None:
            if artifact_value is None:
                raise M22QueueError("explicit artifact mapping requires artifact")
            artifact_path = _validate_artifact_admission(candidate, mapping, seed)
            topology = CANONICAL_TOPOLOGY
            if artifact_path.exists():
                artifact_state = "EXPLICIT_ARTIFACT"
                command = None
            else:
                artifact_state = "MISSING_ARTIFACT"
                command = build_eval_command(candidate, artifact_path, seed=seed, gpu=gpu)
        else:
            artifact_path = output_root / str(candidate["candidate_id"]).removesuffix(".pt") / f"seed{seed}"
            topology = CANONICAL_TOPOLOGY
            artifact_state = "MISSING_ARTIFACT"
            command = build_eval_command(candidate, artifact_path, seed=seed, gpu=gpu)
        rows.append(
            {
                "candidate": dict(candidate),
                "artifact": str(artifact_path),
                "artifact_state": artifact_state,
                "evaluation_topology": topology,
                "explicit_mapping": mapping is not None,
                "eval_command": command,
            }
        )
    return {
        "schema": QUEUE_SCHEMA,
        "manifest_schema": manifest["schema"],
        "candidate_count": len(rows),
        "serial": True,
        "rows": rows,
    }


def write_queue_outputs(queue: Mapping[str, Any], output_root: Path) -> tuple[Path, Path]:
    output_root = Path(output_root).expanduser().resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    json_path = output_root / "a2_piper_v19_m22_queue.json"
    md_path = output_root / "a2_piper_v19_m22_queue.md"
    json_path.write_text(json.dumps(queue, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    lines = ["# A2 Piper v19 M22 queue", "", "| Candidate | Step | Artifact | State |", "|---|---:|---|---|"]
    for row in queue["rows"]:
        candidate = row["candidate"]
        lines.append(
            f"| `{candidate['candidate_id']}` | {candidate['step']} | `{row['artifact']}` | {row['artifact_state']} |"
        )
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, md_path


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--artifact-map", type=Path)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--gpu")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    discovered = build_manifest(args.run_dir)
    manifest_path = write_immutable_manifest(discovered, args.manifest)
    manifest = load_manifest(manifest_path)
    mapping = load_artifact_mapping(args.artifact_map)
    queue = build_queue(manifest, mapping, args.output_root, seed=args.seed, gpu=args.gpu)
    paths = write_queue_outputs(queue, args.output_root)
    print(f"candidate manifest: {manifest_path}")
    print(f"queue JSON: {paths[0]}")
    print(f"queue Markdown: {paths[1]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
