#!/usr/bin/env bash
set -euo pipefail
[[ $# -eq 4 ]] || { echo "usage: $0 GPU LABEL OUTPUT_ROOT SEED" >&2;exit 2; }
for view in control dual;do bash "$(dirname "$0")/v26_5_wave2_r1_r14_eval_side.sh" "$1" "$view" "$2" "$3" "$4" left pilot;done
