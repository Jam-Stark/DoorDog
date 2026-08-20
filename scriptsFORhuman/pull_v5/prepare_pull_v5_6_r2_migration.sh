#!/usr/bin/env bash
set -euo pipefail

repo_root="${1:-/home/baoquanc/workspace/DoorDog-A2_Piper_pull_v0}"
archive_path="${2:-${repo_root}/a2_piper_pull_v5_6_r2_runtime_assets_20260820.zip}"
manifest_path="${repo_root}/scriptsFORhuman/pull_v5/PULL_V5_6_R2_RUNTIME_ASSETS.txt"

if [[ "$(git -C "${repo_root}" rev-parse --is-inside-work-tree 2>/dev/null)" != "true" ]]; then
  echo "repository root is not a Git worktree: ${repo_root}" >&2
  exit 2
fi
if [[ ! -f "${manifest_path}" ]]; then
  echo "runtime asset manifest is missing: ${manifest_path}" >&2
  exit 2
fi
if [[ -e "${archive_path}" ]]; then
  echo "refusing to replace an existing archive: ${archive_path}" >&2
  exit 2
fi

mapfile -t assets < <(sed -e '/^[[:space:]]*#/d' -e '/^[[:space:]]*$/d' "${manifest_path}")
for relative_path in "${assets[@]}"; do
  if [[ ! -f "${repo_root}/${relative_path}" ]]; then
    echo "required runtime asset is missing: ${relative_path}" >&2
    exit 2
  fi
done

(
  cd "${repo_root}"
  zip -q "${archive_path}" "${assets[@]}"
)

echo "created ${archive_path}"
echo "asset_count=${#assets[@]}"
