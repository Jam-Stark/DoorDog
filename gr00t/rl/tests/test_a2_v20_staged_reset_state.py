"""CPU-only staged-reset registry and mixed-state snapshot checks for v20."""

import ast
from pathlib import Path
from typing import Callable

import pytest
import torch


ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT / "gr00t/rl/envs/door/door_open_a2_base.py"
STAGED_SOURCE = ROOT / "gr00t/rl/envs/base_task/staged_task_base.py"


def test_v20_state_is_registered_and_partially_reset():
    source = SOURCE.read_text(encoding="utf-8")
    for name in (
        "a2_v20_send_ready",
        "a2_v20_pre_send_crossing_seen",
        "a2_v20_first_pre_send_crossing_step",
        "a2_v20_first_send_ready_step",
        "a2_v20_first_root_crossing_step",
        "a2_v20_hinge_at_first_root_crossing",
        "a2_v20_root_x_at_first_crossing",
        "a2_v20_root_entry_pos_se2",
        "a2_v20_root_entry_valid",
        "a2_v20_max_pre_send_displacement_se2",
        "a2_v20_r2_max_pre_send_reconfiguration",
        "a2_corridor_latched",
        "a2_v20_handle_tcp_capture_pos",
        "a2_v20_handle_tcp_capture_quat",
        "a2_v20_handle_tcp_capture_valid",
        "a2_v20_snapshot_crossing_seen",
        "a2_v20_snapshot_root_x_rel",
    ):
        assert f'("{name}"' in source
    for name in ("a2_v20_snapshot_crossing_seen", "a2_v20_snapshot_root_x_rel"):
        assert f'("{name}"' in source


def test_v20_staged_reset_contract_has_exact_load_shape_checks():
    source = SOURCE.read_text(encoding="utf-8")
    assert "_register_a2_v20_staged_reset_buffers" in source
    assert "_load_a2_v20_named_buffer" in source
    assert "data_dtype={data.dtype}" in source
    assert "data_device={data.device}" in source


def test_v20_registry_is_single_writer_and_partial_snapshot_load_preserves_mixed_state():
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
    function = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef)
        and node.name == "_register_a2_v20_staged_reset_buffers"
    )
    namespace = {"torch": torch}
    exec(compile(ast.Module(body=[function], type_ignores=[]), str(SOURCE), "exec"), namespace)

    class Registry:
        enable_staged_reset = True
        num_envs = 4

        def __init__(self):
            self.rows = []

        def _register_buffer_to_track(self, name, shape, store, load, *, dtype):
            self.rows.append((name, shape, dtype, store, load))

    registry = Registry()
    namespace["_register_a2_v20_staged_reset_buffers"](registry)
    names = [row[0] for row in registry.rows]
    assert names
    assert len(names) == len(set(names))
    assert names.count("a2_v20_send_ready") == 1
    specs = {row[0]: (row[1], row[2]) for row in registry.rows}
    assert specs["a2_v20_snapshot_crossing_seen"] == ((4,), torch.bool)
    assert specs["a2_v20_snapshot_root_x_rel"] == ((4,), torch.float32)

    class State:
        def __init__(self):
            self._a2_v20_send_ready = torch.tensor([False, True])

    state = State()
    load_tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
    load_function = next(
        node
        for node in ast.walk(load_tree)
        if isinstance(node, ast.FunctionDef) and node.name == "_load_a2_v20_named_buffer"
    )
    load_namespace = {"torch": torch}
    exec(compile(ast.Module(body=[load_function], type_ignores=[]), str(SOURCE), "exec"), load_namespace)
    load_namespace["_load_a2_v20_named_buffer"](
        state, "a2_v20_send_ready", torch.tensor([0]), torch.tensor([True])
    )
    assert state._a2_v20_send_ready.tolist() == [True, True]
    with pytest.raises(RuntimeError, match="incompatible state"):
        load_namespace["_load_a2_v20_named_buffer"](
            state, "a2_v20_send_ready", torch.tensor([1]), torch.tensor([[True]])
        )


def _extract_function(path: Path, name: str, *, namespace: dict | None = None):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    function = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == name
    )
    exec_namespace = {"torch": torch, "Callable": Callable}
    if namespace:
        exec_namespace.update(namespace)
    exec(
        compile(ast.Module(body=[function], type_ignores=[]), str(path), "exec"),
        exec_namespace,
    )
    return exec_namespace[name]


def test_v20_actual_registry_uses_inherited_storage_and_mixed_env_callbacks():
    """Execute the exact local A2 and StagedTaskBase method bodies in a CPU harness.

    IsaacSim's ``omni`` module is not needed to validate these pure tensor methods.  The
    harness executes the exact inherited registration/snapshot/indexing bodies, not a
    reimplementation or mocked index operation.
    """
    inherited_register = _extract_function(STAGED_SOURCE, "_register_buffer_to_track")
    inherited_snapshot = _extract_function(STAGED_SOURCE, "_take_snapshot_of_buffered_states")
    register_v20 = _extract_function(SOURCE, "_register_a2_v20_staged_reset_buffers")
    store_v20 = _extract_function(SOURCE, "_store_a2_v20_named_buffer")
    load_v20 = _extract_function(SOURCE, "_load_a2_v20_named_buffer")

    class DetachedDoorState:
        enable_staged_reset = True
        num_envs = 4
        num_stages = 2
        staged_reset_max_samples_per_stage = 3
        device = torch.device("cpu")

        def __init__(self):
            self.staged_reset_buf = {}
            self.staged_reset_num_samples = torch.zeros(2, 4, dtype=torch.long)
            self.stage_buf = torch.tensor([1, 0, 1, 0], dtype=torch.long)
            self._a2_v20_send_ready = torch.tensor([False, True, False, True])
            self._a2_v20_root_entry_pos_se2 = torch.arange(12, dtype=torch.float32).reshape(4, 3)
            self._a2_v20_handle_tcp_capture_quat = torch.tensor(
                [[1.0, 0.0, 0.0, 0.0]] * 4, dtype=torch.float32
            )

        def _register_buffer_to_track(self, *args, **kwargs):
            return inherited_register(self, *args, **kwargs)

    state = DetachedDoorState()
    state._store_a2_v20_named_buffer = store_v20.__get__(state)
    state._load_a2_v20_named_buffer = load_v20.__get__(state)
    register_v20(state)
    names = list(state.staged_reset_buf)
    assert len(names) == len(set(names)) == 17
    assert state.staged_reset_buf["a2_v20_send_ready"]["data"].shape == (2, 3, 4)
    for name, dtype in (("a2_v20_snapshot_crossing_seen", torch.bool), ("a2_v20_snapshot_root_x_rel", torch.float32)):
        data = state.staged_reset_buf[name]["data"]
        assert data.shape == (2, 3, 4)
        assert data.dtype is dtype
        assert data.device == state.device
    assert state.staged_reset_buf["a2_v20_root_entry_pos_se2"]["data"].shape == (2, 3, 4, 3)
    assert state.staged_reset_buf["a2_v20_handle_tcp_capture_quat"]["data"].shape == (2, 3, 4, 4)

    original = {}
    for name, case in state.staged_reset_buf.items():
        shape = tuple(case["data"].shape[2:])
        dtype = case["data"].dtype
        value = torch.arange(torch.tensor(shape).prod().item(), dtype=torch.float32).reshape(shape)
        if dtype == torch.bool:
            value = value.bool()
        elif dtype == torch.long:
            value = value.long()
        setattr(state, f"_{name}", value)
        original[name] = value.clone()

    advance_mask = torch.tensor([True, False, True, False])
    inherited_snapshot(state, advance_mask)
    selected_env_ids = torch.tensor([0, 2], dtype=torch.long)
    selected_stages = torch.tensor([1, 1], dtype=torch.long)
    selected_samples = torch.tensor([0, 0], dtype=torch.long)
    for name, case in state.staged_reset_buf.items():
        assert torch.equal(
            case["data"][selected_stages, selected_samples, selected_env_ids],
            original[name][selected_env_ids],
        )
        value = getattr(state, f"_{name}")
        mutated = torch.ones_like(value) if value.dtype == torch.bool else torch.full_like(value, -1)
        value[:] = mutated
        case["_mutated"] = mutated
    for name, case in state.staged_reset_buf.items():
        case["load_callback"](
            selected_env_ids,
            case["data"][selected_stages, selected_samples, selected_env_ids].clone(),
        )
        value = getattr(state, f"_{name}")
        assert torch.equal(value[selected_env_ids], original[name][selected_env_ids])
        untouched = torch.tensor([1, 3], dtype=torch.long)
        assert torch.equal(value[untouched], case["_mutated"][untouched])
    assert torch.equal(
        state._a2_v20_snapshot_crossing_seen[selected_env_ids],
        original["a2_v20_snapshot_crossing_seen"][selected_env_ids],
    )
    assert torch.equal(
        state._a2_v20_snapshot_root_x_rel[selected_env_ids],
        original["a2_v20_snapshot_root_x_rel"][selected_env_ids],
    )
    untouched = torch.tensor([1, 3], dtype=torch.long)
    assert torch.equal(
        state._a2_v20_snapshot_crossing_seen[untouched],
        state.staged_reset_buf["a2_v20_snapshot_crossing_seen"]["_mutated"][untouched],
    )
    assert torch.equal(
        state._a2_v20_snapshot_root_x_rel[untouched],
        state.staged_reset_buf["a2_v20_snapshot_root_x_rel"]["_mutated"][untouched],
    )

    env_ids = torch.tensor([1, 3], dtype=torch.long)
    send_ready = state.staged_reset_buf["a2_v20_send_ready"]
    position = state.staged_reset_buf["a2_v20_root_entry_pos_se2"]
    quaternion = state.staged_reset_buf["a2_v20_handle_tcp_capture_quat"]
    send_snapshot = send_ready["store_callback"](env_ids)
    position_snapshot = position["store_callback"](env_ids)
    quaternion_snapshot = quaternion["store_callback"](env_ids)
    assert send_snapshot.shape == (2,)
    assert position_snapshot.shape == (2, 3)
    assert quaternion_snapshot.shape == (2, 4)
    state._a2_v20_send_ready[:] = False
    state._a2_v20_root_entry_pos_se2[:] = -1.0
    state._a2_v20_handle_tcp_capture_quat[:] = 0.0
    send_ready["load_callback"](env_ids, send_snapshot)
    position["load_callback"](env_ids, position_snapshot)
    quaternion["load_callback"](env_ids, quaternion_snapshot)
    assert state._a2_v20_send_ready.tolist() == [False, True, False, True]
    assert torch.equal(state._a2_v20_root_entry_pos_se2[env_ids], position_snapshot)
    assert torch.equal(state._a2_v20_handle_tcp_capture_quat[env_ids], quaternion_snapshot)
    assert torch.all(state._a2_v20_root_entry_pos_se2[torch.tensor([0, 2])] == -1.0)
    with pytest.raises(RuntimeError, match="incompatible state"):
        send_ready["load_callback"](env_ids, torch.ones(2, 1, dtype=torch.bool))


def test_a2_init_reaches_v20_registration_before_method_return():
    source = SOURCE.read_text(encoding="utf-8")
    start = source.index("    def _init_a2_door_pregrasp_state")
    end = source.index("    def _register_a2_v20_staged_reset_buffers", start)
    method = source[start:end]
    assert method.index("self._register_a2_v20_staged_reset_buffers()") < len(method)
