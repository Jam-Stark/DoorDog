import ast
import math
from pathlib import Path

import numpy as np
import pytest
import torch
from gr00t.rl.utils.average_meters import TensorAverageMeterDict
from omegaconf import OmegaConf


ROOT = Path(__file__).resolve().parents[3]
TRAINER_SOURCE = ROOT / "gr00t/rl/trl/trainer/ppo_trainer_a2_base_api.py"
V13_A_CONFIG = ROOT / "gr00t/rl/config/ablation/wbmanip/base_v13_A_main.yaml"
V13_1_CONFIG = ROOT / "gr00t/rl/config/ablation/wbmanip/base_v13_1_main.yaml"
OPTIONAL_RATIO_DENOMINATORS = {
    "a2_stage3_contact_stability_conditional_frac": (
        "a2_stage3_contact_stability_denominator_frac"
    ),
    "a2_stage4_contact_stability_conditional_frac": (
        "a2_stage4_contact_stability_denominator_frac"
    ),
    "a2_stage3_hold_and_drive_frac": "a2_stage3_hold_and_drive_denominator_frac",
    "a2_stage3_stage4_hold_and_drive_frac": "a2_stage3_stage4_hold_and_drive_denominator_frac",
    "a2_stage3_unlatch_hold_issued_frac": (
        "a2_stage3_unlatch_hold_issued_denominator_frac"
    ),
    "a2_stage3_stage4_coasting_frac": (
        "a2_stage3_stage4_coasting_denominator_frac"
    ),
    "a2_stage3_stage4_over_force_frac": (
        "a2_stage3_stage4_over_force_denominator_frac"
    ),
    "a2_stage3_handle_hard_limit_frac": (
        "a2_stage3_handle_hard_limit_denominator_frac"
    ),
    "a2_stage4_release_gate_frac": "a2_stage4_release_gate_denominator_frac",
}
OPTIONAL_RATIO_NUMERATORS = {
    "a2_stage3_contact_stability_conditional_frac": (
        "a2_stage3_contact_stability_numerator_frac"
    ),
    "a2_stage4_contact_stability_conditional_frac": (
        "a2_stage4_contact_stability_numerator_frac"
    ),
    "a2_stage3_hold_and_drive_frac": "a2_stage3_hold_and_drive_numerator_frac",
    "a2_stage3_stage4_hold_and_drive_frac": "a2_stage3_stage4_hold_and_drive_numerator_frac",
    "a2_stage3_unlatch_hold_issued_frac": (
        "a2_stage3_unlatch_hold_issued_numerator_frac"
    ),
    "a2_stage3_stage4_coasting_frac": (
        "a2_stage3_stage4_coasting_numerator_frac"
    ),
    "a2_stage3_stage4_over_force_frac": (
        "a2_stage3_stage4_over_force_numerator_frac"
    ),
    "a2_stage3_handle_hard_limit_frac": (
        "a2_stage3_handle_hard_limit_numerator_frac"
    ),
    "a2_stage4_release_gate_frac": "a2_stage4_release_gate_numerator_frac",
}

OPTIONAL_RATIO_SPECS = {
    ratio_key: (OPTIONAL_RATIO_NUMERATORS[ratio_key], denominator_key)
    for ratio_key, denominator_key in OPTIONAL_RATIO_DENOMINATORS.items()
}


def _trainer_ast():
    return ast.parse(TRAINER_SOURCE.read_text(encoding="utf-8"))


def _method_node(tree, name):
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            return node
    raise AssertionError(f"method {name!r} not found")


def _load_ratio_helper():
    source = TRAINER_SOURCE.read_text(encoding="utf-8")
    tree = ast.parse(source)
    nodes = []
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name)
            and target.id == "_A2_EVAL_OPTIONAL_RATIO_SPECS"
            for target in node.targets
        ):
            nodes.append(node)
        if isinstance(node, ast.FunctionDef) and node.name == "_normalize_a2_eval_optional_ratios":
            nodes.append(node)
    namespace = {"math": math, "np": np, "torch": torch}
    exec(
        compile(ast.Module(body=nodes, type_ignores=[]), str(TRAINER_SOURCE), "exec"),
        namespace,
    )
    return (
        namespace["_normalize_a2_eval_optional_ratios"],
        namespace["_A2_EVAL_OPTIONAL_RATIO_SPECS"],
    )


NORMALIZE_RATIOS, TRAINER_RATIO_MAPPING = _load_ratio_helper()


def _load_metric_helper():
    tree = ast.parse(TRAINER_SOURCE.read_text(encoding="utf-8"))
    names = (
        "_A2_EVAL_OPTIONAL_RATIO_SPECS",
        "_A2_GLOBAL_ENV_QUANTILE_SPECS",
        "_A2_ROOT_X_FIRST_CROSSING_ENV_COUNT_KEY",
        "_canonicalize_a2_metric_device",
        "_prepare_a2_env_metrics_for_aggregation",
        "_finalize_a2_conditional_ratios",
    )
    nodes = []
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id in names
            for target in node.targets
        ):
            nodes.append(node)
        if isinstance(node, ast.FunctionDef) and node.name in names:
            nodes.append(node)
    namespace = {"torch": torch}
    exec(
        compile(ast.Module(body=nodes, type_ignores=[]), str(TRAINER_SOURCE), "exec"),
        namespace,
    )
    return (
        namespace["_prepare_a2_env_metrics_for_aggregation"],
        namespace["_finalize_a2_conditional_ratios"],
        namespace["_canonicalize_a2_metric_device"],
    )


PREPARE_METRICS, FINALIZE_RATIOS, CANONICALIZE_METRIC_DEVICE = _load_metric_helper()


def test_metric_device_canonicalization_resolves_only_indexless_cuda(monkeypatch):
    current_device_calls = []

    def current_device():
        current_device_calls.append(True)
        return 3

    monkeypatch.setattr(torch.cuda, "current_device", current_device)

    assert CANONICALIZE_METRIC_DEVICE(torch.device("cuda")) == torch.device("cuda:3")
    assert current_device_calls == [True]

    explicit_cuda = torch.device("cuda:2")
    cpu = torch.device("cpu")
    assert CANONICALIZE_METRIC_DEVICE(explicit_cuda) is explicit_cuda
    assert CANONICALIZE_METRIC_DEVICE(cpu) is cpu
    assert current_device_calls == [True]

    with pytest.raises(TypeError, match="torch.device"):
        CANONICALIZE_METRIC_DEVICE("cuda")


def test_optional_ratio_mapping_is_exact_and_zero_is_json_null_with_raw_fields_retained():
    assert TRAINER_RATIO_MAPPING == OPTIONAL_RATIO_SPECS

    record = {}
    raw_fields = {}
    for ratio_key, denominator_key in OPTIONAL_RATIO_DENOMINATORS.items():
        numerator_key = OPTIONAL_RATIO_NUMERATORS[ratio_key]
        ratio = torch.tensor(0.75)
        numerator = torch.tensor(0.25)
        denominator = torch.tensor(0.0)
        record[ratio_key] = ratio
        record[numerator_key] = numerator
        record[denominator_key] = denominator
        raw_fields[numerator_key] = numerator
        raw_fields[denominator_key] = denominator

    records = [record]
    assert NORMALIZE_RATIOS(records) is records
    for ratio_key, denominator_key in OPTIONAL_RATIO_DENOMINATORS.items():
        numerator_key = OPTIONAL_RATIO_NUMERATORS[ratio_key]
        assert record[ratio_key] is None
        assert record[numerator_key] is raw_fields[numerator_key]
        assert record[denominator_key] is raw_fields[denominator_key]


def test_optional_ratio_positive_denominator_leaves_ratio_unchanged():
    for ratio_key, denominator_key in OPTIONAL_RATIO_DENOMINATORS.items():
        ratio = torch.tensor(0.75)
        record = {
            ratio_key: ratio,
            denominator_key: torch.tensor(2.0),
        }
        NORMALIZE_RATIOS([record])
        assert record[ratio_key] is ratio


def test_optional_ratio_rejects_missing_invalid_nonscalar_and_nonfinite_denominators():
    ratio_key, denominator_key = next(iter(OPTIONAL_RATIO_DENOMINATORS.items()))
    invalid_denominators = (
        torch.tensor([0.0]),
        np.array([0.0]),
        "0",
        None,
        float("nan"),
        float("inf"),
        -1.0,
    )
    for denominator in invalid_denominators:
        with pytest.raises(ValueError, match="denominator"):
            NORMALIZE_RATIOS([{ratio_key: torch.tensor(0.5), denominator_key: denominator}])

    with pytest.raises(ValueError, match="denominator"):
        NORMALIZE_RATIOS([{ratio_key: torch.tensor(0.5)}])




def test_prepare_conditional_ratios_is_vectorized_and_sample_weighted():
    ratio_keys = list(OPTIONAL_RATIO_SPECS)
    first_ratio, second_ratio = ratio_keys[:2]
    first_numerator, first_denominator = OPTIONAL_RATIO_SPECS[first_ratio]
    second_numerator, second_denominator = OPTIONAL_RATIO_SPECS[second_ratio]
    metrics = {
        first_ratio: torch.tensor(0.5),
        first_numerator: torch.tensor(1.0),
        first_denominator: torch.tensor(2.0),
        second_ratio: torch.tensor(0.75),
        second_numerator: torch.tensor(3.0),
        second_denominator: torch.tensor(4.0),
    }
    accelerator = _RecordingAccelerator(
        torch.tensor([1.0, 2.0, 3.0, 4.0, 4.0, 8.0, 1.0, 2.0])
    )

    prepared = PREPARE_METRICS(metrics, accelerator, torch.device("cpu"))

    assert len(accelerator.calls) == 1
    torch.testing.assert_close(
        accelerator.calls[0],
        torch.tensor([1.0, 2.0, 3.0, 4.0]),
    )
    assert first_ratio not in prepared
    assert second_ratio not in prepared
    assert prepared[first_numerator].item() == pytest.approx(5.0)
    assert prepared[first_denominator].item() == pytest.approx(10.0)
    assert prepared[second_numerator].item() == pytest.approx(4.0)
    assert prepared[second_denominator].item() == pytest.approx(6.0)

    finalized = FINALIZE_RATIOS(prepared)
    assert finalized[first_ratio].item() == pytest.approx(0.5)
    assert finalized[second_ratio].item() == pytest.approx(4.0 / 6.0)


def test_conditional_ratio_metering_ignores_inactive_zero_denominator_steps():
    ratio_key, (numerator_key, denominator_key) = next(iter(OPTIONAL_RATIO_SPECS.items()))
    meters = TensorAverageMeterDict()
    meters.add(
        PREPARE_METRICS(
            {
                ratio_key: torch.tensor(0.5),
                numerator_key: torch.tensor(2.0),
                denominator_key: torch.tensor(4.0),
            },
            _IdentityAccelerator(),
            torch.device("cpu"),
        )
    )
    meters.add(
        PREPARE_METRICS(
            {
                ratio_key: torch.tensor(0.0),
                numerator_key: torch.tensor(0.0),
                denominator_key: torch.tensor(0.0),
            },
            _IdentityAccelerator(),
            torch.device("cpu"),
        )
    )

    metered = meters.mean_and_clear()
    assert ratio_key not in metered
    finalized = FINALIZE_RATIOS(metered)
    assert finalized[ratio_key].item() == pytest.approx(0.5)


def test_zero_denominator_finalizes_finite_zero_then_eval_normalizes_to_na():
    ratio_key, (numerator_key, denominator_key) = next(iter(OPTIONAL_RATIO_SPECS.items()))
    finalized = FINALIZE_RATIOS(
        {
            numerator_key: torch.tensor(0.0),
            denominator_key: torch.tensor(0.0),
        }
    )
    assert finalized[ratio_key].item() == 0.0
    assert bool(torch.isfinite(finalized[ratio_key]))

    records = [finalized]
    NORMALIZE_RATIOS(records)
    assert records[0][ratio_key] is None
    assert records[0][numerator_key].item() == 0.0
    assert records[0][denominator_key].item() == 0.0


def test_ratio_helper_is_eval_only_and_training_env_metrics_are_cross_rank_gathered():
    tree = _trainer_ast()
    train_node = _method_node(tree, "train")
    process_node = _method_node(tree, "_process_env_step")
    eval_node = _method_node(tree, "eval")

    env_assignment = next(
        node
        for node in ast.walk(train_node)
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Name) and target.id == "env_log_dict"
            for target in node.targets
        )
    )
    assert isinstance(env_assignment.value, ast.DictComp)
    env_mean_line = next(
        node.lineno
        for node in ast.walk(train_node)
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Name) and target.id == "env_log_dict_local"
            for target in node.targets
        )
        and isinstance(node.value, ast.Call)
        and isinstance(node.value.func, ast.Attribute)
        and node.value.func.attr == "mean_and_clear"
    )
    train_finalize_line = next(
        node.lineno
        for node in ast.walk(train_node)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "_finalize_a2_conditional_ratios"
    )
    rank_gather_lines = [
        node.lineno
        for node in ast.walk(env_assignment.value)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "gather_for_metrics"
    ]
    assert env_mean_line < train_finalize_line < min(rank_gather_lines)
    assert any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "gather_for_metrics"
        for node in ast.walk(env_assignment.value)
    )
    assert any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "mean"
        for node in ast.walk(env_assignment.value)
    )
    assert any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "item"
        for node in ast.walk(env_assignment.value)
    )
    assert any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "add"
        and any(
            isinstance(argument, ast.Name)
            and argument.id == "prepared_env_metrics"
            for argument in node.args
        )
        for node in ast.walk(process_node)
    )
    assert not any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "_normalize_a2_eval_optional_ratios"
        for node in ast.walk(process_node)
    )
    assert not any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "_normalize_a2_eval_optional_ratios"
        for node in ast.walk(train_node)
    )

    merge_line = next(
        node.lineno
        for node in ast.walk(eval_node)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "update"
        and any(
            isinstance(argument, ast.Name)
            and argument.id == "prepared_env_metrics"
            for argument in node.args
        )
    )
    eval_prepare_line = next(
        node.lineno
        for node in ast.walk(eval_node)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "_prepare_a2_env_metrics_for_aggregation"
    )
    eval_finalize_line = next(
        node.lineno
        for node in ast.walk(eval_node)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "_finalize_a2_conditional_ratios"
    )
    assert eval_prepare_line < eval_finalize_line < merge_line
    helper_lines = [
        node.lineno
        for node in ast.walk(eval_node)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "_normalize_a2_eval_optional_ratios"
    ]
    safe_to_log_lines = [
        node.lineno
        for node in ast.walk(eval_node)
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Name)
            and target.id in {"strict_safe_to_log_metrics", "safe_to_log_metrics"}
            for target in node.targets
        )
        and isinstance(node.value, ast.Call)
        and isinstance(node.value.func, ast.Name)
        and node.value.func.id == "_make_json_safe"
    ]
    assert len(helper_lines) == 2
    assert len(safe_to_log_lines) == 2
    assert min(helper_lines) > merge_line
    assert sorted(helper_lines)[0] < sorted(safe_to_log_lines)[0]
    assert sorted(helper_lines)[1] < sorted(safe_to_log_lines)[1]


class _FakeAccelerator:
    def __init__(self, gathered):
        self.gathered = list(gathered)

    def gather(self, value):
        if not self.gathered:
            raise AssertionError("unexpected gather call")
        gathered = self.gathered.pop(0)
        assert gathered.dtype == value.dtype
        assert gathered.device == value.device
        return gathered


class _IdentityAccelerator:
    def gather(self, value):
        return value




class _RecordingAccelerator:
    def __init__(self, gathered):
        self.gathered = gathered
        self.calls = []

    def gather(self, value):
        self.calls.append(value.detach().clone())
        assert self.gathered.dtype == value.dtype
        assert self.gathered.device == value.device
        return self.gathered
def _valid_env_metrics():
    return {
        "a2_root_x_first_crossing_env_count": torch.tensor(2.0),
        "_a2_stage5_forward_velocity_samples": torch.tensor([0.0, 100.0]),
        "_a2_stage5_forward_velocity_sample_mask": torch.tensor([True, True]),
        "a2_stage5_forward_velocity_p50": torch.tensor(-1.0),
        "a2_stage5_forward_velocity_p95": torch.tensor(-1.0),
        "_a2_stage45_doorframe_contact_force_samples": torch.tensor([1.0, 2.0]),
        "_a2_stage45_doorframe_contact_force_sample_mask": torch.tensor([True, True]),
        "a2_stage45_doorframe_contact_force_p50": torch.tensor(-1.0),
        "a2_stage45_doorframe_contact_force_p95": torch.tensor(-1.0),
        "ordinary_metric": torch.tensor(4.0),
    }


def test_global_metric_helper_sums_counts_and_computes_exact_global_quantiles():
    device = torch.device("cpu")
    metrics = _valid_env_metrics()
    original_count = metrics["a2_root_x_first_crossing_env_count"].clone()
    accelerator = _FakeAccelerator(
        [
            torch.tensor([2.0, 5.0]),
            torch.tensor([0.0, 100.0, 10.0, 20.0]),
            torch.tensor([True, True, True, False]),
            torch.tensor([1.0, 2.0, 20.0, 40.0]),
            torch.tensor([True, True, True, False]),
        ]
    )

    prepared = PREPARE_METRICS(metrics, accelerator, device)

    assert prepared is not metrics
    assert prepared["a2_root_x_first_crossing_env_count"].item() == 7.0
    assert prepared["a2_stage5_forward_velocity_p50"].item() == 10.0
    assert prepared["a2_stage5_forward_velocity_p95"].item() == 91.0
    assert prepared["a2_stage45_doorframe_contact_force_p50"].item() == 2.0
    assert prepared["a2_stage45_doorframe_contact_force_p95"].item() == pytest.approx(18.2)
    assert prepared["ordinary_metric"] is metrics["ordinary_metric"]
    assert metrics["a2_root_x_first_crossing_env_count"].item() == original_count.item()
    assert all(
        key not in prepared
        for key in (
            "_a2_stage5_forward_velocity_samples",
            "_a2_stage5_forward_velocity_sample_mask",
            "_a2_stage45_doorframe_contact_force_samples",
            "_a2_stage45_doorframe_contact_force_sample_mask",
        )
    )


def test_global_metric_helper_has_valid_single_process_inactive_quantile_path():
    metrics = _valid_env_metrics()
    metrics["_a2_stage5_forward_velocity_sample_mask"] = torch.tensor([False, False])
    metrics["_a2_stage45_doorframe_contact_force_sample_mask"] = torch.tensor(
        [False, False]
    )
    prepared = PREPARE_METRICS(metrics, _IdentityAccelerator(), torch.device("cpu"))
    assert prepared["a2_stage5_forward_velocity_p50"].item() == 0.0
    assert prepared["a2_stage5_forward_velocity_p95"].item() == 0.0
    assert prepared["a2_stage45_doorframe_contact_force_p50"].item() == 0.0
    assert prepared["a2_stage45_doorframe_contact_force_p95"].item() == 0.0


def test_global_metric_helper_rejects_invalid_dtype_shape_and_finite_contracts():
    invalid_metrics = []
    metrics = _valid_env_metrics()
    metrics["a2_root_x_first_crossing_env_count"] = torch.tensor(2, dtype=torch.long)
    invalid_metrics.append(metrics)
    metrics = _valid_env_metrics()
    metrics["_a2_stage5_forward_velocity_samples"] = torch.tensor([1, 2], dtype=torch.long)
    invalid_metrics.append(metrics)
    metrics = _valid_env_metrics()
    metrics["_a2_stage5_forward_velocity_samples"] = torch.tensor([[1.0, 2.0]])
    invalid_metrics.append(metrics)
    metrics = _valid_env_metrics()
    metrics["_a2_stage5_forward_velocity_sample_mask"] = torch.tensor([1.0, 0.0])
    invalid_metrics.append(metrics)
    metrics = _valid_env_metrics()
    metrics["_a2_stage5_forward_velocity_samples"][0] = float("nan")
    invalid_metrics.append(metrics)

    for invalid in invalid_metrics:
        with pytest.raises(ValueError):
            PREPARE_METRICS(invalid, _IdentityAccelerator(), torch.device("cpu"))


def test_global_metric_helper_is_before_meter_and_eval_merge():
    tree = _trainer_ast()
    process_node = _method_node(tree, "_process_env_step")
    eval_node = _method_node(tree, "eval")
    process_prepare = [
        node.lineno
        for node in ast.walk(process_node)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "_prepare_a2_env_metrics_for_aggregation"
    ]
    process_add = next(
        node.lineno
        for node in ast.walk(process_node)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "add"
    )
    eval_prepare = [
        node.lineno
        for node in ast.walk(eval_node)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "_prepare_a2_env_metrics_for_aggregation"
    ]
    eval_merge = next(
        node.lineno
        for node in ast.walk(eval_node)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "update"
        and any(
            isinstance(argument, ast.Name)
            and argument.id == "prepared_env_metrics"
            for argument in node.args
        )
    )
    assert process_prepare and max(process_prepare) < process_add
    assert eval_prepare and max(eval_prepare) < eval_merge

def test_v13_1_config_is_v13_a_semantics_with_bounded_m15_overrides():
    config = OmegaConf.load(V13_1_CONFIG)
    v13_a = OmegaConf.load(V13_A_CONFIG)

    assert config.checkpoint == (
        "logs_rl/a2_piper_full_stage_a2_base/"
        "base_v13_A_main-20260716_225345/model_step_003000.pt"
    )
    assert (ROOT / config.checkpoint).is_file()
    assert config.checkpoint_load_mode == "policy_only"
    assert config.auto_load_latest is False
    assert config.seed == 0
    assert config.num_envs == 1024
    assert config.num_envs * 4 == 4096
    assert config.headless is True
    assert config.algo.trl.num_total_batches == 2000
    assert config.callbacks.model_save.save_frequency == 250

    v13_a_env = OmegaConf.to_container(v13_a.env.config, resolve=True)
    config_env = OmegaConf.to_container(config.env.config, resolve=True)
    for key, value in v13_a_env.items():
        assert config_env[key] == value
    assert config_env["a2_stage2_contact_force_threshold"] == 1.0
    assert config_env["a2_stage2_squeeze_force_min"] == 2.0
    assert config_env["a2_stage2_squeeze_force_max"] == 20.0
    assert config_env["a2_stage2_over_force_threshold"] == 40.0
    assert config_env["a2_grasp_gate_mode"] == "control_streak"
    assert config_env["a2_grasp_streak_control_steps"] == 5
    assert config_env["a2_stage3_to4_door_hinge_threshold"] == 0.25
    assert config_env["a2_stage3_to4_requires_grasp_streak"] is True
    assert config_env["a2_stage3_base_unlocked"] is True
    assert config_env["a2_stage4_release_hinge_threshold"] == 1.2
    assert config_env["a2_stage45_door_frame_contact_scale"] == 0.2

    for section in ("rewards", "robot", "simulator"):
        assert OmegaConf.to_container(config[section], resolve=True) == OmegaConf.to_container(
            v13_a[section], resolve=True
        )
    assert not (V13_1_CONFIG.parent / "base_v13_1_noM13.yaml").exists()
