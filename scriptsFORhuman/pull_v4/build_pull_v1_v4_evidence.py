#!/usr/bin/env python3
"""Build the capped, path-provenance Pull v1--v4 evidence excerpt.

The default command is a read-only Tier-1 plan.  ``build`` is intentionally
explicit because it reads the four render output directories and writes the
manifest plus the root archive after the render leases have been released.
"""

from __future__ import annotations

import argparse
import json
import os
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence


ROOT = Path(__file__).resolve().parents[2]
SCRIPT_DIR = ROOT / "scriptsFORhuman" / "pull_v4"
TRAIN_ROOT = ROOT / "logs_rl" / "a2_piper_full_stage_a2_pull" / "a2_piper_full_stage_a2_pull"
EVAL_ROOT = ROOT / "logs_eval"
RENDER_ROOT = EVAL_ROOT / "a2_piper_pull_v4" / "renders"
MANIFEST_PATH = SCRIPT_DIR / "MANIFEST.md"
TARGET_ZIP = ROOT / "a2_piper_pull_v1_to_v4_evidence_20260811.zip"

CAP_BYTES = 500_000_000
# The trial archive reserves this much stored space for the generated
# manifest.  It is deliberately larger than the expected English manifest.
MANIFEST_RESERVE_BYTES = 2_000_000
ZIP_COMPRESSION = zipfile.ZIP_DEFLATED
ZIP_COMPRESSION_LEVEL = 6


@dataclass(frozen=True)
class Entry:
    tier: str
    category: str
    round_label: str
    cell: str
    source: Path
    archive_path: str
    status: str = "INCLUDED"
    reason: str = ""

    @property
    def source_bytes(self) -> int:
        return self.source.stat().st_size if self.source.is_file() else 0


@dataclass(frozen=True)
class MissingRecord:
    category: str
    round_label: str
    cell: str
    expected_source: Path
    reason: str

    @property
    def source_bytes(self) -> int | None:
        return self.expected_source.stat().st_size if self.expected_source.is_file() else None


@dataclass(frozen=True)
class OmissionRecord:
    category: str
    round_label: str
    cell: str
    logical_id: str
    reason: str


@dataclass(frozen=True)
class Tier2Resolution:
    entries: tuple[Entry, ...]
    omitted: tuple[Entry | OmissionRecord, ...]
    r1_attempt_paths: tuple[str, ...] = ()


def _flat_archive_path(category: str, round_label: str, cell: str, original_name: str) -> str:
    if not original_name or "/" in original_name or "\\" in original_name:
        raise ValueError(f"invalid original basename: {original_name!r}")
    return f"{category}/{round_label}_{cell}__{original_name}"


def _source(relative: str) -> Path:
    path = ROOT / relative
    if not path.is_relative_to(ROOT):
        raise RuntimeError(f"source escaped repository root: {path}")
    return path


def _config_specs() -> tuple[Entry, ...]:
    # This is the exact nine-config Tier-1 set.  Retry provenance is retained
    # in both the cell name and the original source path.
    specs = (
        ("v0", "p4_formal_seed0", "logs_rl/a2_piper_full_stage_a2_pull/a2_piper_full_stage_a2_pull/pull_v0_p4_formal_seed0-20260805_211252/config.yaml"),
        ("v1", "A_seed0", "logs_rl/a2_piper_full_stage_a2_pull/a2_piper_full_stage_a2_pull/pull_v1_A_seed0-20260809_025222/config.yaml"),
        ("v1", "B_seed0", "logs_rl/a2_piper_full_stage_a2_pull/a2_piper_full_stage_a2_pull/pull_v1_B_seed0-20260809_025222/config.yaml"),
        ("v1", "R_seed0_retry2", "logs_rl/a2_piper_full_stage_a2_pull/a2_piper_full_stage_a2_pull/pull_v1_R_seed0-20260809_110901_retry2/config.yaml"),
        ("v2", "W_wave1_seed0", "logs_rl/a2_piper_full_stage_a2_pull/a2_piper_full_stage_a2_pull/pull_v2_W_wave1_seed0/config.yaml"),
        ("v2", "W_wave2_relay_seed1", "logs_rl/a2_piper_full_stage_a2_pull/a2_piper_full_stage_a2_pull/pull_v2_W_wave2_relay_seed1/config.yaml"),
        ("v3", "T_wave1_seed0", "logs_rl/a2_piper_full_stage_a2_pull/a2_piper_full_stage_a2_pull/pull_v3_T_wave1_seed0/config.yaml"),
        ("v4", "A_wave1_seed0", "logs_rl/a2_piper_full_stage_a2_pull/a2_piper_full_stage_a2_pull/pull_v4_A_wave1_seed0/config.yaml"),
        ("v4", "B_wave1_seed0", "logs_rl/a2_piper_full_stage_a2_pull/a2_piper_full_stage_a2_pull/pull_v4_B_wave1_seed0/config.yaml"),
    )
    entries = tuple(
        Entry(
            tier="Tier1",
            category="config",
            round_label=round_label,
            cell=cell,
            source=_source(relative),
            archive_path=_flat_archive_path("configs", round_label, cell, "config.yaml"),
        )
        for round_label, cell, relative in specs
    )
    g6_source = _source(
        "logs_eval/a2_piper_pull_v4/pull_v4_B_wave1_seed0_step250_g6_budget/hydra/.hydra/runtime_config.yaml"
    )
    return entries + (
        Entry(
            tier="Tier1",
            category="runtime_config",
            round_label="v4",
            cell="B_wave1_seed0_step250_g6",
            source=g6_source,
            archive_path=_flat_archive_path(
                "configs", "v4", "B_wave1_seed0_step250_g6", "runtime_config.yaml"
            ),
        ),
    )


def _metric_entry(round_label: str, cell: str, relative_eval_dir: str) -> Entry:
    source = _source(f"logs_eval/a2_piper_pull_{round_label}/{relative_eval_dir}/eval/metrics_eval.json")
    return Entry(
        tier="Tier1",
        category="formal_metric",
        round_label=round_label,
        cell=cell,
        source=source,
        archive_path=_flat_archive_path("eval_metrics", round_label, cell, "metrics_eval.json"),
    )


def _metric_specs() -> tuple[Entry, ...]:
    entries: list[Entry] = []
    for seed in (0, 1):
        for step in (250, 500, 750, 1000, 1250, 1500, 1750, 2000, 2250, 2500):
            cell = f"p4_event_funnel_seed{seed}_step{step}"
            rel = f"p4_event_funnel/seed{seed}_step{step}"
            entries.append(_metric_entry("v0", cell, rel))
    entries.append(
        _metric_entry("v0", "p5_release_candidate_seed0_step2500_render", "p5_release_candidate/seed0_step2500_render")
    )

    # v1: accepted retry provenance only.  The two guard-failure runs are not
    # part of the formal metric set.
    v1_specs = (
        ("wave1", "A_seed0_step250_retry1", "wave1/A_seed0_step250_retry1"),
        ("wave1", "A_seed0_step500", "wave1/A_seed0_step500"),
        ("wave1", "A_seed0_step750", "wave1/A_seed0_step750"),
        ("wave1", "B_seed0_step250", "wave1/B_seed0_step250"),
        ("wave1", "B_seed0_step500", "wave1/B_seed0_step500"),
        ("wave1", "B_seed0_step750", "wave1/B_seed0_step750"),
        ("wave2", "A_seed1_step250", "wave2/A_seed1_step250"),
        ("wave2", "A_seed1_step500", "wave2/A_seed1_step500"),
        ("wave2", "A_seed1_step750", "wave2/A_seed1_step750"),
        ("wave2", "B_seed1_step250", "wave2/B_seed1_step250"),
        ("wave2", "B_seed1_step500", "wave2/B_seed1_step500"),
        ("wave2", "B_seed1_step750", "wave2/B_seed1_step750"),
        ("wave3", "R_seed0_step250_retry2", "wave3/R_seed0_step250_retry2"),
        ("wave3", "R_seed0_step500_retry2", "wave3/R_seed0_step500_retry2"),
        ("wave3", "R_seed0_step750_retry2", "wave3/R_seed0_step750_retry2"),
        ("wave3", "R_seed1_step250_retry2", "wave3/R_seed1_step250_retry2"),
        ("wave3", "R_seed1_step500_retry2", "wave3/R_seed1_step500_retry2"),
        ("wave3", "R_seed1_step750_retry2", "wave3/R_seed1_step750_retry2"),
    )
    entries.extend(_metric_entry("v1", cell, rel) for _wave, cell, rel in v1_specs)

    for family in ("W_wave1", "W_wave2_relay"):
        for seed in (0, 1):
            for step in (250, 500, 750):
                cell = f"{family}_seed{seed}_step{step}"
                entries.append(_metric_entry("v2", cell, f"{family}_seed{seed}_step{step}"))

    for seed in (0, 1):
        for step in (250, 500, 750):
            cell = f"T_wave1_seed{seed}_step{step}"
            entries.append(_metric_entry("v3", cell, f"pull_v3_T_wave1_seed{seed}_step{step}"))

    for arm in ("A", "B"):
        for seed in (0, 1):
            for step in (250, 500, 750):
                cell = f"{arm}_wave1_seed{seed}_step{step}"
                entries.append(_metric_entry("v4", cell, f"pull_v4_{arm}_wave1_seed{seed}_step{step}"))
    for seed in (0, 1):
        for step in (250, 500, 750):
            cell = f"B_wave1_seed{seed}_step{step}_g6_budget"
            entries.append(
                _metric_entry("v4", cell, f"pull_v4_B_wave1_seed{seed}_step{step}_g6_budget")
            )
    return tuple(entries)


def _training_log_specs() -> tuple[Entry, ...]:
    specs = (
        ("v1", "A_seed0", "pull_v1_A_seed0-20260809_025222", "train_stdout.txt"),
        ("v1", "A_seed1", "pull_v1_A_seed1-20260809_071140", "train_stdout.txt"),
        ("v1", "B_seed0", "pull_v1_B_seed0-20260809_025222", "train_stdout.txt"),
        ("v1", "B_seed1", "pull_v1_B_seed1-20260809_071140", "train_stdout.txt"),
        ("v1", "R_seed0_retry2", "pull_v1_R_seed0-20260809_110901_retry2", "train_stdout.txt"),
        ("v1", "R_seed1_retry2", "pull_v1_R_seed1-20260809_110901_retry2", "train_stdout.txt"),
        ("v3", "T_wave1_seed0", "pull_v3_T_wave1_seed0", "runner.log"),
        ("v3", "T_wave1_seed1", "pull_v3_T_wave1_seed1", "runner.log"),
        ("v4", "A_wave1_seed0", "pull_v4_A_wave1_seed0", "runner.log"),
        ("v4", "A_wave1_seed1", "pull_v4_A_wave1_seed1", "runner.log"),
        ("v4", "B_wave1_seed0", "pull_v4_B_wave1_seed0", "runner.log"),
        ("v4", "B_wave1_seed1", "pull_v4_B_wave1_seed1", "runner.log"),
    )
    return tuple(
        Entry(
            tier="Tier1",
            category="training_log",
            round_label=round_label,
            cell=cell,
            source=TRAIN_ROOT / run_name / basename,
            archive_path=_flat_archive_path("training_logs", round_label, cell, basename),
        )
        for round_label, cell, run_name, basename in specs
    )


def _missing_v2_logs() -> tuple[MissingRecord, ...]:
    records = []
    for run_name, cell in (
        ("pull_v2_W_wave1_seed0", "W_wave1_seed0"),
        ("pull_v2_W_wave1_seed1", "W_wave1_seed1"),
        ("pull_v2_W_wave2_relay_seed0", "W_wave2_relay_seed0"),
        ("pull_v2_W_wave2_relay_seed1", "W_wave2_relay_seed1"),
    ):
        records.append(
            MissingRecord(
                category="training_log",
                round_label="v2",
                cell=cell,
                expected_source=TRAIN_ROOT / run_name / "runner.log",
                reason="required full runner.log is unavailable; .hydra/train.log is intentionally not substituted",
            )
        )
    return tuple(records)


def _assert_unique_archive_paths(entries: Iterable[Entry]) -> None:
    paths = [entry.archive_path for entry in entries]
    duplicates = sorted({path for path in paths if paths.count(path) > 1})
    if duplicates:
        raise RuntimeError(f"duplicate archive paths: {duplicates}")


def _resolve_tier1() -> tuple[tuple[Entry, ...], tuple[MissingRecord, ...]]:
    entries = _config_specs() + _metric_specs() + _training_log_specs()
    missing = _missing_v2_logs()
    _assert_unique_archive_paths(entries)

    configs = [entry for entry in entries if entry.category in {"config", "runtime_config"}]
    metrics = [entry for entry in entries if entry.category == "formal_metric"]
    logs = [entry for entry in entries if entry.category == "training_log"]
    if len(configs) != 10:
        raise RuntimeError(f"Tier-1 config set must contain 10 files (9 training + 1 G6 runtime); got {len(configs)}")
    if len(metrics) != 75:
        raise RuntimeError(f"Tier-1 formal metric set must contain 75 files; got {len(metrics)}")
    if len(logs) != 12:
        raise RuntimeError(f"Tier-1 available training-log set must contain 12 files; got {len(logs)}")
    if len(missing) != 4:
        raise RuntimeError(f"Tier-1 missing v2 log set must contain 4 records; got {len(missing)}")

    for entry in entries:
        if not entry.source.is_file():
            raise FileNotFoundError(f"required Tier-1 source is missing: {entry.source}")
        if entry.source.stat().st_size <= 0:
            raise RuntimeError(f"required Tier-1 source is empty: {entry.source}")
    for record in missing:
        if record.expected_source.exists():
            raise RuntimeError(
                f"v2 runner log is no longer missing; update the frozen evidence specification explicitly: "
                f"{record.expected_source}"
            )
    return tuple(entries), missing


RENDER_SPECS = (
    ("R1", "v2_W_wave2_seed1_step750", "R1_v2_W_wave2_seed1_step750"),
    ("R2", "v4_B_seed0_step750", "R2_v4_B_seed0_step750"),
    ("R3", "v4_B_seed1_step500_g6", "R3_v4_B_seed1_step500_g6"),
    ("R4", "v4_A_seed1_step750", "R4_v4_A_seed1_step750"),
)

R1_FAILURE_RECEIPT = "render_failure_receipt.json"
R1_FAILURE_STATUS = "FAILED_AFTER_3_LAUNCH_ATTEMPTS"
R1_OMISSION_REASON = "R1_FAILED_AFTER_3_LAUNCH_ATTEMPTS"


def _read_r1_failure_receipt(path: Path) -> tuple[str, ...]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"cannot parse R1 failure receipt: {path}") from exc
    if not isinstance(payload, dict):
        raise RuntimeError("R1 failure receipt must be a JSON object")
    if payload.get("schema") != "a2_piper_render_failure_receipt_v1":
        raise RuntimeError("R1 failure receipt schema is not the approved v1 failure schema")
    if payload.get("render_id") != "R1":
        raise RuntimeError("R1 failure receipt render_id must be R1")
    if payload.get("status") != R1_FAILURE_STATUS:
        raise RuntimeError(f"R1 failure receipt status must be {R1_FAILURE_STATUS}")
    attempts = payload.get("attempts")
    if not isinstance(attempts, list) or len(attempts) != 3:
        raise RuntimeError("R1 failure receipt must record exactly three launcher attempts")
    if [attempt.get("attempt") for attempt in attempts if isinstance(attempt, dict)] != [1, 2, 3]:
        raise RuntimeError("R1 failure receipt attempt numbering must be exactly 1, 2, 3")
    if payload.get("eval_started") is not False or payload.get("videos_produced") != 0:
        raise RuntimeError("R1 failure receipt must record evaluator NOT_RUN and zero videos")
    if payload.get("source_or_reward_changed") is not False:
        raise RuntimeError("R1 failure receipt must record no source/reward change")
    if payload.get("no_fourth_attempt_per_user_contract") is not True:
        raise RuntimeError("R1 failure receipt must record the no-fourth-attempt contract")
    runtime_behavior = payload.get("runtime_behavior")
    if not isinstance(runtime_behavior, str) or not runtime_behavior.startswith("INCONCLUSIVE:"):
        raise RuntimeError("R1 failure receipt runtime_behavior must be explicitly INCONCLUSIVE")

    paths: list[str] = []
    for attempt in attempts:
        if not isinstance(attempt, dict):
            raise RuntimeError("R1 failure receipt attempt records must be objects")
        for key in ("evidence_directory", "launcher_stdout"):
            value = attempt.get(key)
            if not isinstance(value, str) or not value or Path(value).is_absolute():
                raise RuntimeError(f"R1 failure receipt attempt {key} must be a repo-relative path")
            paths.append(value)
    return tuple(paths)


def _r1_logical_omissions(cell: str) -> tuple[OmissionRecord, ...]:
    records: list[OmissionRecord] = []
    for env in ("env0000", "env0001"):
        for camera in ("main", "handle_side", "handle_top"):
            records.append(
                OmissionRecord(
                    category="expected_logical_artifact",
                    round_label="R1",
                    cell=cell,
                    logical_id=f"{env}/episode0000/{camera}",
                    reason=R1_OMISSION_REASON,
                )
            )
    return tuple(records)


def _pid_is_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _resolve_render_entries() -> Tier2Resolution:
    entries: list[Entry] = []
    omitted: list[Entry | OmissionRecord] = []
    r1_attempt_paths: tuple[str, ...] = ()
    for render_id, cell, dirname in RENDER_SPECS:
        render_dir = RENDER_ROOT / dirname
        if not render_dir.is_dir():
            raise FileNotFoundError(f"required render directory is missing: {render_dir}")

        writing = sorted(
            path for path in render_dir.rglob("*") if path.is_file() and ".writing" in path.name
        )
        if writing:
            raise RuntimeError(f"render output is still active ({render_id}); writing files remain: {writing}")
        for pid_path in sorted(render_dir.rglob("launcher.pid")):
            try:
                pid = int(pid_path.read_text(encoding="utf-8").strip())
            except ValueError as exc:
                raise RuntimeError(f"invalid launcher pid marker: {pid_path}") from exc
            if _pid_is_alive(pid):
                raise RuntimeError(f"render output is still active ({render_id}); launcher pid {pid} is alive")

        renderings = render_dir / "renderings"
        if render_id == "R1":
            failure_receipt = renderings / R1_FAILURE_RECEIPT
            outcome_receipt = renderings / "render_outcome_receipt.json"
            videos = sorted(renderings.glob("*.mp4"), key=lambda path: path.name)
            if failure_receipt.is_file():
                if outcome_receipt.exists() or videos:
                    raise RuntimeError(
                        "R1 failure receipt cannot coexist with a canonical outcome receipt or videos"
                    )
                r1_attempt_paths = _read_r1_failure_receipt(failure_receipt)
                if failure_receipt.stat().st_size <= 0:
                    raise RuntimeError(f"R1 failure receipt is empty: {failure_receipt}")
                entries.append(
                    Entry(
                        tier="Tier2",
                        category="render_failure_receipt",
                        round_label="R1",
                        cell=cell,
                        source=failure_receipt,
                        archive_path=_flat_archive_path("videos", "R1", cell, failure_receipt.name),
                        status="INCONCLUSIVE_NOT_RUN",
                        reason="exactly three failed launcher attempts; no fourth attempt per user contract",
                    )
                )
                omitted.extend(_r1_logical_omissions(cell))
                continue
            raise FileNotFoundError(
                f"R1 requires the exact terminal failure receipt after three attempts: {failure_receipt}"
            )
        receipt = renderings / "render_outcome_receipt.json"
        if not receipt.is_file():
            raise FileNotFoundError(f"required render receipt is missing: {receipt}")
        videos = sorted(renderings.glob("*.mp4"), key=lambda path: path.name)
        if len(videos) != 6:
            raise RuntimeError(f"{render_id} must contain exactly six final MP4s; found {len(videos)} in {renderings}")
        for source in (receipt, *videos):
            if source.stat().st_size <= 0:
                raise RuntimeError(f"render source is empty: {source}")

        entries.append(
            Entry(
                tier="Tier2",
                category="render_receipt",
                round_label=render_id,
                cell=cell,
                source=receipt,
                archive_path=_flat_archive_path("videos", render_id, cell, receipt.name),
            )
        )
        entries.extend(
            Entry(
                tier="Tier2",
                category="video",
                round_label=render_id,
                cell=cell,
                source=video,
                archive_path=_flat_archive_path("videos", render_id, cell, video.name),
            )
            for video in videos
        )
    _assert_unique_archive_paths(entries)
    return Tier2Resolution(
        entries=tuple(entries),
        omitted=tuple(omitted),
        r1_attempt_paths=r1_attempt_paths,
    )


def _zip_entries(
    destination: Path,
    entries: Sequence[Entry],
    manifest_bytes: bytes | None,
    *,
    include_manifest_reserve: bool = False,
) -> None:
    with zipfile.ZipFile(
        destination,
        mode="w",
        compression=ZIP_COMPRESSION,
        compresslevel=ZIP_COMPRESSION_LEVEL,
        allowZip64=True,
    ) as archive:
        if manifest_bytes is not None:
            archive.writestr("MANIFEST.md", manifest_bytes)
        if include_manifest_reserve:
            reserve_info = zipfile.ZipInfo("__manifest_reserve__")
            reserve_info.compress_type = zipfile.ZIP_STORED
            archive.writestr(reserve_info, b" " * MANIFEST_RESERVE_BYTES)
        for entry in entries:
            archive.write(entry.source, entry.archive_path)


def _measure_trial_size(entries: Sequence[Entry], manifest_bytes: bytes | None = None) -> int:
    with tempfile.TemporaryFile(prefix="pull-evidence-plan-") as handle:
        _zip_entries(handle, entries, manifest_bytes, include_manifest_reserve=manifest_bytes is None)
        handle.flush()
        return handle.tell()


def _measure_payload_bytes(entries: Sequence[Entry]) -> dict[str, int]:
    totals = {"Tier1": 0, "Tier2": 0}
    with tempfile.TemporaryFile(prefix="pull-evidence-payload-") as handle:
        _zip_entries(handle, entries, None)
        handle.flush()
        handle.seek(0)
        with zipfile.ZipFile(handle, mode="r") as archive:
            for entry in entries:
                info = archive.getinfo(entry.archive_path)
                totals[entry.tier] += info.compress_size
    return totals


def _source_bytes(entries: Iterable[Entry | OmissionRecord]) -> int:
    return sum(entry.source_bytes for entry in entries if isinstance(entry, Entry))


def _resolve_tier2_with_cap(static_entries: Sequence[Entry]) -> Tier2Resolution:
    render_resolution = _resolve_render_entries()
    all_render_entries = render_resolution.entries
    mandatory_receipts = tuple(
        entry
        for entry in all_render_entries
        if entry.category in {"render_receipt", "render_failure_receipt"}
    )
    if _measure_trial_size(tuple(static_entries) + mandatory_receipts) > CAP_BYTES:
        raise RuntimeError("Tier-1 evidence plus mandatory render receipts exceeds the decimal cap reserve")

    selected: list[Entry] = []
    omitted: list[Entry | OmissionRecord] = list(render_resolution.omitted)
    cap_reached = False
    for entry in all_render_entries:
        if entry.category in {"render_receipt", "render_failure_receipt"}:
            selected.append(entry)
            continue
        if cap_reached:
            omitted.append(
                Entry(
                    tier="Tier2",
                    category="video",
                    round_label=entry.round_label,
                    cell=entry.cell,
                    source=entry.source,
                    archive_path=entry.archive_path,
                    status="OMITTED_CAP",
                    reason="cap-driven omission after stable camera/env filename ordering",
                )
            )
            continue
        candidate = tuple(static_entries) + tuple(selected) + (entry,)
        trial_size = _measure_trial_size(candidate)
        if trial_size <= CAP_BYTES:
            selected.append(entry)
        else:
            cap_reached = True
            omitted.append(
                Entry(
                    tier="Tier2",
                    category="video",
                    round_label=entry.round_label,
                    cell=entry.cell,
                    source=entry.source,
                    archive_path=entry.archive_path,
                    status="OMITTED_CAP",
                    reason="cap-driven omission after stable camera/env filename ordering",
                )
            )
    return Tier2Resolution(
        entries=tuple(selected),
        omitted=tuple(omitted),
        r1_attempt_paths=render_resolution.r1_attempt_paths,
    )


def _fmt_bytes(value: int | None) -> str:
    return "—" if value is None else f"{value:,}"


def _render_manifest(
    entries: Sequence[Entry],
    missing: Sequence[MissingRecord],
    omitted: Sequence[Entry | OmissionRecord],
    payload_bytes: dict[str, int],
    planned_archive_bytes: int,
    r1_attempt_paths: Sequence[str] = (),
) -> str:
    included_tier1 = [entry for entry in entries if entry.tier == "Tier1"]
    included_tier2 = [entry for entry in entries if entry.tier == "Tier2"]
    lines = [
        "# Pull v1–v4 evidence excerpt manifest",
        "",
        "This archive is a capped derivative excerpt, not a copy of whole evidence units. Original files remain in the repository and are never moved or deleted.",
        "",
        f"- Archive target: `{TARGET_ZIP.name}`",
        f"- Decimal byte cap: `{CAP_BYTES:,}` bytes (final ZIP size is asserted after writing)",
        f"- Manifest reservation used during Tier-2 selection: `{MANIFEST_RESERVE_BYTES:,}` bytes",
        f"- Planned ZIP size with the generated manifest: `{planned_archive_bytes:,}` bytes",
        "- Tier-1 inventory: 9 training configs, 1 G6 runtime-config exemplar, 75 formal metrics, and 12 available full training logs.",
        "- Tier-1 missing inventory: 4 required v2 full runner logs, recorded explicitly below.",
        "- Tier 3: none. No hidden continuation or additional tier was inferred.",
        "- Render ordering note: R1→R4 is an operational inference from the enumerated render-directory order; no continuation or priority instruction was recovered.",
        "- R1 runtime status: INCONCLUSIVE / NOT_RUN after exactly three failed launcher attempts; no fourth attempt was made and no behavioral claim is made.",
        "",
        "## Tier byte report",
        "",
        "| Tier | Included files | Source bytes | Compressed payload bytes |",
        "| --- | ---: | ---: | ---: |",
        f"| Tier1 | {len(included_tier1)} | {_fmt_bytes(_source_bytes(included_tier1))} | {_fmt_bytes(payload_bytes['Tier1'])} |",
        f"| Tier2 | {len(included_tier2)} | {_fmt_bytes(_source_bytes(included_tier2))} | {_fmt_bytes(payload_bytes['Tier2'])} |",
        f"| Omitted Tier2 MP4s | {len(omitted)} | {_fmt_bytes(_source_bytes(omitted))} | not archived |",
        "",
        "## Source provenance",
        "",
        "`Archive path` is the flat path inside the ZIP. `Original repo-relative source` is resolved from this repository root. `Bytes` is the source-file byte count.",
        "",
        "| Archive path | Original repo-relative source | Bytes | Category | Status |",
        "| --- | --- | ---: | --- | --- |",
    ]
    rows: list[Entry | MissingRecord | OmissionRecord] = list(entries) + list(missing) + list(omitted)
    for item in rows:
        if isinstance(item, Entry):
            archive_path = (
                f"`{item.archive_path}`"
                if item.status in {"INCLUDED", "INCONCLUSIVE_NOT_RUN"}
                else "—"
            )
            source = item.source.relative_to(ROOT).as_posix()
            lines.append(
                f"| {archive_path} | `{source}` | {_fmt_bytes(item.source_bytes)} | {item.category} | {item.status}{(': ' + item.reason) if item.reason else ''} |"
            )
        elif isinstance(item, MissingRecord):
            source = item.expected_source.relative_to(ROOT).as_posix()
            lines.append(
                f"| — | `{source}` | {_fmt_bytes(item.source_bytes)} | {item.category} | MISSING: {item.reason} |"
            )
        else:
            lines.append(
                f"| — | — | — | {item.category} | OMITTED: {item.reason} ({item.logical_id}) |"
            )
    lines.extend(
        [
            "",
            "## Tier-2 selection and omissions",
            "",
            "Each render receipt is mandatory and appears before its selected MP4 entries; only cap-eligible actual MP4 files from successful R2–R4 renders are considered in stable filename order and may be omitted for the decimal cap, while the six R1 logical NOT_RUN artifacts are omitted because three launches failed.",
            "",
            "R1 has an exact failure receipt instead of an outcome receipt. Its six omitted entries are logical env×camera artifacts only; no timestamped filenames, source paths, or behavioral claims are invented.",
            "",
            "R1 failure-receipt attempt evidence paths (recorded by the copied receipt):",
        ]
    )
    lines.extend(f"- `{path}`" for path in r1_attempt_paths)
    lines.extend(
        [
            "",
            "Required v2 full runner logs are explicitly missing. The corresponding `.hydra/train.log` files are not substituted.",
            "",
            "The archive contains no content-digest fields or functions.",
            "",
        ]
    )
    return "\n".join(lines)


def _plan(*, include_renders: bool = False) -> int:
    entries, missing = _resolve_tier1()
    configs = [entry for entry in entries if entry.category in {"config", "runtime_config"}]
    metrics = [entry for entry in entries if entry.category == "formal_metric"]
    logs = [entry for entry in entries if entry.category == "training_log"]
    print("Read-only Tier-1 plan (no manifest/archive writes)")
    print(f"configs: {len(configs)} total (9 training + 1 G6 runtime exemplar), {_source_bytes(configs):,} source bytes")
    print(f"formal metrics: {len(metrics)} exact files, {_source_bytes(metrics):,} source bytes")
    print(f"available training logs: {len(logs)} files, {_source_bytes(logs):,} source bytes")
    print(f"missing v2 runner logs: {len(missing)} (no .hydra/train.log substitution)")
    print(f"target ZIP: {TARGET_ZIP} ({'already exists' if TARGET_ZIP.exists() else 'absent'})")
    print(f"manifest destination: {MANIFEST_PATH} ({'already exists' if MANIFEST_PATH.exists() else 'absent'})")
    if not include_renders:
        print("Tier-2 renders: deferred until all four render-output leases are terminal")
        return 0

    render_resolution = _resolve_render_entries()
    print("Tier-2 read-only resolution:")
    r1_entries = [entry for entry in render_resolution.entries if entry.round_label == "R1"]
    r1_omissions = [item for item in render_resolution.omitted if isinstance(item, OmissionRecord)]
    if len(r1_entries) != 1 or r1_entries[0].category != "render_failure_receipt" or len(r1_omissions) != 6:
        raise RuntimeError(
            f"R1 failure branch topology failed: entries={len(r1_entries)} logical_omissions={len(r1_omissions)}"
        )
    print(
        f"R1: failure receipt included; runtime INCONCLUSIVE/NOT_RUN; "
        f"logical expected-video omissions: {len(r1_omissions)}"
    )
    for render_id, _cell, _dirname in RENDER_SPECS:
        render_entries = [entry for entry in render_resolution.entries if entry.round_label == render_id]
        if render_id == "R1":
            continue
        receipts = [entry for entry in render_entries if entry.category == "render_receipt"]
        videos = [entry for entry in render_entries if entry.category == "video"]
        if len(receipts) != 1 or len(videos) != 6:
            raise RuntimeError(f"{render_id} strict topology failed: receipts={len(receipts)} videos={len(videos)}")
        print(f"{render_id}: canonical outcome receipt + {len(videos)} MP4s")
    return 0


def _compute_manifest_bytes(
    tier1: Sequence[Entry],
    missing: Sequence[MissingRecord],
    tier2: Tier2Resolution,
) -> tuple[tuple[Entry, ...], dict[str, int], bytes]:
    included = tuple(tier1) + tier2.entries
    payload_bytes = _measure_payload_bytes(included)

    planned_archive_bytes = 0
    manifest_bytes = b""
    for _ in range(4):
        manifest = _render_manifest(
            included,
            missing,
            tier2.omitted,
            payload_bytes,
            planned_archive_bytes=planned_archive_bytes,
            r1_attempt_paths=tier2.r1_attempt_paths,
        )
        manifest_bytes = manifest.encode("utf-8")
        measured_size = _measure_trial_size(included, manifest_bytes)
        if measured_size > CAP_BYTES:
            raise RuntimeError(
                f"manifest-inclusive trial archive exceeds cap after Tier-2 selection: {measured_size} > {CAP_BYTES}"
            )
        if measured_size == planned_archive_bytes and planned_archive_bytes != 0:
            break
        planned_archive_bytes = measured_size
    else:
        raise RuntimeError("planned archive size did not converge while rendering the manifest")
    if len(manifest_bytes) > MANIFEST_RESERVE_BYTES:
        raise RuntimeError(
            f"generated manifest exceeds the reserved selection budget: {len(manifest_bytes)} > {MANIFEST_RESERVE_BYTES}"
        )
    return included, payload_bytes, manifest_bytes


def _build() -> int:
    manifest_preexisting = MANIFEST_PATH.exists()
    if manifest_preexisting and not MANIFEST_PATH.is_file():
        raise RuntimeError(f"generated manifest path is not a regular file: {MANIFEST_PATH}")

    tier1, missing = _resolve_tier1()
    tier2 = _resolve_tier2_with_cap(tier1)
    included, payload_bytes, manifest_bytes = _compute_manifest_bytes(tier1, missing, tier2)
    if manifest_preexisting:
        existing_manifest_bytes = MANIFEST_PATH.read_bytes()
        if existing_manifest_bytes != manifest_bytes:
            raise RuntimeError(
                "existing MANIFEST.md differs from the recomputed frozen-input manifest; refusing recovery"
            )
        recovery = True
    else:
        MANIFEST_PATH.write_bytes(manifest_bytes)
        recovery = False
    target_owned = False
    try:
        archive = zipfile.ZipFile(
            TARGET_ZIP,
            mode="x",
            compression=ZIP_COMPRESSION,
            compresslevel=ZIP_COMPRESSION_LEVEL,
            allowZip64=True,
        )
    except FileExistsError as exc:
        raise FileExistsError(f"refusing to overwrite existing target ZIP: {TARGET_ZIP}") from exc
    target_owned = True
    try:
        with archive:
            archive.write(MANIFEST_PATH, "MANIFEST.md")
            for entry in included:
                archive.write(entry.source, entry.archive_path)
    except Exception:
        if target_owned and TARGET_ZIP.exists():
            TARGET_ZIP.unlink()
        raise

    try:
        actual_size = TARGET_ZIP.stat().st_size
        with zipfile.ZipFile(TARGET_ZIP, mode="r") as archive:
            names = archive.namelist()
            expected = ["MANIFEST.md", *(entry.archive_path for entry in included)]
            if names != expected:
                raise RuntimeError("archive layout/order differs from the resolved manifest entry set")
            if len(names) != len(set(names)):
                raise RuntimeError("archive contains duplicate names")
            actual_payload = {"Tier1": 0, "Tier2": 0}
            for entry in included:
                info = archive.getinfo(entry.archive_path)
                if info.file_size != entry.source_bytes:
                    raise RuntimeError(f"archive source-byte mismatch for {entry.archive_path}")
                actual_payload[entry.tier] += info.compress_size
            if actual_payload != payload_bytes:
                raise RuntimeError(
                    f"compressed payload report changed during final write: {actual_payload} != {payload_bytes}"
                )
    except Exception:
        if target_owned and TARGET_ZIP.exists():
            TARGET_ZIP.unlink()
        raise
    if actual_size > CAP_BYTES:
        if target_owned and TARGET_ZIP.exists():
            TARGET_ZIP.unlink()
        raise RuntimeError(f"final archive exceeds decimal cap: {actual_size} > {CAP_BYTES}")

    print(f"Built {TARGET_ZIP}")
    print(f"Final ZIP bytes: {actual_size:,} <= cap {CAP_BYTES:,}")
    print(f"Manifest: {MANIFEST_PATH} ({len(manifest_bytes):,} bytes)")
    if recovery:
        print("Recovery path: existing manifest matched recomputed bytes exactly and was preserved without rewrite")
    else:
        print("Manifest path: generated for this build")
    print(f"Tier1 entries: {len(tier1)}; Tier2 entries: {len(tier2.entries)}; omitted MP4s: {len(tier2.omitted)}")
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Plan or build the capped Pull v1-v4 evidence excerpt")
    parser.add_argument("--plan", action="store_true", help="read-only Tier-1 plan (same as the plan subcommand)")
    parser.add_argument("--build", action="store_true", help="build outputs (same as the build subcommand)")
    subparsers = parser.add_subparsers(dest="command")
    plan_parser = subparsers.add_parser("plan", help="read-only path/count/byte resolution (default)")
    plan_parser.add_argument(
        "--renders",
        action="store_true",
        help="also resolve the terminal R1 failure branch and strict R2-R4 render topology",
    )
    subparsers.add_parser("build", help="build MANIFEST.md and the root ZIP after render leases are terminal")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.plan and args.build:
        raise ValueError("--plan and --build are mutually exclusive")
    if args.command and ((args.plan and args.command != "plan") or (args.build and args.command != "build")):
        raise ValueError("command and flag select different execution paths")
    command = args.command or ("build" if args.build else "plan")
    if command == "plan":
        return _plan(include_renders=bool(getattr(args, "renders", False)))
    if command == "build":
        return _build()
    raise RuntimeError(f"unknown command: {command}")


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (FileExistsError, FileNotFoundError, RuntimeError, ValueError) as exc:
        raise SystemExit(f"ERROR: {exc}") from exc
