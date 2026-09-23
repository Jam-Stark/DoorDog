"""Control-only pause for the Owner-authorized C002 7000 evaluation."""

import json
import os
from pathlib import Path
import signal
import time

import torch
from transformers import TrainerCallback


class MilestonePause(TrainerCallback):
    def __init__(self, output_dir):
        self.output_dir = Path(output_dir)

    def on_step_end(self, args, state, control, **kwargs):
        if state.global_step != 7000:
            return
        checkpoint = Path(args.output_dir) / "model_step_007000.pt"
        if not checkpoint.is_file():
            raise RuntimeError("7000 pause must run after the checkpoint save callback.")
        torch.cuda.synchronize()
        receipt = {
            "global_step": state.global_step,
            "pid": os.getpid(),
            "epoch": time.time(),
            "checkpoint": str(checkpoint),
            "action": "SIGSTOP after checkpoint and CUDA synchronization",
        }
        target = self.output_dir / "pause7000.json"
        temporary = target.with_suffix(".tmp")
        temporary.write_text(json.dumps(receipt, indent=2) + "\n")
        temporary.replace(target)
        os.kill(os.getpid(), signal.SIGSTOP)
        (self.output_dir / "resumed7000.json").write_text(
            json.dumps({"global_step": state.global_step, "pid": os.getpid(), "epoch": time.time()}, indent=2) + "\n"
        )
