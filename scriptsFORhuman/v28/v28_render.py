"""Render the three preregistered first episodes for a frozen v28 candidate."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from v28_contract import EVAL_SEEDS, SIDES, read_json, require, write_json
from v28_run_cell import evaluation_command, evaluation_overrides, run


def render(args):
    lock = read_json(args.endpoint_lock)
    candidates = lock["candidates"]
    candidate = candidates[args.candidate_index]
    args.checkpoint = Path(candidate["checkpoint"]).resolve()
    args.cell = candidate["cell"]
    require(args.checkpoint.is_file() and (args.checkpoint.parent / "config.yaml").is_file(),
            "render requires the frozen checkpoint and adjacent training config")
    args.episodes, args.seed = 3, EVAL_SEEDS["render"]
    args.stratum = "render"
    values = evaluation_overrides(args)
    values.update({"headless": True, "simulator.config.render_results": True,
                   "simulator.config.cameras.enable_cameras": False,
                   "simulator.config.cameras.eval_camera_resolutions": [720, 1280]})
    expected = [args.output / name for name in ("metrics_eval.json", "a2_v14_per_env_records.json",
                "stage2_5_step_trace.json", "a2_eval_diagnostic_metadata.json", ".hydra/runtime_config.yaml")]
    result = run(evaluation_command(values), args.output, args.gpu, expected,
                 {"mode": "render", "cell": args.cell, "checkpoint": str(args.checkpoint),
                  "endpoint_lock": str(args.endpoint_lock), "candidate_index": args.candidate_index,
                  "side": args.side, "seed": args.seed, "episode_ids": [0, 1, 2],
                  "episode_index": 0, "overrides": values,
                  "acceptance_scope": "Predetermined episode render QA only; not qualification statistics."})
    if result:
        return result
    videos = []
    pattern = re.compile(r"_env(\d{4})_episode(\d{4})(?:_(handle_top|handle_side))?_len")
    for path in sorted((args.output / "renderings").glob("*.mp4")):
        matched = pattern.search(path.name)
        require(matched is not None, f"unrecognized completed render: {path.name}")
        videos.append({"path": str(path), "env_id": int(matched[1]),
                       "episode_index": int(matched[2]), "camera": matched[3] or "main"})
    identities = {(row["env_id"], row["episode_index"], row["camera"]) for row in videos}
    expected_ids = {(env_id, 0, camera) for env_id in range(3) for camera in ("main", "handle_top", "handle_side")}
    require(identities == expected_ids and len(videos) == 9, "render did not deliver all three fixed episodes/views")
    write_json(args.output / "render_manifest.json", {
        "schema": "a2_piper_v28_render_v1", "status": "RENDER_COMPLETED", "evidence_level": "RUNTIME",
        "candidate": candidate, "endpoint_lock": str(args.endpoint_lock), "side": args.side,
        "seed": args.seed, "episode_ids": [0, 1, 2], "videos": videos,
        "scope": "Third-person main/handle views for QA; not a G2 optical or CAD acceptance."})
    print(json.dumps({"status": "RENDER_COMPLETED", "manifest": str(args.output / "render_manifest.json")}))
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gpu", type=int, choices=range(8), required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--endpoint-lock", type=Path, required=True)
    parser.add_argument("--candidate-index", type=int, choices=(0, 1), required=True)
    parser.add_argument("--side", choices=SIDES, required=True)
    args = parser.parse_args()
    args.output = args.output.resolve()
    args.endpoint_lock = args.endpoint_lock.resolve()
    return render(args)


if __name__ == "__main__":
    raise SystemExit(main())
