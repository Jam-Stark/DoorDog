# Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0


import math

import torch
from omegaconf.dictconfig import DictConfig
from torch.optim import Optimizer
from torch.optim.lr_scheduler import _LRScheduler


def update_scheduled_params(obj, scheduler_dict, step, split_char="@"):
    """Apply validated scheduled parameters and fire exact boundary callbacks.

    R1 uses this generic scheduler with a segment [0, 500] string schedule;
    no R1-specific scheduler branch is introduced.
    """
    if isinstance(step, bool) or not isinstance(step, int) or step < 0:
        raise ValueError(f"scheduled parameter step must be a non-negative int; got {step!r}.")
    if scheduler_dict is None:
        return {}
    if not hasattr(scheduler_dict, "items"):
        raise TypeError("scheduler_dict must be a mapping.")
    scheduled_params_dict = {}
    converters = {"float": float, "int": int, "str": str, "bool": bool}
    for target, cfg in scheduler_dict.items():
        if not isinstance(target, str) or not target:
            raise ValueError(f"scheduled target must be a non-empty string; got {target!r}.")
        if not hasattr(cfg, "get"):
            raise TypeError(f"schedule entry {target!r} must be a mapping.")
        sch_type = cfg.get("type")
        if sch_type not in ("linear", "segment"):
            raise ValueError(f"unsupported schedule type {sch_type!r} for {target!r}.")
        val_type = cfg.get("val_type", "float")
        if val_type not in converters:
            raise ValueError(f"unsupported schedule val_type {val_type!r} for {target!r}.")
        seg_steps = list(cfg.get("seg_steps", ()))
        seg_vals = list(cfg.get("seg_vals", ()))
        if not seg_steps or len(seg_steps) != len(seg_vals):
            raise ValueError(f"schedule {target!r} requires equally sized non-empty seg_steps/seg_vals.")
        if any(isinstance(v, bool) or not isinstance(v, int) for v in seg_steps):
            raise ValueError(f"schedule {target!r} seg_steps must be integer boundaries.")
        if any(v < 0 for v in seg_steps) or any(a >= b for a, b in zip(seg_steps, seg_steps[1:])):
            raise ValueError(f"schedule {target!r} seg_steps must be monotonic non-negative boundaries.")
        target_attr = target
        target_obj = obj
        if split_char in target:
            target_obj_str, target_attr = target.rsplit(split_char, 1)
            for x in target_obj_str.split(split_char):
                if x.lstrip("-").isdigit():
                    target_obj = target_obj[int(x)]
                else:
                    target_obj = getattr(target_obj, x)
        if sch_type == "linear":
            if len(seg_vals) < 2:
                raise ValueError(f"linear schedule {target!r} requires at least two values.")
            i = len(seg_vals) - 1
            while i > 0 and step < seg_steps[i]:
                i -= 1
            if i == len(seg_vals) - 1:
                val = seg_vals[i]
            else:
                denominator = seg_steps[i + 1] - seg_steps[i]
                if denominator <= 0:
                    raise ValueError(f"linear schedule {target!r} has invalid segment width.")
                t = (step - seg_steps[i]) / denominator
                t = max(0.0, min(1.0, t))
                val = (1.0 - t) * seg_vals[i] + t * seg_vals[i + 1]
        else:
            i = len(seg_vals) - 1
            while i > 0 and step < seg_steps[i]:
                i -= 1
            val = seg_vals[i]
        val = converters[val_type](val)

        if isinstance(val, (DictConfig, dict)):
            if target_attr.lstrip("-").isdigit():
                tmp_obj = target_obj[int(target_attr)]
            else:
                tmp_obj = getattr(target_obj, target_attr)
            if cfg.get("overwrite_dict", False):
                if target_attr.lstrip("-").isdigit():
                    target_obj[int(target_attr)] = val
                else:
                    setattr(target_obj, target_attr, val)
            else:
                for k, v in val.items():
                    if isinstance(tmp_obj, dict):
                        tmp_obj[k] = v
                    else:
                        setattr(tmp_obj, k, v)
        else:
            if target_attr.lstrip("-").isdigit():
                target_obj[int(target_attr)] = val
            else:
                setattr(target_obj, target_attr, val)

        scheduled_params_dict[target] = val
        if "trigger_func" in cfg and step in seg_steps:
            trigger_obj = obj
            target_func = cfg["trigger_func"]
            if not isinstance(target_func, str) or split_char not in target_func:
                raise ValueError(f"schedule {target!r} trigger_func must be a dotted @ path.")
            target_obj_str, target_func = target_func.rsplit(split_char, 1)
            for x in target_obj_str.split(split_char):
                trigger_obj = getattr(trigger_obj, x)
            # Expose the exact boundary to callbacks without creating a
            # special scheduler API.  The callback itself validates it.
            setattr(trigger_obj, "_a2_v20_R1_schedule_step", step)
            getattr(trigger_obj, target_func)()
    return scheduled_params_dict


class WarmupCosineScheduler(_LRScheduler):
    def __init__(
        self,
        optimizer: Optimizer,
        num_warmup_steps: int,
        num_training_steps: int,
        final_lr: float = 0.0,
        last_epoch: int = -1,
    ):
        self.num_warmup_steps = num_warmup_steps
        self.num_training_steps = num_training_steps
        self.final_lr = final_lr
        super(WarmupCosineScheduler, self).__init__(optimizer, last_epoch)

    def get_lr(self):
        current_step = self.last_epoch
        if current_step < self.num_warmup_steps:
            return [
                base_lr * float(current_step) / float(max(1, self.num_warmup_steps))
                for base_lr in self.base_lrs
            ]
        else:
            progress = float(current_step - self.num_warmup_steps) / float(
                max(1, self.num_training_steps - self.num_warmup_steps)
            )
            cosine_decay = 0.5 * (1.0 + math.cos(math.pi * min(progress, 1.0)))
            return [
                self.final_lr + (base_lr - self.final_lr) * cosine_decay
                for base_lr in self.base_lrs
            ]


if __name__ == "__main__":

    class YourModel(torch.nn.Module):
        def __init__(self):
            super(YourModel, self).__init__()
            self.fc = torch.nn.Linear(10, 1)

        def forward(self, x):
            return self.fc(x)

    model = YourModel()
    optimizer = torch.optim.AdamW(model.parameters(), lr=0.001)

    num_warmup_steps = 1000
    num_training_steps = 10000
    final_lr = 0.0001

    scheduler = WarmupCosineScheduler(optimizer, num_warmup_steps, num_training_steps, final_lr)

    lrs = []
    for step in range(num_training_steps):
        scheduler.step()
        lrs.append(scheduler.get_lr()[0])

    # Plotting the learning rate vs training steps
    import matplotlib.pyplot as plt

    plt.plot(range(num_training_steps), lrs)
    plt.xlabel("Training Steps")
    plt.ylabel("Learning Rate")
    plt.title("Learning Rate vs Training Steps")
    # plt.show()
    plt.savefig("out/lr_vs_steps.png")
