"""Shared exact64 natural-reset checks for pull-v26.8 evaluation artifacts."""
from __future__ import annotations

import collections
from collections.abc import Mapping


EPISODES = 64
NATURAL_RATIOS = [1, 0, 0, 0, 0, 0]
START_RECORD_TYPE = "episode_start"
START_STAGE_FIELD = "a2_v26_episode_start_stage"
V6_BANK_SWITCHES = (
    "a2_pull_v6_stage4_bank_enabled",
    "a2_pull_v61_late_state_bank_enabled",
)
SIDE_SIGNS = {"left": 1.0, "right": -1.0}


class NaturalProtocolViolation(RuntimeError):
    """The frozen pull natural-reset protocol was not observed."""


def require(value: bool, message: str) -> None:
    if not value:
        raise NaturalProtocolViolation(message)


def validate_natural_config(env: Mapping) -> None:
    """Assert the pull-native Stage0-only reset configuration."""
    require(env.get("enable_staged_reset") is True, "natural protocol requires enable_staged_reset=true")
    ratios = env.get("staged_reset_ratios")
    require(ratios is not None and list(ratios) == NATURAL_RATIOS, f"natural protocol ratios are not {NATURAL_RATIOS}")
    for key in V6_BANK_SWITCHES:
        require(env.get(key) is False, f"natural protocol requires {key}=false")


def validate_natural_runtime(runtime: dict, *, side: str, mirror_enabled: bool) -> None:
    env = runtime["env"]["config"]
    evaluation = runtime["algo"]["config"]["eval"]
    require(runtime.get("num_envs") == EPISODES, "natural protocol requires 64 eval envs")
    require(env.get("a2_door_open_lr_distribution") == side, f"natural protocol side is not {side!r}")
    validate_natural_config(env)
    require(env.get("a2_v26_6_side_mirrored_handle_offset_enabled") is mirror_enabled, "mirror-switch contract")
    require(evaluation.get("num_eval_episodes") == EPISODES and evaluation.get("eval_num_envs_episodes") is True, "natural protocol requires first-episode exact64 evaluation")


def _validate_side(row: dict, side: str, label: str) -> None:
    actual = row.get("door_handle_side")
    sign = row.get("door_open_lr")
    require(actual in SIDE_SIGNS and isinstance(sign, (int, float)) and float(sign) == SIDE_SIGNS[actual], f"{label}: invalid side provenance")
    if side in SIDE_SIGNS:
        require(actual == side, f"{label}: side contamination")


def split_natural_trace_rows(trace: object, path: str, *, side: str) -> dict[int, list[dict]]:
    require(isinstance(trace, list), f"{path}: trace must be a list")
    starts: dict[int, tuple[int, dict]] = {}
    rows: dict[int, list[tuple[int, dict]]] = collections.defaultdict(list)
    for index, row in enumerate(trace):
        require(isinstance(row, dict), f"{path}: trace row {index} must be object")
        env_id = row.get("env_id")
        require(isinstance(env_id, int) and 0 <= env_id < EPISODES, f"{path}: invalid trace env id")
        if row.get("record_type") == START_RECORD_TYPE:
            require(env_id not in starts, f"{path}: duplicate episode_start env{env_id}")
            require(row.get("step_index") == -1, f"{path}: episode_start step index env{env_id}")
            require(row.get("stage_buf") == 0, f"{path}: episode_start stage is not zero env{env_id}")
            require(row.get("episode_index") == 0 and row.get("first_episode_active") is True, f"{path}: episode_start is not first episode env{env_id}")
            require(row.get(START_STAGE_FIELD) == 0, f"{path}: episode_start initial stage is not zero env{env_id}")
            _validate_side(row, side, f"{path}: episode_start env{env_id}")
            starts[env_id] = (index, row)
            continue
        require(row.get("first_episode_active") is True and row.get("episode_index") == 0, f"{path}: trace row {index} is not first episode")
        require(row.get(START_STAGE_FIELD) == 0, f"{path}: trace row {index} initial stage is not zero")
        _validate_side(row, side, f"{path}: trace row {index}")
        rows[env_id].append((index, row))
    require(set(starts) == set(range(EPISODES)), f"{path}: missing exact64 episode_start rows")
    result: dict[int, list[dict]] = {}
    for env_id in range(EPISODES):
        start_index, _ = starts[env_id]
        env_rows = rows.get(env_id, [])
        require(all(index > start_index for index, _ in env_rows), f"{path}: episode_start is not first persisted env{env_id}")
        result[env_id] = [row for _, row in env_rows]
    return result
