"""Executable matched-render producer with physical-to-logical device binding."""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from ._r2_common import R2Error, canonical_json, device_env, validate_device_contract, validate_gpu
from ._r2_workflow import artifact_hash, read_artifact, runtime_command, spawn_once, write_raw

RENDER_SCHEMA = "a2_piper_base_v20_R2_render_execution_v1"


def build_render_command(*, repo_root: Path, physical_gpu: int, config: Path, checkpoint: Path,
                         output_root: Path | None = None) -> tuple[list[str], dict[str, str]]:
    gpu = validate_gpu(physical_gpu)
    if not config.is_file() or config.is_symlink() or not checkpoint.is_file() or checkpoint.is_symlink():
        raise R2Error("render config/checkpoint must be regular non-symlink files")
    output = output_root or Path(repo_root) / "logs_eval/base_v20_R2/render"
    extra = ["+checkpoint=" + str(checkpoint), "+num_envs=1", "+seed=0", "+headless=true",
             "+render=true", "+simulator.config.render_results=true",
             "+env.config.a2_v20_R2_trace_root=" + str(output / "traces"),
             "+env.config.a2_v20_R2_record_set_staging_path=" + str(output / "record_set.staging.jsonl")]
    argv, env, binding = runtime_command(module="gr00t.rl.eval_agent_trl", repo_root=repo_root, gpu=gpu,
                                         render=True, extra=extra)
    if binding["logical_device"] != "cuda:0" or env.get("CUDA_VISIBLE_DEVICES") != str(gpu):
        raise R2Error("render must use physical visibility mask and logical cuda:0")
    return argv, env


def _selected_paths(freeze: dict[str, Any]) -> tuple[Path, Path]:
    checkpoint = freeze.get("selected_checkpoint_path")
    config = freeze.get("selected_config_path")
    if not isinstance(checkpoint, str) or not isinstance(config, str):
        raise R2Error("release freeze lacks selected checkpoint/config paths for render")
    return Path(checkpoint), Path(config)


def plan_render(*, release_freeze: Path, m22: Path, pooled: Path, repo_root: Path,
                physical_gpu: int, output_root: Path) -> dict[str, object]:
    freeze = read_artifact(release_freeze, schema="a2_piper_base_v20_R2_release_freeze_v1", adjudicator_state="POLICY_PASS")
    read_artifact(m22, schema="a2_piper_base_v20_R2_m22_adjudication_v1", adjudicator_state="M22_70ROW_PASS")
    read_artifact(pooled, schema="a2_piper_base_v20_R2_endpoint_report_v1", adjudicator_state="POOLED7_PASS")
    checkpoint, config = _selected_paths(freeze)
    argv, env = build_render_command(repo_root=repo_root, physical_gpu=physical_gpu, config=config,
                                     checkpoint=checkpoint, output_root=output_root)
    return {"schema": RENDER_SCHEMA, "producer_state": "COMMAND_PLANNED", "run_uuid": "render-selected",
            "group": freeze["selected_group"], "physical_gpu": physical_gpu, "logical_device": "cuda:0",
            "config_sha256": artifact_hash(config), "checkpoint_sha256": artifact_hash(checkpoint),
            "release_freeze_sha256": artifact_hash(release_freeze), "m22_sha256": artifact_hash(m22),
            "pooled_sha256": artifact_hash(pooled), "videos": [], "command": argv, "env": env,
            "output_root": str(output_root)}


def run_render(*, release_freeze: Path, m22: Path, pooled: Path, repo_root: Path,
               physical_gpu: int, output_root: Path, attempt_marker: Path | None = None) -> dict[str, object]:
    root = Path(repo_root).resolve()
    plan = plan_render(release_freeze=release_freeze, m22=m22, pooled=pooled, repo_root=root,
                       physical_gpu=physical_gpu, output_root=output_root)
    marker = attempt_marker or root / "logs_eval/base_v20_R2/locks/RENDER_ATTEMPT_CONSUMED.json"
    marker_payload = {"schema": RENDER_SCHEMA, "producer_state": "PROCESS_STARTED", "run_uuid": plan["run_uuid"],
                      "group": plan["group"], "physical_gpu": physical_gpu, "logical_device": "cuda:0",
                      "config_sha256": plan["config_sha256"], "checkpoint_sha256": plan["checkpoint_sha256"],
                      "release_freeze_sha256": plan["release_freeze_sha256"]}
    write_raw(marker, marker_payload, producer_state="PROCESS_STARTED")
    # Use the pre-created marker; all render output must be produced by the child.
    checkpoint, config = _selected_paths(read_artifact(release_freeze, schema="a2_piper_base_v20_R2_release_freeze_v1", adjudicator_state="POLICY_PASS"))
    argv, env = build_render_command(repo_root=root, physical_gpu=physical_gpu, config=config,
                                     checkpoint=checkpoint, output_root=output_root)
    receipt = spawn_once(argv=argv, repo_root=root, output_root=output_root, env=env,
                         name="render_selected", render=True, physical_gpu=physical_gpu,
                         attempt_marker=marker, parents={"release_freeze": release_freeze, "m22": m22, "pooled": pooled},
                         marker_payload={"run_uuid": plan["run_uuid"]})
    videos = []
    for video in sorted(output_root.rglob("*.mp4")):
        if video.is_symlink() or not video.is_file() or video.name.endswith(".writing"):
            raise R2Error(f"invalid child render output: {video}")
        videos.append({"path": str(video), "sha256": artifact_hash(video), "sidecar": str(video.with_suffix(".jsonl"))})
    if not videos:
        raise R2Error("render child exited zero without any MP4 output")
    result = {**plan, "producer_state": "PROCESS_COMPLETED", "videos": videos,
              "process_receipt": str(output_root / "process_receipt.json"),
              "process_receipt_sha256": artifact_hash(output_root / "process_receipt.json"),
              "exit_code": receipt["exit_code"]}
    write_raw(output_root / "render_execution.json", result, producer_state="PROCESS_COMPLETED")
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release-freeze", type=Path, required=True); parser.add_argument("--m22", type=Path, required=True)
    parser.add_argument("--pooled", type=Path, required=True); parser.add_argument("--physical-gpu", type=int, required=True)
    parser.add_argument("--repo-root", type=Path, required=True); parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--attempt-marker", type=Path)
    args = parser.parse_args(argv)
    run_render(release_freeze=args.release_freeze, m22=args.m22, pooled=args.pooled, repo_root=args.repo_root,
               physical_gpu=args.physical_gpu, output_root=args.output_root, attempt_marker=args.attempt_marker)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
