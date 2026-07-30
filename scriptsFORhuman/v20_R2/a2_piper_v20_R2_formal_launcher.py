"""Formal launcher: build an explicit plan, then optionally launch one tmux wave."""
from __future__ import annotations

import argparse
import subprocess
from pathlib import Path
from typing import Any

from ._r2_common import R2Error, canonical_json, validate_regular_file
from ._r2_workflow import (
    GROUPS,
    artifact_hash,
    parse_gpus,
    read_artifact,
    r2_config_path,
    spawn_once,
    train_command,
    write_raw,
)

ATTEMPT_SCHEMA = "a2_piper_base_v20_R2_training_attempt_v1"
ATTEMPT_MARKER = "logs_eval/base_v20_R2/locks/FORMAL_WAVE_ATTEMPT_CONSUMED.json"


def build_formal_launch_plan(*, promotion_pass: Path, physical_gpus: tuple[int, ...],
                             repo_root: Path, config_root: Path,
                             training_root: Path | None = None,
                             launcher_root: Path | None = None) -> dict[str, object]:
    root = Path(repo_root).resolve()
    if tuple(physical_gpus) != tuple(range(7)):
        raise R2Error("formal launch requires one-to-one physical GPUs 0-6")
    promotion = read_artifact(promotion_pass, schema="a2_piper_base_v20_R2_config_promotion_artifact_v1",
                              adjudicator_state="PROMOTION_PASS")
    configs = promotion.get("configs")
    if not isinstance(configs, list) or {row.get("group") for row in configs} != set(GROUPS):
        raise R2Error("promotion PASS must bind all seven frozen configs")
    frozen_by_group = {row["group"]: Path(row["frozen_path"]) for row in configs}
    base = training_root or root / "logs_rl/a2_piper_full_stage_a2_base/base_v20_R2/formal"
    launch_base = launcher_root or root / "logs_rl/launchers/base_v20_R2/formal"
    rows: list[dict[str, object]] = []
    for group, gpu in zip(GROUPS, physical_gpus):
        config = frozen_by_group[group]
        config = validate_regular_file(config, label=f"promoted {group} config")
        seed = 1 if group == "G7" else 0
        group_root = base / group
        train_argv, env, binding = train_command(repo_root=root, config=config, gpu=gpu, group=group,
                                                 seed=seed, num_envs=4096, batches=2500,
                                                 save_frequency=250, output_root=group_root, formal=True)
        tmux_session = f"base_v20_R2_formal_{group}"
        tmux_argv = ["tmux", "new-session", "-d", "-s", tmux_session, "--", *train_argv]
        rows.append({"group": group, "physical_gpu": gpu, "seed": seed,
                     "tmux_session": tmux_session, "argv": train_argv, "tmux_argv": tmux_argv,
                     "env": env, "device": binding, "config_sha256": artifact_hash(config),
                     "output_root": str(group_root), "launcher_root": str(launch_base)})
    return {"schema": ATTEMPT_SCHEMA, "producer_state": "LAUNCH_PLAN_COMPLETE",
            "attempt_id": "formal-wave-seed0-seed1-G7", "group": "G1",
            "command": rows[0]["tmux_argv"], "env": rows[0]["env"],
            "source_lock_sha256": promotion["source_lock_sha256"],
            "config_sha256": rows[0]["config_sha256"], "checkpoint_sha256": None,
            "promotion_pass_sha256": artifact_hash(promotion_pass), "groups": rows,
            "training_root": str(base), "launcher_root": str(launch_base)}


def _consume_attempt_marker(*, root: Path, plan: dict[str, object], promotion_pass: Path,
                            marker: Path) -> None:
    payload = {"schema": ATTEMPT_SCHEMA, "producer_state": "ATTEMPT_CONSUMED",
               "attempt_id": plan["attempt_id"], "group": "G1", "command": plan["command"],
               "env": plan["env"], "source_lock_sha256": plan["source_lock_sha256"],
               "config_sha256": plan["config_sha256"], "promotion_pass_sha256": artifact_hash(promotion_pass),
               "groups": plan["groups"]}
    write_raw(marker, payload, producer_state="ATTEMPT_CONSUMED")


def run_formal_wave(*, repo_root: Path, promotion_pass: Path, physical_gpus: tuple[int, ...],
                    config_root: Path, launcher_root: Path, training_root: Path,
                    output: Path | None = None, attempt_marker: Path | None = None,
                    tmux_path: str = "tmux") -> dict[str, object]:
    root = Path(repo_root).resolve()
    plan = build_formal_launch_plan(promotion_pass=promotion_pass, physical_gpus=physical_gpus,
                                    repo_root=root, config_root=config_root,
                                    training_root=training_root, launcher_root=launcher_root)
    marker = attempt_marker or root / ATTEMPT_MARKER
    _consume_attempt_marker(root=root, plan=plan, promotion_pass=promotion_pass, marker=marker)
    launcher_root.mkdir(parents=True, exist_ok=True)
    write_raw(launcher_root / "formal_launch_plan.json", plan, producer_state="LAUNCH_PLAN_COMPLETE")
    receipts: list[dict[str, object]] = []
    for row in plan["groups"]:
        tmux_argv = [tmux_path, *list(row["tmux_argv"])[1:]]
        group_root = Path(str(row["output_root"]))
        # One independent tmux session per group.  spawn_once captures the
        # launcher receipt; formal_completion later verifies child closure and
        # training outputs rather than treating this plan as PASS.
        receipt = spawn_once(argv=tmux_argv, repo_root=root, output_root=group_root,
                             env=row["env"], name=f"formal_{row['group']}_tmux",
                             physical_gpu=int(row["physical_gpu"]), attempt_marker=marker,
                             active_source_lock=None, parents={"promotion_pass": promotion_pass},
                             marker_payload={"group": row["group"], "seed": row["seed"],
                                             "tmux_session": row["tmux_session"]})
        receipts.append({"group": row["group"], "seed": row["seed"],
                         "process_receipt": str(group_root / "process_receipt.json"),
                         "receipt_sha256": artifact_hash(group_root / "process_receipt.json"),
                         "exit_code": receipt["exit_code"]})
    result = {"schema": ATTEMPT_SCHEMA, "producer_state": "PROCESS_COMPLETED",
              "attempt_id": plan["attempt_id"], "group": "G1", "command": plan["command"],
              "env": plan["env"], "source_lock_sha256": plan["source_lock_sha256"],
              "config_sha256": plan["config_sha256"], "promotion_pass_sha256": artifact_hash(promotion_pass),
              "groups": plan["groups"], "process_receipts": receipts,
              "attempt_marker": str(marker), "attempt_marker_sha256": artifact_hash(marker)}
    if output is not None:
        write_raw(output, result, producer_state="PROCESS_COMPLETED")
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, required=True); parser.add_argument("--promotion-pass", type=Path, required=True)
    parser.add_argument("--physical-gpus", required=True); parser.add_argument("--launcher-root", type=Path, required=True)
    parser.add_argument("--training-root", type=Path, required=True); parser.add_argument("--config-root", type=Path, required=False)
    parser.add_argument("--output", type=Path); parser.add_argument("--attempt-marker", type=Path); parser.add_argument("--tmux-path", default="tmux")
    args = parser.parse_args(argv)
    root = args.repo_root.resolve(); config_root = args.config_root or root / "logs_eval/base_v20_R2/promotion/frozen_configs"
    run_formal_wave(repo_root=root, promotion_pass=args.promotion_pass, physical_gpus=parse_gpus(args.physical_gpus),
                    config_root=config_root, launcher_root=args.launcher_root, training_root=args.training_root,
                    output=args.output, attempt_marker=args.attempt_marker, tmux_path=args.tmux_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
