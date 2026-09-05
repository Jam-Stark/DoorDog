"""Wait in an independent tmux session and execute registered milestone evals.

Main owns wave transitions and any failure repair. This worker only services
the already-launched wave, writes event files, and sleeps ten minutes between
checks. It does not select checkpoints, change contracts, or relaunch cells.
"""
from __future__ import annotations

import argparse
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

from v27_contract import ROOT, HERE, RUNTIME, EVAL, PYTHON, cells, read_json, write_json, train_checkpoint

WAIT_SECONDS = 600


def event(name, value):
    path = RUNTIME / "events" / f"{name}.json"
    if not path.exists():
        value = {"created_at":datetime.now(timezone.utc).isoformat(), **value}
        write_json(path,value)
        print(f"EVENT {name}: {value}",flush=True)


def run_command(command):
    return subprocess.run(["bash",str(HERE / "v27_orchestrate.sh"),*command],cwd=ROOT).returncode


def eval_busy():
    return any(not (receipt.parent / "exit_code.txt").exists()
               for receipt in (ROOT / ".ai/runtime/runs").glob("v27_eval_*/RUN_RECEIPT.json"))


def training_states(wave):
    pending = False
    active = {}
    for cell,spec in cells(wave).items():
        output = train_checkpoint(cell,spec["batches"]).parent
        process_path = output / "v27_process_evidence.json"
        if not process_path.exists():
            pending = True
            continue
        process = read_json(process_path)
        stop_path = RUNTIME / "cell_states" / f"{cell}.json"
        if process["state"] == "FAIL" and not stop_path.exists():
            before_policy = not any(process.get(key,False) for key in ("policy_readout_observed","policy_execution_started"))
            state = {"status":"PRE_POLICY_REPAIR_PENDING" if before_policy else "STOPPED",
                     "process_evidence":str(process_path),"wave":wave}
            write_json(stop_path,state)
            event(f"{wave.lower()}_{cell}_train_failed",state)
        if stop_path.exists():
            state = read_json(stop_path)["status"]
            if state == "PRE_POLICY_REPAIR_PENDING": pending = True
            if state != "REPAIRED": continue
        active[cell] = process
    return active,pending


def checkpoint_ready(cell,step,process):
    path = train_checkpoint(cell,step)
    # A later iteration proves the synchronous prior checkpoint save returned.
    # The final iteration instead uses the successful process/checkpoint receipt.
    return path.is_file() and (process.get("last_iteration",0) > step or process["state"] == "PASS")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--wave",choices=("A","B","C"),required=True)
    args = parser.parse_args()
    specs = cells(args.wave)
    jobs = sorted({(step,"R" if spec["arm"].startswith("R") else "L" if spec["arm"].startswith("L") else "all")
                   for spec in specs.values() for step in spec["milestones"]})
    complete = set()
    while len(complete) < len(jobs):
        active,pending = training_states(args.wave)
        if pending:
            time.sleep(WAIT_SECONDS)
            continue
        for step,family in jobs:
            job = (step,family)
            if job in complete: continue
            scope = [cell for cell in active if step in specs[cell]["milestones"]
                     and (family == "all" or specs[cell]["arm"].startswith(family))]
            suffix = f"wave_{args.wave.lower()}" + (f"_{family.lower()}" if args.wave == "B" else "")
            manifest = RUNTIME / "eval_manifests" / suffix / f"step{step}.json"
            reducer = EVAL / suffix / f"step{step}" / "reducer.json"
            if reducer.exists():
                event(f"{suffix}_step{step}_ready",{"kind":"MILESTONE_REDUCED","reducer":str(reducer),"manifest":str(manifest)})
                complete.add(job)
                continue
            if not scope:
                event(f"{suffix}_step{step}_not_run",{"kind":"NOT_RUN","reason":"NO_ACTIVE_CELLS"})
                complete.add(job)
                continue
            receipts_file = manifest.with_name(f"{manifest.stem}_receipts.json")
            if receipts_file.exists():
                receipts = list(read_json(receipts_file).values())
                if all((Path(path).parent / "exit_code.txt").exists() for path in receipts):
                    rc = run_command(["eval-finalize","--manifest",str(manifest)])
                    if reducer.exists():
                        event(f"{suffix}_step{step}_ready",{"kind":"MILESTONE_REDUCED","reducer":str(reducer),"manifest":str(manifest),"returncode":rc})
                        complete.add(job)
                    else:
                        event(f"{suffix}_step{step}_reducer_failed",{"kind":"HARNESS_ATTENTION_REQUIRED","manifest":str(manifest),"returncode":rc})
                break
            if manifest.exists():
                event(f"{suffix}_step{step}_launch_incomplete",{"kind":"HARNESS_ATTENTION_REQUIRED","manifest":str(manifest)})
                break
            if eval_busy() or not all(checkpoint_ready(cell,step,active[cell]) for cell in scope):
                break
            event(f"{suffix}_step{step}_checkpoints_ready",{"kind":"CHECKPOINTS_READY","cells":scope,"step":step})
            rc = run_command(["milestone-launch","--wave",args.wave,"--step",str(step),"--family",family])
            if rc:
                event(f"{suffix}_step{step}_launch_failed",{"kind":"HARNESS_ATTENTION_REQUIRED","returncode":rc})
            break
        if len(complete) < len(jobs): time.sleep(WAIT_SECONDS)
    write_json(RUNTIME / f"wave_{args.wave.lower()}_watch_done.json",{"status":"WATCH_COMPLETE","jobs":[list(job) for job in sorted(complete)]})


if __name__ == "__main__":
    main()
