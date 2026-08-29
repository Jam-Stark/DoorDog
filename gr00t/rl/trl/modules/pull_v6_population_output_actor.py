"""Pull-v6.1 population actor with a frozen recurrent carrier."""

from __future__ import annotations

from gr00t.rl.trl.modules.pull_v6_post_release_obs_override_actor import (
    PullV6PostReleaseObsOverrideActor,
)


class PullV6PopulationOutputActor(PullV6PostReleaseObsOverrideActor):
    """Train policy outputs and mode heads while preserving the learned LSTM state map."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        for parameter in self.actor_module.parameters():
            parameter.requires_grad_(True)
        self.release_mode_gripper_mean_override.requires_grad_(True)
        for parameter in self.post_release_obs_override.parameters():
            parameter.requires_grad_(True)
        self.std.requires_grad_(True)
        if self.running_mean_std is not None:
            self.running_mean_std.freeze()
