"""Assemble the v28 candidate manifest and closure from actual execution artifacts."""
from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from v28_contract import HERE, RUNTIME, read_json, require, write_json


def qualification_lanes(state, candidate, kind):
    lanes = [task for task in state["tasks"].values() if task["kind"] == "eval"
             and task["eval_kind"] == kind and task["checkpoint"] == candidate["checkpoint"]]
    return [{key: task.get(key) for key in ("id", "side", "seed", "episodes", "status", "receipt", "output")}
            for task in lanes]


def candidate_report(state, candidate, rank):
    reports = {}
    for kind in ("DEV", "CONF"):
        lanes = qualification_lanes(state, candidate, kind)
        sources = [record["path"] for record in state["reducers"].values()
                   if any(task_id in {lane["id"] for lane in lanes} for task_id in record["task_ids"])]
        if lanes:
            reports[kind] = {"status": "EVALUATED" if all(row["status"] == "COMPLETE" for row in lanes)
                            else "INCOMPLETE_OR_INVALID", "lanes": lanes, "source_reducers": sources,
                            "results": [read_json(Path(path)) for path in sources]}
        else:
            qualified = state["wave_b"].get("qualified_candidate")
            reason = ("PRIMARY_QUALIFIED" if rank == 1 and qualified == state["wave_b"]["candidates"][0]
                      else "DEV_DID_NOT_PASS_BILATERALLY" if kind == "CONF" and reports["DEV"]["status"] != "NOT_RUN"
                      else "PREREQUISITE_NOT_REACHED")
            reports[kind] = {"status": "NOT_RUN", "reason": reason, "lanes": [], "source_reducers": []}
    renders = []
    for task in state["tasks"].values():
        if task["kind"] != "render" or task["checkpoint"] != candidate["checkpoint"]:
            continue
        path = Path(task["output"]) / "render_manifest.json"
        renders.append({"side": task["side"], "status": task["status"], "receipt": task["receipt"],
                        "manifest": str(path) if path.is_file() else None,
                        "result": read_json(path) if path.is_file() else None})
    return {**candidate, "role": "PRIMARY" if rank == 0 else "BACKUP", "rank": rank + 1,
            "qualification": reports, "renders": renders}


def build_closure(state_path: Path, next_stage_review: Path, output_date: str):
    state = read_json(state_path)
    active = [task["id"] for task in state["tasks"].values() if task["status"] in {"LAUNCHED", "PENDING_GPU"}]
    require(not active, f"closure awaits active tasks: {active}")
    require(state["stop"] is None or state["stop"]["reason"].startswith("G1_"),
            "resource/infra scheduling stop is not an experiment closure")
    next_stage = read_json(next_stage_review)
    require(set(next_stage["decisions"]) == {"N01", "N02"}, "closure needs actual N01/N02 review")
    for item in next_stage["decisions"].values():
        require(item["disposition"] in {"CONTINUE", "DEFER", "CLOSE"}, "next-stage disposition")
    selection = state["wave_a"].get("selection")
    lock_path = state["wave_a"].get("endpoint_lock")
    lock = read_json(Path(lock_path)) if lock_path else None
    candidates = [] if lock is None else lock["candidates"]
    wave_b_status = state["wave_b"]["status"]
    qualification = ("BILATERAL_TEACHER_QUALIFIED_SIM_V28" if wave_b_status == "QUALIFIED" else
                     "QUALIFICATION_NOT_CONFIRMED" if wave_b_status == "QUALIFICATION_NOT_CONFIRMED" else "NOT_RUN")
    outcome = "OWNER_DECISION_REQUIRED" if state["stop"] else "V28_EXECUTION_CLOSED"
    stamp = datetime.now(ZoneInfo("Asia/Hong_Kong")).strftime("%Y-%m-%d %H:%M HKT")
    manifest_path = HERE / f"a2_piper_base_v28_teacher_candidate_manifest_{output_date}.json"
    closure_path = HERE / f"a2_piper_base_v28_execution_closure_{output_date}.md"
    manifest = {"schema": "a2_piper_base_v28_teacher_candidate_manifest_v1", "status": qualification,
                "recorded_at": stamp, "source_state": str(state_path.resolve()), "source_lock": state["source_lock"],
                "endpoint_lock": lock_path, "g1": state["g1"], "wave_a": state["wave_a"],
                "original_three_seed_endpoint": None if selection is None else selection["endpoint_reliability"],
                "candidate_pool": [] if selection is None else selection["ranked_candidates"],
                "candidates": [candidate_report(state, candidate, rank) for rank, candidate in enumerate(candidates)],
                "qualification": state["wave_b"], "budget": state["budget"], "stop": state["stop"],
                "next_stage_review": str(next_stage_review.resolve()), "next_stage": next_stage,
                "evidence_level": "EXPERIMENT" if qualification != "NOT_RUN" else "RUNTIME_OBSERVATION",
                "not_run_boundaries": {"G2_optics_CAD_mount_swap": "DEFERRED_TO_C_S_G2",
                                       "Teacher_G7_binding": "OWNER_AUTHORIZATION_REQUIRED",
                                       "hardware": "NOT_AUTHORIZED", "push": "NOT_AUTHORIZED"},
                "limitations": ["Qualification covers only the evaluated fixed candidate(s).",
                                "Qualification never upgrades the original three-seed endpoint conclusion.",
                                "A284 is a separate seed/driver variant, not a causal driver estimate.",
                                "No-event metrics are null; pinhole projection and sampled clearance are geometric proxies.",
                                "Learning failure with tower contact does not prove infeasible geometry.",
                                "X24/X25 and archived G0/C3 limitations remain in force."]}
    write_json(manifest_path, manifest)
    lines = ["# base_v28 execution closure", "", stamp, "",
             f"执行状态：`{outcome}`。G1：`{state['g1']['status']}`；资格：`{qualification}`。", "",
             f"原三 seed 的 6000 reach：`{None if selection is None else selection['endpoint_reliability']['outcome']}`。"
             "历史候选、A284 与资格确认分别报告。", "",
             "| 候选 | Cell / seed / step / driver | DEV | CONF |",
             "|---|---|---|---|"]
    for row in manifest["candidates"]:
        identity = f"{row['cell']} / {row['seed']} / {row['step']} / {row['driver_target_stage']}"
        lines.append(f"| {row['role']} | {identity} | {row['qualification']['DEV']['status']} | {row['qualification']['CONF']['status']} |")
    if not candidates:
        lines += ["", "候选资格确认未运行；具体前置条件与未完成项见 manifest。"]
    lines += ["", "## 预算与停止原因", "", "```json",
              json.dumps({"budget": state["budget"], "stop": state["stop"], "commit_milestones": state["commit_milestones"]},
                         ensure_ascii=False, indent=2), "```", "",
              "## 后续议题回收", "", "```json", json.dumps(next_stage, ensure_ascii=False, indent=2), "```", "",
              "本次回收只确定后续立项去向，未启动新的方法实验。", "",
              "## 证据与限制", "",
              "G0 沿用既有准入证据；原 FAIL、D36/D37、旧 C3 时点不改写。X24 未建立随机分布校准；X25 的臂前伸耦合残余仍是后续分析线索。"
              "相机投影与采样间隙不构成光学、CAD 或硬件验收；无事件保持 null。塔架接触伴随学习失败只支持待区分解释。", "",
              f"[候选与完整评估 manifest]({manifest_path.resolve()})；[执行状态]({state_path.resolve()})；"
              f"[逐 milestone reducers]({(state_path.parent / 'reducers').resolve()})；"
              f"[readouts]({(state_path.parent / 'readouts').resolve()})。", "",
              "训练、评估与 render 任务均已到终态；watcher/supervisor 与 writer 资源的最终释放由 Main 记录在 cleanup receipt。"]
    require(not closure_path.exists(), f"closure exists: {closure_path}")
    closure_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    write_json(state_path.parent / "closure_receipt.json", {"schema": "a2_piper_v28_execution_closure_v1", "status": outcome,
               "manifest": str(manifest_path), "closure": str(closure_path), "recorded_at": stamp,
               "active_tasks": active, "qualification": qualification})
    return manifest_path, closure_path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--next-stage-review", type=Path, required=True)
    parser.add_argument("--date", default=datetime.now(ZoneInfo("Asia/Hong_Kong")).strftime("%Y%m%d"))
    args = parser.parse_args()
    manifest, closure = build_closure(args.state, args.next_stage_review, args.date)
    print(json.dumps({"manifest": str(manifest), "closure": str(closure)}))


if __name__ == "__main__":
    main()
