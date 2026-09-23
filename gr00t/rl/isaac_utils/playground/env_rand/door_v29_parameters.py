"""Fixed per-door B01/B04 parameters. All dynamics values use SI units."""

import math
from collections.abc import Sequence

import numpy as np


MASS_RANGES_KG = ((30.0, 80.0), (80.0, 120.0), (120.0, 160.0))


def sample_door_parameters(
    sides: Sequence[str], rng: np.random.Generator
) -> list[dict]:
    """Balance the six mass/closer cells within each side, then shuffle.

    Integer remainders also balance the mass and closer marginals (difference
    at most one). Geometry and the physics engine determine inertia; this
    sampler never substitutes a plate approximation for the actual inertia.
    """
    result = [{} for _ in sides]
    for side in ("left", "right"):
        indices = [i for i, value in enumerate(sides) if value == side]
        mass_order = rng.permutation(3)
        closer_flip = int(rng.integers(2))
        cells = [
            (int(mass_order[i % 3]), bool((i % 2) ^ closer_flip))
            for i in range(len(indices))
        ]
        rng.shuffle(cells)
        for index, (mass_bucket, closer_enabled) in zip(indices, cells):
            torque = float(rng.uniform(2.5, 12.0)) if closer_enabled else 0.0
            omega = float(rng.uniform(0.15, 0.40)) if closer_enabled else 0.0
            static = float(rng.uniform(0.0, 1.0))
            result[index] = {
                "mass_bucket": mass_bucket,
                "mass_kg": float(rng.uniform(*MASS_RANGES_KG[mass_bucket])),
                "closer_enabled": closer_enabled,
                "torque_cap_nm": torque,
                "omega_ref_rad_s": omega,
                "stiffness_nm_rad": torque / (math.pi / 2.0 + math.pi / 18.0),
                "damping_nm_s_rad": torque / omega if closer_enabled else 0.0,
                "target_position_rad": -math.pi / 18.0,
                "static_friction_nm": static,
                "dynamic_friction_nm": static * float(rng.uniform(0.5, 1.0)),
                "viscous_friction_nm_s_rad": float(rng.uniform(0.0, 0.5)),
                "max_opening_deg": float(rng.uniform(90.0, 150.0)),
            }
    if any(not parameters for parameters in result):
        raise ValueError("v29 door sides must be left or right")
    return result
