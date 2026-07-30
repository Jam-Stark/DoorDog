"""CPU-only executable-DAG contract test for the R2 revision-1 workflow."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from scriptsFORhuman.v20_R2 import _r2_common as common
from scriptsFORhuman.v20_R2 import _r2_workflow as workflow
from scriptsFORhuman.v20_R2 import a2_piper_v20_R2_formal_launcher as formal_launcher
from scriptsFORhuman.v20_R2 import a2_piper_v20_R2_m22_runner as m22_runner
from scriptsFORhuman.v20_R2 import a2_piper_v20_R2_render_review as render_review
from scriptsFORhuman.v20_R2 import a2_piper_v20_R2_render_runner as render_runner

ROOT = Path(__file__).resolve().parents[3]
CONFIG_ROOT = ROOT / "gr00t/rl/config/ablation/wbmanip"
CHECKPOINT = ROOT / "logs_eval/_eval_inputs/base_v17_G1_ckpt0500_20260723/model_step_000500.pt"


def test_executable_dag_contract_cpu(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # One child, one immutable attempt marker, one receipt; a second launch on
    # the same output root is rejected before Popen and a non-zero child stays
    # terminal evidence rather than becoming a retry.
    ok_root = tmp_path / "executor_ok"
    receipt = workflow.spawn_once(
        argv=[sys.executable, "-B", "-c", "print('r2-executor-ok')"],
        repo_root=ROOT, output_root=ok_root, env={}, name="fake_ok",
    )
    marker = json.loads((ok_root / "ATTEMPT_CONSUMED.json").read_text())
    assert marker["producer_state"] == "ATTEMPT_CONSUMED"
    assert receipt["pid"] > 0 and receipt["parent_pid"] > 0
    assert receipt["observed_commit"] and receipt["observed_tree"]
    assert workflow.read_artifact(ok_root / "process_receipt.json", producer_state="PROCESS_COMPLETED")["exit_code"] == 0
    with pytest.raises(common.R2Error):
        workflow.spawn_once(
            argv=[sys.executable, "-B", "-c", "print('retry-forbidden')"],
            repo_root=ROOT, output_root=ok_root, env={}, name="fake_retry",
        )

    failed_root = tmp_path / "executor_nonzero"
    with pytest.raises(common.R2Error, match="exited nonzero"):
        workflow.spawn_once(
            argv=[sys.executable, "-B", "-c", "raise SystemExit(3)"],
            repo_root=ROOT, output_root=failed_root, env={}, name="fake_fail",
        )
    failed = workflow.read_artifact(failed_root / "process_receipt.json", producer_state="PROCESS_COMPLETED")
    assert failed["exit_code"] == 3 and failed["natural_exit"] is False
    assert json.loads((failed_root / "ATTEMPT_CONSUMED.json").read_text())["producer_state"] == "ATTEMPT_CONSUMED"

    # Device binding rejects physical GPU 7 and maps render's physical GPU to
    # the process-visible mask while preserving logical cuda:0.
    with pytest.raises(common.R2Error):
        common.validate_gpu(7)
    _, eval_env, binding = workflow.runtime_command(module="gr00t.rl.eval_agent_trl", repo_root=ROOT, gpu=3)
    assert eval_env == {"ACCELERATE_TORCH_DEVICE": "cuda:3"}
    assert binding["physical_gpu"] == 3 and binding["logical_device"] == "cuda:3"

    # Formal planning is CPU/static but still reconstructs the exact G1-G7
    # ownership map and the exceptional G7 seed=1 contract.
    promotion = {
        "source_lock_sha256": "a" * 64,
        "configs": [{"group": group, "frozen_path": str(CONFIG_ROOT / workflow.CONFIG_FILENAMES[group])}
                    for group in workflow.GROUPS],
    }
    promotion_path = tmp_path / "PROMOTION_PASS.json"
    promotion_path.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(formal_launcher, "read_artifact", lambda *args, **kwargs: promotion)
    formal_plan = formal_launcher.build_formal_launch_plan(
        promotion_pass=promotion_path, physical_gpus=tuple(range(7)),
        repo_root=ROOT, config_root=CONFIG_ROOT,
        training_root=tmp_path / "formal", launcher_root=tmp_path / "launchers",
    )
    formal_rows = formal_plan["groups"]
    assert [(row["group"], row["physical_gpu"]) for row in formal_rows] == list(zip(workflow.GROUPS, range(7)))
    assert {row["seed"] for row in formal_rows if row["group"] != "G7"} == {0}
    assert next(row["seed"] for row in formal_rows if row["group"] == "G7") == 1

    # M22 command reconstruction is an exact 7 x 10 set and carries one
    # physical GPU per group without launching IsaacSim. eval_command binds
    # the active source lock for provenance; stub it (CPU contract test, no
    # ACTIVE_SOURCE_LOCK artifact exists pre-adjudication) like the other
    # module read_artifact stubs above.
    monkeypatch.setattr(workflow, "_source_lock_provenance", lambda repo_root, config_text: {
        "source_lock_sha256": "a" * 64,
        "plan_sha256": "a" * 64,
        "r1_plan_sha256": "a" * 64,
        "b0_json_sha256": "a" * 64,
        "b0_csv_sha256": "a" * 64,
        "urdf_path": common.R1_URDF_PATH,
        "urdf_sha256": "a" * 64,
        "git_commit": "0" * 40,
    })
    manifest = tmp_path / "M22_70ROW.json"
    manifest.write_text("{}", encoding="utf-8")
    m22_payload = {"source_lock_sha256": "b" * 64, "rows": []}
    for index, (group, step) in enumerate((
        (group, step) for group in workflow.GROUPS for step in workflow.M22_STEPS
    )):
        m22_payload["rows"].append({
            "entry_id": f"{index + 1:064x}", "group": group, "checkpoint_step": step,
            "checkpoint_path": str(CHECKPOINT), "training_run_config_path": str(CONFIG_ROOT / workflow.CONFIG_FILENAMES[group]),
            "checkpoint_sha256": "c" * 64, "resolved_config_sha256": "d" * 64,
        })
    monkeypatch.setattr(m22_runner, "read_artifact", lambda *args, **kwargs: m22_payload)
    monkeypatch.setattr(m22_runner, "artifact_hash", lambda path: "e" * 64)
    m22_rows = m22_runner.build_m22_commands(
        manifest=manifest, repo_root=ROOT, physical_gpus=tuple(range(7)), output_root=tmp_path / "m22",
    )
    assert len(m22_rows) == 70
    assert {(row["group"], row["checkpoint_step"]) for row in m22_rows} == {
        (group, step) for group in workflow.GROUPS for step in workflow.M22_STEPS
    }
    assert {row["physical_gpu"] for row in m22_rows} == set(range(7))

    # Render remains CPU-buildable and proves physical-to-logical device
    # mapping; review cannot auto-pass without explicit independent answers.
    render_argv, render_env = render_runner.build_render_command(
        repo_root=ROOT, physical_gpu=3,
        config=CONFIG_ROOT / workflow.CONFIG_FILENAMES["G1"], checkpoint=CHECKPOINT,
        output_root=tmp_path / "render",
    )
    assert render_env["CUDA_VISIBLE_DEVICES"] == "3"
    assert render_env["ACCELERATE_TORCH_DEVICE"] == "cuda:0"
    assert "+render=true" in render_argv
    qa = tmp_path / "render_qa.json"
    qa.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(render_review, "read_artifact", lambda *args, **kwargs: {
        "raw_sha256": "f" * 64, "process_receipt_sha256": "e" * 64,
    })
    monkeypatch.setattr(render_review, "artifact_hash", lambda path: "f" * 64)
    with pytest.raises(common.R2Error, match="explicit independent"):
        render_review.review_render(qa, "reviewer_A")
    answers = {item: True for item in render_review.CHECKLIST}
    review = render_review.review_render(qa, "reviewer_A", answers)
    assert review["adjudicator_state"] == "RENDER_QA_PASS"

    # Raw/adjudication status smuggling is rejected before an artifact can be
    # treated as a computed PASS.
    with pytest.raises(common.R2Error):
        common.validate_raw_producer_payload({"producer_state": "PROCESS_COMPLETED", "status": "PASS"})
    with pytest.raises(common.R2Error):
        workflow.write_adjudication(
            tmp_path / "forbidden.json",
            {"producer_state": "PROCESS_COMPLETED", "adjudicator_state": "STATIC_PASS"},
            "STATIC_PASS",
        )
