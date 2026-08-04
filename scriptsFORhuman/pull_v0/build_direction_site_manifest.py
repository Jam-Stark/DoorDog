#!/usr/bin/env python3
"""Build the immutable pull-v0 direction-site classification manifest."""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
import subprocess
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "scriptsFORhuman/pull_v0/PULL_V0_DIRECTION_SITE_MANIFEST.json"
PLAN_ID = "a2_piper_pull_v0_tensile_feasibility_v1"
EXPECTED_BASE = "4aec9fe76043c3bb85d8bcdd1c2cd9210086dc09"

QUERIES = (
    (
        "Q1_DIRECTION_AND_TARGET",
        r"door_open_io|doorOpenIO|door_open_lr|doorOpenLR|grasp_target|A2_PREGRASP_OFFSET",
        ("gr00t/rl",),
    ),
    (
        "Q2_RESET_AND_STAGE_MACHINE",
        r"_reset_root_states|stage_0_to_1|stage_1_to_2|stage_2_to_3|stage_3_to_4|stage_4_to_5",
        ("gr00t/rl/envs/door",),
    ),
    (
        "Q3_WORLD_X_AND_PUSH_INSTITUTION",
        r"target_root_pos|root_x|crossing|corridor|send_ready|send_hinge|face_door|walk_to_door",
        ("gr00t/rl/envs/door", "gr00t/rl/config"),
    ),
    (
        "Q4_FORCE_CONTACT_AND_EFFORT",
        r"push_door|dont_push|handle_local|slip|hold_oracle|pd_effort|door_body_contact",
        ("gr00t/rl/envs/door", "gr00t/rl/config"),
    ),
)


def _git(*args: str) -> str:
    result = subprocess.run(
        ("git", *args),
        cwd=ROOT,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return result.stdout


def _query(query_id: str, pattern: str, paths: tuple[str, ...]) -> list[tuple[str, int, str]]:
    del query_id
    output = _git("grep", "-n", "-E", pattern, "--", *paths)
    rows = []
    for raw in output.splitlines():
        path, line_text, content = raw.split(":", 2)
        rows.append((path, int(line_text), content))
    return rows


def _nearest_symbol(path: str, line_number: int, cache: dict[str, list[str]]) -> str:
    lines = cache.setdefault(path, (ROOT / path).read_text(encoding="utf-8").splitlines())
    if path.endswith(".py"):
        for text in reversed(lines[:line_number]):
            match = re.match(r"\s*(?:async\s+)?(?:def|class)\s+([A-Za-z_][A-Za-z0-9_]*)", text)
            if match:
                return match.group(1)
    if path.endswith((".yaml", ".yml")):
        for text in reversed(lines[:line_number]):
            match = re.match(r"\s*([A-Za-z_][A-Za-z0-9_.-]*):(?:\s|$)", text)
            if match:
                return match.group(1)
    return Path(path).name


def _decision(
    path: str,
    line_number: int,
    content: str,
    query_ids: tuple[str, ...],
) -> dict[str, str]:
    lower = content.lower()

    if path.startswith("gr00t/rl/tests/"):
        return {
            "classification": "test",
            "decision": "Existing regression/evidence test site; preserve it and add pull-specific tests in the pull test namespace.",
            "source_action": "preserve_existing_test",
            "implementation_target": "gr00t/rl/tests/test_a2_pull_v0_*.py",
            "verification": "Existing test remains green; pull contract tests cover the corresponding direction semantic.",
        }

    if path.startswith("gr00t/rl/config/ablation/wbmanip/base_v"):
        return {
            "classification": "no-op",
            "decision": "Historical push/v20/v21-B ablation config is immutable evidence and is not a pull configuration source.",
            "source_action": "preserve_byte_identical",
            "implementation_target": "gr00t/rl/config/ablation/wbmanip/pull_v0_*.yaml",
            "verification": "Source blob/hash remains unchanged; pull configs live under the pull_v0 prefix.",
        }

    if path == "gr00t/rl/config/base_eval.yaml":
        return {
            "classification": "no-op",
            "decision": "Shared push evaluation defaults remain unchanged; pull evaluation binds explicit pull overrides/receipts.",
            "source_action": "preserve_byte_identical",
            "implementation_target": "scriptsFORhuman/pull_v0/ and pull-specific configs",
            "verification": "Pull receipts bind the resolved config; no push eval default is mutated.",
        }

    if path in {
        "gr00t/rl/config/env/door_open_a2_base.yaml",
        "gr00t/rl/config/rewards/wbmanip/reward_door_open_a2_base.yaml",
        "gr00t/rl/config/exp/wbmanip/door_open_a2_base_stage0_2_grasp_terminal_lstm.yaml",
    }:
        target = {
            "gr00t/rl/config/env/door_open_a2_base.yaml": "gr00t/rl/config/env/door_open_a2_pull.yaml",
            "gr00t/rl/config/rewards/wbmanip/reward_door_open_a2_base.yaml": "gr00t/rl/config/rewards/wbmanip/reward_door_open_a2_pull.yaml",
            "gr00t/rl/config/exp/wbmanip/door_open_a2_base_stage0_2_grasp_terminal_lstm.yaml": "pull-specific experiment config",
        }[path]
        return {
            "classification": "change",
            "decision": "This push-config semantic needs an explicit pull counterpart; the matched push file itself remains unchanged.",
            "source_action": "preserve_source_and_fork_pull_counterpart",
            "implementation_target": target,
            "verification": "Hydra compose and freeze guard prove pull values; push blob/hash regression proves isolation.",
        }

    if path == "gr00t/rl/data/tasks/door/scenario_cfg/isaacsim.py":
        return {
            "classification": "change",
            "decision": "The push scenario remains fixed right/out; add a separate right/in pull scenario binding.",
            "source_action": "preserve_push_binding_and_add_pull_binding",
            "implementation_target": "pull task scenario/config namespace",
            "verification": "Paired out/in scenario tests and deterministic geometry proof.",
        }

    if path == "gr00t/rl/isaac_utils/playground/env_rand/door.py":
        if "grasp_target" in lower or "door_open_io" in lower or "dooropenio" in lower:
            return {
                "classification": "change",
                "decision": "Use the existing IO sign to place the single grasp_target on the active handle face; retain metadata/replay identity.",
                "source_action": "minimal_shared_asset_change",
                "implementation_target": "spawn_door active-face grasp_target placement",
                "verification": "Paired deterministic in/out target-face and byte-compatible mechanics tests.",
            }
        return {
            "classification": "no-op",
            "decision": "Left/right hinge, handle, latch, and procedural geometry semantics are direction-invariant for pull-v0.",
            "source_action": "preserve_byte_identical",
            "implementation_target": "none",
            "verification": "Paired geometry proof confirms identical mechanics outside IO metadata/target pose.",
        }

    if path == "gr00t/rl/envs/door/door_open_a2_base.py":
        if 5090 <= line_number <= 5710:
            return {
                "classification": "change",
                "decision": "Add only the pull plan-id freeze-guard branch; v20 and v21-B branch bodies remain byte-identical.",
                "source_action": "guard_extension_only",
                "implementation_target": "_validate_a2_v20_r1_config pull branch and pull validator",
                "verification": "v20 G4, v21-B, valid pull, and invalid pull regression matrix.",
            }
        if any(token in lower for token in ("a2_v20", "a2_v21", "corridor", "send_ready", "send_hinge")):
            return {
                "classification": "no-op",
                "decision": "Push send/crossing/corridor/evidence institution is preserved and explicitly disabled for pull; only sign-correct telemetry is ported separately.",
                "source_action": "preserve_push_institution",
                "implementation_target": "door_open_a2_pull.py report-only telemetry",
                "verification": "Pull freeze guard requires selectors disabled; push hashes/tests remain unchanged.",
            }
        if any(token in lower for token in ("push_door_handle", "push_door_hinge", "dont_push_door")):
            return {
                "classification": "no-op",
                "decision": "Positive handle/hinge joint progress is direction-invariant; reuse the semantics without a sign flip.",
                "source_action": "reuse_direction_invariant_term",
                "implementation_target": "pull reward registry/counterpart",
                "verification": "Paired in/out joint-progress unit test and runtime telemetry.",
            }
        return {
            "classification": "change",
            "decision": "Direction-sensitive reset/stage/world-X/contact/effort semantic must consume the immutable pull direction contract in the pull env path.",
            "source_action": "preserve_push_path_and_implement_pull_override_or_helper",
            "implementation_target": "gr00t/rl/envs/door/door_open_a2_pull.py and a2_pull_direction.py",
            "verification": "Paired in/out contract tests, two-direction architecture smoke, and finite telemetry proof.",
        }

    if path == "gr00t/rl/envs/door/a2_piper_door_scene_preview.py":
        return {
            "classification": "change",
            "decision": "Pull static proof needs paired out/in pose, target, TCP, and orientation overlays; preserve default push preview behavior.",
            "source_action": "add_pull_specific_preview_mode_or_entrypoint",
            "implementation_target": "pull geometry-proof preview/overlay",
            "verification": "Static paired assertions plus GUI receipt; never label static proof runtime PASS.",
        }

    if path in {
        "gr00t/rl/envs/door/a2_v20_r2_evidence.py",
        "gr00t/rl/envs/door/a2_v20_r2_forced_semantics.py",
        "gr00t/rl/envs/door/a2_v21b_evidence.py",
    }:
        return {
            "classification": "no-op",
            "decision": "Push/v20/v21-B evidence schema and forced-semantics code are immutable and not reused as pull scientific authority.",
            "source_action": "preserve_byte_identical",
            "implementation_target": "pull-specific evidence schema",
            "verification": "Source blob/hash regression and pull namespace isolation tests.",
        }

    if path in {
        "gr00t/rl/envs/door/reset_from_dataset.py",
        "gr00t/rl/envs/legged_base_task/legged_robot_base.py",
    }:
        return {
            "classification": "no-op",
            "decision": "Generic reset/base behavior is outside the pull direction owner; pull overrides bind signed semantics without mutating this shared site.",
            "source_action": "preserve_shared_generic_code",
            "implementation_target": "pull env override",
            "verification": "Two-direction reset smoke exercises the resolved pull path.",
        }

    if path in {
        "gr00t/rl/scripts/README.md",
        "gr00t/rl/scripts/a2_piper_v14_reachability_map.py",
        "gr00t/rl/scripts/generate_1000_doors.sh",
        "gr00t/rl/scripts/generate_door_assets.py",
    }:
        return {
            "classification": "no-op",
            "decision": "Offline generation/legacy reachability/documentation site is not the active procedural pull training path.",
            "source_action": "preserve_existing_tooling",
            "implementation_target": "none",
            "verification": "Resolved pull scenario proves runtime procedural spawning; no offline regeneration is required.",
        }

    raise RuntimeError(
        f"Unclassified direction-site path {path}:{line_number} for queries {query_ids}: {content}"
    )


def main() -> None:
    head = _git("rev-parse", "HEAD").strip()
    if head != EXPECTED_BASE:
        raise RuntimeError(f"Manifest must be generated at base {EXPECTED_BASE}; got {head}.")

    query_rows: dict[str, list[tuple[str, int, str]]] = {}
    sites: dict[tuple[str, int], dict[str, object]] = {}
    for query_id, pattern, paths in QUERIES:
        rows = _query(query_id, pattern, paths)
        query_rows[query_id] = rows
        for path, line_number, content in rows:
            key = (path, line_number)
            if key in sites and sites[key]["content"] != content:
                raise RuntimeError(f"Inconsistent content for {path}:{line_number}.")
            site = sites.setdefault(
                key,
                {"path": path, "line": line_number, "content": content, "matched_queries": []},
            )
            site["matched_queries"].append(query_id)

    file_cache: dict[str, list[str]] = {}
    records = []
    for index, ((path, line_number), site) in enumerate(sorted(sites.items()), start=1):
        query_ids = tuple(site["matched_queries"])
        decision = _decision(path, line_number, str(site["content"]), query_ids)
        records.append(
            {
                "site_id": f"D{index:04d}",
                "path": path,
                "line": line_number,
                "symbol": _nearest_symbol(path, line_number, file_cache),
                "matched_queries": list(query_ids),
                "content": site["content"],
                "line_sha256": hashlib.sha256(str(site["content"]).encode("utf-8")).hexdigest(),
                **decision,
            }
        )

    invalid = [row for row in records if row["classification"] not in {"change", "no-op", "test"}]
    if invalid:
        raise RuntimeError(f"Manifest has invalid classifications: {invalid[:3]}")
    counts = Counter(row["classification"] for row in records)
    files = sorted({row["path"] for row in records})
    file_blobs = {path: _git("hash-object", path).strip() for path in files}

    payload = {
        "schema": "a2_piper_pull_v0_direction_site_manifest_v1",
        "created_at_hkt": dt.datetime.now(dt.timezone(dt.timedelta(hours=8))).strftime("%Y-%m-%d %H:%M HKT"),
        "plan_id": PLAN_ID,
        "source_commit": head,
        "source_tree": _git("rev-parse", "HEAD^{tree}").strip(),
        "status": "CLOSED_STATIC",
        "formal_implementation_gate": "PASS",
        "allowed_classifications": ["change", "no-op", "test"],
        "unclassified_count": 0,
        "query_counts_raw": {query_id: len(rows) for query_id, rows in query_rows.items()},
        "raw_match_count": sum(len(rows) for rows in query_rows.values()),
        "unique_site_count": len(records),
        "classification_counts": dict(sorted(counts.items())),
        "file_count": len(files),
        "file_blobs": file_blobs,
        "classification_policy": {
            "push_and_v21b": "Preserve existing configs, evidence code, and institution branches; pull uses isolated counterparts.",
            "shared_asset": "Only IO-aware single grasp_target placement changes; hinge/handle/latch mechanics remain no-op.",
            "pull_env": "Direction-sensitive semantics move through an immutable direction contract and pull env path.",
            "thresholds": "All new task thresholds remain report_only until measured.",
            "effort": "Implicit-actuator effort remains ESTIMATE_ONLY.",
        },
        "queries": [
            {"query_id": query_id, "pattern": pattern, "paths": list(paths)}
            for query_id, pattern, paths in QUERIES
        ],
        "sites": records,
    }
    OUTPUT.write_text(json.dumps(payload, indent=2, sort_keys=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
