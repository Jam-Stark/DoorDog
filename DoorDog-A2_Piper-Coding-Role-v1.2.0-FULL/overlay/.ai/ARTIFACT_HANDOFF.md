<!-- managed-by: jam-coding-role; file: ARTIFACT_HANDOFF.md -->
# Stage artifact packaging and Pro_Space handoff

This profile is for training、evaluation、simulation and long-running projects, not every coding task.

## Trigger

At an Owner-defined stage closure, inspect untracked/ignored artifacts required for the next planning round: resolved configs、train/eval logs、reducers、metrics、telemetry、representative renders/videos、run receipts and explicitly requested checkpoints.

## Selection safety

- Select only configured allowlist paths; never archive the entire untracked tree.
- Exclude credentials、tokens、private keys、environment files、cache and unrelated worktree outputs.
- Checkpoints are opt-in.
- Enforce per-file and bundle size limits.
- Record missing and excluded artifacts honestly.

## Namespace

```text
ZIP:
<project>__<worktree>__<stage>__<YYYYMMDD-HHMMSS-HKT>__<sha>__artifacts.zip

Drive:
Pro_Space/<project>/<worktree>/<stage>/<timestamp>__<sha>/
```

Each bundle includes `BUNDLE_MANIFEST.json` and `PRO_HANDOFF.md` with repository revision、branch/worktree、stage、selection decisions、evidence boundary and cloud-planner questions.

## Standing authorization

Owner has approved `Pro_Space` folder ID `1JWQrkkOrItsKlFUjfxsadUrOcXChGpOf` as a public-writer, create-only stage-artifact target.

Authorized without repeated confirmation:

- create a new unique release namespace;
- upload a bundle that passed the configured selection and secret scan;
- create an upload receipt.

Not authorized:

- overwrite、delete or move existing cloud files;
- edit another task's artifact;
- upload an unfiltered tree、credentials、private configuration or personal data.

## Upload capability routing

Use the first available verified capability:

1. connected Google Drive upload tool;
2. reliable browser/computer-use upload to the shared folder;
3. authenticated `rclone`/Drive API already configured on the machine;
4. otherwise produce the bundle and mark `NOT_UPLOADED`.

Public web editor access does not itself create anonymous Drive API credentials.

## Hook boundary

Do not run large ZIP/upload work in a short SessionEnd hook. A stage-close command or external scheduler performs the work; hooks may only remind or surface pending events.
