"""Generate the fail-fast base_v20 seven-cell training launcher.

This module only writes a launcher bundle.  It never invokes ``tmux``,
``accelerate`` or Isaac Sim.  The generated command and wrapper files are the
source of truth for the later formal run.

Each process exposes exactly one physical GPU through ``CUDA_VISIBLE_DEVICES``
and addresses it as logical ``cuda:0``.  This isolates both CUDA and IsaacSim's
Vulkan context from the reserved GPU7.  ``num_envs`` remains owned by each
ablation config; this launcher does not override it.
"""

from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
import os
import re
import shlex
import subprocess
from pathlib import Path
from typing import Any, Mapping, Sequence

import yaml


class LauncherError(RuntimeError):
    """Raised when launcher provenance or the no-overwrite contract is invalid."""


ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = ROOT / "gr00t/rl/config/ablation/wbmanip"
SOURCE_PATH = ROOT / "gr00t/rl/train_agent_trl.py"
ACCELERATE_PATH = Path("/home/baoquanc/anaconda3/envs/isaaclab/bin/accelerate")
CHECKPOINT_RELATIVE = Path(
    "logs_rl/a2_piper_full_stage_a2_base/base_v19/"
    "base_v19_G2_norm_control-20260727_012027/model_step_002000.pt"
)
CHECKPOINT_SHA256 = "b331c9a343c71dccf6cce31f71c1727a24298d72808c25763a0f702c369a866d"
LAUNCHER_PARENT_RELATIVE = Path("logs_rl/launchers/base_v20")
TRAINING_ROOT_RELATIVE = Path("logs_rl/a2_piper_full_stage_a2_base/base_v20")
SOURCE_RELATIVE = Path("gr00t/rl/train_agent_trl.py")
PROJECT_NAME = "a2_piper_full_stage_a2_base"
EXP_NAME = "wbmanip/door_open_a2_base_lstm"
PORT_BASE = 29620
RESERVED_GPU = 7
SCHEMA = "a2_piper_v20_launcher_v1"
_SAFE_TOKEN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_COMMIT = re.compile(r"^[0-9a-f]{40,64}$")
WANDB_MODES = ("online", "offline", "disabled")


@dataclasses.dataclass(frozen=True)
class GroupSpec:
    """One immutable row of the approved seven-cell matrix."""

    group: str
    gpu: int
    seed: int
    config_name: str
    experiment_name: str

    @property
    def config_filename(self) -> str:
        return f"{self.config_name}.yaml"


GROUPS: tuple[GroupSpec, ...] = (
    GroupSpec("G1", 0, 0, "base_v20_G1_g2_continuation", "base_v20_G1_g2_continuation"),
    GroupSpec("G2", 1, 0, "base_v20_G2_economics_only", "base_v20_G2_economics_only"),
    GroupSpec("G3", 2, 0, "base_v20_G3_send_institution_only", "base_v20_G3_send_institution_only"),
    GroupSpec("G4", 3, 0, "base_v20_G4_send_economics", "base_v20_G4_send_economics"),
    GroupSpec("G5", 4, 0, "base_v20_G5_send_arm_tie", "base_v20_G5_send_arm_tie"),
    GroupSpec("G6", 5, 0, "base_v20_G6_full", "base_v20_G6_full"),
    GroupSpec("G7", 6, 1, "base_v20_G7_full_seed1", "base_v20_G7_full_seed1"),
)


@dataclasses.dataclass(frozen=True)
class GroupPaths:
    """Generated paths for one group's command and runtime evidence."""

    root: Path
    command: Path
    wrapper: Path
    log: Path
    start: Path
    end: Path
    pid: Path
    exit_code: Path
    natural_exit: Path
    runtime_metadata: Path
    wandb_metadata: Path


def _absolute(path: Path | str, *, label: str) -> Path:
    value = Path(path).expanduser()
    if not value.is_absolute():
        raise LauncherError(f"{label} must be an absolute path after normalization: {value}")
    return value.resolve()


def _safe_token(value: str, *, label: str) -> str:
    if not isinstance(value, str) or not _SAFE_TOKEN.fullmatch(value) or ".." in value:
        raise LauncherError(f"{label} must be a simple non-empty filename token: {value!r}")
    return value


def _validate_wandb_mode(value: str) -> str:
    if value not in WANDB_MODES:
        raise LauncherError(
            f"WANDB_MODE must be explicitly one of {', '.join(WANDB_MODES)}; got {value!r}"
        )
    return value


def _validate_sha256(value: str, *, label: str) -> str:
    if not isinstance(value, str) or not _SHA256.fullmatch(value):
        raise LauncherError(f"{label} must be a lowercase SHA-256 hex digest")
    return value


def sha256_file(path: Path | str) -> str:
    """Hash one existing regular file without silently accepting a missing input."""

    path = Path(path)
    if not path.is_file():
        raise LauncherError(f"cannot hash missing file: {path}")
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _git_identity(repo_root: Path) -> tuple[str, str]:
    """Return branch and commit, failing if repository provenance is unavailable."""

    def run(*args: str) -> str:
        try:
            result = subprocess.run(
                ["git", "-C", str(repo_root), *args],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
        except (OSError, subprocess.CalledProcessError) as exc:
            detail = getattr(exc, "stderr", "") or str(exc)
            raise LauncherError(f"git provenance command failed ({' '.join(args)}): {detail.strip()}") from exc
        value = result.stdout.strip()
        if not value:
            raise LauncherError(f"git provenance command returned no value: {' '.join(args)}")
        return value

    branch = run("rev-parse", "--abbrev-ref", "HEAD")
    commit = run("rev-parse", "HEAD")
    return branch, commit


def _mapping(value: Any, *, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise LauncherError(f"{label} must be a mapping")
    return value


def _validate_config_contract(
    path: Path, spec: GroupSpec, *, require_formal_bundle: bool
) -> dict[str, Any]:
    """Validate the config-owned v20 settings before emitting a command."""

    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        raise LauncherError(f"cannot parse config {path}: {exc}") from exc
    config = _mapping(raw, label=f"config {path}")
    expected: dict[str, Any] = {
        "checkpoint": CHECKPOINT_RELATIVE.as_posix(),
        "checkpoint_load_mode": "policy_only",
        "auto_load_latest": False,
        "seed": spec.seed,
        "num_envs": 4096,
        "headless": True,
    }
    for key, expected_value in expected.items():
        actual = config.get(key)
        if actual != expected_value or isinstance(expected_value, bool) and not isinstance(actual, bool):
            raise LauncherError(
                f"{spec.group} config {path} violates {key}={expected_value!r}; got {actual!r}"
            )
    algo = _mapping(config.get("algo"), label=f"{path}: algo")
    trl = _mapping(algo.get("trl"), label=f"{path}: algo.trl")
    if trl.get("num_total_batches") != 2500:
        raise LauncherError(f"{spec.group} config must own algo.trl.num_total_batches=2500")
    callbacks = _mapping(config.get("callbacks"), label=f"{path}: callbacks")
    model_save = _mapping(callbacks.get("model_save"), label=f"{path}: callbacks.model_save")
    if model_save.get("save_frequency") != 250:
        raise LauncherError(f"{spec.group} config must own callbacks.model_save.save_frequency=250")
    env_config = _mapping(config.get("env"), label=f"{path}: env").get("config")
    env_config = _mapping(env_config, label=f"{path}: env.config")
    provenance = (
        env_config.get("a2_v20_formal_launch"),
        env_config.get("a2_v20_formal_values_frozen"),
        env_config.get("a2_v20_calibration_label"),
    )
    if (
        not isinstance(provenance[0], bool)
        or not isinstance(provenance[1], bool)
        or not isinstance(provenance[2], str)
        or not provenance[2]
    ):
        raise LauncherError(
            f"{spec.group} config must declare the complete v20 provenance triple"
        )
    expected_nonformal = (False, False, "non_formal_calibration_only")
    if require_formal_bundle:
        if provenance[0] is not True or provenance[1] is not True or provenance[2] == expected_nonformal[2]:
            raise LauncherError(
                f"{spec.group} config is not formal-launch eligible; requires "
                "formal_launch=true, formal_values_frozen=true, and a frozen calibration label"
            )
    elif provenance != expected_nonformal:
        raise LauncherError(
            f"{spec.group} non-formal config provenance must be "
            "(formal_launch=false, formal_values_frozen=false, "
            "calibration_label=non_formal_calibration_only)"
        )
    config["_v20_provenance"] = provenance
    return dict(config)


def _resolve_config_paths(config_dir: Path, config_paths: Mapping[str, Path] | None) -> dict[str, Path]:
    result: dict[str, Path] = {}
    for spec in GROUPS:
        candidate = config_paths[spec.group] if config_paths is not None and spec.group in config_paths else config_dir / spec.config_filename
        path = _absolute(candidate, label=f"{spec.group} config")
        if not path.is_file():
            raise LauncherError(f"missing {spec.group} config: {path}")
        result[spec.group] = path
    if config_paths is not None and set(config_paths) != {spec.group for spec in GROUPS}:
        raise LauncherError("config_paths must contain exactly G1 through G7")
    return result


def build_training_command(
    *,
    repo_root: Path | str,
    spec: GroupSpec,
    accelerate_path: Path | str,
    artifact_root: Path | str,
    timestamp: str,
    wandb_mode: str,
    port_base: int = PORT_BASE,
) -> dict[str, Any]:
    """Build one exact v19-compatible command without executing it."""

    repo_root = _absolute(repo_root, label="repo_root")
    artifact_root = _absolute(artifact_root, label="artifact_root")
    accelerate_path = _absolute(accelerate_path, label="accelerate")
    if not accelerate_path.is_file():
        raise LauncherError(f"accelerate executable does not exist: {accelerate_path}")
    timestamp = _safe_token(timestamp, label="timestamp")
    wandb_mode = _validate_wandb_mode(wandb_mode)
    if isinstance(port_base, bool) or not isinstance(port_base, int) or not 1024 <= port_base <= 65529:
        raise LauncherError(f"port_base must permit seven TCP ports in 1024..65535: {port_base!r}")
    port = port_base + spec.gpu
    source = repo_root / SOURCE_RELATIVE
    argv = [
        str(accelerate_path),
        "launch",
        "--num_processes",
        "1",
        "--main_process_port",
        str(port),
        str(source),
        f"+exp={EXP_NAME}",
        f"+ablation=wbmanip/{spec.config_name}",
        f"project_name={PROJECT_NAME}",
        f"experiment_name={spec.experiment_name}",
        f"base_dir={artifact_root}",
        f"timestamp={timestamp}",
    ]
    env_prefix = (
        f"env CUDA_VISIBLE_DEVICES={spec.gpu} "
        "ACCELERATE_TORCH_DEVICE=cuda:0 "
        f"WANDB_MODE={wandb_mode} "
    )
    return {
        "argv": argv,
        "port": port,
        "gpu": spec.gpu,
        "num_processes": 1,
        "num_envs_source": "config",
        "env": {
            "CUDA_VISIBLE_DEVICES": str(spec.gpu),
            "ACCELERATE_TORCH_DEVICE": "cuda:0",
            "WANDB_MODE": wandb_mode,
        },
        "shell": env_prefix + shlex.join(argv),
    }


def _group_paths(launcher_root: Path, group: str) -> GroupPaths:
    group_root = launcher_root / group
    return GroupPaths(
        root=group_root,
        command=group_root / "command.sh",
        wrapper=group_root / "wrapper.sh",
        log=group_root / "stdout_stderr.log",
        start=group_root / "start_timestamp.txt",
        end=group_root / "end_timestamp.txt",
        pid=group_root / "pid.txt",
        exit_code=group_root / "exit_code.txt",
        natural_exit=group_root / "natural_exit.marker",
        runtime_metadata=group_root / "runtime_metadata.json",
        wandb_metadata=group_root / "wandb.json",
    )


def _wrapper_text(spec: GroupSpec, paths: GroupPaths, command: Mapping[str, Any], wandb_mode: str) -> str:
    q = shlex.quote
    command_path = q(str(paths.command))
    log_path = q(str(paths.log))
    start_path = q(str(paths.start))
    end_path = q(str(paths.end))
    pid_path = q(str(paths.pid))
    exit_path = q(str(paths.exit_code))
    natural_path = q(str(paths.natural_exit))
    runtime_path = q(str(paths.runtime_metadata))
    return f"""#!/usr/bin/env bash
set -Eeuo pipefail

readonly GROUP={q(spec.group)}
readonly GPU={spec.gpu}
readonly PORT={int(command["port"])}
readonly WANDB_MODE={q(wandb_mode)}
readonly COMMAND_FILE={command_path}
readonly LOG_FILE={log_path}
readonly START_FILE={start_path}
readonly END_FILE={end_path}
readonly PID_FILE={pid_path}
readonly EXIT_FILE={exit_path}
readonly NATURAL_EXIT_FILE={natural_path}
readonly RUNTIME_METADATA={runtime_path}

die() {{ printf 'v20 wrapper (%s): %s\\n' "$GROUP" "$*" >&2; exit 97; }}
[[ -x "$COMMAND_FILE" ]] || die "command file is not executable: $COMMAND_FILE"
[[ -e "$LOG_FILE" ]] || die "log file was not generated: $LOG_FILE"
[[ ! -e "$START_FILE" && ! -e "$END_FILE" && ! -e "$PID_FILE" ]] || die "runtime evidence already exists; refusing overwrite"
[[ ! -e "$EXIT_FILE" && ! -e "$NATURAL_EXIT_FILE" && ! -e "$RUNTIME_METADATA" ]] || die "runtime evidence already exists; refusing overwrite"

start_time="$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
printf '%s\\n' "$start_time" > "$START_FILE"
printf '%s\\n' "$$" > "$PID_FILE"

write_runtime_metadata() {{
    local status="$1"
    local code_json="$2"
    local natural="$3"
    local end_json="$4"
    local tmp="${{RUNTIME_METADATA}}.tmp.$$"
    printf '{{"schema":"a2_piper_v20_group_runtime_v1","group":"%s","gpu":%s,"port":%s,"pid":%s,"start_time":"%s","end_time":%s,"status":"%s","exit_code":%s,"natural_exit":%s,"wandb":{{"mode":"%s","run_id":"UNKNOWN_UNTIL_RUNTIME","state":"UNKNOWN_UNTIL_RUNTIME"}}}}\\n' \\
        "$GROUP" "$GPU" "$PORT" "$$" "$start_time" "$end_json" "$status" "$code_json" "$natural" "$WANDB_MODE" > "$tmp"
    mv -- "$tmp" "$RUNTIME_METADATA"
}}

write_runtime_metadata 'RUNNING' 'null' 'false' 'null'

finish() {{
    local code="$?"
    trap - EXIT
    local end_time
    end_time="$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
    printf '%s\\n' "$end_time" > "$END_FILE"
    printf '%s\\n' "$code" > "$EXIT_FILE"
    if [[ "$code" -eq 0 ]]; then
        printf 'natural_exit=true\\n' > "$NATURAL_EXIT_FILE"
        write_runtime_metadata 'NATURAL_EXIT' "$code" 'true' "\\\"$end_time\\\""
    else
        write_runtime_metadata 'FAILED' "$code" 'false' "\\\"$end_time\\\""
    fi
    exit "$code"
}}
trap finish EXIT

set +e
"$COMMAND_FILE" 2>&1 | tee -a "$LOG_FILE"
command_status="${{PIPESTATUS[0]}}"
set -e
exit "$command_status"
"""


def _tmux_text(
    *,
    launcher_root: Path,
    artifact_root: Path,
    session_name: str,
    paths: Mapping[str, GroupPaths],
) -> str:
    q = shlex.quote
    lines = [
        "#!/usr/bin/env bash",
        "set -Eeuo pipefail",
        "",
        f"readonly SESSION_NAME={q(session_name)}",
        f"readonly LAUNCHER_ROOT={q(str(launcher_root))}",
        f"readonly ARTIFACT_ROOT={q(str(artifact_root))}",
        "die() { printf 'v20 tmux launcher: %s\\n' \"$*\" >&2; exit 97; }",
        "command -v tmux >/dev/null 2>&1 || die 'tmux is required at launch time'",
        "if tmux has-session -t \"$SESSION_NAME\" 2>/dev/null; then",
        "    die \"tmux session already exists: $SESSION_NAME\"",
        "fi",
        "if [[ -e \"$ARTIFACT_ROOT\" || -L \"$ARTIFACT_ROOT\" ]]; then",
        "    die \"artifact root already exists: $ARTIFACT_ROOT\"",
        "fi",
        "mkdir -p -- \"$(dirname -- \"$ARTIFACT_ROOT\")\"",
        "mkdir -- \"$ARTIFACT_ROOT\" || die \"could not claim artifact root: $ARTIFACT_ROOT\"",
        "",
    ]
    first = paths["G1"].wrapper
    lines.append(f"tmux new-session -d -s \"$SESSION_NAME\" -n G1 {q(str(first))}")
    lines.append("tmux set-option -t \"$SESSION_NAME\" remain-on-exit on")
    for spec in GROUPS[1:]:
        lines.append(
            f"tmux new-window -t \"$SESSION_NAME\" -n {spec.group} {q(str(paths[spec.group].wrapper))}"
        )
    lines.extend(
        [
            "expected_windows='G1,G2,G3,G4,G5,G6,G7'",
            "actual_windows=\"$(tmux list-windows -t \"$SESSION_NAME\" -F '#{window_name}' | paste -sd, -)\"",
            "[[ \"$actual_windows\" == \"$expected_windows\" ]] || die \"tmux window topology mismatch: $actual_windows\"",
            "tmux has-session -t \"$SESSION_NAME\" 2>/dev/null || die \"tmux session disappeared before launch was verified\"",
            "printf 'created tmux session %s with seven group windows; training status remains runtime evidence\\n' \"$SESSION_NAME\"",
            "",
        ]
    )
    return "\n".join(lines)


def _write_exclusive(path: Path, data: str | bytes, *, mode: int = 0o644) -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    fd = os.open(path, flags, mode)
    try:
        if isinstance(data, bytes):
            with os.fdopen(fd, "wb") as handle:
                handle.write(data)
        else:
            with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle:
                handle.write(data)
    except BaseException:
        try:
            os.unlink(path)
        except FileNotFoundError:
            pass
        raise


def generate_launcher(
    *,
    timestamp: str,
    wandb_mode: str,
    repo_root: Path | str = ROOT,
    config_dir: Path | str = CONFIG_DIR,
    config_paths: Mapping[str, Path] | None = None,
    checkpoint_path: Path | str | None = None,
    expected_checkpoint_sha256: str = CHECKPOINT_SHA256,
    source_path: Path | str = SOURCE_PATH,
    accelerate_path: Path | str = ACCELERATE_PATH,
    launcher_parent: Path | str | None = None,
    artifact_root: Path | str | None = None,
    port_base: int = PORT_BASE,
    branch: str | None = None,
    source_commit: str | None = None,
    require_formal_bundle: bool = True,
) -> Path:
    """Validate inputs and write one immutable versioned launcher bundle.

    The destination launcher root and the future direct ``base_v20`` training
    root are both no-overwrite boundaries.  A pre-existing path is an error,
    including an empty directory or symlink.
    """

    repo_root = _absolute(repo_root, label="repo_root")
    timestamp = _safe_token(timestamp, label="timestamp")
    wandb_mode = _validate_wandb_mode(wandb_mode)
    if launcher_parent is None:
        launcher_parent = repo_root / LAUNCHER_PARENT_RELATIVE
    launcher_parent = _absolute(launcher_parent, label="launcher_parent")
    if artifact_root is None:
        artifact_root = repo_root / TRAINING_ROOT_RELATIVE
    artifact_root = _absolute(artifact_root, label="artifact_root")
    launcher_root = launcher_parent / f"base_v20_7cell_{timestamp}"
    if launcher_root.exists() or launcher_root.is_symlink():
        raise LauncherError(f"launcher artifact root already exists: {launcher_root}")
    if artifact_root.exists() or artifact_root.is_symlink():
        raise LauncherError(f"training artifact root already exists: {artifact_root}")
    if isinstance(port_base, bool) or not isinstance(port_base, int) or not 1024 <= port_base <= 65529:
        raise LauncherError(f"port_base must permit seven TCP ports in 1024..65535: {port_base!r}")
    ports = [port_base + spec.gpu for spec in GROUPS]
    if len(set(ports)) != len(ports):
        raise LauncherError("group ports must be unique")

    source_path = _absolute(source_path, label="source_path")
    if not source_path.is_file():
        raise LauncherError(f"missing training source: {source_path}")
    accelerate_path = _absolute(accelerate_path, label="accelerate")
    if not accelerate_path.is_file():
        raise LauncherError(f"missing accelerate executable: {accelerate_path}")
    checkpoint_path = _absolute(
        checkpoint_path if checkpoint_path is not None else repo_root / CHECKPOINT_RELATIVE,
        label="checkpoint_path",
    )
    expected_checkpoint_sha256 = _validate_sha256(
        expected_checkpoint_sha256, label="expected_checkpoint_sha256"
    )
    checkpoint_sha256 = sha256_file(checkpoint_path)
    if checkpoint_sha256 != expected_checkpoint_sha256:
        raise LauncherError(
            "warm-start checkpoint SHA-256 mismatch: "
            f"expected {expected_checkpoint_sha256}, got {checkpoint_sha256} ({checkpoint_path})"
        )
    config_dir = _absolute(config_dir, label="config_dir")
    resolved_configs = _resolve_config_paths(config_dir, config_paths)
    if not isinstance(require_formal_bundle, bool):
        raise LauncherError("require_formal_bundle must be bool")
    validated_configs = {
        spec.group: _validate_config_contract(
            resolved_configs[spec.group], spec, require_formal_bundle=require_formal_bundle
        )
        for spec in GROUPS
    }
    provenance = {validated_configs[spec.group]["_v20_provenance"] for spec in GROUPS}
    if require_formal_bundle and len(provenance) != 1:
        raise LauncherError(
            f"formal launcher requires one matching provenance triple across G1-G7; got {sorted(provenance)!r}"
        )

    if branch is None or source_commit is None:
        detected_branch, detected_commit = _git_identity(repo_root)
        branch = detected_branch if branch is None else branch
        source_commit = detected_commit if source_commit is None else source_commit
    if not isinstance(branch, str) or not branch.strip():
        raise LauncherError("git branch provenance is required")
    if not isinstance(source_commit, str) or not _COMMIT.fullmatch(source_commit):
        raise LauncherError("source commit provenance must be a lowercase git commit hash")
    source_sha256 = sha256_file(source_path)

    launcher_parent.mkdir(parents=True, exist_ok=True)
    try:
        # mkdir is the no-overwrite claim.  It also prevents two generators
        # racing on the same timestamp from replacing one another.
        launcher_root.mkdir(mode=0o755)
    except FileExistsError as exc:
        raise LauncherError(f"launcher artifact root appeared during generation: {launcher_root}") from exc

    paths_by_group = {spec.group: _group_paths(launcher_root, spec.group) for spec in GROUPS}
    group_rows: list[dict[str, Any]] = []
    generated_files: list[Path] = []
    try:
        for spec in GROUPS:
            paths = paths_by_group[spec.group]
            paths.root.mkdir(mode=0o755)
            command = build_training_command(
                repo_root=repo_root,
                spec=spec,
                accelerate_path=accelerate_path,
                artifact_root=artifact_root,
                timestamp=timestamp,
                wandb_mode=wandb_mode,
                port_base=port_base,
            )
            command_text = (
                "#!/usr/bin/env bash\n"
                "set -Eeuo pipefail\n"
                f"cd -- {shlex.quote(str(repo_root))}\n"
                f"exec {command['shell']}\n"
            )
            _write_exclusive(paths.command, command_text, mode=0o755)
            _write_exclusive(paths.wrapper, _wrapper_text(spec, paths, command, wandb_mode), mode=0o755)
            _write_exclusive(paths.log, b"")
            _write_exclusive(
                paths.wandb_metadata,
                json.dumps(
                    {
                        "schema": "a2_piper_v20_wandb_binding_v1",
                        "mode": wandb_mode,
                        "project": PROJECT_NAME,
                        "run_name": spec.experiment_name,
                        "run_id": "UNKNOWN_UNTIL_RUNTIME",
                        "state": "UNKNOWN_UNTIL_RUNTIME",
                    },
                    indent=2,
                    sort_keys=True,
                )
                + "\n",
            )
            generated_files.extend([paths.command, paths.wrapper, paths.log, paths.wandb_metadata])
            config_hash = sha256_file(resolved_configs[spec.group])
            run_dir = artifact_root / f"{spec.experiment_name}-{timestamp}"
            group_rows.append(
                {
                    "group": spec.group,
                    "gpu": spec.gpu,
                    "seed": spec.seed,
                    "reserved_gpu": RESERVED_GPU,
                    "config_name": spec.config_name,
                    "experiment_name": spec.experiment_name,
                    "config_path": str(resolved_configs[spec.group]),
                    "config_sha256": config_hash,
                    "checkpoint_path": str(checkpoint_path),
                    "checkpoint_sha256": checkpoint_sha256,
                    "num_envs": 4096,
                    "num_processes": 1,
                    "port": command["port"],
                    "command_argv": command["argv"],
                    "command_shell": command["shell"],
                    "env": command["env"],
                    "expected_run_dir": str(run_dir),
                    "files": {
                        "command": str(paths.command),
                        "wrapper": str(paths.wrapper),
                        "stdout_stderr_log": str(paths.log),
                        "start_timestamp": str(paths.start),
                        "end_timestamp": str(paths.end),
                        "pid": str(paths.pid),
                        "exit_code": str(paths.exit_code),
                        "natural_exit_marker": str(paths.natural_exit),
                        "runtime_metadata": str(paths.runtime_metadata),
                        "wandb_metadata": str(paths.wandb_metadata),
                    },
                }
            )

        launch_tmux = launcher_root / "launch_tmux.sh"
        _write_exclusive(
            launch_tmux,
            _tmux_text(
                launcher_root=launcher_root,
                artifact_root=artifact_root,
                session_name=f"base_v20_7cell_{timestamp}",
                paths=paths_by_group,
            ),
            mode=0o755,
        )
        generated_files.append(launch_tmux)
        manifest_path = launcher_root / "manifest.json"
        ready_path = launcher_root / "GENERATION_READY"
        manifest = {
            "schema": SCHEMA,
            "launcher_version": "base_v20",
            "launcher_root": str(launcher_root),
            "session_name": f"base_v20_7cell_{timestamp}",
            "artifact_root": str(artifact_root),
            "direct_output_contract": "logs_rl/a2_piper_full_stage_a2_base/base_v20/<run-dir>",
            "wandb_mode": wandb_mode,
            "wandb": {"mode": wandb_mode, "project": PROJECT_NAME},
            "topology": {
                "training_groups": 7,
                "one_process_per_group": True,
                "envs_per_group": 4096,
                "training_gpus": [0, 1, 2, 3, 4, 5, 6],
                "reserved_gpu": RESERVED_GPU,
                "ports": ports,
            },
            "git": {"branch": branch, "commit": source_commit},
            "branch": branch,
            "source": {
                "path": str(source_path),
                "sha256": source_sha256,
                "commit": source_commit,
            },
            "source_sha256": source_sha256,
            "checkpoint": {
                "path": str(checkpoint_path),
                "relative_path": CHECKPOINT_RELATIVE.as_posix(),
                "sha256": checkpoint_sha256,
                "expected_sha256": expected_checkpoint_sha256,
            },
            "checkpoint_sha256": checkpoint_sha256,
            "configs": {
                row["group"]: {
                    "path": row["config_path"],
                    "sha256": row["config_sha256"],
                    "experiment_name": row["experiment_name"],
                }
                for row in group_rows
            },
            "groups": group_rows,
            "launch_tmux": str(launch_tmux),
            "generated_files": sorted(
                [str(path) for path in generated_files] + [str(manifest_path), str(ready_path)]
            ),
            "generation": {
                "timestamp_token": timestamp,
                "training_not_started": True,
            },
        }
        _write_exclusive(manifest_path, json.dumps(manifest, indent=2, sort_keys=True) + "\n")
        _write_exclusive(
            ready_path,
            "Generated only; launch_tmux.sh has not been executed.\n",
        )
    except BaseException:
        # Keep a partial bundle for forensic inspection; never delete a path
        # that may have become user-visible after the exclusive mkdir claim.
        raise
    return launcher_root


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--timestamp", required=True, help="deterministic run token, e.g. 20260728_180000")
    parser.add_argument("--wandb-mode", required=True, choices=WANDB_MODES, help="explicit WANDB_MODE")
    parser.add_argument("--repo-root", type=Path, default=ROOT)
    parser.add_argument("--config-dir", type=Path, default=CONFIG_DIR)
    parser.add_argument("--checkpoint", type=Path, default=None)
    parser.add_argument("--checkpoint-sha256", default=CHECKPOINT_SHA256)
    parser.add_argument("--source", type=Path, default=SOURCE_PATH)
    parser.add_argument("--accelerate", type=Path, default=ACCELERATE_PATH)
    parser.add_argument("--launcher-parent", type=Path, default=None)
    parser.add_argument("--artifact-root", type=Path, default=None)
    parser.add_argument("--port-base", type=int, default=PORT_BASE)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        launcher_root = generate_launcher(
            timestamp=args.timestamp,
            wandb_mode=args.wandb_mode,
            repo_root=args.repo_root,
            config_dir=args.config_dir,
            checkpoint_path=args.checkpoint,
            expected_checkpoint_sha256=args.checkpoint_sha256,
            source_path=args.source,
            accelerate_path=args.accelerate,
            launcher_parent=args.launcher_parent,
            artifact_root=args.artifact_root,
            port_base=args.port_base,
        )
    except LauncherError as exc:
        _parser().error(str(exc))
    print(launcher_root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
