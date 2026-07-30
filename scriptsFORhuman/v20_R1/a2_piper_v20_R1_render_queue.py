"""Queue bound matched renders with one selected checkpoint per group."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Mapping

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _r1_common import (  # noqa: E402
    GROUPS,
    PLAN_ID,
    R1Error,
    R1_ARTIFACT_ROOT,
    RUNTIME_PASS,
    device_env,
    exact_digest,
    sha256_file,
    validate_gpu,
    write_json_no_overwrite,
)

SCHEMA = "a2_piper_v20_R1_render_queue_v3"
CAMERAS = ("default", "handle-side", "handle-top")
DOORS = ("low_light_weak", "median", "high_heavy_strong")


def build_render_queue(
    *,
    checkpoint: Path | None = None,
    output_dir: Path,
    gpu: int,
    groups: tuple[str, ...] = ("G1", "G4", "G6", "G7"),
    selected_checkpoints: Mapping[str, Path] | None = None,
    selected_configs: Mapping[str, Mapping[str, Any]] | None = None,
    admission_manifest_sha256: str | None = None,
) -> dict[str, Any]:
    validate_gpu(gpu)
    if output_dir.exists():
        raise R1Error("R1 render output namespace already exists")
    expected_output = "logs_eval/base_v20_R1/render"
    if expected_output not in str(output_dir.resolve()).replace("\\", "/"):
        raise R1Error("render output must use canonical logs_eval/base_v20_R1/render")
    if selected_checkpoints is None or checkpoint is not None:
        raise R1Error("render queue requires explicit per-group selected_checkpoints; shared fallback is forbidden")
    if selected_configs is None:
        raise R1Error("render queue requires exact selected config/hash bindings")
    if admission_manifest_sha256 is None:
        raise R1Error("render queue requires exact promotion/admission hash")
    exact_digest(admission_manifest_sha256, name="render admission SHA256", length=64)
    if set(selected_checkpoints) != set(groups) or set(selected_configs) != set(groups):
        raise R1Error("render selected checkpoint/config maps must bind exactly requested groups")
    rows = []
    seen_hashes = set()
    for group in groups:
        path = Path(selected_checkpoints[group]).resolve()
        if not path.is_file() or path.is_symlink():
            raise R1Error(f"render checkpoint missing or symlinked for {group}: {path}")
        digest = sha256_file(path)
        exact_digest(digest, name=f"{group}.checkpoint_sha256", length=64)
        if digest in seen_hashes:
            raise R1Error("render checkpoint mapping contains duplicate/alias hashes")
        seen_hashes.add(digest)
        config = selected_configs[group]
        if not isinstance(config, Mapping):
            raise R1Error(f"render config binding is malformed for {group}")
        config_path = config.get("path")
        config_sha = config.get("sha256")
        if not isinstance(config_path, str) or not config_path.endswith(".yaml"):
            raise R1Error(f"render config path is missing for {group}")
        exact_digest(config_sha, name=f"{group}.config_sha256", length=64)
        command = [
            sys.executable,
            "scriptsFORhuman/v20_R1/a2_piper_v20_R1_render_adjudicator.py",
            "--device",
            "cuda:0",
            "--checkpoint",
            str(path),
            "--checkpoint-sha256",
            digest,
            "--config",
            config_path,
            "--config-sha256",
            config_sha,
            "--doors",
            ",".join(DOORS),
            "--cameras",
            ",".join(CAMERAS),
            "--output-dir",
            str(output_dir / group),
        ]
        env = device_env(gpu, render=True)
        if env.get("ACCELERATE_TORCH_DEVICE") != "cuda:0":
            raise R1Error("render logical device must be cuda:0 after visibility masking")
        rows.append(
            {
                "group": group,
                "checkpoint": str(path),
                "checkpoint_sha256": digest,
                "config": config_path,
                "config_sha256": config_sha,
                "doors": list(DOORS),
                "cameras": list(CAMERAS),
                "gpu": gpu,
                "env": env,
                "command": command,
                "output_dir": str(output_dir / group),
                "admission_manifest_sha256": admission_manifest_sha256,
            }
        )
    result = {
        "schema": SCHEMA,
        "plan_id": PLAN_ID,
        "status": RUNTIME_PASS,
        "gpu": gpu,
        "rows": rows,
        "matched_checkpoint_per_group": True,
        "shared_checkpoint_fallback": False,
        "admission_manifest_sha256": admission_manifest_sha256,
    }
    output_dir.mkdir(parents=True)
    write_json_no_overwrite(output_dir / "render_queue.json", result)
    return result


def _require_blocked_r1_cli_opt_in() -> None:
    if "BASE_V20_ALLOW_BLOCKED_R1_EXECUTION" not in __import__("os").environ:
        print(
            "R1 execution is blocked by default; set BASE_V20_ALLOW_BLOCKED_R1_EXECUTION explicitly to run historical tooling",
            file=__import__("sys").stderr,
        )
        raise SystemExit(2)


if __name__ == "__main__":
    _require_blocked_r1_cli_opt_in()
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--gpu", type=int, required=True)
    parser.add_argument("--admission-manifest-sha256", required=True)
    args = parser.parse_args()
    raise SystemExit(
        "CLI requires explicit selected group/checkpoint/config bindings; call build_render_queue()"
    )
