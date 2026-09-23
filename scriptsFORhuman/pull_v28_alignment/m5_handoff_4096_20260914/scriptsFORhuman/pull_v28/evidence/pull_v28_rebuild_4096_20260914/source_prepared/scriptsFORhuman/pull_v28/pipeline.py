#!/usr/bin/env python3
"""v28 4096-env train dispatch and one GPU0 natural-evaluation queue."""
from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PYTHON = Path("/home/baoquanc/anaconda3/envs/isaaclab/bin/python")
RUNNER = REPO / "scriptsFORhuman/pull_v26_8/runner.py"
SUPERVISOR = REPO / ".ai/scripts/run_supervisor.py"
MATERIALIZE = REPO / "scriptsFORhuman/pull_v28/config_materialize.py"
REDUCE = REPO / "scriptsFORhuman/pull_v28/reduce.py"
READOUT = REPO / "scriptsFORhuman/pull_v28/readout.py"
SOURCE = REPO / "logs_rl/a2_piper_pull_v26_8_backbone/pull_v26_8_backbone_20260905_natural1_r2/wave2/train/P_S2/resolved_config.yaml"
RUN_GROUP = "pull_v28_rebuild_4096_20260914"
TRAIN_ROOT_DEFAULT = REPO / "logs_rl/a2_piper_pull_v28" / RUN_GROUP
EVAL_ROOT_DEFAULT = REPO / "logs_eval/a2_piper_pull_v28" / RUN_GROUP
CELLS = ("PA_S1", "PA_S2", "PA_S3")
CELL_GPU = {"PA_S1": 1, "PA_S2": 2, "PA_S3": 3}
EVAL_GPU = 0
STEPS = (1500, 3000, 4500, 6000)
TERMINAL_TRAIN_STATES = {"PROCESS_FAILED", "CANCELLED", "LAUNCH_FAILED", "PROCESS_COMPLETED"}
INITIAL_EXPECTED_SECONDS = 151200.0
INITIAL_ETA_SOURCE = "temporary v28 4096 startup estimate; replace after the first formal batches"


def require(value: bool, message: str) -> None:
    if not value:
        raise RuntimeError(message)


def gpu_state(gpu: int) -> tuple[int, list[int]]:
    require(gpu in (0, 1, 2, 3), "v28 uses physical GPU0 through GPU3 only")
    text = subprocess.check_output(
        ["nvidia-smi", f"--id={gpu}", "--query-gpu=memory.free", "--format=csv,noheader,nounits"],
        text=True,
    ).strip()
    free = int(text.splitlines()[0])
    processes = subprocess.check_output(
        ["nvidia-smi", f"--id={gpu}", "--query-compute-apps=pid", "--format=csv,noheader"],
        text=True,
    ).splitlines()
    return free, [int(line.strip()) for line in processes if line.strip() and line.strip() != "No running compute processes found"]


def require_train_gpu(gpu: int) -> None:
    free, processes = gpu_state(gpu)
    require(free >= 20480 and not processes, f"GPU{gpu} unavailable for v28 training: free={free}MiB processes={processes}")


def eval_gpu_ready() -> tuple[bool, str]:
    free, processes = gpu_state(EVAL_GPU)
    if processes:
        return False, f"GPU{EVAL_GPU} is occupied by compute pids={processes}"
    if free < 5120:
        return False, f"GPU{EVAL_GPU} free={free}MiB (<5120MiB)"
    return True, "GPU0 idle"


def receipt_name(root: Path, kind: str, suffix: str, attempt: int) -> str:
    return f"{root.name}_{kind}_{suffix}_attempt{attempt}"


def receipt_path(cell: str, train_root: Path, attempt: int) -> Path:
    name = receipt_name(train_root, "train", cell.lower(), attempt)
    return REPO / ".ai/runtime/runs" / name / "STATUS.json"


def cell_seed(cell: str) -> int:
    require(cell in CELLS, f"unknown v28 4096 cell: {cell}")
    return int(cell[-1])


def runtime_env(gpu: int) -> dict[str, str]:
    env = os.environ.copy()
    env.update(
        CUDA_VISIBLE_DEVICES=str(gpu),
        CUDA_DEVICE_ORDER="PCI_BUS_ID",
        ACCELERATE_TORCH_DEVICE="cuda:0",
        WANDB_MODE="disabled",
        HYDRA_FULL_ERROR="1",
        PYTHONUNBUFFERED="1",
        OMP_NUM_THREADS="8",
        PYTHONPATH=str(REPO),
    )
    return env


def train(a: argparse.Namespace) -> int:
    seed, gpu, root = cell_seed(a.cell), CELL_GPU[a.cell], a.train_root
    output = root / a.cell
    require(not output.exists(), f"fresh training output required: {output}")
    require_train_gpu(gpu)
    output.mkdir(parents=True)
    subprocess.run(
        [
            str(PYTHON), str(MATERIALIZE), "--source", str(SOURCE), "--output", str(output / "config.yaml"),
            "--cell", a.cell, "--seed", str(seed), "--train-dir", str(output),
        ],
        check=True,
    )
    compose = [str(PYTHON), "-B", "-m", "gr00t.rl.train_agent_trl", "--config-dir", str(output), "--config-name", "config", "--cfg", "job", "--resolve"]
    with (output / "resolved_config_verified.yaml").open("x", encoding="utf-8") as stream:
        subprocess.run(compose, env=runtime_env(gpu), stdout=stream, check=True)
    final = output / "model_step_006000.pt"
    command = [
        str(PYTHON), str(RUNNER), "--output", str(output), "--gpu", str(gpu), "--required", final.name, "--", "env",
        *[f"{key}={value}" for key, value in runtime_env(gpu).items() if key in {"CUDA_VISIBLE_DEVICES", "CUDA_DEVICE_ORDER", "ACCELERATE_TORCH_DEVICE", "WANDB_MODE", "HYDRA_FULL_ERROR", "PYTHONUNBUFFERED", "OMP_NUM_THREADS", "PYTHONPATH"}],
        str(PYTHON), "-B", "-m", "gr00t.rl.train_agent_trl", "--config-dir", str(output), "--config-name", "config",
    ]
    return subprocess.run(command, cwd=REPO).returncode


def evaluate(a: argparse.Namespace) -> int:
    require(a.step in STEPS, "unsupported v28 4096 milestone")
    ready, reason = eval_gpu_ready()
    if not ready:
        print(json.dumps({"status": "DEFERRED_RESOURCE", "reason": reason}), flush=True)
        return 75
    seed, train_dir = cell_seed(a.cell), a.train_root / a.cell
    checkpoint = train_dir / f"model_step_{a.step:06d}.pt"
    require(checkpoint.is_file(), f"missing checkpoint: {checkpoint}")
    for side in ("left", "right"):
        output = a.eval_root / a.cell / f"{a.cell}_STEP{a.step}" / side
        require(not output.exists(), f"fresh evaluation output required: {output}")
        output.mkdir(parents=True)
        diagnostic_terms = "[dont_push_door_handle,target_root_distance,pull_door_handle,pull_door_hinge,a2_stage3_unlatch_hold,a2_stage3_stage4_hold_and_drive,penalty_a2_wrist_motion_l2,penalty_a2_wrist_tower_contact,penalty_a2_stage4_arm_default_pose_l1]"
        common = [f"checkpoint={checkpoint}", "checkpoint_load_mode=full", "++auto_load_latest=false", f"++seed={seed}", "++num_envs=64", "++env.config.num_envs=64", "++env.config.simulator.config.scene.num_envs=64", "++simulator.config.scene.num_envs=64", "++headless=true", "++use_wandb=false", "++algo.config.num_mini_batches=1", "++algo.config.eval.num_eval_episodes=64", "++algo.config.eval.eval_num_envs_episodes=true", "++algo.config.eval.dump_to_log_metrics=true", "++algo.config.eval.a2_diagnostic_trace_enabled=true", f"++algo.config.eval.a2_diagnostic_reward_terms={diagnostic_terms}", f"++env.config.a2_door_open_lr_distribution={side}", f"++env.config.a2_door_open_lr_permutation_seed={seed}", "++env.config.enable_staged_reset=true", "++env.config.staged_reset_ratios=[1.0,0.0,0.0,0.0,0.0,0.0]", "++env.config.a2_pull_v6_stage4_bank_enabled=false", "++env.config.a2_pull_v61_late_state_bank_enabled=false", "++simulator.config.render_results=false", "++simulator.config.cameras.enable_cameras=false", f"++eval_name=PULL_V28_{a.cell}_STEP{a.step}_{side}", f"++eval_output_dir={output}", f"hydra.run.dir={output}", "+device=cuda:0"]
        compose = [str(PYTHON), "-B", "-m", "gr00t.rl.eval_agent_trl", *common, "--cfg", "job", "--resolve"]
        with (output / "eval_overrides.yaml").open("x", encoding="utf-8") as stream:
            subprocess.run(compose, env=runtime_env(EVAL_GPU), stdout=stream, check=True)
        command = [str(PYTHON), str(RUNNER), "--output", str(output), "--gpu", str(EVAL_GPU), "--required", "metrics_eval.json", "--required", "a2_v14_per_env_records.json", "--required", "stage2_5_step_trace.json", "--required", "a2_eval_diagnostic_metadata.json", "--required", ".hydra/runtime_config.yaml", "--", "env", *[f"{key}={value}" for key, value in runtime_env(EVAL_GPU).items() if key in {"CUDA_VISIBLE_DEVICES", "CUDA_DEVICE_ORDER", "ACCELERATE_TORCH_DEVICE", "WANDB_MODE", "HYDRA_FULL_ERROR", "PYTHONUNBUFFERED", "OMP_NUM_THREADS", "PYTHONPATH"}], str(PYTHON), "-B", "-m", "gr00t.rl.eval_agent_trl", *common]
        rc = subprocess.run(command, cwd=REPO).returncode
        if rc:
            return rc
    return 0


def cell_decision_path(eval_root: Path, cell: str, step: int) -> Path:
    return eval_root / cell / "decisions" / f"M{step}.json"


def reduce_cell(eval_root: Path, cell: str, step: int) -> tuple[int, int]:
    output = cell_decision_path(eval_root, cell, step)
    require(not output.exists(), f"per-cell decision already exists: {output}")
    reduced = subprocess.run(
        [str(PYTHON), str(REDUCE), "--eval-root", str(eval_root / cell), "--step", str(step), "--output", str(output), "--cells", cell],
        cwd=REPO,
    )
    require(output.is_file(), f"per-cell reducer did not write its decision: {output}")
    readout = subprocess.run([str(PYTHON), str(READOUT), "--decision", str(output), "--output", str(output.with_suffix(".md"))], cwd=REPO)
    return reduced.returncode, readout.returncode


def aggregate_milestone(eval_root: Path, step: int, state: dict) -> None:
    key = str(step)
    if key in state["aggregates"]:
        return
    decisions = [cell_decision_path(eval_root, cell, step) for cell in CELLS]
    if not all(path.is_file() for path in decisions):
        return
    output = eval_root / "decisions" / f"M{step}.json"
    require(not output.exists(), f"aggregate decision already exists: {output}")
    reduced = subprocess.run(
        [str(PYTHON), str(REDUCE), "--step", str(step), "--output", str(output), "--aggregate-decisions", *map(str, decisions)],
        cwd=REPO,
    )
    require(output.is_file(), f"aggregate reducer did not write its decision: {output}")
    readout = subprocess.run([str(PYTHON), str(READOUT), "--decision", str(output), "--output", str(output.with_suffix(".md"))], cwd=REPO)
    state["aggregates"][key] = {
        "decisions": [str(path) for path in decisions],
        "output": str(output),
        "reducer_returncode": reduced.returncode,
        "readout_returncode": readout.returncode,
    }


def write_queue_state(path: Path, state: dict) -> None:
    path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")


def train_status(cell: str, train_root: Path, attempt: int) -> tuple[Path, dict | None]:
    path = receipt_path(cell, train_root, attempt)
    return path, json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None


def terminal_without_checkpoint(cell: str, step: int, train_root: Path, attempt: int) -> tuple[bool, dict]:
    receipt, status = train_status(cell, train_root, attempt)
    if status is None or status.get("process_state") not in TERMINAL_TRAIN_STATES:
        return False, {"receipt": str(receipt)}
    return True, {"receipt": str(receipt), "process_state": status["process_state"]}


def item_key(cell: str, step: int) -> str:
    return f"{cell}:M{step}"


def record_queue_item(state: dict, cell: str, step: int, outcome: dict) -> None:
    state["items"][item_key(cell, step)] = outcome


def eval_queue(a: argparse.Namespace) -> int:
    state_path = a.eval_root / "eval_queue_state.json"
    if state_path.is_file():
        state = json.loads(state_path.read_text(encoding="utf-8"))
    else:
        require(not state_path.exists(), f"queue state is not a file: {state_path}")
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state = {
            "schema": "a2_piper_pull_v28_eval_queue_v1",
            "gpu": EVAL_GPU,
            "attempt": a.attempt,
            "train_root": str(a.train_root),
            "eval_root": str(a.eval_root),
            "train_receipts": {cell: str(receipt_path(cell, a.train_root, a.attempt)) for cell in CELLS},
            "items": {},
            "aggregates": {},
        }
        write_queue_state(state_path, state)

    while True:
        for step in STEPS:
            for cell in CELLS:
                key = item_key(cell, step)
                if key in state["items"]:
                    continue
                checkpoint = a.train_root / cell / f"model_step_{step:06d}.pt"
                if checkpoint.is_file():
                    continue
                terminal, train = terminal_without_checkpoint(cell, step, a.train_root, a.attempt)
                if not terminal:
                    continue
                try:
                    reducer_rc, readout_rc = reduce_cell(a.eval_root, cell, step)
                    outcome = {"status": "MISSING_CHECKPOINT", "checkpoint": str(checkpoint), "train": train, "reducer_returncode": reducer_rc, "readout_returncode": readout_rc}
                except (RuntimeError, subprocess.CalledProcessError) as error:
                    outcome = {"status": "MISSING_CHECKPOINT", "checkpoint": str(checkpoint), "train": train, "decision_error": f"{type(error).__name__}: {error}"}
                record_queue_item(state, cell, step, outcome)
                aggregate_milestone(a.eval_root, step, state)
                write_queue_state(state_path, state)
                break
            else:
                continue
            break
        else:
            ready = None
            for step in STEPS:
                for cell in CELLS:
                    if item_key(cell, step) not in state["items"]:
                        checkpoint = a.train_root / cell / f"model_step_{step:06d}.pt"
                        if checkpoint.is_file():
                            ready = (cell, step, checkpoint)
                            break
                if ready is not None:
                    break
            if ready is not None:
                gpu_ready, reason = eval_gpu_ready()
                if not gpu_ready:
                    state["deferred_resource"] = {"reason": reason, "checkpoint": str(ready[2])}
                    write_queue_state(state_path, state)
                    time.sleep(1800)
                    continue
                cell, step, checkpoint = ready
                try:
                    evaluation_rc = evaluate(argparse.Namespace(cell=cell, step=step, train_root=a.train_root, eval_root=a.eval_root))
                    if evaluation_rc == 75:
                        state["deferred_resource"] = {"reason": "GPU0 became busy before evaluation", "checkpoint": str(checkpoint)}
                        write_queue_state(state_path, state)
                        time.sleep(1800)
                        continue
                    reducer_rc, readout_rc = reduce_cell(a.eval_root, cell, step)
                    outcome = {"status": "VALID" if evaluation_rc == reducer_rc == readout_rc == 0 else "INVALID", "checkpoint": str(checkpoint), "evaluation_returncode": evaluation_rc, "reducer_returncode": reducer_rc, "readout_returncode": readout_rc}
                except (RuntimeError, subprocess.CalledProcessError) as error:
                    outcome = {"status": "INVALID", "checkpoint": str(checkpoint), "error": f"{type(error).__name__}: {error}"}
                record_queue_item(state, cell, step, outcome)
                state.pop("deferred_resource", None)
                aggregate_milestone(a.eval_root, step, state)
                write_queue_state(state_path, state)
                continue

            for step in STEPS:
                aggregate_milestone(a.eval_root, step, state)
            if len(state["items"]) == len(CELLS) * len(STEPS):
                state["process_state"] = "PROCESS_COMPLETED"
                write_queue_state(state_path, state)
                return 0
            state["waiting"] = "no checkpoint is ready and no training receipt is terminal before its checkpoint"
            write_queue_state(state_path, state)
            time.sleep(1800)
            continue
        continue


def submit(a: argparse.Namespace, kind: str) -> int:
    if kind == "train":
        gpu = CELL_GPU[a.cell]
        command = [str(PYTHON), str(Path(__file__).resolve()), "train", "--cell", a.cell, "--train-root", str(a.train_root), "--eval-root", str(a.eval_root)]
        suffix = a.cell.lower()
        output = a.train_root / f"{a.cell}__train_attempt{a.attempt}.supervisor.log"
    else:
        gpu = EVAL_GPU
        command = [str(PYTHON), str(Path(__file__).resolve()), "eval-queue", "--attempt", str(a.attempt), "--train-root", str(a.train_root), "--eval-root", str(a.eval_root)]
        suffix = "gpu0"
        output = a.eval_root / f"eval_queue_attempt{a.attempt}.supervisor.log"
    name = receipt_name(a.train_root, kind, suffix, a.attempt)
    prepared = subprocess.check_output(
        [
            str(PYTHON), str(SUPERVISOR), "prepare", "--project-root", str(REPO), "--name", name,
            "--command", shlex.join(command), "--cwd", str(REPO), "--output", str(output),
            "--expected-seconds", str(a.expected_seconds), "--eta-source", a.eta_source,
            "--stop-condition", "declared v28 budget; invalid or missing evaluation is recorded without stopping training",
            "--resource", f"GPU{gpu}", "--config-ref", "gr00t/rl/config/ablation/wbmanip/pull_v28_common.yaml",
            "--checkpoint-lineage", "null scratch",
        ],
        text=True,
    )
    receipt = json.loads(prepared)["receipt"]
    subprocess.run([str(PYTHON), str(SUPERVISOR), "launch", "--receipt", receipt, "--backend", "tmux"], check=True)
    print(json.dumps({"receipt": receipt, "session": name, "gpu": gpu}))
    return 0


def add_roots(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--train-root", type=Path, default=TRAIN_ROOT_DEFAULT)
    parser.add_argument("--eval-root", type=Path, default=EVAL_ROOT_DEFAULT)


def add_submit_timing(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--expected-seconds", type=float, default=INITIAL_EXPECTED_SECONDS)
    parser.add_argument("--eta-source", default=INITIAL_ETA_SOURCE)


def main() -> int:
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="action", required=True)
    x = sub.add_parser("train"); x.set_defaults(func=train); x.add_argument("--cell", required=True, choices=CELLS); add_roots(x)
    x = sub.add_parser("eval"); x.set_defaults(func=evaluate); x.add_argument("--cell", required=True, choices=CELLS); x.add_argument("--step", type=int, required=True, choices=STEPS); add_roots(x)
    x = sub.add_parser("eval-queue"); x.set_defaults(func=eval_queue); x.add_argument("--attempt", type=int, default=1); add_roots(x)
    x = sub.add_parser("submit-train"); x.set_defaults(func=lambda a: submit(a, "train")); x.add_argument("--cell", required=True, choices=CELLS); x.add_argument("--attempt", type=int, default=1); add_roots(x); add_submit_timing(x)
    x = sub.add_parser("submit-eval-queue"); x.set_defaults(func=lambda a: submit(a, "eval_queue")); x.add_argument("--attempt", type=int, default=1); add_roots(x); add_submit_timing(x)
    a = p.parse_args()
    return a.func(a)


if __name__ == "__main__":
    raise SystemExit(main())
