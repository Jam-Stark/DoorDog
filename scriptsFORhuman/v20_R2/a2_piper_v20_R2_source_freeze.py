"""Build the immutable producer-only R2 source lock.

The lock is a source snapshot, not an admission result.  It binds the active
Git identity, every deterministic source/input selection and the exact CPU
command templates that P0 must execute.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Mapping

from ._r2_common import (
    ADMISSION_PLAN_ID,
    B0_CSV_PATH,
    B0_CSV_SHA256,
    B0_JSON_PATH,
    B0_JSON_SHA256,
    R1_BLOCKER_COMMIT,
    R1_CHECKPOINT_PATH,
    R1_CHECKPOINT_SHA256,
    R1_PLAN_PATH,
    R1_PLAN_SHA256,
    R1_URDF_PATH,
    R1_URDF_SHA256,
    R2Error,
    R2_PLAN_LOCK_PATH,
    R2_PLAN_LOCK_SHA256,
    R2_PLAN_PATH,
    R2_PLAN_SHA256,
    canonical_json,
    hash_command_env,
    resolve_repo_path,
    sha256_bytes,
    sha256_file,
    validate_clean_git,
    write_json_exclusive,
)


R2_SOURCE_ROOT = "scriptsFORhuman/v20_R2"
R2_SCHEMA_ROOT = "scriptsFORhuman/v20_R2/schemas"
R2_TEST_GLOB = "gr00t/rl/tests/test_a2_v20*.py"
R2_CONFIG_ROOT = "gr00t/rl/config/ablation/wbmanip"
CHECKPOINT_CONFIG_PATH = "logs_rl/a2_piper_full_stage_a2_base/base_v19/base_v19_G2_norm_control-20260727_012027/config.yaml"
LEGACY_G2_CONFIG_PATH = "gr00t/rl/config/ablation/wbmanip/base_v19_G2_norm_control.yaml"
CHECKPOINT_SIZE_BYTES = 29_996_147

R2_CONFIG_PATHS = (
    "gr00t/rl/config/ablation/wbmanip/base_v20_R2_G1_g2_continuation.yaml",
    "gr00t/rl/config/ablation/wbmanip/base_v20_R2_G2_economics_only.yaml",
    "gr00t/rl/config/ablation/wbmanip/base_v20_R2_G3_send_curriculum_only.yaml",
    "gr00t/rl/config/ablation/wbmanip/base_v20_R2_G4_send_curriculum_economics.yaml",
    "gr00t/rl/config/ablation/wbmanip/base_v20_R2_G5_send_curriculum_arm_tie.yaml",
    "gr00t/rl/config/ablation/wbmanip/base_v20_R2_G6_full.yaml",
    "gr00t/rl/config/ablation/wbmanip/base_v20_R2_G7_full_seed1.yaml",
    "gr00t/rl/config/ablation/wbmanip/base_v20_R2_P2_G4_learnability_pilot.yaml",
)
DIMENSIONS = {"observation": 1620, "actor_action": 12, "base_command": 5, "manipulation_action": 7}


def _git_tracked(repo_root: Path, relative: str) -> bool:
    try:
        subprocess.check_call(
            ["git", "ls-files", "--error-unmatch", "--", relative],
            cwd=repo_root,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except (OSError, subprocess.CalledProcessError):
        return False
    return True


def _source_entry(repo_root: Path, relative: str, kind: str, *, allow_untracked: bool = False) -> dict[str, Any]:
    """Return a regular-file source row; only the exact checkpoint is exempt."""

    tracked = _git_tracked(repo_root, relative)
    if not tracked and not allow_untracked:
        raise R2Error(f"source must be tracked before freeze: {relative}")
    if allow_untracked and relative != R1_CHECKPOINT_PATH:
        raise R2Error("only the exact R1 checkpoint may be exempt from trackedness")
    path = resolve_repo_path(repo_root, relative, require_file=True)
    size = path.stat().st_size
    if allow_untracked and size != CHECKPOINT_SIZE_BYTES:
        raise R2Error(f"R1 checkpoint size mismatch: expected {CHECKPOINT_SIZE_BYTES}, got {size}")
    return {"path": relative, "sha256": sha256_file(path), "size_bytes": size, "kind": kind, "tracked": tracked}


def _changed_candidate_paths(repo_root: Path, ancestor: str) -> list[str]:
    try:
        output = subprocess.check_output(
            ["git", "diff", "--name-status", "--find-renames", ancestor, "HEAD", "--"], cwd=repo_root, text=True
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise R2Error("cannot discover changed candidate paths") from exc
    selected: list[str] = []
    for line in output.splitlines():
        if not line.strip():
            continue
        fields = line.split("\t")
        status, paths = fields[0], fields[1:]
        if status.startswith(("R", "C")):
            if len(paths) != 2:
                raise R2Error(f"malformed rename/copy status: {line!r}")
            paths = [paths[-1]]
        if any(path.endswith((".py", ".yaml")) for path in paths):
            if status.startswith("D"):
                raise R2Error(f"changed source was deleted and cannot be frozen: {paths[-1]}")
            selected.extend(path for path in paths if path.endswith((".py", ".yaml")))
    return sorted(set(selected))


def _scalar(text: str, key: str) -> str:
    matches = re.findall(rf"^\s*{re.escape(key)}:\s*([^#\s]+)\s*$", text, re.MULTILINE)
    if len(matches) != 1:
        raise R2Error(f"expected exactly one scalar {key!r}, found {len(matches)}")
    return matches[0].strip("'\"")


def _bool(text: str, key: str) -> bool:
    value = _scalar(text, key).lower()
    if value not in {"true", "false"}:
        raise R2Error(f"{key} must be a YAML boolean, got {value!r}")
    return value == "true"


def _dimensions(repo_root: Path) -> dict[str, int]:
    text = resolve_repo_path(repo_root, CHECKPOINT_CONFIG_PATH, require_file=True).read_text(encoding="utf-8")
    keys = {"observation": "obs_dim", "actor_action": "action_dim", "base_command": "base_command_dim", "manipulation_action": "manipulation_action_dim"}
    result = {name: int(_scalar(text, key)) for name, key in keys.items()}
    if result != DIMENSIONS or result["base_command"] + result["manipulation_action"] != result["actor_action"]:
        raise R2Error(f"checkpoint-adjacent dimension contract mismatch: {result}")
    return result


def _factor_bindings(repo_root: Path) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for relative in R2_CONFIG_PATHS:
        path = resolve_repo_path(repo_root, relative, require_file=True)
        text = path.read_text(encoding="utf-8")
        stem = Path(relative).stem
        if "_P2_" in stem:
            group = "P2"
        else:
            match = re.search(r"_R2_(G[1-7])_", stem)
            if match is None:
                raise R2Error(f"cannot derive factor group: {relative}")
            group = match.group(1)
        result.append(
            {
                "group": group,
                "source_path": relative,
                "source_sha256": sha256_file(path),
                "seed": int(_scalar(text, "seed")),
                "num_envs": int(_scalar(text, "num_envs")),
                "batches": int(_scalar(text, "num_total_batches")),
                "send_curriculum": _bool(text, "a2_v20_R1_send_curriculum_enabled"),
                "economics": _bool(text, "a2_v20_traversal_economics_enabled"),
                "arm_tie": _bool(text, "a2_v20_arm_tie_enabled"),
                "crossing_mode": _scalar(text, "a2_v20_pre_send_crossing_mode"),
            }
        )
    return sorted(result, key=lambda row: row["group"])


def _resolved_templates(repo_root: Path) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for relative in R2_CONFIG_PATHS:
        stem = Path(relative).stem
        group = "P2" if "_P2_" in stem else re.search(r"_R2_(G[1-7])_", stem).group(1)
        argv = [sys.executable, "-B", "gr00t/rl/train_agent_trl.py", "--cfg", "job", "--resolve", "+exp=wbmanip/door_open_a2_base_lstm", f"+ablation=wbmanip/{stem}"]
        result.append(
            {
                "name": f"hydra_resolve_{group}",
                "group": group,
                "source_path": relative,
                "source_sha256": sha256_file(resolve_repo_path(repo_root, relative, require_file=True)),
                "resolved_config_sha256": sha256_bytes(canonical_json([line.rstrip() for line in resolve_repo_path(repo_root, relative, require_file=True).read_text(encoding="utf-8").splitlines() if line.strip() and not line.lstrip().startswith("#")]).encode("utf-8")),
                "argv_template": argv,
                "env": {"PYTHONDONTWRITEBYTECODE": "1"},
                "env_sha256": hash_command_env(argv, {"PYTHONDONTWRITEBYTECODE": "1"}),
            }
        )
    return result


def discover_sources(repo_root: Path) -> list[dict[str, Any]]:
    """Discover all R2 files, all v20 tests, all eight R2 configs and inputs."""

    root = resolve_repo_path(repo_root, ".")
    selected: list[dict[str, Any]] = []
    for relative, kind in (
        (R2_PLAN_PATH, "immutable_input"),
        (R2_PLAN_LOCK_PATH, "immutable_input"),
        (R1_PLAN_PATH, "immutable_input"),
        (B0_JSON_PATH, "immutable_input"),
        (B0_CSV_PATH, "immutable_input"),
        (LEGACY_G2_CONFIG_PATH, "immutable_input"),
        (R1_URDF_PATH, "urdf"),
    ):
        selected.append(_source_entry(root, relative, kind))
    selected.append(_source_entry(root, R1_CHECKPOINT_PATH, "checkpoint", allow_untracked=True))
    for path in sorted(resolve_repo_path(root, R2_SOURCE_ROOT).glob("*.py")):
        selected.append(_source_entry(root, path.relative_to(root).as_posix(), "source"))
    for path in sorted(resolve_repo_path(root, R2_SCHEMA_ROOT).glob("*.json")):
        selected.append(_source_entry(root, path.relative_to(root).as_posix(), "schema"))
    for path in sorted(resolve_repo_path(root, "gr00t/rl/tests").glob("test_a2_v20*.py")):
        selected.append(_source_entry(root, path.relative_to(root).as_posix(), "test"))
    for relative in R2_CONFIG_PATHS:
        selected.append(_source_entry(root, relative, "config"))
    by_path = {str(row["path"]): row for row in selected}
    changed = _changed_candidate_paths(root, R1_BLOCKER_COMMIT)
    for relative in changed:
        row = by_path.get(relative)
        if row is None:
            row = _source_entry(root, relative, "changed_config" if relative.endswith(".yaml") else "changed_source")
            by_path[relative] = row
        row["roles"] = sorted(set(row.get("roles", [])) | {"changed_candidate"})
    result = sorted(by_path.values(), key=lambda row: row["path"])
    if set(changed) != {str(row["path"]) for row in result if "changed_candidate" in row.get("roles", [])}:
        raise R2Error("changed candidate discovery contains an unbound path")
    return result


def _immutable_expected(repo_root: Path) -> None:
    checks = (
        (R2_PLAN_PATH, R2_PLAN_SHA256, "R2 plan", None),
        (R2_PLAN_LOCK_PATH, R2_PLAN_LOCK_SHA256, "R2 plan lock", None),
        (R1_PLAN_PATH, R1_PLAN_SHA256, "R1 plan", None),
        (B0_JSON_PATH, B0_JSON_SHA256, "B0 JSON", None),
        (B0_CSV_PATH, B0_CSV_SHA256, "B0 CSV", None),
        (R1_CHECKPOINT_PATH, R1_CHECKPOINT_SHA256, "R1 checkpoint", CHECKPOINT_SIZE_BYTES),
        (R1_URDF_PATH, R1_URDF_SHA256, "R1 URDF", None),
    )
    for relative, expected, label, expected_size in checks:
        path = resolve_repo_path(repo_root, relative, require_file=True)
        if sha256_file(path) != expected:
            raise R2Error(f"{label} SHA-256 mismatch")
        if expected_size is not None and path.stat().st_size != expected_size:
            raise R2Error(f"{label} size mismatch: expected {expected_size}")


def _script(code: str, *args: str) -> list[str]:
    return [sys.executable, "-B", "-c", code, *args]


def build_command_templates(repo_root: Path, source_lock: Mapping[str, Any], *, output_root: Path | None = None, source_lock_path: Path | None = None) -> list[dict[str, Any]]:
    """Build the complete executable §10.5 P0 matrix."""

    root = resolve_repo_path(repo_root, ".")
    output = str(output_root if output_root is not None else "{OUTPUT_ROOT}")
    lock = str(source_lock_path if source_lock_path is not None else "{SOURCE_LOCK}")
    rows = list(source_lock.get("sources", []))
    all_paths = sorted(str(row["path"]) for row in rows)
    py_paths = [path for path in all_paths if path.endswith(".py")]
    test_paths = sorted(str(row["path"]) for row in rows if row.get("kind") == "test")
    focused_paths = [path for path in test_paths if "_R2" in Path(path).stem]
    hash_code = "import hashlib,pathlib,sys; a=sys.argv[1:]; assert len(a)%3==0; [((lambda p,h,s: None if p.is_file() and not p.is_symlink() and p.stat().st_size==int(s) and hashlib.sha256(p.read_bytes()).hexdigest()==h else (_ for _ in ()).throw(SystemExit(1)))(pathlib.Path(*p.split('\\0',1)),h,s)) for p,h,s in zip(a[0::3],a[1::3],a[2::3])]; print('SOURCE_HASHES_OK')"
    compile_code = "import pathlib,sys; [compile(pathlib.Path(p).read_text(encoding='utf-8'),p,'exec') for p in sys.argv[1:]]; print('PY_COMPILE_OK',len(sys.argv)-1)"
    discovery_code = "import json,sys; print(json.dumps(sorted(sys.argv[1:]),separators=(',',':')))"
    factor_code = "import json,re,sys; rows=[]\nfor p in sys.argv[1:]:\n t=open(p,encoding='utf-8').read(); f=lambda k: re.findall(r'^\\s*'+re.escape(k)+r':\\s*([^#\\s]+)\\s*$',t,re.M); rows.append({'path':p,'seed':int(f('seed')[0]),'num_envs':int(f('num_envs')[0]),'batches':int(f('num_total_batches')[0]),'send_curriculum':f('a2_v20_R1_send_curriculum_enabled')[0],'economics':f('a2_v20_traversal_economics_enabled')[0],'arm_tie':f('a2_v20_arm_tie_enabled')[0],'crossing_mode':f('a2_v20_pre_send_crossing_mode')[0]})\nprint(json.dumps(rows,sort_keys=True,separators=(',',':')))"
    parity_code = "import pathlib,re,sys; t=pathlib.Path(sys.argv[1]).read_text(); g=lambda k: re.findall(r'^\\s*'+re.escape(k)+r':\\s*([^#\\s]+)\\s*$',t,re.M); exp={'a2_v20_send_latch_enabled':'false','a2_v20_traversal_economics_enabled':'false','a2_v20_arm_tie_enabled':'false','a2_v20_pre_send_crossing_mode':'disabled','a2_v20_target_root_pre_send_scale':'0.0','a2_v20_target_root_post_send_stage4_scale':'0.5'}; bad=[k for k,v in exp.items() if g(k)!=[v]]; assert not bad, ('V19_G2_DISABLED_PARITY_MISMATCH',bad); print('V19_G2_DISABLED_PARITY_OK')"
    dimensions_code = "import pathlib,re,sys; t=pathlib.Path(sys.argv[1]).read_text(); e={'obs_dim':'1620','action_dim':'12','base_command_dim':'5','manipulation_action_dim':'7'}; [(_ for _ in ()).throw(SystemExit(1)) if re.findall(r'^\\s*'+k+r':\\s*(\\d+)\\s*$',t,re.M)!=[v] else None for k,v in e.items()]; print('DIMENSIONS_OK')"
    hidden_code = "import pathlib,sys; bad=('hidden_action_override','scripted_trajectory','damped_least_squares','privileged_hinge_override'); [(_ for _ in ()).throw(SystemExit('forbidden hidden action override')) if any(x in pathlib.Path(p).read_text(encoding='utf-8').lower() for x in bad) else None for p in sys.argv[1:]]; print('NO_HIDDEN_ACTION_OVERRIDE_OK')"
    device_code = "from scriptsFORhuman.v20_R2._r2_common import validate_device_contract; validate_device_contract(gpu=3,render=False,argv=['python','device=cuda:3'],env={'ACCELERATE_TORCH_DEVICE':'cuda:3'},app_launcher_device='cuda:3',accelerator_device='cuda:3'); validate_device_contract(gpu=3,render=True,argv=['python','device=cuda:0'],env={'CUDA_VISIBLE_DEVICES':'3','ACCELERATE_TORCH_DEVICE':'cuda:0'},app_launcher_device='cuda:0',accelerator_device='cuda:0'); print('DEVICE_CONTRACT_OK')"
    output_code = "import datetime,re,sys; p=sys.argv[1].replace('\\\\','/'); assert p.endswith('/admission/revision0/p0') or p.endswith('/admission/revision1/p0'); assert re.fullmatch(r'\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}Z',datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat().replace('+00:00','Z')); print('OUTPUT_ROOT_UTC_OK')"
    commands: list[dict[str, Any]] = []

    def add(name: str, category: str, argv: list[str], env: Mapping[str, str] | None = None) -> None:
        selected = dict(sorted((env or {}).items()))
        commands.append({"name": name, "category": category, "argv": argv, "env": selected, "env_sha256": hash_command_env(argv, selected)})

    add("source_lock_rehash", "rehash", _script("import hashlib,pathlib,sys; print(hashlib.sha256(pathlib.Path(sys.argv[1]).read_bytes()).hexdigest())", lock), {"PYTHONDONTWRITEBYTECODE": "1"})
    add("git_status", "git", ["git", "status", "--porcelain=v1", "--untracked-files=all"])
    add("git_branch", "git", ["git", "branch", "--show-current"])
    add("git_ancestor", "git", ["git", "merge-base", "--is-ancestor", R1_BLOCKER_COMMIT, "HEAD"])
    add("git_tree", "git", ["git", "rev-parse", "HEAD^{tree}"])
    hash_args = [item for row in rows for item in (str(row["path"]), str(row["sha256"]), str(row.get("size_bytes", 0)))]
    immutable = source_lock.get("immutable_inputs", {})
    if isinstance(immutable, Mapping):
        config_path = immutable.get("checkpoint_config_path")
        config_sha = immutable.get("checkpoint_config_sha256")
        config_size = immutable.get("checkpoint_config_size_bytes")
        if isinstance(config_path, str) and isinstance(config_sha, str) and isinstance(config_size, int):
            hash_args.extend([config_path, config_sha, str(config_size)])
    # NUL-prefixing paths makes the hash check unambiguous even when a path
    # contains spaces; the repository currently has none, but the contract is
    # explicit rather than relying on shell splitting.
    add("source_hashes", "hash", _script(hash_code, *hash_args), {"PYTHONDONTWRITEBYTECODE": "1"})
    add("py_compile", "compile", _script(compile_code, *py_paths), {"PYTHONDONTWRITEBYTECODE": "1"})
    add("diff_check", "diff", ["git", "diff", "--check", R1_BLOCKER_COMMIT, "HEAD", "--"])
    add("full_test_discovery", "test_discovery", _script(discovery_code, *test_paths), {"PYTHONDONTWRITEBYTECODE": "1"})
    add("full_pytest", "full_pytest", [sys.executable, "-B", "-m", "pytest", "-q", "-p", "no:cacheprovider", *test_paths], {"PYTHONDONTWRITEBYTECODE": "1"})
    add("focused_pytest", "focused_pytest", [sys.executable, "-B", "-m", "pytest", "-q", "-p", "no:cacheprovider", *focused_paths], {"PYTHONDONTWRITEBYTECODE": "1"})
    for row in _resolved_templates(root):
        add(row["name"], "hydra_resolve", list(row["argv_template"]), row["env"])
    add("factor_source_to_resolved", "factor_matrix", _script(factor_code, *[str(row["source_path"]) for row in source_lock.get("factor_bindings", [])]), {"PYTHONDONTWRITEBYTECODE": "1"})
    add("v19_g2_disabled_parity", "legacy_parity", _script(parity_code, R2_CONFIG_PATHS[0]), {"PYTHONDONTWRITEBYTECODE": "1"})
    add("dimensions", "dimensions", _script(dimensions_code, CHECKPOINT_CONFIG_PATH), {"PYTHONDONTWRITEBYTECODE": "1"})
    add("hidden_action_override", "hidden_override", _script(hidden_code, *[p for p in py_paths if not p.startswith("scriptsFORhuman/")]), {"PYTHONDONTWRITEBYTECODE": "1"})
    staged = [path for path in test_paths if "staged_reset" in Path(path).stem]
    add("staged_reset_ownership", "staged_ownership", [sys.executable, "-B", "-m", "pytest", "-q", "-p", "no:cacheprovider", *staged], {"PYTHONDONTWRITEBYTECODE": "1"})
    m48 = [path for path in test_paths if "evidence_record" in Path(path).stem or "endpoint_report" in Path(path).stem]
    add("m48_consumer", "m48_consumer", [sys.executable, "-B", "-m", "pytest", "-q", "-p", "no:cacheprovider", *m48], {"PYTHONDONTWRITEBYTECODE": "1"})
    add("device_environment", "device_environment", _script(device_code), {"PYTHONDONTWRITEBYTECODE": "1"})
    add("output_root_utc", "output_root_utc", _script(output_code, output), {"PYTHONDONTWRITEBYTECODE": "1"})
    return commands


def build_source_lock(*, repo_root: Path, revision: int, required_branch: str, required_ancestor: str) -> dict[str, Any]:
    if revision not in (0, 1):
        raise R2Error("R2 permits only static revision 0 or 1")
    if required_branch != "A2_Piper" or required_ancestor != R1_BLOCKER_COMMIT:
        raise R2Error("R2 source freeze requires branch A2_Piper and the exact R1 blocker ancestor")
    root = resolve_repo_path(repo_root, ".")
    identity = validate_clean_git(root, branch=required_branch, required_ancestor=required_ancestor)
    _immutable_expected(root)
    sources = discover_sources(root)
    changed = _changed_candidate_paths(root, required_ancestor)
    dimensions = _dimensions(root)
    factors = _factor_bindings(root)
    resolved = _resolved_templates(root)
    checkpoint_config = resolve_repo_path(root, CHECKPOINT_CONFIG_PATH, require_file=True)
    provisional = {
        "sources": sources,
        "factor_bindings": factors,
        "immutable_inputs": {
            "checkpoint_config_path": CHECKPOINT_CONFIG_PATH,
            "checkpoint_config_sha256": sha256_file(checkpoint_config),
            "checkpoint_config_size_bytes": checkpoint_config.stat().st_size,
        },
    }
    commands = build_command_templates(root, provisional)
    urdf_blob = subprocess.check_output(["git", "hash-object", R1_URDF_PATH], cwd=root, text=True).strip()
    if urdf_blob != "95c7698866962fa6e1b971b9ee534452775d8698":
        raise R2Error("runtime URDF Git blob mismatch")
    return {
        "schema": "a2_piper_base_v20_R2_source_lock_v1",
        "producer_state": "SOURCE_FROZEN",
        "revision": revision,
        "admission_plan_id": ADMISSION_PLAN_ID,
        "scientific_plan_id": "base_v20_R1_policy_behavior_v1",
        "git": {"commit": identity["commit"], "tree": identity["tree"], "branch": identity["branch"], "required_ancestor": required_ancestor},
        "immutable_inputs": {
            "r2_plan_sha256": R2_PLAN_SHA256,
            "r2_plan_lock_sha256": R2_PLAN_LOCK_SHA256,
            "r1_plan_sha256": R1_PLAN_SHA256,
            "b0_json_sha256": B0_JSON_SHA256,
            "b0_csv_sha256": B0_CSV_SHA256,
            "checkpoint_sha256": R1_CHECKPOINT_SHA256,
            "checkpoint_size_bytes": CHECKPOINT_SIZE_BYTES,
            "checkpoint_config_path": CHECKPOINT_CONFIG_PATH,
            "checkpoint_config_sha256": sha256_file(checkpoint_config),
            "checkpoint_config_size_bytes": checkpoint_config.stat().st_size,
            "legacy_g2_config_path": LEGACY_G2_CONFIG_PATH,
            "urdf_sha256": R1_URDF_SHA256,
            "urdf_git_blob_sha1": urdf_blob,
        },
        "sources": sources,
        "changed_candidates": changed,
        "resolved_configs": resolved,
        "dimensions": dimensions,
        "factor_bindings": factors,
        "commands": commands,
        "discovery": {
            "r2_tests_glob": R2_TEST_GLOB,
            "r2_config_root": R2_CONFIG_ROOT,
            "test_count": sum(row["kind"] == "test" for row in sources),
            "config_count": sum(row["kind"] == "config" for row in sources),
            "changed_candidate_count": len(changed),
            "resolved_config_count": len(resolved),
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--revision", type=int, required=True, choices=(0, 1))
    parser.add_argument("--required-branch", default="A2_Piper")
    parser.add_argument("--required-ancestor", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    output = args.output if args.output.is_absolute() else args.repo_root / args.output
    payload = build_source_lock(repo_root=args.repo_root, revision=args.revision, required_branch=args.required_branch, required_ancestor=args.required_ancestor)
    write_json_exclusive(output, payload)
    print(canonical_json({"producer_state": payload["producer_state"], "output": str(output)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
