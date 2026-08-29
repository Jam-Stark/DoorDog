"""Pull-v6.1 D25-gated current-observation post-release controller."""

from __future__ import annotations

import torch

from gr00t.rl.trl.modules.pull_v6_post_release_obs_override_actor import (
    PullV6PostReleaseObsOverrideActor,
)
from gr00t.rl.trl.utils.rl import unsplit_trajectories


class PullV6LatePostReleaseObsOverrideActor(PullV6PostReleaseObsOverrideActor):
    """Activate the learned base/arm override only after the stable D25 handoff."""

    def _post_release_control(
        self, obs_dict, release_mode: torch.Tensor, masks=None, original_dones=None
    ) -> torch.Tensor:
        del release_mode
        control = obs_dict[self.input_key][..., -3:-2]
        if control.ndim == 3 and masks is not None and original_dones is not None:
            control = unsplit_trajectories(control, masks, original_dones)
        return control
