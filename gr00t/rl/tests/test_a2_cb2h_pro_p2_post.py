from __future__ import annotations

import json
from pathlib import Path
import subprocess

import pytest

from gr00t.rl.scripts import run_a2_cb2h_pro_p2_post as post
from gr00t.rl.scripts import run_a2_cb2h_pro_p2 as p2
from gr00t.rl.scripts import run_a2_student_eval_v19 as student_eval
from gr00t.rl.trl.modules import vision_actor_critic_modules_p2_recurrent as actor_modules
from omegaconf import OmegaConf


def _compose_evaluator_contract(overrides: list[str]):
    from hydra import compose, initialize_config_dir

    with initialize_config_dir(
        version_base="1.1", config_dir=str((student_eval.REPO_ROOT / "gr00t/rl/config").resolve())
    ):
        return compose(config_name="base_eval", overrides=overrides)


def _telemetry_payload(*, records: int = 2, started: int = 1, ended: int | None = None) -> dict:
    identity = post._gpu_identity()
    ended = (records - 1) * 1_000_000_000 + started if ended is None else ended
    samples = []
    for index in range(records):
        samples.append(
            {
                **identity,
                "memory_used_mib": 1000.0 + index,
                "memory_total_mib": 48000.0,
                "utilization_gpu_pct": 10.0,
                "power_draw_w": 100.0,
                "temperature_c": 50.0,
                "sample_time_ns": started + index * 1_000_000_000,
            }
        )
    return {
        "schema": p2.P2_TELEMETRY_SCHEMA,
        "record_count": records,
        "records": samples,
        "peak_vram_mib": max(item["memory_used_mib"] for item in samples),
        "process_started_ns": started,
        "process_ended_ns": ended,
        "sample_interval_s": 5.0,
        "max_adjacent_gap_s": 15.0,
        "gpu_identity": identity,
    }


def _minimal_pair(tmp_path: Path) -> dict:
    root = tmp_path / "pair"
    common = root / "common_init"
    common.mkdir(parents=True)
    (root / "serial").mkdir()
    artifact = common / "b1_common_init.pt"
    artifact.write_bytes(b"common-init")
    branches = {}
    for branch in post.BRANCHES:
        branch_root = root / branch
        branch_root.mkdir()
        checkpoint = branch_root / "model_step_000500.pt"
        config = branch_root / "config.yaml"
        checkpoint.write_bytes(branch.encode())
        config.write_text("branch: " + branch, encoding="utf-8")
        branches[branch] = {
            "architecture": "fixture-" + branch,
            "root": str(branch_root),
            "manifest_ref": {"path": str(branch_root / post.BRANCH_MANIFEST_FILENAME), "sha256": "a" * 64, "size": 1},
            "final_checkpoint": {"path": str(checkpoint), "sha256": "b" * 64, "global_step": 500},
            "final_config": {"path": str(config), "sha256": "c" * 64},
            "common_init": {"artifact": {"path": str(artifact), "sha256": "d" * 64}},
            "teacher": {},
        }
        (branch_root / post.BRANCH_MANIFEST_FILENAME).write_bytes(b"x")
    return {"pair_root": str(root), "branches": branches, "common_init": {"artifact": {"path": str(artifact), "sha256": "d" * 64}}, "pair_manifest": {"path": str(root / "serial/pair_manifest.json"), "sha256": "e" * 64}, "content_sha256": "f" * 64}


def _formal_job(output_root: Path) -> post.FormalJob:
    pair = post.validate_pair_manifest()
    identity = pair["branches"]["b1"]
    return post.FormalJob(
        "b1",
        "replicate_01",
        output_root,
        Path(identity["final_checkpoint"]["path"]),
        identity["final_checkpoint"]["sha256"],
        Path(identity["final_config"]["path"]),
        identity["final_config"]["sha256"],
        ("fake",),
    )


def _record(env_id: int, *, stage: int, case: dict | None = None, contact: bool = False, overspeed: bool = False, over_force: bool = False, yaw: float = 0.1, lateral: float = 0.2) -> dict:
    return {
        "env_id": env_id,
        "episode_index": 0,
        "max_stage": stage,
        "goal_reached": stage >= 5,
        "terminal_reason": "upper_dof_overspeed" if overspeed else "stage_overtime",
        "reward": -float(env_id),
        "randomized_case": case or {"door_hinge_drive_max_force": 1.0, "door_handle_drive_max_force": 2.0, "door_handle_height": 0.8, "door_weight": 100.0},
        "event_metrics": {
            "doorframe_contact": contact,
            "doorframe_penalty": -1.0 if contact else 0.0,
            "overspeed": overspeed,
            "overspeed_penalty": -1.0 if overspeed else 0.0,
            "over_force": over_force,
            "over_force_penalty": -1.0 if over_force else 0.0,
            "root_yaw_abs": yaw,
            "root_y_abs": lateral,
        },
        "terminal_diagnostic": {
            "root_yaw": yaw,
            "root_pos_rel": [0.0, lateral, 0.0],
            "reward_episode_sums_unit": "episode-sum",
            "over_force": over_force,
            "reward_episode_sums": {
                "penalty_door_frame_contact": -1.0 if contact else 0.0,
                "penalty_dof_overspeed": -1.0 if overspeed else 0.0,
                "penalty_a2_stage2_over_force": -1.0 if over_force else 0.0,
                "penalty_a2_stage3_stage4_over_force": 0.0,
            },
        },
    }


def _records(branch: str, replicate_id: str, *, stage: int = 0, contact_count: int = 0, overspeed_count: int = 0, over_force_count: int = 0, yaw: float = 0.1, lateral: float = 0.2) -> dict:
    return {
        "replicate_id": replicate_id,
        "episodes": [
            _record(i, stage=stage, contact=i < contact_count, overspeed=i < overspeed_count, over_force=i < over_force_count, yaw=yaw, lateral=lateral)
            for i in range(16)
        ],
    }


def _pooled(branch: str, *, stage: int = 1) -> list[dict]:
    return [_records(branch, replicate_id, stage=stage) for replicate_id in post.REPLICATE_IDS]


def _set_event_count(runs: list[dict], field: str, count: int) -> None:
    for index, episode in enumerate(episode for run in runs for episode in run["episodes"]):
        value = index < count
        episode["event_metrics"][field] = value
        if field == "doorframe_contact":
            episode["event_metrics"]["doorframe_penalty"] = -1.0 if value else 0.0
        elif field == "overspeed":
            episode["event_metrics"]["overspeed_penalty"] = -1.0 if value else 0.0
        elif field == "over_force":
            episode["event_metrics"]["over_force_penalty"] = -1.0 if value else 0.0


def test_retry3_pair_is_read_only_validated_and_exact():
    if not post.PAIR_ROOT.is_dir():
        pytest.skip("pinned retry3 pair is unavailable")
    result = post.validate_pair_manifest()
    assert result["pair_manifest"]["sha256"] == post.PAIR_MANIFEST_SHA256
    assert result["branches"]["b1"]["final_checkpoint"]["global_step"] == 500
    assert result["branches"]["b2"]["architecture"] == "C-B2H-DUALRAW-SHAREDENC-TOEIN20-V19-P2"


def test_build_plan_has_exact_six_packed_forward_mode_and_fresh_root(tmp_path: Path):
    pair = post.validate_pair_manifest()
    output = tmp_path / "post"
    plan = post.build_formal_plan(pair, output_root=output)
    assert len(plan.jobs) == 6
    assert [(job.branch, job.replicate_id) for job in plan.jobs] == [(b, r) for b in post.BRANCHES for r in post.REPLICATE_IDS]
    assert all(job.command.count("--student-d435i-forward-mode") == 1 for job in plan.jobs)
    assert all(post._command_arg(job.command, "--student-d435i-forward-mode") == "packed" for job in plan.jobs)
    assert all("--controller" in job.command and "student" in job.command for job in plan.jobs)
    assert not output.exists()


@pytest.mark.parametrize("replacement", [None, "sequential", "packed-extra"])
def test_formal_command_packed_mode_is_required_exactly_once(tmp_path: Path, replacement: str | None):
    pair = post.validate_pair_manifest()
    plan = post.build_formal_plan(pair, output_root=tmp_path / "post")
    job = plan.jobs[0]
    command = list(job.command)
    index = command.index("--student-d435i-forward-mode")
    if replacement is None:
        del command[index : index + 2]
    else:
        command[index + 1] = replacement
    if replacement == "packed-extra":
        command.extend(("--student-d435i-forward-mode", "packed"))
    tampered = post.FormalJob(
        job.branch,
        job.replicate_id,
        job.output_root,
        job.checkpoint,
        job.checkpoint_sha256,
        job.config,
        job.config_sha256,
        tuple(command),
    )
    with pytest.raises(post.P2PostBlocked):
        post._validate_formal_command(tampered)


def test_formal_commands_pin_evaluator_override_and_real_p2_actor_contract(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """Exercise command parsing, evaluator override composition, and both real P2 actors on CPU."""
    pytest.importorskip("torch")
    from gr00t.rl.tests import test_a2_cb2h_pro_p2 as p2_cpu_tests

    pair = post.validate_pair_manifest()
    plan = post.build_formal_plan(pair, output_root=tmp_path / "post")
    seen_branches: set[str] = set()
    adjacent_configs = {}
    for job in plan.jobs:
        mode = post._command_arg(job.command, "--student-d435i-forward-mode")
        assert mode == "packed"
        overrides = student_eval.build_hydra_overrides(
            "formal",
            job.output_root,
            checkpoint=job.checkpoint,
            controller=post._command_arg(job.command, "--controller"),
            student_d435i_forward_mode=mode,
        )
        packed_overrides = [
            item
            for item in overrides
            if item.startswith("+algo.config.actor.view_contract.d435i_forward_mode=")
        ]
        assert packed_overrides == ["+algo.config.actor.view_contract.d435i_forward_mode=packed"]
        evaluator_config = _compose_evaluator_contract(overrides)
        assert evaluator_config.algo.config.actor.view_contract.d435i_forward_mode == "packed"

        adjacent = OmegaConf.load(job.config)
        p2.validate_composed_config(adjacent, job.branch)
        post._validate_adjacent_p2_actor_contract(job.config, job.branch)
        assert adjacent.algo.config.actor.view_contract.d435i_forward_mode == "packed"
        seen_branches.add(job.branch)
        adjacent_configs[job.branch] = adjacent

    # Instantiate the actual P2 actor classes from the adjacent saved configs;
    # only the expensive encoder factory is replaced by the existing CPU test
    # implementation.  Thus the command, config, view contract, and topology
    # all flow into the same constructor under test.
    monkeypatch.setattr(actor_modules, "instantiate", p2_cpu_tests._fake_instantiate)
    for branch, config in adjacent_configs.items():
        meta_dim = int(config.algo.config.actor.view_contract.camera_meta_dim)
        env_config = OmegaConf.create(OmegaConf.to_container(config, resolve=False))
        env_config.robot.algo_obs_dim_dict = {
            "actor_obs": 81,
            "vision_obs": 384 * 216 * 6,
            "camera_meta": meta_dim,
        }
        if branch == "b2":
            env_config.robot.algo_obs_dim_dict["context_vision_obs"] = 136 * 384 * 3
        actor_cls = getattr(
            actor_modules,
            "DualD435VisionRecurrentActor" if branch == "b1" else "DualD435HeadVisionRecurrentActor",
        )
        actor = actor_cls(
            env_config,
            config.algo.config,
            config.algo.config.actor.backbone,
            module_dim_dict={"actor_obs": -1},
            view_contract=OmegaConf.to_container(config.algo.config.actor.view_contract, resolve=True),
            running_mean_std=True,
        )
        state_keys = tuple(actor.state_dict().keys())
        state_count = len(state_keys)
        assert actor.d435i_forward_mode == "packed"
        student_eval.validate_student_forward_mode_contract(
            config.algo.config, actor, "packed"
        )
        assert tuple(actor.state_dict().keys()) == state_keys
        assert len(actor.state_dict()) == state_count
        assert "d435i_forward_mode" not in actor.state_dict()
        with pytest.raises(AttributeError):
            actor.d435i_forward_mode = "sequential"
        actor.core.d435i_forward_mode = "sequential"
        with pytest.raises(RuntimeError):
            student_eval.validate_student_forward_mode_contract(config.algo.config, actor, "packed")
        actor.core.d435i_forward_mode = None
        with pytest.raises(RuntimeError):
            student_eval.validate_student_forward_mode_contract(config.algo.config, actor, "packed")
        actor.core.d435i_forward_mode = "packed"
        if branch == "b1":
            assert not hasattr(actor, "head_vision_module")
        else:
            assert hasattr(actor, "head_vision_module")
    assert seen_branches == set(post.BRANCHES)


def test_pair_manifest_hash_drift_fails_closed():
    with pytest.raises(post.P2PostBlocked):
        post.validate_pair_manifest(pair_manifest_sha256="0" * 64)


def test_case_mismatch_across_replicates_is_rejected(tmp_path: Path):
    pair = _minimal_pair(tmp_path)
    artifacts = {branch: [_records(branch, replicate) for replicate in post.REPLICATE_IDS] for branch in post.BRANCHES}
    artifacts["b2"][1]["episodes"][3]["randomized_case"]["door_weight"] = 101.0
    with pytest.raises(post.P2PostBlocked):
        post.adjudicate_formal_records(pair, artifacts)


def test_record_event_metrics_requires_exact_episode_sum_and_safety_types():
    record = _record(0, stage=0)
    assert post._record_event_metrics(record, "fixture")["over_force"] is False
    record["terminal_diagnostic"]["reward_episode_sums_unit"] = "per-step"
    with pytest.raises(post.P2PostBlocked):
        post._record_event_metrics(record, "fixture")
    record["terminal_diagnostic"]["reward_episode_sums_unit"] = "episode-sum"
    record["terminal_diagnostic"].pop("over_force")
    with pytest.raises((post.P2PostBlocked, TypeError)):
        post._record_event_metrics(record, "fixture")
    record["terminal_diagnostic"]["over_force"] = 1
    with pytest.raises(TypeError):
        post._record_event_metrics(record, "fixture")
    record["terminal_diagnostic"]["over_force"] = False
    record["terminal_diagnostic"]["root_yaw"] = float("nan")
    with pytest.raises((ValueError, post.P2PostBlocked)):
        post._record_event_metrics(record, "fixture")
    record["terminal_diagnostic"]["root_yaw"] = 0.1
    record["terminal_diagnostic"]["root_pos_rel"] = [0.0, 0.2]
    with pytest.raises(post.P2PostBlocked):
        post._record_event_metrics(record, "fixture")
    record["terminal_diagnostic"]["root_pos_rel"] = [0.0, 0.2, 0.0]
    record["terminal_diagnostic"]["reward_episode_sums"].pop("penalty_dof_overspeed")
    with pytest.raises(post.P2PostBlocked):
        post._record_event_metrics(record, "fixture")


def test_effectiveness_stage0_gate_selects_b2(tmp_path: Path):
    pair = _minimal_pair(tmp_path)
    artifacts = {
        "b1": [_records("b1", r, stage=0) for r in post.REPLICATE_IDS],
        "b2": [_records("b2", r, stage=1) for r in post.REPLICATE_IDS],
    }
    result = post.adjudicate_formal_records(pair, artifacts)
    assert result["effectiveness"]["stage0_failures_reduction"]["pass"] is True
    assert result["decision"] == post.DECISION_SELECT_B2


def test_stage0_reduction_exact_four_passes(tmp_path: Path):
    pair = _minimal_pair(tmp_path)
    b1 = _pooled("b1", stage=1)
    b2 = _pooled("b2", stage=1)
    for episode in b1[0]["episodes"][:4]:
        episode["max_stage"] = 0
    result = post.adjudicate_formal_records(pair, {"b1": b1, "b2": b2})
    gate = result["effectiveness"]["stage0_failures_reduction"]
    assert gate["reduction"] == 4
    assert gate["pass"] is True


def test_effectiveness_mean_stage_gate_exact_boundary(tmp_path: Path):
    pair = _minimal_pair(tmp_path)
    artifacts = {
        "b1": [_records("b1", r, stage=1) for r in post.REPLICATE_IDS],
        "b2": [_records("b2", r, stage=1) for r in post.REPLICATE_IDS],
    }
    for run in artifacts["b2"]:
        for episode in run["episodes"]:
            episode["max_stage"] = 2
    result = post.adjudicate_formal_records(pair, artifacts)
    assert result["effectiveness"]["paired_mean_max_stage"]["pass"] is True
    assert result["decision"] == post.DECISION_SELECT_B2


def test_mean_stage_delta_exact_point_two_is_accepted(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    pair = _minimal_pair(tmp_path)
    artifacts = {"b1": _pooled("b1"), "b2": _pooled("b2")}

    def summary(records):
        branch = records[0]["branch"]
        return {
            "episode_count": 48,
            "goal_count": 0,
            "stage0_count": 0,
            "stage2_plus_count": 0,
            "doorframe_contact_count": 0,
            "overspeed_count": 0,
            "over_force_count": 0,
            "mean_doorframe_penalty": 0.0,
            "mean_overspeed_penalty": 0.0,
            "mean_over_force_penalty": 0.0,
            "mean_max_stage": 1.0 if branch == "b1" else 1.2,
            "mean_reward": 0.0,
            "mean_abs_root_yaw": 0.0,
            "mean_abs_root_y": 0.0,
        }

    monkeypatch.setattr(post, "_branch_summary", summary)
    result = post.adjudicate_formal_records(pair, artifacts)
    gate = result["effectiveness"]["paired_mean_max_stage"]
    assert gate["delta"] == pytest.approx(0.20)
    assert gate["pass"] is True


def test_doorframe_baseline_zero_does_not_create_relative_effectiveness(tmp_path: Path):
    pair = _minimal_pair(tmp_path)
    artifacts = {
        "b1": [_records("b1", r, stage=1, contact_count=0) for r in post.REPLICATE_IDS],
        "b2": [_records("b2", r, stage=1, contact_count=0) for r in post.REPLICATE_IDS],
    }
    result = post.adjudicate_formal_records(pair, artifacts)
    gate = result["effectiveness"]["doorframe_contact_reduction"]
    assert gate["pass"] is False
    assert gate["reason"] == "baseline_zero_no_relative_reduction"


def test_doorframe_reduction_exact_twenty_percent_includes_baseline_zero_rule(tmp_path: Path):
    pair = _minimal_pair(tmp_path)
    b1 = _pooled("b1")
    b2 = _pooled("b2")
    _set_event_count(b1, "doorframe_contact", 20)
    _set_event_count(b2, "doorframe_contact", 16)
    result = post.adjudicate_formal_records(pair, {"b1": b1, "b2": b2})
    gate = result["effectiveness"]["doorframe_contact_reduction"]
    assert gate["ratio"] == pytest.approx(0.20)
    assert gate["pass"] is True


@pytest.mark.parametrize("field", ["stage2_plus_count", "overspeed_count", "over_force_count"])
def test_each_count_safety_gate_can_select_b1(tmp_path: Path, field: str):
    pair = _minimal_pair(tmp_path)
    kwargs = {"stage": 1, "contact_count": 0, "overspeed_count": 0, "over_force_count": 0}
    b1_kwargs = dict(kwargs)
    b2_kwargs = dict(kwargs)
    if field == "stage2_plus_count":
        b1_kwargs["stage"] = 2
        b2_kwargs["stage"] = 1
        for run in (b1_kwargs,):
            run["stage"] = 2
    elif field == "overspeed_count":
        b2_kwargs["overspeed_count"] = 16
    else:
        b2_kwargs["over_force_count"] = 16
    artifacts = {
        "b1": [_records("b1", r, **b1_kwargs) for r in post.REPLICATE_IDS],
        "b2": [_records("b2", r, **b2_kwargs) for r in post.REPLICATE_IDS],
    }
    result = post.adjudicate_formal_records(pair, artifacts)
    assert result["decision"] == post.DECISION_SELECT_B1
    assert result["safety"][field]["pass"] is False


def test_ten_percent_mean_boundary_passes_and_positive_worsening_fails(tmp_path: Path):
    pair = _minimal_pair(tmp_path)
    good = {"b1": [_records("b1", r, stage=1, yaw=1.0) for r in post.REPLICATE_IDS], "b2": [_records("b2", r, stage=2, yaw=1.1) for r in post.REPLICATE_IDS]}
    assert post.adjudicate_formal_records(pair, good)["safety"]["mean_abs_root_yaw"]["pass"] is True
    bad = {"b1": [_records("b1", r, stage=1, yaw=1.0) for r in post.REPLICATE_IDS], "b2": [_records("b2", r, stage=2, yaw=1.1000001) for r in post.REPLICATE_IDS]}
    assert post.adjudicate_formal_records(pair, bad)["safety"]["mean_abs_root_yaw"]["pass"] is False


@pytest.mark.parametrize(
    ("metric", "summary_key"),
    [("root_yaw_abs", "mean_abs_root_yaw"), ("root_y_abs", "mean_abs_root_y")],
)
def test_yaw_and_lateral_exact_ten_percent_boundary(tmp_path: Path, metric: str, summary_key: str):
    pair = _minimal_pair(tmp_path)
    good_b1 = _pooled("b1", stage=1)
    good_b2 = _pooled("b2", stage=2)
    for runs, value in ((good_b1, 1.0), (good_b2, 1.1)):
        for run in runs:
            for episode in run["episodes"]:
                episode["event_metrics"][metric] = value
    good = post.adjudicate_formal_records(pair, {"b1": good_b1, "b2": good_b2})
    assert good["safety"][summary_key]["pass"] is True
    bad_b2 = _pooled("b2", stage=2)
    for run in bad_b2:
        for episode in run["episodes"]:
            episode["event_metrics"][metric] = 1.1000001
    bad = post.adjudicate_formal_records(pair, {"b1": good_b1, "b2": bad_b2})
    assert bad["safety"][summary_key]["pass"] is False


def test_stage2_plus_decrease_exact_two_allowed_three_fails(tmp_path: Path):
    pair = _minimal_pair(tmp_path)
    allowed_b1 = _pooled("b1", stage=1)
    allowed_b2 = _pooled("b2", stage=1)
    for index, episode in enumerate(ep for run in allowed_b1 for ep in run["episodes"]):
        episode["max_stage"] = 2 if index < 3 else 1
    for index, episode in enumerate(ep for run in allowed_b2 for ep in run["episodes"]):
        episode["max_stage"] = 2 if index < 1 else 1
    allowed = post.adjudicate_formal_records(pair, {"b1": allowed_b1, "b2": allowed_b2})
    assert allowed["safety"]["stage2_plus_count"]["decrease"] == 2
    assert allowed["safety"]["stage2_plus_count"]["pass"] is True

    failing_b1 = _pooled("b1", stage=1)
    failing_b2 = _pooled("b2", stage=1)
    for index, episode in enumerate(ep for run in failing_b1 for ep in run["episodes"]):
        episode["max_stage"] = 2 if index < 4 else 1
    for index, episode in enumerate(ep for run in failing_b2 for ep in run["episodes"]):
        episode["max_stage"] = 2 if index < 1 else 1
    failing = post.adjudicate_formal_records(pair, {"b1": failing_b1, "b2": failing_b2})
    assert failing["safety"]["stage2_plus_count"]["decrease"] == 3
    assert failing["safety"]["stage2_plus_count"]["pass"] is False


@pytest.mark.parametrize("field", ["overspeed", "over_force"])
def test_count_safety_equality_allowed_and_increase_fails(tmp_path: Path, field: str):
    pair = _minimal_pair(tmp_path)
    equal_b1 = _pooled("b1")
    equal_b2 = _pooled("b2")
    _set_event_count(equal_b1, field, 5)
    _set_event_count(equal_b2, field, 5)
    equal = post.adjudicate_formal_records(pair, {"b1": equal_b1, "b2": equal_b2})
    assert equal["safety"][f"{field}_count"]["pass"] is True
    increased_b2 = _pooled("b2")
    _set_event_count(increased_b2, field, 6)
    increased = post.adjudicate_formal_records(pair, {"b1": equal_b1, "b2": increased_b2})
    assert increased["safety"][f"{field}_count"]["pass"] is False


def test_zero_baseline_safety_means_allow_only_zero_candidate(tmp_path: Path):
    pair = _minimal_pair(tmp_path)
    b1 = _pooled("b1", stage=1)
    b2 = _pooled("b2", stage=1)
    for run in b1:
        for episode in run["episodes"]:
            episode["event_metrics"]["root_yaw_abs"] = 0.0
            episode["event_metrics"]["root_y_abs"] = 0.0
    for run in b2:
        for episode in run["episodes"]:
            episode["event_metrics"]["root_yaw_abs"] = 0.0
            episode["event_metrics"]["root_y_abs"] = 0.0
    result = post.adjudicate_formal_records(pair, {"b1": b1, "b2": b2})
    assert result["safety"]["mean_abs_root_yaw"]["pass"] is True
    assert result["safety"]["mean_abs_root_y"]["pass"] is True
    b2[0]["episodes"][0]["event_metrics"]["root_yaw_abs"] = 0.1
    result = post.adjudicate_formal_records(pair, {"b1": b1, "b2": b2})
    assert result["safety"]["mean_abs_root_yaw"]["pass"] is False


def test_telemetry_identity_and_peak_fail_closed():
    payload = _telemetry_payload()
    assert post._validate_post_telemetry(payload)["peak_vram_mib"] == 1001.0
    identity = post._gpu_identity()
    payload["gpu_identity"] = {**identity, "uuid": "wrong"}
    with pytest.raises(post.P2PostBlocked):
        post._validate_post_telemetry(payload)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda value: value.update(records=value["records"][:1], record_count=1),
        lambda value: value.update(sample_interval_s=-5.0),
        lambda value: value.update(process_started_ns=2_000_000_000),
        lambda value: value["records"][0].update(sample_time_ns=value["process_started_ns"] + 1),
        lambda value: value["records"][1].update(sample_time_ns=value["process_ended_ns"] - 1),
        lambda value: value["records"][0].pop("power_draw_w"),
        lambda value: value["records"][0].update(memory_used_mib=float("nan")),
        lambda value: value["records"][0].update(uuid="wrong"),
        lambda value: value.update(peak_vram_mib=999.0),
        lambda value: value["records"][1].update(sample_time_ns=value["records"][0]["sample_time_ns"] + 20_000_000_000),
        lambda value: value.update(record_count=3),
    ],
)
def test_post_telemetry_exact_p2_contract_rejects_tampering(mutate):
    import copy

    payload = _telemetry_payload()
    mutate(payload := copy.deepcopy(payload))
    with pytest.raises(post.P2PostBlocked):
        post._validate_post_telemetry(payload)


def test_run_one_primes_sampler_before_delayed_background_and_exact_validation(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    job = _formal_job(tmp_path / "child")
    events: list[str] = []

    class FakeSampler:
        def __init__(self, _env):
            self.initial_sampled = False

        def sample_once(self):
            events.append("sample_once")
            self.initial_sampled = True

        def start(self):
            assert self.initial_sampled
            events.append("start")

        def stop(self, **kwargs):
            # Model a delayed first background sample: the synchronous sample
            # brackets the process on the left and the stop sample brackets it
            # on the right.  The exact P2 validator must accept the payload.
            events.append("stop")
            started = kwargs["process_started_ns"]
            ended = kwargs["process_ended_ns"]
            payload = _telemetry_payload(started=started - 1_000_000, ended=ended + 1_000_000)
            payload["process_started_ns"] = started
            payload["process_ended_ns"] = ended
            payload["records"][1]["sample_time_ns"] = ended + 1_000_000
            payload["record_count"] = len(payload["records"])
            assert p2.validate_gpu_telemetry(payload) == payload
            return payload

    def fake_run(*args, **kwargs):
        events.append("child")
        job.output_root.mkdir(parents=True)
        job.metrics_path.write_text("{}", encoding="utf-8")
        job.selection_path.write_text("{}", encoding="utf-8")
        return subprocess.CompletedProcess(args[0], 0, "", "")

    monkeypatch.setattr(post, "GpuTelemetrySampler", FakeSampler)
    monkeypatch.setattr(post.subprocess, "run", fake_run)
    telemetry_ref = post._run_one(job, post.build_child_environment({}))

    assert events == ["sample_once", "start", "child", "stop"]
    telemetry = post._load_json(job.output_root / post.TELEMETRY_FILENAME)
    assert p2.validate_gpu_telemetry(telemetry) == telemetry
    assert telemetry_ref["record_count"] == 2


def test_run_one_initial_sample_failure_is_bounded_and_prevents_child_launch(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    job = _formal_job(tmp_path / "child")
    events: list[str] = []

    class FakeSampler:
        def __init__(self, _env):
            pass

        def sample_once(self):
            events.append("sample_once")
            raise RuntimeError("initial sample boom")

        def start(self):
            events.append("start")

    def fail_run(*_args, **_kwargs):
        events.append("child")
        raise AssertionError("child must not launch after initial sampler failure")

    monkeypatch.setattr(post, "GpuTelemetrySampler", FakeSampler)
    monkeypatch.setattr(post.subprocess, "run", fail_run)
    with pytest.raises(post.P2PostBlocked, match="initial GPU telemetry sample failed: initial sample boom"):
        post._run_one(job, post.build_child_environment({}))

    assert events == ["sample_once"]
    failure = json.loads((job.output_root / post.FAILURE_FILENAME).read_text(encoding="utf-8"))
    assert failure["phase"] == "initial_gpu_sample"
    assert "initial sample boom" in failure["telemetry_error"]
    assert "initial sample boom" in (job.output_root / post.PROCESS_STDERR_FILENAME).read_text(encoding="utf-8")


def test_run_one_preserves_exact_validator_error_in_failure_artifact(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    job = _formal_job(tmp_path / "child")

    class FakeSampler:
        def __init__(self, _env):
            pass

        def sample_once(self):
            return None

        def start(self):
            return None

        def stop(self, **_kwargs):
            return _telemetry_payload(records=1)

    def fake_run(*args, **_kwargs):
        job.output_root.mkdir(parents=True)
        return subprocess.CompletedProcess(args[0], 0, "", "")

    monkeypatch.setattr(post, "GpuTelemetrySampler", FakeSampler)
    monkeypatch.setattr(post.subprocess, "run", fake_run)
    with pytest.raises(post.P2PostBlocked) as exc_info:
        post._run_one(job, post.build_child_environment({}))

    expected = "P2 telemetry requires at least two records"
    assert expected in str(exc_info.value)
    failure = json.loads((job.output_root / post.FAILURE_FILENAME).read_text(encoding="utf-8"))
    assert expected in failure["telemetry_error"]


def test_formal_evaluator_artifacts_are_path_hash_and_packed_provenance_checked(tmp_path: Path):
    pair = post.validate_pair_manifest()
    identity = pair["branches"]["b1"]
    output = tmp_path / "b1" / "formal" / "replicate_01"
    output.mkdir(parents=True)
    metrics = {
        "episode_rewards": [-1.0] * 16,
        "episode_goal_reached": [False] * 16,
        "episode_max_stage_reached": [0] * 16,
        "episode_terminal_reasons": ["stage_overtime"] * 16,
        "episode_terminal_diagnostics": [
            {
                "env_id": i,
                "randomized_case": {"door_hinge_drive_max_force": 1.0, "door_handle_drive_max_force": 2.0, "door_handle_height": 0.8, "door_weight": 100.0},
                "root_yaw": 0.1,
                "root_pos_rel": [0.0, 0.2, 0.0],
                "reward_episode_sums_unit": "episode-sum",
                "over_force": False,
                "reward_episode_sums": {"penalty_door_frame_contact": 0.0, "penalty_dof_overspeed": 0.0, "penalty_a2_stage2_over_force": 0.0, "penalty_a2_stage3_stage4_over_force": 0.0},
            }
            for i in range(16)
        ],
    }
    checkpoint = dict(identity["final_checkpoint"], config_path=identity["final_config"]["path"], config_sha256=identity["final_config"]["sha256"], controller="student", policy_tensor_count=599)
    student_eval.seal_formal_selection(
        metrics,
        output,
        checkpoint,
        controller="student",
        teacher_info=student_eval.validate_teacher_identity(),
        experience_info=student_eval.resolve_experience_source(post.REPO_ROOT, "student"),
        case_seed=0,
        replicate_id="replicate_01",
        student_d435i_forward_mode="packed",
    )
    job = post.FormalJob("b1", "replicate_01", output, Path(identity["final_checkpoint"]["path"]), identity["final_checkpoint"]["sha256"], Path(identity["final_config"]["path"]), identity["final_config"]["sha256"], ())
    loaded = post._load_formal_artifacts(job, identity)
    assert len(loaded["episodes"]) == 16
    # Mutate the actual sealed bytes after the initial load; reload must fail
    # on the evaluator-v2 content hash rather than trusting in-memory data.
    metrics_path = job.metrics_path
    metrics_path.write_bytes(metrics_path.read_bytes() + b"\n")
    with pytest.raises(post.P2PostBlocked):
        post._load_formal_artifacts(job, identity)


def test_child_failure_retains_failure_and_stops(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    pair = post.validate_pair_manifest()
    identity = pair["branches"]["b1"]
    job = post.FormalJob("b1", "replicate_01", tmp_path / "child", Path(identity["final_checkpoint"]["path"]), identity["final_checkpoint"]["sha256"], Path(identity["final_config"]["path"]), identity["final_config"]["sha256"], ("fake",))

    class FakeSampler:
        def __init__(self, _env):
            self.records = []

        def sample_once(self):
            return None

        def start(self):
            return None

        def stop(self, **kwargs):
            return _telemetry_payload(started=kwargs["process_started_ns"], ended=kwargs["process_ended_ns"])

    monkeypatch.setattr(post, "GpuTelemetrySampler", FakeSampler)
    monkeypatch.setattr(post.subprocess, "run", lambda *args, **kwargs: subprocess.CompletedProcess(args[0], 3, "", "boom"))
    with pytest.raises(RuntimeError):
        post._run_one(job, post.build_child_environment({}))
    assert (job.output_root / post.FAILURE_FILENAME).is_file()
    assert not (tmp_path / "later").exists()


def _install_execute_fixture(monkeypatch: pytest.MonkeyPatch, plan: post.FormalPlan) -> list[str]:
    calls: list[str] = []

    def fake_run(job, _environment):
        job.output_root.mkdir(parents=True)
        job.metrics_path.write_text("{}", encoding="utf-8")
        job.selection_path.write_text("{}", encoding="utf-8")
        (job.output_root / post.PROCESS_STDOUT_FILENAME).write_text("stdout\n", encoding="utf-8")
        (job.output_root / post.PROCESS_STDERR_FILENAME).write_text("stderr\n", encoding="utf-8")
        telemetry_path = job.output_root / post.TELEMETRY_FILENAME
        telemetry_path.write_text(post.canonical_json(_telemetry_payload()), encoding="utf-8")
        telemetry = post._load_json(telemetry_path)
        calls.append(f"run:{job.branch}:{job.replicate_id}")
        return {
            "path": str(telemetry_path),
            "sha256": post.sha256_file(telemetry_path),
            "size": telemetry_path.stat().st_size,
            "schema": telemetry["schema"],
            "record_count": telemetry["record_count"],
            "peak_vram_mib": telemetry["peak_vram_mib"],
            "gpu_identity": telemetry["gpu_identity"],
            "stdout_log": post._process_log_ref(job.output_root / post.PROCESS_STDOUT_FILENAME, job.output_root, "stdout"),
            "stderr_log": post._process_log_ref(job.output_root / post.PROCESS_STDERR_FILENAME, job.output_root, "stderr"),
        }

    def fake_load(job, _identity):
        assert not (plan.output_root / post.FINAL_MANIFEST_FILENAME).exists()
        case = {"door_hinge_drive_max_force": 1.0, "door_handle_drive_max_force": 2.0, "door_handle_height": 0.8, "door_weight": 100.0}
        stage = 1 if job.branch == "b2" else 0
        episodes = [
            {
                "env_id": i, "episode_index": 0, "goal_reached": False, "max_stage": stage,
                "terminal_reason": "stage_overtime", "reward": -1.0, "randomized_case": case,
                "event_metrics": {"doorframe_contact": job.branch == "b1", "doorframe_penalty": -1.0 if job.branch == "b1" else 0.0, "overspeed": False, "overspeed_penalty": 0.0, "over_force": False, "over_force_penalty": 0.0, "root_yaw_abs": 0.1, "root_y_abs": 0.2},
            }
            for i in range(16)
        ]
        return {"branch": job.branch, "replicate_id": job.replicate_id, "episodes": episodes, "metrics": {"path": str(job.metrics_path), "sha256": post.sha256_file(job.metrics_path), "size": job.metrics_path.stat().st_size}, "selection": {"path": str(job.selection_path), "sha256": post.sha256_file(job.selection_path), "size": job.selection_path.stat().st_size}}

    monkeypatch.setattr(post, "_run_one", fake_run)
    monkeypatch.setattr(post, "_load_formal_artifacts", fake_load)
    return calls


def test_execute_seals_final_manifest_last_and_keeps_formal_refs_only(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    pair = post.validate_pair_manifest()
    plan = post.build_formal_plan(pair, output_root=tmp_path / "post")
    calls = _install_execute_fixture(monkeypatch, plan)
    result = post.execute_post_plan(plan, environment_factory=lambda: {})
    assert len(calls) == 6
    assert result["decision"] == post.DECISION_SELECT_B2
    final = plan.output_root / post.FINAL_MANIFEST_FILENAME
    assert final.is_file()
    payload = json.loads(final.read_text(encoding="utf-8"))
    assert all("episodes" not in item for branch in payload["formal_artifacts"].values() for item in branch)


@pytest.mark.parametrize("artifact", ["metrics", "selection", "telemetry", "stdout"])
@pytest.mark.parametrize("operation", ["mutate", "delete"])
def test_execute_final_barrier_rejects_real_byte_toctou(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, artifact: str, operation: str
):
    pair = post.validate_pair_manifest()
    plan = post.build_formal_plan(pair, output_root=tmp_path / f"post_{artifact}_{operation}")
    _install_execute_fixture(monkeypatch, plan)
    original_pair_snapshot = post._assert_pair_snapshot
    target_job = plan.jobs[0]
    target_path = {
        "metrics": target_job.metrics_path,
        "selection": target_job.selection_path,
        "telemetry": target_job.output_root / post.TELEMETRY_FILENAME,
        "stdout": target_job.output_root / post.PROCESS_STDOUT_FILENAME,
    }[artifact]

    def mutate_at_final_barrier(pair_snapshot):
        if operation == "delete":
            target_path.unlink()
        else:
            target_path.write_bytes(target_path.read_bytes() + b"\nTOCTOU")
        original_pair_snapshot(pair_snapshot)

    monkeypatch.setattr(post, "_assert_pair_snapshot", mutate_at_final_barrier)
    with pytest.raises((post.P2PostBlocked, FileNotFoundError)):
        post.execute_post_plan(plan, environment_factory=lambda: {})
    assert not (plan.output_root / post.FINAL_MANIFEST_FILENAME).exists()
    assert (plan.output_root / post.ROOT_FAILURE_FILENAME).is_file()


def test_execute_race_failure_never_seals_decision(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    pair = post.validate_pair_manifest()
    plan = post.build_formal_plan(pair, output_root=tmp_path / "post")
    monkeypatch.setattr(post, "_run_one", lambda job, _environment: (job.output_root.mkdir(parents=True), {"path": str(job.output_root / "telemetry"), "sha256": "a" * 64, "size": 1, "schema": post.TELEMETRY_SCHEMA, "record_count": 1, "peak_vram_mib": 1000.0, "gpu_identity": post._gpu_identity()})[1])
    monkeypatch.setattr(post, "_load_formal_artifacts", lambda job, _identity: {"branch": job.branch, "replicate_id": job.replicate_id, "episodes": []})
    monkeypatch.setattr(post, "_assert_pair_snapshot", lambda _pair: (_ for _ in ()).throw(post.P2PostBlocked("tamper")))
    with pytest.raises(post.P2PostBlocked):
        post.execute_post_plan(plan, environment_factory=lambda: {})
    assert not (plan.output_root / post.FINAL_MANIFEST_FILENAME).exists()
    assert (plan.output_root / post.ROOT_FAILURE_FILENAME).is_file()
