from pathlib import Path

import torch
import yaml

from gr00t.rl.scripts.sweep_a2_student_camera_pose import build_eval_command
from gr00t.rl.utils.a2_dual_portrait_panorama import (
    depth_aware_cylindrical_panorama,
)


ROOT = Path(__file__).resolve().parents[3]
CONFIG = (
    ROOT
    / "gr00t/rl/config/camera_pose_sweep/"
    "d435i_dual_portrait_up60_a2_head_oem.yaml"
)
TOEIN20_CONFIG = (
    ROOT
    / "gr00t/rl/config/camera_pose_sweep/"
    "d435i_dual_portrait_up60_a2_head_oem_toein20.yaml"
)
ENV_SOURCE = (
    ROOT / "gr00t/rl/envs/door/door_open_a2_camera_pose_sweep.py"
)
RUNNER_SOURCE = ROOT / "gr00t/rl/scripts/run_a2_camera_pose_eval.py"


def test_c_b2_config_preserves_nominal_geometry_and_oem_head():
    config = yaml.safe_load(CONFIG.read_text())
    cameras = config["simulator"]["config"]["cameras"]
    assert cameras["camera_pos"] == [0.215, 0.095, 0.165]
    assert cameras["camera_resolutions"] == [384, 216]
    assert {"rgb", "distance_to_image_plane", "instance_id_segmentation_fast"} == {
        next(iter(item)) for item in cameras["camera_types"]
    }

    scheme = config["env"]["config"]["a2_camera_scheme_c"]
    assert scheme["ablation_id"] == "C-B2-DUAL-PORTRAIT-OEM"
    pair = scheme["d435i_pair"]
    assert pair["left"]["position_m"] == [0.215, 0.095, 0.165]
    assert pair["right"]["position_m"] == [0.215, -0.095, 0.165]
    assert pair["left"]["rpy_deg"] == [0.0, -60.0, -15.0]
    assert pair["right"]["rpy_deg"] == [0.0, -60.0, 15.0]
    assert pair["rgb_native_fov_hv_deg"] == [69.4, 42.5]
    assert pair["rgb_portrait_fov_hv_deg"] == [42.5, 69.4]
    assert pair["nominal_baseline_m"] == 0.19
    assert pair["nominal_overlap_deg"] == 12.5

    head = scheme["head_camera"]
    assert head["extrinsic_status"] == "official_unitree_a2_urdf_camera_link"
    assert head["position_m"] == [0.3381, 0.0336, 0.0525]
    assert head["rotation_wxyz"] == [1.0, 0.0, 0.0, 0.0]
    panorama = scheme["panorama"]
    assert panorama["projection"] == "cylindrical_depth_aware"
    assert panorama["stitch_mode"] == "z_buffer_no_rgb_averaging"
    assert panorama["invalid_depth_fallback"] == (
        "best_single_view_fixed_geometry"
    )
    assert panorama["output_resolution"] == [384, 416]


def _panorama_inputs(depth_value: float):
    left_rgb = torch.zeros((4, 4, 3), dtype=torch.uint8)
    left_rgb[..., 0] = 255
    right_rgb = torch.zeros((4, 4, 3), dtype=torch.uint8)
    right_rgb[..., 1] = 255
    depth = torch.full((4, 4, 1), depth_value, dtype=torch.float32)
    intrinsics = torch.tensor(
        [[2.0, 0.0, 1.5], [0.0, 2.0, 1.5], [0.0, 0.0, 1.0]],
        dtype=torch.float32,
    )
    identity = torch.eye(3, dtype=torch.float32)
    translation = torch.zeros(3, dtype=torch.float32)
    return {
        "left_rgb": left_rgb,
        "left_depth": depth,
        "left_intrinsics": intrinsics,
        "left_rotation_virtual_from_source": identity,
        "left_translation_virtual_from_source": translation,
        "right_rgb": right_rgb,
        "right_depth": depth.clone(),
        "right_intrinsics": intrinsics.clone(),
        "right_rotation_virtual_from_source": identity.clone(),
        "right_translation_virtual_from_source": translation.clone(),
        "output_height": 8,
        "output_width": 8,
        "horizontal_fov_deg": 90.0,
        "vertical_fov_deg": 90.0,
        "minimum_depth_m": 0.28,
        "maximum_depth_m": 20.0,
    }


def test_depth_aware_panorama_uses_z_buffer_without_color_averaging():
    result = depth_aware_cylindrical_panorama(**_panorama_inputs(1.0))
    assert result["valid_input_depth_pixels"] == 32
    assert result["depth_fused_output_pixels"] > 0
    colors = {
        tuple(color)
        for color in result["rgb"].reshape(-1, 3).tolist()
    }
    assert colors <= {(0, 0, 0), (255, 0, 0), (0, 255, 0)}


def test_c_b2_toein20_is_an_independent_symmetric_ablation():
    original = yaml.safe_load(CONFIG.read_text())
    config = yaml.safe_load(TOEIN20_CONFIG.read_text())
    assert config["env"]["_target_"].endswith(
        "DoorPregraspCameraSchemeCBDualPortraitOEMToein20"
    )
    cameras = config["simulator"]["config"]["cameras"]
    assert cameras["camera_rot_wxyz"] == [
        0.852868532,
        -0.086824089,
        -0.492403877,
        -0.150383733,
    ]
    scheme = config["env"]["config"]["a2_camera_scheme_c"]
    assert scheme["ablation_id"] == "C-B2-DUAL-PORTRAIT-OEM-TOEIN20"
    pair = scheme["d435i_pair"]
    assert pair["left"]["rpy_deg"] == [0.0, -60.0, -20.0]
    assert pair["right"]["rpy_deg"] == [0.0, -60.0, 20.0]
    assert pair["nominal_baseline_m"] == 0.19
    assert pair["nominal_overlap_deg"] == 2.5
    panorama = scheme["panorama"]
    assert panorama["horizontal_fov_deg"] == 82.5
    assert panorama["output_resolution"] == [384, 474]
    original_scheme = original["env"]["config"]["a2_camera_scheme_c"]
    assert original_scheme["d435i_pair"]["left"]["rpy_deg"] == [0.0, -60.0, -15.0]
    assert original_scheme["panorama"]["output_resolution"] == [384, 416]


def test_depth_holes_select_one_raw_view_instead_of_blending():
    result = depth_aware_cylindrical_panorama(
        **_panorama_inputs(float("inf"))
    )
    assert result["valid_input_depth_pixels"] == 0
    assert result["depth_fused_output_pixels"] == 0
    assert result["fallback_output_pixels"] > 0
    colors = {
        tuple(color)
        for color in result["rgb"].reshape(-1, 3).tolist()
    }
    assert colors <= {(0, 0, 0), (255, 0, 0), (0, 255, 0)}


def test_c_b2_eval_command_and_overlay_are_allowlisted_without_training(tmp_path):
    command = build_eval_command(
        python_path=Path("/isaac/python"),
        checkpoint=Path("/checkpoint.pt"),
        num_envs=2,
        output_dir=tmp_path / "c_b2",
        runtime_repository=Path("/runtime"),
        overlay_repository=Path("/overlay"),
        camera_config="d435i_dual_portrait_up60_a2_head_oem",
    )
    assert (
        "+camera_pose_sweep=d435i_dual_portrait_up60_a2_head_oem"
        in command
    )
    assert not any("train_agent" in token for token in command)
    runner_source = RUNNER_SOURCE.read_text()
    assert '"gr00t.rl.utils.a2_dual_portrait_panorama"' in runner_source
    assert '"d435i_dual_portrait_up60_a2_head_oem"' in runner_source
    env_source = ENV_SOURCE.read_text()
    assert "class DoorPregraspCameraSchemeCBDualPortraitOEM" in env_source
    c_b2_source = env_source[
        env_source.index("class DoorPregraspCameraSchemeCBDualPortraitOEM") :
    ]
    assert "simulator.sim.render()" not in c_b2_source
    assert '"distance_to_image_plane"' in c_b2_source
    assert "depth_aware_cylindrical_panorama" in c_b2_source

    toein20_command = build_eval_command(
        python_path=Path("/isaac/python"),
        checkpoint=Path("/checkpoint.pt"),
        num_envs=2,
        output_dir=tmp_path / "c_b2_toein20",
        runtime_repository=Path("/runtime"),
        overlay_repository=Path("/overlay"),
        camera_config="d435i_dual_portrait_up60_a2_head_oem_toein20",
    )
    assert (
        "+camera_pose_sweep=d435i_dual_portrait_up60_a2_head_oem_toein20"
        in toein20_command
    )
    assert not any("train_agent" in token for token in toein20_command)
    assert '"d435i_dual_portrait_up60_a2_head_oem_toein20"' in runner_source
    assert "class DoorPregraspCameraSchemeCBDualPortraitOEMToein20" in env_source
