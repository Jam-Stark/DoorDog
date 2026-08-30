#!/usr/bin/env bash
set -euo pipefail
[[ $# -eq 4 ]] || exit 2
for side in left right;do for view in control dual;do bash "$(dirname "$0")/v26_5_wave2_r1_r15_eval_side.sh" "$1" "$view" "$2" "$3" "$4" "$side" natural;done;done
