#!/usr/bin/env python3
"""Prepare and run one immutable pull-v0 P1 push-anchor attempt."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import shutil
import signal
import subprocess
from datetime import datetime
from pathlib import Path
from types import FrameType
from typing import Any, BinaryIO, Mapping
from zoneinfo import ZoneInfo

import yaml

if __package__:
    from . import capture_p1_anchor_gpu_evidence as attempt19_gpu_evidence
else:
    import capture_p1_anchor_gpu_evidence as attempt19_gpu_evidence


ROOT = Path(__file__).resolve().parents[2]
EVIDENCE_ROOT = ROOT / "scriptsFORhuman" / "pull_v0"
SOURCE_FREEZE_PATH = EVIDENCE_ROOT / "PULL_V0_SOURCE_FREEZE.json"
REPAIR_RECEIPT_PATH = EVIDENCE_ROOT / "PULL_V0_REPAIR_R1_RECEIPT.json"
REPAIR_R1_RECEIPT_PATH = REPAIR_RECEIPT_PATH
REPAIR_R2_RECEIPT_PATH = EVIDENCE_ROOT / "PULL_V0_REPAIR_R2_RECEIPT.json"
REPAIR_R3_RECEIPT_PATH = EVIDENCE_ROOT / "PULL_V0_REPAIR_R3_RECEIPT.json"
REPAIR_R4_RECEIPT_PATH = EVIDENCE_ROOT / "PULL_V0_REPAIR_R4_RECEIPT.json"
REPAIR_R5_RECEIPT_PATH = EVIDENCE_ROOT / "PULL_V0_REPAIR_R5_RECEIPT.json"
REPAIR_R6_RECEIPT_PATH = EVIDENCE_ROOT / "PULL_V0_REPAIR_R6_RECEIPT.json"
REPAIR_R7_RECEIPT_PATH = EVIDENCE_ROOT / "PULL_V0_REPAIR_R7_RECEIPT.json"
REPAIR_R8_RECEIPT_PATH = EVIDENCE_ROOT / "PULL_V0_REPAIR_R8_RECEIPT.json"
REPAIR_R9_RECEIPT_PATH = EVIDENCE_ROOT / "PULL_V0_REPAIR_R9_RECEIPT.json"
REPAIR_R10_RECEIPT_PATH = EVIDENCE_ROOT / "PULL_V0_REPAIR_R10_RECEIPT.json"
REPAIR_R11_RECEIPT_PATH = EVIDENCE_ROOT / "PULL_V0_REPAIR_R11_RECEIPT.json"
REPAIR_R12_RECEIPT_PATH = EVIDENCE_ROOT / "PULL_V0_REPAIR_R12_RECEIPT.json"
REPAIR_R13_RECEIPT_PATH = EVIDENCE_ROOT / "PULL_V0_REPAIR_R13_RECEIPT.json"
REPAIR_R14_RECEIPT_PATH = EVIDENCE_ROOT / "PULL_V0_REPAIR_R14_RECEIPT.json"
GPU_LEASE_AMENDMENT_RECEIPT_PATH = EVIDENCE_ROOT / "PULL_V0_GPU_LEASE_AMENDMENT_RECEIPT.json"
R15_RECEIPT_PATH = EVIDENCE_ROOT / "PULL_V0_REPAIR_R15_RECEIPT.json"
R16_RECEIPT_PATH = EVIDENCE_ROOT / "PULL_V0_REPAIR_R16_RECEIPT.json"
R17_RECEIPT_PATH = EVIDENCE_ROOT / "PULL_V0_REPAIR_R17_RECEIPT.json"
EXPECTED_R16_RECEIPT_SHA256 = "cf0d7107062bf8558adf4c64aaee03f91625950bdcaf2e1ee1d767883da1787e"
ATTEMPT17_RECEIPT_PATH = EVIDENCE_ROOT / "PULL_V0_P1_PUSH_ANCHOR_ATTEMPT17_RECEIPT.json"
ATTEMPT8_INVALIDATION_PATH = EVIDENCE_ROOT / "PULL_V0_P1_PUSH_ANCHOR_ATTEMPT8_INVALIDATION.json"
ATTEMPT9_INVALIDATION_PATH = EVIDENCE_ROOT / "PULL_V0_P1_PUSH_ANCHOR_ATTEMPT9_INVALIDATION.json"
ATTEMPT9_RESPONSE_TELEMETRY_PATH = EVIDENCE_ROOT / "PULL_V0_P1_PUSH_ANCHOR_ATTEMPT9_RESPONSE_TELEMETRY.json"
ATTEMPT10_RECEIPT_PATH = EVIDENCE_ROOT / "PULL_V0_P1_PUSH_ANCHOR_ATTEMPT10_RECEIPT.json"
ATTEMPT11_RECEIPT_PATH = EVIDENCE_ROOT / "PULL_V0_P1_PUSH_ANCHOR_ATTEMPT11_RECEIPT.json"
ATTEMPT13_RECEIPT_PATH = EVIDENCE_ROOT / "PULL_V0_P1_PUSH_ANCHOR_ATTEMPT13_RECEIPT.json"
ATTEMPT14_RECEIPT_PATH = EVIDENCE_ROOT / "PULL_V0_P1_PUSH_ANCHOR_ATTEMPT14_RECEIPT.json"
ATTEMPT15_RECEIPT_PATH = EVIDENCE_ROOT / "PULL_V0_P1_PUSH_ANCHOR_ATTEMPT15_RECEIPT.json"
ATTEMPT16_RECEIPT_PATH = EVIDENCE_ROOT / "PULL_V0_P1_PUSH_ANCHOR_ATTEMPT16_RECEIPT.json"
ATTEMPT12_INVALIDATION_PATH = EVIDENCE_ROOT / "PULL_V0_P1_PUSH_ANCHOR_ATTEMPT12_PREPARATION_INVALIDATION.json"
ATTEMPT18_RECEIPT_PATH = EVIDENCE_ROOT / "PULL_V0_P1_PUSH_ANCHOR_ATTEMPT18_RECEIPT.json"
ATTEMPT18_RETRY1_LAUNCH_OCCUPANCY_PATH = (
    EVIDENCE_ROOT / "PULL_V0_P1_PUSH_ANCHOR_ATTEMPT18_RETRY1_LAUNCH_OCCUPANCY.json"
)
ATTEMPT18_RETRY1_STEADY_STATE_FOOTPRINT_PATH = (
    EVIDENCE_ROOT / "PULL_V0_P1_PUSH_ANCHOR_ATTEMPT18_RETRY1_STEADY_STATE_FOOTPRINT.json"
)
ATTEMPT19_LAUNCH_OCCUPANCY_PATH = (
    EVIDENCE_ROOT / "PULL_V0_P1_PUSH_ANCHOR_ATTEMPT19_LAUNCH_OCCUPANCY.json"
)
ATTEMPT19_STEADY_STATE_FOOTPRINT_PATH = (
    EVIDENCE_ROOT / "PULL_V0_P1_PUSH_ANCHOR_ATTEMPT19_STEADY_STATE_FOOTPRINT.json"
)
ATTEMPT20_RECEIPT_PATH = EVIDENCE_ROOT / "PULL_V0_P1_PUSH_ANCHOR_ATTEMPT20_RECEIPT.json"
ATTEMPT20_LAUNCH_OCCUPANCY_PATH = (
    EVIDENCE_ROOT / "PULL_V0_P1_PUSH_ANCHOR_ATTEMPT20_LAUNCH_OCCUPANCY.json"
)
ATTEMPT20_STEADY_STATE_FOOTPRINT_PATH = (
    EVIDENCE_ROOT / "PULL_V0_P1_PUSH_ANCHOR_ATTEMPT20_STEADY_STATE_FOOTPRINT.json"
)
ATTEMPT19_CONTACT_CAPACITY = 64
SHARED_CONTACT_CAPACITY = 8
EXPECTED_R17_SCHEMA = "pull_v0_repair_r17_receipt_v1"
EXPECTED_R16_REVISION = "R16"
EXPECTED_R17_REVISION = "R17"
EXPECTED_R17_STATUS = "APPROVED_FOR_ATTEMPT20_PREPARATION_ONLY"
ATTEMPT_GPU_CONTEXT_CLASSIFICATION_MODES = {
    19: {
        "mode": "STRICT_G_ONLY_INACTIVE_VULKAN_ENUMERATION",
        "same_pid_nonselected_pmon_types": ["G"],
        "same_pid_nonselected_compute_apps_allowed": False,
        "nonselected_same_pid_low_memory_enumeration_allowed": False,
        "other_tenant_attribution_for_attempt_pid_allowed": False,
    },
    20: {
        "mode": "LOW_MEMORY_SAME_PID_ENUMERATION_CONTEXTS",
        "same_pid_nonselected_pmon_types": ["C", "G", "C+G"],
        "same_pid_nonselected_compute_apps_allowed": False,
        "same_pid_nonselected_compute_utilization_required_zero": True,
        "nonselected_same_pid_low_memory_enumeration_allowed": True,
        "nonselected_same_pid_fb_memory_threshold_mib": 1024,
        "other_tenant_attribution_for_attempt_pid_allowed": False,
    },
}
LIFECYCLE_SIGNAL_CHILD_WAIT_TIMEOUT_SECONDS = 600.0
SOURCE_CONFIG = ROOT / (
    "logs_rl/a2_piper_full_stage_a2_pull/pull_v0_p0c/out_resolved/config.yaml"
)
PYTHON = Path("/home/baoquanc/anaconda3/envs/isaaclab/bin/python")
PHYSICAL_GPU = 2
AUTHORIZED_GPUS = (2, 3)
EXPECTED_BASE_SHA = "4aec9fe76043c3bb85d8bcdd1c2cd9210086dc09"
EXPECTED_REPAIR_RECEIPT_SHA256 = (
    "14b15df80229fbd7e01fded10c8a1675f58317cabb727e6d12f0931ab82f8335"
)
EXPECTED_STALE_CANDIDATE_ID = (
    "244a7569ff6f4ab06c2d7349cb5ca08c12f228c3b72d6df10a72727f8d872c7f"
)
EXPECTED_R2_SCHEMA = "pull_v0_repair_r2_receipt_v1"
EXPECTED_R2_REVISION = "R2"
EXPECTED_R2_ROOT_CAUSE = "TENSOR_DEVICE_CALLSITE_CONTRACT"
EXPECTED_R2_TRIGGER_ATTEMPT = 3
EXPECTED_R2_RECEIPT_SHA256 = (
    "9899b5bbb93455cea82c80bee6a2c58e00b7ad692c1302dfe7aedc553b5f5263"
)
EXPECTED_R3_SCHEMA = "pull_v0_repair_r3_receipt_v1"
EXPECTED_R3_REVISION = "R3"
EXPECTED_R3_ROOT_CAUSE = "ACQUISITION_CONTROL_CIRCULARITY_AND_TELEMETRY_INCOMPLETE"
EXPECTED_R3_TRIGGER_ATTEMPT = 4
EXPECTED_R3_RECEIPT_SHA256 = (
    "49ca2e32a81f2635afc3303f40e5cf50c0b581f991b2fbe564f36090e72ebf25"
)
EXPECTED_R4_SCHEMA = "pull_v0_repair_r4_receipt_v1"
EXPECTED_R4_REVISION = "R4"
EXPECTED_R4_ROOT_CAUSE = "RESET_BOUNDARY_CONTACT_UNQUALIFIED_BEFORE_STAGING"
EXPECTED_R4_TRIGGER_ATTEMPT = 5
EXPECTED_R4_RECEIPT_SHA256 = (
    "0c1debd42bbee1d9007190b2e3768670c23981a903df5ba9c5b6512d22b904aa"
)
EXPECTED_R5_SCHEMA = "pull_v0_repair_r5_receipt_v1"
EXPECTED_R5_REVISION = "R5"
EXPECTED_R5_ROOT_CAUSE = "GENERIC_BASE_RELIEF_WATCHDOG_CROSS_TALK"
EXPECTED_R5_TRIGGER_ATTEMPT = 6
EXPECTED_R6_SCHEMA = "pull_v0_repair_r6_receipt_v1"
EXPECTED_R6_REVISION = "R6"
EXPECTED_R6_ROOT_CAUSE = "STAGE0_COMMAND_TO_PLANT_RESPONSE_UNRESOLVED"
EXPECTED_R6_TRIGGER_ATTEMPT = 7
EXPECTED_R6_RECEIPT_SHA256 = "7854607b14022fc1954ec024d791fe43e1fd3c0339fe48fb47c8a03cb2a2e6a6"
EXPECTED_R7_SCHEMA = "pull_v0_repair_r7_receipt_v1"
EXPECTED_R7_REVISION = "R7"
EXPECTED_R7_ROOT_CAUSE = "STAGE0_COMMAND_RESPONSE_LATCH_REQUIRED"
EXPECTED_R7_TRIGGER_ATTEMPT = 8
EXPECTED_R7_RECEIPT_SHA256 = "a5f576c06718b145e992bd4927384efae9e7b8714f6f8b87836914da6c702b5f"
EXPECTED_ATTEMPT8_RECEIPT_SHA256 = "dab0732f722bd8444b357b721acbc9c14d8b6725d81096bcfaeb039b9e8e0722"
EXPECTED_ATTEMPT8_INVALIDATION_SHA256 = "dc43421bc12af85a18bbeb6398b1242daf4f293982894a5e17f0d01ec1535fd4"
EXPECTED_R8_SCHEMA = "pull_v0_repair_r8_receipt_v1"
EXPECTED_R8_REVISION = "R8"
EXPECTED_R8_ROOT_CAUSE = "STAGE0_ROOT_QUATERNION_SOURCE_MISMATCH"
EXPECTED_R8_TRIGGER_ATTEMPT = 9
EXPECTED_R8_RECEIPT_SHA256 = "00e7abbc6612f7a841cb0a809c7053ba343dab1e7d14f94d092510a82f11b76b"
EXPECTED_ATTEMPT9_RECEIPT_SHA256 = "286fa3b832911ce3530b17696049b0a5e9d5584bf78e5199d1506c208b043624"
EXPECTED_ATTEMPT9_INVALIDATION_SHA256 = "ad21ae10c7f443fea640f195dfa5806eedfbb7374a740785c0b80d546d5eda1a"
EXPECTED_ATTEMPT9_RESPONSE_TELEMETRY_SHA256 = "653a599a83e386251ee1a7dc98d51b93e3a474123569565ff311b1d99af9e937"
EXPECTED_R9_SCHEMA = "pull_v0_repair_r9_receipt_v1"
EXPECTED_R9_REVISION = "R9"
EXPECTED_R9_ROOT_CAUSE = "STAGE0_TIMEOUT_BELOW_KINEMATIC_CAPACITY"
EXPECTED_R9_TRIGGER_ATTEMPT = 10
EXPECTED_R9_RECEIPT_SHA256 = "3bed2ab4b7e4e21e3d0c05d07b36afa49d7e5a597c8c4efb41178e35f4d6cd69"
EXPECTED_ATTEMPT10_RECEIPT_SHA256 = "725300a992e5e842b4335d62e8ee71bbcf4b3bcd414a5087ba6dca38ecdaaaf6"
EXPECTED_ATTEMPT10_PLAN_SHA256 = "98bad3d8b617811e9db459be434f754d90bbafe1bc388035d84e0f219d12ae11"
EXPECTED_ATTEMPT10_PLAN_IDENTITY_SHA256 = "176d5c7de626d336040100c991439399ce385c6063bce6e1563e1174f7c616bc"
EXPECTED_ATTEMPT10_PROCESS_SHA256 = "91094b6010c2a19545f6c5e31e66f2a8acdb61042fb714e0e61a5d2e3551ba88"
EXPECTED_ATTEMPT10_LOG_SHA256 = "dc5a0171a6cb2c4d59265761665fd314a9cc5fe918bc5074567f461de4a907ee"
EXPECTED_ATTEMPT10_SUMMARY_SHA256 = "b2c2904a18c4f5ffc675ee1da37e237a9265f7abc13e080417ffcee5123be06e"
EXPECTED_ATTEMPT10_METRICS_SHA256 = "74f160458bf51cfd28e4fd15275b6cfd64f8a6987b12d6d031e0d5fadca2b3cb"
EXPECTED_R10_SCHEMA = "pull_v0_repair_r10_receipt_v1"
EXPECTED_R10_REVISION = "R10"
EXPECTED_R10_ROOT_CAUSE = "PULL_P1_STAGE0_HOST_STAGE_OVERTIME_PREEMPTED_LOCAL_WATCHDOG"
EXPECTED_R10_RECEIPT_SHA256 = "745f0106ba3503f8f2c729ef21576c19dae5e4a477c39c0b547ae6c5f8926301"
EXPECTED_ATTEMPT11_RECEIPT_SHA256 = "4e37e1c20667ba4d4c9c69ce848725dd1fbe5eda3954dff0f942cc7dbf3f595b"
EXPECTED_ATTEMPT11_PLAN_SHA256 = "78be473a11f3b304c49ad34e0d82cc1a7c1edb0c147675fe7f15056fdb47fa81"
EXPECTED_ATTEMPT11_PLAN_IDENTITY_SHA256 = "ecf47679407d4bfddd7a5d3046e6e4e2801d4f5d4a4fb769ecc7a1194849812f"
EXPECTED_ATTEMPT11_PROCESS_SHA256 = "2c55d7ac5412e331be36e12c75a4834415a0236077d8d1b2ca34f7af295c9b9a"
EXPECTED_ATTEMPT11_LOG_SHA256 = "81d2d7f8298fdbc20a2856e36af2f8774497b10097dd263fd726a52b8cd34fef"
EXPECTED_ATTEMPT11_SUMMARY_SHA256 = "28f52faedb360307add4b14df0a3d902510683482f39de7a972400c800436031"
EXPECTED_ATTEMPT11_METRICS_SHA256 = "991070babb9e4ffe744f8a5f0a21dc56b067c1efeb386283b237b46687b587b4"
EXPECTED_R11_SCHEMA = "pull_v0_repair_r11_receipt_v1"
EXPECTED_R11_REVISION = "R11"
EXPECTED_R11_ROOT_CAUSE = "ATTEMPT12_PREPARATION_REPAIR_RECEIPT_PATH_MISMATCH"
EXPECTED_R11_RECEIPT_SHA256 = "4c50d52e25658e296b3101b283bb2eb57e7d9f5747dedb8a8b76a22783e563a4"
EXPECTED_ATTEMPT12_PLAN_SHA256 = "2e4231c6f6a7862d094d5182857c37b9381b557b6760636c508e3fd87c648dbc"
EXPECTED_ATTEMPT12_PLAN_IDENTITY_SHA256 = "435bc01e7ad08001390463911d0e450d43ced7110c855f3e3ea69b20006ebe93"
EXPECTED_ATTEMPT12_INVALIDATION_SHA256 = "0d82c848cab382f873a01f67eb88669efae4d4669fb67bbac42161532d280d78"
EXPECTED_R12_SCHEMA = "pull_v0_repair_r12_receipt_v1"
EXPECTED_R12_REVISION = "R12"
EXPECTED_R12_ROOT_CAUSE = "ATTEMPT13_HYDRA_STRUCT_CONFIG_MISSING_PLUS_OVERRIDE"
EXPECTED_R12_RECEIPT_SHA256 = "676e0df6a8b3a9dca35ce53c41726df6ec64db57e6652f4b25e1b01131c833bb"
EXPECTED_ATTEMPT13_RECEIPT_SHA256 = "f85e1d177b5e3422ed99f4de250187ad9e7186f7034d9b79e1d1cd339b779cd5"
EXPECTED_ATTEMPT13_PLAN_SHA256 = "25c106d21b399add34a182a031804ee6bc4e7aef884af457d10225dedd73e353"
EXPECTED_ATTEMPT13_PLAN_IDENTITY_SHA256 = "3aa964ac867e122b787518058da8ff9665315ea31b6fab9156010e5478ae4a5b"
EXPECTED_ATTEMPT13_PROCESS_SHA256 = "fc23b6f83adad04f4ede47397fcff3856abaceccd99b861aaeb6efa49b472b7e"
EXPECTED_ATTEMPT13_LOG_SHA256 = "c7012546d0bd515a60d58ee4d554ef998cc361716408961ad84a3d0c37c782c6"
EXPECTED_ATTEMPT13_ERROR_TYPE = "ConfigCompositionException"
EXPECTED_ATTEMPT13_MISSING_PLUS_OVERRIDE = "+env.config.max_stage_time=[400,100,100,100,100,200]"
EXPECTED_ATTEMPT13_BAD_OVERRIDE = "env.config.max_stage_time=[400,100,100,100,100,200]"
EXPECTED_R13_SCHEMA = "pull_v0_repair_r13_receipt_v1"
EXPECTED_R13_REVISION = "R13"
EXPECTED_R13_ROOT_CAUSE = "ATTEMPT14_RENDERER_MULTIGPU_RESOURCE_LEASE_VIOLATION"
EXPECTED_R13_RECEIPT_SHA256 = "afc3466fc270f9f5166a29a06c34fc6e39c853d0441a52d4539cd0cff0304c32"
EXPECTED_ATTEMPT14_RECEIPT_SHA256 = "60c007cf6267e42b66605217880adc24e638da744142e85e362a313ba4778638"
EXPECTED_ATTEMPT14_PLAN_SHA256 = "fce7011380089e4f8647dfccf5ed4a4c75b149001c0acc6b7dfbf8de02f4f3c4"
EXPECTED_ATTEMPT14_PLAN_IDENTITY_SHA256 = "0e24e0c0d74b40791cb4b0d510426078202a62989d518a100ec9889c89d3f75d"
EXPECTED_ATTEMPT14_STDOUT_SHA256 = "ccc370f82c7dc2043b97d063788a2a5cf43e2c8755a3cc7388911ccd6172bbab"
EXPECTED_ATTEMPT14_KIT_LOG_SHA256 = "0085e219a74f2c9f36fe32e65a38cc64fab039b656535af7f80209e44554511b"
EXPECTED_ATTEMPT14_TRACE_TMP_BYTES = 1784450644
SINGLE_GPU_KIT_ARGS = (
    "--/renderer/multiGpu/enabled=False "
    "--/renderer/multiGpu/autoEnable=False "
    "--/renderer/multiGpu/maxGpuCount=1"
)
EXPECTED_R14_SCHEMA = "pull_v0_repair_r14_receipt_v1"
EXPECTED_R14_REVISION = "R14"
EXPECTED_R14_ROOT_CAUSE = "ATTEMPT15_HYDRA_KIT_ARGS_TRANSPORT_FAILURE"
EXPECTED_R14_RECEIPT_SHA256 = "bedc40a3693db21981498573e5afd14e8ed736ca84eca5261dfacd9715b59d24"
EXPECTED_ATTEMPT15_RECEIPT_SHA256 = "01c952a4402a887275ff53f02f26ea4a88f3f6c79ed0fc4388f4d32cbde763b0"
EXPECTED_ATTEMPT15_PLAN_SHA256 = "254a6937153960ceff5f5c71299ec7106349e544a7b252e31b107123da091bbc"
EXPECTED_ATTEMPT15_PLAN_IDENTITY_SHA256 = "30568bef98d7dc1a54691c39640231e84a2e862fdefe6e382ca899275a53cceb"
EXPECTED_ATTEMPT15_PROCESS_SHA256 = "130460dddc02fc0f2f199b4a573ecafad49554513dce5fe4ee69e68fa152133b"
EXPECTED_ATTEMPT15_STDOUT_SHA256 = "91579492644ccba3239d89d43a0524bb1846edd152ace05d57bd9612f5e862bc"
EXPECTED_ATTEMPT16_RECEIPT_SHA256 = "2cfbd95e10dc57e16cf2f566925593c41680f3592539676c013c4931a22c06c5"
EXPECTED_ATTEMPT16_PLAN_SHA256 = "7371fef9948e72a9900da45074daba9d5848556ebc9dac91eb9eba44fdaf55e9"
EXPECTED_ATTEMPT16_STDOUT_SHA256 = "f490a2540c700304de21598a95e7c6f787dccf0a6a8338cb3536838aff321e0d"
EXPECTED_ATTEMPT16_KIT_LOG_SHA256 = "e3e1d25bae608e323122651f288b1528d7187f9d806779b581f8086d8ed25618"
EXPECTED_R15_SCHEMA = "pull_v0_repair_r15_receipt_v1"
EXPECTED_R15_REVISION = "R15"
EXPECTED_R15_RECEIPT_SHA256 = "3b850232429e4cdaee96281ad16ba2216f34df5baeb5262312f8bba831f841a0"
EXPECTED_ATTEMPT17_RECEIPT_SHA256 = "5c51dd2d51b2913acc12a9a379ece4fca151d798a4c79570f784e31588ef1cad"
EXPECTED_A4_A6_AUTHORITY_SHA256 = "84e94561bac1eb39b49d27e67c9f5b192844f7b9f5e203961495beea683dfc49"
EXPECTED_A4_A6_AUTHORITY_PATH = (
    "/home/baoquanc/workspace/DoorDog-A2_Piper/scriptsFORhuman/pull_task/"
    "a2_piper_pull_v0_gpu_lease_amendment_20260804.md"
)
EXPECTED_VULKAN_RECEIPT_SHA256 = "7d2fbc98a07355f989bc450e39b7ba85fe8deb29ecee32852605f07e6c7bd383"
EXPECTED_INFRA_RECLASSIFICATION_RECEIPT_SHA256 = "b3b31ff57e63e87c7712db862fb56f523229b579df7195370eee5e650ebe8b43"
EXPECTED_GPU_LEASE_AMENDMENT_SCHEMA = "pull_v0_gpu_lease_amendment_receipt_v1"
EXPECTED_GPU_LEASE_AMENDMENT_REVISION = "A4_A6"
EXPECTED_GPU_LEASE_AMENDMENT_SHA256 = "1a80804a1062e9878f73c35c89e360e7eaf95c2fa50a6dcf2a9cac85a259e292"
PULL_V0_RENDERER_SINGLE_GPU_OVERRIDE = "+a2_pull_v0_renderer_single_gpu=true"
EXPECTED_SUPERSEDED_R2_RECEIPT_SHA256 = (
    "9d03fdd870042890f24be5c9dfc841db8429f1c28741a236ef3ff5349af92e6f"
)
ATTEMPT3_RECEIPT_PATH = EVIDENCE_ROOT / "PULL_V0_P1_PUSH_ANCHOR_ATTEMPT3_RECEIPT.json"
ATTEMPT4_RECEIPT_PATH = EVIDENCE_ROOT / "PULL_V0_P1_PUSH_ANCHOR_ATTEMPT4_RECEIPT.json"
ATTEMPT5_RECEIPT_PATH = EVIDENCE_ROOT / "PULL_V0_P1_PUSH_ANCHOR_ATTEMPT5_RECEIPT.json"
ATTEMPT6_RECEIPT_PATH = EVIDENCE_ROOT / "PULL_V0_P1_PUSH_ANCHOR_ATTEMPT6_RECEIPT.json"
ATTEMPT7_RECEIPT_PATH = EVIDENCE_ROOT / "PULL_V0_P1_PUSH_ANCHOR_ATTEMPT7_RECEIPT.json"
ATTEMPT8_RECEIPT_PATH = EVIDENCE_ROOT / "PULL_V0_P1_PUSH_ANCHOR_ATTEMPT8_RECEIPT.json"
ATTEMPT9_RECEIPT_PATH = EVIDENCE_ROOT / "PULL_V0_P1_PUSH_ANCHOR_ATTEMPT9_RECEIPT.json"
EXPECTED_CHECKPOINT_SHA256 = (
    "f000f13e817309f7b73e33c5c4d95076397debb992713e5613dce567bfda806d"
)
FIXTURE = {
    "door_width_m": 0.95,
    "door_height_m": 2.05,
    "handle_height_m": 0.95,
    "handle_edge_offset_m": 0.115,
    "door_mass_kg": 120.0,
    "hinge_max_force_nm": 7.25,
    "hinge_stiffness_nm_per_rad": 5.5,
    "hinge_damping_nms_per_rad": 50.0,
    "handle_max_force_nm": 2.0,
    "handle_stiffness_nm_per_rad": 50.0,
    "handle_damping_nms_per_rad": 0.5,
    "axle_length_m": 0.195,
    "handle_length_m": 0.125,
    "hook_length_m": 0.050,
    "handle_radius_m": 0.013,
    "hook_present": True,
}
PULL_ANCHOR_MAX_STAGE_TIME = (400, 100, 100, 100, 100, 200)
PULL_ANCHOR_GLOBAL_MAX_EPISODE_LENGTH_S = 120
PULL_ANCHOR_RESET_QUALIFICATION_STEPS = 3
PULL_ANCHOR_LOCAL_STAGE0_TIMEOUT_STEPS = 360


def _validate_pull_anchor_stage_time_contract(value: object) -> list[int]:
    if (
        isinstance(value, (str, bytes))
        or not isinstance(value, (list, tuple))
        or len(value) != len(PULL_ANCHOR_MAX_STAGE_TIME)
        or any(isinstance(item, bool) or not isinstance(item, int) for item in value)
    ):
        raise RuntimeError(
            "Pull-anchor max_stage_time must be a six-entry integer sequence."
        )
    normalized = tuple(value)
    if normalized[0] <= (
        PULL_ANCHOR_RESET_QUALIFICATION_STEPS
        + PULL_ANCHOR_LOCAL_STAGE0_TIMEOUT_STEPS
    ):
        raise RuntimeError(
            "Pull-anchor host stage budget must exceed reset qualification plus local watchdog: "
            f"{normalized[0]} <= "
            f"{PULL_ANCHOR_RESET_QUALIFICATION_STEPS} + "
            f"{PULL_ANCHOR_LOCAL_STAGE0_TIMEOUT_STEPS}."
        )
    if normalized != PULL_ANCHOR_MAX_STAGE_TIME:
        raise RuntimeError(
            "Pull-anchor max_stage_time must be exactly "
            f"{list(PULL_ANCHOR_MAX_STAGE_TIME)!r}; got {list(normalized)!r}."
        )
    return list(normalized)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical_sha256(value: object) -> str:
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _hkt_now() -> str:
    return datetime.now(ZoneInfo("Asia/Hong_Kong")).strftime(
        "%Y-%m-%d %H:%M:%S HKT"
    )


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def _validate_attempt_index(attempt: int) -> int:
    if isinstance(attempt, bool) or not isinstance(attempt, int) or attempt <= 0:
        raise ValueError(f"attempt must be a positive integer; got {attempt!r}")
    return attempt


def _require_post_r1_attempt(attempt: int) -> int:
    attempt = _validate_attempt_index(attempt)
    if attempt < 3:
        raise RuntimeError(
            f"Historical attempt{attempt} is immutable; post-R1 admission requires attempt >= 3."
        )
    return attempt


def _attempt_output_root(attempt: int) -> Path:
    attempt = _validate_attempt_index(attempt)
    return ROOT / "logs_eval" / "a2_piper_pull_v0" / "p1_push_anchor" / f"attempt{attempt}"


def _attempt_plan_path(attempt: int) -> Path:
    attempt = _validate_attempt_index(attempt)
    return EVIDENCE_ROOT / f"PULL_V0_P1_PUSH_ANCHOR_ATTEMPT{attempt}_PLAN.json"


def _read_repair_receipt(
    path: Path | None = None,
    *,
    attempt: int = 3,
    repair_receipt_sha256: str | None = None,
    allow_attempt18_runtime: bool = False,
) -> tuple[dict, str]:
    if attempt == 3:
        expected_path = REPAIR_R1_RECEIPT_PATH
        selected_path = expected_path if path is None else path
        if not selected_path.is_absolute():
            selected_path = ROOT / selected_path
        if selected_path.resolve() != expected_path.resolve():
            raise RuntimeError(
                "Attempt 3 is immutable and must remain bound to the canonical Repair R1 receipt."
            )
    elif attempt == 4:
        if path is None:
            raise RuntimeError(
                "Post-R1 attempts >=4 require an explicit --repair-receipt R2 path."
            )
        expected_path = REPAIR_R2_RECEIPT_PATH
        selected_path = path
        if not selected_path.is_absolute():
            selected_path = ROOT / selected_path
        if selected_path.resolve() != expected_path.resolve():
            raise RuntimeError(
                "Post-R1 attempts >=4 accept only the canonical Repair R2 receipt path."
            )
    elif attempt == 5:
        if path is None:
            raise RuntimeError(
                "Post-R3 attempts >=5 require an explicit --repair-receipt R3 path."
            )
        expected_path = REPAIR_R3_RECEIPT_PATH
        selected_path = path
        if not selected_path.is_absolute():
            selected_path = ROOT / selected_path
        if selected_path.resolve() != expected_path.resolve():
            raise RuntimeError(
                "Post-R3 attempts >=5 accept only the canonical Repair R3 receipt path."
            )
    elif attempt == 19:
        if path is None:
            raise RuntimeError(
                "Attempt19 requires an explicit --repair-receipt R16 path."
            )
        if repair_receipt_sha256 is None:
            raise RuntimeError(
                "Attempt19 requires explicit --repair-receipt-sha256 binding."
            )
        expected_path = R16_RECEIPT_PATH
        selected_path = path
        if not selected_path.is_absolute():
            selected_path = ROOT / selected_path
        if selected_path.resolve() != expected_path.resolve():
            raise RuntimeError(
                "Attempt19 accepts only the canonical Repair R16 receipt path."
            )
    elif attempt == 20:
        if path is None:
            raise RuntimeError(
                "Attempt20 requires an explicit --repair-receipt R17 path."
            )
        if repair_receipt_sha256 is None:
            raise RuntimeError(
                "Attempt20 requires explicit --repair-receipt-sha256 binding."
            )
        expected_path = R17_RECEIPT_PATH
        selected_path = path
        if not selected_path.is_absolute():
            selected_path = ROOT / selected_path
        if selected_path.resolve() != expected_path.resolve():
            raise RuntimeError(
                "Attempt20 accepts only the canonical Repair R17 receipt path."
            )
    elif attempt >= 6:
        if attempt > 18:
            raise RuntimeError(
                f"Unsupported repair binding attempt: {attempt}; Repair R17 is sealed to attempt 20."
            )
        if repair_receipt_sha256 is None:
            raise RuntimeError(
                "Post-R4 attempts >=6 require explicit --repair-receipt-sha256 binding."
            )
        if (
            not isinstance(repair_receipt_sha256, str)
            or len(repair_receipt_sha256) != 64
            or any(character not in "0123456789abcdef" for character in repair_receipt_sha256)
        ):
            raise RuntimeError("--repair-receipt-sha256 must be exactly 64 lowercase hex characters.")
        if path is None:
            raise RuntimeError(
                "Post-R4 attempts >=6 require an explicit repair receipt path."
            )
        expected_path = (
            REPAIR_R4_RECEIPT_PATH
            if attempt == 6
            else REPAIR_R5_RECEIPT_PATH
            if attempt == 7
            else REPAIR_R6_RECEIPT_PATH
            if attempt == 8
            else REPAIR_R7_RECEIPT_PATH
            if attempt == 9
            else REPAIR_R8_RECEIPT_PATH
            if attempt == 10
            else REPAIR_R9_RECEIPT_PATH
            if attempt == 11
            else REPAIR_R10_RECEIPT_PATH
            if attempt == 12
            else REPAIR_R11_RECEIPT_PATH
            if attempt == 13
            else REPAIR_R12_RECEIPT_PATH
            if attempt == 14
            else REPAIR_R13_RECEIPT_PATH
            if attempt == 15
            else REPAIR_R14_RECEIPT_PATH
            if attempt == 16
            else GPU_LEASE_AMENDMENT_RECEIPT_PATH
            if attempt == 17
            else R15_RECEIPT_PATH
        )
        selected_path = path
        if not selected_path.is_absolute():
            selected_path = ROOT / selected_path
        if selected_path.resolve() != expected_path.resolve():
            expected_label = (
                "Repair R9"
                if attempt == 11
                else "Repair R10"
                if attempt == 12
                else "Repair R11"
                if attempt == 13
                else "Repair R12"
                if attempt == 14
                else "Repair R13"
                if attempt == 15
                else "Repair R14"
                if attempt == 16
                else "A4_A6 GPU-lease amendment"
                if attempt == 17
                else "Repair R15"
            )
            raise RuntimeError(
                f"Post-R4 attempt {attempt} accepts only the canonical {expected_label} path."
            )
    else:
        raise RuntimeError(f"Unsupported repair binding attempt: {attempt}")
    if not selected_path.is_file() or selected_path.is_symlink():
        raise RuntimeError(f"Repair receipt must be a regular file: {selected_path}")
    receipt_sha256 = _sha256(selected_path)
    if attempt == 4 and receipt_sha256 == EXPECTED_SUPERSEDED_R2_RECEIPT_SHA256:
        raise RuntimeError("Repair R2 receipt is the superseded pre-bind validation-count artifact.")
    receipt = json.loads(selected_path.read_text(encoding="utf-8"))
    if not isinstance(receipt, dict):
        raise RuntimeError(f"Repair receipt must be a JSON object: {selected_path}")
    if attempt == 3:
        if receipt_sha256 != EXPECTED_REPAIR_RECEIPT_SHA256:
            raise RuntimeError(
                "Repair R1 receipt hash changed; update the authorized binding before preparation: "
                f"expected={EXPECTED_REPAIR_RECEIPT_SHA256}, actual={receipt_sha256}."
            )
        if (
            receipt.get("schema_version") != "pull_v0_repair_r1_receipt_v1"
            or receipt.get("repair_revision") != "R1"
            or receipt.get("stale_candidate_id") != EXPECTED_STALE_CANDIDATE_ID
        ):
            raise RuntimeError("Repair R1 receipt identity does not match the authorized binding.")
        return receipt, receipt_sha256
    parent = receipt.get("parent_receipt")
    trigger = receipt.get("trigger")
    if attempt == 19:
        if (
            receipt_sha256 != repair_receipt_sha256
            or receipt_sha256 != EXPECTED_R16_RECEIPT_SHA256
            or receipt.get("schema_version") != "pull_v0_repair_r16_receipt_v1"
            or receipt.get("repair_revision") != "R16"
            or receipt.get("revision_detail") != "R16.4"
            or receipt.get("status") != "APPROVED_FOR_ATTEMPT19_PREPARATION_ONLY"
            or receipt.get("runtime_validation") != "NOT_RUN"
            or receipt.get("scientific_verdict_consumed") is not False
            or receipt.get("stale_candidate_id") != EXPECTED_STALE_CANDIDATE_ID
            or not isinstance(parent, dict)
            or parent.get("path") != "scriptsFORhuman/pull_v0/PULL_V0_P1_PUSH_ANCHOR_ATTEMPT18_RECEIPT.json"
            or not isinstance(parent.get("sha256"), str)
            or not ATTEMPT18_RECEIPT_PATH.is_file()
            or parent.get("sha256") != _sha256(ATTEMPT18_RECEIPT_PATH)
            or parent.get("repair_revision") != "ATTEMPT18_RUNTIME"
            or not isinstance(receipt.get("source_repair"), dict)
            or receipt["source_repair"].get("anchor_only_detailed_contact_capacity")
            != ATTEMPT19_CONTACT_CAPACITY
            or receipt["source_repair"].get("shared_default_detailed_contact_capacity")
            != SHARED_CONTACT_CAPACITY
            or receipt["source_repair"].get("track_contact_points") is not True
            or receipt["source_repair"].get("track_friction_forces") is not True
            or receipt["source_repair"].get("track_pose") is not True
            or receipt.get("attempt19_preparation_contract", {}).get(
                "detailed_contact_capacity"
            )
            != ATTEMPT19_CONTACT_CAPACITY
            or receipt.get("attempt19_preparation_contract", {}).get(
                "evidence_derivation_revision"
            )
            != "R16.4"
        ):
            raise RuntimeError(
                "Repair R16 identity, Attempt18 parent binding, or contact-capacity contract is not authorized."
            )
        return receipt, receipt_sha256
    if attempt == 20:
        scope = receipt.get("scope")
        contract = receipt.get("attempt20_preparation_contract")
        if (
            receipt_sha256 != repair_receipt_sha256
            or receipt.get("schema_version") != EXPECTED_R17_SCHEMA
            or receipt.get("repair_revision") != EXPECTED_R17_REVISION
            or receipt.get("status") != EXPECTED_R17_STATUS
            or receipt.get("runtime_validation") != "NOT_RUN"
            or receipt.get("scientific_verdict_consumed") is not False
            or receipt.get("stale_candidate_id") != EXPECTED_STALE_CANDIDATE_ID
            or not isinstance(parent, dict)
            or parent.get("path") != str(R16_RECEIPT_PATH.relative_to(ROOT))
            or parent.get("sha256") != EXPECTED_R16_RECEIPT_SHA256
            or parent.get("repair_revision") != EXPECTED_R16_REVISION
            or not isinstance(trigger, dict)
            or trigger.get("attempt") != 19
            or not isinstance(trigger.get("root_cause"), str)
            or not trigger["root_cause"].strip()
            or not isinstance(scope, dict)
            or scope.get("attempt19_artifacts_immutable") is not True
            or scope.get("attempt20_prepared") is not False
            or scope.get("attempt20_runtime_executed") is not False
            or scope.get("product_mechanics_changed") is not False
            or not isinstance(contract, dict)
            or contract.get("next_attempt") != 20
            or contract.get("context_classification_mode")
            != ATTEMPT_GPU_CONTEXT_CLASSIFICATION_MODES[20]["mode"]
            or contract.get("process_receipt_on_interrupt_required") is not True
            or contract.get("lifecycle_signal_receipt_required") is not True
            or contract.get("other_tenant_attribution_for_attempt_pid_allowed") is not False
        ):
            raise RuntimeError(
                "Repair R17 identity, Attempt19 trigger, or Attempt20 lifecycle/classification contract is not authorized."
            )
        return receipt, receipt_sha256
    if attempt == 4:
        if (
            receipt_sha256 != EXPECTED_R2_RECEIPT_SHA256
            or receipt.get("schema_version") != EXPECTED_R2_SCHEMA
            or receipt.get("repair_revision") != EXPECTED_R2_REVISION
            or receipt.get("stale_candidate_id") != EXPECTED_STALE_CANDIDATE_ID
            or not isinstance(parent, dict)
            or parent.get("path") != str(REPAIR_R1_RECEIPT_PATH.relative_to(ROOT))
            or parent.get("sha256") != EXPECTED_REPAIR_RECEIPT_SHA256
            or parent.get("repair_revision") != "R1"
            or not isinstance(trigger, dict)
            or trigger.get("attempt") != EXPECTED_R2_TRIGGER_ATTEMPT
            or trigger.get("root_cause") != EXPECTED_R2_ROOT_CAUSE
        ):
            raise RuntimeError(
                "Repair R2 receipt identity, parent R1 binding, or trigger is not authorized."
            )
        attempt3_artifact = trigger.get("attempt_receipt")
        if not isinstance(attempt3_artifact, dict):
            raise RuntimeError("Repair R2 trigger must include the immutable attempt3 receipt artifact.")
        if (
            attempt3_artifact.get("path") != str(ATTEMPT3_RECEIPT_PATH.relative_to(ROOT))
            or not ATTEMPT3_RECEIPT_PATH.is_file()
            or attempt3_artifact.get("sha256") != _sha256(ATTEMPT3_RECEIPT_PATH)
        ):
            raise RuntimeError("Repair R2 trigger does not bind the immutable attempt3 receipt.")
        return receipt, receipt_sha256
    if attempt == 5:
        if (
            receipt.get("schema_version") != EXPECTED_R3_SCHEMA
            or receipt.get("repair_revision") != EXPECTED_R3_REVISION
            or receipt.get("stale_candidate_id") != EXPECTED_STALE_CANDIDATE_ID
            or not isinstance(parent, dict)
            or parent.get("path") != str(REPAIR_R2_RECEIPT_PATH.relative_to(ROOT))
            or parent.get("sha256") != EXPECTED_R2_RECEIPT_SHA256
            or parent.get("repair_revision") != "R2"
            or not isinstance(trigger, dict)
            or trigger.get("attempt") != EXPECTED_R3_TRIGGER_ATTEMPT
            or trigger.get("root_cause") != EXPECTED_R3_ROOT_CAUSE
        ):
            raise RuntimeError(
                "Repair R3 receipt identity, parent R2 binding, or trigger is not authorized."
            )
        attempt4_artifact = trigger.get("attempt_receipt")
        if not isinstance(attempt4_artifact, dict):
            raise RuntimeError("Repair R3 trigger must include the immutable attempt4 receipt artifact.")
        if (
            attempt4_artifact.get("path") != str(ATTEMPT4_RECEIPT_PATH.relative_to(ROOT))
            or not ATTEMPT4_RECEIPT_PATH.is_file()
            or attempt4_artifact.get("sha256") != _sha256(ATTEMPT4_RECEIPT_PATH)
        ):
            raise RuntimeError("Repair R3 trigger does not bind immutable attempt4 receipt.")
        return receipt, receipt_sha256
    if attempt == 6:
        if (
            receipt_sha256 != repair_receipt_sha256
            or receipt_sha256 != EXPECTED_R4_RECEIPT_SHA256
            or receipt.get("schema_version") != EXPECTED_R4_SCHEMA
            or receipt.get("repair_revision") != EXPECTED_R4_REVISION
            or receipt.get("stale_candidate_id") != EXPECTED_STALE_CANDIDATE_ID
            or not isinstance(parent, dict)
            or parent.get("path") != str(REPAIR_R3_RECEIPT_PATH.relative_to(ROOT))
            or parent.get("sha256") != EXPECTED_R3_RECEIPT_SHA256
            or parent.get("repair_revision") != "R3"
            or not isinstance(trigger, dict)
            or trigger.get("attempt") != EXPECTED_R4_TRIGGER_ATTEMPT
            or trigger.get("root_cause") != EXPECTED_R4_ROOT_CAUSE
        ):
            raise RuntimeError(
                "Repair R4 receipt identity, parent R3 binding, or trigger is not authorized."
            )
        attempt5_artifact = trigger.get("attempt_receipt")
        if not isinstance(attempt5_artifact, dict):
            raise RuntimeError("Repair R4 trigger must include the immutable attempt5 receipt artifact.")
        if (
            attempt5_artifact.get("path") != str(ATTEMPT5_RECEIPT_PATH.relative_to(ROOT))
            or not ATTEMPT5_RECEIPT_PATH.is_file()
            or attempt5_artifact.get("sha256") != _sha256(ATTEMPT5_RECEIPT_PATH)
        ):
            raise RuntimeError("Repair R4 trigger does not bind immutable attempt5 receipt.")
        return receipt, receipt_sha256
    if attempt == 7:
        if (
            receipt_sha256 != repair_receipt_sha256
            or receipt.get("schema_version") != EXPECTED_R5_SCHEMA
            or receipt.get("repair_revision") != EXPECTED_R5_REVISION
            or receipt.get("stale_candidate_id") != EXPECTED_STALE_CANDIDATE_ID
            or not isinstance(parent, dict)
            or parent.get("path") != str(REPAIR_R4_RECEIPT_PATH.relative_to(ROOT))
            or parent.get("sha256") != EXPECTED_R4_RECEIPT_SHA256
            or parent.get("repair_revision") != "R4"
            or not isinstance(trigger, dict)
            or trigger.get("attempt") != EXPECTED_R5_TRIGGER_ATTEMPT
            or trigger.get("root_cause") != EXPECTED_R5_ROOT_CAUSE
        ):
            raise RuntimeError(
                "Repair R5 receipt identity, parent R4 binding, or trigger is not authorized."
            )
        attempt6_artifact = trigger.get("attempt_receipt")
        if not isinstance(attempt6_artifact, dict):
            raise RuntimeError("Repair R5 trigger must include the immutable attempt6 receipt artifact.")
        if (
            attempt6_artifact.get("path") != str(ATTEMPT6_RECEIPT_PATH.relative_to(ROOT))
            or not ATTEMPT6_RECEIPT_PATH.is_file()
            or attempt6_artifact.get("sha256") != _sha256(ATTEMPT6_RECEIPT_PATH)
        ):
            raise RuntimeError("Repair R5 trigger does not bind immutable attempt6 receipt.")
        return receipt, receipt_sha256
    if attempt == 8:
        if (
            receipt_sha256 != repair_receipt_sha256
            or receipt_sha256 != EXPECTED_R6_RECEIPT_SHA256
            or receipt.get("schema_version") != EXPECTED_R6_SCHEMA
            or receipt.get("repair_revision") != EXPECTED_R6_REVISION
            or receipt.get("stale_candidate_id") != EXPECTED_STALE_CANDIDATE_ID
            or not isinstance(parent, dict)
            or parent.get("path") != str(REPAIR_R5_RECEIPT_PATH.relative_to(ROOT))
            or parent.get("sha256") != _sha256(REPAIR_R5_RECEIPT_PATH)
            or parent.get("repair_revision") != EXPECTED_R5_REVISION
            or not isinstance(trigger, dict)
            or trigger.get("attempt") != EXPECTED_R6_TRIGGER_ATTEMPT
            or trigger.get("root_cause") != EXPECTED_R6_ROOT_CAUSE
        ):
            raise RuntimeError(
                "Repair R6 receipt identity, parent R5 binding, or trigger is not authorized."
            )
        attempt7_artifact = trigger.get("attempt_receipt")
        if not isinstance(attempt7_artifact, dict):
            raise RuntimeError("Repair R6 trigger must include the immutable attempt7 receipt artifact.")
        if (
            attempt7_artifact.get("path") != str(ATTEMPT7_RECEIPT_PATH.relative_to(ROOT))
            or not ATTEMPT7_RECEIPT_PATH.is_file()
            or attempt7_artifact.get("sha256") != _sha256(ATTEMPT7_RECEIPT_PATH)
        ):
            raise RuntimeError("Repair R6 trigger does not bind immutable attempt7 receipt.")
        return receipt, receipt_sha256
    if attempt == 9:
        if (
            receipt_sha256 != repair_receipt_sha256
            or receipt_sha256 != EXPECTED_R7_RECEIPT_SHA256
            or receipt.get("schema_version") != EXPECTED_R7_SCHEMA
            or receipt.get("repair_revision") != EXPECTED_R7_REVISION
            or receipt.get("stale_candidate_id") != EXPECTED_STALE_CANDIDATE_ID
            or not isinstance(parent, dict)
            or parent.get("path") != str(REPAIR_R6_RECEIPT_PATH.relative_to(ROOT))
            or parent.get("sha256") != EXPECTED_R6_RECEIPT_SHA256
            or parent.get("repair_revision") != EXPECTED_R6_REVISION
            or not isinstance(trigger, dict)
            or trigger.get("attempt") != EXPECTED_R7_TRIGGER_ATTEMPT
            or trigger.get("root_cause") != "ATTEMPT8_TELEMETRY_SCHEMA_INVALIDATED"
        ):
            raise RuntimeError(
                "Repair R7 identity, parent R6 binding, or trigger is not authorized."
            )
        attempt8_artifact = trigger.get("attempt_receipt")
        invalidation_artifact = trigger.get("invalidation_manifest")
        if not isinstance(attempt8_artifact, dict) or not isinstance(invalidation_artifact, dict):
            raise RuntimeError("Repair R7 trigger must include Attempt8 receipt and invalidation artifacts.")
        if (
            attempt8_artifact.get("path") != str(ATTEMPT8_RECEIPT_PATH.relative_to(ROOT))
            or attempt8_artifact.get("sha256") != EXPECTED_ATTEMPT8_RECEIPT_SHA256
            or not ATTEMPT8_RECEIPT_PATH.is_file()
            or _sha256(ATTEMPT8_RECEIPT_PATH) != EXPECTED_ATTEMPT8_RECEIPT_SHA256
            or invalidation_artifact.get("path") != str(ATTEMPT8_INVALIDATION_PATH.relative_to(ROOT))
            or invalidation_artifact.get("sha256") != EXPECTED_ATTEMPT8_INVALIDATION_SHA256
            or not ATTEMPT8_INVALIDATION_PATH.is_file()
            or _sha256(ATTEMPT8_INVALIDATION_PATH) != EXPECTED_ATTEMPT8_INVALIDATION_SHA256
        ):
            raise RuntimeError("Repair R7 trigger does not bind immutable Attempt8 invalid evidence.")
        return receipt, receipt_sha256
    if attempt == 10:
        if (
            receipt_sha256 != repair_receipt_sha256
            or receipt_sha256 != EXPECTED_R8_RECEIPT_SHA256
            or receipt.get("schema_version") != EXPECTED_R8_SCHEMA
            or receipt.get("repair_revision") != EXPECTED_R8_REVISION
            or receipt.get("stale_candidate_id") != EXPECTED_STALE_CANDIDATE_ID
            or not isinstance(parent, dict)
            or parent.get("path") != str(REPAIR_R7_RECEIPT_PATH.relative_to(ROOT))
            or parent.get("sha256") != EXPECTED_R7_RECEIPT_SHA256
            or parent.get("repair_revision") != EXPECTED_R7_REVISION
            or not isinstance(trigger, dict)
            or trigger.get("attempt") != EXPECTED_R8_TRIGGER_ATTEMPT
            or trigger.get("root_cause") != "ATTEMPT9_QUATERNION_SOURCE_AND_RECEIPT_NORMALIZATION"
        ):
            raise RuntimeError(
                "Repair R8 identity, parent R7 binding, or trigger is not authorized."
            )
        attempt9_artifact = trigger.get("attempt_receipt")
        invalidation_artifact = trigger.get("invalidation_manifest")
        normalized_artifact = trigger.get("normalized_response_telemetry")
        if not all(
            isinstance(value, dict)
            for value in (attempt9_artifact, invalidation_artifact, normalized_artifact)
        ):
            raise RuntimeError(
                "Repair R8 trigger must include Attempt9 receipt, invalidation, and normalized telemetry artifacts."
            )
        if (
            attempt9_artifact.get("path") != str(ATTEMPT9_RECEIPT_PATH.relative_to(ROOT))
            or attempt9_artifact.get("sha256") != EXPECTED_ATTEMPT9_RECEIPT_SHA256
            or not ATTEMPT9_RECEIPT_PATH.is_file()
            or _sha256(ATTEMPT9_RECEIPT_PATH) != EXPECTED_ATTEMPT9_RECEIPT_SHA256
            or invalidation_artifact.get("path") != str(ATTEMPT9_INVALIDATION_PATH.relative_to(ROOT))
            or invalidation_artifact.get("sha256") != EXPECTED_ATTEMPT9_INVALIDATION_SHA256
            or not ATTEMPT9_INVALIDATION_PATH.is_file()
            or _sha256(ATTEMPT9_INVALIDATION_PATH) != EXPECTED_ATTEMPT9_INVALIDATION_SHA256
            or normalized_artifact.get("path") != str(ATTEMPT9_RESPONSE_TELEMETRY_PATH.relative_to(ROOT))
            or normalized_artifact.get("sha256") != EXPECTED_ATTEMPT9_RESPONSE_TELEMETRY_SHA256
            or not ATTEMPT9_RESPONSE_TELEMETRY_PATH.is_file()
            or _sha256(ATTEMPT9_RESPONSE_TELEMETRY_PATH) != EXPECTED_ATTEMPT9_RESPONSE_TELEMETRY_SHA256
        ):
            raise RuntimeError("Repair R8 trigger does not bind immutable Attempt9 evidence.")
        return receipt, receipt_sha256
    if attempt == 11:
        if (
            receipt_sha256 != repair_receipt_sha256
            or receipt_sha256 != EXPECTED_R9_RECEIPT_SHA256
            or receipt.get("schema_version") != EXPECTED_R9_SCHEMA
            or receipt.get("repair_revision") != EXPECTED_R9_REVISION
            or receipt.get("stale_candidate_id") != EXPECTED_STALE_CANDIDATE_ID
            or not isinstance(parent, dict)
            or parent.get("path") != str(REPAIR_R8_RECEIPT_PATH.relative_to(ROOT))
            or parent.get("sha256") != EXPECTED_R8_RECEIPT_SHA256
            or parent.get("repair_revision") != EXPECTED_R8_REVISION
            or not isinstance(trigger, dict)
            or trigger.get("attempt") != EXPECTED_R9_TRIGGER_ATTEMPT
            or trigger.get("root_cause") != EXPECTED_R9_ROOT_CAUSE
        ):
            raise RuntimeError(
                "Repair R9 identity, parent R8 binding, or trigger is not authorized."
            )
        attempt10_artifact = trigger.get("attempt_receipt")
        immutable_runtime_artifacts = trigger.get("immutable_runtime_artifacts")
        if not isinstance(attempt10_artifact, dict) or not isinstance(immutable_runtime_artifacts, dict):
            raise RuntimeError(
                "Repair R9 trigger must include Attempt10 receipt and immutable runtime artifacts."
            )
        if (
            attempt10_artifact.get("path") != str(ATTEMPT10_RECEIPT_PATH.relative_to(ROOT))
            or attempt10_artifact.get("sha256") != EXPECTED_ATTEMPT10_RECEIPT_SHA256
            or not ATTEMPT10_RECEIPT_PATH.is_file()
            or _sha256(ATTEMPT10_RECEIPT_PATH) != EXPECTED_ATTEMPT10_RECEIPT_SHA256
        ):
            raise RuntimeError("Repair R9 trigger does not bind the canonical Attempt10 receipt.")
        expected_runtime_artifacts = {
            "plan": (
                ROOT / "scriptsFORhuman/pull_v0/PULL_V0_P1_PUSH_ANCHOR_ATTEMPT10_PLAN.json",
                EXPECTED_ATTEMPT10_PLAN_SHA256,
            ),
            "process_receipt": (
                ROOT / "logs_eval/a2_piper_pull_v0/p1_push_anchor/attempt10/process_receipt.json",
                EXPECTED_ATTEMPT10_PROCESS_SHA256,
            ),
            "log": (
                ROOT / "logs_eval/a2_piper_pull_v0/p1_push_anchor/attempt10/stdout_stderr.log",
                EXPECTED_ATTEMPT10_LOG_SHA256,
            ),
            "summary": (
                ROOT / "logs_eval/a2_piper_pull_v0/p1_push_anchor/attempt10/eval/a2_hold_oracle_summary.json",
                EXPECTED_ATTEMPT10_SUMMARY_SHA256,
            ),
            "metrics": (
                ROOT / "logs_eval/a2_piper_pull_v0/p1_push_anchor/attempt10/eval/metrics_eval.json",
                EXPECTED_ATTEMPT10_METRICS_SHA256,
            ),
        }
        for name, (artifact_path, expected_sha256) in expected_runtime_artifacts.items():
            artifact = immutable_runtime_artifacts.get(name)
            if (
                not isinstance(artifact, dict)
                or artifact.get("path") != str(artifact_path.relative_to(ROOT))
                or artifact.get("sha256") != expected_sha256
                or not artifact_path.is_file()
                or _sha256(artifact_path) != expected_sha256
            ):
                raise RuntimeError(
                    f"Repair R9 immutable runtime artifact binding is invalid: {name}."
                )
        process_receipt = json.loads(
            (ROOT / "logs_eval/a2_piper_pull_v0/p1_push_anchor/attempt10/process_receipt.json")
            .read_text(encoding="utf-8")
        )
        if (
            not isinstance(process_receipt, dict)
            or process_receipt.get("attempt") != 10
            or process_receipt.get("plan_sha256") != EXPECTED_ATTEMPT10_PLAN_IDENTITY_SHA256
            or process_receipt.get("repair_receipt_sha256") != EXPECTED_R8_RECEIPT_SHA256
            or process_receipt.get("stdout_stderr_sha256") != EXPECTED_ATTEMPT10_LOG_SHA256
            or process_receipt.get("summary_sha256") != EXPECTED_ATTEMPT10_SUMMARY_SHA256
            or process_receipt.get("metrics_sha256") != EXPECTED_ATTEMPT10_METRICS_SHA256
        ):
            raise RuntimeError("Repair R9 process receipt does not preserve the immutable Attempt10 bindings.")
        return receipt, receipt_sha256
    if attempt == 12:
        if (
            receipt_sha256 != repair_receipt_sha256
            or receipt_sha256 != EXPECTED_R10_RECEIPT_SHA256
            or receipt.get("schema_version") != EXPECTED_R10_SCHEMA
            or receipt.get("repair_revision") != EXPECTED_R10_REVISION
            or receipt.get("stale_candidate_id") != EXPECTED_STALE_CANDIDATE_ID
            or not isinstance(parent, dict)
            or parent.get("path") != str(REPAIR_R9_RECEIPT_PATH.relative_to(ROOT))
            or parent.get("sha256") != EXPECTED_R9_RECEIPT_SHA256
            or parent.get("repair_revision") != EXPECTED_R9_REVISION
            or not isinstance(trigger, dict)
            or trigger.get("attempt") != 11
            or trigger.get("root_cause") != EXPECTED_R10_ROOT_CAUSE
        ):
            raise RuntimeError(
                "Repair R10 identity, parent R9 binding, or trigger is not authorized."
            )
        attempt11_artifact = trigger.get("attempt_receipt")
        immutable_runtime_artifacts = trigger.get("immutable_runtime_artifacts")
        if not isinstance(attempt11_artifact, dict) or not isinstance(
            immutable_runtime_artifacts, dict
        ):
            raise RuntimeError(
                "Repair R10 trigger must include Attempt11 receipt and immutable runtime artifacts."
            )
        if (
            attempt11_artifact.get("path")
            != str(ATTEMPT11_RECEIPT_PATH.relative_to(ROOT))
            or attempt11_artifact.get("sha256") != EXPECTED_ATTEMPT11_RECEIPT_SHA256
            or not ATTEMPT11_RECEIPT_PATH.is_file()
            or _sha256(ATTEMPT11_RECEIPT_PATH) != EXPECTED_ATTEMPT11_RECEIPT_SHA256
        ):
            raise RuntimeError("Repair R10 trigger does not bind the canonical Attempt11 receipt.")
        expected_runtime_artifacts = {
            "plan": (
                ROOT / "scriptsFORhuman/pull_v0/PULL_V0_P1_PUSH_ANCHOR_ATTEMPT11_PLAN.json",
                EXPECTED_ATTEMPT11_PLAN_SHA256,
            ),
            "process_receipt": (
                ROOT / "logs_eval/a2_piper_pull_v0/p1_push_anchor/attempt11/process_receipt.json",
                EXPECTED_ATTEMPT11_PROCESS_SHA256,
            ),
            "log": (
                ROOT / "logs_eval/a2_piper_pull_v0/p1_push_anchor/attempt11/stdout_stderr.log",
                EXPECTED_ATTEMPT11_LOG_SHA256,
            ),
            "summary": (
                ROOT
                / "logs_eval/a2_piper_pull_v0/p1_push_anchor/attempt11/eval/a2_hold_oracle_summary.json",
                EXPECTED_ATTEMPT11_SUMMARY_SHA256,
            ),
            "metrics": (
                ROOT
                / "logs_eval/a2_piper_pull_v0/p1_push_anchor/attempt11/eval/metrics_eval.json",
                EXPECTED_ATTEMPT11_METRICS_SHA256,
            ),
        }
        for name, (artifact_path, expected_sha256) in expected_runtime_artifacts.items():
            artifact = immutable_runtime_artifacts.get(name)
            if (
                not isinstance(artifact, dict)
                or artifact.get("path") != str(artifact_path.relative_to(ROOT))
                or artifact.get("sha256") != expected_sha256
                or not artifact_path.is_file()
                or _sha256(artifact_path) != expected_sha256
            ):
                raise RuntimeError(
                    f"Repair R10 immutable runtime artifact binding is invalid: {name}."
                )
        process_receipt = json.loads(
            (
                ROOT
                / "logs_eval/a2_piper_pull_v0/p1_push_anchor/attempt11/process_receipt.json"
            ).read_text(encoding="utf-8")
        )
        if (
            not isinstance(process_receipt, dict)
            or process_receipt.get("attempt") != 11
            or process_receipt.get("plan_sha256") != EXPECTED_ATTEMPT11_PLAN_IDENTITY_SHA256
            or process_receipt.get("repair_receipt_sha256") != EXPECTED_R9_RECEIPT_SHA256
            or process_receipt.get("stdout_stderr_sha256") != EXPECTED_ATTEMPT11_LOG_SHA256
            or process_receipt.get("summary_sha256") != EXPECTED_ATTEMPT11_SUMMARY_SHA256
            or process_receipt.get("metrics_sha256") != EXPECTED_ATTEMPT11_METRICS_SHA256
        ):
            raise RuntimeError(
                "Repair R10 process receipt does not preserve the immutable Attempt11 bindings."
            )
        return receipt, receipt_sha256
    if attempt == 13:
        if (
            receipt_sha256 != repair_receipt_sha256
            or receipt_sha256 != EXPECTED_R11_RECEIPT_SHA256
            or receipt.get("schema_version") != EXPECTED_R11_SCHEMA
            or receipt.get("repair_revision") != EXPECTED_R11_REVISION
            or receipt.get("stale_candidate_id") != EXPECTED_STALE_CANDIDATE_ID
            or not isinstance(parent, dict)
            or parent.get("path") != str(REPAIR_R10_RECEIPT_PATH.relative_to(ROOT))
            or parent.get("sha256") != EXPECTED_R10_RECEIPT_SHA256
            or parent.get("repair_revision") != EXPECTED_R10_REVISION
            or not isinstance(trigger, dict)
            or trigger.get("attempt") != 12
            or trigger.get("root_cause") != EXPECTED_R11_ROOT_CAUSE
        ):
            raise RuntimeError(
                "Repair R11 identity, parent R10 binding, or trigger is not authorized."
            )
        invalidation_artifact = trigger.get("invalidation_manifest")
        if not isinstance(invalidation_artifact, dict):
            raise RuntimeError(
                "Repair R11 trigger must include the Attempt12 preparation invalidation artifact."
            )
        if (
            invalidation_artifact.get("path") != str(ATTEMPT12_INVALIDATION_PATH.relative_to(ROOT))
            or invalidation_artifact.get("sha256") != EXPECTED_ATTEMPT12_INVALIDATION_SHA256
            or not ATTEMPT12_INVALIDATION_PATH.is_file()
            or _sha256(ATTEMPT12_INVALIDATION_PATH) != EXPECTED_ATTEMPT12_INVALIDATION_SHA256
        ):
            raise RuntimeError(
                "Repair R11 trigger does not bind the canonical Attempt12 invalidation artifact."
            )
        invalidation = json.loads(ATTEMPT12_INVALIDATION_PATH.read_text(encoding="utf-8"))
        if (
            not isinstance(invalidation, dict)
            or invalidation.get("preparation_validity") != "PREPARATION_INVALID"
            or invalidation.get("probe_validity") != "NOT_RUN"
            or invalidation.get("runtime_validation") != "NOT_RUN"
            or invalidation.get("pull_mechanism_verdict") != "NOT_ASSESSED"
            or invalidation.get("plan", {}).get("sha256") != EXPECTED_ATTEMPT12_PLAN_SHA256
            or invalidation.get("absence_of_runtime_artifacts", {}).get("process_receipt") is not False
            or invalidation.get("absence_of_runtime_artifacts", {}).get("log") is not False
            or invalidation.get("absence_of_runtime_artifacts", {}).get("summary") is not False
            or invalidation.get("absence_of_runtime_artifacts", {}).get("metrics") is not False
        ):
            raise RuntimeError(
                "Attempt12 preparation invalidation does not preserve the required no-runtime evidence."
            )
        return receipt, receipt_sha256
    if attempt == 14:
        attempt13_artifact = trigger.get("attempt_receipt") if isinstance(trigger, dict) else None
        immutable_runtime_artifacts = (
            trigger.get("immutable_runtime_artifacts") if isinstance(trigger, dict) else None
        )
        if (
            receipt_sha256 != repair_receipt_sha256
            or receipt_sha256 != EXPECTED_R12_RECEIPT_SHA256
            or receipt.get("schema_version") != EXPECTED_R12_SCHEMA
            or receipt.get("repair_revision") != EXPECTED_R12_REVISION
            or receipt.get("stale_candidate_id") != EXPECTED_STALE_CANDIDATE_ID
            or not isinstance(parent, dict)
            or parent.get("path") != str(REPAIR_R11_RECEIPT_PATH.relative_to(ROOT))
            or parent.get("sha256") != EXPECTED_R11_RECEIPT_SHA256
            or parent.get("repair_revision") != EXPECTED_R11_REVISION
            or not isinstance(trigger, dict)
            or trigger.get("attempt") != 13
            or trigger.get("root_cause") != EXPECTED_R12_ROOT_CAUSE
            or not isinstance(attempt13_artifact, dict)
            or attempt13_artifact.get("path") != str(ATTEMPT13_RECEIPT_PATH.relative_to(ROOT))
            or attempt13_artifact.get("sha256") != EXPECTED_ATTEMPT13_RECEIPT_SHA256
            or not ATTEMPT13_RECEIPT_PATH.is_file()
            or _sha256(ATTEMPT13_RECEIPT_PATH) != EXPECTED_ATTEMPT13_RECEIPT_SHA256
            or not isinstance(immutable_runtime_artifacts, dict)
        ):
            raise RuntimeError(
                "Repair R12 identity, parent R11 binding, or Attempt13 application evidence is not authorized."
            )
        expected_runtime_artifacts = {
            "plan": (
                ROOT / "scriptsFORhuman/pull_v0/PULL_V0_P1_PUSH_ANCHOR_ATTEMPT13_PLAN.json",
                EXPECTED_ATTEMPT13_PLAN_SHA256,
            ),
            "process_receipt": (
                ROOT / "logs_eval/a2_piper_pull_v0/p1_push_anchor/attempt13/process_receipt.json",
                EXPECTED_ATTEMPT13_PROCESS_SHA256,
            ),
            "log": (
                ROOT / "logs_eval/a2_piper_pull_v0/p1_push_anchor/attempt13/stdout_stderr.log",
                EXPECTED_ATTEMPT13_LOG_SHA256,
            ),
        }
        for name, (artifact_path, expected_sha256) in expected_runtime_artifacts.items():
            artifact = immutable_runtime_artifacts.get(name)
            if (
                not isinstance(artifact, dict)
                or artifact.get("path") != str(artifact_path.relative_to(ROOT))
                or artifact.get("sha256") != expected_sha256
                or not artifact_path.is_file()
                or _sha256(artifact_path) != expected_sha256
            ):
                raise RuntimeError(f"Repair R12 immutable Attempt13 artifact binding is invalid: {name}.")
        attempt13_receipt = json.loads(ATTEMPT13_RECEIPT_PATH.read_text(encoding="utf-8"))
        if (
            not isinstance(attempt13_receipt, dict)
            or attempt13_receipt.get("schema_version") != "pull_v0_p1_push_anchor_attempt_receipt_v13"
            or attempt13_receipt.get("attempt") != 13
            or attempt13_receipt.get("status") != "APPLICATION_CONFIG_ERROR_BEFORE_PROBE"
            or attempt13_receipt.get("probe_validity") != "NOT_RUN"
            or attempt13_receipt.get("runtime_validation") != "NOT_RUN"
            or attempt13_receipt.get("pull_mechanism_verdict") != "NOT_ASSESSED"
            or attempt13_receipt.get("application_success") is not False
            or attempt13_receipt.get("natural_exit") is not False
            or attempt13_receipt.get("application_contract_error", {}).get("exception_type")
            != EXPECTED_ATTEMPT13_ERROR_TYPE
            or attempt13_receipt.get("application_contract_error", {}).get("missing_plus_override")
            != EXPECTED_ATTEMPT13_MISSING_PLUS_OVERRIDE
        ):
            raise RuntimeError("Attempt13 receipt does not preserve the application config failure contract.")
        plan = json.loads(expected_runtime_artifacts["plan"][0].read_text(encoding="utf-8"))
        if (
            plan.get("plan_sha256") != EXPECTED_ATTEMPT13_PLAN_IDENTITY_SHA256
            or plan.get("repair_receipt", {}).get("path")
            != str(REPAIR_R11_RECEIPT_PATH.relative_to(ROOT))
            or plan.get("repair_receipt", {}).get("sha256") != EXPECTED_R11_RECEIPT_SHA256
            or EXPECTED_ATTEMPT13_BAD_OVERRIDE not in plan.get("argv", [])
            or EXPECTED_ATTEMPT13_MISSING_PLUS_OVERRIDE in plan.get("argv", [])
        ):
            raise RuntimeError("Attempt13 immutable plan does not preserve the missing-plus override failure.")
        process_receipt = json.loads(
            expected_runtime_artifacts["process_receipt"][0].read_text(encoding="utf-8")
        )
        if (
            process_receipt.get("attempt") != 13
            or process_receipt.get("plan_sha256") != EXPECTED_ATTEMPT13_PLAN_IDENTITY_SHA256
            or process_receipt.get("repair_receipt_sha256") != EXPECTED_R11_RECEIPT_SHA256
            or process_receipt.get("application_success") is not False
            or process_receipt.get("natural_exit") is not False
            or process_receipt.get("returncode") != 1
            or process_receipt.get("summary_path") is not None
            or process_receipt.get("summary_sha256") is not None
            or process_receipt.get("metrics_path") is not None
            or process_receipt.get("metrics_sha256") is not None
        ):
            raise RuntimeError("Attempt13 process receipt does not preserve the pre-probe application failure.")
        log_text = expected_runtime_artifacts["log"][0].read_text(encoding="utf-8", errors="replace")
        if (
            f"hydra.errors.{EXPECTED_ATTEMPT13_ERROR_TYPE}" not in log_text
            or "Could not override 'env.config.max_stage_time'." not in log_text
            or f"To append to your config use {EXPECTED_ATTEMPT13_MISSING_PLUS_OVERRIDE}" not in log_text
        ):
            raise RuntimeError("Attempt13 log does not preserve the exact missing-plus Hydra error.")
        return receipt, receipt_sha256
    if attempt == 15:
        attempt14_artifact = trigger.get("attempt_receipt") if isinstance(trigger, dict) else None
        if (
            receipt_sha256 != repair_receipt_sha256
            or receipt_sha256 != EXPECTED_R13_RECEIPT_SHA256
            or receipt.get("schema_version") != EXPECTED_R13_SCHEMA
            or receipt.get("repair_revision") != EXPECTED_R13_REVISION
            or receipt.get("stale_candidate_id") != EXPECTED_STALE_CANDIDATE_ID
            or not isinstance(parent, dict)
            or parent.get("path") != str(REPAIR_R12_RECEIPT_PATH.relative_to(ROOT))
            or parent.get("sha256") != EXPECTED_R12_RECEIPT_SHA256
            or parent.get("repair_revision") != EXPECTED_R12_REVISION
            or not isinstance(trigger, dict)
            or trigger.get("attempt") != 14
            or trigger.get("root_cause") != EXPECTED_R13_ROOT_CAUSE
            or not isinstance(attempt14_artifact, dict)
            or attempt14_artifact.get("path") != str(ATTEMPT14_RECEIPT_PATH.relative_to(ROOT))
            or attempt14_artifact.get("sha256") != EXPECTED_ATTEMPT14_RECEIPT_SHA256
            or not ATTEMPT14_RECEIPT_PATH.is_file()
            or _sha256(ATTEMPT14_RECEIPT_PATH) != EXPECTED_ATTEMPT14_RECEIPT_SHA256
            or receipt.get("scope", {}).get("attempt15_prepared") is not False
            or receipt.get("scope", {}).get("attempt15_runtime_executed") is not False
        ):
            raise RuntimeError(
                "Repair R13 identity, parent R12 binding, or Attempt14 invalidation is not authorized."
            )
        attempt14_receipt = json.loads(ATTEMPT14_RECEIPT_PATH.read_text(encoding="utf-8"))
        if (
            not isinstance(attempt14_receipt, dict)
            or attempt14_receipt.get("schema_version")
            != "pull_v0_p1_push_anchor_attempt_receipt_v14"
            or attempt14_receipt.get("attempt") != 14
            or attempt14_receipt.get("status") != "PROBE_INVALID"
            or attempt14_receipt.get("probe_validity") != "PROBE_INVALID"
            or attempt14_receipt.get("scientific_verdict_consumed") is not False
            or attempt14_receipt.get("resource_stop", {}).get("triggered") is not True
        ):
            raise RuntimeError("Attempt14 invalidation does not preserve the resource-stop boundary.")
        return receipt, receipt_sha256
    if attempt == 16:
        attempt15_artifact = trigger.get("attempt_receipt") if isinstance(trigger, dict) else None
        if (
            receipt_sha256 != repair_receipt_sha256
            or receipt_sha256 != EXPECTED_R14_RECEIPT_SHA256
            or receipt.get("schema_version") != EXPECTED_R14_SCHEMA
            or receipt.get("repair_revision") != EXPECTED_R14_REVISION
            or receipt.get("stale_candidate_id") != EXPECTED_STALE_CANDIDATE_ID
            or not isinstance(parent, dict)
            or parent.get("path") != str(REPAIR_R13_RECEIPT_PATH.relative_to(ROOT))
            or parent.get("sha256") != EXPECTED_R13_RECEIPT_SHA256
            or parent.get("repair_revision") != EXPECTED_R13_REVISION
            or not isinstance(trigger, dict)
            or trigger.get("attempt") != 15
            or trigger.get("root_cause") != EXPECTED_R14_ROOT_CAUSE
            or not isinstance(attempt15_artifact, dict)
            or attempt15_artifact.get("path") != str(ATTEMPT15_RECEIPT_PATH.relative_to(ROOT))
            or attempt15_artifact.get("sha256") != EXPECTED_ATTEMPT15_RECEIPT_SHA256
            or not ATTEMPT15_RECEIPT_PATH.is_file()
            or _sha256(ATTEMPT15_RECEIPT_PATH) != EXPECTED_ATTEMPT15_RECEIPT_SHA256
            or receipt.get("scope", {}).get("attempt16_prepared") is not False
            or receipt.get("scope", {}).get("attempt16_runtime_executed") is not False
        ):
            raise RuntimeError(
                "Repair R14 identity, parent R13 binding, or Attempt15 transport failure is not authorized."
            )
        attempt15_receipt = json.loads(ATTEMPT15_RECEIPT_PATH.read_text(encoding="utf-8"))
        evidence = attempt15_receipt.get("evidence")
        if (
            not isinstance(attempt15_receipt, dict)
            or attempt15_receipt.get("schema_version")
            != "pull_v0_p1_push_anchor_attempt_receipt_v15"
            or attempt15_receipt.get("attempt") != 15
            or attempt15_receipt.get("status") != "PROBE_INVALID"
            or attempt15_receipt.get("probe_validity") != "PROBE_INVALID"
            or attempt15_receipt.get("runtime_validation") != "INVALIDATED_BEFORE_APPLAUNCHER"
            or attempt15_receipt.get("pull_mechanism_verdict") != "NOT_ASSESSED"
            or attempt15_receipt.get("scientific_verdict_consumed") is not False
            or attempt15_receipt.get("application_success") is not False
            or attempt15_receipt.get("natural_exit") is not False
            or attempt15_receipt.get("returncode") != 2
            or not isinstance(evidence, dict)
            or evidence.get("plan", {}).get("sha256") != EXPECTED_ATTEMPT15_PLAN_SHA256
            or evidence.get("plan", {}).get("plan_sha256") != EXPECTED_ATTEMPT15_PLAN_IDENTITY_SHA256
            or evidence.get("process_receipt", {}).get("sha256") != EXPECTED_ATTEMPT15_PROCESS_SHA256
            or evidence.get("stdout", {}).get("sha256") != EXPECTED_ATTEMPT15_STDOUT_SHA256
            or evidence.get("summary") is not None
            or evidence.get("metrics") is not None
            or attempt15_receipt.get("application_contract_error", {}).get("root_cause")
            != EXPECTED_R14_ROOT_CAUSE
            or attempt15_receipt.get("application_contract_error", {}).get("unrecognized_arguments")
            != [
                "--kit_args",
                SINGLE_GPU_KIT_ARGS,
            ]
        ):
            raise RuntimeError("Attempt15 Hydra transport failure evidence is not preserved exactly.")
        return receipt, receipt_sha256
    if attempt == 17:
        parent = receipt.get("parent_receipt")
        authority = receipt.get("authority")
        trigger = receipt.get("trigger")
        scope = receipt.get("scope")
        amendments = receipt.get("amendments")
        contract = receipt.get("attempt17_preparation_contract")

        def _artifact_matches(value: object, relative_path: str, expected_sha256: str) -> bool:
            return (
                isinstance(value, dict)
                and value.get("path") == relative_path
                and value.get("sha256") == expected_sha256
                and (ROOT / relative_path).is_file()
                and _sha256(ROOT / relative_path) == expected_sha256
            )

        attempt16_trigger = trigger.get("attempt16") if isinstance(trigger, dict) else None
        footprint_artifact = (
            trigger.get("one_time_vulkan_footprint_receipt") if isinstance(trigger, dict) else None
        )
        infra_artifact = (
            trigger.get("infra_reclassification_receipt") if isinstance(trigger, dict) else None
        )
        if (
            receipt_sha256 != repair_receipt_sha256
            or receipt_sha256 != EXPECTED_GPU_LEASE_AMENDMENT_SHA256
            or receipt.get("schema_version") != EXPECTED_GPU_LEASE_AMENDMENT_SCHEMA
            or receipt.get("amendment_revision") != EXPECTED_GPU_LEASE_AMENDMENT_REVISION
            or receipt.get("repair_revision") != EXPECTED_GPU_LEASE_AMENDMENT_REVISION
            or receipt.get("status") != "APPROVED_FOR_ATTEMPT17_PREPARATION_ONLY"
            or receipt.get("runtime_validation") != "NOT_RUN"
            or receipt.get("stale_candidate_id") != EXPECTED_STALE_CANDIDATE_ID
            or not isinstance(authority, dict)
            or authority.get("path") != EXPECTED_A4_A6_AUTHORITY_PATH
            or authority.get("sha256") != EXPECTED_A4_A6_AUTHORITY_SHA256
            or not isinstance(parent, dict)
            or parent.get("path") != str(REPAIR_R14_RECEIPT_PATH.relative_to(ROOT))
            or parent.get("sha256") != EXPECTED_R14_RECEIPT_SHA256
            or parent.get("repair_revision") != EXPECTED_R14_REVISION
            or not isinstance(amendments, dict)
            or amendments.get("amendment4_compute_authorized_physical_devices") != [2, 3]
            or amendments.get("amendment4_selected_physical_device") != 2
            or amendments.get("amendment4_revoked_physical_devices") != [4, 5, 6]
            or amendments.get("amendment5_incidental_vulkan_enumeration_authorized_on_visible_devices")
            is not True
            or amendments.get("amendment5_no_compute_on_non_leased_devices") is not True
            or amendments.get("amendment5_container_isolation_authorized") is not False
            or amendments.get("amendment5_container_isolation_required") is not False
            or amendments.get("amendment6_attempt15_infra_id")
            != "INFRA_001_HYDRA_KIT_ARGS_TRANSPORT"
            or amendments.get("amendment6_attempt16_infra_id")
            != "INFRA_002_VULKAN_ENUMERATION_AUTHORIZATION"
            or amendments.get("amendment6_next_scientific_attempt") != 17
            or not isinstance(attempt16_trigger, dict)
            or not _artifact_matches(
                attempt16_trigger.get("receipt"),
                str(ATTEMPT16_RECEIPT_PATH.relative_to(ROOT)),
                EXPECTED_ATTEMPT16_RECEIPT_SHA256,
            )
            or not _artifact_matches(
                attempt16_trigger.get("plan"),
                str(_attempt_plan_path(16).relative_to(ROOT)),
                EXPECTED_ATTEMPT16_PLAN_SHA256,
            )
            or not _artifact_matches(
                attempt16_trigger.get("stdout"),
                str((ROOT / "logs_eval/a2_piper_pull_v0/p1_push_anchor/attempt16/stdout_stderr.log").relative_to(ROOT)),
                EXPECTED_ATTEMPT16_STDOUT_SHA256,
            )
            or not _artifact_matches(
                attempt16_trigger.get("kit_log"),
                "/home/baoquanc/anaconda3/envs/isaaclab/lib/python3.11/site-packages/isaacsim/kit/logs/Kit/Isaac-Sim/5.1/kit_20260804_050202.log",
                EXPECTED_ATTEMPT16_KIT_LOG_SHA256,
            )
            or not _artifact_matches(
                footprint_artifact,
                str((EVIDENCE_ROOT / "PULL_V0_VULKAN_ENUMERATION_CONTEXT_RECEIPT.json").relative_to(ROOT)),
                EXPECTED_VULKAN_RECEIPT_SHA256,
            )
            or not _artifact_matches(
                infra_artifact,
                str((EVIDENCE_ROOT / "PULL_V0_P1_INFRA_RECLASSIFICATION_RECEIPT.json").relative_to(ROOT)),
                EXPECTED_INFRA_RECLASSIFICATION_RECEIPT_SHA256,
            )
            or not isinstance(scope, dict)
            or scope.get("r14_parent_immutable") is not True
            or scope.get("attempt15_and_16_receipts_preserved") is not True
            or scope.get("attempt15_and_16_anchor_attempts_consumed") is not False
            or scope.get("attempt17_prepared") is not False
            or scope.get("attempt17_runtime_executed") is not False
            or scope.get("product_mechanics_changed") is not False
            or scope.get("fixture_changed") is not False
            or scope.get("thresholds_or_timeouts_changed") is not False
            or scope.get("p1_p2_gates_changed") is not False
            or not isinstance(contract, dict)
            or contract.get("authorized_compute_physical_devices") != [2, 3]
            or contract.get("selected_physical_device") != 2
            or contract.get("unauthorized_compute_physical_devices") != [0, 1, 4, 5, 6, 7]
            or contract.get("cuda_device") != "cuda:2"
            or contract.get("cuda_visible_devices") != "UNSET"
            or contract.get("renderer_multi_gpu_enabled") is not False
            or contract.get("renderer_multi_gpu_auto_enable") is not False
            or contract.get("renderer_multi_gpu_max_gpu_count") != 1
            or contract.get("hydra_override") != PULL_V0_RENDERER_SINGLE_GPU_OVERRIDE
            or contract.get("incidental_vulkan_contexts_authorized_on_all_visible_devices") is not True
            or contract.get("no_compute_on_non_leased_devices") is not True
            or contract.get("container_isolation_authorized") is not False
            or contract.get("container_isolation_required") is not False
            or contract.get("per_run_launch_occupancy_receipt_required") is not True
            or contract.get("steady_state_footprint_receipt_required") is not True
            or contract.get("infrastructure_to_anchor_transition") != "first_simulation_step"
            or contract.get("anchor_verdict_required_after_transition") is not True
        ):
            raise RuntimeError(
                "A4_A6 amendment identity, Attempt16 evidence, or Attempt17 GPU lease contract is not authorized."
            )
        return receipt, receipt_sha256
    if attempt == 18:
        parent = receipt.get("parent_receipt")
        trigger = receipt.get("trigger")
        scope = receipt.get("scope")
        source_repair = receipt.get("source_repair")
        attempt17_artifact = trigger.get("attempt_receipt") if isinstance(trigger, dict) else None
        if (
            receipt_sha256 != repair_receipt_sha256
            or receipt_sha256 != EXPECTED_R15_RECEIPT_SHA256
            or receipt.get("schema_version") != EXPECTED_R15_SCHEMA
            or receipt.get("repair_revision") != EXPECTED_R15_REVISION
            or receipt.get("status") != "APPROVED_FOR_ATTEMPT18_PREPARATION_ONLY"
            or receipt.get("runtime_validation") != "NOT_RUN"
            or receipt.get("stale_candidate_id") != EXPECTED_STALE_CANDIDATE_ID
            or not isinstance(parent, dict)
            or parent.get("path") != str(GPU_LEASE_AMENDMENT_RECEIPT_PATH.relative_to(ROOT))
            or parent.get("sha256") != EXPECTED_GPU_LEASE_AMENDMENT_SHA256
            or parent.get("repair_revision") != EXPECTED_GPU_LEASE_AMENDMENT_REVISION
            or not isinstance(trigger, dict)
            or trigger.get("attempt") != 17
            or trigger.get("root_cause") != "CENTER_CLOSE_HANDOFF_OUTSIDE_RELIEF_BUDGET"
            or not isinstance(attempt17_artifact, dict)
            or attempt17_artifact.get("path") != str(ATTEMPT17_RECEIPT_PATH.relative_to(ROOT))
            or attempt17_artifact.get("sha256") != EXPECTED_ATTEMPT17_RECEIPT_SHA256
            or not ATTEMPT17_RECEIPT_PATH.is_file()
            or _sha256(ATTEMPT17_RECEIPT_PATH) != EXPECTED_ATTEMPT17_RECEIPT_SHA256
            or not isinstance(scope, dict)
            or scope.get("attempt17_parent_immutable") is not True
            or scope.get("attempt17_scientific_verdict_consumed") is not True
            or scope.get("attempt18_prepared") is not False
            or scope.get("attempt18_runtime_executed") is not False
            or scope.get("attempt18_artifacts_created") is not False
            or scope.get("fixture_changed") is not False
            or scope.get("thresholds_or_timeouts_changed") is not False
            or scope.get("p1_p2_gates_changed") is not False
            or scope.get("pull_verdict") != "NOT_ASSESSED"
            or not isinstance(source_repair, dict)
            or source_repair.get("reachability_helper") != "a2_pull_p1_center_handoff_reachable_mask"
            or source_repair.get("existing_budget_config_key") != "a2_hold_oracle_base_relief_max_displacement_m"
            or source_repair.get("arm_dls_pending_handoff") is not False
            or source_repair.get("stage0_override_pending_handoff") is not False
            or source_repair.get("new_threshold_or_gate") is not False
            or source_repair.get("low_level_usd_api") is not False
        ):
            raise RuntimeError("Repair R15 identity, Attempt17 ancestry, or no-runtime scope is not authorized.")
        if not allow_attempt18_runtime:
            for relative in (
                "scriptsFORhuman/pull_v0/PULL_V0_P1_PUSH_ANCHOR_ATTEMPT18_RECEIPT.json",
                "scriptsFORhuman/pull_v0/PULL_V0_P1_PUSH_ANCHOR_ATTEMPT18_PLAN.json",
                "logs_eval/a2_piper_pull_v0/p1_push_anchor/attempt18/process_receipt.json",
                "logs_eval/a2_piper_pull_v0/p1_push_anchor/attempt18/stdout_stderr.log",
            ):
                if (ROOT / relative).exists():
                    raise RuntimeError(f"R15 no-runtime scope was violated by Attempt18 artifact: {relative}")
        else:
            for artifact_path in (
                ATTEMPT18_RECEIPT_PATH,
                _attempt_output_root(18) / "process_receipt.json",
                _attempt_output_root(18) / "stdout_stderr.log",
                _attempt_output_root(18) / "eval" / "a2_hold_oracle_summary.json",
                _attempt_output_root(18) / "eval" / "metrics_eval.json",
                ATTEMPT18_RETRY1_STEADY_STATE_FOOTPRINT_PATH,
            ):
                if artifact_path.exists():
                    label = (
                        str(artifact_path.relative_to(ROOT))
                        if artifact_path.is_relative_to(ROOT)
                        else str(artifact_path)
                    )
                    raise RuntimeError(
                        "Attempt18 runtime re-entry found pre-existing scientific artifact: "
                        f"{label}"
                    )
        return receipt, receipt_sha256
    raise RuntimeError(f"Unsupported repair binding attempt: {attempt}; Repair R15 is sealed to attempt 18.")


def _resolve_selected_repair_receipt_path(path: Path | None, *, attempt: int) -> Path:
    """Return the exact path validated and serialized into a preparation plan."""
    if path is None:
        if attempt != 3:
            raise RuntimeError(
                f"Attempt {attempt} requires an explicit canonical repair receipt path."
            )
        selected = REPAIR_R1_RECEIPT_PATH
    else:
        selected = path
    if not selected.is_absolute():
        selected = ROOT / selected
    return selected.resolve()


def _repair_receipt_plan_entry(
    selected_path: Path, *, repair_receipt: Mapping[str, Any], repair_receipt_sha256: str
) -> dict[str, Any]:
    """Serialize the already validated repair identity without a second attempt chain."""
    entry: dict[str, Any] = {
        "path": str(selected_path.relative_to(ROOT)),
        "sha256": repair_receipt_sha256,
        "expected_sha256": repair_receipt_sha256,
        "revision": repair_receipt["repair_revision"],
        "stale_candidate_id": repair_receipt["stale_candidate_id"],
    }
    if repair_receipt["repair_revision"] != "R1":
        parent = repair_receipt.get("parent_receipt")
        if not isinstance(parent, Mapping) or not isinstance(parent.get("sha256"), str):
            raise RuntimeError(
                f"Repair {repair_receipt['repair_revision']} lacks a parent receipt hash for plan serialization."
            )
        entry["parent_receipt_sha256"] = parent["sha256"]
    return entry


def _plan_identity(plan: dict) -> dict:
    return {
        key: value
        for key, value in plan.items()
        if key not in {"generated_at_hkt", "plan_sha256"}
    }


def _assert_existing_plan_matches(existing: dict, expected: dict, plan_path: Path) -> dict:
    if not isinstance(existing, dict):
        raise RuntimeError(f"Existing plan is not a JSON object: {plan_path}")
    existing_identity = _plan_identity(existing)
    expected_identity = _plan_identity(expected)
    if existing_identity != expected_identity:
        raise RuntimeError(
            f"Existing plan semantic identity differs; refusing reuse: {plan_path}"
        )
    existing_plan_sha256 = existing.get("plan_sha256")
    if (
        existing_plan_sha256 != expected.get("plan_sha256")
        or _canonical_sha256(existing_identity) != existing_plan_sha256
    ):
        raise RuntimeError(
            f"Existing plan identity hash differs; refusing reuse: {plan_path}"
        )
    return existing


def _validate_attempt18_retry1_launch_occupancy(
    plan: Mapping[str, Any], occupancy_path: Path | None = None
) -> dict[str, Any]:
    """Validate the fresh retry1 pre-launch occupancy without probing host processes."""
    expected_path = ATTEMPT18_RETRY1_LAUNCH_OCCUPANCY_PATH
    selected_path = expected_path if occupancy_path is None else occupancy_path
    if not selected_path.is_absolute():
        selected_path = ROOT / selected_path
    if selected_path.resolve() != expected_path.resolve():
        expected_label = (
            str(expected_path.relative_to(ROOT))
            if expected_path.is_relative_to(ROOT)
            else str(expected_path)
        )
        raise RuntimeError(
            "Attempt18 retry1 launch occupancy must use the canonical path: "
            f"expected={expected_label}, actual={selected_path}."
        )
    if not selected_path.is_file() or selected_path.is_symlink():
        raise RuntimeError(
            f"Attempt18 retry1 launch occupancy is missing or not a regular file: {selected_path}"
        )
    try:
        occupancy = json.loads(selected_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(
            f"Attempt18 retry1 launch occupancy is not readable JSON: {selected_path}"
        ) from exc
    if not isinstance(occupancy, dict):
        raise RuntimeError("Attempt18 retry1 launch occupancy must be a JSON object.")
    if (
        occupancy.get("schema_version") != "pull_v0_p1_attempt18_launch_occupancy_v1"
        or occupancy.get("attempt") != 18
        or occupancy.get("status") != "PASS"
        or occupancy.get("phase") != "IMMEDIATELY_BEFORE_LAUNCH"
        or not isinstance(occupancy.get("captured_at_hkt"), str)
        or not occupancy["captured_at_hkt"].strip()
        or not isinstance(occupancy.get("observation"), str)
        or not occupancy["observation"].strip()
    ):
        raise RuntimeError(
            "Attempt18 retry1 launch occupancy schema, attempt, status, or phase is invalid."
        )
    plan_path = _attempt_plan_path(18)
    if not plan_path.is_file() or plan_path.is_symlink():
        raise RuntimeError(f"Attempt18 plan is missing or not a regular file: {plan_path}")
    plan_binding = occupancy.get("plan")
    expected_plan_path = str(plan_path.relative_to(ROOT))
    expected_plan_sha256 = _sha256(plan_path)
    expected_plan_identity = plan.get("plan_sha256")
    if (
        not isinstance(plan_binding, Mapping)
        or plan_binding.get("path") != expected_plan_path
        or plan_binding.get("sha256") != expected_plan_sha256
        or plan_binding.get("plan_sha256") != expected_plan_identity
    ):
        raise RuntimeError(
            "Attempt18 retry1 launch occupancy does not bind the exact prepared plan file and identity."
        )
    if (
        occupancy.get("selected_compute_physical_device") != 2
        or occupancy.get("authorized_compute_physical_devices") != [2, 3]
        or occupancy.get("unauthorized_compute_physical_devices") != [0, 1, 4, 5, 6, 7]
    ):
        raise RuntimeError("Attempt18 retry1 launch occupancy violates the GPU2/[2, 3] lease contract.")
    if (
        occupancy.get("runtime_started") is not False
        or occupancy.get("scientific_attempt_started") is not False
        or occupancy.get("cuda_visible_devices") != "UNSET"
        or occupancy.get("container_isolation_used") is not False
        or occupancy.get("incidental_vulkan_enumeration_contexts_authorized") is not True
    ):
        raise RuntimeError(
            "Attempt18 retry1 launch occupancy crosses the runtime boundary or changes the visibility/isolation contract."
        )

    def finite_nonnegative(value: Any, label: str) -> float:
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(float(value))
            or float(value) < 0.0
        ):
            raise RuntimeError(f"Attempt18 retry1 occupancy {label} must be finite and non-negative.")
        return float(value)

    tenant_records = occupancy.get("non_leased_tenant_occupancy_at_launch")
    if not isinstance(tenant_records, list):
        raise RuntimeError(
            "Attempt18 retry1 launch occupancy must explicitly record non-leased tenant attribution."
        )
    tenant_by_device: dict[int, dict[str, Any]] = {}
    for record_index, raw_record in enumerate(tenant_records):
        if not isinstance(raw_record, Mapping):
            raise RuntimeError(
                f"Attempt18 retry1 tenant attribution[{record_index}] must be an object."
            )
        device_index = raw_record.get("device_index")
        if (
            isinstance(device_index, bool)
            or not isinstance(device_index, int)
            or device_index in tenant_by_device
            or device_index not in {0, 1, 4, 5, 6, 7}
        ):
            raise RuntimeError(
                "Attempt18 retry1 tenant attribution must use unique non-leased device indices."
            )
        if raw_record.get("attribution") != "OTHER_TENANT":
            raise RuntimeError(
                "Attempt18 retry1 tenant attribution must explicitly be OTHER_TENANT."
            )
        utilization = finite_nonnegative(
            raw_record.get("utilization_gpu_percent"),
            f"tenant attribution[{record_index}].utilization_gpu_percent",
        )
        if utilization > 100.0:
            raise RuntimeError(
                f"Attempt18 retry1 tenant attribution[{record_index}] utilization exceeds 100%."
            )
        processes = raw_record.get("processes")
        if not isinstance(processes, list) or not processes:
            raise RuntimeError(
                "Attempt18 retry1 OTHER_TENANT attribution requires at least one process record."
            )
        normalized_processes: list[dict[str, Any]] = []
        seen_pids: set[int] = set()
        for process_index, raw_process in enumerate(processes):
            if not isinstance(raw_process, Mapping):
                raise RuntimeError(
                    f"Attempt18 retry1 tenant process[{record_index}:{process_index}] must be an object."
                )
            pid = raw_process.get("pid")
            if (
                isinstance(pid, bool)
                or not isinstance(pid, int)
                or pid <= 0
                or pid in seen_pids
            ):
                raise RuntimeError(
                    "Attempt18 retry1 tenant process records require unique positive pids."
                )
            name = raw_process.get("name")
            if not isinstance(name, str) or not name.strip():
                raise RuntimeError("Attempt18 retry1 tenant process names must be non-empty strings.")
            memory_used_mib = finite_nonnegative(
                raw_process.get("memory_used_mib"),
                f"tenant process[{record_index}:{process_index}].memory_used_mib",
            )
            seen_pids.add(pid)
            normalized_processes.append(
                {"pid": pid, "name": name, "memory_used_mib": memory_used_mib}
            )
        tenant_by_device[device_index] = {
            "utilization_gpu_percent": utilization,
            "processes": normalized_processes,
        }

    devices = occupancy.get("per_device")
    if not isinstance(devices, list) or len(devices) != 8:
        raise RuntimeError(
            "Attempt18 retry1 launch occupancy must contain exactly one device record for physical GPUs 0-7."
        )
    by_index: dict[int, Mapping[str, Any]] = {}
    for record_index, raw_device in enumerate(devices):
        if not isinstance(raw_device, Mapping):
            raise RuntimeError(f"Attempt18 retry1 device[{record_index}] must be an object.")
        device_index = raw_device.get("index")
        if (
            isinstance(device_index, bool)
            or not isinstance(device_index, int)
            or device_index in by_index
            or device_index < 0
            or device_index > 7
        ):
            raise RuntimeError("Attempt18 retry1 device records must cover unique physical indices 0-7.")
        by_index[device_index] = raw_device
        if raw_device.get("leased") is not (device_index in {2, 3}):
            raise RuntimeError(
                f"Attempt18 retry1 GPU{device_index} leased flag violates the GPU2/[2, 3] contract."
            )
        if "uuid" in raw_device and (
            not isinstance(raw_device["uuid"], str) or not raw_device["uuid"].strip()
        ):
            raise RuntimeError(f"Attempt18 retry1 GPU{device_index} UUID is invalid.")
        utilization = finite_nonnegative(
            raw_device.get("utilization_gpu_percent"),
            f"GPU{device_index}.utilization_gpu_percent",
        )
        if utilization > 100.0:
            raise RuntimeError(f"Attempt18 retry1 GPU{device_index} utilization exceeds 100%.")
        finite_nonnegative(raw_device.get("memory_used_mib"), f"GPU{device_index}.memory_used_mib")
        processes = raw_device.get("compute_processes")
        if not isinstance(processes, list):
            raise RuntimeError(f"Attempt18 retry1 GPU{device_index} compute_processes must be a list.")
        if device_index in {2, 3}:
            if utilization != 0.0 or processes:
                raise RuntimeError(
                    f"Attempt18 retry1 leased GPU{device_index} must be idle immediately before launch."
                )
            if device_index in tenant_by_device:
                raise RuntimeError(
                    f"Attempt18 retry1 tenant attribution incorrectly names leased GPU{device_index}."
                )
        else:
            tenant = tenant_by_device.get(device_index)
            if tenant is None:
                if utilization != 0.0 or processes:
                    raise RuntimeError(
                        f"Attempt18 retry1 GPU{device_index} has unrecorded non-leased occupancy."
                    )
            elif (
                utilization != tenant["utilization_gpu_percent"]
                or processes != tenant["processes"]
            ):
                raise RuntimeError(
                    f"Attempt18 retry1 OTHER_TENANT attribution does not match GPU{device_index}."
                )
    if set(by_index) != set(range(8)):
        raise RuntimeError("Attempt18 retry1 device records must cover physical GPUs 0-7 exactly.")
    return occupancy


def _launch_occupancy_path(attempt: int) -> Path:
    paths = {
        19: ATTEMPT19_LAUNCH_OCCUPANCY_PATH,
        20: ATTEMPT20_LAUNCH_OCCUPANCY_PATH,
    }
    try:
        return paths[attempt]
    except KeyError as exc:
        raise RuntimeError(f"Attempt{attempt} does not use runner-managed launch occupancy.") from exc


def _validate_attempt_launch_occupancy(
    plan: Mapping[str, Any], *, attempt: int
) -> dict[str, Any]:
    """Require fresh canonical launch evidence before subprocess launch."""
    path = _launch_occupancy_path(attempt)
    if not path.is_file() or path.is_symlink():
        raise RuntimeError(
            f"Attempt{attempt} launch occupancy is missing or not a regular non-symlink file: "
            f"{path}"
        )
    plan_path = _attempt_plan_path(attempt)
    if not plan_path.is_file() or plan_path.is_symlink():
        raise RuntimeError(f"Attempt{attempt} plan is missing or not a regular file: {plan_path}")
    evidence = attempt19_gpu_evidence._read_json(path)
    plan_artifact = {
        "path": str(plan_path.relative_to(ROOT)),
        "sha256": _sha256(plan_path),
        "plan_sha256": plan.get("plan_sha256"),
    }
    return attempt19_gpu_evidence.validate_launch_evidence(
        evidence,
        plan=plan,
        plan_artifact=plan_artifact,
        now=datetime.now(ZoneInfo("Asia/Hong_Kong")),
        require_fresh=True,
        attempt=attempt,
    )


def _validate_attempt19_launch_occupancy(plan: Mapping[str, Any]) -> dict[str, Any]:
    """Require fresh canonical Attempt19 launch evidence before subprocess launch."""
    return _validate_attempt_launch_occupancy(plan, attempt=19)


def _copy_exact(source: Path, destination: Path, expected_sha256: str) -> None:
    if not source.is_file() or source.is_symlink():
        raise RuntimeError(f"Input must be a regular non-symlink file: {source}")
    if _sha256(source) != expected_sha256:
        raise RuntimeError(f"Input hash mismatch: {source}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        if _sha256(destination) != expected_sha256:
            raise RuntimeError(f"Existing materialized input hash mismatch: {destination}")
        return
    shutil.copy2(source, destination)
    destination.chmod(0o444)


def _materialize_config(destination: Path, *, detailed_contact_capacity: int = SHARED_CONTACT_CAPACITY) -> str:
    if not SOURCE_CONFIG.is_file() or SOURCE_CONFIG.is_symlink():
        raise RuntimeError(f"Missing P0-C out config: {SOURCE_CONFIG}")
    config = yaml.safe_load(SOURCE_CONFIG.read_text(encoding="utf-8"))
    config["num_envs"] = 1
    config["seed"] = 0
    config["headless"] = True
    config["use_wandb"] = False
    env = config["env"]["config"]
    max_stage_time = _validate_pull_anchor_stage_time_contract(
        list(PULL_ANCHOR_MAX_STAGE_TIME)
    )
    if (
        isinstance(detailed_contact_capacity, bool)
        or not isinstance(detailed_contact_capacity, int)
        or detailed_contact_capacity < 1
    ):
        raise RuntimeError("Detailed contact capacity must be a positive integer.")
    env.update(
        {
            "max_episode_length_s": PULL_ANCHOR_GLOBAL_MAX_EPISODE_LENGTH_S,
            "max_stage_time": max_stage_time,
            "a2_pull_p1_central_fixture_enabled": True,
            "a2_pull_door_open_io": "out",
            "a2_pull_door_open_lr": "right",
            "a2_pull_hook_profile": "P1_PRESENT_0P050M",
            "a2_pull_friction_profile": "RESOLVED_V20_G4",
            "a2_pull_finger_profile": "V20_G4_45N_KP1300_KD32",
            "a2_pull_target_orientation_wxyz": [0.5, 0.5, 0.5, 0.5],
            "a2_pull_control_proof_min_duration_s": 0.20,
            "a2_pull_control_proof_min_retreat_m": 0.002,
            "a2_pull_control_proof_monotone_tolerance_m": 0.0005,
            "a2_pull_control_proof_min_streak_steps": 5,
            "a2_pull_control_clearance_min_m": 0.02,
            "a2_pull_threshold_mode": "report_only",
            "a2_pull_effort_provenance": "ESTIMATE_ONLY",
            "a2_door_weight_range": [80.0, 160.0],
            "a2_hold_diagnostic_contact_detail_enabled": True,
            "a2_hold_diagnostic_max_contact_data_count_per_prim": detailed_contact_capacity,
            "a2_v20_R1_plan_id": "disabled",
            "a2_v20_R1_send_curriculum_enabled": False,
            "a2_v20_R1_snapshot_guard_enabled": False,
            "a2_v20_send_latch_enabled": False,
            "a2_v20_pre_send_crossing_mode": "disabled",
            "a2_v20_telemetry_enabled": False,
            "a2_v20_traversal_economics_enabled": False,
            "a2_corridor_enabled": False,
            "a2_v20_arm_tie_enabled": False,
            "a2_v20_arm_tangent_carry_scale": 0.0,
            "a2_v20_handle_arc_tracking_scale": 0.0,
            "a2_v20_R2_evidence_enabled": False,
            "a2_v20_formal_launch": False,
        }
    )
    if env["max_episode_length_s"] != PULL_ANCHOR_GLOBAL_MAX_EPISODE_LENGTH_S:
        raise RuntimeError("Pull-anchor global max_episode_length_s must remain exactly 120.")
    if env["a2_hold_diagnostic_max_contact_data_count_per_prim"] != detailed_contact_capacity:
        raise RuntimeError("Detailed contact capacity materialization changed unexpectedly.")
    if env["a2_v20_R1_plan_id"] != "disabled":
        raise RuntimeError("Pull-anchor materialized config must keep the R1 guard disabled.")
    if env["max_stage_time"] != max_stage_time:
        raise RuntimeError("Pull-anchor max_stage_time materialization changed unexpectedly.")
    if config["robot"]["dof_effort_limit_list"][-2:] != [45.0, 45.0]:
        raise RuntimeError("P1 anchor source config does not retain 45 N finger effort")
    if [
        config["robot"]["control"]["stiffness"][key]
        for key in ("arm_j7", "arm_j8")
    ] != [1300.0, 1300.0]:
        raise RuntimeError("P1 anchor source config does not retain Kp=1300")
    if [
        config["robot"]["control"]["damping"][key]
        for key in ("arm_j7", "arm_j8")
    ] != [32.0, 32.0]:
        raise RuntimeError("P1 anchor source config does not retain Kd=32")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
    destination.chmod(0o444)
    return _sha256(destination)


def _argv(
    checkpoint: Path,
    output_root: Path,
    *,
    use_hydra_renderer_transport: bool = False,
    physical_gpu: int | None = None,
    detailed_contact_capacity: int | None = None,
) -> list[str]:
    gpu = PHYSICAL_GPU if physical_gpu is None else physical_gpu
    eval_output = output_root / "eval"
    hydra_output = output_root / "hydra"
    diagnostic_terms = "[penalty_dof_overspeed,penalty_door_panel_contact]"
    argv = [
        str(PYTHON),
        "-B",
        "-m",
        "gr00t.rl.eval_agent_trl",
        f"checkpoint={checkpoint}",
        "checkpoint_load_mode=full",
        "+auto_load_latest=false",
        "+num_envs=1",
        "+seed=0",
        "+headless=true",
        "+use_wandb=false",
    ]
    if use_hydra_renderer_transport:
        argv.append(PULL_V0_RENDERER_SINGLE_GPU_OVERRIDE)
    else:
        argv.extend(("--kit_args", SINGLE_GPU_KIT_ARGS))
    argv.extend([
        "algo.config.eval.num_eval_episodes=1",
        "+algo.config.eval.eval_num_envs_episodes=true",
        "+algo.config.eval.dump_to_log_metrics=true",
        "algo.config.eval.save_goal_reached_only=false",
        "algo.config.eval.save_trajectories=false",
        "algo.config.eval.save_videos=false",
        "algo.config.eval.num_save_episodes=1",
        "algo.config.eval.a2_diagnostic_trace_enabled=true",
        f"algo.config.eval.a2_diagnostic_reward_terms={diagnostic_terms}",
        "algo.config.eval.a2_forced_gripper_close_enabled=false",
        "algo.config.eval.a2_hold_oracle_enabled=true",
        "algo.config.eval.a2_pull_p1_probe_enabled=true",
        "algo.config.eval.a2_pull_p1_probe_mode=push_anchor",
        "algo.config.eval.a2_pull_p1_anchor_acquisition_enabled=true",
        "algo.config.eval.a2_pull_p1_proof_offset_m=0.006",
        "algo.config.eval.a2_pull_p1_proof_ramp_steps=30",
        "algo.config.eval.a2_pull_p1_proof_hold_steps=10",
        "algo.config.eval.a2_pull_p1_body_contact_threshold_n=1.0",
        "algo.config.eval.a2_pull_p1_stage0_staging_speed_mps=0.15",
        "algo.config.eval.a2_pull_p1_stage0_settle_steps=5",
        "algo.config.eval.a2_pull_p1_stage0_timeout_steps=360",
        "algo.config.eval.a2_pull_p1_reset_contact_qualification_steps=3",
        "algo.config.eval.a2_pull_p1_reset_contact_qualification_streak_steps=2",
        "algo.config.eval.a2_pull_p1_reset_upright_tolerance_rad=0.35",
        "algo.config.eval.a2_pull_p1_reset_gripper_action=-1.0",
        "+env.config.max_stage_time=[400,100,100,100,100,200]",
        "algo.config.eval.a2_v20_arc_probe_enabled=false",
        "algo.config.eval.a2_v20_arc_probe_mode=F1",
        "algo.config.eval.a2_v20_arc_probe_target_hinge_rad=0.25",
        "algo.config.eval.a2_v20_arc_probe_terminal_window_steps=10",
        "algo.config.eval.a2_v20_arc_probe_timeout_steps=600",
        "algo.config.eval.a2_eval_v20_strict_telemetry=false",
        "+simulator.config.render_results=false",
        "+simulator.config.cameras.enable_cameras=false",
        f"eval_output_dir={eval_output}",
        f"eval_log_dir={hydra_output}",
        f"env.config.save_rendering_dir={output_root / 'renderings'}",
        f"+device=cuda:{gpu}",
        f"hydra.run.dir={hydra_output}",
    ])
    if detailed_contact_capacity is not None:
        if (
            isinstance(detailed_contact_capacity, bool)
            or not isinstance(detailed_contact_capacity, int)
            or detailed_contact_capacity < 1
        ):
            raise ValueError("Detailed contact capacity override must be a positive integer.")
        argv.append(
            f"+env.config.a2_hold_diagnostic_max_contact_data_count_per_prim={detailed_contact_capacity}"
        )
    return argv


def _attempt20_preparation_artifact_paths() -> tuple[Path, ...]:
    output_root = _attempt_output_root(20)
    return (
        _attempt_plan_path(20),
        ATTEMPT20_RECEIPT_PATH,
        ATTEMPT20_LAUNCH_OCCUPANCY_PATH,
        ATTEMPT20_STEADY_STATE_FOOTPRINT_PATH,
        output_root,
    )


def _assert_attempt20_preparation_namespace_clear() -> None:
    existing = [path for path in _attempt20_preparation_artifact_paths() if path.exists()]
    if existing:
        raise RuntimeError(
            "Attempt20 preparation refuses to reuse or overwrite canonical artifacts: "
            f"{[str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path) for path in existing]}"
        )


def validate_preparation(
    attempt: int,
    repair_receipt_path: Path | None = None,
    repair_receipt_sha256: str | None = None,
) -> dict[str, Any]:
    """Validate the Attempt20 R17 preparation gate without writing artifacts."""
    attempt = _require_post_r1_attempt(attempt)
    if attempt != 20:
        raise RuntimeError("Dry-run preparation validation is only defined for Attempt20/R17.")
    if repair_receipt_path is None or repair_receipt_sha256 is None:
        raise RuntimeError("Attempt20 validate-only requires its R17 receipt path and SHA256.")
    source_freeze = json.loads(SOURCE_FREEZE_PATH.read_text(encoding="utf-8"))
    if source_freeze["base_commit"] != EXPECTED_BASE_SHA:
        raise RuntimeError("Source-freeze base SHA changed")
    frozen = source_freeze["warm_checkpoint"]
    if frozen["sha256"] != EXPECTED_CHECKPOINT_SHA256:
        raise RuntimeError("Source-freeze warm checkpoint hash changed")
    selected_repair_receipt_path = _resolve_selected_repair_receipt_path(
        repair_receipt_path, attempt=attempt
    )
    repair_receipt, validated_sha256 = _read_repair_receipt(
        selected_repair_receipt_path,
        attempt=attempt,
        repair_receipt_sha256=repair_receipt_sha256,
    )
    _assert_attempt20_preparation_namespace_clear()
    return {
        "schema_version": "pull_v0_p1_push_anchor_preparation_validation_v1",
        "status": "VALIDATED_NO_ARTIFACTS_CREATED",
        "attempt": attempt,
        "repair_receipt": _repair_receipt_plan_entry(
            selected_repair_receipt_path,
            repair_receipt=repair_receipt,
            repair_receipt_sha256=validated_sha256,
        ),
        "plan_path": str(_attempt_plan_path(attempt).relative_to(ROOT)),
        "output_root": str(_attempt_output_root(attempt).relative_to(ROOT)),
        "canonical_artifacts_absent": [
            str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path)
            for path in _attempt20_preparation_artifact_paths()
        ],
        "writes_performed": False,
    }


def prepare(
    attempt: int,
    repair_receipt_path: Path | None = None,
    repair_receipt_sha256: str | None = None,
    *,
    allow_existing_plan: bool = False,
) -> dict:
    attempt = _require_post_r1_attempt(attempt)
    if attempt in (18, 19, 20):
        if repair_receipt_path is None or repair_receipt_sha256 is None:
            raise RuntimeError(
                f"Attempt{attempt} requires its explicit repair receipt path and SHA256."
            )
    if PHYSICAL_GPU not in AUTHORIZED_GPUS:
        raise RuntimeError("Selected GPU is outside the user-authorized GPU2-3 lease")
    source_freeze = json.loads(SOURCE_FREEZE_PATH.read_text(encoding="utf-8"))
    selected_repair_receipt_path = _resolve_selected_repair_receipt_path(
        repair_receipt_path, attempt=attempt
    )
    repair_receipt, repair_receipt_sha256 = _read_repair_receipt(
        selected_repair_receipt_path,
        attempt=attempt,
        repair_receipt_sha256=repair_receipt_sha256,
        allow_attempt18_runtime=allow_existing_plan and attempt == 18,
    )
    repair_receipt_plan_entry = _repair_receipt_plan_entry(
        selected_repair_receipt_path,
        repair_receipt=repair_receipt,
        repair_receipt_sha256=repair_receipt_sha256,
    )
    if source_freeze["base_commit"] != EXPECTED_BASE_SHA:
        raise RuntimeError("Source-freeze base SHA changed")
    frozen = source_freeze["warm_checkpoint"]
    if frozen["sha256"] != EXPECTED_CHECKPOINT_SHA256:
        raise RuntimeError("Source-freeze warm checkpoint hash changed")
    if attempt == 20 and not allow_existing_plan:
        _assert_attempt20_preparation_namespace_clear()
    checkpoint_source = Path(frozen["source_path_read_only"])
    output_root = _attempt_output_root(attempt)
    input_root = output_root / "input"
    checkpoint = input_root / "model_step_002500.pt"
    config_path = input_root / "config.yaml"
    _copy_exact(checkpoint_source, checkpoint, EXPECTED_CHECKPOINT_SHA256)
    detailed_contact_capacity = (
        ATTEMPT19_CONTACT_CAPACITY if attempt >= 19 else SHARED_CONTACT_CAPACITY
    )
    if config_path.exists():
        config_sha256 = _sha256(config_path)
        if attempt >= 19:
            existing_config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
            existing_capacity = existing_config["env"]["config"].get(
                "a2_hold_diagnostic_max_contact_data_count_per_prim"
            )
            if existing_capacity != detailed_contact_capacity:
                raise RuntimeError(
                    f"Attempt{attempt} existing materialized config does not bind detailed contact capacity 64."
                )
    else:
        config_sha256 = _materialize_config(
            config_path, detailed_contact_capacity=detailed_contact_capacity
        )
    use_hydra_renderer_transport = attempt >= 16
    argv = _argv(
        checkpoint,
        output_root,
        use_hydra_renderer_transport=use_hydra_renderer_transport,
        physical_gpu=PHYSICAL_GPU,
        detailed_contact_capacity=(
            detailed_contact_capacity if attempt >= 19 else None
        ),
    )
    env_contract = {
        "ACCELERATE_TORCH_DEVICE": f"cuda:{PHYSICAL_GPU}",
        "WANDB_MODE": "offline",
        "HYDRA_FULL_ERROR": "1",
        "PYTHONUNBUFFERED": "1",
        "PYTHONPATH": str(ROOT),
        "CUDA_VISIBLE_DEVICES": "UNSET",
    }
    plan = {
        "schema_version": "pull_v0_p1_push_anchor_plan_v1",
        "generated_at_hkt": _hkt_now(),
        "status": "READY",
        "attempt": attempt,
        "implementation_repair_used": attempt >= 2,
        "base_sha": EXPECTED_BASE_SHA,
        "repair_receipt": repair_receipt_plan_entry,
        "checkpoint": {
            "path": str(checkpoint.relative_to(ROOT)),
            "sha256": _sha256(checkpoint),
            "source_path_read_only": str(checkpoint_source),
        },
        "resolved_config": {
            "path": str(config_path.relative_to(ROOT)),
            "sha256": config_sha256,
            "source_path": str(SOURCE_CONFIG.relative_to(ROOT)),
        },
        "fixture": FIXTURE,
        "host_stage_time_contract": {
            "max_stage_time_steps": list(PULL_ANCHOR_MAX_STAGE_TIME),
            "global_max_episode_length_s": PULL_ANCHOR_GLOBAL_MAX_EPISODE_LENGTH_S,
            "reset_qualification_steps": PULL_ANCHOR_RESET_QUALIFICATION_STEPS,
            "local_stage0_timeout_steps": PULL_ANCHOR_LOCAL_STAGE0_TIMEOUT_STEPS,
            "host_stage0_budget_exceeds_reset_plus_local_watchdog": True,
        },
        "mass_range_authority": {
            "path": "scriptsFORhuman/pull_v0/source_freeze/v20_G4_resolved_config.yaml",
            "resolved_range_kg": [80.0, 160.0],
            "selected_midpoint_kg": 120.0,
            "repo_default_range_kg": [80.0, 120.0],
            "repo_default_not_used_reason": (
                "Amendment 2 binds P1 to the resolved v20 G4 range, not the repo default."
            ),
        },
        "actuator_profile": {
            "finger_effort_n": [45.0, 45.0],
            "finger_stiffness": [1300.0, 1300.0],
            "finger_damping": [32.0, 32.0],
            "provenance": "ESTIMATE_ONLY",
        },
        "script_contract": {
            "sequence": [
                "reset_signed_outside_face",
                "scripted_acquisition_without_stage2_gate",
                "stage0_predicates_reported_separately",
                "center_and_close",
                "contiguous_world_positive_x_proof",
                "handle_rotation",
                "measured_clearance_decision",
                "live_circular_arc_with_base_yield",
                "whole_body_clear_completion",
            ],
            "commandable_dofs_only": True,
            "admission_stage2_grasp_gate": False,
            "reset_target_contract": {
                "approach_side_x_sign": -1,
                "initial_yaw_rad": 0.0,
                "target_orientation_wxyz": [0.5, 0.5, 0.5, 0.5],
            },
            "stage0_predicate_fields": ["staging_band", "arm_default", "base_still"],
            "stage1_stage2_residual_fields": [
                "target_tcp_position_error_m",
                "target_tcp_orientation_error_rad",
                "bilateral_handle_contact",
            ],
            "proof_world_direction": "+X",
            "proof_offset_m": 0.006,
            "proof_ramp_steps": 30,
            "proof_hold_steps": 10,
        },
        "hard_gate": {
            "stable_bilateral_capture": True,
            "latch_release": True,
            "hinge_progress_min_rad": 0.25,
            "body_panel_contact_allowed": False,
            "measured_clearance_required_before_e5": True,
            "whole_body_mask_required_for_completion": True,
        },
        "threshold_mode": "report_only",
        "gpu_resource_lease": {
            "authorized_physical_devices": list(AUTHORIZED_GPUS),
            "selected_physical_device": PHYSICAL_GPU,
            "gpu7_compute_authorized": False,
        },
        "renderer_single_gpu_contract": {
            "kit_args": SINGLE_GPU_KIT_ARGS,
            "renderer_multi_gpu_enabled": False,
            "renderer_multi_gpu_auto_enable": False,
            "renderer_multi_gpu_max_gpu_count": 1,
            "active_gpu_index": PHYSICAL_GPU,
            "physics_cuda_device": PHYSICAL_GPU,
            "tensor_device": f"cuda:{PHYSICAL_GPU}",
            "cuda_visible_devices": "UNSET",
            "physical_gpu_lease": list(AUTHORIZED_GPUS),
            "gpu7_compute_authorized": False,
        },
        "argv": argv,
        "env": env_contract,
        "command_sha256": _canonical_sha256({"argv": argv, "env": env_contract}),
    }
    if use_hydra_renderer_transport:
        plan["renderer_single_gpu_transport"] = {
            "mode": "Hydra boolean -> args_cli.multi_gpu/kit_args",
            "hydra_config_key": "a2_pull_v0_renderer_single_gpu",
            "hydra_override": PULL_V0_RENDERER_SINGLE_GPU_OVERRIDE,
            "args_cli_multi_gpu": False,
            "args_cli_kit_args": SINGLE_GPU_KIT_ARGS,
            "raw_kit_args_in_argv": False,
        }
    if attempt == 20:
        plan["gpu_context_classification_mode"] = ATTEMPT_GPU_CONTEXT_CLASSIFICATION_MODES[20]
        plan["lifecycle_signal_contract"] = {
            "process_receipt_on_interrupt_required": True,
            "handled_signals": ["SIGINT", "SIGTERM"],
            "keyboard_interrupt_mapped_to": "SIGINT",
            "child_wait_timeout_seconds": LIFECYCLE_SIGNAL_CHILD_WAIT_TIMEOUT_SECONDS,
            "no_polling_loop": True,
        }
    if attempt >= 17:
        plan["gpu_topology_authorization"] = {
            "authorized_compute_physical_devices": [2, 3],
            "selected_physical_device": 2,
            "unauthorized_compute_physical_devices": [0, 1, 4, 5, 6, 7],
            "incidental_vulkan_contexts_authorized_on_all_visible_devices": True,
            "no_compute_on_non_leased_devices": True,
            "container_isolation_authorized": False,
            "container_isolation_required": False,
        }
        plan["infrastructure_resource_contract"] = {
            "per_run_launch_occupancy_receipt_required": True,
            "steady_state_footprint_receipt_required": True,
            "infrastructure_to_anchor_transition": "first_simulation_step",
            "anchor_verdict_required_after_transition": True,
        }
    if attempt >= 19:
        plan["detailed_contact_capacity_contract"] = {
            "config_key": "a2_hold_diagnostic_max_contact_data_count_per_prim",
            "anchor_only_detailed_contact_capacity": ATTEMPT19_CONTACT_CAPACITY,
            "shared_default_detailed_contact_capacity": SHARED_CONTACT_CAPACITY,
            "num_envs": 1,
            "sensor_body": "door_handle",
            "sensor_body_collision_shape_count": 5,
            "filter_bodies": ["arm_body7", "arm_body8"],
            "filter_collision_shape_counts": {"arm_body7": 1, "arm_body8": 1},
            "observed_total_collision_shape_count": 7,
            "candidate_sensor_filter_shape_pair_count": 10,
            "track_pose": True,
            "track_contact_points": True,
            "track_friction_forces": True,
            "threshold_or_gate": False,
            "low_level_usd_api": False,
        }
    plan["plan_sha256"] = _canonical_sha256(_plan_identity(plan))
    plan_path = _attempt_plan_path(attempt)
    if plan_path.exists():
        if not allow_existing_plan:
            raise RuntimeError(
                f"Preparation refuses to reuse an existing plan: {plan_path}"
            )
        existing = json.loads(plan_path.read_text(encoding="utf-8"))
        return _assert_existing_plan_matches(existing, plan, plan_path)
    _write_json(plan_path, plan)
    return plan


class _LifecycleSignal(RuntimeError):
    """Boundary signal that must seal a process receipt instead of losing state."""

    def __init__(self, signum: int, *, source: str) -> None:
        self.signum = signum
        self.signal_name = signal.Signals(signum).name
        self.timestamp_hkt = _hkt_now()
        self.source = source
        super().__init__(f"{self.signal_name} received by runner boundary")


def _empty_lifecycle_signal() -> dict[str, Any]:
    return {
        "received": False,
        "source": None,
        "signal_number": None,
        "signal_name": None,
        "timestamp_hkt": None,
        "timestamp_status": "NOT_APPLICABLE",
        "forwarded_to_eval_pid": False,
        "eval_reaped": True,
        "already_exited_before_forward": False,
        "sigkill_sent": False,
        "sigkill_timestamp_hkt": None,
        "child_wait_timeout_seconds": LIFECYCLE_SIGNAL_CHILD_WAIT_TIMEOUT_SECONDS,
    }


def _stop_child_after_lifecycle_signal(
    child: subprocess.Popen[bytes], signal_event: _LifecycleSignal
) -> tuple[int, dict[str, Any]]:
    polled = child.poll()
    forwarded = False
    already_exited_before_forward = polled is not None
    sigkill_sent = False
    sigkill_timestamp_hkt = None
    if polled is None:
        try:
            child.send_signal(signal_event.signum)
            forwarded = True
        except ProcessLookupError:
            already_exited_before_forward = True
        try:
            returncode = child.wait(
                timeout=LIFECYCLE_SIGNAL_CHILD_WAIT_TIMEOUT_SECONDS
            )
        except subprocess.TimeoutExpired:
            sigkill_timestamp_hkt = _hkt_now()
            child.kill()
            sigkill_sent = True
            returncode = child.wait()
    else:
        returncode = polled
    return (
        returncode,
        {
            "received": True,
            "source": signal_event.source,
            "signal_number": signal_event.signum,
            "signal_name": signal_event.signal_name,
            "timestamp_hkt": signal_event.timestamp_hkt,
            "timestamp_status": "RECORDED",
            "forwarded_to_eval_pid": forwarded,
            "eval_reaped": True,
            "already_exited_before_forward": already_exited_before_forward,
            "sigkill_sent": sigkill_sent,
            "sigkill_timestamp_hkt": sigkill_timestamp_hkt,
            "child_wait_timeout_seconds": LIFECYCLE_SIGNAL_CHILD_WAIT_TIMEOUT_SECONDS,
        },
    )


def _wait_for_popen_child(child: subprocess.Popen[bytes]) -> tuple[int, dict[str, Any]]:
    previous_handlers = {
        signal.SIGINT: signal.getsignal(signal.SIGINT),
        signal.SIGTERM: signal.getsignal(signal.SIGTERM),
    }

    def handle_signal(signum: int, frame: FrameType | None) -> None:
        del frame
        raise _LifecycleSignal(signum, source="SIGNAL_HANDLER")

    for signum in previous_handlers:
        signal.signal(signum, handle_signal)
    try:
        try:
            return child.wait(), _empty_lifecycle_signal()
        except _LifecycleSignal as signal_event:
            return _stop_child_after_lifecycle_signal(child, signal_event)
        except KeyboardInterrupt:
            signal_event = _LifecycleSignal(int(signal.SIGINT), source="KEYBOARD_INTERRUPT")
            return _stop_child_after_lifecycle_signal(child, signal_event)
    finally:
        for signum, previous_handler in previous_handlers.items():
            signal.signal(signum, previous_handler)


def _popen_run_with_lifecycle(
    plan: Mapping[str, Any], env: Mapping[str, str], stream: BinaryIO
) -> tuple[int, int, dict[str, Any]]:
    argv = plan.get("argv")
    if not isinstance(argv, list) or any(not isinstance(item, str) for item in argv):
        raise RuntimeError("Prepared plan argv must be a list of strings before launch.")
    child = subprocess.Popen(
        argv,
        cwd=ROOT,
        env=dict(env),
        stdout=stream,
        stderr=subprocess.STDOUT,
    )
    returncode, lifecycle_signal = _wait_for_popen_child(child)
    return child.pid, returncode, lifecycle_signal


def run(
    attempt: int,
    repair_receipt_path: Path | None = None,
    repair_receipt_sha256: str | None = None,
) -> int:
    attempt = _require_post_r1_attempt(attempt)
    plan = prepare(
        attempt,
        repair_receipt_path,
        repair_receipt_sha256,
        allow_existing_plan=True,
    )
    if attempt == 18:
        _validate_attempt18_retry1_launch_occupancy(plan)
    elif attempt in (19, 20):
        _validate_attempt_launch_occupancy(plan, attempt=attempt)
    output_root = _attempt_output_root(attempt)
    summary_path = output_root / "eval" / "a2_hold_oracle_summary.json"
    metrics_path = output_root / "eval" / "metrics_eval.json"
    receipt_path = output_root / "process_receipt.json"
    stdout_path = output_root / "stdout_stderr.log"
    existing_outputs = (
        stdout_path,
        summary_path,
        metrics_path,
        receipt_path,
    )
    if any(path.exists() for path in existing_outputs):
        raise RuntimeError(
            f"Refusing to reuse or overwrite existing P1 push-anchor attempt {attempt} "
            f"outputs: {[str(path.relative_to(ROOT)) for path in existing_outputs if path.exists()]}"
        )
    stdout_path.parent.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env.update(plan["env"])
    env.pop("CUDA_VISIBLE_DEVICES", None)
    started_at = _hkt_now()
    runner_pid = os.getpid()
    lifecycle_signal = _empty_lifecycle_signal()
    with stdout_path.open("wb") as stream:
        if attempt in (19, 20):
            eval_pid, returncode, lifecycle_signal = _popen_run_with_lifecycle(
                plan,
                env,
                stream,
            )
        else:
            result = subprocess.run(
                plan["argv"],
                cwd=ROOT,
                env=env,
                stdout=stream,
                stderr=subprocess.STDOUT,
                check=False,
            )
            eval_pid = None
            returncode = result.returncode
    receipt = {
        "schema_version": "pull_v0_p1_push_anchor_process_v1",
        "attempt": attempt,
        "started_at_hkt": started_at,
        "finished_at_hkt": _hkt_now(),
        "returncode": returncode,
        "natural_exit": returncode == 0,
        "required_summary_present": summary_path.is_file(),
        "required_metrics_present": metrics_path.is_file(),
        "application_success": (
            returncode == 0
            and summary_path.is_file()
            and metrics_path.is_file()
        ),
        "physical_gpu": PHYSICAL_GPU,
        "plan_path": str(_attempt_plan_path(attempt).relative_to(ROOT)),
        "plan_sha256": plan["plan_sha256"],
        "repair_receipt_path": plan["repair_receipt"]["path"],
        "repair_receipt_sha256": plan["repair_receipt"]["sha256"],
        "stale_candidate_id": plan["repair_receipt"]["stale_candidate_id"],
        "stdout_stderr_path": str(stdout_path.relative_to(ROOT)),
        "stdout_stderr_sha256": _sha256(stdout_path),
        "summary_path": (
            str(summary_path.relative_to(ROOT)) if summary_path.exists() else None
        ),
        "summary_sha256": _sha256(summary_path) if summary_path.exists() else None,
        "metrics_path": (
            str(metrics_path.relative_to(ROOT)) if metrics_path.exists() else None
        ),
        "metrics_sha256": _sha256(metrics_path) if metrics_path.exists() else None,
    }
    if attempt in (19, 20):
        receipt.update(
            {
                "runner_pid": runner_pid,
                "eval_pid": eval_pid,
                "eval_cmdline": list(plan["argv"]),
                "eval_output_dir": str((output_root / "eval").resolve()),
                "lifecycle_signal": lifecycle_signal,
            }
        )
    _write_json(receipt_path, receipt)
    if receipt["application_success"]:
        return 0
    if lifecycle_signal["received"]:
        return 128 + int(lifecycle_signal["signal_number"])
    return 1


def main() -> int:
    def positive_attempt(raw: str) -> int:
        try:
            value = int(raw)
        except ValueError as exc:
            raise argparse.ArgumentTypeError("attempt must be an integer") from exc
        if value <= 0:
            raise argparse.ArgumentTypeError("attempt must be a positive integer")
        return value

    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", type=positive_attempt, required=True)
    parser.add_argument(
        "--repair-receipt",
        type=Path,
        default=None,
        help="Canonical repair receipt path for the selected attempt; Attempt18 accepts sealed Repair R15, Attempt19 accepts sealed Repair R16, and Attempt20 accepts sealed Repair R17.",
    )
    parser.add_argument(
        "--repair-receipt-sha256",
        default=None,
        help="Explicit 64-hex SHA256 binding required for attempts >=6.",
    )
    parser.add_argument("--prepare-only", action="store_true")
    parser.add_argument("--validate-only", "--dry-run", dest="validate_only", action="store_true")
    args = parser.parse_args()
    if args.prepare_only and args.validate_only:
        parser.error("--prepare-only and --validate-only are mutually exclusive")
    if args.validate_only:
        validate_preparation(args.attempt, args.repair_receipt, args.repair_receipt_sha256)
        return 0
    if args.prepare_only:
        prepare(args.attempt, args.repair_receipt, args.repair_receipt_sha256)
        return 0
    return run(args.attempt, args.repair_receipt, args.repair_receipt_sha256)


if __name__ == "__main__":
    raise SystemExit(main())
