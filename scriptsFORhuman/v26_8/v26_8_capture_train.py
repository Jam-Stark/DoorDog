#!/usr/bin/env python3
"""Stream one policy-only train process and persist its observed load receipt."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
PLAN = ROOT / "scriptsFORhuman/v26_8/a2_piper_base_v26_8_bilateral_opening_scaffold_decay_plan_20260903.md"
LOAD_LINE = "Loaded policy-only checkpoint actor from key 'policy_state_dict'; actor_rms_loaded=True"


def require(value: bool, message: str) -> None:
    if not value:
        raise RuntimeError(message)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    require(args.command and args.command[0] == "--", "capture wrapper requires '-- COMMAND ...'")
    command = args.command[1:]
    require(command, "capture wrapper requires a train command")
    cfg_path = args.output / "resolved_config.yaml"
    require(args.output.is_dir() and cfg_path.is_file() and args.checkpoint.is_file() and PLAN.is_file(), "capture wrapper input artifact")
    cfg = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
    require(cfg.get("checkpoint_load_mode") == "policy_only" and cfg.get("policy_only_load_actor_rms") is True, "capture wrapper policy-only actor-RMS contract")
    eval_cfg = cfg.get("algo", {}).get("config", {}).get("eval", {})
    require(eval_cfg.get("a2_v26_5_policy_only_identity_control", False) is False and eval_cfg.get("a2_v26_5_policy_only_residual", False) is False, "capture wrapper requires the ordinary legacy actor loader")
    require(Path(cfg["checkpoint"]).as_posix() == args.checkpoint.relative_to(ROOT).as_posix(), "capture wrapper checkpoint/config mismatch")
    source = (ROOT / "gr00t/rl/trl/trainer/ppo_trainer_a2_base_api.py").read_text(encoding="utf-8")
    require("Loaded policy-only checkpoint actor from key" in source and "elif load_actor_rms:" in source and "actor_state, strict=True" in source, "capture wrapper strict-loader source binding")
    log_path = args.output / "train_runtime.log"
    receipt_path = args.output / "v26_8_policy_load_receipt.json"
    process_receipt_path = args.output / "v26_8_runtime_process_receipt.json"
    require(
        not log_path.exists()
        and not receipt_path.exists()
        and not process_receipt_path.exists(),
        "capture wrapper refuses existing output",
    )
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
    seen = False
    with log_path.open("x", encoding="utf-8") as log:
        require(process.stdout is not None, "capture wrapper stdout pipe")
        for line in process.stdout:
            sys.stdout.write(line); sys.stdout.flush(); log.write(line); log.flush()
            if LOAD_LINE in line:
                require(not seen, "capture wrapper observed duplicated strict policy-load line")
                payload = {"schema": "a2_piper_base_v26_8_policy_load_receipt_v1", "status": "POLICY_LOAD_CONFIRMED", "checkpoint": str(args.checkpoint), "checkpoint_sha256": sha256(args.checkpoint), "plan_sha256": sha256(PLAN), "checkpoint_load_mode": "policy_only", "actor_rms_loaded": True, "strict": True, "state_key": "policy_state_dict"}
                with receipt_path.open("x", encoding="utf-8") as receipt:
                    json.dump(payload, receipt, indent=2, sort_keys=True, allow_nan=False); receipt.write("\n")
                seen = True
    return_code = process.wait()
    wrapper_returncode = (
        1 if return_code == 0 and not seen else return_code % 256
    )
    process_payload = {
        "schema": "a2_piper_base_v26_8_runtime_process_receipt_v1",
        "status": (
            "RUNTIME_PROCESS_PASS"
            if return_code == 0 and wrapper_returncode == 0 and seen
            else "RUNTIME_PROCESS_FAIL"
        ),
        "isaac_process_returncode": return_code,
        "wrapper_returncode": wrapper_returncode,
        "policy_load_observed": seen,
    }
    with process_receipt_path.open("x", encoding="utf-8") as receipt:
        json.dump(process_payload, receipt, indent=2, sort_keys=True, allow_nan=False)
        receipt.write("\n")
    if seen:
        payload = json.loads(receipt_path.read_text(encoding="utf-8"))
        payload.update(
            {
                "isaac_process_returncode": return_code,
                "wrapper_returncode": wrapper_returncode,
                "runtime_process_receipt": str(process_receipt_path),
            }
        )
        receipt_path.write_text(
            json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n",
            encoding="utf-8",
        )
    if return_code == 0:
        require(seen, "training exited zero without the strict policy-load success line")
    return return_code


if __name__ == "__main__":
    raise SystemExit(main())
