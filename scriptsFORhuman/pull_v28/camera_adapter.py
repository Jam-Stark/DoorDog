"""Pull event adapter around the received v28 camera geometry/metrics code."""
from __future__ import annotations
import importlib.util
from pathlib import Path

HERE = Path(__file__).resolve().parent
REFERENCE = HERE / "mainline_reference/20260913/files/scriptsFORhuman/v28"
DEFAULT_RIG = HERE.parents[1] / "gr00t/rl/data/robots/a2_piper_v28_merged_20260909/config/camera_rig.json"
DEFAULT_NATIVE = REFERENCE / "camera/d435_native_sim_parameters_20260907.json"
spec = importlib.util.spec_from_file_location("pull_v28_reference_camera_metrics", REFERENCE / "v28_camera_metrics.py")
metrics = importlib.util.module_from_spec(spec)
spec.loader.exec_module(metrics)
CAMERA_KEYS = tuple(dict.fromkeys((*metrics.REQUIRED, *metrics.SCALARS, "stage_buf", "env_id", "step_index",
    "first_episode_active", "episode_index", "v28_post_release", "v28_crossing_yaw_deg", "v28_vy_cmd_at_clip")))


def select_camera(row):
    result = {key: row[key] for key in CAMERA_KEYS}
    for key, shape in metrics.REQUIRED.items():
        metrics.vector(result, key, shape)
    for key in metrics.SCALARS:
        metrics.scalar(result, key)
    if result["v28_crossing_yaw_deg"] is not None:
        metrics.scalar(result, "v28_crossing_yaw_deg")
    if not isinstance(result["v28_post_release"], bool) or not isinstance(result["v28_vy_cmd_at_clip"], bool):
        raise ValueError("camera release/clip fields must be bool")
    if row["v28_crossing_event"] != "E6_PATH_REVERSAL_ENTRY":
        raise ValueError("pull camera crossing must name existing E6 event")
    return result


def summarize(rows, trace, rig=DEFAULT_RIG, native=DEFAULT_NATIVE):
    # Read the huge trace only in the caller. Feed compact in-memory records to
    # the unmodified reference reducer; retain its geometry and 26 plan fields.
    if not rows:
        raise ValueError("v28 all-stage trace has no camera samples")
    if not native.is_file():
        raise FileNotFoundError(f"required delivered native camera calibration missing: {native}")
    original = metrics.parse_rows
    metrics.parse_rows = lambda path: rows
    metrics.NATIVE_PARAMETERS = native
    try:
        result = metrics.reduce(trace, rig)
    finally:
        metrics.parse_rows = original
    result["orientation_definition"] = "Bearings relative to trunk yaw; crossing yaw latched at pull E6_PATH_REVERSAL_ENTRY, once per episode."
    result["release_definition"] = "Persistent pull release_event, no bilateral contact, Stage4 C/D; no mainline release gate."
    checks = {}

    def check(name, value, threshold, samples):
        checks[name] = {"value": value, "upper_bound": threshold, "samples": samples,
                        "met": None if value is None else value <= threshold}

    # Frozen report-only thresholds, mainline plan section7; absent events are
    # unavailable checks. The 26 telemetry fields are not 26 invented gates.
    for stage, threshold in ((2,105.), (3,250.), (4,150.), (5,90.)):
        block = result["stages"].get(str(stage))
        check(f"stage{stage}_wrist_speed_p95_deg_s", None if block is None else block["wrist_cam_ang_speed_deg_s"]["p95"],
              threshold, 0 if block is None else block["records"])
    for stage, threshold in ((0,1.5), (5,1.5), (2,2.5), (4,2.5)):
        block = result["stages"].get(str(stage))
        stats = None if block is None else block["arm_j6_reversals"]
        check(f"stage{stage}_j6_reversals_per_s", None if stats is None else stats["per_s"],
              threshold, 0 if stats is None else stats["consecutive_pairs"])
    for stage in (0,5):
        selected = [row for row in rows if row["stage_buf"] == stage]
        block = result["stages"].get(str(stage))
        check(f"stage{stage}_arm_l1_p95_rad", None if block is None else block["arm_posture_l1_rad"]["p95"], .5, len(selected))
        share = None if not selected else sum(abs(row["arm_joint_pos"][5] - 1.57) > .3 for row in selected) / len(selected)
        check(f"stage{stage}_j6_abs_dev_gt_0p3_share", share, .05, len(selected))
    ret = result["overall"]["post_release_return_time_s"]
    for quantile, threshold in (("p50",2.), ("p95",4.)):
        check(f"post_release_return_{quantile}_s", ret["observed"][quantile], threshold, ret["observed_episodes"])
    available = [value["met"] for value in checks.values() if value["met"] is not None]
    if not available:
        status = "NOT_OBSERVED"
    elif all(available) and len(available) == len(checks) and ret["right_censored_episodes"] == 0:
        status = "CAMERA_MET"
    elif any(available):
        status = "CAMERA_PARTIAL"
    else:
        status = "CAMERA_UNMET"
    result.update(status=status, report_only=True, checks=checks,
        available_checks=len(available), total_checks=len(checks),
        classification="MET requires all frozen checks observed and met with no censored return; PARTIAL means some observed checks met or evidence incomplete; UNMET means all observed checks failed. No added training gate.")
    return result
