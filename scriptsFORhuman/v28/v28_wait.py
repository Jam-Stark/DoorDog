"""One quiet, persisted v28 wait until an actual Main action or a fixed deadline."""
from __future__ import annotations

import argparse
import os
import time
from pathlib import Path

from v28_contract import require
from v28_orchestrate import read_json, utc_now, write_canonical_json
from v28_watch_wave import execution_terminal


def ready(state, target):
    if state["stop"] is not None:
        return "OWNER_DECISION_OR_STOP"
    if any(task["status"] == "NEEDS_INFRA_REPAIR" for task in state["tasks"].values()):
        return "INFRA_REPAIR_REQUIRED"
    if target == "g1" and state["g1"]["status"] in {"PASS", "FAIL"}:
        return "G1_DECIDED"
    milestone = {"step1000": "wave_a_step1000_aggregate", "endpoint": "wave_a_endpoint_lock"}.get(target)
    if milestone and state["commit_milestones"][milestone] in {"REACHED", "COMMITTED"}:
        return "COMMIT_MILESTONE_REACHED"
    if execution_terminal(state):
        return "EXECUTION_TERMINAL"
    return None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--target", choices=("g1", "step1000", "endpoint", "terminal"), required=True)
    parser.add_argument("--until-epoch", type=float)
    parser.add_argument("--renew-reason")
    args = parser.parse_args()
    state_path = args.state.resolve()
    state = read_json(state_path)
    plan_path = state_path.parent / "waits" / f"{args.target}.json"
    if plan_path.exists():
        plan = read_json(plan_path)
        if args.renew_reason:
            require(args.until_epoch is not None and args.until_epoch > time.time(), "renewal needs a future deadline")
            plan.setdefault("prior_waits", []).append({"wait_until_epoch": plan["wait_until_epoch"],
                                                       "return_reason": plan.get("return_reason")})
            plan.update(wait_until_epoch=args.until_epoch, renewal_reason=args.renew_reason,
                        notifications_seen=len(state["notifications"]))
    else:
        deadline = args.until_epoch if args.until_epoch is not None else state["next_decision_epoch"]
        require(deadline > time.time(), "new logical wait needs a future decision deadline")
        plan = {"schema": "a2_piper_v28_main_wait_v1", "target": args.target, "state": str(state_path),
                "wait_until_epoch": deadline, "created_at": utc_now(),
                "notifications_seen": len(state["notifications"])}
    plan.update(status="WAITING", waiter_pid=os.getpid())
    write_canonical_json(plan_path, plan)
    while True:
        state = read_json(state_path)
        reason = ready(state, args.target)
        if reason is None and len(state["notifications"]) > plan["notifications_seen"]:
            reason = "REGISTERED_NOTIFICATION"
        receipt = state.get("watcher_receipt")
        if reason is None and receipt:
            supervisor = read_json(Path(receipt).with_name("STATUS.json"))
            if supervisor["process_state"] in {"PROCESS_FAILED", "LAUNCH_FAILED", "CANCELLED"}:
                reason = "WATCHER_FAILED"
        remaining = plan["wait_until_epoch"] - time.time()
        if reason is None and remaining <= 0:
            reason = "FIXED_DECISION_DEADLINE"
        if reason is not None:
            plan.update(status="RETURNED", returned_at=utc_now(), return_reason=reason,
                        g1_status=state["g1"]["status"], wave_a_status=state["wave_a"]["status"],
                        wave_b_status=state["wave_b"]["status"], watcher_receipt=receipt)
            write_canonical_json(plan_path, plan)
            import json
            print(json.dumps({key: plan[key] for key in ("target", "return_reason", "state", "wait_until_epoch",
                                                       "g1_status", "wave_a_status", "wave_b_status", "watcher_receipt")}))
            return 0
        time.sleep(min(30, remaining))


if __name__ == "__main__":
    main()
