# Restore the stopped pull v28 run

This restores the current 2048-environment experiment only: PA_S1/2/3 resume full checkpoints at 1050/1400/1450 to 6000, with original seeds and PPO configuration. Attempt 3 trains on GPU 1/2/3; GPU 0 fills the 24 natural evaluation lanes at 1500/3000/4500/6000. P2 and G0 are not rerun. New-machine IsaacLab, CUDA, GPU memory and simulation compatibility have not been verified.

The destination needs Linux, Git with SSH access to git@github.com:Jam-Stark/DoorDog.git, Git LFS, tar with zstd support, tmux, and the project IsaacLab/PyTorch/CUDA environment with PyYAML and existing project dependencies installed. Activate that Python environment first: the pipeline uses sys.executable. Four suitable visible NVIDIA GPUs numbered 0–3 are required for resume. The script pulls branch codex/a2-piper-pull-v0-20260803. It does not fetch all LFS history. Before resume, fetch only the MERGED robot and runtime assets referenced by the restored config with git lfs pull --include=<required paths>; the destination AI must resolve these paths from that config and the manifest. The resume archive also restores the frozen A2_Base policy and metadata, original P_S2 config, current checkpoints/configs, logs and runtime evidence.

Copy migrate.py and the supplied migration manifest outside the destination repository before starting. Obtain archives or all their numbered parts from the manifest Drive file IDs (https://drive.google.com/file/d/FILE_ID/view). Predownloaded archives/parts need no Drive credential or rclone installation:

```sh
python /path/to/migrate.py --repo /new/workspace/DoorDog --manifest /path/to/manifest.json --archive-dir /path/to/downloads
```

If a file is missing locally, either add --rclone-remote gdrive: for an already configured rclone Drive remote, or set GOOGLE_DRIVE_ACCESS_TOKEN in the environment to a valid Drive read access token. The token route downloads through the authenticated Drive v3 files endpoint; credentials are never written by the script. rclone is needed only when that option is used. Default extraction includes role resume; add --include-history to restore old P2/1024/4096 evidence. A complete archive takes precedence; otherwise numbered parts are downloaded/read in manifest order and concatenated. Size is checked without hashes.

Prepare clones or pulls the repository, extracts relative archive paths, rewrites old repository/SSD prefixes in restored YAML (including checkpoint-adjacent evaluation configs), and preserves the entire old evaluation directory as a sibling ending _before_migration_attempt3. Previous runner output files move into each cell's history_before_migration_attempt3. It writes .ai/runtime/migrations/pull_v28_2048_attempt3/prepare.json with the exact four commands. It does not launch training or evaluation.

Inspect that receipt and the destination environment, then use the same command with --resume to submit the three continuation tasks and fresh evaluation queue:

```sh
python /path/to/migrate.py --repo /new/workspace/DoorDog --manifest /path/to/manifest.json --archive-dir /path/to/downloads --resume
```

Manifest schema: pull_v28_migration_v1. Archives have name, bytes, role, and either drive_file_id or ordered parts entries with name/drive_file_id/bytes. drive_folder_id is used by rclone. train_root, eval_root, and checkpoints.PA_S*.path are repository-relative; each checkpoint entry has its explicit step. Optional path_rewrites maps old absolute prefixes to new repository-relative prefixes. The original repository root is replaced automatically.


Fetch the verified MERGED robot selectively after prepare (then fetch any additional runtime dependency referenced by the restored config):

```sh
git -C /new/workspace/DoorDog lfs pull --include='gr00t/rl/data/robots/a2_piper_v28_merged_20260909/**' --exclude=''
```

The restored config asset_root points into robots. A2_Base policy and metadata are supplied in resume_core. See NEW_MACHINE_AI_PROMPT_20260915.md for the complete Chinese handoff.
