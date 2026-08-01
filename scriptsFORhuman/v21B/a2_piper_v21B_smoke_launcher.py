"""Single B4 64-env/10-batch smoke plan (no implicit multi-cell launch)."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
from typing import Any, Mapping

from ._v21b_common import V21BError, V21B_WARM_START_PATH, canonical_json_bytes, read_yaml, sha256_file, validate_v21b_config
from .a2_piper_v21B_adaptation import validate_materialized_config_receipt
from .a2_piper_v21B_schemas import artifact_payload, schema, validate_artifact


SMOKE_TRAINING_REL = "logs_rl/a2_piper_full_stage_a2_base_smoke/base_v21B/B4"
SMOKE_LAUNCHER_REL = "logs_rl/launchers/base_v21B_smoke/B4"
V21B_PYTHON = "/home/baoquanc/anaconda3/envs/isaaclab/bin/python"


def build_b4_smoke_plan(repo_root: Path, *, adaptation: Mapping[str, Any], p0_admission: Mapping[str, Any], materialization: Mapping[str, Any], materialized_config: Path, output_root: Path | None = None, gpu: int = 3) -> dict[str, Any]:
    if gpu == 7 or gpu not in range(7):
        raise V21BError("B4 smoke cannot use GPU7; expected a legal physical GPU 0-6")
    validate_artifact(adaptation, expected_schema=schema("adaptation"), expected_cell=None)
    validate_artifact(p0_admission, expected_schema=schema("p0_admission"))
    validate_artifact(materialization, expected_schema=schema("materialization"))
    if materialization.get("phase") != "FORMAL_PROMOTED" or materialization.get("adaptation_bundle_sha256") != hashlib.sha256(canonical_json_bytes(dict(adaptation))).hexdigest():
        raise V21BError("B4 smoke requires a signed FORMAL_PROMOTED materialization bound to adaptation")
    receipt = validate_materialized_config_receipt(materialization, Path(materialized_config), cell="B4", phase="FORMAL_PROMOTED")
    config_path = Path(receipt["path"])
    loaded = receipt["config"]
    root = repo_root.resolve()
    config = config_path
    training_root = output_root.resolve() if output_root is not None else root / SMOKE_TRAINING_REL
    if training_root.name != "B4" or "base_v21B" not in training_root.as_posix():
        raise V21BError("B4 smoke output must be the dedicated base_v21B/B4 root")
    launcher_root = root / SMOKE_LAUNCHER_REL
    adaptation_sha256 = hashlib.sha256(canonical_json_bytes(dict(adaptation))).hexdigest()
    argv = [
        "env", "-u", "CUDA_VISIBLE_DEVICES", f"ACCELERATE_TORCH_DEVICE=cuda:{gpu}", "WANDB_MODE=online", f"PYTHONPATH={root}", V21B_PYTHON, "-m", "gr00t.rl.train_agent_trl", f"--config-dir={config.parent}", f"--config-name={config.stem}",
        f"checkpoint={V21B_WARM_START_PATH}", "checkpoint_load_mode=policy_only", "auto_load_latest=false", "headless=true",
        "use_wandb=true",
        "num_envs=64", "seed=0", "algo.trl.num_total_batches=10", "callbacks.model_save.save_frequency=10",
        f"env.config.a2_v21B_adaptation_bundle_sha256={adaptation_sha256}",
        f"+env.config.a2_v21B_materialization_sha256={receipt['materialization_sha256']}",
        f"+env.config.a2_v21B_materialized_config_sha256={receipt['materialized_config_sha256']}",
        f"env.config.a2_v21B_source_checkpoint_sha256={materialization['source_checkpoint_sha256']}",
        f"env.config.a2_v21B_source_lock_sha256={materialization['source_lock_sha256']}",
        f"env.config.a2_v21B_source_config_sha256={receipt['source_config_sha256']}",
        "+env.config.a2_v21B_census_topology=canonical16",
        f"experiment_dir={training_root}", "env.config.a2_v21B_formal_launch=true",
    ]
    payload = artifact_payload("smoke_plan", status="SMOKE_PLAN_COMPLETE", cell="B4", physical_gpu=gpu, num_envs=64, batches=10, save_frequency=10, training_root=str(training_root), launcher_root=str(launcher_root), checkpoint=V21B_WARM_START_PATH, checkpoint_load_mode="policy_only", auto_load_latest=False, adaptation_bundle_sha256=adaptation_sha256, p0_admission_sha256=hashlib.sha256(canonical_json_bytes(dict(p0_admission))).hexdigest(), source_checkpoint_sha256=materialization["source_checkpoint_sha256"], source_lock_sha256=materialization["source_lock_sha256"], source_config_sha256=receipt["source_config_sha256"], materialization_sha256=receipt["materialization_sha256"], materialized_config_sha256=receipt["materialized_config_sha256"], materialized_config_path=str(config_path), command_sha256=hashlib.sha256(canonical_json_bytes(argv)).hexdigest(), wandb_mode="online", command=argv, one_cell_only=True, canonical_root_contract={"training": SMOKE_TRAINING_REL, "launcher": SMOKE_LAUNCHER_REL})
    payload["plan_sha256"] = hashlib.sha256(canonical_json_bytes(payload)).hexdigest()
    return validate_artifact(payload, expected_schema=schema("smoke_plan"), expected_cell="B4")


def main(argv: list[str] | None = None) -> int:
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args(argv)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["SMOKE_TRAINING_REL", "SMOKE_LAUNCHER_REL", "V21B_PYTHON", "build_b4_smoke_plan", "main"]
