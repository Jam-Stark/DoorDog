<!-- managed-by: jam-coding-role; file: ARTIFACT_HANDOFF.md -->
# Explicit stage artifact handoff and Pro_Space

This facility is disabled for ordinary task closure.

## Trigger

Use it only when one of the following is true:

- Owner explicitly asks for a bundle/upload;
- the approved stage plan declares `artifact_handoff = true`;
- a selected cloud/local planner workflow requires untracked evaluation artifacts.

Do not package artifacts merely because a coding task、smoke、review or training command finished.

## Selection safety

- Select only configured allowlist paths; never archive the entire untracked tree.
- Exclude credentials、tokens、private keys、environment files、cache and unrelated worktree outputs.
- Checkpoints are opt-in.
- Enforce per-file and bundle size limits.
- Record missing and excluded artifacts honestly.

## Namespace

```text
Bundle directory:
<project>__<worktree>__<stage>__<YYYYMMDD-HHMMSS-HKT>__<sha>__artifacts/

Semantic ZIPs:
source_and_configs.zip
logs_and_metrics.zip
plots_and_evidence.zip
checkpoints_part01.zip

Drive:
Pro_Space/<project>/<worktree>/<stage>/<timestamp>__<sha>/
```

Each ZIP is a standard archive that can be opened independently and includes `BUNDLE_MANIFEST.json`、`PRO_HANDOFF.md` and its own artifact subset. The bundle directory includes a plain-text `BUNDLE_INDEX.md` describing every ZIP、its contents、order and purpose. No SHA256 manifest is created.

## ZIP size and splitting

- Each ZIP must be at most **95 MiB**. Do not target the connector's exact 100 MiB ceiling.
- Split oversized bundles by semantic content first: source/config、logs/metrics、plots/evidence and checkpoints.
- When one semantic group still exceeds the limit, create numbered independent archives such as `logs_and_metrics_part01.zip` or `checkpoints_part01.zip`.
- Do not create `.z01/.z02/.zip` split archives. Pro/cloud tools must be able to open every ZIP without downloading and reassembling other parts.
- A single artifact larger than the ZIP payload limit is excluded with an explicit reason. For checkpoints, remove non-essential models or use an explicitly approved `rclone` exception; never cut a checkpoint binary into unusable fragments.

## Standing authorization

Owner has approved `Pro_Space` folder ID `1JWQrkkOrItsKlFUjfxsadUrOcXChGpOf` as a public-writer, create-only stage-artifact target.

Authorized: create a unique release namespace、upload a filtered bundle、write an upload receipt.

Not authorized: overwrite/delete/move existing cloud files、edit another task's artifacts、upload an unfiltered tree or credentials.

## Capability routing

Use the first verified path: connected Drive upload tool -> reliable browser/computer-use -> existing authenticated rclone/API -> otherwise create the bundle and report `NOT_UPLOADED`.

Public editor permission is not anonymous API authentication.

## Command boundary

`pack` and `upload` require an explicit `--confirm-stage-handoff` flag. Large ZIP/upload work does not run in SessionEnd hooks.
