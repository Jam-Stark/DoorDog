"""Pull-v6.1 integrated actor with unchanged pull-v6 post-release behavior."""

from __future__ import annotations

from gr00t.rl.trl.modules.pull_v6_post_release_obs_override_actor import (
    PullV6PostReleaseObsOverrideActor,
)


class PullV6PostReleaseIntegratedActor(PullV6PostReleaseObsOverrideActor):
    """Train the existing carrier, release means, D override, and action std together."""

    def __init__(
        self, *args, freeze_running_mean_std: bool = True, **kwargs
    ) -> None:
        super().__init__(*args, **kwargs)
        for parameter in self.memory.parameters():
            parameter.requires_grad_(True)
        for parameter in self.actor_module.parameters():
            parameter.requires_grad_(True)
        self.release_mode_gripper_mean_override.requires_grad_(True)
        for parameter in self.post_release_obs_override.parameters():
            parameter.requires_grad_(True)
        self.std.requires_grad_(True)
        if self.running_mean_std is not None:
            if freeze_running_mean_std:
                self.running_mean_std.freeze()
            else:
                self.running_mean_std.unfreeze()
