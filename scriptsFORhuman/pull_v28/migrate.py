#!/usr/bin/env python3
"""Prepare the stopped 2048-env pull experiment on a new machine; opt in to resume.

Authentication: predownload archives, an existing rclone remote, or the
GOOGLE_DRIVE_ACCESS_TOKEN environment variable. No credential is persisted.
"""
from __future__ import annotations
import argparse
import json
import os
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

GIT_URL = "git@github.com:Jam-Stark/DoorDog.git"
BRANCH = "codex/a2-piper-pull-v0-20260803"
OLD_REPO = "/home/baoquanc/workspace/DoorDog-A2_Piper_pull_v0"
STEPS = {"PA_S1":1050, "PA_S2":1400, "PA_S3":1450}
ATTEMPT = 3
SOURCE = "logs_rl/a2_piper_pull_v26_8_backbone/pull_v26_8_backbone_20260905_natural1_r2/wave2/train/P_S2/resolved_config.yaml"


def require(value, message):
    if not value:
        raise RuntimeError(message)


def run(command, cwd=None):
    subprocess.run([str(part) for part in command], cwd=cwd, check=True)


def download(entry, destination, manifest, remote):
    if destination.is_file():
        require(destination.stat().st_size == entry["bytes"], f"archive size differs: {destination}")
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    if entry.get("parts"):
        partial = destination.with_suffix(destination.suffix + ".partial")
        with partial.open("wb") as output:
            for part in entry["parts"]:
                piece = destination.parent / part["name"]
                download(part, piece, manifest, remote)
                with piece.open("rb") as source:
                    shutil.copyfileobj(source, output, length=8 * 1024 * 1024)
        require(partial.stat().st_size == entry["bytes"], f"incomplete archive: {partial}")
        partial.rename(destination)
        return
    partial = destination.with_suffix(destination.suffix + ".partial")
    if remote:
        command = ["rclone", "copyto"]
        if entry.get("rclone_path"):
            command += [remote.rstrip("/") + "/" + entry["rclone_path"], str(partial)]
        else:
            command += [remote.rstrip("/") + "/" + entry["name"], str(partial),
                        "--drive-root-folder-id", manifest["drive_folder_id"]]
        run(command)
    else:
        token = os.environ["GOOGLE_DRIVE_ACCESS_TOKEN"]
        request = urllib.request.Request(
            f"https://www.googleapis.com/drive/v3/files/{entry['drive_file_id']}?alt=media&supportsAllDrives=true",
            headers={"Authorization": "Bearer " + token})
        with urllib.request.urlopen(request) as response, partial.open("wb") as output:
            shutil.copyfileobj(response, output, length=8 * 1024 * 1024)
    require(partial.stat().st_size == entry["bytes"], f"incomplete archive: {partial}")
    partial.rename(destination)


def relocate_yaml(repo, members, manifest):
    # Text replacement preserves existing OmegaConf interpolations and YAML aliases.
    replacements = {OLD_REPO: str(repo)}
    for old, relative_target in manifest.get("path_rewrites", {}).items():
        replacements[old] = str(repo / relative_target)
    active_prefixes = (manifest["train_root"].rstrip("/") + "/", manifest["eval_root"].rstrip("/") + "/", "gr00t/rl/")
    candidates = {repo / member for member in members
                  if member.endswith((".yaml", ".yml"))
                  and (member.removeprefix("./").startswith(active_prefixes)
                       or member.removeprefix("./") == SOURCE)}
    candidates.update((repo / "gr00t/rl/config").rglob("*.yaml"))
    changed = []
    for path in sorted(candidates):
        original = path.read_text()
        text = original
        for old, new in sorted(replacements.items(), key=lambda pair: -len(pair[0])):
            text = text.replace(old, new)
        if text != original:
            path.write_text(text)
            changed.append(str(path.relative_to(repo)))
    return changed


def prepare(args, manifest):
    import yaml
    repo = args.repo
    if not (repo / ".git").exists():
        run(["env", "GIT_LFS_SKIP_SMUDGE=1", "git", "clone", "--branch", BRANCH, GIT_URL, repo])
    else:
        run(["env", "GIT_LFS_SKIP_SMUDGE=1", "git", "switch", BRANCH], cwd=repo)
        run(["env", "GIT_LFS_SKIP_SMUDGE=1", "git", "pull", "--ff-only", "origin", BRANCH], cwd=repo)
    members = []
    for entry in manifest["archives"]:
        if entry.get("role", "resume") == "history" and not args.include_history:
            continue
        archive = args.archive_dir / entry["name"]
        download(entry, archive, manifest, args.rclone_remote)
        listing = subprocess.check_output(["tar", "--zstd", "-tf", str(archive)], text=True)
        members.extend(listing.splitlines())
        run(["tar", "--zstd", "-xf", archive, "-C", repo])
    changed = relocate_yaml(repo, members, manifest)
    train = repo / manifest["train_root"]
    evaluation = repo / manifest["eval_root"]
    require((repo / SOURCE).is_file(), "archive must restore the original P_S2 resolved config")
    require((repo / "gr00t/rl/data/policies/A2_Base/policy.pt").is_file(), "archive must restore frozen A2_Base policy")
    require((repo / "gr00t/rl/data/policies/A2_Base/policy_metadata.json").is_file(), "A2_Base metadata missing")
    require(set(manifest["checkpoints"]) == set(STEPS), "manifest must name exactly PA_S1/2/3")
    checkpoints = {}
    archived = []
    # runner.py uses exclusive-create for these files; preserve old attempt data.
    for cell, step in STEPS.items():
        item = manifest["checkpoints"][cell]
        require(item["step"] == step, f"{cell}: expected current full checkpoint step {step}")
        checkpoint = repo / item["path"]
        require(checkpoint.is_file(), f"missing current checkpoint: {checkpoint}")
        output = train / cell
        require(checkpoint.parent == output, f"{cell}: checkpoint must remain adjacent to its config")
        config = yaml.safe_load((output / "config.yaml").read_text())
        require(config["seed"] == int(cell[-1]), f"{cell}: seed changed")
        require(config["num_envs"] == config["env"]["config"]["num_envs"] == 2048, f"{cell}: current contract is2048env")
        require(config["algo"]["trl"]["num_total_batches"] == 6000, "target must remain6000")
        require(config["checkpoint_load_mode"] == "full" and config["auto_load_latest"] is False, "full explicit resume required")
        old_output = output / "history_before_migration_attempt3"
        for name in ("isaac.log", "gpu_memory.csv", "runtime_result.json"):
            path = output / name
            if path.exists():
                old_output.mkdir(exist_ok=True)
                path.rename(old_output / name)
                archived.append(str((old_output / name).relative_to(repo)))
        checkpoints[cell] = checkpoint
    # All prior MISSING_CHECKPOINT decisions/queue state stay together. The new
    # queue has fresh state and receipts and will fill the24 declared lanes.
    if evaluation.exists():
        old_eval = evaluation.with_name(evaluation.name + "_before_migration_attempt3")
        require(not old_eval.exists(), f"migration archive already exists: {old_eval}")
        evaluation.rename(old_eval)
        archived.append(str(old_eval.relative_to(repo)))
    evaluation.mkdir(parents=True)
    pipeline = repo / "scriptsFORhuman/pull_v28/pipeline.py"
    commands = [[sys.executable, str(pipeline), "submit-resume", "--cell", cell,
                 "--checkpoint", str(checkpoints[cell]), "--attempt", str(ATTEMPT),
                 "--train-root", str(train), "--eval-root", str(evaluation)] for cell in STEPS]
    commands.append([sys.executable, str(pipeline), "submit-eval-queue", "--attempt", str(ATTEMPT),
                     "--train-root", str(train), "--eval-root", str(evaluation)])
    return {"schema":"pull_v28_migration_prepared_v1", "status":"PREPARED_NOT_STARTED",
            "repo":str(repo), "manifest":str(args.manifest), "git_branch":BRANCH,
            "checkpoints":{cell:str(path) for cell,path in checkpoints.items()},
            "start_steps":STEPS, "target_step":6000, "num_envs":2048, "attempt":ATTEMPT,
            "gpu_assignment":{"PA_S1":1,"PA_S2":2,"PA_S3":3,"evaluation":0},
            "rewritten_yaml":changed, "archived":archived, "commands":commands,
            "scope":"resume same-seed full checkpoints and24milestone lanes; do not rerun P2/G0"}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo",type=Path,required=True)
    parser.add_argument("--manifest",type=Path,required=True)
    parser.add_argument("--archive-dir",type=Path,required=True,
                        help="directory of predownloaded archives, or where authenticated downloads will be saved")
    parser.add_argument("--rclone-remote",help="existing rclone Drive remote, e.g.gdrive:; otherwise use GOOGLE_DRIVE_ACCESS_TOKEN")
    parser.add_argument("--include-history",action="store_true")
    parser.add_argument("--resume",action="store_true",help="explicitly start three resumed tasks plus GPU0 evaluation queue")
    args=parser.parse_args()
    args.repo=args.repo.expanduser().resolve()
    args.manifest=args.manifest.expanduser().resolve()
    args.archive_dir=args.archive_dir.expanduser().resolve()
    manifest=json.loads(args.manifest.read_text())
    require(manifest["schema"] == "pull_v28_migration_v1", "unsupported migration manifest")
    receipt=args.repo/".ai/runtime/migrations/pull_v28_2048_attempt3/prepare.json"
    if receipt.exists():
        prepared=json.loads(receipt.read_text())
        require(prepared["status"] == "PREPARED_NOT_STARTED", "migration has already submitted its commands")
    else:
        prepared=prepare(args,manifest)
        receipt.parent.mkdir(parents=True,exist_ok=True)
        receipt.write_text(json.dumps(prepared,indent=2)+"\n")
    if args.resume:
        # Use the activated destination Python, including when --resume follows a
        # previous prepare invocation from another shell.
        for command in prepared["commands"]:
            command[0]=sys.executable
            run(command,cwd=args.repo)
        prepared["status"]="RESUME_SUBMITTED"
        receipt.write_text(json.dumps(prepared,indent=2)+"\n")
    print(json.dumps({"status":prepared["status"],"receipt":str(receipt),"resume_requested":args.resume}),flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
