"""Pure tests for the v14 M18 reachability-map decision logic."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = ROOT / "gr00t/rl/scripts/a2_piper_v14_reachability_map.py"
SPEC = importlib.util.spec_from_file_location("a2_piper_v14_reachability_map", SCRIPT_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def _cell(handle: float, standoff: float, root: float, *, feasible: bool) -> object:
    return MODULE.GridCell(
        handle_height_m=handle,
        standoff_m=standoff,
        root_height_m=root,
        tcp_error_m=0.01 if feasible else 0.04,
        self_collision=False,
        self_collision_evidence="max_robot_self_contact_n=0;source=none",
        min_joint_limit_margin_rad=0.20 if feasible else 0.09,
        arm_j6_margin_rad=0.20 if feasible else 0.09,
    )


def test_exact_m18_grid_has_210_cells_and_fixed_values():
    cells = MODULE.build_grid_cells()
    assert len(cells) == 7 * 10 * 3
    assert MODULE.HANDLE_HEIGHTS_M == (0.80, 0.85, 0.90, 0.95, 1.00, 1.05, 1.10)
    assert MODULE.STANDOFFS_M == (0.40, 0.45, 0.50, 0.55, 0.60, 0.65, 0.70, 0.75, 0.80, 0.85)
    assert MODULE.ROOT_HEIGHTS_M == (0.55, 0.65, 0.75)
    assert len(MODULE.M18_ROBOT_BODY_NAMES) == 27
    assert len(set(MODULE.M18_ROBOT_BODY_NAMES)) == 27
    assert len(MODULE.M18_ARM_BODY_NAMES) == 10
    assert set(MODULE.M18_ARM_BODY_NAMES) < set(MODULE.M18_ROBOT_BODY_NAMES)


def test_handle_height_shards_merge_to_exact_grid(tmp_path):
    shard_csvs = []
    for handle_height in MODULE.HANDLE_HEIGHTS_M:
        specs = MODULE.select_grid_cells(handle_height)
        assert len(specs) == 10 * 3
        assert {spec[0] for spec in specs} == {handle_height}
        for root_height in MODULE.ROOT_HEIGHTS_M:
            root_specs = MODULE.select_grid_cells(handle_height, root_height)
            assert len(root_specs) == 10
            assert {spec[0] for spec in root_specs} == {handle_height}
            assert {spec[2] for spec in root_specs} == {root_height}
            single = MODULE.select_grid_cells(
                handle_height, root_height, MODULE.STANDOFFS_M[0]
            )
            assert single == [(handle_height, MODULE.STANDOFFS_M[0], root_height)]
        cells = [
            _cell(handle, standoff, root, feasible=True)
            for handle, standoff, root in specs
        ]
        summary = MODULE.summarize_reachability(cells)
        csv_path, _json_path, _markdown_path = MODULE.write_reachability_outputs(
            tmp_path / f"height_{handle_height:.2f}",
            cells,
            summary,
            stem="shard",
        )
        shard_csvs.append(csv_path)

    merged = MODULE.read_reachability_csvs(shard_csvs)
    assert [
        (cell.handle_height_m, cell.standoff_m, cell.root_height_m)
        for cell in merged
    ] == MODULE.build_grid_cells()
    selection = MODULE.summarize_reachability(merged)["selection"]
    assert selection["highest_feasible_handle_cap_m"] == 1.10
    assert selection["maximal_continuous_standoff_band_m"]["values"] == list(
        MODULE.STANDOFFS_M
    )
    assert selection["retained_high_handles_m"] == [1.00, 1.05, 1.10]
    assert selection["retained_high_handles_require_root_height_ge_0_7"] is False

    near_grid_csv = tmp_path / "near_grid.csv"
    shard_text = shard_csvs[0].read_text(encoding="utf-8")
    exact_cell = "0.8,0.4,0.55,"
    assert shard_text.count(exact_cell) == 1
    near_grid_csv.write_text(
        shard_text.replace(exact_cell, "0.804,0.4,0.55,", 1),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="exact 210-cell grid"):
        MODULE.read_reachability_csvs([near_grid_csv, *shard_csvs[1:]])

    with pytest.raises(ValueError, match="exact 210-cell grid"):
        MODULE.read_reachability_csvs(shard_csvs[:-1])


def test_feasibility_is_strict_and_missing_evidence_is_infeasible():
    good = _cell(0.80, 0.40, 0.55, feasible=True)
    assert MODULE.assess_cell(good)[0] is True
    assert MODULE.assess_cell(
        MODULE.GridCell(
            **{
                **good.__dict__,
                "tcp_error_m": 0.03,
            }
        )
    )[0] is False
    assert MODULE.assess_cell(
        MODULE.GridCell(
            **{
                **good.__dict__,
                "self_collision": True,
            }
        )
    )[0] is False
    missing = MODULE.GridCell(0.80, 0.40, 0.55, None, None, None, None, None)
    feasible, reasons = MODULE.assess_cell(missing)
    assert feasible is False
    assert any(reason.startswith("missing_or_nonfinite") for reason in reasons)


def test_summary_uses_any_root_height_and_highest_cap_then_band_tie_rule():
    handles = (0.80, 0.85, 0.90, 0.95)
    standoffs = (0.40, 0.45, 0.50)
    roots = (0.55, 0.65)
    cells = []
    for handle in handles:
        for standoff in standoffs:
            for root in roots:
                # The first root is infeasible for every cell. The second root
                # carries the usable band through 0.90 m, proving the OR rule.
                feasible = root == 0.65 and (
                    handle <= 0.90 and standoff in (0.40, 0.45)
                )
                cells.append(_cell(handle, standoff, root, feasible=feasible))

    summary = MODULE.summarize_reachability(cells)
    selection = summary["selection"]
    assert selection["highest_feasible_handle_cap_m"] == 0.90
    assert selection["retained_handle_heights_m"] == [0.80, 0.85, 0.90]
    assert selection["maximal_continuous_standoff_band_m"]["values"] == [0.40, 0.45]
    assert selection["one_point_ten_m_allowed"] is False
    assert "highest handle-height cap" in selection["tie_rule"]
    assert summary["minimum_feasible_root_height_by_handle_m"]["0.9"] == 0.65
    assert selection["retained_high_handles_require_root_height_ge_0_7"] is None


def test_summary_records_high_handle_root_height_requirement():
    cells = [
        _cell(handle, 0.55, root, feasible=root == 0.75)
        for handle in (1.00, 1.05)
        for root in (0.65, 0.75)
    ]

    summary = MODULE.summarize_reachability(cells)
    selection = summary["selection"]
    assert selection["highest_feasible_handle_cap_m"] == 1.05
    assert selection["retained_high_handles_m"] == [1.00, 1.05]
    assert selection["retained_high_handles_require_root_height_ge_0_7"] is True
    assert summary["minimum_feasible_root_height_by_handle_m"] == {
        "1.0": 0.75,
        "1.05": 0.75,
    }


def test_runtime_is_fail_fast_and_has_no_remote_ground_dependency():
    source = SCRIPT_PATH.read_text(encoding="utf-8")
    assert 'SimulationApp({"headless": True, "fast_shutdown": True})' in source
    assert "GroundPlaneCfg" not in source
    assert "ContactSensorCfg" not in source
    assert "filter_prim_paths_expr=" not in source
    assert "CollisionPropertiesCfg(collision_enabled=False)" in source
    assert "replicate_physics=False" in source
    assert "subscribe_contact_report_events" not in source
    assert "get_physx_simulation_interface().get_contact_report()" in source
    assert "ContactEventType.CONTACT_PERSIST" in source
    assert "PhysicsSchemaTools.intToSdfPath" in source
    assert "sim.clear_all_callbacks()" in source
    assert "sim.clear_instance()" in source
    assert source.index("return _write_reachability_result(args, cells)") < source.index(
        "simulation_app.close()"
    )
    assert source.index("    sim.reset()") < source.index(
        "    actual_body_names = list(robot.body_names)"
    )
    final_probe = source.index("; collecting final contact frame", source.index("def _run_ik_runtime"))
    final_step = source.index("    sim.step()", final_probe)
    final_collect = source.index("    collision, collision_max_force", final_step)
    assert final_probe < final_step < final_collect
    assert "@step=" not in source
    assert 'final_joint_margins = _soft_joint_margins(robot, arm_joint_ids)' in source


def test_contact_actor_path_parser_is_exact_and_fail_fast():
    assert MODULE._parse_m18_robot_actor_path(
        "/World/envs/env_12/Robot/arm_body6_to_gripper"
    ) == (12, "arm_body6_to_gripper")
    assert MODULE._parse_m18_robot_actor_path("/World/envs/env_0/door/panel") is None
    with pytest.raises(RuntimeError, match="unknown robot body"):
        MODULE._parse_m18_robot_actor_path("/World/envs/env_0/Robot/not_a_body")
    with pytest.raises(RuntimeError, match="invalid env token"):
        MODULE._parse_m18_robot_actor_path("/World/envs/env_x/Robot/arm_body0")


def test_output_contract_includes_csv_and_option_a_summary(tmp_path):
    cells = [_cell(0.80, 0.40, 0.55, feasible=True)]
    summary = MODULE.summarize_reachability(cells)
    csv_path, json_path, markdown_path = MODULE.write_reachability_outputs(
        tmp_path, cells, summary, stem="reachability"
    )
    assert csv_path.is_file() and json_path.is_file() and markdown_path.is_file()
    assert "self_collision_evidence" in csv_path.read_text(encoding="utf-8")
    assert "static diagnostic placement" in json_path.read_text(encoding="utf-8")
    assert "not action/command dimensions" in markdown_path.read_text(encoding="utf-8")
    assert "Minimum feasible root height" in markdown_path.read_text(encoding="utf-8")
