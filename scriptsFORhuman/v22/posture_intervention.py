"""P0-B frozen causal posture intervention over ordinary/height/hard manifests."""

from __future__ import annotations

import argparse
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from ._v22_common import REPO_ROOT, V22_ARTIFACT_ROOT, V22Error, read_json, write_json
from .m22 import load_scenario_manifest
from .posture_probe import build_probe_argv, run_probe


ROOT = REPO_ROOT / V22_ARTIFACT_ROOT / "p0b_posture_intervention"
OUTPUT = REPO_ROOT / V22_ARTIFACT_ROOT / "locks/V22_POSTURE_CAUSAL_INTERVENTION.json"
INTERVENTIONS = ("legacy", "zero", "clamp", "height_nominal")
MANIFESTS = ("ordinary16", "height16", "hard16")


def _v21_selector(scenario: dict, topology: str) -> list[str]:
    manifest = scenario["manifest"]
    return [
        "++env.config.a2_v21B_signed_probe_scenarios_enabled=true",
        f"++env.config.a2_v21B_census_topology={topology}",
        f"++env.config.a2_v21B_scenario_manifest_path={scenario['path']}",
        f"++env.config.a2_v21B_scenario_manifest_sha256={scenario['manifest_sha256']}",
        f"++env.config.a2_v21B_scenario_manifest_file_sha256={scenario['file_sha256']}",
        f"++env.config.a2_v21B_canonical_manifest_sha256={scenario['canonical_manifest_sha256']}",
        f"++env.config.a2_v21B_scenario_manifest_source_checkpoint_sha256={manifest['source_checkpoint_sha256']}",
        f"++env.config.a2_v21B_scenario_manifest_source_lock_sha256={manifest['source_lock_sha256']}",
        f"++env.config.a2_v21B_scenario_manifest_source_config_sha256={manifest['source_config_sha256']}",
        f"++env.config.a2_v21B_scenario_manifest_materialization_sha256={scenario['materialization_sha256']}",
        f"++env.config.a2_v21B_scenario_manifest_json_sha256={scenario['manifest_json_sha256']}",
        f"++env.config.a2_v21B_scenario_manifest_json={scenario['manifest_json']!r}",
    ]


def _height_selector(root: Path) -> list[str]:
    path = root / "height16_manifest.json"
    rows = [
        {
            "scenario_id": f"height16_r{index:02d}",
            "handle_height_m": round(0.85 + index * (1.10 - 0.85) / 15, 6),
            "door_weight_kg": 120.0,
            "hinge_max_force_nm": 10.0,
            "hinge_damping_native": 50.0,
            "hinge_stiffness_native": 6.0,
            "bucket": "H0",
        }
        for index in range(16)
    ]
    manifest_name = "v22_p0b_height16"
    manifest_sha = write_json(
        path,
        {
            "schema": "a2_piper_base_v22_scenario_manifest_v1",
            "manifest_name": manifest_name,
            "plan_id": "base_v22_posture_clearance_force_routing_v3",
            "execution_id": "base_v22_execution_v3",
            "purpose": "P0-B height-conditioned causal intervention",
            "rows": rows,
        },
    )
    return [
        "++env.config.a2_v22_scenario_manifest_enabled=true",
        f"++env.config.a2_v22_scenario_manifest_path='{path}'",
        f"++env.config.a2_v22_scenario_manifest_sha256={manifest_sha}",
        f"++env.config.a2_v22_scenario_manifest_name='{manifest_name}'",
    ]


def _analyze_run(root: Path) -> dict:
    metrics = read_json(root / "metrics_eval.json")
    records = read_json(root / "a2_v14_per_env_records.json")
    trace = read_json(root / "stage2_step_trace.json")
    terminal = {int(row["env_id"]): row for row in metrics["episode_terminal_diagnostics"]}
    need_active: dict[int, bool] = {env_id: False for env_id in range(16)}
    for row in trace:
        env_id = int(row["env_id"])
        if int(row["stage_buf"]) in (3, 4) and row.get("v22_posture_need_active") is True:
            need_active[env_id] = True
    record_by_env = {int(row["env_id"]): row for row in records}
    return {
        "goal_of_16": sum(1 for value in metrics["episode_goal_reached"] if value is True),
        "supported_crossing_of_16": sum(1 for row in records if row.get("crossing_while_holding") is True),
        "per_env": {
            str(env_id): {
                "goal": bool(metrics["episode_goal_reached"][env_id]),
                "max_stage": int(metrics["episode_max_stage_reached"][env_id]),
                "supported_crossing": record_by_env[env_id].get("crossing_while_holding") is True,
                "clearance_success": terminal[env_id]["v22_clearance_success"],
                "posture_need_active_during_open_or_swing": need_active[env_id],
            }
            for env_id in range(16)
        },
    }


def _independent_label(legacy: dict, zero: dict) -> str:
    legacy_success = legacy["goal"] or legacy["supported_crossing"]
    zero_success = zero["goal"] or zero["supported_crossing"]
    if legacy_success and not zero_success:
        return "POSTURE_NEEDED"
    if zero_success and (not legacy_success or zero["max_stage"] >= legacy["max_stage"]):
        return "POSTURE_NOT_NEEDED"
    return "AMBIGUOUS_NO_SUCCESS_CONTRAST"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gpus", type=int, nargs="+", required=True)
    args = parser.parse_args()
    if ROOT.exists():
        raise V22Error(f"P0-B root must be fresh: {ROOT}")
    ROOT.mkdir(parents=True)

    atlas = read_json(REPO_ROOT / V22_ARTIFACT_ROOT / "locks/V22_POSTURE_ATLAS.json")
    nominal_pitch = atlas["nominal_pitch_rad"]
    nominal_roll = atlas["nominal_roll_rad"]
    if any(float(value) != 0.0 for value in nominal_pitch + nominal_roll):
        raise V22Error("P0-B height_nominal runner currently requires the frozen all-zero posture atlas")
    scenario = load_scenario_manifest()
    selectors = {
        "ordinary16": _v21_selector(scenario, "canonical16"),
        "hard16": _v21_selector(scenario, "heavy16"),
        "height16": _height_selector(ROOT),
    }
    jobs = [(manifest, intervention) for manifest in MANIFESTS for intervention in INTERVENTIONS]

    def _one(index_job):
        index, (manifest, intervention) = index_job
        root = ROOT / manifest / intervention
        mode = "zero" if intervention == "height_nominal" else intervention
        argv = build_probe_argv(
            output_dir=root,
            eval_name=f"v22_P0B_{manifest}_{intervention}",
            seed=0,
            intervention=mode,
            clamp_rad=(0.15, 0.10) if mode == "clamp" else None,
            nominal_heights=atlas["nominal_heights_m"],
            nominal_pitch=nominal_pitch,
            nominal_roll=nominal_roll,
            wrench_threshold_n=atlas["directional_wrench_threshold_n"],
            tracking_p90_rad=atlas["arm_tracking_error_p90_rad"],
            workspace_margin_threshold=atlas["workspace_margin_threshold"],
            include_height_linspace=False,
            selector_overrides=selectors[manifest],
        )
        run_probe(argv, gpu=args.gpus[index % len(args.gpus)], output_dir=root)
        return manifest, intervention, _analyze_run(root)

    results: dict[str, dict[str, dict]] = {manifest: {} for manifest in MANIFESTS}
    with ThreadPoolExecutor(max_workers=len(args.gpus)) as pool:
        for manifest, intervention, result in pool.map(_one, list(enumerate(jobs))):
            results[manifest][intervention] = result

    labels = []
    for manifest in MANIFESTS:
        legacy = results[manifest]["legacy"]["per_env"]
        zero = results[manifest]["zero"]["per_env"]
        for env_id in range(16):
            label = _independent_label(legacy[str(env_id)], zero[str(env_id)])
            labels.append(
                {
                    "manifest": manifest,
                    "env_id": env_id,
                    "label": label,
                    "posture_need_predicted": legacy[str(env_id)][
                        "posture_need_active_during_open_or_swing"
                    ],
                    "legacy": legacy[str(env_id)],
                    "zero": zero[str(env_id)],
                }
            )
    labeled = [row for row in labels if row["label"] != "AMBIGUOUS_NO_SUCCESS_CONTRAST"]
    predicted = [row for row in labeled if row["posture_need_predicted"]]
    true_positive = sum(1 for row in predicted if row["label"] == "POSTURE_NEEDED")
    false_positive = sum(1 for row in predicted if row["label"] == "POSTURE_NOT_NEEDED")
    positives = sum(1 for row in labeled if row["label"] == "POSTURE_NEEDED")
    payload = {
        "schema": "a2_piper_base_v22_posture_causal_intervention_v1",
        "plan_id": "base_v22_posture_clearance_force_routing_v3",
        "execution_id": "base_v22_execution_v3",
        "node": "P0-B",
        "status": "P0_B_COMPLETE_INDEPENDENT_LABELS" if labeled else "P0_B_INCONCLUSIVE_NO_LABELS",
        "height_nominal_intervention": (
            "identical to zero because the frozen P0-C atlas selected 0 rad pitch/roll at every height"
        ),
        "results": results,
        "labels": labels,
        "posture_need_precision": (
            true_positive / (true_positive + false_positive)
            if true_positive + false_positive
            else None
        ),
        "posture_need_recall": true_positive / positives if positives else None,
        "label_counts": {
            "POSTURE_NEEDED": positives,
            "POSTURE_NOT_NEEDED": sum(
                1 for row in labeled if row["label"] == "POSTURE_NOT_NEEDED"
            ),
            "AMBIGUOUS_NO_SUCCESS_CONTRAST": len(labels) - len(labeled),
        },
        "precision_binding_state": (
            "INDEPENDENT_LABELS_AVAILABLE; overall posture gates remain "
            "REPORT_ONLY_INSUFFICIENT_DENOMINATOR"
        ),
    }
    write_json(OUTPUT, payload)
    print(json.dumps({"status": payload["status"], "label_counts": payload["label_counts"]}, indent=2))
    return 0 if labeled else 2


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except V22Error as exc:
        raise SystemExit(f"V22 P0-B FAIL: {exc}")
