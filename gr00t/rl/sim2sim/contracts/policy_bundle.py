"""Config-derived StudentPolicyBundle reference exporter and validator.

The only source of dimensions, orders, camera geometry, and controller values
is a checkpoint-adjacent *resolved* Hydra config.  A native actor load is a
separate producer operation.  Until that succeeds, the exported receipt says
so explicitly instead of manufacturing a state dict or golden tensors.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any, Mapping

import jsonschema
import yaml


BUNDLE_SCHEMA_VERSION = "doordog.student.bundle.v1"
NATIVE_RECEIPT_SCHEMA = "doordog.sim2sim.native_loader_receipt.v1"
BLOCKED_INPUT_STUDENT_CHECKPOINT = "BLOCKED_INPUT_STUDENT_CHECKPOINT"
BLOCKED_NATIVE_LOADER = "BLOCKED_NATIVE_LOADER"


def _required(mapping: Mapping[str, Any], *path: str) -> Any:
    value: Any = mapping
    for key in path:
        if not isinstance(value, Mapping) or key not in value:
            rendered = ".".join(path)
            raise KeyError(f"resolved config does not declare required field {rendered!r}")
        value = value[key]
    return value


def _schema_path() -> Path:
    return Path(__file__).resolve().parents[1] / "schemas" / "student_policy_bundle.schema.json"


def _load_yaml(path: Path) -> Mapping[str, Any]:
    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(document, Mapping):
        raise TypeError(f"resolved config is not a mapping: {path}")
    return document


def _source_identity(config_path: Path) -> dict[str, Any]:
    source_root = config_path.parent
    for candidate in (config_path.parent, *config_path.parents):
        if (candidate / ".git").exists():
            source_root = candidate
            break
    process = subprocess.run(
        ["git", "-C", str(source_root), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    )
    return {"git_commit": process.stdout.strip(), "source_root": str(source_root)}


def _component_contract(config: Mapping[str, Any]) -> tuple[list[dict[str, Any]], int]:
    env_config = _required(config, "env", "config")
    obs = _required(env_config, "obs")
    names = _required(obs, "obs_dict", "actor_obs")
    dimensions = _required(obs, "obs_dims")
    scales = _required(obs, "obs_scales")
    if not isinstance(names, list):
        raise TypeError("env.config.obs.obs_dict.actor_obs must be a list")
    components = []
    for name in names:
        dim = _required(dimensions, name)
        scale = _required(scales, name)
        if not isinstance(dim, int) or dim < 1:
            raise ValueError(f"actor observation {name!r} has invalid dimension {dim!r}")
        components.append({"name": name, "dim": dim, "dtype": "float32", "scale": scale})
    total = sum(component["dim"] for component in components)
    expected = _required(env_config, "robot", "algo_obs_dim_dict", "actor_obs")
    if total != expected:
        raise ValueError(f"actor observation components total {total}, config declares {expected}")
    return components, total


def _stream(
    name: str,
    camera: Mapping[str, Any],
    *,
    resolution: list[int],
    update_period: float,
    packing: str,
) -> dict[str, Any]:
    return {
        "name": name,
        "resolution_hw": resolution,
        "channels": 3,
        "dtype": "uint8",
        "update_period_s": update_period,
        "parent": _required(camera, "camera_parent") if name == "left" else _required(camera, "parent"),
        "position_m": _required(camera, "camera_pos") if name == "left" else _required(camera, "position_m"),
        "rotation_wxyz": _required(camera, "camera_rot_wxyz") if name == "left" else _required(camera, "rotation_wxyz"),
        "convention": _required(camera, "camera_convention") if name == "left" else _required(camera, "convention"),
        "packing": packing,
    }


def _camera_contract(config: Mapping[str, Any]) -> dict[str, Any]:
    cameras = _required(config, "simulator", "config", "cameras")
    multi = _required(cameras, "policy_multiview")
    right = _required(multi, "right")
    head = _required(multi, "context")
    primary = _required(multi, "primary_resolution")
    head_resolution = _required(head, "resolution")
    meta_order = _required(multi, "camera_meta", "order")
    return {
        "rig_id": _required(cameras, "architecture_id"),
        "layout": _required(multi, "layout"),
        "image_mean": _required(cameras, "image_mean"),
        "image_std": _required(cameras, "image_std"),
        "meta_order": meta_order,
        "streams": [
            _stream(
                "left",
                cameras,
                resolution=primary,
                update_period=_required(cameras, "camera_update_period"),
                packing="vision_obs.channel_stack[0:3]",
            ),
            _stream(
                "right",
                right,
                resolution=_required(right, "resolution"),
                update_period=_required(right, "update_period"),
                packing="vision_obs.channel_stack[3:6]",
            ),
            _stream(
                "head",
                head,
                resolution=head_resolution,
                update_period=_required(head, "update_period"),
                packing="context_vision_obs",
            ),
        ],
    }


def _action_contract(config: Mapping[str, Any]) -> dict[str, Any]:
    algo = _required(config, "algo", "config")
    env_config = _required(config, "env", "config")
    a2_base = _required(env_config, "a2_base")
    delta_indices = _required(env_config, "delta_action_indices")
    base_indices = _required(env_config, "warped_action", "indices")
    high_level_dim = _required(algo, "student_action_dim")
    gripper_index = high_level_dim - 1
    segments = [
        {"name": "a2_base_command", "indices": base_indices},
        {"name": "piper_arm_delta", "indices": delta_indices},
        {"name": "gripper_primitive", "indices": [gripper_index]},
    ]
    flattened = [index for segment in segments for index in segment["indices"]]
    if sorted(flattened) != list(range(high_level_dim)) or len(set(flattened)) != high_level_dim:
        raise ValueError(f"high-level action segments are not a bijection over 0..{high_level_dim - 1}")
    return {
        "contract_id": "a2_piper_student_high_level_action.v1",
        "high_level_dim": high_level_dim,
        "segments": segments,
        "applied_action_dim": _required(env_config, "obs", "obs_dims", "actions"),
        "delta_action_scale": _required(env_config, "delta_action_scale"),
        "delta_action_clip": _required(env_config, "delta_action_clip"),
        "reset_delta_actions_with_backmap": _required(env_config, "reset_delta_actions_with_backmap"),
        "gripper_open_target": _required(a2_base, "gripper_open_target"),
        "gripper_close_target": _required(a2_base, "gripper_close_target"),
        "gripper_primitive_limit": _required(a2_base, "gripper_primitive_limit"),
    }


def _control_contract(config: Mapping[str, Any]) -> dict[str, Any]:
    robot = _required(config, "env", "config", "robot")
    control = _required(robot, "control")
    stiffness = _required(control, "stiffness")
    damping = _required(control, "damping")
    effort_limits = _required(robot, "dof_effort_limit_list")
    dof_names = _required(robot, "dof_names")
    if len(effort_limits) != len(dof_names):
        raise ValueError("robot dof_effort_limit_list does not align with robot.dof_names")
    def gain_key(name: str) -> str:
        if name in stiffness and name in damping:
            return name
        for leg_group in ("hip", "thigh", "calf"):
            if f"_{leg_group}_" in name:
                return leg_group
        raise KeyError(f"resolved control mapping lacks gains for joint {name!r}")

    robot_pd = {
        name: {
            "stiffness": stiffness[gain_key(name)],
            "damping": damping[gain_key(name)],
            "effort_limit": effort_limits[index],
        }
        for index, name in enumerate(dof_names)
    }
    return {
        "control_type": _required(control, "control_type"),
        "clip_torques_per_physics_step": _required(control, "clip_torques"),
        "robot_pd": robot_pd,
        "gripper_pd": {
            "status": "UNRESOLVED_CONFIG_FIELD",
            "required_fields": ["stiffness", "damping", "effort_limit"],
            "reason": "resolved config does not expose a dedicated gripper PD mapping",
        },
    }


def build_config_derived_manifest(config_path: Path, checkpoint_path: Path) -> dict[str, Any]:
    """Build a manifest only from a resolved config and checkpoint path identity."""
    config_path = config_path.resolve(strict=True)
    checkpoint_path = checkpoint_path.resolve(strict=False)
    config = _load_yaml(config_path)
    actor = _required(config, "algo", "config", "actor")
    env_config = _required(config, "env", "config")
    components, actor_obs_dim = _component_contract(config)
    action = _action_contract(config)
    if action["high_level_dim"] != _required(actor, "backbone", "mlp_module", "module_config_dict", "output_dim")[0]:
        raise ValueError("student_action_dim and actor MLP output dimension disagree")
    sim = _required(config, "simulator", "config", "sim")
    physics_hz = _required(sim, "fps")
    decimation = _required(sim, "control_decimation")
    if physics_hz % decimation:
        raise ValueError(f"physics_hz {physics_hz} is not divisible by control_decimation {decimation}")
    robot = _required(env_config, "robot")
    architecture_id = _required(config, "simulator", "config", "cameras", "architecture_id")
    return {
        "schema_version": BUNDLE_SCHEMA_VERSION,
        "bundle_id": f"student-{architecture_id.lower()}",
        "artifact_status": "NATIVE_LOADER_BLOCKED",
        "loader": {
            "kind": "native_hydra",
            "target": _required(actor, "_target_"),
            "checkpoint_payload_key": "policy_state_dict",
            "native_receipt_schema": NATIVE_RECEIPT_SCHEMA,
        },
        "policy": {
            "interface_id": f"{architecture_id}.student12.v1",
            "architecture_id": architecture_id,
            "action_dim": action["high_level_dim"],
            "deterministic_eval": True,
            "deterministic_output": "act_inference.mean",
            "recurrent": {
                "type": _required(actor, "rnn_type"),
                "hidden_dim": _required(actor, "rnn_hidden_dim"),
                "num_layers": _required(actor, "rnn_num_layers"),
                "state": "lstm_hidden_and_cell",
                "reset": "done",
            },
        },
        "observation": {
            "contract_id": "a2_piper_student_actor_obs.v1",
            "actor_obs_dim": actor_obs_dim,
            "components": components,
            "vision_obs_dim": _required(robot, "algo_obs_dim_dict", "vision_obs"),
            "context_vision_obs_dim": _required(robot, "algo_obs_dim_dict", "context_vision_obs"),
            "camera_meta_dim": _required(actor, "view_contract", "camera_meta_dim"),
        },
        "action": action,
        "camera_rig": _camera_contract(config),
        "control": _control_contract(config),
        "robot": {
            "student_dof_order": _required(robot, "dof_names"),
            "policy_leg_order": _required(env_config, "a2_base", "policy_leg_order"),
            "default_joint_angles": _required(robot, "init_state", "default_joint_angles"),
        },
        "timebase": {
            "physics_hz": physics_hz,
            "control_decimation": decimation,
            "control_hz": physics_hz // decimation,
        },
        "provenance": {
            "checkpoint": {"path": str(checkpoint_path), "exists": checkpoint_path.is_file()},
            "resolved_config": {"path": str(config_path)},
            "source_identity": _source_identity(config_path),
        },
        "files": {"config_snapshot": "config_snapshot.yaml"},
    }


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _native_loader_receipt(path: Path) -> Mapping[str, Any]:
    receipt = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(receipt, Mapping) or receipt.get("schema") != NATIVE_RECEIPT_SCHEMA:
        raise ValueError(f"native loader receipt has unsupported schema: {path}")
    return receipt


def export_reference_bundle(
    *,
    config_path: Path,
    checkpoint_path: Path,
    output_dir: Path,
    actor_state_dict: Path | None = None,
    native_loader_receipt: Path | None = None,
    golden_dir: Path | None = None,
) -> dict[str, Any]:
    """Export config contract plus a typed native-load receipt.

    A READY bundle needs both an existing checkpoint and a successful native
    loader receipt paired with its extracted actor state dict.  No state or
    golden artifact is synthesized when that producer operation has not run.
    """
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = output_dir / "manifest.json"
    receipt_path = output_dir / "export_receipt.json"
    if manifest_path.exists() or receipt_path.exists():
        raise FileExistsError(f"refusing to overwrite bundle receipt in {output_dir}")
    manifest = build_config_derived_manifest(config_path, checkpoint_path)
    snapshot_path = output_dir / "config_snapshot.yaml"
    if snapshot_path.exists():
        raise FileExistsError(f"refusing to overwrite config snapshot: {snapshot_path}")
    shutil.copy2(config_path, snapshot_path)

    checkpoint = checkpoint_path.resolve(strict=False)
    if not checkpoint.is_file():
        receipt = {
            "schema": "doordog.sim2sim.policy_bundle_export_receipt.v1",
            "status": BLOCKED_INPUT_STUDENT_CHECKPOINT,
            "checkpoint": str(checkpoint),
            "manifest": "manifest.json",
            "reason": "checkpoint path does not exist; no state dict was exported",
        }
        _write_json(manifest_path, manifest)
        _write_json(receipt_path, receipt)
        return receipt

    if actor_state_dict is None or native_loader_receipt is None or golden_dir is None:
        receipt = {
            "schema": "doordog.sim2sim.policy_bundle_export_receipt.v1",
            "status": BLOCKED_NATIVE_LOADER,
            "checkpoint": str(checkpoint),
            "manifest": "manifest.json",
            "reason": "native Hydra loader has not produced actor state, receipt, and golden I/O",
        }
        _write_json(manifest_path, manifest)
        _write_json(receipt_path, receipt)
        return receipt

    native = _native_loader_receipt(native_loader_receipt)
    actor_state_dict = actor_state_dict.resolve(strict=True)
    if native.get("status") != "NATIVE_LOADER_READY":
        raise ValueError(f"native loader did not report readiness: {native.get('status')!r}")
    destination = output_dir / "actor_state_dict.pt"
    shutil.copy2(actor_state_dict, destination)
    native_destination = output_dir / "native_loader_receipt.json"
    shutil.copy2(native_loader_receipt.resolve(strict=True), native_destination)
    golden_source = golden_dir.resolve(strict=True)
    golden_manifest = golden_source / "golden_manifest.json"
    golden_data = golden_source / "golden_io.npz"
    golden_manifest.resolve(strict=True)
    golden_data.resolve(strict=True)
    shutil.copytree(golden_source, output_dir / "golden")
    manifest["artifact_status"] = "READY"
    manifest["files"]["actor_state_dict"] = destination.name
    manifest["files"]["native_loader_receipt"] = native_destination.name
    manifest["files"]["golden_manifest"] = "golden/golden_manifest.json"
    manifest["files"]["golden_io"] = "golden/golden_io.npz"
    manifest["native_loader"] = dict(native)
    manifest["golden_io"] = json.loads(golden_manifest.read_text(encoding="utf-8"))
    receipt = {
        "schema": "doordog.sim2sim.policy_bundle_export_receipt.v1",
        "status": "EXPORTED_READY",
        "checkpoint": str(checkpoint),
        "manifest": "manifest.json",
        "actor_state_dict": destination.name,
        "golden_manifest": "golden/golden_manifest.json",
    }
    _write_json(manifest_path, manifest)
    _write_json(receipt_path, receipt)
    return receipt


def validate_bundle(bundle_dir: Path, *, mode: str = "compatible") -> dict[str, Any]:
    """Validate structural compatibility; strict formal checks stay opt-in."""
    if mode not in {"compatible", "strict"}:
        raise ValueError(f"unsupported validation mode {mode!r}")
    bundle_dir = bundle_dir.resolve(strict=True)
    manifest = json.loads((bundle_dir / "manifest.json").read_text(encoding="utf-8"))
    schema = json.loads(_schema_path().read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator(schema).validate(manifest)
    components = manifest["observation"]["components"]
    total = sum(component["dim"] for component in components)
    if total != manifest["observation"]["actor_obs_dim"]:
        raise ValueError("actor observation component sum does not match actor_obs_dim")
    segments = manifest["action"]["segments"]
    indices = [index for segment in segments for index in segment["indices"]]
    if sorted(indices) != list(range(manifest["action"]["high_level_dim"])):
        raise ValueError("action segments are not a complete ordered partition")
    if manifest["timebase"]["physics_hz"] != manifest["timebase"]["control_hz"] * manifest["timebase"]["control_decimation"]:
        raise ValueError("timebase values are inconsistent")
    if len(manifest["camera_rig"]["meta_order"]) != manifest["observation"]["camera_meta_dim"]:
        raise ValueError("camera metadata order does not match actor camera_meta dimension")
    warnings = []
    if manifest["control"]["gripper_pd"]["status"] != "RESOLVED":
        warnings.append("gripper PD is unresolved in the selected resolved config")
    if manifest["artifact_status"] != "READY":
        warnings.append("native actor artifact is not exported")
    if mode == "strict":
        if not manifest.get("formal_paired_evidence"):
            raise ValueError("strict mode is reserved for formal paired evidence")
        exact_hashes = manifest["provenance"].get("exact_hashes")
        if not isinstance(exact_hashes, Mapping) or not exact_hashes:
            raise ValueError("strict formal evidence requires producer-supplied exact hashes")
        if manifest["artifact_status"] != "READY":
            raise ValueError("strict formal evidence requires a READY actor artifact")
    return {
        "schema": "doordog.sim2sim.policy_bundle_validation.v1",
        "status": "VALID_COMPATIBLE" if not warnings else "VALID_COMPATIBLE_WITH_WARNINGS",
        "mode": mode,
        "warnings": warnings,
        "actor_obs_dim": manifest["observation"]["actor_obs_dim"],
        "action_dim": manifest["action"]["high_level_dim"],
        "control_hz": manifest["timebase"]["control_hz"],
    }
