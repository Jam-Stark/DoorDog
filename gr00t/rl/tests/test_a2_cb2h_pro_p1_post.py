from __future__ import annotations

import json
import math
from pathlib import Path
import subprocess

import pytest

from gr00t.rl.scripts import run_a2_cb2h_pro_p1 as p1
from gr00t.rl.scripts import run_a2_cb2h_pro_p1_post as post


def _telemetry_payload(*, peak: float = 1024.0, stamp: float = 1000.0) -> dict:
    sample = {
        "physical_gpu_index": p1.EXPECTED_GPU_INDEX,
        "logical_device": p1.EXPECTED_LOGICAL_DEVICE,
        "uuid": p1.EXPECTED_GPU_UUID,
        "cuda_visible_devices": p1.EXPECTED_GPU_INDEX,
        "world_size": 1,
        "peak_vram_mib": peak,
        "sample_epoch_s": stamp,
    }
    return {
        "schema": p1.P1_GPU_TELEMETRY_SCHEMA,
        "physical_gpu_index": p1.EXPECTED_GPU_INDEX,
        "logical_device": p1.EXPECTED_LOGICAL_DEVICE,
        "uuid": p1.EXPECTED_GPU_UUID,
        "cuda_visible_devices": p1.EXPECTED_GPU_INDEX,
        "world_size": 1,
        "started_at_epoch_s": stamp,
        "ended_at_epoch_s": stamp + 1.0,
        "samples": [sample],
        "peak_vram_mib": peak,
    }


def _install_fake_sampler(monkeypatch: pytest.MonkeyPatch, payload_factory=None):
    events = []
    state = {"count": 0}

    class FakeSampler:
        def __init__(self, environment):
            self.environment = dict(environment)
            self.samples = []
            self.started_at_epoch_s = None
            self.ended_at_epoch_s = None
            self.index = state["count"]

        def start(self):
            events.append(("start", self.index))
            self.started_at_epoch_s = 1000.0 + self.index

        def stop(self):
            events.append(("stop", self.index))
            state["count"] += 1
            self.ended_at_epoch_s = 1001.0 + self.index
            payload = (
                _telemetry_payload(stamp=1000.0 + self.index)
                if payload_factory is None
                else payload_factory(self.index, self.environment)
            )
            self.samples = list(payload.get("samples", [])) if isinstance(payload, dict) else []
            return payload

    monkeypatch.setattr(post.p1, "GpuTelemetrySampler", FakeSampler)
    return events


def _write(path: Path, value: bytes) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(value)
    return p1.sha256_file(path)


def _fake_contract(tmp_path: Path) -> dict:
    phase = tmp_path / "phase_a_manifest.json"
    phase_sha = _write(phase, b"phase")
    replicas = []
    for index, replicate_id in enumerate(post.REPLICATE_IDS, start=1):
        h5 = tmp_path / replicate_id / "teacher_trajectory.h5"
        trajectory = tmp_path / replicate_id / "trajectory.json"
        h5_sha = _write(h5, f"h5-{replicate_id}".encode())
        trajectory_sha = _write(trajectory, f"trajectory-{replicate_id}".encode())
        replicas.append(
            {
                "replicate_id": replicate_id,
                "h5": {"path": str(h5), "sha256": h5_sha},
                "trajectory_manifest": {"path": str(trajectory), "sha256": trajectory_sha},
                "active_frame_count": p1.EXPECTED_ACTIVE_FRAME_COUNT,
                "active_mask_sha256": f"{index:064x}"[-64:],
            }
        )
    return {
        "root": str(p1.N3_INPUT_ROOT),
        "phase_manifest": {"path": str(phase), "sha256": phase_sha},
        "replicates": replicas,
        "experience_identity": {
            "controller": "teacher",
            "camera_mode": "cameras",
            "path": "fixture.experience",
            "sha256": "a" * 64,
        },
    }


def _fake_manifests(
    tmp_path: Path,
    stage: post.PostStage = post.POST_STAGE_200,
) -> tuple[dict[str, dict], dict[str, str]]:
    _write(tmp_path / "source.pt", b"source")
    _write(tmp_path / "source.yaml", b"source-config")
    source = {
        "checkpoint": {"path": str(tmp_path / "source.pt"), "sha256": "1" * 64},
        "config": {"path": str(tmp_path / "source.yaml"), "sha256": "2" * 64},
        "global_step": p1.EXPECTED_INITIAL_GLOBAL_STEP,
        "checkpoint_load_mode": "full",
    }
    target_config = {"path": str(p1.TARGET_CONFIG), "sha256": p1.sha256_file(p1.TARGET_CONFIG)}
    teacher = {"fixture_teacher": True}
    runtime = {"commit": p1.EXPECTED_RUNTIME_COMMIT, "clean_gr00t": True}
    gpu = {
        "physical_gpu_index": p1.EXPECTED_GPU_INDEX,
        "logical_gpu_index": 0,
        "logical_device": p1.EXPECTED_LOGICAL_DEVICE,
        "uuid": p1.EXPECTED_GPU_UUID,
        "cuda_visible_devices": p1.EXPECTED_GPU_INDEX,
        "world_size": 1,
        "binding_mode": p1.EXPECTED_GPU_BINDING_MODE,
        "cuda_device_order": p1.EXPECTED_CUDA_DEVICE_ORDER,
    }
    manifests = {}
    shas: dict[str, str] = {}
    for mode in post.POST_BRANCHES:
        root = tmp_path / mode
        final_checkpoint = root / f"model_step_{stage.target_global_step:06d}.pt"
        final_config = root / "config.yaml"
        checkpoint_sha = _write(final_checkpoint, f"checkpoint-{mode}".encode())
        config_sha = _write(final_config, f"config-{mode}".encode())
        effective = {
            "actor_learning_rate": 1.0e-4,
            "d435i_forward_mode": mode,
            "enforce_teacher_rollout": True,
            "num_envs": 64,
            "num_mini_batches": 4,
            "num_steps_per_env": 8,
            "num_total_batches": stage.target_global_step,
            "ratio_teacher_rollout": 1.0,
            "save_frequency": stage.target_global_step,
            "use_a2_base": True,
        }
        launch = {
            "actor_learning_rate": 1.0e-4,
            "auto_load_latest": False,
            "checkpoint_load_mode": "full",
            "common_init_contract_sha256": p1.P1_COMMON_INIT_CONTRACT_SHA256,
            "enforce_teacher_rollout": True,
            "forward_mode": mode,
            "logical_device": p1.EXPECTED_LOGICAL_DEVICE,
            "num_envs": 64,
            "num_mini_batches": 4,
            "num_steps_per_env": 8,
            "physical_gpu_index": p1.EXPECTED_GPU_INDEX,
            "ratio_teacher_rollout": 1.0,
            "world_size": 1,
        }
        result = {
            "backward_call_count": stage.additional_iterations * 4,
            "completed_iterations": stage.requested_iterations,
            "optimizer_step_count": stage.additional_iterations * 4,
            "peak_vram_mib": 32000.0,
            "requested_iterations": stage.requested_iterations,
            "run_iterations": stage.additional_iterations,
            "scheduler_last_epoch_after": stage.target_global_step,
            "scheduler_last_epoch_before": stage.source_global_step,
            "scheduler_step_count": stage.additional_iterations,
            "scheduler_step_count_after": stage.target_global_step + 1,
            "scheduler_step_count_before": stage.source_global_step + 1,
            "start_global_step": stage.source_global_step,
            "target_global_step": stage.target_global_step,
            "training_performed": True,
        }
        if stage == post.POST_STAGE_500:
            result["total_completed_iterations"] = stage.requested_iterations
            result["additional_iterations"] = stage.additional_iterations
        source["global_step"] = stage.source_global_step
        raw = {
            "branch": mode,
            "root": str(root),
            "source": source,
            "target_config": target_config,
            "runtime": runtime,
            "teacher": teacher,
            "effective_training_contract": effective,
            "launch_contract": launch,
            "result": result,
            "final_checkpoint": {"global_step": stage.target_global_step},
        }
        manifests[mode] = {
            **raw,
            "raw": raw,
            "final_checkpoint": {
                "path": str(final_checkpoint),
                "sha256": checkpoint_sha,
                "global_step": stage.target_global_step,
            },
            "final_config": {"path": str(final_config), "sha256": config_sha},
            "runtime_evidence": {"metrics": {"gpu_identity": gpu, "peak_vram_mib": 32000.0}},
        }
        manifest_path = root / p1.P1_BRANCH_MANIFEST_FILENAME
        _write(manifest_path, json.dumps(raw, sort_keys=True).encode())
        shas[mode] = p1.sha256_file(manifest_path)
    return manifests, shas


@pytest.fixture
def fake_inputs(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    manifests, shas = _fake_manifests(tmp_path, post.POST_STAGE_200)
    contract = _fake_contract(tmp_path)

    def load(root: Path, **kwargs):
        expected_sha = kwargs["expected_sha256"]
        manifest_path = root / p1.P1_BRANCH_MANIFEST_FILENAME
        if p1.sha256_file(manifest_path) != expected_sha:
            raise RuntimeError("fixture manifest SHA256 drifted")
        return manifests[root.name]

    monkeypatch.setattr(post.p1, "load_sealed_branch_manifest", load)
    monkeypatch.setattr(post, "_validate_n3_contract", lambda _root, _sha: contract)
    return manifests, shas, contract


@pytest.fixture
def fake_inputs_500(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    manifests, shas = _fake_manifests(tmp_path, post.POST_STAGE_500)
    contract = _fake_contract(tmp_path)

    def load(root: Path, **kwargs):
        expected_sha = kwargs["expected_sha256"]
        manifest_path = root / p1.P1_BRANCH_MANIFEST_FILENAME
        if p1.sha256_file(manifest_path) != expected_sha:
            raise RuntimeError("fixture manifest SHA256 drifted")
        return manifests[root.name]

    monkeypatch.setattr(post.p1, "load_sealed_branch_manifest", load)
    monkeypatch.setattr(post, "_validate_n3_contract", lambda _root, _sha: contract)
    return manifests, shas, contract


def test_retry3_manifests_are_read_only_validated():
    seq_root = post.PAIR_ROOT / "sequential"
    packed_root = post.PAIR_ROOT / "packed"
    if not seq_root.is_dir() or not packed_root.is_dir():
        pytest.skip("pinned retry3 pair is unavailable")
    manifests = {
        "sequential": p1.load_sealed_branch_manifest(
            seq_root, expected_sha256=post.SEQUENTIAL_MANIFEST_SHA256, expected_mode="sequential"
        ),
        "packed": p1.load_sealed_branch_manifest(
            packed_root, expected_sha256=post.PACKED_MANIFEST_SHA256, expected_mode="packed"
        ),
    }
    post._validate_sealed_pair(post.PAIR_ROOT, manifests)
    assert manifests["sequential"]["result"]["target_global_step"] == 10200
    assert manifests["packed"]["result"]["requested_iterations"] == 200


def test_build_plan_has_exact_cardinality_order_bindings_and_fresh_root(fake_inputs, tmp_path: Path):
    _manifests, shas, contract = fake_inputs
    output = tmp_path / "post-output"
    plan = post.build_post_plan(
        tmp_path,
        sequential_manifest_sha256=shas["sequential"],
        packed_manifest_sha256=shas["packed"],
        output_root=output,
        n3_root=p1.N3_INPUT_ROOT,
        n3_phase_manifest_sha256=contract["phase_manifest"]["sha256"],
    )
    assert not output.exists()
    assert [(run.mode, run.replicate_id) for run in plan.n3_runs] == [
        (mode, replicate) for mode in post.POST_BRANCHES for replicate in post.REPLICATE_IDS
    ]
    assert [(run.mode, run.replicate_id) for run in plan.formal_runs] == [
        (mode, replicate) for mode in post.POST_BRANCHES for replicate in post.REPLICATE_IDS
    ]
    assert all(run.output_root.is_relative_to(output) for run in plan.all_runs)
    assert all("--recurrent-reset-per-replicate" in run.command for run in plan.n3_runs)
    assert all("--controller" in run.command and "student" in run.command for run in plan.formal_runs)
    assert all("--render" not in run.command for run in plan.formal_runs)


def test_build_500_plan_has_exact_stage_tuple_and_step10500_commands(fake_inputs_500, tmp_path: Path):
    _manifests, shas, contract = fake_inputs_500
    output = tmp_path / "post-500-output"
    plan = post.build_post_plan(
        tmp_path,
        sequential_manifest_sha256=shas["sequential"],
        packed_manifest_sha256=shas["packed"],
        output_root=output,
        n3_root=p1.N3_INPUT_ROOT,
        n3_phase_manifest_sha256=contract["phase_manifest"]["sha256"],
    )
    assert plan.stage == post.POST_STAGE_500
    assert plan.stage.source_global_step == 10200
    assert plan.stage.target_global_step == 10500
    assert plan.stage.requested_iterations == 500
    assert plan.stage.additional_iterations == 300
    assert len(plan.all_runs) == 12
    assert len({run.command_sha256 for run in plan.all_runs}) == 12
    assert all("model_step_010500.pt" in " ".join(run.command) for run in plan.all_runs)
    assert all(
        "--expected-global-step" not in run.command or "10500" in run.command
        for run in plan.formal_runs
    )
    assert not output.exists()


def _stage500_manifest_paths(plan: post.PostPlan) -> dict[str, Path]:
    return {
        mode: plan.pair_root / mode / p1.P1_BRANCH_MANIFEST_FILENAME
        for mode in post.POST_BRANCHES
    }


@pytest.mark.parametrize("tamper", ["mutate", "swap", "same_size"])
def test_stage500_reload_rejects_manifest_tamper_before_final_manifest(
    fake_inputs_500,
    tmp_path: Path,
    tamper: str,
):
    plan = _build_fake_plan(fake_inputs_500, tmp_path)
    paths = _stage500_manifest_paths(plan)
    if tamper == "mutate":
        path = paths["sequential"]
        path.write_bytes(path.read_bytes().replace(b'"branch": "sequential"', b'"branch": "packed"'))
    elif tamper == "swap":
        sequential_bytes = paths["sequential"].read_bytes()
        packed_bytes = paths["packed"].read_bytes()
        paths["sequential"].write_bytes(packed_bytes)
        paths["packed"].write_bytes(sequential_bytes)
    else:
        path = paths["sequential"]
        original = path.read_bytes()
        tampered = original.replace(b'"branch": "sequential"', b'"branch": "SEQUENTIAL"')
        assert len(tampered) == len(original)
        path.write_bytes(tampered)
    with pytest.raises((post.P1PostBlocked, RuntimeError)):
        post._reload_stage500_plan_inputs(plan)
    assert not (plan.output_root / post.FINAL_MANIFEST_FILENAME).exists()


def test_stage500_reload_rejects_supplied_hash_drift_before_final_manifest(
    fake_inputs_500, tmp_path: Path
):
    plan = _build_fake_plan(fake_inputs_500, tmp_path)
    plan.branch_manifest_shas["sequential"] = "0" * 64
    with pytest.raises(post.P1PostBlocked, match="supplied branch manifest SHA drifted"):
        post._reload_stage500_plan_inputs(plan)
    assert not (plan.output_root / post.FINAL_MANIFEST_FILENAME).exists()


def test_stage500_reload_uses_fresh_manifests_and_current_branch_refs(
    fake_inputs_500, tmp_path: Path
):
    _manifests, shas, _contract = fake_inputs_500
    plan = _build_fake_plan(fake_inputs_500, tmp_path)
    refreshed = post._reload_stage500_plan_inputs(plan)
    assert refreshed is not plan
    assert refreshed.stage == post.POST_STAGE_500
    assert refreshed.branch_manifests == _manifests
    refs = post._branch_input_refs(refreshed)
    for mode in post.POST_BRANCHES:
        path = refreshed.pair_root / mode / p1.P1_BRANCH_MANIFEST_FILENAME
        assert refs[mode]["manifest"]["sha256"] == shas[mode]
        assert refs[mode]["manifest"]["sha256"] == p1.sha256_file(path)
        assert refs[mode]["manifest"]["size_bytes"] == path.stat().st_size
    assert not (plan.output_root / post.FINAL_MANIFEST_FILENAME).exists()


def test_mixed_200_500_pair_is_rejected(fake_inputs, fake_inputs_500, tmp_path: Path):
    manifests_200, _shas_200, _contract_200 = fake_inputs
    manifests_500, _shas_500, _contract_500 = fake_inputs_500
    pair_root = tmp_path / "mixed-pair"
    mixed = {
        "sequential": manifests_200["sequential"],
        "packed": manifests_500["packed"],
    }
    for mode in post.POST_BRANCHES:
        mixed[mode]["root"] = str(pair_root / mode)
    with pytest.raises(post.P1PostBlocked, match="mixed post-training stages"):
        post._validate_sealed_pair(pair_root, mixed)


def test_gpu_environment_is_exact_and_no_fallback():
    env = post.build_gpu7_environment({"WORLD_SIZE": "8", "CUDA_VISIBLE_DEVICES": "0", "A2_GPU_BAD": "1"})
    assert env["CUDA_VISIBLE_DEVICES"] == "7"
    assert env["A2_EXPECTED_GPU_UUID"] == p1.EXPECTED_GPU_UUID
    assert "WORLD_SIZE" not in env
    assert env["A2_EXPECTED_WORLD_SIZE"] == "1"


def test_peak_limit_blocks(tmp_path: Path):
    root = tmp_path / "peak"
    root.mkdir()
    path = root / post.TELEMETRY_FILENAME
    path.write_text(json.dumps(_telemetry_payload(peak=47104.0)), encoding="utf-8")
    with pytest.raises(post.P1PostBlocked):
        post._load_child_telemetry(path)
    unrelated = root / "unrelated.json"
    unrelated.write_text(json.dumps({"peak_vram_mib": 47104}), encoding="utf-8")
    assert not hasattr(post, "_scan_peak_artifacts")


@pytest.mark.parametrize("case", ["missing", "empty", "malformed", "wrong_uuid", "nonnumeric", "nonfinite"])
def test_child_telemetry_schema_fail_closed(tmp_path: Path, case: str):
    path = tmp_path / post.TELEMETRY_FILENAME
    if case == "missing":
        with pytest.raises(post.P1PostBlocked):
            post._load_child_telemetry(path)
        return
    if case == "empty":
        path.write_text("", encoding="utf-8")
    elif case == "malformed":
        path.write_text("{", encoding="utf-8")
    else:
        payload = _telemetry_payload()
        if case == "wrong_uuid":
            payload["uuid"] = "GPU-wrong"
        elif case == "nonnumeric":
            payload["samples"][0]["peak_vram_mib"] = "not-a-number"
        elif case == "nonfinite":
            payload["samples"][0]["sample_epoch_s"] = math.nan
        path.write_text(json.dumps(payload, allow_nan=True), encoding="utf-8")
    with pytest.raises(post.P1PostBlocked):
        post._load_child_telemetry(path)


def test_tampered_manifest_hash_and_output_escape_fail(tmp_path: Path):
    if (post.PAIR_ROOT / "sequential" / p1.P1_BRANCH_MANIFEST_FILENAME).is_file():
        with pytest.raises(RuntimeError):
            p1.load_sealed_branch_manifest(
                post.PAIR_ROOT / "sequential",
                expected_sha256="0" * 64,
                expected_mode="sequential",
            )
    root = tmp_path / "root"
    root.mkdir()
    outside = tmp_path / "outside.json"
    outside.write_text("{}", encoding="utf-8")
    with pytest.raises(RuntimeError, match="escapes"):
        post._artifact_ref(outside, root)


def test_decision_pass_requires_nonzero_goals_and_directional_gate():
    adjudication = {
        "status": "PASS_DIRECTIONAL",
        "directional_gates": {"gates": {"nrmse": {"pass": True}}},
        "formal_outcomes": {"packed": {"goals": 1}},
    }
    assert post._decision(adjudication)["decision"] == post.DECISION_PASS
    zero_goal = {
        "status": "INCONCLUSIVE_NO_GOAL_QUALITY",
        "directional_gates": {"gates": {"nrmse": {"pass": True}}},
        "formal_outcomes": {"packed": {"goals": 0}},
    }
    result = post._decision(zero_goal)
    assert result["decision"] == post.DECISION_EXTEND
    assert result["policy_quality_pass"] is False


def test_500_stage_decision_is_terminal_and_separates_directional_support_from_quality():
    directional_zero_goal = {
        "status": "INCONCLUSIVE_NO_GOAL_QUALITY",
        "directional_gates": {"gates": {"nrmse": {"pass": True}}},
        "formal_outcomes": {"packed": {"goals": 0}},
    }
    support = post._decision(directional_zero_goal, post.POST_STAGE_500)
    assert support["decision"] == post.DECISION_DIRECTIONAL_SUPPORT
    assert support["verdict"] == post.DECISION_DIRECTIONAL_SUPPORT
    assert support["directional_support"] is True
    assert support["policy_quality_pass"] is False
    assert support["zero_goals_is_not_policy_quality_pass"] is True
    assert support["terminal"] is True
    assert support["extend_both_only"] is False

    no_gate = {
        "status": "FAIL_NO_DIRECTIONAL_GATE",
        "directional_gates": {"gates": {"nrmse": {"pass": False}}},
        "formal_outcomes": {"packed": {"goals": 0}},
    }
    stopped = post._decision(no_gate, post.POST_STAGE_500)
    assert stopped["decision"] == post.DECISION_STOP
    assert stopped["verdict"] == post.DECISION_STOP
    assert stopped["terminal"] is True
    assert stopped["extend_both_only"] is False


def _fake_formal_payload() -> dict:
    return {
        "episodes": [
            {
                "env_id": index,
                "episode_index": 0,
                "goal_reached": index == 0,
                "max_stage": 3 if index == 0 else 1,
                "randomized_case": {"case": index},
                "reward": float(index),
            }
            for index in range(16)
        ]
    }


def test_formal_case_identity_mismatch_blocks_report(fake_inputs, tmp_path: Path):
    plan = _build_fake_plan(fake_inputs, tmp_path)
    payload = _fake_formal_payload()
    payload["episodes"][1]["env_id"] = 0
    refs = {mode: [] for mode in post.POST_BRANCHES}
    for mode in post.POST_BRANCHES:
        for replicate_id in post.REPLICATE_IDS:
            metrics = tmp_path / f"{mode}-{replicate_id}.json"
            metrics.write_text(json.dumps(payload), encoding="utf-8")
            refs[mode].append({"replicate_id": replicate_id, "metrics_path": str(metrics)})
    with pytest.raises(post.P1PostBlocked, match="case identity"):
        post._formal_report(plan, refs)


def test_telemetry_path_confinement(fake_inputs, tmp_path: Path):
    plan = _build_fake_plan(fake_inputs, tmp_path)
    with pytest.raises(RuntimeError, match="escapes"):
        post._telemetry_ref(plan.n3_runs[0], tmp_path / "different-root")


def test_peak_breach_retains_child_telemetry_and_failure(
    fake_inputs, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    plan = _build_fake_plan(fake_inputs, tmp_path)
    _install_fake_sampler(monkeypatch, lambda index, _env: _telemetry_payload(peak=47104.0, stamp=1000.0 + index))

    def fake_run(command, **kwargs):
        run = plan.n3_runs[0]
        run.output_root.mkdir(parents=True, exist_ok=True)
        (run.output_root / post.N3_CHILD_ACTION_FILENAME).write_text("{}", encoding="utf-8")
        return subprocess.CompletedProcess(command, 0, stdout="ok", stderr="")

    monkeypatch.setattr(post.subprocess, "run", fake_run)
    with pytest.raises(post.P1PostBlocked):
        post._run_one(plan.n3_runs[0], post.build_gpu7_environment({}))
    assert (plan.n3_runs[0].output_root / post.TELEMETRY_FILENAME).is_file()
    assert (plan.n3_runs[0].output_root / "p1_post_child_failure.json").is_file()


def _build_fake_plan(fake_inputs, tmp_path: Path) -> post.PostPlan:
    _manifests, shas, contract = fake_inputs
    return post.build_post_plan(
        tmp_path,
        sequential_manifest_sha256=shas["sequential"],
        packed_manifest_sha256=shas["packed"],
        output_root=tmp_path / "post-output",
        n3_root=p1.N3_INPUT_ROOT,
        n3_phase_manifest_sha256=contract["phase_manifest"]["sha256"],
    )


def test_execute_is_serial_n3_then_formal_calls_path_adjudicator_and_seals(
    fake_inputs, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    plan = _build_fake_plan(fake_inputs, tmp_path)
    sampler_events = _install_fake_sampler(monkeypatch)
    calls = []

    def fake_run(command, **kwargs):
        calls.append((tuple(command), kwargs))
        command = tuple(command)
        if "--n3-infer" in command:
            run = next(item for item in plan.n3_runs if tuple(item.command) == command)
            assert not run.output_root.exists()
            run.output_root.mkdir(parents=True, exist_ok=True)
            (run.output_root / post.N3_CHILD_ACTION_FILENAME).write_text("{}", encoding="utf-8")
        else:
            run = next(item for item in plan.formal_runs if tuple(item.command) == command)
            assert not run.output_root.exists()
            run.output_root.mkdir(parents=True, exist_ok=True)
            (run.output_root / post.FORMAL_METRICS_FILENAME).write_text(
                json.dumps(_fake_formal_payload()), encoding="utf-8"
            )
            (run.output_root / post.FORMAL_SELECTION_FILENAME).write_text("{}", encoding="utf-8")
        return subprocess.CompletedProcess(command, 0, stdout="ok", stderr="")

    adjudication = {
        "schema": p1.P1_ADJUDICATION_SCHEMA,
        "status": "PASS_DIRECTIONAL",
        "directional_gates": {"gates": {"nrmse": {"pass": True}}},
        "formal_outcomes": {"packed": {"goals": 1}},
        "open_loop_nrmse": {
            "sequential": {"replicate_values": [1, 1, 1]},
            "packed": {"replicate_values": [0.5, 0.5, 0.5]},
        },
    }
    captured = {}

    def fake_adjudicate(**kwargs):
        captured.update(kwargs)
        return adjudication

    monkeypatch.setattr(post.subprocess, "run", fake_run)
    monkeypatch.setattr(post.p1, "adjudicate_p1_from_paths", fake_adjudicate)
    sealed = post.execute_post_plan(plan)
    assert len(calls) == 12
    assert all(calls[index][0] == plan.all_runs[index].command for index in range(12))
    assert all(call[1]["env"]["CUDA_VISIBLE_DEVICES"] == "7" for call in calls)
    assert len(sampler_events) == 24
    assert [event[0] for event in sampler_events] == [item for _ in plan.all_runs for item in ("start", "stop")]
    assert captured["formal_artifacts"].keys() == set(post.POST_BRANCHES)
    assert captured["action_artifacts"].keys() == set(post.POST_BRANCHES)
    assert sealed["decision"] == post.DECISION_PASS
    final_path = plan.output_root / post.FINAL_MANIFEST_FILENAME
    assert final_path.is_file()
    final = json.loads(final_path.read_text(encoding="utf-8"))
    assert final["runs"]["n3"][0]["artifacts"][0]["path"].startswith(str(plan.output_root))
    assert final["runs"]["n3"][0]["telemetry"]["record_count"] == 1
    assert final["runs"]["formal"][0]["telemetry"]["sha256"]
    assert final["gpu_telemetry"]["run_count"] == 12
    assert final["gpu_telemetry"]["overall_peak_vram_mib"] < p1.VRAM_LIMIT_MIB
    telemetry_refs = final["gpu_telemetry"]["artifacts"]
    assert len(telemetry_refs) == 12
    assert len({ref["path"] for ref in telemetry_refs}) == 12
    assert len({ref["command_id"] for ref in telemetry_refs}) == 12
    assert all(Path(ref["path"]).is_file() for ref in telemetry_refs)
    assert final["extension_policy"]["one_branch_extension_forbidden"] is True
    assert final["manifest_content_sha256"]
    assert not list(plan.output_root.rglob("*.writing"))


def test_execute_500_seals_terminal_directional_support_without_extension(
    fake_inputs_500, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    plan = _build_fake_plan(fake_inputs_500, tmp_path)
    assert plan.stage == post.POST_STAGE_500

    def fake_run_one(run, _environment):
        run.output_root.mkdir(parents=True, exist_ok=False)
        telemetry_path = run.output_root / post.TELEMETRY_FILENAME
        p1.seal_json(telemetry_path, _telemetry_payload(stamp=float(len(run.command))))
        for artifact_path in run.artifact_paths:
            payload = _fake_formal_payload() if run.operation == "formal" and artifact_path.name == post.FORMAL_METRICS_FILENAME else {}
            artifact_path.write_text(json.dumps(payload), encoding="utf-8")
        summary = post._load_child_telemetry(telemetry_path)
        summary["path"] = str(telemetry_path.resolve())
        return post._child_telemetry_ref(run, summary)

    adjudication = {
        "schema": p1.P1_ADJUDICATION_SCHEMA,
        "status": "INCONCLUSIVE_NO_GOAL_QUALITY",
        "directional_gates": {"gates": {"nrmse": {"pass": True}}},
        "formal_outcomes": {"packed": {"goals": 0}},
        "open_loop_nrmse": {
            "sequential": {"replicate_values": [1, 1, 1]},
            "packed": {"replicate_values": [0.5, 0.5, 0.5]},
        },
    }
    monkeypatch.setattr(post, "_run_one", fake_run_one)
    monkeypatch.setattr(post, "_adjudicate_stage500_from_paths", lambda *_args: adjudication)
    sealed = post.execute_post_plan(plan)
    assert sealed["decision"] == post.DECISION_DIRECTIONAL_SUPPORT
    assert sealed["policy_quality_evidence"]["policy_quality_pass"] is False
    assert sealed["policy_quality_evidence"]["zero_goals_is_not_policy_quality_pass"] is True
    assert sealed["post_stage"] == {
        "stage_id": "p1_stage_500",
        "requested_iterations": 500,
        "completed_iterations": 500,
        "total_completed_iterations": 500,
        "additional_iterations": 300,
        "run_iterations": 300,
        "source_global_step": 10200,
        "target_global_step": 10500,
        "terminal": True,
    }
    assert sealed["extension_policy"]["stage500_never_requests_another_extension"] is True
    assert sealed["extension_policy"]["automatic_extension"] is False


def test_execute_failure_retains_root_and_does_not_seal_final(
    fake_inputs, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    plan = _build_fake_plan(fake_inputs, tmp_path)
    _install_fake_sampler(monkeypatch)

    def failed_run(command, **kwargs):
        run = plan.n3_runs[0]
        assert not run.output_root.exists()
        return subprocess.CompletedProcess(command, 17, stdout="partial", stderr="failure")

    monkeypatch.setattr(post.subprocess, "run", failed_run)
    with pytest.raises(RuntimeError, match="failed"):
        post.execute_post_plan(plan)
    assert plan.output_root.is_dir()
    assert (plan.output_root / post.FAILURE_FILENAME).is_file()
    child_root = plan.n3_runs[0].output_root
    assert (child_root / post.TELEMETRY_FILENAME).is_file()
    assert (child_root / "p1_post_child_failure.json").is_file()
    assert not (plan.output_root / post.FINAL_MANIFEST_FILENAME).exists()


def test_success_without_child_root_is_created_only_after_return_and_fails_closed(
    fake_inputs, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    plan = _build_fake_plan(fake_inputs, tmp_path)
    _install_fake_sampler(monkeypatch)

    def child_without_root(command, **kwargs):
        assert not plan.n3_runs[0].output_root.exists()
        return subprocess.CompletedProcess(command, 0, stdout="no-root", stderr="")

    monkeypatch.setattr(post.subprocess, "run", child_without_root)
    with pytest.raises(FileNotFoundError, match="output root"):
        post.execute_post_plan(plan)
    child_root = plan.n3_runs[0].output_root
    assert child_root.is_dir()
    assert (child_root / post.TELEMETRY_FILENAME).is_file()
    assert (child_root / "p1_post_child_failure.json").is_file()
    assert (plan.output_root / post.FAILURE_FILENAME).is_file()
    assert not (plan.output_root / post.FINAL_MANIFEST_FILENAME).exists()


def test_main_dry_run_is_nonmutating(
    fake_inputs, tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    _manifests, shas, contract = fake_inputs
    output = tmp_path / "dry-run-output"
    rc = post.main(
        [
            "--dry-run",
            "--pair-root",
            str(tmp_path),
            "--sequential-manifest-sha256",
            shas["sequential"],
            "--packed-manifest-sha256",
            shas["packed"],
            "--output-root",
            str(output),
            "--n3-phase-manifest-sha256",
            contract["phase_manifest"]["sha256"],
        ]
    )
    assert rc == 0
    assert not output.exists()
    assert "n3_runs=6 formal_runs=6" in capsys.readouterr().out
