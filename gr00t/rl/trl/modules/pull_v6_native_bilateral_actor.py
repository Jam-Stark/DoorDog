"""Fully trainable recurrent actor for native bilateral pull learning."""

from __future__ import annotations

from gr00t.rl.trl.modules.pull_v6_post_release_obs_override_actor import (
    PullV6PostReleaseObsOverrideActor,
)


class PullV6NativeBilateralActor(PullV6PostReleaseObsOverrideActor):
    """Train the entire 135-D recurrent policy without a side-specialist parent."""

    def __init__(
        self, *args, freeze_running_mean_std: bool = False, **kwargs
    ) -> None:
        if freeze_running_mean_std:
            raise ValueError(
                "Native bilateral training requires freeze_running_mean_std=false."
            )
        super().__init__(*args, **kwargs)
        for parameter in self.parameters():
            parameter.requires_grad_(True)
        if self.running_mean_std is None:
            raise RuntimeError("Native bilateral actor requires running normalization.")
        self.running_mean_std.unfreeze()
