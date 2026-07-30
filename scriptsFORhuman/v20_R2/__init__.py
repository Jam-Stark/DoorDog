"""Contract-first helpers and command line tools for base_v20_R2.

The R2 namespace is intentionally independent from ``v20_R1``.  R2 tools may
read immutable R1 inputs, but must not import an R1 producer or consumer.
"""

from __future__ import annotations

SCIENTIFIC_PLAN_ID = "base_v20_R1_policy_behavior_v1"
ADMISSION_PLAN_ID = "base_v20_R2_admission_execution_v1"

__all__ = ["ADMISSION_PLAN_ID", "SCIENTIFIC_PLAN_ID"]
