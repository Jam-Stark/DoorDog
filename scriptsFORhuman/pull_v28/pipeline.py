#!/usr/bin/env python3
"""v28 train/eval/watcher dispatch.  Long work is declared through run_supervisor."""
from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PYTHON = Path("/home/baoquanc/anaconda3/envs/isaaclab/bin/python")
RUNNER = REPO / "scriptsFORhuman/pull_v26_8/runner.py"
SUPERVISOR = REPO / ".ai/scripts/run_supervisor.py"
MATERIALIZE = REPO / "scriptsFORhuman/pull_v28/config_materialize.py"
REDUCE = REPO / "scriptsFORhuman/pull_v28/reduce.py"
READOUT = REPO / "scriptsFORhuman/pull_v28/readout.py"
P2_ANALYZE = REPO / "scriptsFORhuman/pull_v7/analyze_p2.py"
SOURCE = REPO / "logs_rl/a2_piper_pull_v26_8_backbone/pull_v26_8_backbone_20260905_natural1_r2/wave2/train/P_S2/resolved_config.yaml"
TRAIN_ROOT_DEFAULT = REPO / "logs_rl/a2_piper_pull_v28/pull_v28_baseline_sync_20260913"
EVAL_ROOT_DEFAULT = REPO / "logs_eval/a2_piper_pull_v28/pull_v28_baseline_sync_20260913"
CELLS = ("PA_S1", "PA_S2", "PA_S3")
STEPS = (1500, 3000, 4500, 6000)


def require(value: bool, message: str) -> None:
    if not value:
        raise RuntimeError(message)


def gpu_state(gpu: int) -> tuple[int, list[int]]:
    require(gpu in (1, 2, 3), "v28 uses GPU1, GPU2 or GPU3 only")
    text = subprocess.check_output(["nvidia-smi", f"--id={gpu}", "--query-gpu=memory.free", "--format=csv,noheader,nounits"], text=True).strip()
    free = int(text.splitlines()[0])
    processes = subprocess.check_output(["nvidia-smi", f"--id={gpu}", "--query-compute-apps=pid", "--format=csv,noheader"], text=True).splitlines()
    return free, [int(line.strip()) for line in processes if line.strip() and line.strip() != "No running compute processes found"]


def require_train_gpu(gpu: int) -> None:
    free, processes = gpu_state(gpu)
    require(free >= 20480 and not processes, f"GPU{gpu} unavailable for v28 training: free={free}MiB processes={processes}")


def receipt_path(cell: str, attempt: int) -> Path:
    return REPO / ".ai/runtime/runs" / f"pull_v28_train_{cell.lower()}_attempt{attempt}" / "STATUS.json"


def descendant_pids(root_pid: int) -> set[int]:
    rows = subprocess.check_output(["ps", "-eo", "pid=,ppid="], text=True).splitlines()
    children: dict[int, set[int]] = {}
    for row in rows:
        pid, parent = (int(value) for value in row.split())
        children.setdefault(parent, set()).add(pid)
    owned, todo = {root_pid}, [root_pid]
    while todo:
        current = todo.pop()
        for child in children.get(current, ()):
            if child not in owned:
                owned.add(child); todo.append(child)
    return owned


def eval_gpu_ready(gpu: int, owned_receipt: Path | None = None) -> tuple[bool, str]:
    free, processes = gpu_state(gpu)
    if free < 5120:
        return False, f"GPU{gpu} free={free}MiB (<5120MiB)"
    if not processes:
        return True, "empty card"
    if owned_receipt is None or not owned_receipt.is_file():
        return False, f"GPU{gpu} has unowned compute pids={processes}"
    state = json.loads(owned_receipt.read_text(encoding="utf-8"))
    owner = state.get("supervisor_pid")
    if not isinstance(owner, int):
        return False, f"GPU{gpu} has compute but training ownership is not live"
    unknown = set(processes) - descendant_pids(owner)
    return (not unknown, "same owned training" if not unknown else f"GPU{gpu} unknown compute pids={sorted(unknown)}")


def cell_seed(cell: str) -> int:
    require(cell in CELLS or cell == "G0", f"unknown cell: {cell}")
    return 0 if cell == "G0" else int(cell[-1])


def runtime_env(gpu: int) -> dict[str, str]:
    env = os.environ.copy()
    env.update(CUDA_VISIBLE_DEVICES=str(gpu), CUDA_DEVICE_ORDER="PCI_BUS_ID", ACCELERATE_TORCH_DEVICE="cuda:0", WANDB_MODE="disabled", HYDRA_FULL_ERROR="1", PYTHONUNBUFFERED="1", OMP_NUM_THREADS="8", PYTHONPATH=str(REPO))
    return env


def train(a: argparse.Namespace) -> int:
    seed, root = cell_seed(a.cell), a.train_root
    output = root / a.cell
    require(not output.exists(), f"fresh training output required: {output}")
    require_train_gpu(a.gpu)
    output.mkdir(parents=True)
    batches, envs = (5, 256) if a.smoke else (6000, 1024)
    subprocess.run([str(PYTHON), str(MATERIALIZE), "--source", str(SOURCE), "--output", str(output / "config.yaml"), "--cell", "G0" if a.smoke else a.cell, "--seed", str(seed), "--train-dir", str(output), *( ["--smoke"] if a.smoke else [])], check=True)
    compose = [str(PYTHON), "-B", "-m", "gr00t.rl.train_agent_trl", "--config-dir", str(output), "--config-name", "config", "--cfg", "job", "--resolve"]
    with (output / "resolved_config_verified.yaml").open("x", encoding="utf-8") as stream:
        subprocess.run(compose, env=runtime_env(a.gpu), stdout=stream, check=True)
    final = output / f"model_step_{batches:06d}.pt"
    command = [str(PYTHON), str(RUNNER), "--output", str(output), "--gpu", str(a.gpu), "--required", final.name, "--", "env", *[f"{k}={v}" for k, v in runtime_env(a.gpu).items() if k in {"CUDA_VISIBLE_DEVICES", "CUDA_DEVICE_ORDER", "ACCELERATE_TORCH_DEVICE", "WANDB_MODE", "HYDRA_FULL_ERROR", "PYTHONUNBUFFERED", "OMP_NUM_THREADS", "PYTHONPATH"}], str(PYTHON), "-B", "-m", "gr00t.rl.train_agent_trl", "--config-dir", str(output), "--config-name", "config"]
    return subprocess.run(command, cwd=REPO).returncode


def evaluate(a: argparse.Namespace) -> int:
    require(a.step in STEPS or (a.smoke and a.step == 5), "unsupported v28 milestone")
    ready, reason = eval_gpu_ready(a.gpu, getattr(a, "owned_receipt", None))
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
        common = [f"checkpoint={checkpoint}", "checkpoint_load_mode=full", "++auto_load_latest=false", f"++seed={seed}", "++num_envs=64", "++headless=true", "++use_wandb=false", "++algo.config.num_mini_batches=1", "++algo.config.eval.num_eval_episodes=64", "++algo.config.eval.eval_num_envs_episodes=true", "++algo.config.eval.dump_to_log_metrics=true", "++algo.config.eval.a2_diagnostic_trace_enabled=true", f"++algo.config.eval.a2_diagnostic_reward_terms={diagnostic_terms}", f"++env.config.a2_door_open_lr_distribution={side}", f"++env.config.a2_door_open_lr_permutation_seed={seed}", "++env.config.enable_staged_reset=true", "++env.config.staged_reset_ratios=[1.0,0.0,0.0,0.0,0.0,0.0]", "++env.config.a2_pull_v6_stage4_bank_enabled=false", "++env.config.a2_pull_v61_late_state_bank_enabled=false", "++simulator.config.render_results=false", "++simulator.config.cameras.enable_cameras=false", f"++eval_name=PULL_V28_{a.cell}_STEP{a.step}_{side}", f"++eval_output_dir={output}", f"hydra.run.dir={output}", "+device=cuda:0"]
        compose = [str(PYTHON), "-B", "-m", "gr00t.rl.eval_agent_trl", *common, "--cfg", "job", "--resolve"]
        with (output / "eval_overrides.yaml").open("x", encoding="utf-8") as stream:
            subprocess.run(compose, env=runtime_env(a.gpu), stdout=stream, check=True)
        command = [str(PYTHON), str(RUNNER), "--output", str(output), "--gpu", str(a.gpu), "--required", "metrics_eval.json", "--required", "a2_v14_per_env_records.json", "--required", "stage2_5_step_trace.json", "--required", "a2_eval_diagnostic_metadata.json", "--required", ".hydra/runtime_config.yaml", "--", "env", *[f"{k}={v}" for k, v in runtime_env(a.gpu).items() if k in {"CUDA_VISIBLE_DEVICES", "CUDA_DEVICE_ORDER", "ACCELERATE_TORCH_DEVICE", "WANDB_MODE", "HYDRA_FULL_ERROR", "PYTHONUNBUFFERED", "OMP_NUM_THREADS", "PYTHONPATH"}], str(PYTHON), "-B", "-m", "gr00t.rl.eval_agent_trl", *common]
        rc = subprocess.run(command, cwd=REPO).returncode
        if rc:
            return rc
    return 0


def reduce(a: argparse.Namespace) -> int:
    output = a.eval_root / "decisions" / f"M{a.step}.json"
    reduced = subprocess.run([str(PYTHON), str(REDUCE), "--eval-root", str(a.eval_root), "--step", str(a.step), "--output", str(output), "--cells", *a.cells])
    require(output.is_file(), f"reducer did not write its decision: {output}")
    readout = subprocess.run([str(PYTHON), str(READOUT), "--decision", str(output), "--output", str(output.with_suffix(".md"))])
    return reduced.returncode if reduced.returncode else readout.returncode


def p2_reduce(a: argparse.Namespace) -> int:
    """Keep the frozen P2 reducer in its old-recipe lane before v28 activation."""
    command = [str(PYTHON), str(P2_ANALYZE), "--eval-root", str(a.eval_root), "--step", str(a.step), "--cells", *a.cells]
    if a.output:
        command.extend(["--output", str(a.output)])
    return subprocess.run(command, cwd=REPO).returncode


def watch(a: argparse.Namespace) -> int:
    state_path = a.eval_root / a.cell / "watcher_state.json"
    require(not state_path.exists(), f"fresh watcher state required: {state_path}")
    state_path.parent.mkdir(parents=True, exist_ok=True)
    train_state = receipt_path(a.cell, a.attempt)
    state = {"schema": "a2_piper_pull_v28_watcher_v1", "cell": a.cell, "gpu": a.gpu, "attempt": a.attempt, "completed": []}
    state_path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    for step in STEPS:
        checkpoint = a.train_root / a.cell / f"model_step_{step:06d}.pt"
        while not checkpoint.is_file():
            if train_state.is_file():
                train_status = json.loads(train_state.read_text(encoding="utf-8"))
                if train_status.get("process_state") in {"PROCESS_FAILED", "CANCELLED", "LAUNCH_FAILED", "PROCESS_COMPLETED"}:
                    state["train_terminal_before_checkpoint"] = {"step": step, "process_state": train_status["process_state"]}
                    state_path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
                    return 2
            time.sleep(1800)
        try:
            while True:
                rc = evaluate(argparse.Namespace(cell=a.cell, step=step, gpu=a.gpu, train_root=a.train_root, eval_root=a.eval_root, smoke=False, owned_receipt=train_state))
                if rc != 75:
                    break
                state["queued_resource"] = {"step": step}
                state_path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
                time.sleep(600)
            if rc:
                state["invalid_eval"] = {"step": step, "returncode": rc}
                state_path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
                return rc
            reduced = reduce(argparse.Namespace(step=step, eval_root=a.eval_root / a.cell, cells=[a.cell]))
            if reduced:
                state["invalid_eval"] = {"step": step, "reducer_returncode": reduced}
                state_path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
                return reduced
        except RuntimeError as exc:
            state["invalid_eval"] = {"step": step, "reason": str(exc)}
            state_path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
            return 2
        state["completed"].append(step)
        state_path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    return 0


def submit(a: argparse.Namespace, kind: str) -> int:
    command = [str(PYTHON), str(Path(__file__).resolve()), kind, "--cell", a.cell, "--gpu", str(a.gpu), "--train-root", str(a.train_root), "--eval-root", str(a.eval_root)]
    if kind == "train" and a.smoke:
        command.append("--smoke")
    if kind == "watch":
        command.extend(["--attempt", str(a.attempt)])
    name = f"pull_v28_{kind}_{a.cell.lower()}_attempt{a.attempt}"
    output = a.train_root / f"{a.cell}__{kind}_attempt{a.attempt}.supervisor.log" if kind == "train" else a.eval_root / f"{a.cell}__{kind}_attempt{a.attempt}.supervisor.log"
    expected = 2400 if a.smoke else 151200 if kind == "train" else 172800
    prepared = subprocess.check_output([str(PYTHON), str(SUPERVISOR), "prepare", "--project-root", str(REPO), "--name", name, "--command", shlex.join(command), "--cwd", str(REPO), "--output", str(output), "--expected-seconds", str(expected), "--eta-source", "v28 plan historical 22s/batch; re-estimate after startup", "--stop-condition", "declared v28 budget or corresponding evaluator failure", "--resource", f"GPU{a.gpu}", "--config-ref", "gr00t/rl/config/ablation/wbmanip/pull_v28_common.yaml", "--checkpoint-lineage", "null scratch"], text=True)
    receipt = json.loads(prepared)["receipt"]
    subprocess.run([str(PYTHON), str(SUPERVISOR), "launch", "--receipt", receipt, "--backend", "tmux"], check=True)
    print(json.dumps({"receipt": receipt, "session": name}))
    return 0


def add_roots(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--train-root", type=Path, default=TRAIN_ROOT_DEFAULT)
    parser.add_argument("--eval-root", type=Path, default=EVAL_ROOT_DEFAULT)


def main() -> int:
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="action", required=True)
    for name, func in (("train", train), ("eval", evaluate), ("watch", watch)):
        x = sub.add_parser(name); x.set_defaults(func=func); x.add_argument("--cell", required=True, choices=CELLS if name == "watch" else (*CELLS, "G0")); x.add_argument("--gpu", type=int, required=True); add_roots(x)
        if name == "train": x.add_argument("--smoke", action="store_true")
        if name == "eval": x.add_argument("--step", type=int, required=True); x.add_argument("--smoke", action="store_true")
        if name == "watch": x.add_argument("--attempt", type=int, required=True)
    x = sub.add_parser("reduce"); x.set_defaults(func=reduce); x.add_argument("--step", type=int, required=True); x.add_argument("--cells", nargs="+", default=CELLS); x.add_argument("--eval-root", type=Path, default=EVAL_ROOT_DEFAULT)
    x = sub.add_parser("p2-reduce"); x.set_defaults(func=p2_reduce); x.add_argument("--step", type=int, required=True, choices=(9500, 10000, 10500)); x.add_argument("--cells", nargs="+", required=True); x.add_argument("--eval-root", type=Path, required=True); x.add_argument("--output", type=Path)
    for name in ("submit-train", "submit-watch"):
        x = sub.add_parser(name); x.set_defaults(func=lambda a, k="train" if name == "submit-train" else "watch": submit(a, k)); x.add_argument("--cell", required=True, choices=CELLS if name == "submit-watch" else (*CELLS, "G0")); x.add_argument("--gpu", type=int, required=True); x.add_argument("--attempt", type=int, default=1); add_roots(x)
        if name == "submit-train": x.add_argument("--smoke", action="store_true")
    a = p.parse_args()
    return a.func(a)


if __name__ == "__main__":
    raise SystemExit(main())
