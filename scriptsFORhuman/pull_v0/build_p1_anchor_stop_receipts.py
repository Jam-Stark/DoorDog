#!/usr/bin/env python3
"""Build the immutable P1 fixture, anchor, and stop receipts."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
from typing import Any, Mapping

if __package__:
    from . import capture_p1_anchor_gpu_evidence as attempt19_gpu_evidence
else:
    import capture_p1_anchor_gpu_evidence as attempt19_gpu_evidence


ROOT = Path(__file__).resolve().parents[2]
EVIDENCE_ROOT = ROOT / "scriptsFORhuman" / "pull_v0"
LOG_ROOT = ROOT / "logs_eval" / "a2_piper_pull_v0" / "p1_push_anchor"
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
EXPECTED_R16_RECEIPT_SHA256 = "cf0d7107062bf8558adf4c64aaee03f91625950bdcaf2e1ee1d767883da1787e"
ATTEMPT17_RECEIPT_PATH = EVIDENCE_ROOT / "PULL_V0_P1_PUSH_ANCHOR_ATTEMPT17_RECEIPT.json"
ATTEMPT3_RECEIPT_PATH = EVIDENCE_ROOT / "PULL_V0_P1_PUSH_ANCHOR_ATTEMPT3_RECEIPT.json"
ATTEMPT4_RECEIPT_PATH = EVIDENCE_ROOT / "PULL_V0_P1_PUSH_ANCHOR_ATTEMPT4_RECEIPT.json"
ATTEMPT5_RECEIPT_PATH = EVIDENCE_ROOT / "PULL_V0_P1_PUSH_ANCHOR_ATTEMPT5_RECEIPT.json"
ATTEMPT6_RECEIPT_PATH = EVIDENCE_ROOT / "PULL_V0_P1_PUSH_ANCHOR_ATTEMPT6_RECEIPT.json"
ATTEMPT7_RECEIPT_PATH = EVIDENCE_ROOT / "PULL_V0_P1_PUSH_ANCHOR_ATTEMPT7_RECEIPT.json"
ATTEMPT8_RECEIPT_PATH = EVIDENCE_ROOT / "PULL_V0_P1_PUSH_ANCHOR_ATTEMPT8_RECEIPT.json"
ATTEMPT8_INVALIDATION_PATH = EVIDENCE_ROOT / "PULL_V0_P1_PUSH_ANCHOR_ATTEMPT8_INVALIDATION.json"
ATTEMPT9_RECEIPT_PATH = EVIDENCE_ROOT / "PULL_V0_P1_PUSH_ANCHOR_ATTEMPT9_RECEIPT.json"
ATTEMPT9_INVALIDATION_PATH = EVIDENCE_ROOT / "PULL_V0_P1_PUSH_ANCHOR_ATTEMPT9_INVALIDATION.json"
ATTEMPT9_RESPONSE_TELEMETRY_PATH = EVIDENCE_ROOT / "PULL_V0_P1_PUSH_ANCHOR_ATTEMPT9_RESPONSE_TELEMETRY.json"
ATTEMPT10_RECEIPT_PATH = EVIDENCE_ROOT / "PULL_V0_P1_PUSH_ANCHOR_ATTEMPT10_RECEIPT.json"
ATTEMPT11_RECEIPT_PATH = EVIDENCE_ROOT / "PULL_V0_P1_PUSH_ANCHOR_ATTEMPT11_RECEIPT.json"
ATTEMPT14_RECEIPT_PATH = EVIDENCE_ROOT / "PULL_V0_P1_PUSH_ANCHOR_ATTEMPT14_RECEIPT.json"
ATTEMPT15_RECEIPT_PATH = EVIDENCE_ROOT / "PULL_V0_P1_PUSH_ANCHOR_ATTEMPT15_RECEIPT.json"
ATTEMPT16_RECEIPT_PATH = EVIDENCE_ROOT / "PULL_V0_P1_PUSH_ANCHOR_ATTEMPT16_RECEIPT.json"
ATTEMPT13_RECEIPT_PATH = EVIDENCE_ROOT / "PULL_V0_P1_PUSH_ANCHOR_ATTEMPT13_RECEIPT.json"
EXPECTED_REPAIR_RECEIPT_SHA256 = (
    "14b15df80229fbd7e01fded10c8a1675f58317cabb727e6d12f0931ab82f8335"
)
EXPECTED_STALE_CANDIDATE_ID = (
    "244a7569ff6f4ab06c2d7349cb5ca08c12f228c3b72d6df10a72727f8d872c7f"
)
EXPECTED_R2_SCHEMA = "pull_v0_repair_r2_receipt_v1"
EXPECTED_R2_REVISION = "R2"
EXPECTED_R2_ROOT_CAUSE = "TENSOR_DEVICE_CALLSITE_CONTRACT"
EXPECTED_R2_RECEIPT_SHA256 = (
    "9899b5bbb93455cea82c80bee6a2c58e00b7ad692c1302dfe7aedc553b5f5263"
)
EXPECTED_R3_SCHEMA = "pull_v0_repair_r3_receipt_v1"
EXPECTED_R3_REVISION = "R3"
EXPECTED_R3_ROOT_CAUSE = "ACQUISITION_CONTROL_CIRCULARITY_AND_TELEMETRY_INCOMPLETE"
EXPECTED_R3_RECEIPT_SHA256 = (
    "49ca2e32a81f2635afc3303f40e5cf50c0b581f991b2fbe564f36090e72ebf25"
)
EXPECTED_R4_SCHEMA = "pull_v0_repair_r4_receipt_v1"
EXPECTED_R4_REVISION = "R4"
EXPECTED_R4_ROOT_CAUSE = "RESET_BOUNDARY_CONTACT_UNQUALIFIED_BEFORE_STAGING"
EXPECTED_R4_RECEIPT_SHA256 = (
    "0c1debd42bbee1d9007190b2e3768670c23981a903df5ba9c5b6512d22b904aa"
)
EXPECTED_R5_SCHEMA = "pull_v0_repair_r5_receipt_v1"
EXPECTED_R5_REVISION = "R5"
EXPECTED_R5_ROOT_CAUSE = "GENERIC_BASE_RELIEF_WATCHDOG_CROSS_TALK"
EXPECTED_R6_SCHEMA = "pull_v0_repair_r6_receipt_v1"
EXPECTED_R6_REVISION = "R6"
EXPECTED_R6_ROOT_CAUSE = "STAGE0_COMMAND_TO_PLANT_RESPONSE_UNRESOLVED"
EXPECTED_R7_SCHEMA = "pull_v0_repair_r7_receipt_v1"
EXPECTED_R7_REVISION = "R7"
EXPECTED_R7_RECEIPT_SHA256 = "a5f576c06718b145e992bd4927384efae9e7b8714f6f8b87836914da6c702b5f"
EXPECTED_R8_SCHEMA = "pull_v0_repair_r8_receipt_v1"
EXPECTED_R8_REVISION = "R8"
EXPECTED_R8_RECEIPT_SHA256 = "00e7abbc6612f7a841cb0a809c7053ba343dab1e7d14f94d092510a82f11b76b"
EXPECTED_R9_SCHEMA = "pull_v0_repair_r9_receipt_v1"
EXPECTED_R9_REVISION = "R9"
EXPECTED_R9_RECEIPT_SHA256 = "3bed2ab4b7e4e21e3d0c05d07b36afa49d7e5a597c8c4efb41178e35f4d6cd69"
EXPECTED_R9_ROOT_CAUSE = "STAGE0_TIMEOUT_BELOW_KINEMATIC_CAPACITY"
EXPECTED_ATTEMPT9_RECEIPT_SHA256 = "286fa3b832911ce3530b17696049b0a5e9d5584bf78e5199d1506c208b043624"
EXPECTED_ATTEMPT9_INVALIDATION_SHA256 = "ad21ae10c7f443fea640f195dfa5806eedfbb7374a740785c0b80d546d5eda1a"
EXPECTED_ATTEMPT9_RESPONSE_TELEMETRY_SHA256 = "653a599a83e386251ee1a7dc98d51b93e3a474123569565ff311b1d99af9e937"
EXPECTED_ATTEMPT10_RECEIPT_SHA256 = "725300a992e5e842b4335d62e8ee71bbcf4b3bcd414a5087ba6dca38ecdaaaf6"
EXPECTED_R10_RECEIPT_SHA256 = "745f0106ba3503f8f2c729ef21576c19dae5e4a477c39c0b547ae6c5f8926301"
EXPECTED_R10_SCHEMA = "pull_v0_repair_r10_receipt_v1"
EXPECTED_R10_REVISION = "R10"
EXPECTED_R10_ROOT_CAUSE = "PULL_P1_STAGE0_HOST_STAGE_OVERTIME_PREEMPTED_LOCAL_WATCHDOG"
EXPECTED_R11_SCHEMA = "pull_v0_repair_r11_receipt_v1"
EXPECTED_R11_REVISION = "R11"
EXPECTED_R11_ROOT_CAUSE = "ATTEMPT12_PREPARATION_REPAIR_RECEIPT_PATH_MISMATCH"
EXPECTED_R11_RECEIPT_SHA256 = "4c50d52e25658e296b3101b283bb2eb57e7d9f5747dedb8a8b76a22783e563a4"
EXPECTED_ATTEMPT12_PLAN_SHA256 = "2e4231c6f6a7862d094d5182857c37b9381b557b6760636c508e3fd87c648dbc"
EXPECTED_ATTEMPT12_PLAN_IDENTITY_SHA256 = "435bc01e7ad08001390463911d0e450d43ced7110c855f3e3ea69b20006ebe93"
ATTEMPT12_INVALIDATION_PATH = EVIDENCE_ROOT / "PULL_V0_P1_PUSH_ANCHOR_ATTEMPT12_PREPARATION_INVALIDATION.json"
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
SINGLE_GPU_KIT_ARGS = "--/renderer/multiGpu/enabled=False --/renderer/multiGpu/autoEnable=False --/renderer/multiGpu/maxGpuCount=1"
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
EXPECTED_R15_SCHEMA = "pull_v0_repair_r15_receipt_v1"
EXPECTED_R15_REVISION = "R15"
EXPECTED_R15_RECEIPT_SHA256 = "3b850232429e4cdaee96281ad16ba2216f34df5baeb5262312f8bba831f841a0"
EXPECTED_ATTEMPT17_RECEIPT_SHA256 = "5c51dd2d51b2913acc12a9a379ece4fca151d798a4c79570f784e31588ef1cad"
EXPECTED_ATTEMPT18_PLAN_SHA256 = "58c806cecfef15b876d21358f25742460669cd6e4c14e2c1d6c7ebd43678001f"
EXPECTED_ATTEMPT18_PLAN_IDENTITY_SHA256 = "2c9f1efa53423f6abf0a12c41040cfc0c75ed1fb23ce07c05e8c470f093e6d72"
EXPECTED_ATTEMPT18_PROCESS_SHA256 = "641f99ba8ddda16f6114807b72ae9cc87234bae3dc8c0d7f9a6baf911562a94f"
EXPECTED_ATTEMPT18_LOG_SHA256 = "b49d6ed10e8c2665dd4c498692d011e00fb41c64fee72187b24f040679612cb1"
EXPECTED_ATTEMPT18_RETRY1_LAUNCH_OCCUPANCY_SHA256 = "f2b93c71c02600c362a8e8e8eb9a3bcc52fe320f1681726ae933a8b415a0bcb1"
EXPECTED_ATTEMPT18_RETRY1_STEADY_STATE_FOOTPRINT_SHA256 = "a02d5a64683807dcdb1ce33b47f567ac9120a9640235806f7c1273ccaeaf614a"
ATTEMPT18_CONTACT_WARNING_SIGNATURE = (
    "Incomplete contact data is reported in GpuRigidContactView::getContactData "
    "because there are more contact data points than specified maxContactDataCount = 8."
)
ATTEMPT18_CUDA_ASSERT_SIGNATURE = "CUDA error: device-side assert triggered"
ATTEMPT18_FRICTION_FAILURE_SIGNATURE = "Exception: Failed to get friction data from backend"
ATTEMPT18_RECEIPT_PATH = EVIDENCE_ROOT / "PULL_V0_P1_PUSH_ANCHOR_ATTEMPT18_RECEIPT.json"
ATTEMPT18_PLAN_PATH = EVIDENCE_ROOT / "PULL_V0_P1_PUSH_ANCHOR_ATTEMPT18_PLAN.json"
ATTEMPT18_OUTPUT_ROOT = LOG_ROOT / "attempt18"
ATTEMPT18_PROCESS_PATH = ATTEMPT18_OUTPUT_ROOT / "process_receipt.json"
ATTEMPT18_LOG_PATH = ATTEMPT18_OUTPUT_ROOT / "stdout_stderr.log"
ATTEMPT18_SUMMARY_PATH = ATTEMPT18_OUTPUT_ROOT / "eval" / "a2_hold_oracle_summary.json"
ATTEMPT18_METRICS_PATH = ATTEMPT18_OUTPUT_ROOT / "eval" / "metrics_eval.json"
ATTEMPT18_LAUNCH_OCCUPANCY_PATH = (
    EVIDENCE_ROOT / "PULL_V0_P1_PUSH_ANCHOR_ATTEMPT18_LAUNCH_OCCUPANCY.json"
)
ATTEMPT18_STEADY_STATE_FOOTPRINT_PATH = (
    EVIDENCE_ROOT / "PULL_V0_P1_PUSH_ANCHOR_ATTEMPT18_STEADY_STATE_FOOTPRINT.json"
)
ATTEMPT18_PRELAUNCH_INFRA_RECEIPT_PATH = (
    EVIDENCE_ROOT / "PULL_V0_P1_PUSH_ANCHOR_ATTEMPT18_PRELAUNCH_INFRA1_RECEIPT.json"
)
ATTEMPT18_R15E_RECEIPT_PATH = EVIDENCE_ROOT / "PULL_V0_REPAIR_R15E_RECEIPT.json"
ATTEMPT18_R15F_RECEIPT_PATH = EVIDENCE_ROOT / "PULL_V0_REPAIR_R15F_RECEIPT.json"
ATTEMPT18_R15F_CANONICAL_RECEIPT_PATH = (
    EVIDENCE_ROOT / "PULL_V0_REPAIR_R15F_RECEIPT.json"
)
ATTEMPT18_R15F_RECEIPT_SHA256 = (
    "77fda56deb58e5720711fae654da05301cab306162a8fd6b436e23bac00299e3"
)
ATTEMPT18_RETRY1_LAUNCH_OCCUPANCY_PATH = (
    EVIDENCE_ROOT / "PULL_V0_P1_PUSH_ANCHOR_ATTEMPT18_RETRY1_LAUNCH_OCCUPANCY.json"
)
ATTEMPT18_RETRY1_STEADY_STATE_FOOTPRINT_PATH = (
    EVIDENCE_ROOT / "PULL_V0_P1_PUSH_ANCHOR_ATTEMPT18_RETRY1_STEADY_STATE_FOOTPRINT.json"
)
ATTEMPT19_PLAN_PATH = EVIDENCE_ROOT / "PULL_V0_P1_PUSH_ANCHOR_ATTEMPT19_PLAN.json"
ATTEMPT19_RECEIPT_PATH = EVIDENCE_ROOT / "PULL_V0_P1_PUSH_ANCHOR_ATTEMPT19_RECEIPT.json"
ATTEMPT19_OUTPUT_ROOT = LOG_ROOT / "attempt19"
ATTEMPT19_PROCESS_PATH = ATTEMPT19_OUTPUT_ROOT / "process_receipt.json"
ATTEMPT19_LOG_PATH = ATTEMPT19_OUTPUT_ROOT / "stdout_stderr.log"
ATTEMPT19_SUMMARY_PATH = ATTEMPT19_OUTPUT_ROOT / "eval" / "a2_hold_oracle_summary.json"
ATTEMPT19_METRICS_PATH = ATTEMPT19_OUTPUT_ROOT / "eval" / "metrics_eval.json"
ATTEMPT19_LAUNCH_OCCUPANCY_PATH = (
    EVIDENCE_ROOT / "PULL_V0_P1_PUSH_ANCHOR_ATTEMPT19_LAUNCH_OCCUPANCY.json"
)
ATTEMPT19_STEADY_STATE_FOOTPRINT_PATH = (
    EVIDENCE_ROOT / "PULL_V0_P1_PUSH_ANCHOR_ATTEMPT19_STEADY_STATE_FOOTPRINT.json"
)
ATTEMPT19_SELECTED_COMPUTE_PHYSICAL_DEVICE = 2
ATTEMPT19_AUTHORIZED_COMPUTE_PHYSICAL_DEVICES = [2, 3]
ATTEMPT19_PLAN_PATH = EVIDENCE_ROOT / "PULL_V0_P1_PUSH_ANCHOR_ATTEMPT19_PLAN.json"
ATTEMPT19_OUTPUT_ROOT = LOG_ROOT / "attempt19"
ATTEMPT19_CONTACT_CAPACITY = 64
SHARED_CONTACT_CAPACITY = 8
ATTEMPT18_AUTHORIZED_COMPUTE_PHYSICAL_DEVICES = [2, 3]
ATTEMPT18_SELECTED_COMPUTE_PHYSICAL_DEVICE = 2
ATTEMPT18_UNAUTHORIZED_COMPUTE_PHYSICAL_DEVICES = [0, 1, 4, 5, 6, 7]
ATTEMPT18_SCIENTIFIC_FAIL_OUTCOMES = {
    "BASE_RELIEF_WRONG_SIGN",
    "BASE_RELIEF_TIMEOUT",
    "BASE_RELIEF_DISPLACEMENT_LIMIT",
    "DEPRESS_WRONG_SIGN",
    "DEPRESS_TIMEOUT",
    "CONTACT_SLIP",
    "PUSH_WRONG_SIGN",
    "PUSH_PROGRESS",
    "PUSH_NO_PROGRESS",
    "PUSH_TIMEOUT",
    "CENTER_NO_BILATERAL",
    "UNILATERAL_WEDGE",
    "IK_TRACKING_FAILURE",
    "IK_INVALID",
    "JOINT_LIMIT",
    "ARC_PROBE_TIMEOUT",
    "ARC_PROBE_ROOT_BOUND",
    "ARC_PROBE_ROOT_CROSSING",
    "ARC_PROBE_BODY_COLLISION",
    "ARC_PROBE_OVERSPEED",
    "PULL_P1_PROOF_CONTACT_LOSS",
    "PULL_P1_PROOF_TIMEOUT",
    "PULL_P1_BODY_COLLISION",
    "PULL_P1_LATCH_NOT_RELEASED",
    "PULL_P1_STAGE0_TIMEOUT",
    "PULL_P1_RESET_STATE_INVALID",
    "PULL_P1_STAGE0_HOST_STAGE_OVERTIME",
}
ATTEMPT18_LEGACY_FINDINGS = {
    EXPECTED_R13_ROOT_CAUSE,
    EXPECTED_R14_ROOT_CAUSE,
}
PULL_V0_RENDERER_SINGLE_GPU_OVERRIDE = "+a2_pull_v0_renderer_single_gpu=true"
EXPECTED_ATTEMPT11_RECEIPT_SHA256 = "4e37e1c20667ba4d4c9c69ce848725dd1fbe5eda3954dff0f942cc7dbf3f595b"
EXPECTED_ATTEMPT11_PLAN_SHA256 = "78be473a11f3b304c49ad34e0d82cc1a7c1edb0c147675fe7f15056fdb47fa81"
EXPECTED_ATTEMPT11_PLAN_IDENTITY_SHA256 = "ecf47679407d4bfddd7a5d3046e6e4e2801d4f5d4a4fb769ecc7a1194849812f"
EXPECTED_ATTEMPT11_PROCESS_SHA256 = "2c55d7ac5412e331be36e12c75a4834415a0236077d8d1b2ca34f7af295c9b9a"
EXPECTED_ATTEMPT11_LOG_SHA256 = "81d2d7f8298fdbc20a2856e36af2f8774497b10097dd263fd726a52b8cd34fef"
EXPECTED_ATTEMPT11_SUMMARY_SHA256 = "28f52faedb360307add4b14df0a3d902510683482f39de7a972400c800436031"
EXPECTED_ATTEMPT11_METRICS_SHA256 = "991070babb9e4ffe744f8a5f0a21dc56b067c1efeb386283b237b46687b587b4"
EXPECTED_ATTEMPT8_RECEIPT_SHA256 = "dab0732f722bd8444b357b721acbc9c14d8b6725d81096bcfaeb039b9e8e0722"
EXPECTED_ATTEMPT8_INVALIDATION_SHA256 = "dc43421bc12af85a18bbeb6398b1242daf4f293982894a5e17f0d01ec1535fd4"
EXPECTED_ATTEMPT3_ERROR_SIGNATURE = "TypeError: device must be torch.device; got str."
EXPECTED_FIXTURE = {
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
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _hkt_now() -> str:
    return datetime.now(ZoneInfo("Asia/Hong_Kong")).strftime(
        "%Y-%m-%d %H:%M:%S HKT"
    )


def _read_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError(f"Expected a JSON object: {path}")
    return value


def _write_json(path: Path, value: object) -> None:
    if path.exists():
        raise RuntimeError(f"Refusing to overwrite receipt: {path}")
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def _artifact(path: Path) -> dict:
    if not path.is_file() or path.is_symlink():
        raise RuntimeError(f"Evidence artifact must be a regular file: {path}")
    path_label = str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path)
    return {"path": path_label, "sha256": _sha256(path)}


def _parse_hkt_timestamp(value: Any, label: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise RuntimeError(f"{label} must be a non-empty HKT timestamp.")
    try:
        return datetime.strptime(value, "%Y-%m-%d %H:%M:%S HKT").replace(
            tzinfo=ZoneInfo("Asia/Hong_Kong")
        )
    except ValueError as exc:
        raise RuntimeError(f"{label} must use YYYY-MM-DD HH:MM:SS HKT.") from exc


def _validate_attempt18_runtime_paths(
    *,
    plan_path: Path,
    process_receipt_path: Path,
    log_path: Path,
    summary_path: Path,
    metrics_path: Path,
    launch_occupancy_path: Path,
    steady_state_footprint_path: Path,
) -> None:
    expected = {
        "plan": ATTEMPT18_PLAN_PATH,
        "process receipt": ATTEMPT18_PROCESS_PATH,
        "stdout/stderr log": ATTEMPT18_LOG_PATH,
        "summary": ATTEMPT18_SUMMARY_PATH,
        "metrics": ATTEMPT18_METRICS_PATH,
        "launch occupancy": ATTEMPT18_LAUNCH_OCCUPANCY_PATH,
        "steady-state footprint": ATTEMPT18_STEADY_STATE_FOOTPRINT_PATH,
    }
    supplied = {
        "plan": plan_path,
        "process receipt": process_receipt_path,
        "stdout/stderr log": log_path,
        "summary": summary_path,
        "metrics": metrics_path,
        "launch occupancy": launch_occupancy_path,
        "steady-state footprint": steady_state_footprint_path,
    }
    for label, expected_path in expected.items():
        actual_path = supplied[label]
        if actual_path.resolve() != expected_path.resolve():
            raise RuntimeError(
                f"Attempt18 accepts only the canonical {label} path: "
                f"expected={expected_path}, actual={actual_path}."
            )


def _validate_attempt18_retry_runtime_paths(
    *,
    plan_path: Path,
    process_receipt_path: Path,
    log_path: Path,
    summary_path: Path,
    metrics_path: Path,
    launch_occupancy_path: Path,
    steady_state_footprint_path: Path,
) -> None:
    expected = {
        "plan": ATTEMPT18_PLAN_PATH,
        "process receipt": ATTEMPT18_PROCESS_PATH,
        "stdout/stderr log": ATTEMPT18_LOG_PATH,
        "summary": ATTEMPT18_SUMMARY_PATH,
        "metrics": ATTEMPT18_METRICS_PATH,
        "launch occupancy": ATTEMPT18_RETRY1_LAUNCH_OCCUPANCY_PATH,
        "steady-state footprint": ATTEMPT18_RETRY1_STEADY_STATE_FOOTPRINT_PATH,
    }
    supplied = {
        "plan": plan_path,
        "process receipt": process_receipt_path,
        "stdout/stderr log": log_path,
        "summary": summary_path,
        "metrics": metrics_path,
        "launch occupancy": launch_occupancy_path,
        "steady-state footprint": steady_state_footprint_path,
    }
    for label, expected_path in expected.items():
        actual_path = supplied[label]
        if actual_path.resolve() != expected_path.resolve():
            raise RuntimeError(
                f"Attempt18 accepts only the canonical {label} path for retry1: "
                f"expected={expected_path}, actual={actual_path}."
            )


def _validate_attempt18_prelaunch_chain(
    *,
    plan_path: Path,
    initial_launch_occupancy_path: Path,
    prelaunch_infra_receipt_path: Path,
    r15e_receipt_path: Path,
    r15f_receipt_path: Path,
) -> dict[str, dict[str, Any]]:
    plan_artifact = _artifact(plan_path)
    initial_launch_artifact = _artifact(initial_launch_occupancy_path)
    prelaunch_artifact = _artifact(prelaunch_infra_receipt_path)
    r15e_artifact = _artifact(r15e_receipt_path)
    r15f_artifact = _artifact(r15f_receipt_path)
    if (
        r15f_receipt_path.resolve() == ATTEMPT18_R15F_CANONICAL_RECEIPT_PATH.resolve()
        and r15f_artifact["sha256"] != ATTEMPT18_R15F_RECEIPT_SHA256
    ):
        raise RuntimeError("Canonical R15F receipt hash changed.")
    plan = _read_json(plan_path)
    initial_launch = _read_json(initial_launch_occupancy_path)
    prelaunch = _read_json(prelaunch_infra_receipt_path)
    r15e = _read_json(r15e_receipt_path)
    r15f = _read_json(r15f_receipt_path)
    r15_path_label = (
        str(R15_RECEIPT_PATH.relative_to(ROOT))
        if R15_RECEIPT_PATH.is_relative_to(ROOT)
        else str(R15_RECEIPT_PATH)
    )
    if (
        plan.get("schema_version") != "pull_v0_p1_push_anchor_plan_v1"
        or plan.get("attempt") != 18
        or plan.get("status") != "READY"
        or not isinstance(plan.get("plan_sha256"), str)
    ):
        raise RuntimeError("Attempt18 prelaunch chain plan identity is invalid.")
    plan_binding = initial_launch.get("plan")
    if (
        initial_launch.get("schema_version")
        != "pull_v0_p1_attempt18_launch_occupancy_v1"
        or initial_launch.get("attempt") != 18
        or initial_launch.get("status") != "PASS"
        or initial_launch.get("phase") != "IMMEDIATELY_BEFORE_LAUNCH"
        or initial_launch.get("runtime_started") is not False
        or initial_launch.get("scientific_attempt_started") is not False
        or not isinstance(plan_binding, Mapping)
        or plan_binding.get("path") != plan_artifact["path"]
        or plan_binding.get("sha256") != plan_artifact["sha256"]
        or plan_binding.get("plan_sha256") != plan["plan_sha256"]
    ):
        raise RuntimeError("Attempt18 preserved launch occupancy is not bound to the prepared plan.")
    r15e_parent = r15e.get("parent_receipt")
    prelaunch_parent = prelaunch.get("parent_receipt")
    if (
        prelaunch.get("schema_version")
        != "pull_v0_p1_push_anchor_attempt18_prelaunch_infra_receipt_v1"
        or prelaunch.get("attempt") != 18
        or prelaunch.get("status") != "INFRA_PRELAUNCH_RUNNER_VALIDATION"
        or prelaunch.get("runtime_validation") != "INVALIDATED_BEFORE_LAUNCH"
        or prelaunch.get("scientific_verdict_consumed") is not False
        or prelaunch.get("first_simulation_step_boundary_crossed") is not False
        or prelaunch.get("scientific_attempt_started") is not False
        or not isinstance(prelaunch_parent, Mapping)
        or prelaunch_parent.get("path") != r15_path_label
        or prelaunch_parent.get("sha256") != EXPECTED_R15_RECEIPT_SHA256
        or prelaunch_parent.get("repair_revision") != EXPECTED_R15_REVISION
        or not isinstance(prelaunch.get("error"), Mapping)
        or not prelaunch["error"].get("signature")
    ):
        raise RuntimeError("Attempt18 prelaunch infrastructure receipt identity is invalid.")
    prelaunch_artifacts = prelaunch.get("artifacts")
    if not isinstance(prelaunch_artifacts, Mapping):
        raise RuntimeError("Attempt18 prelaunch infrastructure artifacts are missing.")
    for key, artifact in (
        ("plan", plan_artifact),
        ("initial_launch_occupancy", initial_launch_artifact),
    ):
        bound = prelaunch_artifacts.get(key)
        if not isinstance(bound, Mapping) or bound.get("path") != artifact["path"] or bound.get("sha256") != artifact["sha256"]:
            raise RuntimeError(f"Attempt18 prelaunch artifact binding differs: {key}.")
    if (
        r15e.get("schema_version") != "pull_v0_repair_r15e_receipt_v1"
        or r15e.get("repair_revision") != "R15E"
        or r15e.get("status") != "APPROVED_FOR_ATTEMPT18_RETRY1_PREPARATION_ONLY"
        or r15e.get("runtime_validation") != "NOT_RUN"
        or r15e.get("scientific_verdict_consumed") is not False
        or not isinstance(r15e_parent, Mapping)
        or r15e_parent.get("path") != r15_path_label
        or r15e_parent.get("sha256") != EXPECTED_R15_RECEIPT_SHA256
        or r15e_parent.get("repair_revision") != EXPECTED_R15_REVISION
    ):
        raise RuntimeError("R15E repair receipt identity or R15 ancestry is invalid.")
    trigger = r15e.get("trigger")
    if (
        not isinstance(trigger, Mapping)
        or not isinstance(trigger.get("prelaunch_infra_receipt"), Mapping)
        or trigger["prelaunch_infra_receipt"].get("path") != prelaunch_artifact["path"]
        or trigger["prelaunch_infra_receipt"].get("sha256") != prelaunch_artifact["sha256"]
        or trigger.get("exact_error_signature") != prelaunch["error"].get("signature")
    ):
        raise RuntimeError("R15E prelaunch infrastructure trigger binding is invalid.")
    r15f_parent = r15f.get("parent_receipt")
    r15f_trigger = r15f.get("trigger")
    r15f_required = (
        r15f_trigger.get("required_retry1_launch_occupancy")
        if isinstance(r15f_trigger, Mapping)
        else None
    )
    retry1_path_label = (
        str(ATTEMPT18_RETRY1_LAUNCH_OCCUPANCY_PATH.relative_to(ROOT))
        if ATTEMPT18_RETRY1_LAUNCH_OCCUPANCY_PATH.is_relative_to(ROOT)
        else str(ATTEMPT18_RETRY1_LAUNCH_OCCUPANCY_PATH)
    )
    if (
        r15f.get("schema_version") != "pull_v0_repair_r15f_receipt_v1"
        or r15f.get("repair_revision") != "R15F"
        or r15f.get("status") != "APPROVED_FOR_ATTEMPT18_RETRY1_LAUNCH_ADMISSION_ONLY"
        or r15f.get("runtime_validation") != "NOT_RUN"
        or r15f.get("scientific_verdict_consumed") is not False
        or not isinstance(r15f_parent, Mapping)
        or r15f_parent.get("path") != r15e_artifact["path"]
        or r15f_parent.get("sha256") != r15e_artifact["sha256"]
        or r15f_parent.get("repair_revision") != "R15E"
        or not isinstance(r15f_trigger, Mapping)
        or r15f_trigger.get("attempt") != 18
        or r15f_trigger.get("root_cause")
        != "ATTEMPT18_RETRY1_LAUNCH_OCCUPANCY_ADMISSION_CONTRADICTION"
        or not isinstance(r15f_required, Mapping)
        or r15f_required.get("path") != retry1_path_label
        or r15f_required.get("schema_version")
        != "pull_v0_p1_attempt18_launch_occupancy_v1"
        or r15f_required.get("phase") != "IMMEDIATELY_BEFORE_LAUNCH"
        or r15f_required.get("selected_compute_physical_device") != 2
        or r15f_required.get("authorized_compute_physical_devices") != [2, 3]
        or r15f_required.get("cuda_visible_devices") != "UNSET"
        or r15f_required.get("container_isolation_used") is not False
    ):
        raise RuntimeError("R15F retry1 launch-admission identity or R15E ancestry is invalid.")
    r15f_preserved = r15f.get("preserved_artifacts")
    if (
        not isinstance(r15f_preserved, Mapping)
        or r15f_preserved.get("r15e") != r15e_artifact
        or r15f_preserved.get("prelaunch_infra") != prelaunch_artifact
        or r15f_preserved.get("plan") != plan_artifact
        or r15f_preserved.get("initial_launch_occupancy") != initial_launch_artifact
    ):
        raise RuntimeError("R15F preserved-artifact ancestry is invalid.")
    return {
        "prelaunch_infra": prelaunch_artifact,
        "r15e": r15e_artifact,
        "r15f": r15f_artifact,
        "initial_launch_occupancy": initial_launch_artifact,
    }


def _validate_attempt18_resource_plan_binding(
    evidence: Mapping[str, Any],
    *,
    label: str,
    plan: Mapping[str, Any],
    plan_artifact: Mapping[str, Any],
) -> None:
    binding = _require_mapping(evidence.get("plan"), f"{label}.plan")
    expected = {
        "path": plan_artifact["path"],
        "sha256": plan_artifact["sha256"],
        "plan_sha256": plan["plan_sha256"],
    }
    for field, value in expected.items():
        if binding.get(field) != value:
            raise RuntimeError(
                f"Attempt18 {label} plan binding mismatch for {field}."
            )


def _require_finite_nonnegative(value: Any, label: str) -> float:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(float(value))
        or float(value) < 0.0
    ):
        raise RuntimeError(f"{label} must be a finite non-negative number.")
    return float(value)


def _validate_attempt18_tenant_occupancy_at_launch(
    launch: Mapping[str, Any],
) -> dict[int, dict[str, Any]]:
    records = launch.get("non_leased_tenant_occupancy_at_launch")
    if not isinstance(records, list):
        raise RuntimeError(
            "Attempt18 launch occupancy must include non_leased_tenant_occupancy_at_launch."
        )
    tenant_by_device: dict[int, dict[str, Any]] = {}
    for record_index, raw_record in enumerate(records):
        record = _require_mapping(
            raw_record,
            f"Attempt18 launch tenant occupancy[{record_index}]",
        )
        device_index = record.get("device_index")
        if (
            isinstance(device_index, bool)
            or not isinstance(device_index, int)
            or device_index in tenant_by_device
            or device_index not in ATTEMPT18_UNAUTHORIZED_COMPUTE_PHYSICAL_DEVICES
        ):
            raise RuntimeError(
                "Attempt18 launch tenant occupancy has a duplicate, invalid, or leased device index."
            )
        if record.get("attribution") != "OTHER_TENANT":
            raise RuntimeError(
                "Attempt18 launch tenant occupancy must explicitly identify OTHER_TENANT attribution."
            )
        utilization = _require_finite_nonnegative(
            record.get("utilization_gpu_percent"),
            f"Attempt18 launch tenant occupancy[{record_index}] utilization_gpu_percent",
        )
        if utilization > 100.0:
            raise RuntimeError(
                f"Attempt18 launch tenant occupancy[{record_index}] utilization exceeds 100%."
            )
        processes = record.get("processes")
        if not isinstance(processes, list) or not processes:
            raise RuntimeError(
                "Attempt18 launch tenant occupancy requires at least one tenant process record."
            )
        process_pids: set[int] = set()
        normalized_processes: list[dict[str, Any]] = []
        for process_index, raw_process in enumerate(processes):
            process = _require_mapping(
                raw_process,
                f"Attempt18 launch tenant occupancy[{record_index}].processes[{process_index}]",
            )
            pid = process.get("pid")
            if (
                isinstance(pid, bool)
                or not isinstance(pid, int)
                or pid <= 0
                or pid in process_pids
            ):
                raise RuntimeError(
                    "Attempt18 launch tenant occupancy process records require unique positive pids."
                )
            name = process.get("name")
            if not isinstance(name, str) or not name.strip():
                raise RuntimeError(
                    "Attempt18 launch tenant occupancy process records require a non-empty name."
                )
            memory_used_mib = _require_finite_nonnegative(
                process.get("memory_used_mib"),
                f"Attempt18 launch tenant occupancy[{record_index}] process memory_used_mib",
            )
            process_pids.add(pid)
            normalized_processes.append(
                {
                    "pid": pid,
                    "name": name,
                    "memory_used_mib": memory_used_mib,
                }
            )
        tenant_by_device[device_index] = {
            "utilization_gpu_percent": utilization,
            "processes": normalized_processes,
        }
    return tenant_by_device


def _validate_attempt18_resource_devices(
    evidence: Mapping[str, Any],
    *,
    label: str,
    require_compute_processes: bool,
    footprint: bool,
    tenant_by_device: Mapping[int, Mapping[str, Any]] | None = None,
) -> None:
    tenant_by_device = {} if tenant_by_device is None else tenant_by_device
    devices = evidence.get("per_device")
    if not isinstance(devices, list) or len(devices) != 8:
        raise RuntimeError(
            f"Attempt18 {label} must contain one per-device record for physical devices 0-7."
        )
    by_index: dict[int, Mapping[str, Any]] = {}
    for index, raw_device in enumerate(devices):
        device = _require_mapping(raw_device, f"Attempt18 {label}.per_device[{index}]")
        physical_index = device.get("index")
        if (
            isinstance(physical_index, bool)
            or not isinstance(physical_index, int)
            or physical_index in by_index
            or physical_index < 0
            or physical_index > 7
        ):
            raise RuntimeError(f"Attempt18 {label} has duplicate or invalid physical device indices.")
        by_index[physical_index] = device
        expected_leased = physical_index in ATTEMPT18_AUTHORIZED_COMPUTE_PHYSICAL_DEVICES
        if device.get("leased") is not expected_leased:
            raise RuntimeError(
                f"Attempt18 {label} device {physical_index} does not match the GPU2/[2,3] lease contract."
            )
        utilization = _require_finite_nonnegative(
            device.get("utilization_gpu_percent"),
            f"Attempt18 {label} device {physical_index} utilization_gpu_percent",
        )
        if utilization > 100.0:
            raise RuntimeError(
                f"Attempt18 {label} device {physical_index} utilization exceeds 100%."
            )
        processes_present = require_compute_processes or "compute_processes" in device
        if require_compute_processes:
            processes = device.get("compute_processes")
            if not isinstance(processes, list):
                raise RuntimeError(
                    f"Attempt18 {label} device {physical_index} must include compute_processes."
                )
        elif "compute_processes" in device:
            processes = device["compute_processes"]
            if not isinstance(processes, list):
                raise RuntimeError(
                    f"Attempt18 {label} device {physical_index} compute_processes must be a list."
                )
        else:
            processes = []
        if physical_index in ATTEMPT18_UNAUTHORIZED_COMPUTE_PHYSICAL_DEVICES:
            tenant = tenant_by_device.get(physical_index)
            if not footprint:
                if tenant is None and (utilization != 0.0 or processes):
                    raise RuntimeError(
                        f"Attempt18 {label} records unrecorded compute on non-leased GPU{physical_index}."
                    )
                if tenant is not None and (
                    utilization != tenant["utilization_gpu_percent"]
                    or processes != tenant["processes"]
                ):
                    raise RuntimeError(
                        f"Attempt18 {label} tenant attribution does not match GPU{physical_index}."
                    )
            elif utilization != 0.0 and tenant is None:
                raise RuntimeError(
                    f"Attempt18 {label} records unrecorded non-leased GPU{physical_index} utilization."
                )
            if footprint and processes_present and tenant is not None and processes != tenant["processes"]:
                raise RuntimeError(
                    f"Attempt18 {label} tenant process attribution does not match GPU{physical_index}."
                )
            if footprint and processes_present and tenant is None and processes:
                raise RuntimeError(
                    f"Attempt18 {label} records unrecorded tenant processes on GPU{physical_index}."
                )
            if (
                footprint
                and device.get("context_classification")
                != "AUTHORIZED_INACTIVE_VULKAN_ENUMERATION"
            ):
                raise RuntimeError(
                    f"Attempt18 {label} non-leased GPU{physical_index} must be inactive Vulkan enumeration only."
                )
        if not footprint:
            _require_finite_nonnegative(
                device.get("memory_used_mib"),
                f"Attempt18 {label} device {physical_index} memory_used_mib",
            )
        if footprint:
            _require_finite_nonnegative(
                device.get("total_memory_used_mib"),
                f"Attempt18 {label} device {physical_index} total_memory_used_mib",
            )
            _require_finite_nonnegative(
                device.get("attempt_process_memory_mib"),
                f"Attempt18 {label} device {physical_index} attempt_process_memory_mib",
            )
            if "selected" in device and not isinstance(device["selected"], bool):
                raise RuntimeError(
                    f"Attempt18 {label} device {physical_index} selected must be boolean."
                )
    if set(by_index) != set(range(8)):
        raise RuntimeError(f"Attempt18 {label} device records must cover physical devices 0-7 exactly.")
    selected = by_index[ATTEMPT18_SELECTED_COMPUTE_PHYSICAL_DEVICE]
    if footprint and selected.get("selected") is not True:
        raise RuntimeError("Attempt18 steady-state footprint must mark GPU2 as selected.")


def _validate_attempt18_resource_evidence(
    *,
    plan: Mapping[str, Any],
    plan_artifact: Mapping[str, Any],
    launch_occupancy_path: Path,
    steady_state_footprint_path: Path,
) -> dict[str, Any]:
    launch = _read_json(launch_occupancy_path)
    footprint = _read_json(steady_state_footprint_path)
    for label, evidence, schema in (
        (
            "launch occupancy",
            launch,
            "pull_v0_p1_attempt18_launch_occupancy_v1",
        ),
        (
            "steady-state footprint",
            footprint,
            "pull_v0_p1_attempt18_steady_state_footprint_v1",
        ),
    ):
        if evidence.get("schema_version") != schema:
            raise RuntimeError(f"Attempt18 {label} schema is not the canonical Attempt18 schema.")
        if evidence.get("attempt") != 18:
            raise RuntimeError(f"Attempt18 {label} attempt identity is not 18.")
        if evidence.get("status") != "PASS":
            raise RuntimeError(f"Attempt18 {label} evidence must have status PASS.")
        _validate_attempt18_resource_plan_binding(
            evidence,
            label=label,
            plan=plan,
            plan_artifact=plan_artifact,
        )
        if (
            evidence.get("selected_compute_physical_device")
            != ATTEMPT18_SELECTED_COMPUTE_PHYSICAL_DEVICE
        ):
            raise RuntimeError(
                f"Attempt18 {label} selected GPU is outside the authorized GPU contract; expected GPU2."
            )
        if (
            evidence.get("authorized_compute_physical_devices")
            != ATTEMPT18_AUTHORIZED_COMPUTE_PHYSICAL_DEVICES
        ):
            raise RuntimeError(f"Attempt18 {label} authorized GPU contract is not [2, 3].")
        if (
            evidence.get("unauthorized_compute_physical_devices")
            != ATTEMPT18_UNAUTHORIZED_COMPUTE_PHYSICAL_DEVICES
        ):
            raise RuntimeError(
                f"Attempt18 {label} unauthorized GPU contract is not [0, 1, 4, 5, 6, 7]."
            )
        if evidence.get("cuda_visible_devices") != "UNSET":
            raise RuntimeError(f"Attempt18 {label} must preserve CUDA_VISIBLE_DEVICES=UNSET.")
        if evidence.get("container_isolation_used") is not False:
            raise RuntimeError(f"Attempt18 {label} must not claim container isolation.")

    if launch.get("phase") != "IMMEDIATELY_BEFORE_LAUNCH":
        raise RuntimeError("Attempt18 launch occupancy phase must be IMMEDIATELY_BEFORE_LAUNCH.")
    if (
        launch.get("runtime_started") is not False
        or launch.get("scientific_attempt_started") is not False
    ):
        raise RuntimeError("Attempt18 launch occupancy must be captured before runtime/scientific start.")
    if launch.get("incidental_vulkan_enumeration_contexts_authorized") is not True:
        raise RuntimeError("Attempt18 launch occupancy must record Amendment 5 Vulkan authorization.")
    if not isinstance(launch.get("non_leased_tenant_occupancy_at_launch"), list):
        raise RuntimeError("Attempt18 launch occupancy must record non-leased tenant occupancy.")
    tenant_by_device = _validate_attempt18_tenant_occupancy_at_launch(launch)
    _validate_attempt18_resource_devices(
        launch,
        label="launch occupancy",
        require_compute_processes=True,
        footprint=False,
        tenant_by_device=tenant_by_device,
    )

    if not isinstance(footprint.get("phase"), str) or not footprint["phase"]:
        raise RuntimeError("Attempt18 steady-state footprint phase is missing.")
    boundary_crossed = footprint.get("first_simulation_step_boundary_crossed")
    scientific_started = footprint.get("scientific_attempt_started")
    if not isinstance(boundary_crossed, bool) or not isinstance(scientific_started, bool):
        raise RuntimeError("Attempt18 steady-state footprint first-step fields must be boolean.")
    if boundary_crossed != scientific_started:
        raise RuntimeError(
            "Attempt18 steady-state footprint has inconsistent first-step boundary/scientific-start fields."
        )
    if not isinstance(footprint.get("first_simulation_step_evidence"), str) or not footprint[
        "first_simulation_step_evidence"
    ].strip():
        raise RuntimeError("Attempt18 steady-state footprint must explain the first-step boundary evidence.")
    if footprint.get("kit_active_physical_devices") != [
        ATTEMPT18_SELECTED_COMPUTE_PHYSICAL_DEVICE
    ]:
        raise RuntimeError("Attempt18 steady-state footprint must bind Kit activity to GPU2 only.")
    if (
        footprint.get("app_launcher_device") != "cuda:2"
        or footprint.get("environment_device") != "cuda:2"
    ):
        raise RuntimeError("Attempt18 steady-state footprint must bind launcher and environment to cuda:2.")
    if footprint.get("non_leased_threshold_pass") is not True:
        raise RuntimeError("Attempt18 steady-state footprint must pass the non-leased footprint threshold.")
    threshold = _require_finite_nonnegative(
        footprint.get("non_leased_stop_threshold_mib"),
        "Attempt18 steady-state footprint non_leased_stop_threshold_mib",
    )
    maximum = _require_finite_nonnegative(
        footprint.get("max_non_leased_attempt_process_memory_mib"),
        "Attempt18 steady-state footprint max_non_leased_attempt_process_memory_mib",
    )
    if maximum > threshold:
        raise RuntimeError("Attempt18 steady-state footprint exceeds the non-leased footprint threshold.")
    observed_non_leased_memory = max(
        float(device["attempt_process_memory_mib"])
        for device in footprint["per_device"]
        if device["index"] in ATTEMPT18_UNAUTHORIZED_COMPUTE_PHYSICAL_DEVICES
    )
    if maximum != observed_non_leased_memory:
        raise RuntimeError(
            "Attempt18 steady-state footprint max_non_leased_attempt_process_memory_mib "
            "does not match the per-device footprint."
        )
    observed_utilization = _require_finite_nonnegative(
        footprint.get("non_leased_observed_utilization_gpu_percent"),
        "Attempt18 steady-state footprint non_leased_observed_utilization_gpu_percent",
    )
    _validate_attempt18_resource_devices(
        footprint,
        label="steady-state footprint",
        require_compute_processes=False,
        footprint=True,
        tenant_by_device=tenant_by_device,
    )
    observed_per_device_utilization = max(
        float(device["utilization_gpu_percent"])
        for device in footprint["per_device"]
        if device["index"] in ATTEMPT18_UNAUTHORIZED_COMPUTE_PHYSICAL_DEVICES
    )
    if not math.isclose(
        observed_utilization,
        observed_per_device_utilization,
        rel_tol=1.0e-6,
        abs_tol=1.0e-6,
    ):
        raise RuntimeError(
            "Attempt18 steady-state aggregate non-leased utilization does not match per-device evidence."
        )
    selected_device = next(
        device
        for device in footprint["per_device"]
        if device["index"] == ATTEMPT18_SELECTED_COMPUTE_PHYSICAL_DEVICE
    )
    if boundary_crossed and selected_device.get("context_classification") != "AUTHORIZED_COMPUTE":
        raise RuntimeError(
            "Attempt18 steady-state footprint must classify selected GPU2 as authorized compute after the first step."
        )
    if not boundary_crossed and selected_device.get("context_classification") == "AUTHORIZED_COMPUTE":
        raise RuntimeError(
            "Attempt18 pre-first-step footprint cannot classify GPU2 as scientific compute."
        )
    return {
        "launch": launch,
        "steady_state": footprint,
        "first_simulation_step_boundary_crossed": boundary_crossed,
        "scientific_attempt_started": scientific_started,
        "non_leased_compute_observed": False,
        "tenant_devices_at_launch": sorted(tenant_by_device),
    }


def _validate_attempt19_resource_evidence(
    *,
    plan: Mapping[str, Any],
    plan_artifact: Mapping[str, Any],
    process_receipt: Mapping[str, Any],
    log_path: Path,
    launch_occupancy_path: Path,
    steady_state_footprint_path: Path,
) -> dict[str, Any]:
    """Validate exact Attempt19 launch and first-step resource evidence."""
    expected_paths = {
        "launch occupancy": ATTEMPT19_LAUNCH_OCCUPANCY_PATH,
        "steady-state footprint": ATTEMPT19_STEADY_STATE_FOOTPRINT_PATH,
    }
    supplied_paths = {
        "launch occupancy": launch_occupancy_path,
        "steady-state footprint": steady_state_footprint_path,
    }
    for label, expected_path in expected_paths.items():
        supplied_path = supplied_paths[label]
        if not supplied_path.is_absolute():
            supplied_path = ROOT / supplied_path
        if supplied_path.resolve() != expected_path.resolve():
            raise RuntimeError(
                f"Attempt19 {label} must use the canonical path: expected={expected_path}, actual={supplied_path}."
            )
        if not supplied_path.is_file() or supplied_path.is_symlink():
            raise RuntimeError(
                f"Attempt19 {label} is missing or not a regular non-symlink file: {supplied_path}"
            )
    if not log_path.is_file() or log_path.is_symlink():
        raise RuntimeError(f"Attempt19 runtime log is missing or not a regular file: {log_path}")
    launch = _read_json(launch_occupancy_path)
    footprint = _read_json(steady_state_footprint_path)
    started_at = _parse_hkt_timestamp(
        process_receipt.get("started_at_hkt"), "Attempt19 process started_at_hkt"
    )
    finished_at = _parse_hkt_timestamp(
        process_receipt.get("finished_at_hkt"), "Attempt19 process finished_at_hkt"
    )
    if finished_at < started_at:
        raise RuntimeError("Attempt19 process lifecycle timestamps are reversed.")
    launch_captured_at = _parse_hkt_timestamp(
        launch.get("captured_at_hkt"), "Attempt19 launch occupancy captured_at_hkt"
    )
    steady_captured_at = _parse_hkt_timestamp(
        footprint.get("captured_at_hkt"), "Attempt19 steady-state captured_at_hkt"
    )
    if not launch_captured_at < started_at:
        raise RuntimeError("Attempt19 launch occupancy must be captured before process start.")
    if not started_at <= steady_captured_at <= finished_at:
        raise RuntimeError("Attempt19 steady-state capture must fall within the process lifecycle.")
    eval_pid = footprint.get("process", {}).get("pid") if isinstance(footprint.get("process"), Mapping) else None
    if process_receipt.get("eval_pid") != eval_pid:
        raise RuntimeError("Attempt19 process receipt eval_pid does not match steady-state evidence PID.")
    if process_receipt.get("attempt") != 19:
        raise RuntimeError("Attempt19 process receipt attempt identity is not 19.")
    process_identity = footprint.get("process_identity")
    if not isinstance(process_identity, Mapping):
        raise RuntimeError("Attempt19 steady-state process identity is missing.")
    eval_identity = process_identity.get("eval")
    if not isinstance(eval_identity, Mapping):
        raise RuntimeError("Attempt19 steady-state eval identity is missing.")
    if process_receipt.get("runner_pid") != process_identity.get("runner_pid"):
        raise RuntimeError("Attempt19 process receipt runner_pid does not match steady-state identity.")
    if process_receipt.get("eval_pid") != process_identity.get("eval_pid"):
        raise RuntimeError("Attempt19 process receipt eval_pid does not match steady-state identity.")
    if process_receipt.get("eval_cmdline") != eval_identity.get("cmdline"):
        raise RuntimeError("Attempt19 process receipt eval_cmdline does not match steady-state identity.")
    if process_receipt.get("eval_output_dir") != process_identity.get("eval_output_dir"):
        raise RuntimeError("Attempt19 process receipt eval_output_dir does not match steady-state identity.")
    plan_binding_artifact = {
        **dict(plan_artifact),
        "plan_sha256": plan.get("plan_sha256"),
    }
    launch_result = attempt19_gpu_evidence.validate_launch_evidence(
        launch,
        plan=plan,
        plan_artifact=plan_binding_artifact,
        require_fresh=False,
    )
    log_text = log_path.read_text(encoding="utf-8", errors="replace")
    steady_result = attempt19_gpu_evidence.validate_steady_evidence(
        footprint,
        plan=plan,
        plan_artifact=plan_binding_artifact,
        log_text=log_text,
        required_pid=footprint.get("process", {}).get("pid")
        if isinstance(footprint.get("process"), Mapping)
        else None,
        require_fresh=False,
    )
    log_artifact = _artifact(log_path)
    runtime_log = footprint.get("runtime_log")
    if (
        not isinstance(runtime_log, Mapping)
        or runtime_log.get("path") != log_artifact["path"]
        or runtime_log.get("sha256") != log_artifact["sha256"]
    ):
        raise RuntimeError("Attempt19 steady-state footprint runtime log binding does not match the supplied log.")
    return {
        "launch": launch,
        "steady_state": footprint,
        "launch_artifact": _artifact(launch_occupancy_path),
        "steady_state_artifact": _artifact(steady_state_footprint_path),
        "log_artifact": log_artifact,
        "first_simulation_step_boundary_crossed": steady_result[
            "first_simulation_step_boundary_crossed"
        ],
        "scientific_attempt_started": steady_result["scientific_attempt_started"],
        "selected_compute_physical_device": steady_result[
            "selected_compute_physical_device"
        ],
        "authorized_compute_physical_devices": steady_result[
            "authorized_compute_physical_devices"
        ],
        "non_leased_compute_observed": False,
        "tenant_devices_at_launch": launch_result["tenant_devices_at_launch"],
        "tenant_devices_at_steady_state": steady_result[
            "tenant_devices_at_steady_state"
        ],
        "process_started_at_hkt": process_receipt["started_at_hkt"],
        "process_finished_at_hkt": process_receipt["finished_at_hkt"],
    }


def _assert_close(actual: float, expected: float, field: str) -> None:
    if not math.isclose(float(actual), expected, rel_tol=1.0e-6, abs_tol=1.0e-6):
        raise RuntimeError(
            f"Runtime central fixture mismatch for {field}: {actual} != {expected}"
        )


REQUIRED_SUMMARY_FIELDS = (
    "schema",
    "probe_mode",
    "status",
    "command_contract",
    "acquisition_contract",
    "per_env_outcome",
    "per_env_pass",
    "per_env_proof_completed",
    "per_env_latch_released",
    "per_env_max_hinge_rad",
    "per_env_max_body_force_n",
    "per_env_proof_samples",
    "per_env_arc_samples",
    "finalize_called",
)
REQUIRED_COMMAND_CONTRACT_FIELDS = (
    "commandable_dofs_only",
    "arm",
    "gripper",
    "base",
    "low_level_usd_runtime_writes",
)
REQUIRED_ACQUISITION_FIELDS = (
    "enabled",
    "admission_gate",
    "stage2_grasp_gate_required",
    "stage0_predicates_reported_separately",
    "proof_world_direction",
)
REQUIRED_TERMINAL_FIELDS = (
    "pull_v0_stage0_predicates",
    "pull_v0_scripted_activation",
    "pull_v0_episode",
)


def _require_mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise RuntimeError(f"{label} must be a mapping.")
    return value


def _require_bool_list(value: Any, label: str, length: int = 1) -> list[bool]:
    if not isinstance(value, list) or len(value) != length or any(
        not isinstance(item, bool) for item in value
    ):
        raise RuntimeError(f"{label} must be a bool list of length {length}.")
    return value


def _require_numeric_list(
    value: Any,
    label: str,
    length: int = 1,
    *,
    allow_none: bool = False,
) -> list[float | None]:
    if not isinstance(value, list) or len(value) != length:
        raise RuntimeError(f"{label} must be a numeric list of length {length}.")
    result: list[float | None] = []
    for item in value:
        if allow_none and item is None:
            result.append(None)
            continue
        if isinstance(item, bool) or not isinstance(item, (int, float)) or not math.isfinite(float(item)):
            raise RuntimeError(f"{label} must contain finite numeric values.")
        result.append(float(item))
    return result


def _validate_repair_receipt(
    path: Path,
    *,
    attempt: int,
    allow_attempt18_runtime: bool = False,
) -> tuple[dict, dict]:
    artifact = _artifact(path)
    receipt = _read_json(path)
    if attempt == 3:
        if artifact["sha256"] != EXPECTED_REPAIR_RECEIPT_SHA256:
            raise RuntimeError(
                "Repair R1 receipt hash does not match the authorized binding: "
                f"expected={EXPECTED_REPAIR_RECEIPT_SHA256}, actual={artifact['sha256']}"
            )
        if (
            receipt.get("schema_version") != "pull_v0_repair_r1_receipt_v1"
            or receipt.get("repair_revision") != "R1"
            or receipt.get("stale_candidate_id") != EXPECTED_STALE_CANDIDATE_ID
        ):
            raise RuntimeError("Repair R1 receipt identity is not authorized for attempt 3.")
        return receipt, artifact
    if attempt < 4:
        raise RuntimeError(f"Unsupported repair binding attempt: {attempt}")
    if attempt == 4:
        if path.resolve() != REPAIR_R2_RECEIPT_PATH.resolve():
            raise RuntimeError("Attempt 4 accepts only the canonical Repair R2 receipt path.")
    elif attempt == 5 and path.resolve() != REPAIR_R3_RECEIPT_PATH.resolve():
        raise RuntimeError("Attempt 5 accepts only the canonical Repair R3 receipt path.")
    elif attempt == 6 and path.resolve() != REPAIR_R4_RECEIPT_PATH.resolve():
        raise RuntimeError("Attempt 6 accepts only the canonical Repair R4 receipt path.")
    elif attempt == 7 and path.resolve() != REPAIR_R5_RECEIPT_PATH.resolve():
        raise RuntimeError("Attempt 7 accepts only the canonical Repair R5 receipt path.")
    elif attempt == 8 and path.resolve() != REPAIR_R6_RECEIPT_PATH.resolve():
        raise RuntimeError("Attempt 8 accepts only the canonical Repair R6 receipt path.")
    elif attempt == 9 and path.resolve() != REPAIR_R7_RECEIPT_PATH.resolve():
        raise RuntimeError("Attempt 9 accepts only the canonical Repair R7 receipt path.")
    elif attempt == 10 and path.resolve() != REPAIR_R8_RECEIPT_PATH.resolve():
        raise RuntimeError("Attempt 10 accepts only the canonical Repair R8 receipt path.")
    elif attempt == 11 and path.resolve() != REPAIR_R9_RECEIPT_PATH.resolve():
        raise RuntimeError("Attempt 11 accepts only the canonical Repair R9 receipt path.")
    elif attempt == 12 and path.resolve() != REPAIR_R10_RECEIPT_PATH.resolve():
        raise RuntimeError("Attempt 12 accepts only the canonical Repair R10 receipt path.")
    elif attempt == 13 and path.resolve() != REPAIR_R11_RECEIPT_PATH.resolve():
        raise RuntimeError("Attempt 13 accepts only the canonical Repair R11 receipt path.")
    elif attempt == 14 and path.resolve() != REPAIR_R12_RECEIPT_PATH.resolve():
        raise RuntimeError("Attempt 14 accepts only the canonical Repair R12 receipt path.")
    elif attempt == 15 and path.resolve() != REPAIR_R13_RECEIPT_PATH.resolve():
        raise RuntimeError("Attempt 15 accepts only the canonical Repair R13 receipt path.")
    elif attempt == 16 and path.resolve() != REPAIR_R14_RECEIPT_PATH.resolve():
        raise RuntimeError("Attempt 16 accepts only the canonical Repair R14 receipt path.")
    elif attempt == 17 and path.resolve() != GPU_LEASE_AMENDMENT_RECEIPT_PATH.resolve():
        raise RuntimeError("Attempt 17 accepts only the canonical A4_A6 GPU-lease amendment receipt path.")
    elif attempt == 18 and path.resolve() != R15_RECEIPT_PATH.resolve():
        raise RuntimeError("Attempt 18 accepts only the canonical Repair R15 receipt path.")
    elif attempt == 19 and path.resolve() != R16_RECEIPT_PATH.resolve():
        raise RuntimeError("Attempt 19 accepts only the canonical Repair R16 receipt path.")
    elif attempt > 19:
        raise RuntimeError(f"Unsupported repair binding attempt: {attempt}; Repair R16 is sealed to attempt 19.")
    parent = receipt.get("parent_receipt")
    trigger = receipt.get("trigger")
    if attempt == 19:
        source_repair = receipt.get("source_repair")
        preparation_contract = receipt.get("attempt19_preparation_contract")
        expected_parent_path = str(ATTEMPT18_RECEIPT_PATH.relative_to(ROOT))
        if (
            artifact["sha256"] != EXPECTED_R16_RECEIPT_SHA256
            or
            receipt.get("schema_version") != "pull_v0_repair_r16_receipt_v1"
            or receipt.get("repair_revision") != "R16"
            or receipt.get("revision_detail") != "R16.4"
            or receipt.get("status") != "APPROVED_FOR_ATTEMPT19_PREPARATION_ONLY"
            or receipt.get("runtime_validation") != "NOT_RUN"
            or receipt.get("scientific_verdict_consumed") is not False
            or receipt.get("stale_candidate_id") != EXPECTED_STALE_CANDIDATE_ID
            or not isinstance(parent, dict)
            or parent.get("path") != expected_parent_path
            or not ATTEMPT18_RECEIPT_PATH.is_file()
            or parent.get("sha256") != _sha256(ATTEMPT18_RECEIPT_PATH)
            or parent.get("repair_revision") != "ATTEMPT18_RUNTIME"
            or not isinstance(source_repair, dict)
            or source_repair.get("anchor_only_detailed_contact_capacity") != ATTEMPT19_CONTACT_CAPACITY
            or source_repair.get("shared_default_detailed_contact_capacity") != SHARED_CONTACT_CAPACITY
            or source_repair.get("observed_total_collision_shape_count") != 7
            or source_repair.get("candidate_sensor_filter_shape_pair_count") != 10
            or source_repair.get("track_pose") is not True
            or source_repair.get("track_contact_points") is not True
            or source_repair.get("track_friction_forces") is not True
            or not isinstance(preparation_contract, dict)
            or preparation_contract.get("detailed_contact_capacity") != ATTEMPT19_CONTACT_CAPACITY
            or preparation_contract.get("launch_occupancy_path")
            != str(ATTEMPT19_LAUNCH_OCCUPANCY_PATH.relative_to(ROOT))
            or preparation_contract.get("steady_state_footprint_path")
            != str(ATTEMPT19_STEADY_STATE_FOOTPRINT_PATH.relative_to(ROOT))
            or preparation_contract.get("launch_occupancy_schema")
            != "pull_v0_p1_attempt19_launch_occupancy_v1"
            or preparation_contract.get("steady_state_footprint_schema")
            != "pull_v0_p1_attempt19_steady_state_footprint_v1"
            or preparation_contract.get("capture_tool")
            != "scriptsFORhuman/pull_v0/capture_p1_anchor_gpu_evidence.py"
            or preparation_contract.get("selected_compute_physical_device") != 2
            or preparation_contract.get("authorized_compute_physical_devices") != [2, 3]
            or preparation_contract.get("unauthorized_compute_physical_devices")
            != [0, 1, 4, 5, 6, 7]
            or preparation_contract.get("first_simulation_step_boundary_required") is not True
            or preparation_contract.get("evidence_derivation_revision") != "R16.4"
            or not isinstance(preparation_contract.get("runtime_log_contract"), Mapping)
            or preparation_contract["runtime_log_contract"].get("validator_independent_derivation") is not True
            or not isinstance(preparation_contract.get("pmon_contract"), Mapping)
            or preparation_contract["pmon_contract"].get("source_authoritative_for_attempt_pid") is not True
            or not isinstance(preparation_contract.get("process_identity_contract"), Mapping)
            or preparation_contract["process_identity_contract"].get("module") != "gr00t.rl.eval_agent_trl"
            or not isinstance(preparation_contract.get("lifecycle_contract"), Mapping)
            or preparation_contract["lifecycle_contract"].get("launch_capture_strictly_before_process_started_at") is not True
            or preparation_contract.get("runtime_validation") != "NOT_RUN"
        ):
            raise RuntimeError(
                "Repair R16 identity, Attempt18 parent binding, or contact-capacity contract is not authorized."
            )
        return receipt, artifact
    if attempt == 4:
        if (
            artifact["sha256"] != EXPECTED_R2_RECEIPT_SHA256
            or receipt.get("schema_version") != EXPECTED_R2_SCHEMA
            or receipt.get("repair_revision") != EXPECTED_R2_REVISION
            or receipt.get("stale_candidate_id") != EXPECTED_STALE_CANDIDATE_ID
            or not isinstance(parent, dict)
            or parent.get("path") != str(REPAIR_R1_RECEIPT_PATH.relative_to(ROOT))
            or parent.get("sha256") != EXPECTED_REPAIR_RECEIPT_SHA256
            or parent.get("repair_revision") != "R1"
            or not isinstance(trigger, dict)
            or trigger.get("attempt") != 3
            or trigger.get("root_cause") != EXPECTED_R2_ROOT_CAUSE
        ):
            raise RuntimeError("Repair R2 identity, parent R1 binding, or trigger is not authorized.")
        return receipt, artifact
    if attempt == 5:
        if (
            artifact["sha256"] != EXPECTED_R3_RECEIPT_SHA256
            or
            receipt.get("schema_version") != EXPECTED_R3_SCHEMA
            or receipt.get("repair_revision") != EXPECTED_R3_REVISION
            or receipt.get("stale_candidate_id") != EXPECTED_STALE_CANDIDATE_ID
            or not isinstance(parent, dict)
            or parent.get("path") != str(REPAIR_R2_RECEIPT_PATH.relative_to(ROOT))
            or parent.get("sha256") != EXPECTED_R2_RECEIPT_SHA256
            or parent.get("repair_revision") != "R2"
            or not isinstance(trigger, dict)
            or trigger.get("attempt") != 4
            or trigger.get("root_cause") != EXPECTED_R3_ROOT_CAUSE
        ):
            raise RuntimeError("Repair R3 identity, parent R2 binding, or trigger is not authorized.")
        attempt4_artifact = trigger.get("attempt_receipt")
        if not isinstance(attempt4_artifact, dict):
            raise RuntimeError("Repair R3 trigger must include immutable attempt4 receipt artifact.")
        if (
            attempt4_artifact.get("path") != str(ATTEMPT4_RECEIPT_PATH.relative_to(ROOT))
            or not ATTEMPT4_RECEIPT_PATH.is_file()
            or attempt4_artifact.get("sha256") != _sha256(ATTEMPT4_RECEIPT_PATH)
        ):
            raise RuntimeError("Repair R3 trigger does not bind immutable attempt4 receipt.")
        return receipt, artifact
    if attempt == 6:
        if (
            artifact["sha256"] != EXPECTED_R4_RECEIPT_SHA256
            or receipt.get("schema_version") != EXPECTED_R4_SCHEMA
            or receipt.get("repair_revision") != EXPECTED_R4_REVISION
            or receipt.get("stale_candidate_id") != EXPECTED_STALE_CANDIDATE_ID
            or not isinstance(parent, dict)
            or parent.get("path") != str(REPAIR_R3_RECEIPT_PATH.relative_to(ROOT))
            or parent.get("sha256") != EXPECTED_R3_RECEIPT_SHA256
            or parent.get("repair_revision") != "R3"
            or not isinstance(trigger, dict)
            or trigger.get("attempt") != 5
            or trigger.get("root_cause") != EXPECTED_R4_ROOT_CAUSE
        ):
            raise RuntimeError("Repair R4 identity, parent R3 binding, or trigger is not authorized.")
        attempt5_artifact = trigger.get("attempt_receipt")
        if not isinstance(attempt5_artifact, dict):
            raise RuntimeError("Repair R4 trigger must include immutable attempt5 receipt artifact.")
        if (
            attempt5_artifact.get("path") != str(ATTEMPT5_RECEIPT_PATH.relative_to(ROOT))
            or not ATTEMPT5_RECEIPT_PATH.is_file()
            or attempt5_artifact.get("sha256") != _sha256(ATTEMPT5_RECEIPT_PATH)
        ):
            raise RuntimeError("Repair R4 trigger does not bind immutable attempt5 receipt.")
        return receipt, artifact
    if attempt == 7:
        attempt6_artifact = trigger.get("attempt_receipt") if isinstance(trigger, dict) else None
        if (
            receipt.get("schema_version") != EXPECTED_R5_SCHEMA
            or receipt.get("repair_revision") != EXPECTED_R5_REVISION
            or receipt.get("stale_candidate_id") != EXPECTED_STALE_CANDIDATE_ID
            or not isinstance(parent, dict)
            or parent.get("path") != str(REPAIR_R4_RECEIPT_PATH.relative_to(ROOT))
            or parent.get("sha256") != _sha256(REPAIR_R4_RECEIPT_PATH)
            or parent.get("repair_revision") != EXPECTED_R4_REVISION
            or not isinstance(trigger, dict)
            or trigger.get("attempt") != 6
            or trigger.get("root_cause") != EXPECTED_R5_ROOT_CAUSE
            or not isinstance(attempt6_artifact, dict)
            or attempt6_artifact.get("path") != str(ATTEMPT6_RECEIPT_PATH.relative_to(ROOT))
            or not ATTEMPT6_RECEIPT_PATH.is_file()
            or attempt6_artifact.get("sha256") != _sha256(ATTEMPT6_RECEIPT_PATH)
        ):
            raise RuntimeError("Repair R5 identity, parent R4 binding, or trigger is not authorized.")
        return receipt, artifact
    if attempt == 8:
        attempt7_artifact = trigger.get("attempt_receipt") if isinstance(trigger, dict) else None
        if (
            artifact["sha256"] != _sha256(path)
            or receipt.get("schema_version") != EXPECTED_R6_SCHEMA
            or receipt.get("repair_revision") != EXPECTED_R6_REVISION
            or receipt.get("stale_candidate_id") != EXPECTED_STALE_CANDIDATE_ID
            or not isinstance(parent, dict)
            or parent.get("path") != str(REPAIR_R5_RECEIPT_PATH.relative_to(ROOT))
            or parent.get("sha256") != _sha256(REPAIR_R5_RECEIPT_PATH)
            or parent.get("repair_revision") != EXPECTED_R5_REVISION
            or not isinstance(trigger, dict)
            or trigger.get("attempt") != 7
            or trigger.get("root_cause") != EXPECTED_R6_ROOT_CAUSE
            or not isinstance(attempt7_artifact, dict)
            or attempt7_artifact.get("path") != str(ATTEMPT7_RECEIPT_PATH.relative_to(ROOT))
            or not ATTEMPT7_RECEIPT_PATH.is_file()
            or attempt7_artifact.get("sha256") != _sha256(ATTEMPT7_RECEIPT_PATH)
        ):
            raise RuntimeError("Repair R6 identity, parent R5 binding, or trigger is not authorized.")
        return receipt, artifact
    if attempt == 9:
        attempt8_artifact = trigger.get("attempt_receipt") if isinstance(trigger, dict) else None
        invalidation_artifact = trigger.get("invalidation_manifest") if isinstance(trigger, dict) else None
        if (
            artifact["sha256"] != EXPECTED_R7_RECEIPT_SHA256
            or receipt.get("schema_version") != EXPECTED_R7_SCHEMA
            or receipt.get("repair_revision") != EXPECTED_R7_REVISION
            or receipt.get("stale_candidate_id") != EXPECTED_STALE_CANDIDATE_ID
            or not isinstance(parent, dict)
            or parent.get("path") != str(REPAIR_R6_RECEIPT_PATH.relative_to(ROOT))
            or parent.get("sha256") != _sha256(REPAIR_R6_RECEIPT_PATH)
            or parent.get("repair_revision") != EXPECTED_R6_REVISION
            or not isinstance(trigger, dict)
            or trigger.get("attempt") != 8
            or trigger.get("root_cause") != "ATTEMPT8_TELEMETRY_SCHEMA_INVALIDATED"
            or not isinstance(attempt8_artifact, dict)
            or attempt8_artifact.get("path") != str(ATTEMPT8_RECEIPT_PATH.relative_to(ROOT))
            or attempt8_artifact.get("sha256") != EXPECTED_ATTEMPT8_RECEIPT_SHA256
            or not ATTEMPT8_RECEIPT_PATH.is_file()
            or attempt8_artifact.get("sha256") != _sha256(ATTEMPT8_RECEIPT_PATH)
            or not isinstance(invalidation_artifact, dict)
            or invalidation_artifact.get("path") != str(ATTEMPT8_INVALIDATION_PATH.relative_to(ROOT))
            or invalidation_artifact.get("sha256") != EXPECTED_ATTEMPT8_INVALIDATION_SHA256
            or not ATTEMPT8_INVALIDATION_PATH.is_file()
            or invalidation_artifact.get("sha256") != _sha256(ATTEMPT8_INVALIDATION_PATH)
        ):
            raise RuntimeError("Repair R7 identity, parent R6 binding, or trigger is not authorized.")
        return receipt, artifact
    if attempt == 10:
        attempt9_artifact = trigger.get("attempt_receipt") if isinstance(trigger, dict) else None
        invalidation_artifact = trigger.get("invalidation_manifest") if isinstance(trigger, dict) else None
        normalized_artifact = (
            trigger.get("normalized_response_telemetry") if isinstance(trigger, dict) else None
        )
        if (
            artifact["sha256"] != EXPECTED_R8_RECEIPT_SHA256
            or receipt.get("schema_version") != EXPECTED_R8_SCHEMA
            or receipt.get("repair_revision") != EXPECTED_R8_REVISION
            or receipt.get("stale_candidate_id") != EXPECTED_STALE_CANDIDATE_ID
            or not isinstance(parent, dict)
            or parent.get("path") != str(REPAIR_R7_RECEIPT_PATH.relative_to(ROOT))
            or parent.get("sha256") != EXPECTED_R7_RECEIPT_SHA256
            or parent.get("repair_revision") != EXPECTED_R7_REVISION
            or not isinstance(trigger, dict)
            or trigger.get("attempt") != 9
            or trigger.get("root_cause") != "ATTEMPT9_QUATERNION_SOURCE_AND_RECEIPT_NORMALIZATION"
            or not isinstance(attempt9_artifact, dict)
            or attempt9_artifact.get("path") != str(ATTEMPT9_RECEIPT_PATH.relative_to(ROOT))
            or attempt9_artifact.get("sha256") != EXPECTED_ATTEMPT9_RECEIPT_SHA256
            or not ATTEMPT9_RECEIPT_PATH.is_file()
            or _sha256(ATTEMPT9_RECEIPT_PATH) != EXPECTED_ATTEMPT9_RECEIPT_SHA256
            or not isinstance(invalidation_artifact, dict)
            or invalidation_artifact.get("path") != str(ATTEMPT9_INVALIDATION_PATH.relative_to(ROOT))
            or invalidation_artifact.get("sha256") != EXPECTED_ATTEMPT9_INVALIDATION_SHA256
            or not ATTEMPT9_INVALIDATION_PATH.is_file()
            or _sha256(ATTEMPT9_INVALIDATION_PATH) != EXPECTED_ATTEMPT9_INVALIDATION_SHA256
            or not isinstance(normalized_artifact, dict)
            or normalized_artifact.get("path") != str(ATTEMPT9_RESPONSE_TELEMETRY_PATH.relative_to(ROOT))
            or normalized_artifact.get("sha256") != EXPECTED_ATTEMPT9_RESPONSE_TELEMETRY_SHA256
            or not ATTEMPT9_RESPONSE_TELEMETRY_PATH.is_file()
            or _sha256(ATTEMPT9_RESPONSE_TELEMETRY_PATH) != EXPECTED_ATTEMPT9_RESPONSE_TELEMETRY_SHA256
        ):
            raise RuntimeError("Repair R8 identity, parent R7 binding, or Attempt9 evidence is not authorized.")
        return receipt, artifact
    if attempt == 11:
        attempt10_artifact = trigger.get("attempt_receipt") if isinstance(trigger, dict) else None
        immutable_runtime_artifacts = (
            trigger.get("immutable_runtime_artifacts") if isinstance(trigger, dict) else None
        )
        if (
            artifact["sha256"] != EXPECTED_R9_RECEIPT_SHA256
            or receipt.get("schema_version") != EXPECTED_R9_SCHEMA
            or receipt.get("repair_revision") != EXPECTED_R9_REVISION
            or receipt.get("stale_candidate_id") != EXPECTED_STALE_CANDIDATE_ID
            or not isinstance(parent, dict)
            or parent.get("path") != str(REPAIR_R8_RECEIPT_PATH.relative_to(ROOT))
            or parent.get("sha256") != EXPECTED_R8_RECEIPT_SHA256
            or parent.get("repair_revision") != EXPECTED_R8_REVISION
            or not isinstance(trigger, dict)
            or trigger.get("attempt") != 10
            or trigger.get("root_cause") != EXPECTED_R9_ROOT_CAUSE
            or not isinstance(attempt10_artifact, dict)
            or attempt10_artifact.get("path") != str(ATTEMPT10_RECEIPT_PATH.relative_to(ROOT))
            or attempt10_artifact.get("sha256") != EXPECTED_ATTEMPT10_RECEIPT_SHA256
            or not ATTEMPT10_RECEIPT_PATH.is_file()
            or _sha256(ATTEMPT10_RECEIPT_PATH) != EXPECTED_ATTEMPT10_RECEIPT_SHA256
            or not isinstance(immutable_runtime_artifacts, dict)
        ):
            raise RuntimeError("Repair R9 identity, parent R8 binding, or Attempt10 evidence is not authorized.")
        return receipt, artifact
    if attempt == 12:
        attempt11_artifact = trigger.get("attempt_receipt") if isinstance(trigger, dict) else None
        immutable_runtime_artifacts = (
            trigger.get("immutable_runtime_artifacts") if isinstance(trigger, dict) else None
        )
        if (
            artifact["sha256"] != EXPECTED_R10_RECEIPT_SHA256
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
            or not isinstance(attempt11_artifact, dict)
            or attempt11_artifact.get("path") != str(ATTEMPT11_RECEIPT_PATH.relative_to(ROOT))
            or attempt11_artifact.get("sha256") != EXPECTED_ATTEMPT11_RECEIPT_SHA256
            or not ATTEMPT11_RECEIPT_PATH.is_file()
            or _sha256(ATTEMPT11_RECEIPT_PATH) != EXPECTED_ATTEMPT11_RECEIPT_SHA256
            or not isinstance(immutable_runtime_artifacts, dict)
        ):
            raise RuntimeError("Repair R10 identity, parent R9 binding, or Attempt11 evidence is not authorized.")
        expected_runtime_artifacts = {
            "plan": (
                EVIDENCE_ROOT / "PULL_V0_P1_PUSH_ANCHOR_ATTEMPT11_PLAN.json",
                EXPECTED_ATTEMPT11_PLAN_SHA256,
            ),
            "process_receipt": (
                LOG_ROOT / "attempt11/process_receipt.json",
                EXPECTED_ATTEMPT11_PROCESS_SHA256,
            ),
            "log": (
                LOG_ROOT / "attempt11/stdout_stderr.log",
                EXPECTED_ATTEMPT11_LOG_SHA256,
            ),
            "summary": (
                LOG_ROOT / "attempt11/eval/a2_hold_oracle_summary.json",
                EXPECTED_ATTEMPT11_SUMMARY_SHA256,
            ),
            "metrics": (
                LOG_ROOT / "attempt11/eval/metrics_eval.json",
                EXPECTED_ATTEMPT11_METRICS_SHA256,
            ),
        }
        for name, (artifact_path, expected_sha256) in expected_runtime_artifacts.items():
            artifact_value = immutable_runtime_artifacts.get(name)
            if (
                not isinstance(artifact_value, dict)
                or artifact_value.get("path") != str(artifact_path.relative_to(ROOT))
                or artifact_value.get("sha256") != expected_sha256
                or not artifact_path.is_file()
                or _sha256(artifact_path) != expected_sha256
            ):
                raise RuntimeError(f"Repair R10 immutable runtime artifact binding is invalid: {name}.")
        process_receipt = _read_json(LOG_ROOT / "attempt11/process_receipt.json")
        if (
            process_receipt.get("attempt") != 11
            or process_receipt.get("plan_sha256") != EXPECTED_ATTEMPT11_PLAN_IDENTITY_SHA256
            or process_receipt.get("repair_receipt_sha256") != EXPECTED_R9_RECEIPT_SHA256
            or process_receipt.get("stdout_stderr_sha256") != EXPECTED_ATTEMPT11_LOG_SHA256
            or process_receipt.get("summary_sha256") != EXPECTED_ATTEMPT11_SUMMARY_SHA256
            or process_receipt.get("metrics_sha256") != EXPECTED_ATTEMPT11_METRICS_SHA256
        ):
            raise RuntimeError("Repair R10 process receipt does not preserve Attempt11 bindings.")
        return receipt, artifact
    if attempt == 13:
        invalidation_artifact = trigger.get("invalidation_manifest") if isinstance(trigger, dict) else None
        if (
            artifact["sha256"] != EXPECTED_R11_RECEIPT_SHA256
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
            or not isinstance(invalidation_artifact, dict)
            or invalidation_artifact.get("path") != str(ATTEMPT12_INVALIDATION_PATH.relative_to(ROOT))
            or invalidation_artifact.get("sha256") != EXPECTED_ATTEMPT12_INVALIDATION_SHA256
            or not ATTEMPT12_INVALIDATION_PATH.is_file()
            or _sha256(ATTEMPT12_INVALIDATION_PATH) != EXPECTED_ATTEMPT12_INVALIDATION_SHA256
        ):
            raise RuntimeError("Repair R11 identity, parent R10 binding, or Attempt12 invalidation is not authorized.")
        invalidation = _read_json(ATTEMPT12_INVALIDATION_PATH)
        absence = invalidation.get("absence_of_runtime_artifacts")
        if (
            invalidation.get("preparation_validity") != "PREPARATION_INVALID"
            or invalidation.get("probe_validity") != "NOT_RUN"
            or invalidation.get("runtime_validation") != "NOT_RUN"
            or invalidation.get("pull_mechanism_verdict") != "NOT_ASSESSED"
            or invalidation.get("plan", {}).get("sha256") != EXPECTED_ATTEMPT12_PLAN_SHA256
            or not isinstance(absence, dict)
            or absence.get("process_receipt") is not False
            or absence.get("log") is not False
            or absence.get("summary") is not False
            or absence.get("metrics") is not False
        ):
            raise RuntimeError("Attempt12 invalidation does not preserve the required no-runtime evidence.")
        return receipt, artifact
    if attempt == 14:
        attempt13_artifact = trigger.get("attempt_receipt") if isinstance(trigger, dict) else None
        immutable_runtime_artifacts = (
            trigger.get("immutable_runtime_artifacts") if isinstance(trigger, dict) else None
        )
        if (
            artifact["sha256"] != EXPECTED_R12_RECEIPT_SHA256
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
            raise RuntimeError("Repair R12 identity, parent R11 binding, or Attempt13 evidence is not authorized.")
        expected_artifacts = {
            "plan": (
                EVIDENCE_ROOT / "PULL_V0_P1_PUSH_ANCHOR_ATTEMPT13_PLAN.json",
                EXPECTED_ATTEMPT13_PLAN_SHA256,
            ),
            "process_receipt": (
                LOG_ROOT / "attempt13/process_receipt.json",
                EXPECTED_ATTEMPT13_PROCESS_SHA256,
            ),
            "log": (
                LOG_ROOT / "attempt13/stdout_stderr.log",
                EXPECTED_ATTEMPT13_LOG_SHA256,
            ),
        }
        for name, (artifact_path, expected_sha256) in expected_artifacts.items():
            value = immutable_runtime_artifacts.get(name)
            if (
                not isinstance(value, dict)
                or value.get("path") != str(artifact_path.relative_to(ROOT))
                or value.get("sha256") != expected_sha256
                or not artifact_path.is_file()
                or _sha256(artifact_path) != expected_sha256
            ):
                raise RuntimeError(f"Repair R12 Attempt13 artifact binding is invalid: {name}.")
        attempt13_receipt = _read_json(ATTEMPT13_RECEIPT_PATH)
        application_error = attempt13_receipt.get("application_contract_error")
        if (
            attempt13_receipt.get("schema_version") != "pull_v0_p1_push_anchor_attempt_receipt_v13"
            or attempt13_receipt.get("attempt") != 13
            or attempt13_receipt.get("status") != "APPLICATION_CONFIG_ERROR_BEFORE_PROBE"
            or attempt13_receipt.get("probe_validity") != "NOT_RUN"
            or attempt13_receipt.get("runtime_validation") != "NOT_RUN"
            or attempt13_receipt.get("pull_mechanism_verdict") != "NOT_ASSESSED"
            or attempt13_receipt.get("application_success") is not False
            or attempt13_receipt.get("natural_exit") is not False
            or not isinstance(application_error, dict)
            or application_error.get("exception_type") != EXPECTED_ATTEMPT13_ERROR_TYPE
            or application_error.get("missing_plus_override") != EXPECTED_ATTEMPT13_MISSING_PLUS_OVERRIDE
        ):
            raise RuntimeError("Attempt13 receipt does not preserve the exact pre-probe Hydra failure.")
        plan = _read_json(expected_artifacts["plan"][0])
        if (
            plan.get("plan_sha256") != EXPECTED_ATTEMPT13_PLAN_IDENTITY_SHA256
            or plan.get("repair_receipt", {}).get("path") != str(REPAIR_R11_RECEIPT_PATH.relative_to(ROOT))
            or plan.get("repair_receipt", {}).get("sha256") != EXPECTED_R11_RECEIPT_SHA256
            or EXPECTED_ATTEMPT13_BAD_OVERRIDE not in plan.get("argv", [])
            or EXPECTED_ATTEMPT13_MISSING_PLUS_OVERRIDE in plan.get("argv", [])
        ):
            raise RuntimeError("Attempt13 plan does not preserve the missing-plus override evidence.")
        process_receipt = _read_json(expected_artifacts["process_receipt"][0])
        if (
            process_receipt.get("attempt") != 13
            or process_receipt.get("plan_sha256") != EXPECTED_ATTEMPT13_PLAN_IDENTITY_SHA256
            or process_receipt.get("repair_receipt_sha256") != EXPECTED_R11_RECEIPT_SHA256
            or process_receipt.get("application_success") is not False
            or process_receipt.get("natural_exit") is not False
            or process_receipt.get("returncode") != 1
            or process_receipt.get("summary_path") is not None
            or process_receipt.get("metrics_path") is not None
        ):
            raise RuntimeError("Attempt13 process receipt does not preserve the application failure boundary.")
        log_text = expected_artifacts["log"][0].read_text(encoding="utf-8", errors="replace")
        if (
            f"hydra.errors.{EXPECTED_ATTEMPT13_ERROR_TYPE}" not in log_text
            or "Could not override 'env.config.max_stage_time'." not in log_text
            or f"To append to your config use {EXPECTED_ATTEMPT13_MISSING_PLUS_OVERRIDE}" not in log_text
        ):
            raise RuntimeError("Attempt13 log does not preserve the exact missing-plus message.")
        return receipt, artifact
    if attempt == 15:
        attempt14_artifact = trigger.get("attempt_receipt") if isinstance(trigger, dict) else None
        if (
            artifact["sha256"] != EXPECTED_R13_RECEIPT_SHA256
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
            raise RuntimeError("Repair R13 identity, parent R12 binding, or Attempt14 invalidation is not authorized.")
        attempt14_receipt = _read_json(ATTEMPT14_RECEIPT_PATH)
        evidence = attempt14_receipt.get("evidence")
        resource_stop = attempt14_receipt.get("resource_stop")
        if (
            attempt14_receipt.get("schema_version") != "pull_v0_p1_push_anchor_attempt_receipt_v14"
            or attempt14_receipt.get("attempt") != 14
            or attempt14_receipt.get("status") != "PROBE_INVALID"
            or attempt14_receipt.get("probe_validity") != "PROBE_INVALID"
            or attempt14_receipt.get("scientific_verdict_consumed") is not False
            or not isinstance(resource_stop, dict)
            or resource_stop.get("triggered") is not True
            or 7 not in resource_stop.get("unauthorized_gpu_indices", [])
            or not isinstance(evidence, dict)
            or evidence.get("plan", {}).get("sha256") != EXPECTED_ATTEMPT14_PLAN_SHA256
            or evidence.get("plan", {}).get("plan_sha256") != EXPECTED_ATTEMPT14_PLAN_IDENTITY_SHA256
            or evidence.get("stdout", {}).get("sha256") != EXPECTED_ATTEMPT14_STDOUT_SHA256
            or evidence.get("kit_log", {}).get("sha256") != EXPECTED_ATTEMPT14_KIT_LOG_SHA256
        ):
            raise RuntimeError("Attempt14 invalidation does not preserve the resource-stop evidence.")
        return receipt, artifact
    if attempt == 16:
        attempt15_artifact = trigger.get("attempt_receipt") if isinstance(trigger, dict) else None
        if (
            artifact["sha256"] != EXPECTED_R14_RECEIPT_SHA256
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
            raise RuntimeError("Repair R14 identity, parent R13 binding, or Attempt15 transport failure is not authorized.")
        attempt15_receipt = _read_json(ATTEMPT15_RECEIPT_PATH)
        evidence = attempt15_receipt.get("evidence")
        if (
            attempt15_receipt.get("schema_version") != "pull_v0_p1_push_anchor_attempt_receipt_v15"
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
            != ["--kit_args", SINGLE_GPU_KIT_ARGS]
        ):
            raise RuntimeError("Attempt15 Hydra transport failure evidence is not preserved exactly.")
        return receipt, artifact
    if attempt == 17:
        authority = receipt.get("authority")
        parent = receipt.get("parent_receipt")
        trigger = receipt.get("trigger")
        scope = receipt.get("scope")
        amendments = receipt.get("amendments")
        contract = receipt.get("attempt17_preparation_contract")

        def _artifact_matches(value: object, expected_path: str, expected_sha256: str) -> bool:
            if not isinstance(value, dict) or value.get("path") != expected_path:
                return False
            artifact_path = Path(expected_path)
            if not artifact_path.is_absolute():
                artifact_path = ROOT / artifact_path
            return (
                value.get("sha256") == expected_sha256
                and artifact_path.is_file()
                and _sha256(artifact_path) == expected_sha256
            )

        attempt16_trigger = trigger.get("attempt16") if isinstance(trigger, dict) else None
        footprint_artifact = (
            trigger.get("one_time_vulkan_footprint_receipt") if isinstance(trigger, dict) else None
        )
        infra_artifact = (
            trigger.get("infra_reclassification_receipt") if isinstance(trigger, dict) else None
        )
        if (
            artifact["sha256"] != EXPECTED_GPU_LEASE_AMENDMENT_SHA256
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
                str((EVIDENCE_ROOT / "PULL_V0_P1_PUSH_ANCHOR_ATTEMPT16_PLAN.json").relative_to(ROOT)),
                EXPECTED_ATTEMPT16_PLAN_SHA256,
            )
            or not _artifact_matches(
                attempt16_trigger.get("stdout"),
                "logs_eval/a2_piper_pull_v0/p1_push_anchor/attempt16/stdout_stderr.log",
                EXPECTED_ATTEMPT16_STDOUT_SHA256,
            )
            or not _artifact_matches(
                attempt16_trigger.get("kit_log"),
                "/home/baoquanc/anaconda3/envs/isaaclab/lib/python3.11/site-packages/isaacsim/kit/logs/Kit/Isaac-Sim/5.1/kit_20260804_050202.log",
                EXPECTED_ATTEMPT16_KIT_LOG_SHA256,
            )
            or not _artifact_matches(
                footprint_artifact,
                "scriptsFORhuman/pull_v0/PULL_V0_VULKAN_ENUMERATION_CONTEXT_RECEIPT.json",
                EXPECTED_VULKAN_RECEIPT_SHA256,
            )
            or not _artifact_matches(
                infra_artifact,
                "scriptsFORhuman/pull_v0/PULL_V0_P1_INFRA_RECLASSIFICATION_RECEIPT.json",
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
            or contract.get("hydra_override") != "+a2_pull_v0_renderer_single_gpu=true"
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
        return receipt, artifact
    if attempt == 18:
        parent = receipt.get("parent_receipt")
        trigger = receipt.get("trigger")
        scope = receipt.get("scope")
        source_repair = receipt.get("source_repair")
        if (
            artifact["sha256"] != EXPECTED_R15_RECEIPT_SHA256
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
            or not isinstance(trigger.get("attempt_receipt"), dict)
            or trigger["attempt_receipt"].get("path") != str(ATTEMPT17_RECEIPT_PATH.relative_to(ROOT))
            or trigger["attempt_receipt"].get("sha256") != EXPECTED_ATTEMPT17_RECEIPT_SHA256
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
            for artifact_path in (
                ATTEMPT18_RECEIPT_PATH,
                ATTEMPT18_PLAN_PATH,
                ATTEMPT18_PROCESS_PATH,
                ATTEMPT18_LOG_PATH,
                ATTEMPT18_SUMMARY_PATH,
                ATTEMPT18_METRICS_PATH,
                ATTEMPT18_LAUNCH_OCCUPANCY_PATH,
                ATTEMPT18_STEADY_STATE_FOOTPRINT_PATH,
            ):
                if artifact_path.exists():
                    label = (
                        str(artifact_path.relative_to(ROOT))
                        if artifact_path.is_relative_to(ROOT)
                        else str(artifact_path)
                    )
                    raise RuntimeError(
                        f"R15 preparation validation found pre-existing Attempt18 artifact: {label}"
                    )
        return receipt, artifact
    raise RuntimeError(f"Unsupported repair binding attempt: {attempt}")


def _validate_post_r1_repair_receipt(path: Path) -> dict:
    receipt, _ = _validate_repair_receipt(path, attempt=3)
    return receipt


def _validate_post_r1_summary(summary: Mapping[str, Any]) -> None:
    missing = sorted(set(REQUIRED_SUMMARY_FIELDS) - set(summary))
    if missing:
        raise RuntimeError(f"Post-R1 summary is missing required telemetry fields: {missing}")
    if summary["schema"] != "a2_piper_pull_v0_p1_scripted_probe_runtime_v1":
        raise RuntimeError(f"Unexpected post-R1 summary schema: {summary['schema']!r}")
    if summary["probe_mode"] != "push_anchor":
        raise RuntimeError("Post-R1 summary probe_mode must be push_anchor.")
    if summary["status"] not in ("PASS", "FAIL"):
        raise RuntimeError("Post-R1 summary status must be PASS or FAIL.")
    command_contract = _require_mapping(summary["command_contract"], "summary.command_contract")
    if set(command_contract) != set(REQUIRED_COMMAND_CONTRACT_FIELDS):
        raise RuntimeError("Post-R1 command_contract fields are incomplete or unexpected.")
    if command_contract["commandable_dofs_only"] is not True:
        raise RuntimeError("Post-R1 command contract must be commandable-DOF only.")
    if command_contract["low_level_usd_runtime_writes"] is not False:
        raise RuntimeError("Post-R1 command contract must prohibit low-level USD runtime writes.")
    acquisition = _require_mapping(summary["acquisition_contract"], "summary.acquisition_contract")
    if set(acquisition) != set(REQUIRED_ACQUISITION_FIELDS):
        raise RuntimeError("Post-R1 acquisition_contract fields are incomplete or unexpected.")
    if acquisition["enabled"] is not True or acquisition["stage2_grasp_gate_required"] is not False:
        raise RuntimeError("Post-R1 acquisition contract does not prove stage-2-gate-free admission.")
    if acquisition["stage0_predicates_reported_separately"] is not True:
        raise RuntimeError("Post-R1 acquisition contract must report stage-0 predicates separately.")
    if acquisition["proof_world_direction"] != "+X":
        raise RuntimeError("Post-R1 acquisition contract proof direction must be +X.")
    for field in ("per_env_outcome", "per_env_proof_samples", "per_env_arc_samples"):
        if not isinstance(summary[field], list) or len(summary[field]) != 1:
            raise RuntimeError(f"{field} must be a one-environment list.")
    _require_bool_list(summary["per_env_pass"], "summary.per_env_pass")
    _require_bool_list(summary["per_env_proof_completed"], "summary.per_env_proof_completed")
    _require_bool_list(summary["per_env_latch_released"], "summary.per_env_latch_released")
    _require_numeric_list(
        summary["per_env_max_hinge_rad"],
        "summary.per_env_max_hinge_rad",
        allow_none=True,
    )
    _require_numeric_list(summary["per_env_max_body_force_n"], "summary.per_env_max_body_force_n")
    if summary["finalize_called"] is not True:
        raise RuntimeError("Post-R1 summary finalize_called must be true.")


def _validate_post_r1_metrics(metrics: Mapping[str, Any]) -> Mapping[str, Any]:
    for field in (
        "completed_episodes",
        "episode_terminal_reasons",
        "episode_max_stage_reached",
        "episode_terminal_diagnostics",
    ):
        if field not in metrics:
            raise RuntimeError(f"Post-R1 metrics are missing {field}.")
    if metrics["completed_episodes"] != 1:
        raise RuntimeError("Post-R1 metrics must contain exactly one completed episode.")
    diagnostics = metrics["episode_terminal_diagnostics"]
    if not isinstance(diagnostics, list) or len(diagnostics) != 1:
        raise RuntimeError("Post-R1 metrics must contain one terminal diagnostic record.")
    terminal = _require_mapping(diagnostics[0], "metrics.episode_terminal_diagnostics[0]")
    missing = sorted(set(REQUIRED_TERMINAL_FIELDS) - set(terminal))
    if missing:
        raise RuntimeError(f"Post-R1 terminal diagnostics are missing required fields: {missing}")
    stage0 = _require_mapping(terminal["pull_v0_stage0_predicates"], "terminal.pull_v0_stage0_predicates")
    if set(stage0) != {"staging_band", "arm_default", "base_still", "event_admission"}:
        raise RuntimeError("Post-R1 stage-0 predicate telemetry fields are incomplete.")
    scripted = _require_mapping(terminal["pull_v0_scripted_activation"], "terminal.pull_v0_scripted_activation")
    if set(scripted) != {"first_control_step", "admission_stage2_grasp_gate", "proof_world_direction"}:
        raise RuntimeError("Post-R1 scripted activation telemetry fields are incomplete.")
    if scripted["admission_stage2_grasp_gate"] is not False or scripted["proof_world_direction"] != "+X":
        raise RuntimeError("Post-R1 scripted activation telemetry has invalid admission or direction.")
    episode = _require_mapping(terminal["pull_v0_episode"], "terminal.pull_v0_episode")
    event_reached = _require_mapping(episode.get("event_reached"), "terminal.pull_v0_episode.event_reached")
    for event_name in (
        "E0_RESET_VALID",
        "E1_OUTSIDE_FACE_PREGRASP",
        "E2_TENSILE_CAPTURE",
        "E3_LATCH_RELEASE",
        "E4_POSITIVE_HINGE_RETAINED",
        "E5_CLEARANCE_DECISION",
        "E6_PATH_REVERSAL_ENTRY",
        "E7_WHOLE_BODY_CLEAR",
    ):
        if not isinstance(event_reached.get(event_name), bool):
            raise RuntimeError(f"Post-R1 event telemetry missing bool {event_name}.")
    return terminal


def classify_post_r1_attempt(
    *,
    process_receipt: Mapping[str, Any],
    summary: Mapping[str, Any],
    metrics: Mapping[str, Any],
) -> dict[str, Any]:
    """Classify probe validity without making a pull-mechanism verdict."""

    _validate_post_r1_summary(summary)
    terminal = _validate_post_r1_metrics(metrics)
    if (
        process_receipt.get("application_success") is not True
        or process_receipt.get("natural_exit") is not True
        or process_receipt.get("returncode") != 0
    ):
        return {
            "status": "BLOCKED",
            "probe_validity": "PROBE_INVALID",
            "admission_blocker": "APPLICATION_LIFECYCLE_FAILURE",
            "pull_mechanism_verdict": "NOT_ASSESSED",
        }
    summary_proof = summary["per_env_proof_completed"][0]
    summary_latch = summary["per_env_latch_released"][0]
    summary_hinge = summary["per_env_max_hinge_rad"][0]
    summary_body_force = summary["per_env_max_body_force_n"][0]
    events = terminal["pull_v0_episode"]["event_reached"]
    if not summary_proof or not events["E2_TENSILE_CAPTURE"]:
        blocker = "NO_STABLE_BILATERAL_CAPTURE"
    elif not summary_latch or not events["E3_LATCH_RELEASE"]:
        blocker = "LATCH_RELEASE_NOT_REACHED"
    elif (
        summary_hinge is None
        or summary_hinge < 0.25
        or not events["E4_POSITIVE_HINGE_RETAINED"]
    ):
        blocker = "HINGE_PROGRESS_BELOW_0P25_RAD"
    elif summary_body_force > 1.0:
        blocker = "BODY_PANEL_CONTACT_EXCEEDED_THRESHOLD"
    elif not events["E5_CLEARANCE_DECISION"]:
        blocker = "MEASURED_CLEARANCE_DECISION_NOT_REACHED"
    elif not events["E7_WHOLE_BODY_CLEAR"]:
        blocker = "WHOLE_BODY_CLEAR_NOT_REACHED"
    elif summary["per_env_pass"][0] is not True:
        blocker = "SUMMARY_PER_ENV_PASS_FALSE"
    elif summary["status"] != "PASS":
        blocker = "SUMMARY_STATUS_NOT_PASS"
    else:
        return {
            "status": "PASS",
            "probe_validity": "PROBE_VALID",
            "admission_blocker": None,
            "pull_mechanism_verdict": "NOT_ASSESSED",
        }
    return {
        "status": "BLOCKED",
        "probe_validity": "PROBE_INVALID",
        "admission_blocker": blocker,
        "pull_mechanism_verdict": "NOT_ASSESSED",
    }


def _validate_plan_repair_binding(
    plan: Mapping[str, Any],
    *,
    attempt: int,
    repair_receipt: Mapping[str, Any],
    repair_artifact: Mapping[str, Any],
) -> None:
    if plan.get("attempt") != attempt:
        raise RuntimeError("Plan attempt does not match requested post-repair attempt.")
    if plan.get("implementation_repair_used") is not True:
        raise RuntimeError("Post-repair plan must mark implementation_repair_used=true.")
    if not isinstance(plan.get("plan_sha256"), str) or not plan["plan_sha256"]:
        raise RuntimeError("Post-repair plan must include a non-empty plan_sha256.")
    binding = _require_mapping(plan.get("repair_receipt"), "plan.repair_receipt")
    expected = {
        "path": repair_artifact["path"],
        "sha256": repair_artifact["sha256"],
        "revision": repair_receipt["repair_revision"],
        "stale_candidate_id": EXPECTED_STALE_CANDIDATE_ID,
    }
    for field, value in expected.items():
        if binding.get(field) != value:
            raise RuntimeError(f"Plan Repair receipt binding mismatch for {field}.")
    if repair_receipt["repair_revision"] in (
        "R2", "R3", "R4", "R5", "R6", "R7", "R8", "R9", "R10", "R11", "R12", "R13", "R14", "A4_A6", "R15", "R16"
    ):
        parent_sha = repair_receipt.get("parent_receipt", {}).get("sha256")
        if binding.get("parent_receipt_sha256") != parent_sha:
            raise RuntimeError(
                f"Plan Repair {repair_receipt['repair_revision']} parent receipt hash binding is missing or incorrect."
            )
    if repair_receipt["repair_revision"] == "R16":
        capacity_contract = _require_mapping(
            plan.get("detailed_contact_capacity_contract"),
            "plan.detailed_contact_capacity_contract",
        )
        expected_capacity_contract = {
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
        if dict(capacity_contract) != expected_capacity_contract:
            raise RuntimeError(
                "Attempt19 plan detailed contact-capacity contract is not the approved R16 contract."
            )


def _validate_process_artifacts(
    process_receipt: Mapping[str, Any],
    *,
    attempt: int,
    plan_artifact: Mapping[str, Any],
    plan_sha256: str,
    log_artifact: Mapping[str, Any],
    repair_artifact: Mapping[str, Any],
    process_artifact: Mapping[str, Any],
) -> None:
    if process_receipt.get("schema_version") != "pull_v0_p1_push_anchor_process_v1":
        raise RuntimeError("Process receipt schema is not the post-repair runner schema.")
    if process_receipt.get("attempt") != attempt:
        raise RuntimeError("Process receipt attempt does not match requested post-repair attempt.")
    for field, expected_artifact in (
        ("plan_path", plan_artifact),
        ("stdout_stderr_path", log_artifact),
    ):
        if process_receipt.get(field) != expected_artifact["path"]:
            raise RuntimeError(f"Process receipt {field} does not identify the supplied artifact.")
    if process_receipt.get("plan_sha256") != plan_sha256:
        raise RuntimeError("Process receipt plan hash does not match the plan identity.")
    if process_receipt.get("stdout_stderr_sha256") != log_artifact["sha256"]:
        raise RuntimeError("Process receipt log hash does not match the log artifact.")
    if process_receipt.get("repair_receipt_sha256") != repair_artifact["sha256"]:
        raise RuntimeError("Process receipt Repair hash binding is missing or incorrect.")


def _build_attempt3_contract_failure_receipt(
    *,
    repair_receipt: Mapping[str, Any],
    repair_artifact: Mapping[str, Any],
    plan_artifact: Mapping[str, Any],
    process_artifact: Mapping[str, Any],
    log_artifact: Mapping[str, Any],
    process_receipt: Mapping[str, Any],
    log_text: str,
) -> dict[str, Any]:
    if (
        process_receipt.get("application_success") is not False
        or process_receipt.get("natural_exit") is not True
        or process_receipt.get("returncode") != 0
        or process_receipt.get("required_summary_present") is not False
        or process_receipt.get("required_metrics_present") is not False
        or process_receipt.get("summary_path") is not None
        or process_receipt.get("summary_sha256") is not None
        or process_receipt.get("metrics_path") is not None
        or process_receipt.get("metrics_sha256") is not None
    ):
        raise RuntimeError("Attempt3 process receipt does not prove the pre-probe lifecycle failure.")
    if EXPECTED_ATTEMPT3_ERROR_SIGNATURE not in log_text:
        raise RuntimeError(
            "Attempt3 log does not contain the exact tensor-device contract TypeError signature."
        )
    return {
        "schema_version": "pull_v0_p1_push_anchor_attempt_receipt_v3",
        "generated_at_hkt": _hkt_now(),
        "attempt": 3,
        "status": "BLOCKED",
        "probe_validity": "PROBE_INVALID",
        "admission_blocker": "APPLICATION_CONTRACT_ERROR_BEFORE_PROBE",
        "pull_mechanism_verdict": "NOT_ASSESSED",
        "repair_r1": {
            "artifact": dict(repair_artifact),
            "revision": repair_receipt["repair_revision"],
            "stale_candidate_id": repair_receipt["stale_candidate_id"],
        },
        "artifacts": {
            "plan": dict(plan_artifact),
            "process_receipt": dict(process_artifact),
            "log": dict(log_artifact),
            "summary": None,
            "metrics": None,
        },
        "application_contract_error": {
            "stage": "BEFORE_PROBE",
            "exception_type": "TypeError",
            "signature": EXPECTED_ATTEMPT3_ERROR_SIGNATURE,
            "device_contract": "a2_pull_proof_world_offset_x requires torch.device, but the consumer passed str.",
            "summary_present": False,
            "metrics_present": False,
        },
        "hard_gate": {
            "stable_bilateral_capture": "N/A",
            "latch_release": "N/A",
            "hinge_progress_min_rad": "N/A",
            "observed_max_hinge_rad": "N/A",
            "body_panel_contact_allowed": "N/A",
            "observed_max_body_force_n": "N/A",
            "pass": False,
        },
        "required_telemetry": {
            "summary": "N/A; application failed before probe summary generation.",
            "metrics": "N/A; application failed before terminal metrics generation.",
            "pull_mechanism_verdict": "NOT_ASSESSED",
        },
        "threshold_mode": "report_only",
        "unverified_claims": [
            "No IsaacSim/GPU runtime outcome is asserted beyond the captured application error.",
            "No pull-mechanism verdict is asserted because the probe never started.",
        ],
    }


def _build_attempt4_r2_admission_blocker_receipt(
    *,
    repair_receipt: Mapping[str, Any],
    repair_artifact: Mapping[str, Any],
    plan_artifact: Mapping[str, Any],
    process_artifact: Mapping[str, Any],
    log_artifact: Mapping[str, Any],
    summary_artifact: Mapping[str, Any],
    metrics_artifact: Mapping[str, Any],
    process_receipt: Mapping[str, Any],
    summary: Mapping[str, Any],
    metrics: Mapping[str, Any],
) -> dict[str, Any]:
    """Preserve immutable attempt4 as a control-circularity blocker.

    Attempt4 predates the R3 base-owned anchor telemetry.  The builder therefore
    validates only fields actually emitted by that run and records missing
    push-anchor fields as unavailable rather than fabricating them.
    """
    if (
        process_receipt.get("application_success") is not True
        or process_receipt.get("natural_exit") is not True
        or process_receipt.get("returncode") != 0
    ):
        raise RuntimeError("Attempt4 must prove a naturally completed application lifecycle.")
    if (
        summary.get("schema") != "a2_piper_pull_v0_p1_scripted_probe_runtime_v1"
        or summary.get("probe_mode") != "push_anchor"
        or summary.get("status") != "FAIL"
        or summary.get("per_env_outcome") != ["PULL_P1_BODY_COLLISION"]
        or summary.get("per_env_pass") != [False]
        or summary.get("per_env_proof_completed") != [False]
        or summary.get("per_env_latch_released") != [False]
        or summary.get("per_env_max_hinge_rad") != [None]
        or summary.get("per_env_terminal_bilateral_streak") != [0]
        or summary.get("per_env_max_body_force_n") != [3817.004150390625]
        or summary.get("finalize_called") is not True
    ):
        raise RuntimeError("Attempt4 summary does not match the immutable admission blocker.")
    if (
        metrics.get("completed_episodes") != 1
        or metrics.get("episode_max_stage_reached") != [0]
        or metrics.get("episode_terminal_reasons") != ["stage_overtime"]
    ):
        raise RuntimeError("Attempt4 metrics do not preserve stage-0 terminal evidence.")
    diagnostics = metrics.get("episode_terminal_diagnostics")
    if not isinstance(diagnostics, list) or len(diagnostics) != 1:
        raise RuntimeError("Attempt4 metrics must contain one terminal diagnostic record.")
    terminal = _require_mapping(diagnostics[0], "attempt4 terminal diagnostic")
    terminal_body_force = terminal.get("doorframe_contact_force")
    if terminal_body_force != 0.0:
        raise RuntimeError(
            "Attempt4 terminal diagnostic must preserve zero terminal contact force; "
            f"got {terminal_body_force!r}."
        )
    return {
        "schema_version": "pull_v0_p1_push_anchor_attempt_receipt_v4",
        "generated_at_hkt": _hkt_now(),
        "attempt": 4,
        "status": "BLOCKED",
        "probe_validity": "PROBE_INVALID",
        "admission_blocker": "ACQUISITION_CONTROL_CIRCULARITY_AND_TELEMETRY_INCOMPLETE",
        "pull_mechanism_verdict": "NOT_ASSESSED",
        "repair_r2": {
            "artifact": dict(repair_artifact),
            "revision": repair_receipt["repair_revision"],
            "stale_candidate_id": repair_receipt["stale_candidate_id"],
        },
        "artifacts": {
            "plan": dict(plan_artifact),
            "process_receipt": dict(process_artifact),
            "log": dict(log_artifact),
            "summary": dict(summary_artifact),
            "metrics": dict(metrics_artifact),
        },
        "observed": {
            "running_max_filtered_body_panel_contact_n": 3817.004150390625,
            "terminal_body_panel_contact_n": 0.0,
            "terminal_stage": 0,
            "terminal_reason": "stage_overtime",
            "stage0_trace": "N/A; attempt4 predates R3 base push-anchor trace export.",
        },
        "causality": {
            "classification": "INCONCLUSIVE",
            "reason": (
                "The running-max filtered body-panel contact is non-zero while the "
                "terminal diagnostic force is zero; immutable attempt4 has no base "
                "push-anchor per-step trace to establish ordering or causality."
            ),
        },
        "hard_gate": {
            "stable_bilateral_capture": "N/A",
            "latch_release": "N/A",
            "hinge_progress_min_rad": "N/A",
            "observed_max_hinge_rad": "N/A",
            "body_panel_contact_allowed": False,
            "observed_running_max_body_force_n": 3817.004150390625,
            "observed_terminal_body_force_n": 0.0,
            "pass": False,
        },
        "required_telemetry": {
            "summary": "validated immutable attempt4 summary fields only",
            "metrics": "validated immutable attempt4 terminal stage/reason and zero terminal force",
            "base_push_anchor_trace": "N/A; absent from immutable attempt4",
            "pull_mechanism_verdict": "NOT_ASSESSED",
        },
        "threshold_mode": "report_only",
        "unverified_claims": [
            "No pull-mechanism verdict is consumed from attempt4.",
            "Contact causality is INCONCLUSIVE without the R3 base push-anchor trace.",
            "No attempt5 runtime outcome is asserted by this receipt.",
        ],
    }


def _validate_actual_push_anchor_schema(
    *,
    summary: Mapping[str, Any],
    metrics: Mapping[str, Any],
    require_stage0_response: bool = False,
    attempt: int | None = None,
) -> Mapping[str, Any]:
    """Validate the base-owned push-anchor schema emitted by attempt 5."""
    if (
        summary.get("schema") != "a2_piper_pull_v0_p1_scripted_probe_runtime_v1"
        or summary.get("probe_mode") != "push_anchor"
        or summary.get("status") not in ("PASS", "FAIL")
    ):
        raise RuntimeError("Actual push-anchor summary schema is invalid.")
    for field in (
        "per_env_outcome",
        "per_env_pass",
        "per_env_proof_completed",
        "per_env_latch_released",
        "per_env_max_hinge_rad",
        "per_env_max_body_force_n",
        "finalize_called",
    ):
        if field not in summary:
            raise RuntimeError(f"Actual push-anchor summary is missing {field!r}.")
    expected_max_stage = [4] if attempt in (10, 17, 18, 19) else [0]
    if (
        metrics.get("completed_episodes") != 1
        or metrics.get("episode_max_stage_reached") != expected_max_stage
        or metrics.get("episode_terminal_reasons") != ["stage_overtime"]
    ):
        raise RuntimeError("Actual push-anchor metrics do not preserve the attempt5 stage-0 terminal.")
    diagnostics = metrics.get("episode_terminal_diagnostics")
    if not isinstance(diagnostics, list) or len(diagnostics) != 1:
        raise RuntimeError("Actual push-anchor metrics require one terminal diagnostic.")
    terminal = _require_mapping(diagnostics[0], "actual terminal diagnostic")
    admission = _require_mapping(
        terminal.get("push_anchor_admission"),
        "actual terminal diagnostic.push_anchor_admission",
    )
    if admission.get("schema") != "a2_piper_pull_v0_push_anchor_admission_terminal_v1":
        raise RuntimeError("Actual push-anchor admission schema is not the base terminal schema.")
    if any(str(key).startswith("pull_v0_") for key in admission):
        raise RuntimeError("Base push-anchor admission must not require pull_v0_* namespace fields.")
    required = {
        "trace_step_count",
        "trace_budget_steps",
        "trace",
        "stage0_predicates",
        "scripted_activation",
        "dls_candidate_mask",
        "dls_finally_applied",
        "body_panel_contact_per_filter_max_n",
        "body_panel_contact_total_max_n",
        "first_contact_step",
        "first_contact_phase",
        "first_contact_filter",
        "max_contact_step",
        "max_contact_phase",
        "max_contact_filter",
        "terminal_snapshot",
    }
    missing = sorted(required - set(admission))
    if missing:
        raise RuntimeError(f"Actual push-anchor admission is missing fields: {missing}")
    snapshot = _require_mapping(admission["terminal_snapshot"], "push_anchor_admission.terminal_snapshot")
    if "terminal_body_panel_contact_total_n" not in snapshot:
        raise RuntimeError("Actual push-anchor terminal snapshot lacks current contact force.")
    if not isinstance(admission["trace"], list):
        raise RuntimeError("Actual push-anchor admission trace must be a list.")
    if require_stage0_response:
        _validate_actual_stage0_command_response_contract(summary=summary, admission=admission)
    return admission


def _validate_actual_stage0_command_response_contract(
    *, summary: Mapping[str, Any], admission: Mapping[str, Any]
) -> None:
    """Validate the R7+ two-phase command/response telemetry contract."""
    per_env = summary.get("per_env_stage0_command_response")
    if not isinstance(per_env, list) or len(per_env) != 1:
        raise RuntimeError("R7+ summary requires one per-env stage0 response mapping.")
    summary_response = _require_mapping(per_env[0], "summary.per_env_stage0_command_response[0]")
    if (
        summary_response.get("schema") != "a2_piper_pull_v0_stage0_command_response_summary_v2"
        or summary_response.get("status") != "CAPTURED"
        or summary_response.get("threshold_mode") != "report_only"
    ):
        raise RuntimeError("R7+ stage0 response summary must be CAPTURED v2 report-only telemetry.")
    response_count = summary_response.get("response_count")
    if isinstance(response_count, bool) or not isinstance(response_count, int) or response_count <= 0:
        raise RuntimeError("R7+ stage0 response summary requires a positive response_count.")
    admission_response = _require_mapping(
        admission.get("stage0_command_response"),
        "push_anchor_admission.stage0_command_response",
    )
    if admission_response != summary_response:
        raise RuntimeError("R7+ terminal admission and rollout stage0 response summaries differ.")
    trace = admission["trace"]
    stage0_rows = [
        (index, row)
        for index, row in enumerate(trace)
        if isinstance(row, Mapping) and "stage0_predicates" in row
    ]
    if len(stage0_rows) != response_count:
        raise RuntimeError(
            "R7+ stage0 response count must equal issued stage0 rows: "
            f"responses={response_count}, issued={len(stage0_rows)}."
        )
    responses = summary_response.get("responses")
    if not isinstance(responses, list) or len(responses) != response_count:
        raise RuntimeError("R7+ stage0 response summary.responses count is inconsistent.")
    row_by_index = {index: row for index, row in stage0_rows}
    seen_indices: set[int] = set()

    def finite_vector(value: Any, length: int, label: str) -> list[float]:
        if not isinstance(value, list) or len(value) != length:
            raise RuntimeError(f"{label} must be a numeric list of length {length}.")
        result = []
        for item in value:
            if isinstance(item, bool) or not isinstance(item, (int, float)) or not math.isfinite(float(item)):
                raise RuntimeError(f"{label} must contain finite numeric values.")
            result.append(float(item))
        return result

    def reject_other_attempt_wording(value: Any, label: str) -> None:
        if isinstance(value, str) and re.search(r"\bAttempt\s*\d+\b|\battempt\d+\b", value):
            raise RuntimeError(f"R7+ telemetry contains hard-coded other-attempt wording at {label}.")
        if isinstance(value, Mapping):
            for key, item in value.items():
                reject_other_attempt_wording(item, f"{label}.{key}")
        elif isinstance(value, list):
            for index, item in enumerate(value):
                reject_other_attempt_wording(item, f"{label}[{index}]")

    for response_index, response_value in enumerate(responses):
        response = _require_mapping(response_value, f"R7+ response[{response_index}]")
        reject_other_attempt_wording(response, f"response[{response_index}]")
        if response.get("schema") != "a2_piper_pull_v0_stage0_command_response_v2":
            raise RuntimeError("R7+ response row schema must be v2.")
        generation = response.get("episode_generation")
        row_index = response.get("trace_row_index")
        control_step = response.get("control_step")
        response_step = response.get("response_control_step")
        for value, label in (
            (generation, "episode_generation"),
            (row_index, "trace_row_index"),
            (control_step, "control_step"),
            (response_step, "response_control_step"),
        ):
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise RuntimeError(f"R7+ response {label} must be a non-negative integer.")
        if row_index in seen_indices or row_index not in row_by_index:
            raise RuntimeError("R7+ response trace row identity is missing or duplicated.")
        seen_indices.add(row_index)
        row = row_by_index[row_index]
        if row.get("episode_generation") != generation or row.get("step") != control_step:
            raise RuntimeError("R7+ response generation/row/step identity does not match the trace.")
        if response_step != control_step + 1:
            raise RuntimeError("R7+ response must be captured at the next post-physics control step.")
        raw = finite_vector(response.get("high_level_base_action_raw"), 5, "response.raw")
        trace_raw = finite_vector(response.get("base_action_raw_trace"), 5, "response.trace_raw")
        row_raw = finite_vector(row.get("base_applied_action"), 5, "trace.base_applied_action")
        final = finite_vector(row.get("final_action"), 12, "trace.final_action")
        if raw != trace_raw or raw != row_raw or final[:5] != raw:
            raise RuntimeError("R7+ executor raw action does not equal the exact stage0 trace command.")
        expected = finite_vector(response.get("expected_scaled_body_command"), 5, "response.expected_scaled")
        base_scale = response.get("base_command_scale")
        pitch_scale = response.get("body_pitch_roll_scale")
        if (
            isinstance(base_scale, bool)
            or not isinstance(base_scale, (int, float))
            or not math.isfinite(float(base_scale))
            or float(base_scale) <= 0.0
            or isinstance(pitch_scale, bool)
            or not isinstance(pitch_scale, (int, float))
            or not math.isfinite(float(pitch_scale))
            or float(pitch_scale) <= 0.0
        ):
            raise RuntimeError("R7+ response scaling metadata is invalid.")
        expected_from_raw = [
            raw[0] * float(base_scale),
            raw[1] * float(base_scale),
            raw[2] * float(base_scale),
            max(-1.0, min(1.0, raw[3])) * float(pitch_scale),
            max(-1.0, min(1.0, raw[4])) * float(pitch_scale),
        ]
        if any(not math.isclose(actual, expected_value, rel_tol=1.0e-6, abs_tol=1.0e-6) for actual, expected_value in zip(expected, expected_from_raw)):
            raise RuntimeError("R7+ expected physical scaling does not match raw command metadata.")
        physical = finite_vector(response.get("physical_base_command"), 5, "response.physical")
        clipped = response.get("physical_command_clipped")
        if not isinstance(clipped, bool):
            raise RuntimeError("R7+ response physical_command_clipped must be a bool.")
        if not clipped and any(
            not math.isclose(actual, expected_value, rel_tol=1.0e-6, abs_tol=1.0e-6)
            for actual, expected_value in zip(physical, expected)
        ):
            raise RuntimeError("R7+ unclipped physical command does not equal expected scaling.")
        finite_vector(response.get("downstream_lower_body_command"), 12, "response.lower_body")
        finite_vector(response.get("observed_world_xy_velocity"), 2, "response.velocity")
        finite_vector(response.get("observed_world_xy_displacement"), 2, "response.displacement")
    if seen_indices != set(row_by_index):
        raise RuntimeError("R7+ response rows do not cover every issued stage0 trace row.")


def _normalize_actual_stage0_response_summary(
    response_summary: Mapping[str, Any], *, attempt: int
) -> dict[str, Any]:
    """Keep the validated runtime response evidence when building later receipts.

    R7+ response rows are already checked by
    ``_validate_actual_stage0_command_response_contract``.  This helper only
    projects the exact summary aggregates and boundary identities into a
    compact receipt payload; it deliberately refuses a missing or null
    response instead of falling back to static wording.
    """
    if (
        response_summary.get("schema")
        != "a2_piper_pull_v0_stage0_command_response_summary_v2"
        or response_summary.get("status") != "CAPTURED"
        or response_summary.get("threshold_mode") != "report_only"
    ):
        raise RuntimeError(
            f"Attempt{attempt} requires a captured R7+ stage0 response summary; "
            f"got {response_summary.get('status')!r}."
        )
    response_count = response_summary.get("response_count")
    responses = response_summary.get("responses")
    if (
        isinstance(response_count, bool)
        or not isinstance(response_count, int)
        or response_count <= 0
        or not isinstance(responses, list)
        or len(responses) != response_count
    ):
        raise RuntimeError(f"Attempt{attempt} stage0 response summary count is invalid.")
    first = _require_mapping(responses[0], f"attempt{attempt} first stage0 response")
    terminal = _require_mapping(
        response_summary.get("terminal_response"),
        f"attempt{attempt} terminal stage0 response",
    )

    def identity(response: Mapping[str, Any], label: str) -> dict[str, int]:
        result: dict[str, int] = {}
        for field in (
            "episode_generation",
            "trace_row_index",
            "control_step",
            "response_control_step",
        ):
            value = response.get(field)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise RuntimeError(f"{label}.{field} must be a non-negative integer.")
            result[field] = value
        if result["response_control_step"] != result["control_step"] + 1:
            raise RuntimeError(f"{label} must bind the next post-physics control step.")
        return result

    first_identity = identity(first, f"attempt{attempt}.first_response")
    terminal_identity = identity(terminal, f"attempt{attempt}.terminal_response")
    expected_aggregates = (
        "anti_alignment_count",
        "max_observed_world_xy_speed_mps",
        "max_observed_world_xy_displacement_m",
        "min_progress_velocity_cosine",
        "min_progress_displacement_cosine",
    )
    aggregates: dict[str, Any] = {}
    for field in expected_aggregates:
        value = response_summary.get(field)
        if field.startswith("min_progress_") and value is None:
            aggregates[field] = None
            continue
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
            raise RuntimeError(f"Attempt{attempt} response aggregate {field} is invalid.")
        aggregates[field] = float(value) if field != "anti_alignment_count" else int(value)
    return {
        "schema": response_summary["schema"],
        "status": response_summary["status"],
        "runtime_validation": "VALIDATED_ACTUAL_R7_PLUS_RESPONSE_TELEMETRY",
        "threshold_mode": response_summary["threshold_mode"],
        "response_count": response_count,
        "first_response_identity": first_identity,
        "terminal_response_identity": terminal_identity,
        "aggregates": aggregates,
    }


def _build_attempt5_r3_reset_boundary_blocker_receipt(
    *,
    repair_receipt: Mapping[str, Any],
    repair_artifact: Mapping[str, Any],
    plan_artifact: Mapping[str, Any],
    process_artifact: Mapping[str, Any],
    log_artifact: Mapping[str, Any],
    summary_artifact: Mapping[str, Any],
    metrics_artifact: Mapping[str, Any],
    process_receipt: Mapping[str, Any],
    summary: Mapping[str, Any],
    metrics: Mapping[str, Any],
) -> dict[str, Any]:
    admission = _validate_actual_push_anchor_schema(
        summary=summary,
        metrics=metrics,
        require_stage0_response=False,
    )
    if (
        process_receipt.get("application_success") is not True
        or process_receipt.get("natural_exit") is not True
        or process_receipt.get("returncode") != 0
        or summary.get("status") != "FAIL"
        or summary.get("per_env_outcome") != ["PULL_P1_BODY_COLLISION"]
        or summary.get("per_env_pass") != [False]
        or summary.get("per_env_proof_completed") != [False]
        or summary.get("per_env_latch_released") != [False]
        or summary.get("per_env_max_hinge_rad") != [None]
        or summary.get("per_env_max_body_force_n") != [3817.004150390625]
        or summary.get("finalize_called") is not True
    ):
        raise RuntimeError("Attempt5 summary does not preserve the immutable reset-boundary blocker.")
    running_max = float(admission["body_panel_contact_total_max_n"])
    terminal_snapshot = _require_mapping(admission["terminal_snapshot"], "attempt5 terminal snapshot")
    terminal_current = float(terminal_snapshot["terminal_body_panel_contact_total_n"])
    terminal_live = metrics["episode_terminal_diagnostics"][0].get("doorframe_contact_force")
    first_step = admission.get("first_contact_step")
    first_filter = admission.get("first_contact_filter")
    if (
        running_max != 3817.004150390625
        or terminal_current != 3817.004150390625
        or terminal_live != 0.0
    ):
        raise RuntimeError(
            "Attempt5 immutable evidence must preserve the pre-R4 running-max-as-terminal artifact."
        )
    if first_step != 0 or first_filter != "trunk":
        raise RuntimeError("Attempt5 immutable evidence must preserve first step/filter contact.")
    return {
        "schema_version": "pull_v0_p1_push_anchor_attempt_receipt_v5",
        "generated_at_hkt": _hkt_now(),
        "attempt": 5,
        "status": "BLOCKED",
        "probe_validity": "PROBE_INVALID",
        "admission_blocker": "RESET_BOUNDARY_CONTACT_UNQUALIFIED_BEFORE_STAGING",
        "pull_mechanism_verdict": "NOT_ASSESSED",
        "repair_r3": {
            "artifact": dict(repair_artifact),
            "revision": repair_receipt["repair_revision"],
            "stale_candidate_id": repair_receipt["stale_candidate_id"],
        },
        "artifacts": {
            "plan": dict(plan_artifact),
            "process_receipt": dict(process_artifact),
            "log": dict(log_artifact),
            "summary": dict(summary_artifact),
            "metrics": dict(metrics_artifact),
        },
        "observed": {
            "running_max_body_panel_contact_n": running_max,
            "terminal_live_body_panel_contact_n": 0.0,
            "terminal_live_diagnostic_body_panel_contact_n": terminal_live,
            "attempt5_terminal_snapshot_body_panel_contact_n": terminal_current,
            "first_contact_step": first_step,
            "first_contact_filter": first_filter,
            "first_contact_phase": admission.get("first_contact_phase"),
            "qualification_persistence": "INCONCLUSIVE",
            "causality": "INCONCLUSIVE",
        },
        "reset_boundary": {
            "blocker": "RESET_BOUNDARY_CONTACT_UNQUALIFIED_BEFORE_STAGING",
            "qualification_window": "N/A; attempt5 predates R4 reset qualification window",
            "persistence": "INCONCLUSIVE",
            "causality": "INCONCLUSIVE",
            "staging_started": False,
            "dls_started": False,
            "trace_sample_before_classification": False,
        },
        "hard_gate": {
            "stable_bilateral_capture": "N/A",
            "latch_release": "N/A",
            "hinge_progress_min_rad": "N/A",
            "observed_max_hinge_rad": "N/A",
            "body_panel_contact_allowed": "N/A",
            "observed_max_body_force_n": "N/A",
            "pass": False,
        },
        "required_telemetry": {
            "summary": "validated actual runtime summary schema",
            "metrics": "validated actual push_anchor_admission terminal schema",
            "pull_mechanism_verdict": "NOT_ASSESSED",
            "legacy_pull_v0_namespace": "not required for base-owned admission",
        },
        "threshold_mode": "report_only",
        "effort_provenance": "ESTIMATE_ONLY",
        "unverified_claims": [
            "No pull-mechanism verdict is asserted.",
            "Contact persistence and command causality are INCONCLUSIVE because attempt5 had no reset-boundary qualification window.",
            "No runtime outcome beyond the immutable attempt5 artifacts is asserted.",
        ],
    }


def _build_attempt6_r4_watchdog_cross_talk_receipt(
    *,
    attempt: int = 6,
    admission: Mapping[str, Any] | None = None,
    repair_receipt: Mapping[str, Any],
    repair_artifact: Mapping[str, Any],
    plan_artifact: Mapping[str, Any],
    process_artifact: Mapping[str, Any],
    log_artifact: Mapping[str, Any],
    summary_artifact: Mapping[str, Any],
    metrics_artifact: Mapping[str, Any],
    process_receipt: Mapping[str, Any],
    summary: Mapping[str, Any],
    metrics: Mapping[str, Any],
) -> dict[str, Any]:
    """Classify immutable Attempt6 as a probe-invalid generic-relief cross-talk."""
    if admission is None:
        admission = _validate_actual_push_anchor_schema(
            summary=summary,
            metrics=metrics,
            require_stage0_response=attempt >= 8,
        )
    if (
        process_receipt.get("application_success") is not True
        or process_receipt.get("natural_exit") is not True
        or process_receipt.get("returncode") != 0
        or summary.get("status") != "FAIL"
        or summary.get("per_env_outcome") != ["BASE_RELIEF_TIMEOUT"]
        or summary.get("per_env_pass") != [False]
        or summary.get("per_env_proof_completed") != [False]
        or summary.get("per_env_latch_released") != [True]
        or summary.get("per_env_max_hinge_rad") != [None]
        or summary.get("per_env_max_body_force_n") != [0.0]
        or summary.get("finalize_called") is not True
    ):
        raise RuntimeError("Attempt6 summary does not preserve the immutable watchdog blocker.")
    reset = _require_mapping(
        admission["reset_contact_qualification"],
        "attempt6 push_anchor_admission.reset_contact_qualification",
    )
    samples = reset.get("samples")
    if (
        reset.get("window_complete") is not True
        or reset.get("reset_transient_observed") is not True
        or reset.get("state_valid") is not True
        or reset.get("result") != "CLEARED"
        or not isinstance(samples, list)
        or len(samples) != 3
    ):
        raise RuntimeError("Attempt6 terminal reset qualification latch is incomplete.")
    trace = admission["trace"]
    if admission["trace_step_count"] != len(trace) or len(trace) <= 60:
        raise RuntimeError("Attempt6 trace must exceed the 60-step generic-relief watchdog window.")
    qualification_rows = [row for row in trace if isinstance(row, Mapping) and "qualification" in row]
    if len(qualification_rows) != 3:
        raise RuntimeError("Attempt6 trace must preserve exactly three reset qualification samples.")
    if any(
        row["qualification"].get("staging_started") is not False
        or row["qualification"].get("dls_started") is not False
        for row in qualification_rows
    ):
        raise RuntimeError("Attempt6 qualification trace shows staging/DLS before reset clearance.")
    stage0_rows = [row for row in trace if isinstance(row, Mapping) and "stage0_predicates" in row]
    if not stage0_rows or any(
        row["stage0_predicates"].get("timeout") is True for row in stage0_rows
    ):
        raise RuntimeError("Attempt6 watchdog blocker must remain distinct from stage0 timeout.")
    terminal_snapshot = _require_mapping(admission["terminal_snapshot"], "attempt6 terminal snapshot")
    current_body_force = float(admission["body_panel_contact_total_current_n"])
    max_body_force = float(admission["body_panel_contact_total_max_n"])
    terminal_current = float(terminal_snapshot["terminal_body_panel_contact_total_n"])
    if current_body_force != 0.0 or terminal_current != 0.0:
        raise RuntimeError("Attempt6 watchdog blocker must have zero post-clearance body contact.")
    return {
        "schema_version": f"pull_v0_p1_push_anchor_attempt_receipt_v{attempt}",
        "generated_at_hkt": _hkt_now(),
        "attempt": attempt,
        "status": "BLOCKED",
        "probe_validity": "PROBE_INVALID",
        "admission_blocker": EXPECTED_R5_ROOT_CAUSE,
        "pull_mechanism_verdict": "NOT_ASSESSED",
        f"repair_{repair_receipt['repair_revision'].lower()}": {
            "artifact": dict(repair_artifact),
            "revision": repair_receipt["repair_revision"],
            "stale_candidate_id": repair_receipt["stale_candidate_id"],
        },
        "artifacts": {
            "plan": dict(plan_artifact),
            "process_receipt": dict(process_artifact),
            "log": dict(log_artifact),
            "summary": dict(summary_artifact),
            "metrics": dict(metrics_artifact),
        },
        "observed": {
            "summary_outcome": "BASE_RELIEF_TIMEOUT",
            "trace_step_count": len(trace),
            "generic_relief_timeout_steps": 60,
            "stage0_timeout_observed": False,
            "dls_finally_applied": bool(admission["dls_finally_applied"]),
            "reset_contact_qualification_complete": bool(reset["window_complete"]),
            "reset_transient_observed": bool(reset["reset_transient_observed"]),
            "terminal_body_panel_contact_current_n": terminal_current,
            "body_panel_contact_max_n": max_body_force,
            "max_contact_phase": admission.get("max_contact_phase"),
            "max_contact_step": admission.get("max_contact_step"),
        },
        "watchdog_cross_talk": {
            "blocker": EXPECTED_R5_ROOT_CAUSE,
            "mechanism": (
                "The generic DLS/base-relief state advanced during explicit P1 acquisition-wait "
                "after reset clearance and produced BASE_RELIEF_TIMEOUT before stage0 admission could finish."
            ),
            "qualification_trace_preserved": True,
            "stage0_timeout_independent": True,
            "non_p1_generic_relief_semantics": "UNVERIFIED_STATIC_CONTRACT_ONLY",
        },
        "reset_boundary": {
            "qualification_window_steps": int(reset["window_steps"]),
            "window_complete": bool(reset["window_complete"]),
            "transient_observed": bool(reset["reset_transient_observed"]),
            "result": reset["result"],
            "staging_started_during_window": False,
            "dls_started_during_window": False,
        },
        "hard_gate": {
            "stable_bilateral_capture": False,
            "latch_release": True,
            "hinge_progress_min_rad": 0.25,
            "observed_max_hinge_rad": "N/A",
            "body_panel_contact_allowed": False,
            "observed_max_body_force_n": "N/A; reset transient only",
            "pass": False,
        },
        "required_telemetry": {
            "summary": "validated actual runtime summary schema",
            "metrics": "validated actual base-owned push_anchor_admission terminal schema",
            "reset_contact_qualification": "validated terminal pre-reset latch and trace samples",
            "pull_mechanism_verdict": "NOT_ASSESSED",
            "legacy_pull_v0_namespace": "not required for base-owned admission",
        },
        "threshold_mode": "report_only",
        "effort_provenance": "ESTIMATE_ONLY",
        "runtime_validation": "NOT_ASSESSED",
        "unverified_claims": [
            "No pull-mechanism verdict is asserted.",
            "Attempt6 is probe-invalid because generic base-relief watchdog cross-talk precluded stage0 admission assessment.",
            "No runtime PASS is asserted for the R5 repair; an authorized follow-up runtime is required before assessing it.",
        ],
    }


def _attempt_timeout_from_plan(plan: Mapping[str, Any] | None) -> int | None:
    if plan is None:
        return None
    argv = plan.get("argv")
    if not isinstance(argv, list):
        raise RuntimeError("Attempt10 plan argv must be a list for timeout-budget attribution.")
    prefix = "algo.config.eval.a2_pull_p1_stage0_timeout_steps="
    values = [item[len(prefix) :] for item in argv if isinstance(item, str) and item.startswith(prefix)]
    if len(values) != 1:
        raise RuntimeError("Attempt10 plan must contain exactly one stage0 timeout override.")
    try:
        timeout_steps = int(values[0])
    except ValueError as exc:
        raise RuntimeError("Attempt10 stage0 timeout override must be an integer.") from exc
    if timeout_steps <= 0:
        raise RuntimeError("Attempt10 stage0 timeout override must be positive.")
    return timeout_steps


def _attempt10_budget_analysis(
    *,
    attempt: int,
    plan: Mapping[str, Any] | None,
    stage0_rows: list[Mapping[str, Any]],
    response_summary: Mapping[str, Any],
) -> dict[str, Any] | None:
    if attempt < 10:
        return None
    if not stage0_rows:
        raise RuntimeError("Attempt10 budget analysis requires stage0 trace rows.")
    residuals: list[float] = []
    for index, row in enumerate(stage0_rows):
        target_residuals = _require_mapping(row.get("target_residuals"), f"stage0 row {index}.target_residuals")
        value = target_residuals.get("stage0_horizontal_m")
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
            raise RuntimeError(f"stage0 row {index}.stage0_horizontal_m must be finite.")
        residuals.append(float(value))
    increases = sum(next_value > value + 1.0e-12 for value, next_value in zip(residuals, residuals[1:]))
    if increases:
        raise RuntimeError(f"Attempt{attempt} stage0 horizontal residual is not monotonic: increases={increases}.")
    initial_residual = residuals[0]
    terminal_residual = residuals[-1]
    if attempt == 10:
        _assert_close(initial_residual, 0.9215447306632996, "attempt10 initial_stage0_horizontal_m")
        if response_summary.get("response_count") != 120:
            raise RuntimeError("Attempt10 must preserve exactly 120 response rows.")
        if response_summary.get("anti_alignment_count") != 0:
            raise RuntimeError("Attempt10 must preserve zero anti-alignment responses.")
    configured_timeout_steps = _attempt_timeout_from_plan(plan)
    if configured_timeout_steps is None:
        configured_timeout_steps = 120
    physical_speed_mps = 0.15
    control_dt_s = 0.02
    settle_steps = 5
    distance_per_control_step_m = physical_speed_mps * control_dt_s
    kinematic_lower_bound_steps = math.ceil(initial_residual / distance_per_control_step_m)
    minimum_with_settle_steps = kinematic_lower_bound_steps + settle_steps
    if configured_timeout_steps >= minimum_with_settle_steps:
        raise RuntimeError("Attempt10 timeout budget is not below the measured staging lower bound.")
    return {
        "initial_stage0_horizontal_m": initial_residual,
        "terminal_stage0_horizontal_m": terminal_residual,
        "residual_monotonic_nonincreasing": True,
        "residual_increase_count": increases,
        "physical_speed_mps": physical_speed_mps,
        "control_dt_s": control_dt_s,
        "distance_per_control_step_m": distance_per_control_step_m,
        "kinematic_lower_bound_steps": kinematic_lower_bound_steps,
        "settle_steps": settle_steps,
        "minimum_steps_including_settle": minimum_with_settle_steps,
        "configured_timeout_steps": configured_timeout_steps,
        "timeout_shortfall_vs_kinematic_lower_bound_steps": (
            kinematic_lower_bound_steps - configured_timeout_steps
        ),
        "r9_timeout_steps": 360,
        "r9_nominal_horizon_s": 360 * control_dt_s,
        "r9_nominal_travel_m": 360 * distance_per_control_step_m,
        "budget_role": "P1_STAGE0_ADMISSION_WATCHDOG_ONLY",
        "mechanism_threshold": False,
    }


def _build_attempt11_host_stage_overtime_receipt(
    *,
    attempt: int,
    plan: Mapping[str, Any],
    admission: Mapping[str, Any],
    repair_receipt: Mapping[str, Any],
    repair_artifact: Mapping[str, Any],
    plan_artifact: Mapping[str, Any],
    process_artifact: Mapping[str, Any],
    log_artifact: Mapping[str, Any],
    summary_artifact: Mapping[str, Any],
    metrics_artifact: Mapping[str, Any],
    process_receipt: Mapping[str, Any],
    summary: Mapping[str, Any],
    metrics: Mapping[str, Any],
) -> dict[str, Any]:
    """Classify immutable Attempt11 host-stage overtime without relabeling raw output."""
    if attempt != 11:
        raise RuntimeError(f"Host-stage overtime receipt requires Attempt11; got {attempt!r}.")
    if (
        process_receipt.get("application_success") is not True
        or process_receipt.get("natural_exit") is not True
        or process_receipt.get("returncode") != 0
        or summary.get("status") != "FAIL"
        or summary.get("per_env_outcome") != ["ARC_PROBE_TIMEOUT"]
        or summary.get("per_env_pass") != [False]
        or summary.get("per_env_proof_completed") != [False]
        or summary.get("per_env_latch_released") != [True]
        or summary.get("per_env_max_hinge_rad") != [None]
        or summary.get("per_env_max_body_force_n") != [0.0]
        or summary.get("finalize_called") is not True
    ):
        raise RuntimeError("Attempt11 raw summary does not preserve the ARC probe timeout evidence.")
    diagnostics = metrics.get("episode_terminal_diagnostics")
    if not isinstance(diagnostics, list) or len(diagnostics) != 1:
        raise RuntimeError("Attempt11 metrics require exactly one terminal diagnostic.")
    terminal = _require_mapping(diagnostics[0], "Attempt11 terminal diagnostic")
    if (
        metrics.get("completed_episodes") != 1
        or metrics.get("episode_max_stage_reached") != [0]
        or metrics.get("episode_terminal_reasons") != ["stage_overtime"]
        or terminal.get("stage_buf") != 0
        or terminal.get("time_in_stage_buf") != 250
        or terminal.get("episode_length_buf") != 250
        or terminal.get("terminal_reasons") != "stage_overtime"
    ):
        raise RuntimeError("Attempt11 terminal metrics do not prove stage-0 host overtime.")
    reset = _require_mapping(
        admission.get("reset_contact_qualification"),
        "Attempt11 push_anchor_admission.reset_contact_qualification",
    )
    samples = reset.get("samples")
    if (
        reset.get("window_complete") is not True
        or reset.get("reset_transient_observed") is not True
        or reset.get("state_valid") is not True
        or reset.get("result") != "CLEARED"
        or not isinstance(samples, list)
        or len(samples) != 3
    ):
        raise RuntimeError("Attempt11 reset qualification latch is incomplete.")
    stage0_predicates = _require_mapping(
        admission.get("stage0_predicates"),
        "Attempt11 push_anchor_admission.stage0_predicates",
    )
    if stage0_predicates != {
        "staging_band": False,
        "settle_count": 0,
        "timed_out": False,
    }:
        raise RuntimeError("Attempt11 local stage0 watchdog predicate must remain false.")
    trace = admission.get("trace")
    if not isinstance(trace, list) or len(trace) != 250:
        raise RuntimeError("Attempt11 host-overtime trace must contain exactly 250 rows.")
    stage0_rows = [
        row for row in trace if isinstance(row, Mapping) and "stage0_predicates" in row
    ]
    response_summary = _require_mapping(
        admission.get("stage0_command_response"),
        "Attempt11 push_anchor_admission.stage0_command_response",
    )
    normalized_response = _normalize_actual_stage0_response_summary(
        response_summary, attempt=attempt
    )
    if (
        len(stage0_rows) != 247
        or response_summary.get("response_count") != 247
        or response_summary.get("anti_alignment_count") != 0
    ):
        raise RuntimeError("Attempt11 response telemetry does not preserve 247 aligned rows.")
    residuals = [
        float(_require_mapping(row.get("target_residuals"), "Attempt11 target residuals").get("stage0_horizontal_m"))
        for row in stage0_rows
    ]
    if (
        not residuals
        or residuals[0] != 0.9215447306632996
        or residuals[-1] != 0.005086362361907959
        or any(next_value > value + 1.0e-12 for value, next_value in zip(residuals, residuals[1:]))
    ):
        raise RuntimeError("Attempt11 residual telemetry is not monotonic with the canonical endpoints.")
    timeout_steps = _attempt_timeout_from_plan(plan)
    if timeout_steps != 360:
        raise RuntimeError(f"Attempt11 local watchdog must be exactly 360 steps; got {timeout_steps!r}.")
    reset_steps = 3
    host_stage_steps = int(terminal["time_in_stage_buf"])
    if host_stage_steps >= reset_steps + timeout_steps:
        raise RuntimeError("Attempt11 host-stage overtime evidence must precede the local watchdog horizon.")
    return {
        "schema_version": "pull_v0_p1_push_anchor_attempt_receipt_v11",
        "generated_at_hkt": _hkt_now(),
        "attempt": 11,
        "status": "BLOCKED",
        "probe_validity": "PROBE_INVALID",
        "admission_blocker": EXPECTED_R10_ROOT_CAUSE,
        "pull_mechanism_verdict": "NOT_ASSESSED",
        "repair_r9": {
            "artifact": dict(repair_artifact),
            "revision": repair_receipt["repair_revision"],
            "stale_candidate_id": repair_receipt["stale_candidate_id"],
        },
        "artifacts": {
            "plan": dict(plan_artifact),
            "process_receipt": dict(process_artifact),
            "log": dict(log_artifact),
            "summary": dict(summary_artifact),
            "metrics": dict(metrics_artifact),
        },
        "observed": {
            "raw_summary_outcome": "ARC_PROBE_TIMEOUT",
            "classified_outcome": "PULL_P1_STAGE0_HOST_STAGE_OVERTIME",
            "trace_step_count": len(trace),
            "stage0_response_rows": len(stage0_rows),
            "response_count": 247,
            "anti_alignment_count": 0,
            "residual_initial_m": residuals[0],
            "residual_terminal_m": residuals[-1],
            "residual_monotonic_nonincreasing": True,
            "local_stage0_timeout_observed": False,
            "terminal_reason": "stage_overtime",
        },
        "host_stage_timer": {
            "actual_device_local_stage_timer_steps": host_stage_steps,
            "configured_host_stage_budget_steps": host_stage_steps,
            "reset_qualification_steps": reset_steps,
            "local_stage0_watchdog_steps": timeout_steps,
            "host_budget_less_than_reset_plus_local_watchdog": True,
            "terminal_reason": "stage_overtime",
            "classification_basis": (
                "terminal stage-0 host stage_overtime at the configured host-stage budget; "
                "local stage0 predicate remained untimed_out"
            ),
        },
        "command_to_plant_response": {
            **normalized_response,
            "admission_field_present": True,
        },
        "stage0_timeout_boundary": {
            "blocker": EXPECTED_R10_ROOT_CAUSE,
            "local_watchdog_timeout_observed": False,
            "host_stage_overtime_observed": True,
            "response_metrics_report_only": True,
            "signed_target_and_band_unchanged": True,
        },
        "reset_boundary": {
            "qualification_window_steps": int(reset["window_steps"]),
            "window_complete": bool(reset["window_complete"]),
            "transient_observed": bool(reset["reset_transient_observed"]),
            "result": reset["result"],
            "staging_started_during_window": False,
            "dls_started_during_window": False,
        },
        "hard_gate": {
            "stable_bilateral_capture": False,
            "latch_release": True,
            "hinge_progress_min_rad": 0.25,
            "observed_max_hinge_rad": "N/A",
            "body_panel_contact_allowed": False,
            "observed_max_body_force_n": 0.0,
            "pass": False,
        },
        "quaternion_contract_closure": {
            "source": "canonical ArticulationData.root_quat_w WXYZ",
            "response_rows": 247,
            "anti_alignment_count": 0,
            "residual_monotonic_nonincreasing": True,
            "runtime_validation": "VALIDATED_ACTUAL_R7_PLUS_RESPONSE_TELEMETRY",
        },
        "required_telemetry": {
            "summary": "validated immutable Attempt11 summary with raw ARC label",
            "metrics": "validated immutable base-owned push_anchor_admission stage-overtime terminal",
            "host_stage_timer": "measured from terminal stage-0 stage_overtime boundary",
            "local_stage0_watchdog": "report-only; not reached",
            "pull_mechanism_verdict": "NOT_ASSESSED",
        },
        "threshold_mode": "report_only",
        "effort_provenance": "ESTIMATE_ONLY",
        "runtime_validation": "VALIDATED_ACTUAL_R7_PLUS_RESPONSE_TELEMETRY",
        "unverified_claims": [
            "No pull-mechanism verdict is asserted.",
            "Attempt11 is probe-invalid because host stage overtime terminated stage0 before the local watchdog horizon.",
            "No Attempt12 runtime or pull-mechanism PASS is asserted.",
        ],
    }


def _build_stage0_timeout_actual_schema_receipt(
    *,
    attempt: int,
    plan: Mapping[str, Any] | None = None,
    admission: Mapping[str, Any],
    repair_receipt: Mapping[str, Any],
    repair_artifact: Mapping[str, Any],
    plan_artifact: Mapping[str, Any],
    process_artifact: Mapping[str, Any],
    log_artifact: Mapping[str, Any],
    summary_artifact: Mapping[str, Any],
    metrics_artifact: Mapping[str, Any],
    process_receipt: Mapping[str, Any],
    summary: Mapping[str, Any],
    metrics: Mapping[str, Any],
) -> dict[str, Any]:
    legacy_unresolved = attempt == 7
    response_summary = admission.get("stage0_command_response")
    if attempt >= 8:
        response_summary = _require_mapping(
            response_summary,
            "stage0-timeout push_anchor_admission.stage0_command_response",
        )
    elif response_summary is not None and not isinstance(response_summary, Mapping):
        raise RuntimeError("Stage0 command-response summary must be a mapping when emitted.")
    """Classify a stage-0 timeout using only the actual base-owned schema."""
    if (
        process_receipt.get("application_success") is not True
        or process_receipt.get("natural_exit") is not True
        or process_receipt.get("returncode") != 0
        or summary.get("status") != "FAIL"
        or summary.get("per_env_outcome") != ["PULL_P1_STAGE0_TIMEOUT"]
        or summary.get("per_env_pass") != [False]
        or summary.get("per_env_proof_completed") != [False]
        or summary.get("per_env_latch_released") != [True]
        or summary.get("per_env_max_hinge_rad") != [None]
        or summary.get("per_env_max_body_force_n") != [0.0]
        or summary.get("finalize_called") is not True
    ):
        raise RuntimeError("Actual push-anchor summary does not preserve the stage0 timeout outcome.")
    reset = _require_mapping(
        admission["reset_contact_qualification"],
        "stage0-timeout push_anchor_admission.reset_contact_qualification",
    )
    samples = reset.get("samples")
    if (
        reset.get("window_complete") is not True
        or reset.get("reset_transient_observed") is not True
        or reset.get("state_valid") is not True
        or reset.get("result") != "CLEARED"
        or not isinstance(samples, list)
        or len(samples) != 3
    ):
        raise RuntimeError("Stage0 timeout terminal reset qualification latch is incomplete.")
    trace = admission["trace"]
    stage0_rows = [row for row in trace if isinstance(row, Mapping) and "stage0_predicates" in row]
    if not stage0_rows:
        raise RuntimeError("Stage0 timeout actual admission trace lacks stage0 predicate rows.")
    normalized_response = (
        _normalize_actual_stage0_response_summary(response_summary, attempt=attempt)
        if attempt >= 9
        else None
    )
    budget_analysis = _attempt10_budget_analysis(
        attempt=attempt,
        plan=plan,
        stage0_rows=stage0_rows,
        response_summary=response_summary,
    )
    return {
        "schema_version": f"pull_v0_p1_push_anchor_attempt_receipt_v{attempt}",
        "generated_at_hkt": _hkt_now(),
        "attempt": attempt,
        "status": "BLOCKED",
        "probe_validity": "PROBE_INVALID",
        "admission_blocker": (
            EXPECTED_R9_ROOT_CAUSE
            if budget_analysis is not None
            else EXPECTED_R6_ROOT_CAUSE
            if legacy_unresolved
            else "PULL_P1_STAGE0_TIMEOUT_WITH_RESPONSE_CAPTURED"
        ),
        "pull_mechanism_verdict": "NOT_ASSESSED",
        f"repair_{repair_receipt['repair_revision'].lower()}": {
            "artifact": dict(repair_artifact),
            "revision": repair_receipt["repair_revision"],
            "stale_candidate_id": repair_receipt["stale_candidate_id"],
        },
        "artifacts": {
            "plan": dict(plan_artifact),
            "process_receipt": dict(process_artifact),
            "log": dict(log_artifact),
            "summary": dict(summary_artifact),
            "metrics": dict(metrics_artifact),
        },
        "observed": {
            "summary_outcome": "PULL_P1_STAGE0_TIMEOUT",
            "trace_step_count": len(trace),
            "stage0_rows": len(stage0_rows),
            "stage0_timeout_predicate_observed": any(
                bool(
                    row["stage0_predicates"].get(
                        "timeout", row["stage0_predicates"].get("timed_out", False)
                    )
                )
                for row in stage0_rows
            ) or bool(
                _require_mapping(
                    admission.get("stage0_predicates"),
                    "stage0-timeout push_anchor_admission.stage0_predicates",
                ).get("timed_out", False)
            ),
            "stage0_terminal_predicates": dict(
                _require_mapping(
                    admission.get("stage0_predicates"),
                    "stage0-timeout push_anchor_admission.stage0_predicates",
                )
            ),
            "reset_contact_qualification_complete": bool(reset["window_complete"]),
            "reset_transient_observed": bool(reset["reset_transient_observed"]),
            "terminal_body_panel_contact_current_n": float(
                admission["body_panel_contact_total_current_n"]
            ),
            "body_panel_contact_max_n": float(admission["body_panel_contact_total_max_n"]),
        },
        "command_to_plant_response": {
            **(
                normalized_response
                if normalized_response is not None
                else {
                    "status": (
                        response_summary.get("status")
                        if isinstance(response_summary, Mapping)
                        else "UNAVAILABLE"
                    ),
                    "schema": (
                        response_summary.get("schema")
                        if isinstance(response_summary, Mapping)
                        else None
                    ),
                    "reason": (
                        response_summary.get("reason")
                        if isinstance(response_summary, Mapping)
                        else "post-executor trace not captured"
                    ),
                    "threshold_mode": "report_only",
                }
            ),
            "admission_field_present": "stage0_command_response" in admission,
        },
        "stage0_timeout_boundary": {
            "blocker": (
                EXPECTED_R9_ROOT_CAUSE
                if budget_analysis is not None
                else EXPECTED_R6_ROOT_CAUSE
                if legacy_unresolved
                else "PULL_P1_STAGE0_TIMEOUT_WITH_RESPONSE_CAPTURED"
            ),
            "mechanism": (
                "The signed stage0 command timed out because the configured admission watchdog "
                "was below the measured staging-distance kinematic lower bound; response metrics "
                "remain report-only and do not alter admission."
                if budget_analysis is not None
                else "The signed stage0 command timed out after causal post-executor response telemetry "
                "was captured; response metrics remain report-only and do not alter admission."
                if not legacy_unresolved
                else "The signed stage0 command and timeout outcome were preserved, but the immutable "
                "trace has no post-executor physical command/downstream lower-body response fields; "
                "command-to-plant causality therefore remains unresolved."
            ),
            "signed_target_and_band_unchanged": True,
            "stage0_timeout_is_sole_hard_stop": True,
            "response_metrics_report_only": True,
        },
        "budget_analysis": budget_analysis,
        "quaternion_contract_closure": (
            {
                "source": "canonical ArticulationData.root_quat_w WXYZ",
                "response_rows": normalized_response["response_count"],
                "anti_alignment_count": normalized_response["aggregates"]["anti_alignment_count"],
                "residual_monotonic_nonincreasing": budget_analysis[
                    "residual_monotonic_nonincreasing"
                ],
                "runtime_validation": "VALIDATED_ACTUAL_R7_PLUS_RESPONSE_TELEMETRY",
            }
            if budget_analysis is not None
            else None
        ),
        "reset_boundary": {
            "qualification_window_steps": int(reset["window_steps"]),
            "window_complete": bool(reset["window_complete"]),
            "transient_observed": bool(reset["reset_transient_observed"]),
            "result": reset["result"],
            "staging_started_during_window": False,
            "dls_started_during_window": False,
        },
        "hard_gate": {
            "stable_bilateral_capture": False,
            "latch_release": True,
            "hinge_progress_min_rad": 0.25,
            "observed_max_hinge_rad": "N/A",
            "body_panel_contact_allowed": False,
            "observed_max_body_force_n": 0.0,
            "pass": False,
        },
        "required_telemetry": {
            "summary": "validated actual runtime summary schema",
            "metrics": "validated actual base-owned push_anchor_admission terminal schema",
            "stage0_command_response": (
                "report-only; unavailable in the immutable pre-response trace"
                if legacy_unresolved
                else "validated actual executor/post-physics response telemetry"
            ),
            "pull_mechanism_verdict": "NOT_ASSESSED",
            "legacy_pull_v0_namespace": "not required for base-owned admission",
        },
        "threshold_mode": "report_only",
        "effort_provenance": "ESTIMATE_ONLY",
        "runtime_validation": (
            "VALIDATED_ACTUAL_R7_PLUS_RESPONSE_TELEMETRY"
            if normalized_response is not None
            else "UNVERIFIED"
        ),
        "unverified_claims": (
            [
                "No pull-mechanism verdict is asserted.",
                (
                    "Attempt10 is probe-invalid because timeout capacity was below the measured "
                    "staging-distance lower bound; no pull-mechanism verdict is asserted."
                    if budget_analysis is not None
                    else "The stage0 timeout remains a probe blocker; response metrics are report-only and do not alter admission."
                ),
            ]
            if normalized_response is not None
            else [
                "No pull-mechanism verdict is asserted.",
                (
                    "The stage0 timeout remains a probe blocker; no pull-mechanism verdict is asserted."
                    if not legacy_unresolved
                    else "Attempt7 is probe-invalid because stage0 timed out before signed admission and the immutable trace lacks post-executor response telemetry."
                ),
                (
                    "The response latch is static-only until a separately authorized runtime validates it."
                    if not legacy_unresolved
                    else "R6 static telemetry instrumentation is not a runtime PASS; a separately authorized Attempt8 runtime is required."
                ),
            ]
        ),
    }


def _attempt18_runtime_lifecycle_failed(process_receipt: Mapping[str, Any]) -> bool:
    return not (
        process_receipt.get("application_success") is True
        and process_receipt.get("natural_exit") is True
        and process_receipt.get("returncode") == 0
    )


def _classify_attempt18_scientific_outcome(
    *,
    summary: Mapping[str, Any],
    admission: Mapping[str, Any],
) -> dict[str, Any]:
    outcome = summary["per_env_outcome"][0]
    per_env_pass = summary["per_env_pass"][0]
    terminal_snapshot = _require_mapping(
        admission.get("terminal_snapshot"),
        "Attempt18 push_anchor_admission.terminal_snapshot",
    )
    if terminal_snapshot.get("outcome") != outcome:
        raise RuntimeError(
            "Attempt18 summary outcome does not match terminal telemetry outcome."
        )
    if summary.get("finalize_called") is not True:
        raise RuntimeError("Attempt18 scientific summary must be finalized before classification.")
    config = _require_mapping(summary.get("config"), "Attempt18 summary.config")
    target_hinge = config.get("v20_arc_probe_target_hinge_rad")
    terminal_window_steps = config.get("v20_arc_probe_terminal_window_steps")
    body_contact_threshold = config.get("pull_p1_body_contact_threshold_n")
    if (
        isinstance(target_hinge, bool)
        or not isinstance(target_hinge, (int, float))
        or not math.isfinite(float(target_hinge))
        or float(target_hinge) < 0.25
        or isinstance(terminal_window_steps, bool)
        or not isinstance(terminal_window_steps, int)
        or terminal_window_steps <= 0
        or isinstance(body_contact_threshold, bool)
        or not isinstance(body_contact_threshold, (int, float))
        or not math.isfinite(float(body_contact_threshold))
        or float(body_contact_threshold) < 0.0
    ):
        raise RuntimeError("Attempt18 summary config does not preserve the current anchor gate thresholds.")
    reset_complete = summary.get("per_env_reset_contact_qualification_complete")
    terminal_streak = summary.get("per_env_terminal_bilateral_streak")
    if (
        not isinstance(reset_complete, list)
        or reset_complete != [True]
        or not isinstance(terminal_streak, list)
        or len(terminal_streak) != 1
        or isinstance(terminal_streak[0], bool)
        or not isinstance(terminal_streak[0], int)
        or terminal_streak[0] < 0
    ):
        raise RuntimeError("Attempt18 summary reset or terminal-window telemetry is invalid.")
    hinge = summary["per_env_max_hinge_rad"][0]
    if hinge is not None and (
        isinstance(hinge, bool)
        or not isinstance(hinge, (int, float))
        or not math.isfinite(float(hinge))
    ):
        raise RuntimeError("Attempt18 maximum hinge telemetry is not finite numeric data.")
    body_force_raw = summary["per_env_max_body_force_n"][0]
    if (
        isinstance(body_force_raw, bool)
        or not isinstance(body_force_raw, (int, float))
        or not math.isfinite(float(body_force_raw))
    ):
        raise RuntimeError("Attempt18 body-contact telemetry is not finite numeric data.")
    body_force = float(body_force_raw)
    hinge_reached = hinge is not None and float(hinge) >= float(target_hinge)
    terminal_window_reached = terminal_streak[0] >= terminal_window_steps
    body_contact_clear = body_force <= float(body_contact_threshold)
    pass_contract = (
        summary["status"] == "PASS"
        and outcome == "ARC_PROBE_REACHED"
        and per_env_pass is True
        and summary["per_env_proof_completed"][0] is True
        and summary["per_env_latch_released"][0] is True
        and summary["finalize_called"] is True
        and hinge_reached
        and terminal_window_reached
        and body_contact_clear
        and terminal_snapshot.get("phase") == "DONE"
    )
    if summary["status"] == "PASS" or per_env_pass is True or outcome == "ARC_PROBE_REACHED":
        if not pass_contract:
            raise RuntimeError(
                "Attempt18 PASS summary is inconsistent with the current ARC_PROBE_REACHED hard gate."
            )
        finding = "ARC_PROBE_REACHED"
        return {
            "status": "ANCHOR_PASS",
            "probe_validity": "PROBE_VALID",
            "scientific_verdict_consumed": True,
            "finding": {
                "named_finding": finding,
                "root_cause_code": finding,
                "lineage": "NEW_NAMED_SCIENTIFIC_FINDING",
                "legacy_finding_match": None,
                "basis": "summary outcome and terminal snapshot agree; every current hard-gate predicate is true",
            },
            "observed": {
                "summary_outcome": outcome,
                "terminal_outcome": terminal_snapshot["outcome"],
                "summary_status": summary["status"],
                "per_env_pass": per_env_pass,
                "per_env_proof_completed": summary["per_env_proof_completed"][0],
                "per_env_latch_released": summary["per_env_latch_released"][0],
                "reset_contact_qualification_complete": reset_complete[0],
                "max_hinge_rad": None if hinge is None else float(hinge),
                "target_hinge_rad": float(target_hinge),
                "terminal_bilateral_streak": terminal_streak[0],
                "terminal_bilateral_window_steps": terminal_window_steps,
                "max_body_force_n": body_force,
                "body_contact_threshold_n": float(body_contact_threshold),
            },
        }
    if summary["status"] != "FAIL" or per_env_pass is not False:
        raise RuntimeError("Attempt18 non-passing summary has inconsistent status or per-env gate.")
    if outcome not in ATTEMPT18_SCIENTIFIC_FAIL_OUTCOMES:
        raise RuntimeError(
            "Unknown Attempt18 scientific outcome; refusing fabricated classification: "
            f"{outcome!r}"
        )
    legacy_match = outcome if outcome in ATTEMPT18_LEGACY_FINDINGS else None
    finding_lineage = (
        "LEGACY_R13_R14_FINDING" if legacy_match is not None else "NEW_NAMED_SCIENTIFIC_FINDING"
    )
    return {
        "status": "ANCHOR_FAIL_PHYSICS",
        "probe_validity": "PROBE_VALID",
        "scientific_verdict_consumed": True,
        "finding": {
            "named_finding": outcome,
            "root_cause_code": outcome,
            "lineage": finding_lineage,
            "legacy_finding_match": legacy_match,
            "basis": "summary outcome equals terminal telemetry outcome and summary explicitly reports FAIL/per_env_pass=false",
        },
        "observed": {
            "summary_outcome": outcome,
            "terminal_outcome": terminal_snapshot["outcome"],
            "summary_status": summary["status"],
            "per_env_pass": per_env_pass,
            "per_env_proof_completed": summary["per_env_proof_completed"][0],
            "per_env_latch_released": summary["per_env_latch_released"][0],
            "reset_contact_qualification_complete": reset_complete[0],
            "max_hinge_rad": None if hinge is None else float(hinge),
            "target_hinge_rad": float(target_hinge),
            "terminal_bilateral_streak": terminal_streak[0],
            "terminal_bilateral_window_steps": terminal_window_steps,
            "max_body_force_n": body_force,
            "body_contact_threshold_n": float(body_contact_threshold),
        },
    }


def _build_attempt18_infra_receipt(
    *,
    repair_receipt: Mapping[str, Any],
    repair_artifact: Mapping[str, Any],
    plan_artifact: Mapping[str, Any],
    process_artifact: Mapping[str, Any],
    log_artifact: Mapping[str, Any],
    launch_occupancy_artifact: Mapping[str, Any],
    steady_state_footprint_artifact: Mapping[str, Any],
    summary_artifact: dict[str, Any] | None,
    metrics_artifact: dict[str, Any] | None,
    process_receipt: Mapping[str, Any],
    resource_evidence: Mapping[str, Any],
    prelaunch_chain: Mapping[str, Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    if prelaunch_chain is None:
        prelaunch_chain = {
            "prelaunch_infra": {},
            "r15e": {},
            "r15f": {},
            "initial_launch_occupancy": {},
        }
    return {
        "schema_version": "pull_v0_p1_push_anchor_attempt_receipt_v18",
        "generated_at_hkt": _hkt_now(),
        "attempt": 18,
        "status": "INFRA_PRE_FIRST_SIMULATION_STEP",
        "probe_validity": "PROBE_INVALID",
        "runtime_validation": "INVALIDATED_BEFORE_SCIENTIFIC_VERDICT",
        "scientific_verdict_consumed": False,
        "pull_mechanism_verdict": "NOT_ASSESSED",
        "repair_r15": {
            "artifact": dict(repair_artifact),
            "revision": repair_receipt["repair_revision"],
            "stale_candidate_id": repair_receipt["stale_candidate_id"],
        },
        "repair_r15e": {"artifact": dict(prelaunch_chain["r15e"]), "revision": "R15E"},
        "repair_r15f": {"artifact": dict(prelaunch_chain["r15f"]), "revision": "R15F"},
        "prelaunch_infra": {"artifact": dict(prelaunch_chain["prelaunch_infra"]), "status": "INFRA_PRELAUNCH_RUNNER_VALIDATION"},
        "artifacts": {
            "plan": dict(plan_artifact),
            "process_receipt": dict(process_artifact),
            "log": dict(log_artifact),
            "initial_launch_occupancy": dict(prelaunch_chain["initial_launch_occupancy"]),
            "launch_occupancy": dict(launch_occupancy_artifact),
            "steady_state_footprint": dict(steady_state_footprint_artifact),
            "summary": None if summary_artifact is None else dict(summary_artifact),
            "metrics": None if metrics_artifact is None else dict(metrics_artifact),
        },
        "infrastructure_failure": {
            "boundary": "INFRA_PRE_FIRST_SIMULATION_STEP",
            "application_success": process_receipt.get("application_success"),
            "natural_exit": process_receipt.get("natural_exit"),
            "returncode": process_receipt.get("returncode"),
            "first_simulation_step_boundary_crossed": resource_evidence[
                "first_simulation_step_boundary_crossed"
            ],
            "scientific_attempt_started": resource_evidence["scientific_attempt_started"],
            "summary_present": summary_artifact is not None,
            "metrics_present": metrics_artifact is not None,
            "scientific_verdict_consumed": False,
        },
        "runtime_evidence": {
            "first_simulation_step_boundary_crossed": resource_evidence[
                "first_simulation_step_boundary_crossed"
            ],
            "scientific_attempt_started": resource_evidence["scientific_attempt_started"],
            "selected_compute_physical_device": ATTEMPT18_SELECTED_COMPUTE_PHYSICAL_DEVICE,
            "authorized_compute_physical_devices": list(
                ATTEMPT18_AUTHORIZED_COMPUTE_PHYSICAL_DEVICES
            ),
            "non_leased_compute_observed": False,
            "tenant_devices_at_launch": resource_evidence.get(
                "tenant_devices_at_launch", []
            ),
        },
        "hard_gate": {
            "stable_bilateral_capture": "N/A",
            "latch_release": "N/A",
            "hinge_progress_min_rad": "N/A",
            "observed_max_hinge_rad": "N/A",
            "body_panel_contact_allowed": "N/A",
            "observed_max_body_force_n": "N/A",
            "pass": False,
        },
        "required_telemetry": {
            "summary": "not consumed for scientific classification",
            "metrics": "not consumed for scientific classification",
            "launch_occupancy": "validated exact Attempt18 per-run launch occupancy",
            "steady_state_footprint": "validated exact Attempt18 pre-first-step boundary evidence",
            "pull_mechanism_verdict": "NOT_ASSESSED",
        },
        "threshold_mode": "report_only",
        "unverified_claims": [
            "No scientific anchor verdict is asserted because the exact steady-state evidence proves the first simulation step was not crossed.",
            "No pull-mechanism verdict is asserted.",
        ],
    }


def _build_attempt18_contact_capacity_failure_receipt(
    *,
    repair_receipt: Mapping[str, Any],
    repair_artifact: Mapping[str, Any],
    plan_artifact: Mapping[str, Any],
    process_artifact: Mapping[str, Any],
    log_artifact: Mapping[str, Any],
    launch_occupancy_artifact: Mapping[str, Any],
    steady_state_footprint_artifact: Mapping[str, Any],
    summary_artifact: Mapping[str, Any] | None,
    metrics_artifact: Mapping[str, Any] | None,
    process_receipt: Mapping[str, Any],
    resource_evidence: Mapping[str, Any],
    prelaunch_chain: Mapping[str, Mapping[str, Any]],
    log_text: str,
) -> dict[str, Any]:
    """Seal the exact Attempt18 contact-buffer failure without consuming science."""
    if (
        plan_artifact.get("sha256") != EXPECTED_ATTEMPT18_PLAN_SHA256
        or process_artifact.get("sha256") != EXPECTED_ATTEMPT18_PROCESS_SHA256
        or log_artifact.get("sha256") != EXPECTED_ATTEMPT18_LOG_SHA256
        or launch_occupancy_artifact.get("sha256")
        != EXPECTED_ATTEMPT18_RETRY1_LAUNCH_OCCUPANCY_SHA256
        or steady_state_footprint_artifact.get("sha256")
        != EXPECTED_ATTEMPT18_RETRY1_STEADY_STATE_FOOTPRINT_SHA256
    ):
        raise RuntimeError("Attempt18 contact-capacity failure artifacts do not match the immutable runtime evidence.")
    if (
        process_receipt.get("returncode") != -9
        or process_receipt.get("natural_exit") is not False
        or process_receipt.get("application_success") is not False
        or process_receipt.get("required_summary_present") is not False
        or process_receipt.get("required_metrics_present") is not False
        or process_receipt.get("summary_path") is not None
        or process_receipt.get("summary_sha256") is not None
        or process_receipt.get("metrics_path") is not None
        or process_receipt.get("metrics_sha256") is not None
    ):
        raise RuntimeError("Attempt18 contact-capacity failure requires the exact failed process receipt with no summary/metrics.")
    missing_signatures = [
        signature
        for signature in (
            ATTEMPT18_CONTACT_WARNING_SIGNATURE,
            ATTEMPT18_CUDA_ASSERT_SIGNATURE,
            ATTEMPT18_FRICTION_FAILURE_SIGNATURE,
        )
        if signature not in log_text
    ]
    if missing_signatures:
        raise RuntimeError(
            "Attempt18 contact-capacity failure log is missing exact signatures: "
            + ", ".join(missing_signatures)
        )
    if (
        resource_evidence.get("first_simulation_step_boundary_crossed") is not True
        or resource_evidence.get("scientific_attempt_started") is not True
        or resource_evidence.get("non_leased_compute_observed") is not False
    ):
        raise RuntimeError("Attempt18 contact-capacity failure requires exact post-first-step resource evidence.")
    if summary_artifact is not None or metrics_artifact is not None:
        raise RuntimeError("Attempt18 contact-capacity failure cannot consume partial summary/metrics artifacts.")
    return {
        "schema_version": "pull_v0_p1_push_anchor_attempt_receipt_v18",
        "generated_at_hkt": _hkt_now(),
        "attempt": 18,
        "status": "PROBE_INVALID",
        "probe_validity": "PROBE_INVALID",
        "runtime_validation": "INVALIDATED_AFTER_FIRST_SIMULATION_STEP",
        "scientific_verdict_consumed": False,
        "pull_mechanism_verdict": "NOT_ASSESSED",
        "repair_r15": {
            "artifact": dict(repair_artifact),
            "revision": repair_receipt["repair_revision"],
            "stale_candidate_id": repair_receipt["stale_candidate_id"],
        },
        "repair_r15e": {"artifact": dict(prelaunch_chain["r15e"]), "revision": "R15E"},
        "repair_r15f": {"artifact": dict(prelaunch_chain["r15f"]), "revision": "R15F"},
        "prelaunch_infra": {
            "artifact": dict(prelaunch_chain["prelaunch_infra"]),
            "status": "INFRA_PRELAUNCH_RUNNER_VALIDATION",
        },
        "artifacts": {
            "plan": dict(plan_artifact),
            "process_receipt": dict(process_artifact),
            "log": dict(log_artifact),
            "initial_launch_occupancy": dict(prelaunch_chain["initial_launch_occupancy"]),
            "launch_occupancy": dict(launch_occupancy_artifact),
            "steady_state_footprint": dict(steady_state_footprint_artifact),
            "summary": None,
            "metrics": None,
        },
        "runtime_failure": {
            "boundary": "AFTER_FIRST_SIMULATION_STEP_BEFORE_SUMMARY_METRICS",
            "root_cause_code": "CONTACT_SENSOR_CAPACITY_OVERFLOW",
            "configured_max_contact_data_count_per_prim": SHARED_CONTACT_CAPACITY,
            "required_anchor_only_detailed_contact_capacity": ATTEMPT19_CONTACT_CAPACITY,
            "source_message": ATTEMPT18_CONTACT_WARNING_SIGNATURE,
            "exact_signatures": [
                ATTEMPT18_CONTACT_WARNING_SIGNATURE,
                ATTEMPT18_CUDA_ASSERT_SIGNATURE,
                ATTEMPT18_FRICTION_FAILURE_SIGNATURE,
            ],
            "process_returncode": process_receipt["returncode"],
            "natural_exit": process_receipt["natural_exit"],
            "application_success": process_receipt["application_success"],
            "first_simulation_step_boundary_crossed": True,
            "scientific_attempt_started": True,
            "summary_present": False,
            "metrics_present": False,
            "scientific_verdict_consumed": False,
        },
        "termination": {
            "sigterm": {
                "sent": True,
                "timestamp_hkt": None,
                "timestamp_status": "NOT_RECORDED",
                "disposition": "IGNORED_FOR_60S",
            },
            "sigkill": {
                "sent": True,
                "timestamp_hkt": "2026-08-04 20:14:10 HKT",
                "disposition": "CHILD_REAPED",
            },
            "runner_reaped_at_hkt": "2026-08-04 20:14:13 HKT",
            "sigterm_timestamp_not_fabricated": True,
        },
        "runtime_evidence": {
            "first_simulation_step_boundary_crossed": True,
            "scientific_attempt_started": True,
            "selected_compute_physical_device": ATTEMPT18_SELECTED_COMPUTE_PHYSICAL_DEVICE,
            "authorized_compute_physical_devices": list(ATTEMPT18_AUTHORIZED_COMPUTE_PHYSICAL_DEVICES),
            "non_leased_compute_observed": False,
            "tenant_devices_at_launch": resource_evidence.get("tenant_devices_at_launch", []),
        },
        "hard_gate": {
            "stable_bilateral_capture": "N/A",
            "latch_release": "N/A",
            "hinge_progress_min_rad": "N/A",
            "observed_max_hinge_rad": "N/A",
            "body_panel_contact_allowed": "N/A",
            "observed_max_body_force_n": "N/A",
            "pass": False,
        },
        "required_telemetry": {
            "summary": "absent after runtime failure; not consumed",
            "metrics": "absent after runtime failure; not consumed",
            "launch_occupancy": "validated exact Attempt18 retry1 per-run launch occupancy",
            "steady_state_footprint": "validated exact Attempt18 first-step boundary and GPU footprint evidence",
            "pull_mechanism_verdict": "NOT_ASSESSED",
        },
        "threshold_mode": "report_only",
        "unverified_claims": [
            "No scientific anchor verdict is asserted because contact-buffer overflow aborted the first-step runtime before summary/metrics finalization.",
            "No pull-mechanism verdict is asserted.",
            "The exact SIGTERM send timestamp was not recorded and is represented as null; no timestamp is fabricated.",
        ],
    }


def _build_attempt18_scientific_receipt(
    *,
    admission: Mapping[str, Any],
    repair_receipt: Mapping[str, Any],
    repair_artifact: Mapping[str, Any],
    plan_artifact: Mapping[str, Any],
    process_artifact: Mapping[str, Any],
    log_artifact: Mapping[str, Any],
    launch_occupancy_artifact: Mapping[str, Any],
    steady_state_footprint_artifact: Mapping[str, Any],
    summary_artifact: Mapping[str, Any],
    metrics_artifact: Mapping[str, Any],
    process_receipt: Mapping[str, Any],
    summary: Mapping[str, Any],
    resource_evidence: Mapping[str, Any],
    prelaunch_chain: Mapping[str, Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    if prelaunch_chain is None:
        prelaunch_chain = {
            "prelaunch_infra": {},
            "r15e": {},
            "r15f": {},
            "initial_launch_occupancy": {},
        }
    if (
        resource_evidence["first_simulation_step_boundary_crossed"] is not True
        or resource_evidence["scientific_attempt_started"] is not True
        or resource_evidence.get("non_leased_compute_observed") is not False
    ):
        raise RuntimeError(
            "Attempt18 scientific classification requires exact steady-state evidence after the first simulation step."
        )
    classification = _classify_attempt18_scientific_outcome(
        summary=summary,
        admission=admission,
    )
    return {
        "schema_version": "pull_v0_p1_push_anchor_attempt_receipt_v18",
        "generated_at_hkt": _hkt_now(),
        "attempt": 18,
        "status": classification["status"],
        "probe_validity": classification["probe_validity"],
        "runtime_validation": "VALIDATED_ACTUAL_RUNTIME",
        "scientific_verdict_consumed": classification["scientific_verdict_consumed"],
        "pull_mechanism_verdict": "NOT_ASSESSED",
        "repair_r15": {
            "artifact": dict(repair_artifact),
            "revision": repair_receipt["repair_revision"],
            "stale_candidate_id": repair_receipt["stale_candidate_id"],
        },
        "repair_r15e": {"artifact": dict(prelaunch_chain["r15e"]), "revision": "R15E"},
        "repair_r15f": {"artifact": dict(prelaunch_chain["r15f"]), "revision": "R15F"},
        "prelaunch_infra": {"artifact": dict(prelaunch_chain["prelaunch_infra"]), "status": "INFRA_PRELAUNCH_RUNNER_VALIDATION"},
        "artifacts": {
            "plan": dict(plan_artifact),
            "process_receipt": dict(process_artifact),
            "log": dict(log_artifact),
            "initial_launch_occupancy": dict(prelaunch_chain["initial_launch_occupancy"]),
            "launch_occupancy": dict(launch_occupancy_artifact),
            "steady_state_footprint": dict(steady_state_footprint_artifact),
            "summary": dict(summary_artifact),
            "metrics": dict(metrics_artifact),
        },
        "outcome": {
            "verdict": classification["status"],
            "outcome_code": summary["per_env_outcome"][0],
            "named_finding": classification["finding"]["named_finding"],
            "root_cause": classification["finding"]["root_cause_code"],
            "root_cause_code": classification["finding"]["root_cause_code"],
            "finding_lineage": classification["finding"]["lineage"],
            "legacy_finding_match": classification["finding"]["legacy_finding_match"],
            "mapping_basis": classification["finding"]["basis"],
            "observed": classification["observed"],
        },
        "runtime_evidence": {
            "first_simulation_step_boundary_crossed": resource_evidence[
                "first_simulation_step_boundary_crossed"
            ],
            "scientific_attempt_started": resource_evidence["scientific_attempt_started"],
            "selected_compute_physical_device": ATTEMPT18_SELECTED_COMPUTE_PHYSICAL_DEVICE,
            "authorized_compute_physical_devices": list(
                ATTEMPT18_AUTHORIZED_COMPUTE_PHYSICAL_DEVICES
            ),
            "non_leased_compute_observed": False,
            "tenant_devices_at_launch": resource_evidence.get(
                "tenant_devices_at_launch", []
            ),
        },
        "hard_gate": {
            "stable_bilateral_capture": bool(summary["per_env_proof_completed"][0]),
            "latch_release": bool(summary["per_env_latch_released"][0]),
            "hinge_progress_min_rad": float(
                _require_mapping(summary["config"], "Attempt18 summary.config")[
                    "v20_arc_probe_target_hinge_rad"
                ]
            ),
            "observed_max_hinge_rad": summary["per_env_max_hinge_rad"][0],
            "body_panel_contact_allowed": False,
            "observed_max_body_force_n": float(summary["per_env_max_body_force_n"][0]),
            "pass": classification["status"] == "ANCHOR_PASS",
        },
        "required_telemetry": {
            "summary": "validated current push-anchor runtime summary schema",
            "metrics": "validated current base-owned push_anchor_admission terminal schema",
            "launch_occupancy": "validated exact Attempt18 per-run launch occupancy and GPU lease evidence",
            "steady_state_footprint": "validated exact Attempt18 first-step boundary and GPU footprint evidence",
            "finding_basis": classification["finding"]["basis"],
            "pull_mechanism_verdict": "NOT_ASSESSED",
        },
        "threshold_mode": "report_only",
        "unverified_claims": [
            "No pull-mechanism verdict is asserted.",
        ],
    }


def _build_actual_push_anchor_attempt_receipt(
    *,
    attempt: int,
    plan: Mapping[str, Any] | None = None,
    repair_receipt: Mapping[str, Any],
    repair_artifact: Mapping[str, Any],
    plan_artifact: Mapping[str, Any],
    process_artifact: Mapping[str, Any],
    log_artifact: Mapping[str, Any],
    summary_artifact: Mapping[str, Any],
    metrics_artifact: Mapping[str, Any],
    process_receipt: Mapping[str, Any],
    summary: Mapping[str, Any],
    metrics: Mapping[str, Any],
    launch_occupancy_artifact: Mapping[str, Any] | None = None,
    steady_state_footprint_artifact: Mapping[str, Any] | None = None,
    resource_evidence: Mapping[str, Any] | None = None,
    prelaunch_chain: Mapping[str, Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Route every actual push-anchor attempt through one schema validator."""
    def finalize(receipt: dict[str, Any]) -> dict[str, Any]:
        if attempt != 19:
            return receipt
        if resource_evidence is None:
            raise RuntimeError("Attempt19 scientific receipt requires validated resource evidence.")
        if (
            resource_evidence.get("first_simulation_step_boundary_crossed") is not True
            or resource_evidence.get("scientific_attempt_started") is not True
            or resource_evidence.get("non_leased_compute_observed") is not False
        ):
            raise RuntimeError(
                "Attempt19 scientific receipt requires selected GPU2 first-step evidence with no non-leased attempt compute."
            )
        artifacts = receipt.setdefault("artifacts", {})
        artifacts["launch_occupancy"] = dict(resource_evidence["launch_artifact"])
        artifacts["steady_state_footprint"] = dict(resource_evidence["steady_state_artifact"])
        receipt["runtime_evidence"] = {
            "first_simulation_step_boundary_crossed": True,
            "scientific_attempt_started": True,
            "selected_compute_physical_device": ATTEMPT19_SELECTED_COMPUTE_PHYSICAL_DEVICE,
            "authorized_compute_physical_devices": list(ATTEMPT19_AUTHORIZED_COMPUTE_PHYSICAL_DEVICES),
            "non_leased_compute_observed": False,
            "tenant_devices_at_launch": list(resource_evidence.get("tenant_devices_at_launch", [])),
            "tenant_devices_at_steady_state": list(
                resource_evidence.get("tenant_devices_at_steady_state", [])
            ),
        }
        telemetry = receipt.setdefault("required_telemetry", {})
        telemetry["launch_occupancy"] = "validated exact Attempt19 per-run launch occupancy"
        telemetry["steady_state_footprint"] = "validated exact Attempt19 first-step boundary and GPU footprint"
        return receipt

    admission = _validate_actual_push_anchor_schema(
        summary=summary,
        metrics=metrics,
        require_stage0_response=attempt >= 8,
        attempt=attempt,
    )
    if attempt == 18:
        return finalize(_build_attempt18_scientific_receipt(
            admission=admission,
            repair_receipt=repair_receipt,
            repair_artifact=repair_artifact,
            plan_artifact=plan_artifact,
            process_artifact=process_artifact,
            log_artifact=log_artifact,
            launch_occupancy_artifact=launch_occupancy_artifact
            if launch_occupancy_artifact is not None
            else {},
            steady_state_footprint_artifact=steady_state_footprint_artifact
            if steady_state_footprint_artifact is not None
            else {},
            summary_artifact=summary_artifact,
            metrics_artifact=metrics_artifact,
            process_receipt=process_receipt,
            summary=summary,
            resource_evidence=resource_evidence if resource_evidence is not None else {},
            prelaunch_chain=prelaunch_chain if prelaunch_chain is not None else {},
        ))
    outcome = summary["per_env_outcome"][0]
    if outcome == "BASE_RELIEF_TIMEOUT":
        return finalize(_build_attempt6_r4_watchdog_cross_talk_receipt(
            attempt=attempt,
            admission=admission,
            repair_receipt=repair_receipt,
            repair_artifact=repair_artifact,
            plan_artifact=plan_artifact,
            process_artifact=process_artifact,
            log_artifact=log_artifact,
            summary_artifact=summary_artifact,
            metrics_artifact=metrics_artifact,
            process_receipt=process_receipt,
            summary=summary,
            metrics=metrics,
        ))
    if outcome == "PULL_P1_STAGE0_TIMEOUT":
        return finalize(_build_stage0_timeout_actual_schema_receipt(
            attempt=attempt,
            plan=plan,
            admission=admission,
            repair_receipt=repair_receipt,
            repair_artifact=repair_artifact,
            plan_artifact=plan_artifact,
            process_artifact=process_artifact,
            log_artifact=log_artifact,
            summary_artifact=summary_artifact,
            metrics_artifact=metrics_artifact,
            process_receipt=process_receipt,
            summary=summary,
            metrics=metrics,
        ))
    if attempt == 11 and outcome == "ARC_PROBE_TIMEOUT":
        if plan is None:
            raise RuntimeError("Attempt11 host-stage overtime classification requires its immutable plan.")
        return finalize(_build_attempt11_host_stage_overtime_receipt(
            attempt=attempt,
            plan=plan,
            admission=admission,
            repair_receipt=repair_receipt,
            repair_artifact=repair_artifact,
            plan_artifact=plan_artifact,
            process_artifact=process_artifact,
            log_artifact=log_artifact,
            summary_artifact=summary_artifact,
            metrics_artifact=metrics_artifact,
            process_receipt=process_receipt,
            summary=summary,
            metrics=metrics,
        ))
    raise RuntimeError(
        "Unknown actual push-anchor outcome; refusing legacy or fabricated classification: "
        f"{outcome!r}"
    )


def build_post_r1_attempt_receipt(
    attempt: int,
    *,
    plan_path: Path,
    process_receipt_path: Path,
    log_path: Path,
    summary_path: Path,
    metrics_path: Path,
    repair_receipt_path: Path = REPAIR_RECEIPT_PATH,
    launch_occupancy_path: Path | None = None,
    steady_state_footprint_path: Path | None = None,
    prelaunch_infra_receipt_path: Path | None = None,
    r15e_receipt_path: Path | None = None,
    r15f_receipt_path: Path | None = None,
    retry1_launch_occupancy_path: Path | None = None,
    retry1_steady_state_footprint_path: Path | None = None,
) -> dict[str, Any]:
    if isinstance(attempt, bool) or not isinstance(attempt, int) or attempt < 3:
        raise ValueError(f"post-repair attempt must be an integer >= 3; got {attempt!r}")
    if not repair_receipt_path.is_absolute():
        repair_receipt_path = ROOT / repair_receipt_path
    if attempt == 18:
        prelaunch_infra_receipt_path = (
            ATTEMPT18_PRELAUNCH_INFRA_RECEIPT_PATH
            if prelaunch_infra_receipt_path is None
            else prelaunch_infra_receipt_path
        )
        r15e_receipt_path = (
            ATTEMPT18_R15E_RECEIPT_PATH
            if r15e_receipt_path is None
            else r15e_receipt_path
        )
        r15f_receipt_path = (
            ATTEMPT18_R15F_RECEIPT_PATH
            if r15f_receipt_path is None
            else r15f_receipt_path
        )
        retry1_launch_occupancy_path = (
            ATTEMPT18_RETRY1_LAUNCH_OCCUPANCY_PATH
            if retry1_launch_occupancy_path is None
            else retry1_launch_occupancy_path
        )
        retry1_steady_state_footprint_path = (
            ATTEMPT18_RETRY1_STEADY_STATE_FOOTPRINT_PATH
            if retry1_steady_state_footprint_path is None
            else retry1_steady_state_footprint_path
        )
        if (
            launch_occupancy_path is not None
            or steady_state_footprint_path is not None
        ):
            raise RuntimeError(
                "Attempt18 closure accepts retry1 occupancy/footprint paths only; "
                "the initial launch occupancy is immutable prelaunch evidence."
            )
        if (
            prelaunch_infra_receipt_path is None
            or r15e_receipt_path is None
            or r15f_receipt_path is None
        ):
            raise RuntimeError(
                "Attempt18 closure requires the prelaunch infra, R15E, and R15F receipts."
            )
        if retry1_launch_occupancy_path is None or retry1_steady_state_footprint_path is None:
            raise RuntimeError(
                "Attempt18 post-runtime closure requires retry1 launch occupancy and steady-state footprint receipts."
            )
        _validate_attempt18_retry_runtime_paths(
            plan_path=plan_path,
            process_receipt_path=process_receipt_path,
            log_path=log_path,
            summary_path=summary_path,
            metrics_path=metrics_path,
            launch_occupancy_path=retry1_launch_occupancy_path,
            steady_state_footprint_path=retry1_steady_state_footprint_path,
        )
    elif attempt == 19:
        launch_occupancy_path = (
            ATTEMPT19_LAUNCH_OCCUPANCY_PATH
            if launch_occupancy_path is None
            else launch_occupancy_path
        )
        steady_state_footprint_path = (
            ATTEMPT19_STEADY_STATE_FOOTPRINT_PATH
            if steady_state_footprint_path is None
            else steady_state_footprint_path
        )
        if launch_occupancy_path is None or steady_state_footprint_path is None:
            raise RuntimeError(
                "Attempt19 closure requires canonical launch occupancy and steady-state footprint receipts."
            )
    repair_receipt, repair_artifact = _validate_repair_receipt(
        repair_receipt_path,
        attempt=attempt,
        allow_attempt18_runtime=attempt == 18,
    )
    plan = _read_json(plan_path)
    process_receipt = _read_json(process_receipt_path)
    expected_plan_artifact = _artifact(plan_path)
    expected_process_artifact = _artifact(process_receipt_path)
    expected_log_artifact = _artifact(log_path)
    _validate_plan_repair_binding(
        plan,
        attempt=attempt,
        repair_receipt=repair_receipt,
        repair_artifact=repair_artifact,
    )
    _validate_process_artifacts(
        process_receipt,
        attempt=attempt,
        plan_artifact=expected_plan_artifact,
        plan_sha256=plan["plan_sha256"],
        log_artifact=expected_log_artifact,
        repair_artifact=repair_artifact,
        process_artifact=expected_process_artifact,
    )
    attempt18_resource_evidence: dict[str, Any] | None = None
    attempt18_launch_occupancy_artifact: dict[str, Any] | None = None
    attempt18_steady_state_footprint_artifact: dict[str, Any] | None = None
    attempt18_prelaunch_chain: dict[str, dict[str, Any]] | None = None
    attempt19_resource_evidence: dict[str, Any] | None = None
    if attempt == 18:
        if (
            prelaunch_infra_receipt_path is None
            or r15e_receipt_path is None
            or r15f_receipt_path is None
            or retry1_launch_occupancy_path is None
            or retry1_steady_state_footprint_path is None
        ):
            raise RuntimeError(
                "Attempt18 resource evidence and prelaunch/R15E/R15F repair-chain paths must be supplied for post-runtime closure."
            )
        attempt18_prelaunch_chain = _validate_attempt18_prelaunch_chain(
            plan_path=plan_path,
            initial_launch_occupancy_path=ATTEMPT18_LAUNCH_OCCUPANCY_PATH,
            prelaunch_infra_receipt_path=prelaunch_infra_receipt_path,
            r15e_receipt_path=r15e_receipt_path,
            r15f_receipt_path=r15f_receipt_path,
        )
        attempt18_launch_occupancy_artifact = _artifact(retry1_launch_occupancy_path)
        attempt18_steady_state_footprint_artifact = _artifact(retry1_steady_state_footprint_path)
        attempt18_resource_evidence = _validate_attempt18_resource_evidence(
            plan=plan,
            plan_artifact=expected_plan_artifact,
            launch_occupancy_path=retry1_launch_occupancy_path,
            steady_state_footprint_path=retry1_steady_state_footprint_path,
        )
    elif attempt == 19:
        if launch_occupancy_path is None or steady_state_footprint_path is None:
            raise RuntimeError(
                "Attempt19 closure requires exact canonical launch occupancy and steady-state footprint evidence."
            )
        attempt19_resource_evidence = _validate_attempt19_resource_evidence(
            plan=plan,
            plan_artifact=expected_plan_artifact,
            process_receipt=process_receipt,
            log_path=log_path,
            launch_occupancy_path=launch_occupancy_path,
            steady_state_footprint_path=steady_state_footprint_path,
        )
    summary_exists = summary_path.is_file() and not summary_path.is_symlink()
    metrics_exists = metrics_path.is_file() and not metrics_path.is_symlink()
    if attempt == 18 and _attempt18_runtime_lifecycle_failed(process_receipt):
        if attempt18_resource_evidence is None:
            raise RuntimeError("Attempt18 lifecycle classification lacks resource evidence.")
        if (
            attempt18_resource_evidence["first_simulation_step_boundary_crossed"] is True
            and attempt18_resource_evidence["scientific_attempt_started"] is True
            and process_receipt.get("returncode") == -9
            and not summary_exists
            and not metrics_exists
        ):
            log_text = log_path.read_text(encoding="utf-8", errors="replace")
            if all(
                signature in log_text
                for signature in (
                    ATTEMPT18_CONTACT_WARNING_SIGNATURE,
                    ATTEMPT18_CUDA_ASSERT_SIGNATURE,
                    ATTEMPT18_FRICTION_FAILURE_SIGNATURE,
                )
            ):
                return _build_attempt18_contact_capacity_failure_receipt(
                    repair_receipt=repair_receipt,
                    repair_artifact=repair_artifact,
                    plan_artifact=expected_plan_artifact,
                    process_artifact=expected_process_artifact,
                    log_artifact=expected_log_artifact,
                    launch_occupancy_artifact=attempt18_launch_occupancy_artifact
                    if attempt18_launch_occupancy_artifact is not None
                    else {},
                    steady_state_footprint_artifact=attempt18_steady_state_footprint_artifact
                    if attempt18_steady_state_footprint_artifact is not None
                    else {},
                    summary_artifact=None,
                    metrics_artifact=None,
                    process_receipt=process_receipt,
                    resource_evidence=attempt18_resource_evidence,
                    prelaunch_chain=attempt18_prelaunch_chain
                    if attempt18_prelaunch_chain is not None
                    else {},
                    log_text=log_text,
                )
        if (
            attempt18_resource_evidence["first_simulation_step_boundary_crossed"] is not False
            or attempt18_resource_evidence["scientific_attempt_started"] is not False
            or attempt18_resource_evidence.get("non_leased_compute_observed") is not False
        ):
            raise RuntimeError(
                "Attempt18 lifecycle failed after the first simulation step; the scientific attempt is unsealable."
            )
        if summary_exists != metrics_exists:
            raise RuntimeError(
                "Attempt18 infrastructure failure has an incomplete summary/metrics artifact pair."
            )
        infra_summary_artifact = _artifact(summary_path) if summary_exists else None
        infra_metrics_artifact = _artifact(metrics_path) if metrics_exists else None
        if summary_exists:
            if (
                process_receipt.get("summary_path") != infra_summary_artifact["path"]
                or process_receipt.get("summary_sha256") != infra_summary_artifact["sha256"]
                or process_receipt.get("metrics_path") != infra_metrics_artifact["path"]
                or process_receipt.get("metrics_sha256") != infra_metrics_artifact["sha256"]
            ):
                raise RuntimeError(
                    "Attempt18 infrastructure receipt has inconsistent summary/metrics artifact bindings."
                )
        return _build_attempt18_infra_receipt(
            repair_receipt=repair_receipt,
            repair_artifact=repair_artifact,
            plan_artifact=expected_plan_artifact,
            process_artifact=expected_process_artifact,
            log_artifact=expected_log_artifact,
            launch_occupancy_artifact=attempt18_launch_occupancy_artifact
            if attempt18_launch_occupancy_artifact is not None
            else {},
            steady_state_footprint_artifact=attempt18_steady_state_footprint_artifact
            if attempt18_steady_state_footprint_artifact is not None
            else {},
            summary_artifact=infra_summary_artifact,
            metrics_artifact=infra_metrics_artifact,
            process_receipt=process_receipt,
            resource_evidence=attempt18_resource_evidence,
            prelaunch_chain=attempt18_prelaunch_chain,
        )
    if attempt == 3 and not summary_exists and not metrics_exists:
        return _build_attempt3_contract_failure_receipt(
            repair_receipt=repair_receipt,
            repair_artifact=repair_artifact,
            plan_artifact=expected_plan_artifact,
            process_artifact=expected_process_artifact,
            log_artifact=expected_log_artifact,
            process_receipt=process_receipt,
            log_text=log_path.read_text(encoding="utf-8", errors="replace"),
        )
    if not summary_exists or not metrics_exists:
        raise RuntimeError("Post-repair receipt requires both summary and metrics artifacts.")
    summary = _read_json(summary_path)
    metrics = _read_json(metrics_path)
    expected_summary_artifact = _artifact(summary_path)
    expected_metrics_artifact = _artifact(metrics_path)
    for field, expected_artifact in (
        ("summary_path", expected_summary_artifact),
        ("metrics_path", expected_metrics_artifact),
    ):
        if process_receipt.get(field) != expected_artifact["path"]:
            raise RuntimeError(f"Process receipt {field} does not identify the supplied artifact.")
    if process_receipt.get("summary_sha256") != expected_summary_artifact["sha256"]:
        raise RuntimeError("Process receipt summary hash does not match the summary artifact.")
    if process_receipt.get("metrics_sha256") != expected_metrics_artifact["sha256"]:
        raise RuntimeError("Process receipt metrics hash does not match the metrics artifact.")
    if attempt == 4:
        return _build_attempt4_r2_admission_blocker_receipt(
            repair_receipt=repair_receipt,
            repair_artifact=repair_artifact,
            plan_artifact=expected_plan_artifact,
            process_artifact=expected_process_artifact,
            log_artifact=expected_log_artifact,
            summary_artifact=expected_summary_artifact,
            metrics_artifact=expected_metrics_artifact,
            process_receipt=process_receipt,
            summary=summary,
            metrics=metrics,
        )
    if attempt == 5:
        return _build_attempt5_r3_reset_boundary_blocker_receipt(
            repair_receipt=repair_receipt,
            repair_artifact=repair_artifact,
            plan_artifact=expected_plan_artifact,
            process_artifact=expected_process_artifact,
            log_artifact=expected_log_artifact,
            summary_artifact=expected_summary_artifact,
            metrics_artifact=expected_metrics_artifact,
            process_receipt=process_receipt,
            summary=summary,
            metrics=metrics,
        )
    if attempt >= 6:
        return _build_actual_push_anchor_attempt_receipt(
            attempt=attempt,
            plan=plan,
            repair_receipt=repair_receipt,
            repair_artifact=repair_artifact,
            plan_artifact=expected_plan_artifact,
            process_artifact=expected_process_artifact,
            log_artifact=expected_log_artifact,
            summary_artifact=expected_summary_artifact,
            metrics_artifact=expected_metrics_artifact,
            process_receipt=process_receipt,
            summary=summary,
            metrics=metrics,
            launch_occupancy_artifact=(
                attempt19_resource_evidence["launch_artifact"]
                if attempt19_resource_evidence is not None
                else attempt18_launch_occupancy_artifact
            ),
            steady_state_footprint_artifact=(
                attempt19_resource_evidence["steady_state_artifact"]
                if attempt19_resource_evidence is not None
                else attempt18_steady_state_footprint_artifact
            ),
            resource_evidence=(
                attempt19_resource_evidence
                if attempt19_resource_evidence is not None
                else attempt18_resource_evidence
            ),
            prelaunch_chain=attempt18_prelaunch_chain,
        )
    classification = classify_post_r1_attempt(
        process_receipt=process_receipt,
        summary=summary,
        metrics=metrics,
    )
    repair_key = f"repair_{repair_receipt['repair_revision'].lower()}"
    receipt = {
        "schema_version": "pull_v0_p1_push_anchor_attempt_receipt_v2",
        "generated_at_hkt": _hkt_now(),
        "attempt": attempt,
        "status": classification["status"],
        "probe_validity": classification["probe_validity"],
        "admission_blocker": classification["admission_blocker"],
        "pull_mechanism_verdict": classification["pull_mechanism_verdict"],
        repair_key: {
            "artifact": dict(repair_artifact),
            "revision": repair_receipt["repair_revision"],
            "stale_candidate_id": repair_receipt["stale_candidate_id"],
        },
        "artifacts": {
            "plan": expected_plan_artifact,
            "process_receipt": expected_process_artifact,
            "log": expected_log_artifact,
            "summary": expected_summary_artifact,
            "metrics": expected_metrics_artifact,
        },
        "hard_gate": {
            "stable_bilateral_capture": bool(summary["per_env_proof_completed"][0]),
            "latch_release": bool(summary["per_env_latch_released"][0]),
            "hinge_progress_min_rad": 0.25,
            "observed_max_hinge_rad": (
                None
                if summary["per_env_max_hinge_rad"][0] is None
                else float(summary["per_env_max_hinge_rad"][0])
            ),
            "body_panel_contact_allowed": False,
            "observed_max_body_force_n": float(summary["per_env_max_body_force_n"][0]),
            "pass": classification["status"] == "PASS",
        },
        "required_telemetry": {
            "summary_fields": list(REQUIRED_SUMMARY_FIELDS),
            "terminal_fields": list(REQUIRED_TERMINAL_FIELDS),
            "event_schema": "E0-E7 contiguous pull-v0 episode record",
        },
        "threshold_mode": "report_only",
    }
    return receipt


def _post_r1_attempt_arg(raw: str) -> int:
    try:
        attempt = int(raw)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("attempt must be an integer") from exc
    if attempt < 3:
        raise argparse.ArgumentTypeError("post-R1 attempt must be >= 3")
    return attempt


def _build_legacy_receipts() -> int:
    generated_at = _hkt_now()
    repair_receipt_path = REPAIR_RECEIPT_PATH
    repair_receipt = _read_json(repair_receipt_path)
    if (
        repair_receipt.get("schema_version") != "pull_v0_repair_r1_receipt_v1"
        or repair_receipt.get("repair_revision") != "R1"
        or repair_receipt.get("root_cause", {}).get("conclusion")
        != "ANCHOR_ADMISSION_CONTROL_FLOW"
    ):
        raise RuntimeError("Repair R1 receipt is missing or has an invalid root-cause binding")
    attempt1_plan_path = EVIDENCE_ROOT / "PULL_V0_P1_PUSH_ANCHOR_ATTEMPT1_PLAN.json"
    attempt2_plan_path = EVIDENCE_ROOT / "PULL_V0_P1_PUSH_ANCHOR_ATTEMPT2_PLAN.json"
    attempt1_receipt_path = LOG_ROOT / "attempt1" / "process_receipt.json"
    attempt2_receipt_path = LOG_ROOT / "attempt2" / "process_receipt.json"
    attempt1_log_path = LOG_ROOT / "attempt1" / "stdout_stderr.log"
    attempt2_summary_path = LOG_ROOT / "attempt2" / "eval" / "a2_hold_oracle_summary.json"
    attempt2_metrics_path = LOG_ROOT / "attempt2" / "eval" / "metrics_eval.json"

    attempt1 = _read_json(attempt1_receipt_path)
    attempt2 = _read_json(attempt2_receipt_path)
    summary = _read_json(attempt2_summary_path)
    metrics = _read_json(attempt2_metrics_path)
    attempt1_log = attempt1_log_path.read_text(encoding="utf-8", errors="replace")
    if attempt1.get("summary_path") is not None or (
        "A2 eval diagnostic reward terms must be active non-zero reward terms"
        not in attempt1_log
    ):
        raise RuntimeError("Attempt 1 is not the preserved diagnostic-binding failure")
    if not attempt2.get("application_success") or not attempt2.get("natural_exit"):
        raise RuntimeError("Attempt 2 did not complete its application lifecycle naturally")
    if (
        summary.get("schema") != "a2_piper_pull_v0_p1_scripted_probe_runtime_v1"
        or summary.get("status") != "FAIL"
        or summary.get("per_env_outcome") != ["NO_GATE"]
        or summary.get("per_env_pass") != [False]
        or summary.get("per_env_proof_completed") != [False]
        or summary.get("per_env_latch_released") != [False]
        or summary.get("per_env_terminal_bilateral_streak") != [0]
        or summary.get("finalize_called") is not True
    ):
        raise RuntimeError("Attempt 2 summary does not match the final NO_GATE blocker")
    if (
        metrics.get("completed_episodes") != 1
        or metrics.get("episode_max_stage_reached") != [0]
        or metrics.get("episode_terminal_reasons") != ["stage_overtime"]
    ):
        raise RuntimeError("Attempt 2 terminal metrics do not match the final blocker")
    terminal = metrics["episode_terminal_diagnostics"][0]
    runtime_fixture = terminal["door_scenario"]
    for field, expected in EXPECTED_FIXTURE.items():
        _assert_close(runtime_fixture[field], expected, field)
    if terminal["door_hinge_drive_max_force"] != 7.25:
        raise RuntimeError("Terminal hinge force metadata is not the central fixture")
    if terminal["door_handle_drive_max_force"] != 2.0:
        raise RuntimeError("Terminal handle force metadata is not the central fixture")

    fixture_receipt = {
        "schema_version": "pull_v0_p1_central_fixture_receipt_v1",
        "generated_at_hkt": generated_at,
        "status": "PASS",
        "threshold_mode": "report_only",
        "fixture": {
            **EXPECTED_FIXTURE,
            "axle_length_m": 0.195,
            "handle_length_m": 0.125,
            "hook_length_m": 0.050,
            "handle_radius_m": 0.013,
            "hook_present": True,
        },
        "mass_range_authority": {
            "resolved_config": _artifact(
                EVIDENCE_ROOT / "source_freeze" / "v20_G4_resolved_config.yaml"
            ),
            "resolved_a2_door_weight_range_kg": [80.0, 160.0],
            "selected_midpoint_kg": 120.0,
            "repo_default_range_kg": [80.0, 120.0],
            "repo_default_used": False,
            "reason": (
                "Worker 2 Amendment 2 binds P1 to the resolved v20 G4 range; "
                "the repo-default range is not the runtime authority."
            ),
        },
        "runtime_confirmation": {
            "artifact": _artifact(attempt2_metrics_path),
            "door_scenario": runtime_fixture,
            "direction": terminal["pull_evidence_direction"],
            "physical_gpu": 4,
        },
        "repair_r1": {
            "artifact": _artifact(repair_receipt_path),
            "revision": repair_receipt["repair_revision"],
            "stale_candidate_id": repair_receipt["stale_candidate_id"],
            "physical_stage0_predicate_cause": repair_receipt["root_cause"][
                "physical_stage0_predicate_cause"
            ],
        },
        "static_only_fields": {
            "fields": [
                "axle_length_m",
                "handle_length_m",
                "hook_length_m",
                "handle_radius_m",
                "hook_present",
            ],
            "source_contract": (
                "DoorSpawnerCfg deterministic rand_* replacement; these fields are "
                "not exported as runtime tensors by current terminal diagnostics."
            ),
        },
    }

    anchor_receipt = {
        "schema_version": "pull_v0_p1_push_anchor_receipt_v1",
        "generated_at_hkt": generated_at,
        "status": "BLOCKED",
        "probe_validity": "PROBE_INVALID",
        "threshold_mode": "report_only",
        "repair_r1": {
            "artifact": _artifact(repair_receipt_path),
            "revision": repair_receipt["repair_revision"],
            "stale_candidate_id": repair_receipt["stale_candidate_id"],
            "root_cause_conclusion": repair_receipt["root_cause"]["conclusion"],
            "physical_stage0_predicate_cause": repair_receipt["root_cause"][
                "physical_stage0_predicate_cause"
            ],
        },
        "hard_gate": {
            "stable_bilateral_capture": False,
            "latch_release": False,
            "hinge_progress_min_rad": 0.25,
            "observed_max_hinge_rad": "N/A",
            "body_panel_contact": False,
            "pass": False,
        },
        "attempts": [
            {
                "attempt": 1,
                "kind": "INITIAL_IMPLEMENTATION",
                "result": "APPLICATION_CONFIG_ERROR_BEFORE_PROBE",
                "plan": _artifact(attempt1_plan_path),
                "process_receipt": _artifact(attempt1_receipt_path),
                "log": _artifact(attempt1_log_path),
                "finding": (
                    "The requested diagnostic reward set included an inactive term; "
                    "no anchor summary was produced and no mechanics verdict exists."
                ),
            },
            {
                "attempt": 2,
                "kind": "REPAIR_R1_ADMISSION_AND_TELEMETRY",
                "result": "NO_GATE",
                "plan": _artifact(attempt2_plan_path),
                "process_receipt": _artifact(attempt2_receipt_path),
                "summary": _artifact(attempt2_summary_path),
                "metrics": _artifact(attempt2_metrics_path),
                "finding": {
                    "completed_first_episodes": 1,
                    "max_stage": 0,
                    "terminal_reason": "stage_overtime",
                    "proof_samples": 0,
                    "arc_samples": 0,
                    "stage0_predicates": ["staging_band", "arm_default", "base_still"],
                    "scripted_activation_stage2_gate": False,
                    "proof_world_direction": "+X",
                    "terminal_target_pos_source_handle_distance_m": terminal[
                        "target_pos_source_handle_distance"
                    ],
                    "terminal_target_pos_source_pregrasp_distance_m": terminal[
                        "target_pos_source_pregrasp_distance"
                    ],
                },
            },
        ],
        "stop_condition": (
            "Worker 2 section 4.3: stop after the push-side anchor cannot pass "
            "following one implementation repair."
        ),
        "downstream_state": {
            "pull_side_p1_verdicts_recorded": False,
            "p1_mechanism_matrix_started": False,
            "p2_started": False,
            "next_action_requires_user_direction": True,
        },
        "interpretation": (
            "NO_GATE is a probe-design/admission blocker. It is not evidence that "
            "the pull mechanism is infeasible."
        ),
    }

    fixture_path = EVIDENCE_ROOT / "PULL_V0_P1_FIXTURE_RECEIPT.json"
    anchor_path = EVIDENCE_ROOT / "PULL_V0_P1_PUSH_ANCHOR_RECEIPT.json"
    _write_json(fixture_path, fixture_receipt)
    _write_json(anchor_path, anchor_receipt)
    print(f"Wrote {fixture_path.relative_to(ROOT)}")
    print(f"Wrote {anchor_path.relative_to(ROOT)}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build immutable legacy or post-R1 P1 anchor receipts."
    )
    parser.add_argument(
        "--attempt",
        type=_post_r1_attempt_arg,
        default=None,
        help="Post-R1 attempt index (integer >= 3); omit only for legacy receipt generation.",
    )
    parser.add_argument(
        "--repair-receipt",
        type=Path,
        default=None,
        help="Canonical repair path for the selected attempt; Attempt18 accepts Repair R15 and Attempt19 accepts Repair R16 preparation-only validation.",
    )
    parser.add_argument("--prelaunch-infra-receipt", type=Path, default=None)
    parser.add_argument("--repair-r15e-receipt", type=Path, default=None)
    parser.add_argument("--repair-r15f-receipt", type=Path, default=None)
    parser.add_argument("--retry1-launch-occupancy", type=Path, default=None)
    parser.add_argument("--retry1-steady-state-footprint", type=Path, default=None)
    args = parser.parse_args()
    if args.attempt is None:
        return _build_legacy_receipts()
    attempt = args.attempt
    if attempt >= 4 and args.repair_receipt is None:
        parser.error("--repair-receipt is required for attempts >=4")
    repair_receipt_path = args.repair_receipt or REPAIR_R1_RECEIPT_PATH
    if not repair_receipt_path.is_absolute():
        repair_receipt_path = ROOT / repair_receipt_path
    if attempt == 18:
        prelaunch_infra_receipt_path = (
            args.prelaunch_infra_receipt or ATTEMPT18_PRELAUNCH_INFRA_RECEIPT_PATH
        )
        r15e_receipt_path = args.repair_r15e_receipt or ATTEMPT18_R15E_RECEIPT_PATH
        r15f_receipt_path = args.repair_r15f_receipt or ATTEMPT18_R15F_RECEIPT_PATH
        retry1_launch_occupancy_path = (
            args.retry1_launch_occupancy or ATTEMPT18_RETRY1_LAUNCH_OCCUPANCY_PATH
        )
        retry1_steady_state_footprint_path = (
            args.retry1_steady_state_footprint
            or ATTEMPT18_RETRY1_STEADY_STATE_FOOTPRINT_PATH
        )
        prelaunch_paths = (
            ATTEMPT18_PLAN_PATH,
            ATTEMPT18_LAUNCH_OCCUPANCY_PATH,
            prelaunch_infra_receipt_path,
            r15e_receipt_path,
            r15f_receipt_path,
        )
        scientific_paths = (
            ATTEMPT18_PROCESS_PATH,
            ATTEMPT18_LOG_PATH,
            ATTEMPT18_SUMMARY_PATH,
            ATTEMPT18_METRICS_PATH,
            retry1_launch_occupancy_path,
            retry1_steady_state_footprint_path,
        )
        scientific_core_paths = (
            ATTEMPT18_PROCESS_PATH,
            ATTEMPT18_LOG_PATH,
            retry1_launch_occupancy_path,
            retry1_steady_state_footprint_path,
        )
        prelaunch_existing = [path.exists() for path in prelaunch_paths]
        scientific_existing = [path.exists() for path in scientific_paths]
        if not any(prelaunch_existing) and not any(scientific_existing):
            _validate_repair_receipt(repair_receipt_path, attempt=18)
            print("Validated Repair R15 for Attempt18 preparation only; no Attempt18 artifacts were created.")
            return 0
        if not all(prelaunch_existing):
            raise RuntimeError(
                "Attempt18 prelaunch infrastructure chain is incomplete; refusing retry admission."
            )
        if not any(scientific_existing):
            _validate_attempt18_prelaunch_chain(
                plan_path=ATTEMPT18_PLAN_PATH,
                initial_launch_occupancy_path=ATTEMPT18_LAUNCH_OCCUPANCY_PATH,
                prelaunch_infra_receipt_path=prelaunch_infra_receipt_path,
                r15e_receipt_path=r15e_receipt_path,
                r15f_receipt_path=r15f_receipt_path,
            )
            print("Validated preserved Attempt18 prelaunch infrastructure; ready for retry1 runtime.")
            return 0
        if not all(path.exists() for path in scientific_core_paths):
            raise RuntimeError(
                "Attempt18 retry1 runtime artifact chain is incomplete; refusing partial receipt build."
            )
        summary_exists = ATTEMPT18_SUMMARY_PATH.exists()
        metrics_exists = ATTEMPT18_METRICS_PATH.exists()
        if summary_exists != metrics_exists:
            raise RuntimeError(
                "Attempt18 retry1 summary/metrics artifact pair is incomplete; refusing partial receipt build."
            )
        receipt = build_post_r1_attempt_receipt(
            18,
            plan_path=ATTEMPT18_PLAN_PATH,
            process_receipt_path=ATTEMPT18_PROCESS_PATH,
            log_path=ATTEMPT18_LOG_PATH,
            summary_path=ATTEMPT18_SUMMARY_PATH,
            metrics_path=ATTEMPT18_METRICS_PATH,
            repair_receipt_path=repair_receipt_path,
            prelaunch_infra_receipt_path=prelaunch_infra_receipt_path,
            r15e_receipt_path=r15e_receipt_path,
            r15f_receipt_path=r15f_receipt_path,
            retry1_launch_occupancy_path=retry1_launch_occupancy_path,
            retry1_steady_state_footprint_path=retry1_steady_state_footprint_path,
        )
        _write_json(ATTEMPT18_RECEIPT_PATH, receipt)
        receipt_label = (
            str(ATTEMPT18_RECEIPT_PATH.relative_to(ROOT))
            if ATTEMPT18_RECEIPT_PATH.is_relative_to(ROOT)
            else str(ATTEMPT18_RECEIPT_PATH)
        )
        print(f"Wrote {receipt_label}")
        return 0
    if attempt == 19:
        _validate_repair_receipt(repair_receipt_path, attempt=19)
        attempt19_evidence_paths = (
            ATTEMPT19_PLAN_PATH,
            ATTEMPT19_PROCESS_PATH,
            ATTEMPT19_LOG_PATH,
            ATTEMPT19_SUMMARY_PATH,
            ATTEMPT19_METRICS_PATH,
            ATTEMPT19_LAUNCH_OCCUPANCY_PATH,
            ATTEMPT19_STEADY_STATE_FOOTPRINT_PATH,
        )
        existing = [path for path in (*attempt19_evidence_paths, ATTEMPT19_RECEIPT_PATH) if path.exists()]
        if not existing:
            print("Validated Repair R16 for Attempt19 preparation only; no Attempt19 plan or runtime artifacts were created.")
            return 0
        if ATTEMPT19_RECEIPT_PATH.exists():
            raise RuntimeError(f"Refusing to overwrite immutable Attempt19 receipt: {ATTEMPT19_RECEIPT_PATH}")
        if not all(path.is_file() and not path.is_symlink() for path in attempt19_evidence_paths):
            raise RuntimeError(
                "Attempt19 artifact chain is incomplete; canonical receipt creation requires the plan, process, log, summary, metrics, launch occupancy, and steady-state footprint."
            )
        receipt = build_post_r1_attempt_receipt(
            19,
            plan_path=ATTEMPT19_PLAN_PATH,
            process_receipt_path=ATTEMPT19_PROCESS_PATH,
            log_path=ATTEMPT19_LOG_PATH,
            summary_path=ATTEMPT19_SUMMARY_PATH,
            metrics_path=ATTEMPT19_METRICS_PATH,
            repair_receipt_path=repair_receipt_path,
            launch_occupancy_path=ATTEMPT19_LAUNCH_OCCUPANCY_PATH,
            steady_state_footprint_path=ATTEMPT19_STEADY_STATE_FOOTPRINT_PATH,
        )
        _write_json(ATTEMPT19_RECEIPT_PATH, receipt)
        print(f"Wrote {ATTEMPT19_RECEIPT_PATH.relative_to(ROOT)}")
        return 0
    output_path = EVIDENCE_ROOT / f"PULL_V0_P1_PUSH_ANCHOR_ATTEMPT{attempt}_RECEIPT.json"
    output_root = LOG_ROOT / f"attempt{attempt}"
    receipt = build_post_r1_attempt_receipt(
        attempt,
        plan_path=EVIDENCE_ROOT / f"PULL_V0_P1_PUSH_ANCHOR_ATTEMPT{attempt}_PLAN.json",
        process_receipt_path=output_root / "process_receipt.json",
        log_path=output_root / "stdout_stderr.log",
        summary_path=output_root / "eval" / "a2_hold_oracle_summary.json",
        metrics_path=output_root / "eval" / "metrics_eval.json",
        repair_receipt_path=repair_receipt_path,
    )
    _write_json(output_path, receipt)
    print(f"Wrote {output_path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
