"""Build the strict, offline v20 M22 checkpoint queue.

The queue is deliberately a provenance tool rather than an evaluator.  It
discovers exactly the ten immutable numeric checkpoints used by M22
(``250..2500``), hashes them immediately, and emits one serial canonical16
evaluation command per checkpoint.  ``last.pt`` and all mutable aliases are
never candidates.  No command is started by this module.
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
SCHEMA = "a2_piper_v20_m22_candidate_manifest_v1"
QUEUE_SCHEMA = "a2_piper_v20_m22_queue_v1"
CHECKPOINT_RE = re.compile(r"^model_step_(?P<step>[0-9]+)\.pt$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
GROUP_RE = re.compile(r"(?:^|[/_])(?P<group>G[1-7])(?:_|/|$)")
GROUPS = tuple(f"G{i}" for i in range(1, 8))
EXPECTED_STEPS = tuple(range(250, 2501, 250))
EXPECTED_STEP_SET = frozenset(EXPECTED_STEPS)
CANONICAL_TOPOLOGY = "canonical16"
CANONICAL_EPISODES = 16
EXPECTED_HEIGHT_BOUNDS = (0.80, 1.10)
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
    """Raised when checkpoint or queue provenance is not strict-valid."""


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError as exc:
        raise M22QueueError(f"cannot hash checkpoint {path}: {exc}") from exc
    return digest.hexdigest()


def _canonical_path(value: Any, name: str) -> Path:
    if not isinstance(value, str) or not value.strip():
        raise M22QueueError(f"{name} must be a non-empty path string")
    return Path(value).expanduser().resolve()


def _validate_gpu(gpu: str | None) -> str | None:
    if gpu is None:
        return None
    if not isinstance(gpu, str) or gpu not in tuple(str(index) for index in range(7)):
        raise M22QueueError(
            "gpu must be one physical id in 0..6; GPU7 is reserved; "
            f"got {gpu!r}"
        )
    return gpu


def _group_from_run_dir(run_dir: Path) -> str | None:
    for value in (run_dir.name, str(run_dir)):
        match = GROUP_RE.search(value)
        if match:
            return match.group("group")
    return None


def discover_checkpoints(run_dir: Path) -> list[dict[str, Any]]:
    """Discover only the ten preregistered numeric checkpoint identities.

    Numbered files outside the M22 range are intentionally ignored; a
    manifest then fails unless the exact ten required steps are present.  A
    ``last.pt`` file is recorded by :func:`build_manifest` but is never read
    or treated as an evaluation candidate.
    """

    run_dir = Path(run_dir).expanduser().resolve()
    if not run_dir.is_dir():
        raise M22QueueError(f"checkpoint run directory does not exist: {run_dir}")
    candidates: list[dict[str, Any]] = []
    for path in sorted(run_dir.iterdir(), key=lambda item: item.name):
        match = CHECKPOINT_RE.fullmatch(path.name)
        if match is None:
            continue
        step = int(match.group("step"))
        if step not in EXPECTED_STEP_SET:
            continue
        if not path.is_file():
            raise M22QueueError(f"checkpoint candidate is not a regular file: {path}")
        candidates.append(
            {
                "candidate_id": path.name,
                "step": step,
                "path": str(path),
                "sha256": _sha256(path),
            }
        )
    candidates.sort(key=lambda row: (int(row["step"]), str(row["candidate_id"])))
    if len({int(row["step"]) for row in candidates}) != len(candidates):
        raise M22QueueError("checkpoint candidates contain duplicate numeric steps")
    return candidates


def build_manifest(run_dir: Path, *, group: str | None = None) -> dict[str, Any]:
    """Build an immutable ten-row manifest for one training group."""

    run_dir = Path(run_dir).expanduser().resolve()
    candidates = discover_checkpoints(run_dir)
    if len(candidates) != len(EXPECTED_STEPS) or {
        int(row["step"]) for row in candidates
    } != EXPECTED_STEP_SET:
        got = sorted(int(row["step"]) for row in candidates)
        raise M22QueueError(
            "v20 M22 requires exactly numeric steps 250..2500 (ten checkpoints); "
            f"got {got}"
        )
    resolved_group = group or _group_from_run_dir(run_dir)
    if resolved_group is not None and resolved_group not in GROUPS:
        raise M22QueueError(f"group must be one of {GROUPS}; got {resolved_group!r}")
    return {
        "schema": SCHEMA,
        "version": "v20",
        "group": resolved_group,
        "run_dir": str(run_dir),
        "candidate_discovery": "numeric model_step_*.pt only; exact steps 250..2500; last.pt excluded",
        "expected_steps": list(EXPECTED_STEPS),
        "last_pt_present_but_excluded": (run_dir / "last.pt").is_file(),
        "candidates": candidates,
    }


def build_matrix_manifests(run_dirs: Mapping[str, Path]) -> dict[str, Any]:
    """Build and validate the exact seven-group/70-row M22 topology."""

    if set(run_dirs) != set(GROUPS):
        raise M22QueueError(f"matrix run_dirs must contain exactly {GROUPS}")
    manifests = [build_manifest(run_dirs[group], group=group) for group in GROUPS]
    rows = [row for manifest in manifests for row in manifest["candidates"]]
    if len(rows) != 70 or len({(m["group"], r["candidate_id"]) for m in manifests for r in m["candidates"]}) != 70:
        raise M22QueueError("v20 M22 matrix must contain exactly 7x10 unique rows")
    return {
        "schema": "a2_piper_v20_m22_matrix_manifest_v1",
        "groups": manifests,
        "group_count": 7,
        "candidate_count": 70,
        "strict_topology": "7 groups x 10 numeric checkpoints",
    }


def write_immutable_manifest(manifest: Mapping[str, Any], output_path: Path) -> Path:
    """Create a manifest once, refusing replacement with different bytes."""

    output_path = Path(output_path).expanduser()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = dict(manifest)
    if output_path.exists():
        try:
            existing = json.loads(output_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise M22QueueError(f"existing manifest is unreadable: {output_path}") from exc
        if _canonical_json(existing) != _canonical_json(payload):
            raise M22QueueError(f"immutable candidate manifest differs: {output_path}")
        return output_path
    output_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output_path


def _validate_manifest(manifest: Mapping[str, Any], *, require_exact: bool = True) -> list[Mapping[str, Any]]:
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
        if isinstance(step, bool) or not isinstance(step, int) or step not in EXPECTED_STEP_SET:
            raise M22QueueError(f"manifest step is not one of 250..2500 for {candidate_id!r}")
        match = CHECKPOINT_RE.fullmatch(candidate_id)
        if match is None or int(match.group("step")) != step:
            raise M22QueueError(f"manifest candidate_id/step mismatch for {candidate_id!r}")
        path = _canonical_path(candidate.get("path"), f"manifest {candidate_id} path")
        if path.name != candidate_id or not path.is_file():
            raise M22QueueError(f"manifest checkpoint path is invalid for {candidate_id!r}")
        sha = candidate.get("sha256")
        if not isinstance(sha, str) or SHA256_RE.fullmatch(sha) is None:
            raise M22QueueError(f"manifest SHA-256 is invalid for {candidate_id!r}")
        if _sha256(path) != sha:
            raise M22QueueError(f"manifest checkpoint SHA-256 mismatch for {candidate_id}")
        if candidate_id in seen_ids or step in seen_steps or str(path) in seen_paths:
            raise M22QueueError("manifest candidate identity topology contains duplicates")
        seen_ids.add(candidate_id)
        seen_steps.add(step)
        seen_paths.add(str(path))
    if require_exact and (len(candidates) != 10 or seen_steps != EXPECTED_STEP_SET):
        raise M22QueueError("manifest must contain exactly the ten numeric M22 steps")
    return candidates


def load_manifest(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise M22QueueError(f"cannot read candidate manifest: {path}") from exc
    _validate_manifest(payload)
    return payload


def _validate_exact_height_bounds(config: Mapping[str, Any]) -> None:
    try:
        env_config = config["env"]["config"]
    except (KeyError, TypeError) as exc:
        raise M22QueueError("artifact config is missing env.config") from exc
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
    configured = _canonical_path(config.get("checkpoint"), "artifact config checkpoint")
    if configured != candidate_path:
        raise M22QueueError("artifact config checkpoint conflicts with manifest")
    if config.get("checkpoint_load_mode") != "full":
        raise M22QueueError("artifact config checkpoint_load_mode must be full")
    if config.get("auto_load_latest") is not False:
        raise M22QueueError("artifact config auto_load_latest must be false")
    if isinstance(config.get("seed"), bool) or config.get("seed") != expected_seed:
        raise M22QueueError(f"artifact config seed must equal requested seed {expected_seed}")
    if config.get("num_envs") != CANONICAL_EPISODES:
        raise M22QueueError("artifact config num_envs must be 16")
    evaluation = config.get("algo", {}).get("config", {}).get("eval", {})
    if not isinstance(evaluation, Mapping):
        raise M22QueueError("artifact config algo.config.eval must be a mapping")
    if evaluation.get("num_eval_episodes") != CANONICAL_EPISODES or evaluation.get("eval_num_envs_episodes") is not True:
        raise M22QueueError("artifact config eval topology must be canonical16")
    if evaluation.get("a2_eval_v20_strict_telemetry") is not True:
        raise M22QueueError("artifact config must enable v20 strict telemetry")
    if evaluation.get("a2_eval_m41_strict_telemetry") is not True:
        raise M22QueueError("artifact config must enable M41 strict telemetry")
    if evaluation.get("a2_diagnostic_trace_enabled") is not True:
        raise M22QueueError("artifact config must enable diagnostic tracing")
    _validate_exact_height_bounds(config)


def load_artifact_mapping(path: Path | None) -> dict[str, Mapping[str, Any]]:
    if path is None:
        return {}
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise M22QueueError(f"cannot read explicit artifact mapping: {path}") from exc
    rows: Any = payload.get("candidates") if isinstance(payload, Mapping) and "candidates" in payload else payload
    if isinstance(rows, Mapping):
        rows = [dict(value, candidate_id=key) if isinstance(value, Mapping) else {"candidate_id": key, "artifact": value} for key, value in rows.items()]
    if not isinstance(rows, list):
        raise M22QueueError("artifact mapping must be a mapping or list")
    result: dict[str, Mapping[str, Any]] = {}
    for value in rows:
        if not isinstance(value, Mapping):
            raise M22QueueError("artifact mapping rows must be mappings")
        key = value.get("candidate_id", value.get("path", value.get("step")))
        if key is None or str(key) in result:
            raise M22QueueError("artifact mapping rows require unique candidate identities")
        result[str(key)] = dict(value)
    return result


def build_eval_command(
    checkpoint: Mapping[str, Any] | Path | str,
    output_dir: Path,
    *,
    seed: int = 0,
    gpu: str | None = None,
    topology: str = CANONICAL_TOPOLOGY,
) -> dict[str, Any]:
    """Return one exact v20 canonical16 evaluator invocation, without running it."""

    if topology != CANONICAL_TOPOLOGY:
        raise M22QueueError("queue evaluation_topology must be canonical16")
    checkpoint_path = (Path(checkpoint["path"]) if isinstance(checkpoint, Mapping) else Path(checkpoint)).expanduser().resolve()
    if not CHECKPOINT_RE.fullmatch(checkpoint_path.name) or int(CHECKPOINT_RE.fullmatch(checkpoint_path.name).group("step")) not in EXPECTED_STEP_SET:
        raise M22QueueError("evaluation checkpoint must be a numeric M22 step 250..2500")
    output_dir = Path(output_dir).expanduser().resolve()
    if isinstance(seed, bool) or not isinstance(seed, int) or seed < 0:
        raise M22QueueError(f"seed must be a non-negative int; got {seed!r}")
    gpu = _validate_gpu(gpu)
    if not ISAACLAB_PYTHON.is_file():
        raise M22QueueError(f"IsaacLab Python does not exist: {ISAACLAB_PYTHON}")
    diagnostic_terms = "[" + ",".join(P0_DIAGNOSTIC_REWARD_TERMS) + "]"
    argv = [str(ISAACLAB_PYTHON), "-m", "gr00t.rl.eval_agent_trl"]
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
            "++algo.config.eval.a2_eval_v20_strict_telemetry=true",
            f"++eval_name=v20_m22_step{checkpoint_path.stem.removeprefix('model_step_')}_seed{seed}",
            f"++eval_output_dir={output_dir}",
        ]
    )
    env = (
        {
            "CUDA_VISIBLE_DEVICES": gpu,
            "ACCELERATE_TORCH_DEVICE": "cuda:0",
            "VK_ICD_FILENAMES": "/usr/share/vulkan/icd.d/nvidia_icd.json",
        }
        if gpu is not None
        else {}
    )
    return {
        "argv": argv,
        "env": env,
        "execution": "serial one-GPU; no implicit retry or artifact reuse",
        "evaluation_topology": CANONICAL_TOPOLOGY,
        "evaluation_seed": seed,
        "checkpoint_path": str(checkpoint_path),
    }


def _find_mapping(candidate: Mapping[str, Any], mapping: Mapping[str, Mapping[str, Any]]) -> Mapping[str, Any] | None:
    aliases = (str(candidate["candidate_id"]), str(candidate["path"]), str(candidate["step"]), f"step{candidate['step']}")
    matches = [alias for alias in aliases if alias in mapping]
    if len(matches) > 1:
        raise M22QueueError(f"explicit artifact mapping has conflicting aliases for {candidate['candidate_id']}: {matches}")
    return mapping[matches[0]] if matches else None


def build_queue(
    manifest: Mapping[str, Any],
    artifact_mapping: Mapping[str, Mapping[str, Any]],
    output_root: Path,
    *,
    seed: int = 0,
    gpu: str | None = None,
) -> dict[str, Any]:
    candidates = _validate_manifest(manifest)
    output_root = Path(output_root).expanduser().resolve()
    rows: list[dict[str, Any]] = []
    for candidate in candidates:
        mapping = _find_mapping(candidate, artifact_mapping)
        if mapping is not None:
            if mapping.get("candidate_id", candidate["candidate_id"]) != candidate["candidate_id"]:
                raise M22QueueError("explicit artifact mapping candidate_id conflicts with manifest")
            artifact_value = mapping.get("artifact", mapping.get("artifact_dir"))
            if artifact_value is None:
                raise M22QueueError("explicit artifact mapping requires artifact")
            artifact = _canonical_path(artifact_value, "artifact")
            if artifact.exists():
                if not artifact.is_dir():
                    raise M22QueueError(f"artifact must be a directory: {artifact}")
                config_path = artifact / ".hydra" / "config.yaml"
                if not config_path.is_file():
                    raise M22QueueError(f"artifact lacks .hydra/config.yaml: {config_path}")
                try:
                    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
                except (OSError, UnicodeError, yaml.YAMLError) as exc:
                    raise M22QueueError(f"cannot read artifact config {config_path}") from exc
                if not isinstance(config, Mapping):
                    raise M22QueueError("artifact config must be a mapping")
                _validate_artifact_config(config, Path(candidate["path"]).resolve(), seed)
                state = "EXPLICIT_ARTIFACT"
                command = None
            else:
                state = "MISSING_ARTIFACT"
                command = build_eval_command(candidate, artifact, seed=seed, gpu=gpu)
        else:
            artifact = output_root / candidate["candidate_id"].removesuffix(".pt") / f"seed{seed}"
            state = "MISSING_ARTIFACT"
            command = build_eval_command(candidate, artifact, seed=seed, gpu=gpu)
        rows.append(
            {
                "candidate": dict(candidate),
                "artifact": str(artifact),
                "artifact_state": state,
                "evaluation_topology": CANONICAL_TOPOLOGY,
                "evaluation_seed": seed,
                "explicit_mapping": mapping is not None,
                "eval_command": command,
            }
        )
    return {
        "schema": QUEUE_SCHEMA,
        "manifest_schema": manifest["schema"],
        "group": manifest.get("group"),
        "candidate_count": len(rows),
        "serial": True,
        "rows": rows,
    }


def write_queue_outputs(queue: Mapping[str, Any], output_root: Path) -> tuple[Path, Path]:
    output_root = Path(output_root).expanduser().resolve()
    if output_root.exists():
        raise M22QueueError(f"refusing to overwrite M22 queue output: {output_root}")
    output_root.mkdir(parents=True)
    json_path = output_root / "a2_piper_v20_m22_queue.json"
    md_path = output_root / "a2_piper_v20_m22_queue.md"
    json_path.write_text(json.dumps(queue, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    lines = [
        "# A2 Piper v20 M22 queue",
        "",
        "| Candidate | Step | Artifact | State |",
        "|---|---:|---|---|",
    ]
    for row in queue["rows"]:
        candidate = row["candidate"]
        lines.append(f"| `{candidate['candidate_id']}` | {candidate['step']} | `{row['artifact']}` | {row['artifact_state']} |")
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
    manifest_path = write_immutable_manifest(build_manifest(args.run_dir), args.manifest)
    manifest = load_manifest(manifest_path)
    queue = build_queue(manifest, load_artifact_mapping(args.artifact_map), args.output_root, seed=args.seed, gpu=args.gpu)
    paths = write_queue_outputs(queue, args.output_root)
    print(f"candidate manifest: {manifest_path}")
    print(f"queue JSON: {paths[0]}")
    print(f"queue Markdown: {paths[1]}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except M22QueueError as exc:
        print(f"v20 M22 QUEUE FAIL: {exc}", file=sys.stderr)
        raise SystemExit(2)
