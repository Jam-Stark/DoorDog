#!/usr/bin/env python3
"""Validate and type the R12 dual-input wiring evidence without rerunning Isaac."""
from __future__ import annotations

import argparse
import json
import shlex
from pathlib import Path
from typing import Any

from omegaconf import OmegaConf


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "logs_rl/by_batch/base_v26_acquisition_supplement_20260823/continuation/V26A_LR_S1_POLICY800/model_step_002000.pt"
WIRING_SCRIPT = ROOT / "scriptsFORhuman/v26_5/v26_5_wave2_r1_r12_wiring_gate.sh"
RAW_OBS = ["dof_pos", "relative_to_door", "dof_vel", "actions", "projected_gravity", "door_dof_pos", "base_lin_vel", "base_ang_vel", "hand_force", "stage", "privileged_door_info", "delta_actions", "gripper_handle_transform", "a2_base_command_raw", "a2_base_command"]
GAUGE_OBS = [*RAW_OBS[:12], "gripper_handle_transform_gauge", *RAW_OBS[13:]]
DUAL_INPUT_CONTRACT = {"base_input_key": "actor_obs", "residual_input_key": "residual_actor_obs", "base_observation_width": 133, "residual_observation_width": 133, "base_memory_mlp_frozen": True, "base_std_rms_frozen": True, "residual_action_slice": [5, 12], "residual_final_layer_zero": True}
SCHEMA = "a2_piper_base_v26_5_r12_wiring_validator_v1"


def require(value: bool, message: str) -> None:
    if not value:
        raise RuntimeError(message)


def load_json(path: Path) -> Any:
    require(path.is_file(), f"missing wiring artifact: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def paths(raw_output: Path, supervisor_receipt: Path) -> tuple[Path, Path]:
    raw = raw_output.resolve()
    receipt = supervisor_receipt.resolve()
    require(raw.is_dir(), f"wiring raw output is not a directory: {raw}")
    require(receipt.is_file(), f"wiring supervisor receipt missing: {receipt}")
    return raw, receipt


def validate_source_receipt(raw: Path, receipt_path: Path, *, provenance: str) -> tuple[dict[str, Any], Path, dict[str, bool]]:
    receipt = load_json(receipt_path)
    require(isinstance(receipt, dict), f"invalid supervisor receipt: {receipt_path}")
    command = receipt.get("command")
    require(isinstance(command, str), f"supervisor command missing: {receipt_path}")
    argv = shlex.split(command)
    require(len(argv) >= 4 and argv[:2] == ["bash", str(WIRING_SCRIPT)] and argv[2] == "4" and argv[3] == str(raw), f"supervisor command does not bind wiring raw output: {receipt_path}")
    require(receipt.get("checkpoint") == str(raw / "metrics_eval.json"), f"supervisor checkpoint does not bind wiring raw output: {receipt_path}")
    log = Path(receipt.get("output", "")).resolve()
    require(log.is_file(), f"supervisor log missing: {log}")
    text = log.read_text(encoding="utf-8")
    if provenance == "immutable_failed":
        require(receipt.get("state") == "FAIL" and receipt.get("process_returncode") == 1, f"immutable wiring receipt is not the original FAIL/1: {receipt_path}")
        evidence = {"evaluation_completed_exact64": "Evaluation completed - 64 episodes finished" in text, "post_eval_constructor_error_posixpath": "ConstructorError" in text and "PosixPath" in text}
        require(all(evidence.values()), f"immutable wiring receipt did not fail at the post-eval YAML constructor boundary: {log}")
    elif provenance == "live_validation":
        require(receipt.get("state") == "RUNNING", f"live wiring receipt must be RUNNING during post-eval validation: {receipt_path}")
        evidence = {"evaluation_completed_exact64": "Evaluation completed - 64 episodes finished" in text, "post_eval_constructor_error_posixpath": "ConstructorError" in text and "PosixPath" in text}
        require(evidence["evaluation_completed_exact64"] and not evidence["post_eval_constructor_error_posixpath"], f"live wiring validation did not follow a clean completed eval: {log}")
    elif provenance == "clean_completed":
        require(receipt.get("state") == "PASS" and receipt.get("process_returncode") == 0, f"future wiring receipt is not PASS/0: {receipt_path}")
        evidence = {"evaluation_completed_exact64": "Evaluation completed - 64 episodes finished" in text, "post_eval_constructor_error_posixpath": "ConstructorError" in text and "PosixPath" in text}
        require(evidence["evaluation_completed_exact64"] and not evidence["post_eval_constructor_error_posixpath"], f"future wiring receipt did not complete cleanly: {log}")
    else:
        raise RuntimeError(f"unknown wiring receipt provenance: {provenance}")
    return receipt, log, evidence


def measured_facts(raw: Path) -> dict[str, Any]:
    config = OmegaConf.to_container(OmegaConf.load(raw / ".hydra/runtime_config.yaml"), resolve=False)
    receipt = load_json(raw / "a2_v26_5_runtime_load_receipt.json")
    metrics = load_json(raw / "metrics_eval.json")
    records = load_json(raw / "a2_v14_per_env_records.json")
    require(isinstance(config, dict) and isinstance(receipt, dict) and isinstance(metrics, dict) and isinstance(records, list), f"invalid wiring raw schema: {raw}")
    env = config["env"]["config"]
    obs = config["obs"]["obs_dict"]
    require(env.get("max_episode_length_s") == 0.02 and env.get("a2_v26_5_geometry_target_enabled") is False, f"wiring runtime main geometry/timeout mismatch: {raw}")
    require(obs.get("actor_obs") == RAW_OBS and obs.get("residual_actor_obs") == GAUGE_OBS, f"wiring raw/gauge observation contract mismatch: {raw}")
    actor = receipt.get("actor")
    require(receipt.get("schema") == "a2_piper_base_v26_5_runtime_load_receipt_v1" and receipt.get("status") == "CHECKPOINT_LOAD_COMPLETED" and receipt.get("invocation_kind") == "eval" and receipt.get("output_root") == str(raw) and receipt.get("checkpoint_path") == str(SOURCE) and receipt.get("checkpoint_load_mode") == "policy_only", f"wiring receipt provenance mismatch: {raw}")
    require(isinstance(actor, dict) and actor.get("loaded") is True and actor.get("state_key") == "policy_state_dict" and actor.get("exact_keyset") is True and actor.get("keyset_contract") == "legacy_exact_without_residual" and actor.get("actor_rms_loaded") is True and actor.get("strict") is False and actor.get("missing_keys") == ["residual_module.0.weight", "residual_module.0.bias", "residual_module.2.weight", "residual_module.2.bias"] and actor.get("unexpected_keys") == [] and actor.get("dual_input_contract") == DUAL_INPUT_CONTRACT, f"wiring dual actor receipt mismatch: {raw}")
    terminal = metrics.get("episode_terminal_diagnostics")
    lengths = metrics.get("episode_lengths")
    require(metrics.get("completed_episodes") == 64 and isinstance(terminal, list) and isinstance(lengths, list) and len(terminal) == len(lengths) == len(records) == 64, f"wiring exact64 episode evidence missing: {raw}")
    require(set(row.get("env_id") for row in terminal) == set(range(64)) and all(value == 2 for value in lengths) and all(row.get("episode_length_buf") == 2 for row in terminal), f"wiring two-control-tick terminal evidence mismatch: {raw}")
    return {"runtime_config": {"max_episode_length_s": env["max_episode_length_s"], "main_geometry_target_enabled": env["a2_v26_5_geometry_target_enabled"], "actor_obs": obs["actor_obs"], "residual_actor_obs": obs["residual_actor_obs"]}, "dual_receipt": {"checkpoint_path": receipt["checkpoint_path"], "checkpoint_load_mode": receipt["checkpoint_load_mode"], "actor_state_key": actor["state_key"], "actor_rms_loaded": actor["actor_rms_loaded"], "dual_input_contract": actor["dual_input_contract"]}, "episode_evidence": {"completed_episodes": metrics["completed_episodes"], "record_count": len(records), "terminal_count": len(terminal), "episode_lengths": lengths, "terminal_episode_length_buf": [row["episode_length_buf"] for row in terminal]}}


def assert_admitted(artifact: Path, raw: Path, receipt: Path) -> None:
    value = load_json(artifact)
    require(value.get("schema") == SCHEMA and value.get("status") == "PASS" and value.get("raw_output") == str(raw), f"wiring typed admission missing: {artifact}")
    current = load_json(receipt)
    if current.get("state") == "FAIL" and current.get("process_returncode") == 1:
        _, log, evidence = validate_source_receipt(raw, receipt, provenance="immutable_failed")
        require(value.get("outcome") == "R12_WIRING_ADMITTED_FROM_IMMUTABLE_RAW" and value.get("original_supervisor_receipt") == str(receipt) and value.get("original_supervisor_state") == "FAIL" and value.get("original_supervisor_returncode") == 1 and value.get("original_supervisor_log") == str(log) and value.get("failure_boundary") == "POST_EVAL_VALIDATOR_YAML_CONSTRUCTOR" and value.get("log_evidence") == evidence, f"immutable wiring typed admission provenance mismatch: {artifact}")
    elif current.get("state") == "PASS" and current.get("process_returncode") == 0:
        _, log, evidence = validate_source_receipt(raw, receipt, provenance="clean_completed")
        require(value.get("outcome") == "R12_WIRING_ADMITTED" and value.get("source_supervisor_receipt") == str(receipt) and value.get("source_supervisor_state_at_validation") == "RUNNING" and value.get("source_supervisor_returncode_at_validation") is None and value.get("source_supervisor_log") == str(log) and value.get("failure_boundary") is None and value.get("log_evidence") == evidence, f"clean wiring typed admission provenance mismatch: {artifact}")
    else:
        raise RuntimeError(f"wiring receipt is neither immutable FAIL/1 nor clean PASS/0: {receipt}")
    require(value.get("measured_facts") == measured_facts(raw), f"wiring typed admission facts no longer match immutable/live raw: {artifact}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-output", type=Path, required=True)
    parser.add_argument("--supervisor-receipt", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--immutable-failed-run", action="store_true")
    parser.add_argument("--assert-admitted", action="store_true")
    args = parser.parse_args()
    raw, receipt_path = paths(args.raw_output, args.supervisor_receipt)
    if args.assert_admitted:
        assert_admitted(args.output.resolve(), raw, receipt_path)
        print(args.output.resolve())
        return
    require(not args.output.exists(), f"refusing to overwrite wiring validator artifact: {args.output}")
    provenance = "immutable_failed" if args.immutable_failed_run else "live_validation"
    receipt, log, log_evidence = validate_source_receipt(raw, receipt_path, provenance=provenance)
    facts = measured_facts(raw)
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    payload = {"schema": SCHEMA, "status": "PASS", "outcome": "R12_WIRING_ADMITTED_FROM_IMMUTABLE_RAW" if args.immutable_failed_run else "R12_WIRING_ADMITTED", "raw_output": str(raw), "failure_boundary": "POST_EVAL_VALIDATOR_YAML_CONSTRUCTOR" if args.immutable_failed_run else None, "log_evidence": log_evidence, "measured_facts": facts}
    if args.immutable_failed_run:
        payload.update({"original_supervisor_receipt": str(receipt_path), "original_supervisor_state": receipt["state"], "original_supervisor_returncode": receipt.get("process_returncode"), "original_supervisor_log": str(log)})
    else:
        payload.update({"source_supervisor_receipt": str(receipt_path), "source_supervisor_state_at_validation": receipt["state"], "source_supervisor_returncode_at_validation": receipt.get("process_returncode"), "source_supervisor_log": str(log)})
    with output.open("x", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, allow_nan=False)
        handle.write("\n")
    print(output)


if __name__ == "__main__":
    main()
