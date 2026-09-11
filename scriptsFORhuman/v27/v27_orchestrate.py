"""v27 tmux/receipt entrypoint. Wave transitions remain explicit Main actions."""
from __future__ import annotations

import argparse
import os
import signal
import shlex
import subprocess
import sys
from pathlib import Path

from v27_contract import (ROOT, HERE, RUNTIME, TRAIN, EVAL, PYTHON, RUN_ID, PROXY_KEYS,
                         SEEDS, SIDES, cells, digest, input_checkpoint, train_checkpoint,
                         read_json, require, write_json, stratum_overlay)

from v27_run_cell import SMOKE_BATCHES

SUPERVISOR = ROOT / ".ai/scripts/run_supervisor.py"


def source_check():
    lock = read_json(read_json(RUNTIME / "active_source_lock.json")["path"])
    differences = [name for name, value in lock["source_text"].items()
                   if ((Path(lock["eval_source_root"]) if name.startswith("gr00t/") else ROOT) / name).read_text() != value]
    require(not differences, f"source changed after freeze: {differences}")


def launch(name, gpu, command, expected):
    # Existing asset checker is read-only except its explicit new v27 output.
    asset = RUNTIME / "p0_assets" / f"{name}.json"
    subprocess.run([PYTHON, str(ROOT / "scriptsFORhuman/v26_8/v26_8_p0_assets.py"), "--output", str(asset)],
                   cwd=ROOT, check=True, stdout=subprocess.DEVNULL)
    prefix = ["env", *[f"{key}={os.environ.get(key, '')}" for key in PROXY_KEYS]]
    name = f"v27_{name}"
    receipt = ROOT / ".ai/runtime/runs" / name / "RUN_RECEIPT.json"
    subprocess.run([sys.executable, str(SUPERVISOR), "prepare", "--name", name, "--session", name,
                    "--cwd", str(ROOT), "--command", shlex.join([*prefix, *command]),
                    "--output", str(RUNTIME / "process_logs" / f"{name}.log"),
                    "--checkpoint", str(expected), "--resource", f"GPU{gpu}",
                    "--resource", f"IsaacSim_GPU{gpu}"], cwd=ROOT, check=True)
    subprocess.run([sys.executable, str(SUPERVISOR), "launch", "--receipt", str(receipt)], cwd=ROOT, check=True)
    return str(receipt)


def train_launch(wave):
    source_check()
    require(read_json(RUNTIME / "g0_gate.json")["status"] == "G0_PASS", "G0 not passed")
    require(read_json(RUNTIME / f"wave_{wave.lower()}_contract.json")["status"] == "STATIC_PASS", "wave config not frozen")
    declaration = {"wave": wave, "run_id": RUN_ID, "receipts": {}}
    for cell,spec in cells(wave).items():
        output = TRAIN / cell
        command = ["bash", str(HERE / "v27_train_cell.sh"), "--gpu", str(spec["gpu"]),
                   "--cell", cell, "--output", str(output)]
        declaration["receipts"][cell] = launch(f"train_{cell.lower()}", spec["gpu"], command,
                                               output / f"model_step_{spec['batches']:06d}.pt")
        write_json(RUNTIME / f"wave_{wave.lower()}_launch.json", declaration, replace=True)


def smoke_launch(wave):
    source_check()
    cell = {"A": "Q2_S21", "B": "R2_S41", "C": "SK_S211"}[wave]
    spec = cells(wave)[cell]
    output = TRAIN.parent / "smoke" / f"wave_{wave.lower()}_{cell}"
    command = ["bash", str(HERE / "v27_train_cell.sh"), "--gpu", str(spec["gpu"]),
               "--cell", cell, "--output", str(output), "--smoke"]
    receipt = launch(f"smoke_{wave.lower()}", spec["gpu"], command, output / f"model_step_{SMOKE_BATCHES[wave]:06d}.pt")
    write_json(RUNTIME / f"smoke_{wave.lower()}_launch.json", {"receipt": receipt, "output": str(output), "cell": cell})


def stop_cell_training(cell, step):
    process_path = train_checkpoint(cell, step).parent / "v27_process_evidence.json"
    if process_path.is_file():
        process = read_json(process_path)
        if process["state"] == "RUNNING":
            os.kill(process["pid"], signal.SIGINT)


def eval_finalize(manifest_path):
    manifest = read_json(manifest_path)
    receipts = read_json(Path(manifest_path).with_name(f"{Path(manifest_path).stem}_receipts.json"))
    for path in receipts.values():
        require((Path(path).parent / "exit_code.txt").exists(), "eval queue still running")
        subprocess.run([sys.executable, str(SUPERVISOR), "finalize", "--receipt", path], cwd=ROOT, check=False)
    output = EVAL / manifest["name"] / "reducer.json"
    result = subprocess.run([PYTHON, str(HERE / "v27_reduce.py"), "--manifest", str(manifest_path),
                            "--expected-n", str(manifest["episodes"]), "--output", str(output)], cwd=ROOT)
    require(result.returncode in (0, 2) and output.is_file(), "reducer failed before typed artifact")
    reduced = read_json(output)
    for cell in reduced["invalid_cells"]:
        stop_cell_training(cell, manifest["step"])
    return result.returncode


def eval_manifest(name, checkpoint_cells, strata, episodes, seed, *, recovery=False, extra_overrides=None, step=0, endpoint=False, wave_c_history=None):
    manifest = {"schema": "a2_piper_base_v27_eval_manifest_v1", "name": name,
                "step": step, "endpoint": endpoint, "episodes": episodes, "lanes": []}
    if wave_c_history is not None:
        manifest["wave_c_history"] = wave_c_history
    for cell,checkpoint in checkpoint_cells.items():
        for stratum in strata:
            for side in SIDES:
                output = EVAL / name / cell / stratum / side
                overrides = {} if stratum in ("DEV","CONF","final") else stratum_overlay(stratum)
                if extra_overrides:
                    overrides.update(extra_overrides)
                # All formal evaluation disables training perturbation and bank sampling.
                overrides.update({"env.config.a2_v27_recovery_enabled": False,
                                  "env.config.a2_v27_recovery_loss_steps": 10,
                                  "env.config.a2_v27_recovery_window_steps": 300,
                                  "env.config.a2_v27_recovery_eval_mode": "nominal",
                                  "env.config.a2_v27_perturb_prob": 0.0,
                                  "env.config.a2_v27_perturb_steps": 6,
                                  "env.config.a2_v27_recovery_bank_reset_share": 0.0,
                                  "env.config.a2_v27_friction_bucket_enabled": False})
                if recovery:
                    overrides.update({"env.config.a2_v27_recovery_enabled": not cell.startswith("R0"),
                        "env.config.a2_v27_recovery_eval_mode": stratum})
                manifest["lanes"].append({"cell": cell, "stratum": stratum, "side": side,
                    "seed": seed, "episodes": episodes, "checkpoint": str(checkpoint), "artifact_path": str(output),
                    "overrides": overrides, "expected_contract": overrides,
                    "recovery_itt": recovery and stratum == "injected"})
    path = RUNTIME / "eval_manifests" / f"{name}.json"
    write_json(path, manifest)
    return path


def eval_launch(manifest_path):
    source_check()
    manifest = read_json(manifest_path)
    queues = {gpu: [] for gpu in (6, 7)}
    # Assign ready lanes across the allocated GPUs, one process per GPU.
    for index,lane in enumerate(manifest["lanes"]):
        require(Path(lane["checkpoint"]).is_file(), f"missing endpoint: {lane['checkpoint']}")
        queues[list(queues)[index % len(queues)]].append(index)
    receipts = {}
    for gpu,indices in queues.items():
        if not indices: continue
        result_path = Path(manifest_path).with_name(f"{Path(manifest_path).stem}_gpu{gpu}_result.json")
        receipts[str(gpu)] = launch(f"eval_{manifest['name'].replace('/', '_').lower()}_gpu{gpu}", gpu,
            ["bash", str(HERE / "v27_eval_lane.sh"), "--gpu", str(gpu), "--manifest", str(manifest_path),
             "--indices", *map(str,indices)], result_path)
    write_json(Path(manifest_path).with_name(f"{Path(manifest_path).stem}_receipts.json"), receipts)


def lane_run(args):
    manifest = read_json(args.manifest)
    results = []
    for index in args.indices:
        lane = manifest["lanes"][index]
        stop_file = RUNTIME / "cell_states" / f"{lane['cell']}.json"
        if stop_file.exists() and read_json(stop_file)["status"] in ("STOPPED", "PRE_POLICY_REPAIR_PENDING"):
            results.append({"index":index,"cell":lane["cell"],"stratum":lane["stratum"],"side":lane["side"],
                            "returncode":1,"status":"NOT_RUN_CELL_STOPPED","artifact_path":lane["artifact_path"]})
            continue
        command = ["bash", str(HERE / "v27_eval_cell.sh"), "--gpu", str(args.gpu),
                   "--manifest", str(args.manifest), "--lane", str(index)]
        rc = subprocess.run(command, cwd=ROOT).returncode
        results.append({"index": index, "cell": lane["cell"], "stratum": lane["stratum"],
                        "side": lane["side"], "returncode": rc, "artifact_path": lane["artifact_path"]})
        if rc:
            evidence_path = Path(lane["artifact_path"]) / "v27_process_evidence.json"
            before_policy = evidence_path.is_file() and not any(read_json(evidence_path).get(key,False)
                for key in ("policy_readout_observed","policy_execution_started"))
            write_json(stop_file,{"status":"PRE_POLICY_REPAIR_PENDING" if before_policy else "STOPPED",
                       "failed_lane":lane,"process_evidence":str(evidence_path)},replace=True)
            if not before_policy:
                stop_cell_training(lane["cell"], manifest["step"])
        # A failed lane never discards another cell's authorized evaluation.
    path = args.manifest.with_name(f"{args.manifest.stem}_gpu{args.gpu}_result.json")
    write_json(path, {"status": "PASS" if all(row["returncode"] == 0 for row in results) else "FAIL",
                      "lanes": results})
    return 0 if all(row["returncode"] == 0 for row in results) else 1


def milestone(wave, step, family):
    selected = {cell: spec for cell,spec in cells(wave).items()
                if step in spec["milestones"] and (family == "all" or spec["arm"].startswith(family))}
    selected = {cell:spec for cell,spec in selected.items()
                if not (RUNTIME / "cell_states" / f"{cell}.json").exists()
                or read_json(RUNTIME / "cell_states" / f"{cell}.json")["status"] == "REPAIRED"}
    require(selected, "no cells at requested milestone")
    if wave == "B": require(family in ("L","R"), "Wave B L and R have separate endpoints")
    if wave == "B" and family == "L": strata = ["nominal", "P02", "P05"]
    elif wave == "B": strata = ["nominal", "injected", "sham"]
    elif wave == "C" and read_json(RUNTIME / "wave_b_decision.json")["RECIPE_B"] != "current":
        strata = ["nominal", "P02", "P05"]
    else: strata = ["nominal"]
    path = eval_manifest(f"wave_{wave.lower()}{'_'+family.lower() if wave == 'B' else ''}/step{step}",
        {cell: train_checkpoint(cell,step) for cell in selected}, strata, 64, SEEDS["DEV"],
        recovery=wave == "B" and family == "R", step=step,
        endpoint=all(step == spec["batches"] for spec in selected.values()),
        wave_c_history=[read_json(EVAL / "wave_c" / f"step{earlier}" / "reducer.json")
                        for earlier in (1000,2000,3000,4000,5000,6000) if earlier < step] if wave == "C" else None)
    eval_launch(path)


def status():
    result = {"runs": {}, "gpu": subprocess.check_output(["nvidia-smi",
              "--query-gpu=index,memory.used,memory.total,utilization.gpu", "--format=csv,noheader"], text=True).splitlines()}
    for receipt in sorted((ROOT / ".ai/runtime/runs").glob("v27_*/RUN_RECEIPT.json")):
        record = read_json(receipt)
        exit_file = receipt.parent / "exit_code.txt"
        result["runs"][record["name"]] = {"state": record["state"], "resources": record["resources"],
                                 "returncode": int(exit_file.read_text()) if exit_file.exists() else None}
    print(__import__("json").dumps(result, ensure_ascii=False, indent=2))


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("train-launch"); p.add_argument("--wave", required=True, choices=("A","B","C"))
    p = sub.add_parser("smoke-launch"); p.add_argument("--wave", required=True, choices=("A","B","C"))
    sub.add_parser("q0-dev-launch")
    sub.add_parser("q0-render-launch")
    p = sub.add_parser("q0-conf-launch"); p.add_argument("--candidate", required=True, choices=("C_S2","W_S2","K_S2"))
    p = sub.add_parser("eval-launch"); p.add_argument("--manifest", type=Path, required=True)
    p = sub.add_parser("eval-finalize"); p.add_argument("--manifest", type=Path, required=True)
    p = sub.add_parser("milestone-launch"); p.add_argument("--wave", required=True, choices=("A","B","C")); p.add_argument("--step", type=int, required=True); p.add_argument("--family", default="all", choices=("all","L","R"))
    p = sub.add_parser("lane"); p.add_argument("--gpu", type=int, required=True); p.add_argument("--manifest", type=Path, required=True); p.add_argument("--indices", type=int, nargs="+", required=True)
    sub.add_parser("status")
    args = parser.parse_args()
    if args.command == "train-launch": train_launch(args.wave)
    elif args.command == "smoke-launch": smoke_launch(args.wave)
    elif args.command == "q0-dev-launch": eval_launch(eval_manifest("q0_dev", {cell:input_checkpoint(cell) for cell in ("C_S2","W_S2","K_S2")}, ["DEV"],128,SEEDS["DEV"],endpoint=True))
    elif args.command == "q0-render-launch": eval_launch(eval_manifest("q0_render", {cell:input_checkpoint(cell) for cell in ("C_S2","W_S2","K_S2")}, ["DEV"],3,SEEDS["DEV"],extra_overrides={"simulator.config.render_results":True}))
    elif args.command == "q0-conf-launch": eval_launch(eval_manifest("q0_conf", {args.candidate:input_checkpoint(args.candidate)}, ["CONF"],128,SEEDS["CONF"],endpoint=True))
    elif args.command == "eval-launch": eval_launch(args.manifest)
    elif args.command == "eval-finalize": return eval_finalize(args.manifest)
    elif args.command == "milestone-launch": milestone(args.wave, args.step, args.family)
    elif args.command == "lane": return lane_run(args)
    else: status()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
