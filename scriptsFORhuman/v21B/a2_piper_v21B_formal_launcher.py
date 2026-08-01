"""Seven-cell v21-B formal launch plan in one dedicated tmux session.

This module only builds and validates the command contract.  A caller must
explicitly invoke its launch function under the separately leased GPU/tmux
runtime; importing or planning never starts a process.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any, Mapping

import hashlib

from ._v21b_common import V21B_CELL_ORDER, V21B_CONFIG_PATHS, V21BError, V21B_FORMAL_GPUS, V21B_WARM_START_PATH, canonical_json_bytes, parse_gpus, read_yaml, sha256_file, validate_v21b_config
from .a2_piper_v21B_adaptation import materialized_profile_overrides
from .a2_piper_v21B_adaptation import validate_materialized_config_receipt
from .a2_piper_v21B_schemas import artifact_payload, schema, validate_artifact


FORMAL_SESSION = "base_v21B_formal_v1"
FORMAL_TRAINING_REL = "logs_rl/a2_piper_full_stage_a2_base/base_v21B/formal"
FORMAL_LAUNCHER_REL = "logs_rl/launchers/base_v21B/formal"


def build_formal_launch_plan(repo_root: Path, *, adaptation: Mapping[str, Any], p0_admission: Mapping[str, Any], smoke_pass: Mapping[str, Any], cleanup_pass: Mapping[str, Any], materialization: Mapping[str, Any], physical_gpus: tuple[int, ...] = V21B_FORMAL_GPUS, materialized_configs: Mapping[str, Path] | None = None) -> dict[str, Any]:
    parse_gpus(physical_gpus, formal=True)
    validate_artifact(adaptation, expected_schema=schema("adaptation"))
    validate_artifact(p0_admission, expected_schema=schema("p0_admission"))
    validate_artifact(smoke_pass, expected_schema=schema("smoke_adjudication"), expected_cell="B4")
    validate_artifact(cleanup_pass, expected_schema=schema("smoke_cleanup"), expected_cell="B4")
    validate_artifact(materialization, expected_schema=schema("materialization"))
    if smoke_pass.get("status") != "SMOKE_PASS" or cleanup_pass.get("status") != "CLEANUP_PASS":
        raise V21BError("formal launch requires SMOKE_PASS followed by CLEANUP_PASS")
    if materialization.get("status") != "MATERIALIZATION_PASS" or materialization.get("phase") != "FORMAL_PROMOTED":
        raise V21BError("formal launch requires FORMAL_PROMOTED materialized configs")
    overrides = materialized_profile_overrides(adaptation)
    root = repo_root.resolve()
    rows = []
    for cell, gpu in zip(V21B_CELL_ORDER, physical_gpus):
        if materialized_configs is None or cell not in materialized_configs:
            raise V21BError("formal launch requires all seven materialized config paths")
        receipt = validate_materialized_config_receipt(materialization, Path(materialized_configs[cell]), cell=cell, phase="FORMAL_PROMOTED")
        config = Path(receipt["path"])
        loaded = receipt["config"]
        env = loaded.get("env", {}).get("config", {})
        limit = loaded.get("v21b_arm_realistic_effort_limit_nm")
        if loaded.get("v21b_arm_profile") == "ARM_REALISTIC" and limit != overrides["arm_j1..arm_j6_effort_limit_nm"]:
            raise V21BError(f"{cell} materialized ARM_REALISTIC limit does not match adaptation")
        output = root / FORMAL_TRAINING_REL / cell
        argv = [
            "env", "-u", "CUDA_VISIBLE_DEVICES", f"ACCELERATE_TORCH_DEVICE=cuda:{gpu}", "WANDB_MODE=online", f"PYTHONPATH={root}", "/home/baoquanc/anaconda3/envs/isaaclab/bin/python", "-m", "gr00t.rl.train_agent_trl",
            f"--config-dir={config.parent}", f"--config-name={config.stem}", f"checkpoint={V21B_WARM_START_PATH}",
            "checkpoint_load_mode=policy_only", "auto_load_latest=false", "headless=true", "use_wandb=true",
            f"num_envs=4096", f"seed={loaded['seed']}", "algo.trl.num_total_batches=2500", "callbacks.model_save.save_frequency=250",
            "env.config.a2_v21B_formal_launch=true", "+env.config.a2_v21B_census_topology=canonical16", f"+env.config.a2_v21B_materialization_sha256={receipt['materialization_sha256']}", f"+env.config.a2_v21B_materialized_config_sha256={receipt['materialized_config_sha256']}", f"env.config.a2_v21B_source_checkpoint_sha256={materialization['source_checkpoint_sha256']}", f"env.config.a2_v21B_source_lock_sha256={materialization['source_lock_sha256']}", f"env.config.a2_v21B_source_config_sha256={receipt['source_config_sha256']}", f"experiment_dir={output}",
        ]
        window = ["tmux", "new-window", "-d", "-t", FORMAL_SESSION, "-n", cell, "--", *argv]
        rows.append({"cell": cell, "physical_gpu": gpu, "seed": loaded["seed"], "config": str(config), "materialized_config_sha256": receipt["materialized_config_sha256"], "materialization_sha256": receipt["materialization_sha256"], "source_checkpoint_sha256": materialization["source_checkpoint_sha256"], "source_lock_sha256": materialization["source_lock_sha256"], "source_config_sha256": receipt["source_config_sha256"], "command_sha256": hashlib.sha256(canonical_json_bytes(argv)).hexdigest(), "output_root": str(output), "env": {"CUDA_VISIBLE_DEVICES": str(gpu), "WANDB_MODE": "online"}, "argv": argv, "tmux_window_argv": window})
    session = ["tmux", "new-session", "-d", "-s", FORMAL_SESSION, "-n", "B1", "--", *rows[0]["argv"]]
    receipt_hash = materialization.get("materialization_sha256")
    if not isinstance(receipt_hash, str):
        unsigned = dict(materialization)
        unsigned.pop("materialization_sha256", None)
        receipt_hash = hashlib.sha256(canonical_json_bytes(unsigned)).hexdigest()
    return artifact_payload("formal_plan", status="FORMAL_PLAN_COMPLETE", session=FORMAL_SESSION, physical_gpus=list(V21B_FORMAL_GPUS), forbidden_gpus=[7], windows=["B1", "B2", "B3", "B4", "B5", "B6", "B7"], initial_session_argv=session, rows=rows, num_envs=4096, batches=2500, save_frequency=250, checkpoint=V21B_WARM_START_PATH, checkpoint_load_mode="policy_only", auto_load_latest=False, wandb_mode="online", p0_admission_sha256=hashlib.sha256(canonical_json_bytes(dict(p0_admission))).hexdigest(), adaptation_sha256=hashlib.sha256(canonical_json_bytes(dict(adaptation))).hexdigest(), materialization_sha256=receipt_hash, smoke_pass_sha256=hashlib.sha256(canonical_json_bytes(dict(smoke_pass))).hexdigest(), cleanup_pass_sha256=hashlib.sha256(canonical_json_bytes(dict(cleanup_pass))).hexdigest(), monitor_contract={"iteration": 50, "detach_only": True, "kill_processes": False})


def launch_formal_wave(plan: Mapping[str, Any], *, tmux_binary: str = "tmux") -> None:
    """Launch a previously validated plan; never silently downgrade resources."""

    import subprocess
    from .a2_piper_v21B_schemas import validate_artifact, schema
    validate_artifact(plan, expected_schema=schema("formal_plan"))
    if plan.get("physical_gpus") != list(V21B_FORMAL_GPUS) or plan.get("forbidden_gpus") != [7]:
        raise V21BError("formal launch plan GPU contract is invalid")
    initial = list(plan["initial_session_argv"])
    initial[0] = tmux_binary
    subprocess.run(initial, check=True)
    for row in plan["rows"][1:]:
        window = list(row["tmux_window_argv"])
        window[0] = tmux_binary
        subprocess.run(window, check=True)


def main(argv: list[str] | None = None) -> int:
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args(argv)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


build_formal_plan = build_formal_launch_plan

__all__ = ["FORMAL_SESSION", "FORMAL_TRAINING_REL", "FORMAL_LAUNCHER_REL", "build_formal_launch_plan", "build_formal_plan", "launch_formal_wave", "main"]
