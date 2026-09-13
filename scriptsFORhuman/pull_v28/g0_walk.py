"""Run the frozen D37 matched old/MERGED comparison on m5, three postures."""
from __future__ import annotations
import argparse
import concurrent.futures
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
PYTHON = "/home/baoquanc/anaconda3/envs/isaaclab/bin/python"
REFERENCE = ROOT / "scriptsFORhuman/pull_v28/mainline_reference/20260913"
HARNESS = REFERENCE / "files/gr00t/rl/scripts/smoke_a2_base_flat_walk.py"
GATE = REFERENCE / "files/scriptsFORhuman/v28/v28_g0_walk_gate.py"
INPUTS = REFERENCE / "supplement_pg7"
RUNNER = ROOT / "scriptsFORhuman/pull_v26_8/runner.py"

def run_posture(posture, gpu, output):
    angles = json.loads((INPUTS / "postures.json").read_text())["postures"][posture]
    env = dict(os.environ, CUDA_VISIBLE_DEVICES=str(gpu), CUDA_DEVICE_ORDER="PCI_BUS_ID",
               ACCELERATE_TORCH_DEVICE="cuda:0", PYTHONPATH=str(ROOT), PYTHONUNBUFFERED="1",
               OMP_NUM_THREADS="8", WANDB_MODE="disabled")
    env.pop("DISPLAY", None)
    env.pop("XAUTHORITY", None)
    assets = {"baseline": "A2_Piper", "merged": "a2_piper_v28_merged_20260909"}
    for label, asset in assets.items():
        dest = output / posture / label
        dest.mkdir(parents=True, exist_ok=False)
        command = [PYTHON, "-B", str(HARNESS), "--headless", "--device", "cuda:0",
                   "--num-envs", "64", "--usd-file",
                   str(ROOT / "gr00t/rl/data/robots" / asset / "a2_piper.usd"),
                   "--policy-path", str(ROOT / "gr00t/rl/data/policies/A2_Base/policy.pt"),
                   "--metadata-path", str(ROOT / "gr00t/rl/data/policies/A2_Base/policy_metadata.json"),
                   "--arm-posture", *map(str, angles),
                   "--command-script", str(INPUTS / "commands.json"),
                   "--metrics-json", str(dest / "metrics.json"), "--seed", "281", "--log-interval", "0"]
        with (dest / "launcher.log").open("x") as log:
            result = subprocess.run([PYTHON, str(RUNNER), "--output", str(dest), "--gpu", str(gpu),
                                     "--required", "metrics.json", "--", *command],
                                    cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT)
        if result.returncode:
            return {"posture": posture, "status": "PROCESS_FAILED", "asset": label,
                    "returncode": result.returncode, "runtime": str(dest / "runtime_result.json")}
    comparison = output / posture / "comparison.json"
    result = subprocess.run([PYTHON, str(GATE), "--baseline", str(output/posture/"baseline/metrics.json"),
                             "--candidate", str(output/posture/"merged/metrics.json"),
                             "--command-script", str(INPUTS/"commands.json"),
                             "--harness", str(HARNESS), "--output", str(comparison)],
                            cwd=ROOT, text=True, capture_output=True)
    if result.returncode not in (0, 2):
        raise RuntimeError(result.stderr)
    payload = json.loads(comparison.read_text())
    return {"posture": posture, "status": payload["status"], "comparison": str(comparison),
            "tracking_failures": payload["tracking_failures"], "vx050_slope": payload["vx050_slope"]}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    # Main allocates GPU1-3 exclusively before launch; do not use GPU0.
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        futures = [pool.submit(run_posture, posture, gpu, output)
                   for posture, gpu in zip(("default", "hold", "stage2"), (1, 2, 3))]
        rows = [f.result() for f in futures]
    status = "PASS" if all(row["status"] == "PASS" for row in rows) else (
        "FAIL" if any(row["status"] == "FAIL" for row in rows) else "PROCESS_FAILED")
    result = {"schema": "pull_v28_pg7_v1", "status": status, "criterion": "D37",
              "host": "m5", "results": rows, "seed": 281,
              "scope": "m5 matched deterministic engineering comparison; no stochastic calibration",
              "X24": "OPEN_NO_STOCHASTIC_CALIBRATION",
              "owner_gate": status == "FAIL"}
    (output / "PG7_DECISION.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"status": status, "decision": str(output / "PG7_DECISION.json")}), flush=True)
    return 0 if status == "PASS" else 2

if __name__ == "__main__":
    sys.exit(main())
