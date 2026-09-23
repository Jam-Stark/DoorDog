# 本机IsaacLab限位API节选

采集日期：2026-09-18 HKT；extension version：0.54.4。
来源：/home/baoquanc/workspace/IsaacLab/source/isaaclab/isaaclab/assets/articulation/articulation.py
原始行号：710–768。保留该方法完整实现，未修改语义；静态接口证据，不是运行验证。

```python
    def write_joint_position_limit_to_sim(
        self,
        limits: torch.Tensor | float,
        joint_ids: Sequence[int] | slice | None = None,
        env_ids: Sequence[int] | None = None,
        warn_limit_violation: bool = True,
    ):
        """Write joint position limits into the simulation.

        Args:
            limits: Joint limits. Shape is (len(env_ids), len(joint_ids), 2).
            joint_ids: The joint indices to set the limits for. Defaults to None (all joints).
            env_ids: The environment indices to set the limits for. Defaults to None (all environments).
            warn_limit_violation: Whether to use warning or info level logging when default joint positions
                exceed the new limits. Defaults to True.
        """
        # note: This function isn't setting the values for actuator models. (#128)
        # resolve indices
        physx_env_ids = env_ids
        if env_ids is None:
            env_ids = slice(None)
            physx_env_ids = self._ALL_INDICES
        if joint_ids is None:
            joint_ids = slice(None)
        # broadcast env_ids if needed to allow double indexing
        if env_ids != slice(None) and joint_ids != slice(None):
            env_ids = env_ids[:, None]
        # set into internal buffers
        self._data.joint_pos_limits[env_ids, joint_ids] = limits
        # update default joint pos to stay within the new limits
        if torch.any(
            (self._data.default_joint_pos[env_ids, joint_ids] < limits[..., 0])
            | (self._data.default_joint_pos[env_ids, joint_ids] > limits[..., 1])
        ):
            self._data.default_joint_pos[env_ids, joint_ids] = torch.clamp(
                self._data.default_joint_pos[env_ids, joint_ids], limits[..., 0], limits[..., 1]
            )
            violation_message = (
                "Some default joint positions are outside of the range of the new joint limits. Default joint positions"
                " will be clamped to be within the new joint limits."
            )
            if warn_limit_violation:
                # warn level will show in console
                logger.warning(violation_message)
            else:
                # info level is only written to log file
                logger.info(violation_message)
        # set into simulation
        self.root_physx_view.set_dof_limits(self._data.joint_pos_limits.cpu(), indices=physx_env_ids.cpu())

        # compute the soft limits based on the joint limits
        # TODO: Optimize this computation for only selected joints
        # soft joint position limits (recommended not to be too close to limits).
        joint_pos_mean = (self._data.joint_pos_limits[..., 0] + self._data.joint_pos_limits[..., 1]) / 2
        joint_pos_range = self._data.joint_pos_limits[..., 1] - self._data.joint_pos_limits[..., 0]
        soft_limit_factor = self.cfg.soft_joint_pos_limit_factor
        # add to data
        self._data.soft_joint_pos_limits[..., 0] = joint_pos_mean - 0.5 * joint_pos_range * soft_limit_factor
        self._data.soft_joint_pos_limits[..., 1] = joint_pos_mean + 0.5 * joint_pos_range * soft_limit_factor
```

PhysX原生limit要求lower<upper，等值需motion locked：[官方说明](https://nvidia-omniverse.github.io/PhysX/physx/5.8.0/_api_build/structPxArticulationLimit.html)。
此版本setter会更新缓存/default/soft limits，并向PhysX传CPU tensor；并行规模的切换成本尚未测量。
