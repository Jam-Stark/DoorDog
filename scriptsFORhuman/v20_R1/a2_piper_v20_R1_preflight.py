"""Build the complete hash-bound R1 static preflight manifest."""

from __future__ import annotations

import argparse
import ast
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Mapping

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _r1_common import (  # noqa: E402
    B0_CSV_NAME,
    B0_CSV_SHA256,
    B0_JSON_NAME,
    B0_JSON_SHA256,
    B0_SOURCE_BINDINGS,
    CALIBRATION_LABEL,
    CHECKPOINT_CONFIG_PATH,
    CHECKPOINT_PATH,
    GROUPS,
    PLAN_ID,
    PLAN_SHA256,
    R1Error,
    STATIC_PASS,
    URDF_BLOB_SHA1,
    URDF_SHA256,
    git_identity,
    resolve_repo_path,
    sha256_file,
    validate_exact_hash,
    validate_config_mapping,
    write_json_no_overwrite,
)

SCHEMA = "a2_piper_v20_R1_scientific_manifest_v3"
CONFIG_DIR = "gr00t/rl/config/ablation/wbmanip"
PREFLIGHT_SOURCE_PATHS = (
    "gr00t/rl/envs/base_task/staged_task_base.py",
    "gr00t/rl/envs/door/door_open_a2_base.py",
    "gr00t/rl/config/env/door_open_a2_base.yaml",
    "gr00t/rl/config/rewards/wbmanip/reward_door_open_a2_base.yaml",
    "gr00t/rl/trl/utils/scheduler.py",
    "gr00t/rl/train_agent_trl.py",
)
STATIC_TEST_PATHS = (
    "gr00t/rl/tests/test_a2_v20_R1_curriculum.py",
    "gr00t/rl/tests/test_a2_v20_R1_launcher.py",
    "gr00t/rl/tests/test_a2_v20_R1_m22.py",
    "gr00t/rl/tests/test_a2_v20_R1_main_config.py",
    "gr00t/rl/tests/test_a2_v20_R1_pilot_adjudicator.py",
    "gr00t/rl/tests/test_a2_v20_R1_staged_reset_guard.py",
    "gr00t/rl/tests/test_a2_v20_R1_strict_schema.py",
    "gr00t/rl/tests/test_a2_v20_R1_gates.py",
    "gr00t/rl/tests/test_a2_v20_staged_reset_state.py",
)
R1_SCRIPT_PATHS = tuple(
    "scriptsFORhuman/v20_R1/" + name
    for name in (
        "__init__.py",
        "_r1_common.py",
        "a2_piper_v20_R1_baseline.py",
        "a2_piper_v20_R1_endpoint_report.py",
        "a2_piper_v20_R1_final_analysis.py",
        "a2_piper_v20_R1_launcher.py",
        "a2_piper_v20_R1_m22_adjudicator.py",
        "a2_piper_v20_R1_m22_queue.py",
        "a2_piper_v20_R1_paired_analysis.py",
        "a2_piper_v20_R1_pilot_adjudicator.py",
        "a2_piper_v20_R1_pilot_launcher.py",
        "a2_piper_v20_R1_preflight.py",
        "a2_piper_v20_R1_promote_configs.py",
        "a2_piper_v20_R1_render_queue.py",
        "a2_piper_v20_R1_render_adjudicator.py",
        "a2_piper_v20_R1_semantic_admission.py",
        "a2_piper_v20_R1_smoke_adjudicator.py",
        "a2_piper_v20_R1_smoke_launcher.py",
    )
)


def _hash_path(repo_root: Path, relative: str) -> dict[str, str]:
    path = resolve_repo_path(repo_root, relative)
    if not path.is_file() or path.is_symlink():
        raise R1Error(f"preflight required file is missing or symlinked: {relative}")
    return {"path": relative, "sha256": sha256_file(path)}


def _git_blob(repo_root: Path, relative: str) -> str:
    try:
        return subprocess.check_output(
            ["git", "hash-object", relative], cwd=repo_root, text=True
        ).strip()
    except (OSError, subprocess.CalledProcessError) as exc:
        raise R1Error(f"cannot resolve git blob for {relative}") from exc


def _reject_unbound(value: Any, name: str) -> None:
    if value is None or (
        isinstance(value, str)
        and value.strip().lower() in {"", "tbd", "todo", "unknown", "null"}
    ):
        raise R1Error(f"preflight field {name} is unbound")
    if isinstance(value, Mapping):
        for key, nested in value.items():
            _reject_unbound(nested, f"{name}.{key}")
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            _reject_unbound(nested, f"{name}[{index}]")


def _load_yaml_mapping(repo_root: Path, relative: str) -> dict[str, Any]:
    path = resolve_repo_path(repo_root, relative)
    if not path.is_file() or path.is_symlink():
        raise R1Error(f"preflight YAML missing or symlinked: {relative}")
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        raise R1Error(f"invalid YAML: {relative}") from exc
    if not isinstance(payload, Mapping):
        raise R1Error(f"preflight YAML must be a mapping: {relative}")
    return dict(payload)


def _load_config(repo_root: Path, relative: str, *, group: str | None = None) -> dict[str, Any]:
    payload = _load_yaml_mapping(repo_root, relative)
    validate_config_mapping(payload, group=group)
    _reject_unbound(payload, relative)
    return payload


def _canonical_json_sha(payload: Any) -> str:
    encoded = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    import hashlib

    return hashlib.sha256(encoded).hexdigest()


def _hydra_resolve_command(repo_root: Path, relative: str) -> list[str]:
    config_path = resolve_repo_path(repo_root, relative)
    expected_dir = (repo_root / CONFIG_DIR).resolve()
    if config_path.parent != expected_dir:
        raise R1Error(f"R1 Hydra config must be under {CONFIG_DIR}: {relative}")
    return [
        sys.executable,
        "-B",
        "gr00t/rl/train_agent_trl.py",
        "--cfg",
        "job",
        "--resolve",
        "+exp=wbmanip/door_open_a2_base_lstm",
        "+ablation=wbmanip/" + config_path.stem,
    ]


def _validate_resolved_r1(payload: Mapping[str, Any], *, relative: str, group: str | None) -> dict[str, Any]:
    validate_config_mapping(payload, group=group)
    expected_seed = next((spec["seed"] for spec in GROUPS if spec["group"] == group), None)
    if expected_seed is None and group is not None:
        raise R1Error(f"unknown R1 group for resolved config: {group}")
    if expected_seed is not None and payload.get("seed") != expected_seed:
        raise R1Error(f"resolved seed mismatch for {relative}")
    return dict(payload)


def _compose_config(repo_root: Path, relative: str, *, group: str | None = None) -> dict[str, Any]:
    command = _hydra_resolve_command(repo_root, relative)
    try:
        completed = subprocess.run(
            command,
            cwd=repo_root,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
            text=True,
            capture_output=True,
            check=False,
        )
    except OSError as exc:
        raise R1Error(f"cannot execute real Hydra resolve for {relative}") from exc
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "").strip().splitlines()
        raise R1Error(
            f"real Hydra --cfg job --resolve failed for {relative}: "
            + (detail[-1] if detail else "no diagnostic output")
        )
    try:
        resolved = yaml.safe_load(completed.stdout)
    except yaml.YAMLError as exc:
        raise R1Error(f"real Hydra resolved output is not YAML: {relative}") from exc
    if not isinstance(resolved, Mapping):
        raise R1Error(f"real Hydra resolved output is not a mapping: {relative}")
    return _validate_resolved_r1(resolved, relative=relative, group=group)


def _write_resolved(output_dir: Path, relative: str, payload: Mapping[str, Any]) -> dict[str, str]:
    target = output_dir / "resolved" / (Path(relative).stem + ".json")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return {
        "path": str(target),
        "sha256": sha256_file(target),
        "compose": "HYDRA_RESOLVED",
        "resolved_sha256": _canonical_json_sha(payload),
    }


def _validate_b0(repo_root: Path) -> dict[str, Any]:
    baseline_path = Path(__file__).resolve().parent / "a2_piper_v20_R1_baseline.py"
    import importlib.util

    spec = importlib.util.spec_from_file_location("_r1_preflight_baseline", baseline_path)
    if spec is None or spec.loader is None:
        raise R1Error("cannot load B0 baseline validator")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    payload = module.build_b0_companion(repo_root=repo_root)
    module._validate_companion(payload)
    return payload


def _static_parse(repo_root: Path, paths: tuple[str, ...]) -> list[dict[str, str]]:
    evidence: list[dict[str, str]] = []
    for relative in paths:
        path = resolve_repo_path(repo_root, relative)
        if path.suffix == ".py":
            try:
                ast.parse(path.read_text(encoding="utf-8"), filename=relative)
            except (OSError, SyntaxError) as exc:
                raise R1Error(f"static Python parse failed: {relative}") from exc
        elif path.suffix in {".yaml", ".yml"}:
            _load_yaml_mapping(repo_root, relative)
        else:
            raise R1Error(f"unsupported static path type: {relative}")
        evidence.append(_hash_path(repo_root, relative))
    return evidence


def run_static_test_matrix(repo_root: Path) -> dict[str, Any]:
    command = [
        sys.executable,
        "-B",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        *STATIC_TEST_PATHS,
    ]
    try:
        completed = subprocess.run(
            command,
            cwd=repo_root,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
            text=True,
            capture_output=True,
        )
    except OSError as exc:
        raise R1Error("cannot execute R1 static test matrix") from exc
    if completed.returncode != 0:
        raise R1Error(
            "R1 static test matrix failed:\n"
            + completed.stdout[-4000:]
            + completed.stderr[-4000:]
        )
    return {"status": STATIC_PASS, "command": command, "exit_code": completed.returncode}


def build_manifest(
    repo_root: Path,
    *,
    output_dir: Path | None = None,
    run_tests: bool = False,
) -> dict[str, Any]:
    if run_tests is not True:
        raise R1Error("preflight requires --run-tests before emitting STATIC PASS")
    repo_root = repo_root.resolve()
    plan = _hash_path(
        repo_root, "scriptsFORhuman/a2_piper_base_v20_R1_optimization_plan_20260729.md"
    )
    validate_exact_hash(repo_root / plan["path"], PLAN_SHA256, "R1 plan")
    urdf = _hash_path(repo_root, "gr00t/rl/data/robots/A2_Piper/a2_piper.urdf")
    urdf["git_blob_sha1"] = _git_blob(repo_root, urdf["path"])
    if urdf["git_blob_sha1"] != URDF_BLOB_SHA1:
        raise R1Error("A2 Piper URDF git blob mismatch")
    if urdf["sha256"] != URDF_SHA256:
        raise R1Error("A2 Piper URDF SHA256 mismatch")
    checkpoint = _hash_path(repo_root, CHECKPOINT_PATH)
    validate_exact_hash(
        repo_root / checkpoint["path"],
        "b331c9a343c71dccf6cce31f71c1727a24298d72808c25763a0f702c369a866d",
        "R1 checkpoint",
    )
    checkpoint_config = _hash_path(repo_root, CHECKPOINT_CONFIG_PATH)
    b0_json = _hash_path(repo_root, "scriptsFORhuman/v20_R1/" + B0_JSON_NAME)
    validate_exact_hash(repo_root / b0_json["path"], B0_JSON_SHA256, "B0 JSON companion")
    b0_csv = _hash_path(repo_root, "scriptsFORhuman/v20_R1/" + B0_CSV_NAME)
    validate_exact_hash(repo_root / b0_csv["path"], B0_CSV_SHA256, "B0 CSV companion")
    b0_payload = _validate_b0(repo_root)
    b0_sources = []
    for name, relative, expected in B0_SOURCE_BINDINGS:
        row = _hash_path(repo_root, relative)
        validate_exact_hash(repo_root / relative, expected, f"B0 {name}")
        b0_sources.append(row | {"name": name})
    source_files = _static_parse(repo_root, PREFLIGHT_SOURCE_PATHS)
    script_files = _static_parse(repo_root, R1_SCRIPT_PATHS)
    test_files = _static_parse(repo_root, STATIC_TEST_PATHS)

    candidate_configs = []
    hydra_resolved = []
    for spec in GROUPS:
        relative = CONFIG_DIR + "/" + spec["config"]
        source = _load_config(repo_root, relative, group=spec["group"])
        composed = _compose_config(repo_root, relative, group=spec["group"])
        row = _hash_path(repo_root, relative) | {
            "group": spec["group"],
            "seed": spec["seed"],
            "resolved_sha256": _canonical_json_sha(composed),
        }
        if output_dir is not None:
            row["resolved"] = _write_resolved(output_dir, relative, composed)
        candidate_configs.append(row)
        hydra_resolved.append(
            {
                "group": spec["group"],
                "config": relative,
                "source_sha256": sha256_file(resolve_repo_path(repo_root, relative)),
                "resolved_sha256": row["resolved_sha256"],
                "source_seed": source.get("seed"),
                "command": _hydra_resolve_command(repo_root, relative),
                "status": "HYDRA_RESOLVED",
            }
        )
    pilot_relative = CONFIG_DIR + "/base_v20_R1_P2_G4_learnability_pilot.yaml"
    pilot_source = _load_config(repo_root, pilot_relative)
    pilot_composed = _compose_config(repo_root, pilot_relative, group=None)
    pilot = _hash_path(repo_root, pilot_relative) | {
        "resolved_sha256": _canonical_json_sha(pilot_composed),
    }
    if output_dir is not None:
        pilot["resolved"] = _write_resolved(output_dir, pilot_relative, pilot_composed)
    hydra_resolved.append(
        {
            "config": pilot_relative,
            "source_sha256": sha256_file(resolve_repo_path(repo_root, pilot_relative)),
            "resolved_sha256": pilot["resolved_sha256"],
            "source_seed": pilot_source.get("seed"),
            "command": _hydra_resolve_command(repo_root, pilot_relative),
            "status": "HYDRA_RESOLVED",
        }
    )

    static_tests = run_static_test_matrix(repo_root)
    manifest: dict[str, Any] = {
        "schema": SCHEMA,
        "status": STATIC_PASS,
        "plan_id": PLAN_ID,
        "plan_sha256": PLAN_SHA256,
        "git": git_identity(repo_root),
        "urdf": urdf,
        "checkpoint": checkpoint | {"config": checkpoint_config},
        "b0_companion": {
            "json": b0_json,
            "csv": b0_csv,
            "sources": b0_sources,
            "payload_schema": b0_payload["schema"],
        },
        "preflight_sources": source_files,
        "scripts": script_files,
        "tests": test_files,
        "pilot_config": pilot,
        "candidate_configs": candidate_configs,
        "hydra_compose": {
            "status": "HYDRA_RESOLVED",
            "configs": hydra_resolved,
            "count": len(hydra_resolved),
        },
        "static_tests": static_tests,
        "legal_gpus": list(range(7)),
        "reserved_gpu": 7,
        "calibration_label": CALIBRATION_LABEL,
        "schedule": {"seg_steps": [0, 500], "seg_vals": ["penalty", "terminal"]},
        "gates": {
            "theta_send_rad": 0.90,
            "root_x_margin_m": 0.03,
            "arm_tangent_scale": 3.5,
            "arc_tracking_scale": 0.85,
        },
        "groups": [dict(row) for row in GROUPS],
    }
    if output_dir is not None:
        output_dir.mkdir(parents=True, exist_ok=True)
        write_json_no_overwrite(output_dir / "R1_SCIENTIFIC_MANIFEST.json", manifest)
        (output_dir / "R1_SCIENTIFIC_MANIFEST.md").write_text(
            "# base_v20_R1 scientific manifest\n\n"
            + "- status: " + manifest["status"] + "\n"
            + "- plan: " + PLAN_ID + "\n"
            + "- plan SHA256: " + PLAN_SHA256 + "\n"
            + "- Hydra configs resolved: " + str(len(hydra_resolved)) + "\n",
            encoding="utf-8",
        )
    return manifest


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--run-tests", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    build_manifest(args.repo_root, output_dir=args.output_dir, run_tests=args.run_tests)
    return 0


def _require_blocked_r1_cli_opt_in() -> None:
    if "BASE_V20_ALLOW_BLOCKED_R1_EXECUTION" not in __import__("os").environ:
        print(
            "R1 execution is blocked by default; set BASE_V20_ALLOW_BLOCKED_R1_EXECUTION explicitly to run historical tooling",
            file=__import__("sys").stderr,
        )
        raise SystemExit(2)


if __name__ == "__main__":
    _require_blocked_r1_cli_opt_in()
    raise SystemExit(main())
