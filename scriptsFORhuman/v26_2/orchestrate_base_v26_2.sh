#!/usr/bin/env bash
set -euo pipefail

usage() {
    cat <<'EOF'
usage:
  orchestrate_base_v26_2.sh u-probe --launch
  orchestrate_base_v26_2.sh smoke --launch
  orchestrate_base_v26_2.sh wave1 --launch
  orchestrate_base_v26_2.sh wave1-route-a --launch
  orchestrate_base_v26_2.sh analyze-wave1
  orchestrate_base_v26_2.sh relay --launch SELECTED_W_CHECKPOINT

Relay is intentionally conditional: the current Wave1 mechanism artifact must
have relay_allowed=true, and the selected parent must be a W Wave1 checkpoint.
EOF
}

repo=/home/baoquanc/workspace/DoorDog-A2_Piper
case ${1:-} in
    --help|-h|'') usage; exit 0 ;;
    wave1)
        [[ ${2:-} == --launch && $# -eq 2 ]] || { usage >&2; exit 2; }
        exec bash "$repo/scriptsFORhuman/v26_2/launch_base_v26_2_wave1.sh" --launch
        ;;
    u-probe)
        [[ ${2:-} == --launch && $# -eq 2 ]] || { usage >&2; exit 2; }
        exec /home/baoquanc/anaconda3/envs/isaaclab/bin/python "$repo/scriptsFORhuman/v26_2/v26_2_u_probe_current_fixture.py" --headless --device cuda:0
        ;;
    smoke)
        [[ ${2:-} == --launch && $# -eq 2 ]] || { usage >&2; exit 2; }
        exec bash "$repo/scriptsFORhuman/v26_2/launch_base_v26_2_w_smoke.sh" --launch
        ;;
    wave1-route-a)
        [[ ${2:-} == --launch && $# -eq 2 ]] || { usage >&2; exit 2; }
        exec bash "$repo/scriptsFORhuman/v26_2/launch_base_v26_2_wave1_route_a.sh" --launch
        ;;
    analyze-wave1)
        [[ $# -eq 1 ]] || { usage >&2; exit 2; }
        exec python3 "$repo/scriptsFORhuman/v26_2/v26_2_analyze_mechanism.py" --phase wave1 --eval-root "$repo/logs_eval/base_v26/v26_2_pull_derived_20260825/wave1" --output "$repo/logs_eval/base_v26/v26_2_pull_derived_20260825/wave1_mechanism.json"
        ;;
    relay)
        [[ ${2:-} == --launch && $# -eq 3 ]] || { usage >&2; exit 2; }
        analysis="$repo/logs_eval/base_v26/v26_2_pull_derived_20260825/wave1_mechanism.json"
        checkpoint=$3
        [[ -f "$analysis" && -f "$checkpoint" ]] || { echo "relay requires completed Wave1 analysis and selected checkpoint" >&2; exit 1; }
        python3 - "$analysis" "$checkpoint" <<'PY'
import json, sys
analysis, checkpoint = sys.argv[1:]
payload = json.load(open(analysis, encoding="utf-8"))
if payload.get("outcome", {}).get("relay_allowed") is not True:
    raise SystemExit("Wave1 did not admit relay")
if "/wave1/W/" not in checkpoint or not checkpoint.endswith(("model_step_000250.pt", "model_step_000500.pt", "model_step_000750.pt")):
    raise SystemExit("selected relay parent must be a registered Wave1 W checkpoint")
PY
        exec bash "$repo/scriptsFORhuman/v26_2/launch_base_v26_2_relay.sh" --launch "$checkpoint"
        ;;
    relay-route-a)
        [[ ${2:-} == --launch && $# -eq 2 ]] || { usage >&2; exit 2; }
        exec bash "$repo/scriptsFORhuman/v26_2/launch_base_v26_2_relay_route_a.sh" --launch
        ;;
    analyze-relay)
        [[ $# -eq 1 ]] || { usage >&2; exit 2; }
        exec python3 "$repo/scriptsFORhuman/v26_2/v26_2_analyze_mechanism.py" --phase relay --eval-root "$repo/logs_eval/base_v26/v26_2_pull_derived_20260825/relay" --output "$repo/logs_eval/base_v26/v26_2_pull_derived_20260825/relay_mechanism.json"
        ;;
    *) usage >&2; exit 2 ;;
esac
