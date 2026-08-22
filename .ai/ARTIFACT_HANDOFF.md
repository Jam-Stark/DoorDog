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
ZIP:
<project>__<worktree>__<stage>__<YYYYMMDD-HHMMSS-HKT>__<sha>__artifacts.zip

Drive:
Pro_Space/<project>/<worktree>/<stage>/<timestamp>__<sha>/
```

Each bundle includes `BUNDLE_MANIFEST.json` and `PRO_HANDOFF.md`.

## Standing authorization

Owner has approved `Pro_Space` folder ID `1JWQrkkOrItsKlFUjfxsadUrOcXChGpOf` as a public-writer, create-only stage-artifact target.

Authorized: create a unique release namespace、upload a filtered bundle、write an upload receipt.

Not authorized: overwrite/delete/move existing cloud files、edit another task's artifacts、upload an unfiltered tree or credentials.

## Capability routing

Use the first verified path: connected Drive upload tool -> reliable browser/computer-use -> existing authenticated rclone/API -> otherwise create the bundle and report `NOT_UPLOADED`.

Public editor permission is not anonymous API authentication.

## Command boundary

`pack` and `upload` require an explicit `--confirm-stage-handoff` flag. Large ZIP/upload work does not run in SessionEnd hooks.
