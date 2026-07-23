"""Focused no-simulation checks for the v18 M39 gripper-realism probe."""

from pathlib import Path

import ast
from hashlib import sha256
from types import SimpleNamespace

from hydra import compose, initialize_config_dir
from omegaconf import OmegaConf
import pytest
import torch


ROOT = Path(__file__).resolve().parents[3]
ISAAC_SOURCE = ROOT / "gr00t/rl/simulator/isaacsim/isaacsim.py"
ENV_SOURCE = ROOT / "gr00t/rl/envs/door/door_open_a2_base.py"
ENV_CONFIG = ROOT / "gr00t/rl/config/env/door_open_a2_base.yaml"
ABLATION = ROOT / "gr00t/rl/config/ablation/wbmanip/base_v18_M39_combined_probe.yaml"


def _m39_harness_class():
    """Load only the M39 helpers so tests do not initialize Isaac Sim."""
    tree = ast.parse(ISAAC_SOURCE.read_text(encoding="utf-8"))
    isaac_sim_class = next(
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "IsaacSim"
    )
    wanted = {
        "_m39_material_summary",
        "_m39_asset_material_slices",
        "_capture_m39_material_evidence",
    }
    methods = [
        node
        for node in isaac_sim_class.body
        if isinstance(node, ast.FunctionDef) and node.name in wanted
    ]
    assert {node.name for node in methods} == wanted
    harness_node = ast.ClassDef(
        name="M39Harness",
        bases=[],
        keywords=[],
        body=methods,
        decorator_list=[],
    )
    module = ast.fix_missing_locations(ast.Module(body=[harness_node], type_ignores=[]))
    namespace = {"sha256": sha256, "torch": torch}
    exec(compile(module, str(ISAAC_SOURCE), "exec"), namespace)
    return namespace["M39Harness"]


def _asset(materials, link_paths, shape_counts=None):
    class RootView:
        def __init__(self):
            self.link_paths = [list(link_paths)]

        def get_material_properties(self):
            return materials

    class PhysicsView:
        def create_rigid_body_view(self, path):
            assert shape_counts is not None
            return SimpleNamespace(max_shapes=shape_counts[path])

    asset = SimpleNamespace(root_physx_view=RootView())
    if shape_counts is not None:
        asset._physics_sim_view = PhysicsView()
    return asset


def _exact_door_asset(
    *,
    num_envs=2,
    shape_count=2,
    paths=None,
    count=None,
    material_shape=None,
    materials=None,
):
    env0_path = "/World/envs/env_0/Door/door_handle"
    root_paths = (env0_path, "/World/envs/env_0/Door/panel")
    if paths is None:
        paths = tuple(
            f"/World/envs/env_{env_id}/Door/door_handle" for env_id in range(num_envs)
        )
    if materials is None:
        if material_shape is None:
            material_shape = (num_envs, shape_count, 3)
        materials = torch.full(material_shape, 0.5, dtype=torch.float32)
    class TargetView:
        def __init__(self):
            self.count = len(paths) if count is None else count
            self.max_shapes = shape_count
            self.prim_paths = list(paths)

        def get_material_properties(self):
            return materials

    class PhysicsView:
        def __init__(self):
            self.target_paths = []

        def create_rigid_body_view(self, path):
            self.target_paths.append(path)
            return TargetView()

    class RootView:
        def __init__(self):
            self.link_paths = [list(root_paths)]

        def get_material_properties(self):
            raise AssertionError("exact door evidence must use the target RigidBodyView")

    asset = SimpleNamespace(root_physx_view=RootView(), _physics_sim_view=PhysicsView())
    return asset

def _robot_asset(shape_counts=(2, 3, 1), material_columns=None):
    paths = (
        "/World/envs/env_0/Robot/arm_body7",
        "/World/envs/env_0/Robot/arm_body8",
        "/World/envs/env_0/Robot/chassis",
    )
    if material_columns is None:
        material_columns = sum(shape_counts)
    materials = torch.zeros((2, material_columns, 3), dtype=torch.float32)
    counts = dict(zip(paths, shape_counts))
    return _asset(materials, paths, counts)

def test_exact_door_body_view_requires_all_env_paths_and_material_contract():
    harness = _m39_harness_class()
    materials = torch.tensor(
        [
            [[0.6, 0.5, 0.0], [0.7, 0.55, 0.0]],
            [[0.6, 0.5, 0.0], [0.7, 0.55, 0.0]],
        ],
        dtype=torch.float32,
    )
    asset = _exact_door_asset(materials=materials)
    record = harness._m39_asset_material_slices(
        asset, ("door_handle",), "door", 2, require_exact_body_view=True
    )["door_handle"]
    expected_paths = [
        "/World/envs/env_0/Door/door_handle",
        "/World/envs/env_1/Door/door_handle",
    ]
    expected_hash = sha256("\n".join(expected_paths).encode("utf-8")).hexdigest()
    assert asset._physics_sim_view.target_paths == ["/World/envs/env_*/Door/door_handle"]
    assert record["body_path"] == "/World/envs/env_0/Door/door_handle"
    assert record["target_path"] == record["body_path"]
    assert record["target_body"] == "door_handle"
    assert record["scope"] == "exact_target_rigid_body_view_all_envs"
    assert record["evidence_scope"] == record["scope"]
    assert record["view_count"] == 2
    assert record["shape_count"] == 2
    assert record["prim_paths_sha256"] == expected_hash
    assert torch.equal(record["materials"], materials)

    nonfinite = materials.clone()
    nonfinite[1, 1, 1] = float("nan")
    with pytest.raises(RuntimeError, match="finite floating shape"):
        harness._m39_asset_material_slices(
            _exact_door_asset(materials=nonfinite),
            ("door_handle",),
            "door",
            2,
            require_exact_body_view=True,
        )

    with pytest.raises(RuntimeError, match="count must equal num_envs"):
        harness._m39_asset_material_slices(
            _exact_door_asset(count=1),
            ("door_handle",),
            "door",
            2,
            require_exact_body_view=True,
        )

    wrong_paths = (
        "/World/envs/env_0/Door/door_handle",
        "/World/envs/env_2/Door/door_handle",
    )
    with pytest.raises(RuntimeError, match="do not match the expected env set"):
        harness._m39_asset_material_slices(
            _exact_door_asset(paths=wrong_paths),
            ("door_handle",),
            "door",
            2,
            require_exact_body_view=True,
        )

    with pytest.raises(RuntimeError, match="material tensor must have"):
        harness._m39_asset_material_slices(
            _exact_door_asset(material_shape=(2, 3, 3)),
            ("door_handle",),
            "door",
            2,
            require_exact_body_view=True,
        )

    with pytest.raises(RuntimeError, match="no collision shapes"):
        harness._m39_asset_material_slices(
            _exact_door_asset(shape_count=0),
            ("door_handle",),
            "door",
            2,
            require_exact_body_view=True,
        )

    missing_target = _exact_door_asset()
    missing_target.root_physx_view.link_paths[0] = [
        "/World/envs/env_0/Door/door_handle_extra"
    ]
    with pytest.raises(RuntimeError, match="exactly one body path"):
        harness._m39_asset_material_slices(
            missing_target,
            ("door_handle",),
            "door",
            2,
            require_exact_body_view=True,
        )


def test_shared_m39_selector_is_default_off():
    config = OmegaConf.load(ENV_CONFIG)
    assert config.env.config.a2_m39_gripper_material_enabled is False


def test_default_robot_mapping_keeps_exact_sum_and_positive_targets():
    harness = _m39_harness_class()
    valid_asset = _robot_asset()
    slices = harness._m39_asset_material_slices(
        valid_asset, ("arm_body7", "arm_body8"), "robot", 2
    )
    assert set(slices) == {"arm_body7", "arm_body8"}
    assert slices["arm_body7"]["shape_count"] == 2
    assert slices["arm_body8"]["shape_count"] == 3

    mismatch_asset = _robot_asset(material_columns=5)
    with pytest.raises(RuntimeError, match="body-shape mapping mismatch"):
        harness._m39_asset_material_slices(mismatch_asset, ("arm_body7", "arm_body8"), "robot", 2)

    zero_target_asset = _robot_asset(shape_counts=(0, 3, 1))
    with pytest.raises(RuntimeError, match="target body.*no collision shapes"):
        harness._m39_asset_material_slices(zero_target_asset, ("arm_body7", "arm_body8"), "robot", 2)

def test_m39_event_term_targets_and_ranges_are_explicit():
    source = ISAAC_SOURCE.read_text(encoding="utf-8")
    assert "func=mdp.randomize_rigid_body_material" in source
    assert 'mode="startup"' in source
    assert 'A2_M39_GRIPPER_BODY_NAMES = ("arm_body7", "arm_body8")' in source
    assert "A2_M39_EXPECTED_POST_MATERIAL = (1.1, 0.9, 0.0)" in source
    assert '"asset_cfg": SceneEntityCfg(' in source
    assert '"robot", body_names=["arm_body7", "arm_body8"]' in source
    assert '"static_friction_range": (1.1, 1.1)' in source
    assert '"dynamic_friction_range": (0.9, 0.9)' in source
    assert '"restitution_range": (0.0, 0.0)' in source
    assert '"num_buckets": 1' in source
    assert '"make_consistent": True' in source


def test_generic_friction_coexistence_fails_fast_and_material_contract_is_strict():
    source = ISAAC_SOURCE.read_text(encoding="utf-8")
    assert "m39_enabled and self.domain_rand_config.get(\"randomize_friction\", False)" in source
    assert "cannot coexist with" in source
    assert "_m39_asset_material_slices" in source
    assert "body-shape mapping mismatch" in source
    assert 'A2_M39_GRIPPER_MATERIAL_SCHEMA = "a2_m39_gripper_material_v1"' in source
    for field in (
        '"finger_bodies"',
        '"arm_body7"',
        '"arm_body8"',
        '"handle"',
        '"pre"',
        '"post"',
        '"unchanged"',
        '"all_envs"',
    ):
        assert field in source
    env_source = ENV_SOURCE.read_text(encoding="utf-8")
    init_start = env_source.index("    def _init_a2_door_pregrasp_state(self):")
    init_end = env_source.index("    def ", init_start + 8)
    init_source = env_source[init_start:init_end]
    assert "_get_a2_m39_gripper_material_enabled" in init_source
    assert "_get_a2_hold_contact_detail_enabled" not in init_source
    assert 'getattr(self.simulator, "_m39_material_runtime_metadata", None)' in init_source
    assert "M39 gripper material runtime evidence is unavailable." in init_source


def test_m39_material_mapping_allows_unrelated_zero_shape_links_but_rejects_target():
    source = ISAAC_SOURCE.read_text(encoding="utf-8")
    function_start = source.index("def _m39_asset_material_slices")
    loop_start = source.index("        shape_counts = []", function_start)
    mapping_start = source.index("        slices = {}", loop_start)
    loop_source = source[loop_start:mapping_start]
    assert "shape_counts.append(shape_count)" in loop_source
    assert "has no collision shapes" not in loop_source
    target_source = source[mapping_start:source.index("    def _capture_m39_material_evidence", mapping_start)]
    assert "shape_count = shape_counts[body_index]" in target_source
    assert "if shape_count <= 0:" in target_source
    assert "target body" in target_source
    assert "end = start + shape_count" in target_source
    assert '"shape_count": shape_count' in target_source
    assert "sum(shape_counts) != int(materials.shape[1])" in source




def test_m39_pre_post_door_calls_use_exact_view_and_capture_provenance():
    source = ISAAC_SOURCE.read_text(encoding="utf-8")
    tree = ast.parse(source)
    door_calls = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        if node.func.attr != "_m39_asset_material_slices" or not node.args:
            continue
        argument = node.args[0]
        if not isinstance(argument, ast.Subscript) or not isinstance(argument.value, ast.Attribute):
            continue
        if argument.value.attr != "articulations":
            continue
        key = argument.slice
        if not isinstance(key, ast.Constant) or key.value != "door":
            continue
        door_calls.append(
            next(keyword for keyword in node.keywords if keyword.arg == "require_exact_body_view")
        )
    assert len(door_calls) == 2
    assert all(
        isinstance(keyword.value, ast.Constant) and keyword.value.value is True
        for keyword in door_calls
    )
    assert "require_uniform_full_asset" not in source
    assert source.count(
        "self._m39_material_runtime_metadata = self._capture_m39_material_evidence("
    ) == 1

    harness = _m39_harness_class()
    probe = harness()
    probe.A2_M39_GRIPPER_BODY_NAMES = ("arm_body7", "arm_body8")
    probe.A2_M39_GRIPPER_MATERIAL_SCHEMA = "a2_m39_gripper_material_v1"
    probe.A2_M39_HANDLE_BODY_NAME = "door_handle"
    probe.A2_M39_EXPECTED_POST_MATERIAL = (1.1, 0.9, 0.0)
    handle_materials = torch.tensor(
        [
            [[0.6, 0.5, 0.0], [0.7, 0.55, 0.0]],
            [[0.6, 0.5, 0.0], [0.7, 0.55, 0.0]],
        ],
        dtype=torch.float32,
    )
    door_pre = probe._m39_asset_material_slices(
        _exact_door_asset(materials=handle_materials),
        ("door_handle",),
        "door",
        2,
        require_exact_body_view=True,
    )
    door_post = probe._m39_asset_material_slices(
        _exact_door_asset(materials=handle_materials.clone()),
        ("door_handle",),
        "door",
        2,
        require_exact_body_view=True,
    )
    pre_material = torch.ones((2, 2, 3), dtype=torch.float32) * torch.tensor([0.5, 0.4, 0.0])
    post_material = torch.ones((2, 2, 3), dtype=torch.float32) * torch.tensor([1.1, 0.9, 0.0])
    robot_pre = {}
    robot_post = {}
    for name in probe.A2_M39_GRIPPER_BODY_NAMES:
        robot_pre[name] = {
            "body_path": f"/World/envs/env_0/Robot/{name}",
            "shape_count": 2,
            "materials": pre_material.clone(),
        }
        robot_post[name] = {
            "body_path": f"/World/envs/env_0/Robot/{name}",
            "shape_count": 2,
            "materials": post_material.clone(),
        }
    metadata = probe._capture_m39_material_evidence(
        {"robot": robot_pre, "door": door_pre},
        {"robot": robot_post, "door": door_post},
    )
    handle = metadata["handle"]
    assert metadata["event_term"]["static_friction_range"] == [1.1, 1.1]
    assert metadata["event_term"]["dynamic_friction_range"] == [0.9, 0.9]
    assert metadata["schema"] == "a2_m39_gripper_material_v1"
    assert handle["body_path"] == "/World/envs/env_0/Door/door_handle"
    assert handle["target_path"] == handle["body_path"]
    assert handle["scope"] == "exact_target_rigid_body_view_all_envs"
    assert handle["evidence_scope"] == handle["scope"]
    assert handle["view_count"] == 2
    assert handle["shape_count"] == 2
    assert len(handle["prim_paths_sha256"]) == 64
    assert handle["unchanged"] is True

    changed_materials = handle_materials.clone()
    changed_materials[1, 1, 0] = 0.8
    changed_post = probe._m39_asset_material_slices(
        _exact_door_asset(materials=changed_materials),
        ("door_handle",),
        "door",
        2,
        require_exact_body_view=True,
    )
    with pytest.raises(RuntimeError, match="changed while randomizing finger pads"):
        probe._capture_m39_material_evidence(
            {"robot": robot_pre, "door": door_pre},
            {"robot": robot_post, "door": changed_post},
        )


def test_combined_probe_values_and_provenance_are_exact():
    config = OmegaConf.load(ABLATION)
    assert config.checkpoint.endswith(
        "base_v17_G5_full_m34_m35_hinge125-20260723_011415/model_step_002500.pt"
    )
    assert config.checkpoint_load_mode == "policy_only"
    assert config.auto_load_latest is False
    assert config.seed == 0
    assert config.env.config.a2_m39_gripper_material_enabled is True
    assert config.env.config.a2_hold_diagnostic_contact_detail_enabled is True
    assert config.env.config.a2_stage2_squeeze_force_max == 30.0
    assert config.env.config.a2_stage2_over_force_threshold == 55.0
    assert list(config.robot.dof_effort_limit_list)[-2:] == [45.0, 45.0]
    assert config.robot.control.stiffness.arm_j7 == 1300.0
    assert config.robot.control.stiffness.arm_j8 == 1300.0
    assert config.robot.control.damping.arm_j7 == 32.0
    assert config.robot.control.damping.arm_j8 == 32.0
    assert config.algo.config.eval.a2_diagnostic_trace_enabled is True

    assert config.algo.config.eval.a2_eval_m41_strict_telemetry is True

def test_combined_probe_hydra_compose_preserves_exact_effective_paths():
    config_dir = ROOT / "gr00t/rl/config"
    with initialize_config_dir(version_base="1.1", config_dir=str(config_dir)):
        composed = compose(
            config_name="base",
            overrides=[
                "+exp=wbmanip/door_open_a2_base_lstm",
                "+ablation=wbmanip/base_v18_M39_combined_probe",
            ],
        )
    assert composed.env.config.a2_m39_gripper_material_enabled is True
    assert composed.env.config.a2_hold_diagnostic_contact_detail_enabled is True
    assert composed.env.config.a2_stage2_squeeze_force_max == 30.0
    assert composed.env.config.a2_stage2_over_force_threshold == 55.0
    assert list(composed.robot.dof_effort_limit_list)[-2:] == [45.0, 45.0]
    assert composed.robot.control.stiffness.arm_j7 == 1300.0
    assert composed.robot.control.damping.arm_j8 == 32.0
    assert composed.algo.config.eval.a2_eval_m41_strict_telemetry is True
