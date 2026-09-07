# Pull v26-8 Wave2 continuation contract

Admission uses the frozen first Wave1 bilateral-unlatch endpoint (step4500) and observed opening emergence. After the final Wave1 `step6000` reducer completes, Main freezes exactly two source cells using this D-only ranking stated before the final readout: bilateral durable-unlatch pass first, then descending `min(D_LEFT, D_RIGHT)`, then descending `D_LEFT + D_RIGHT`, then lower seed. The ranking reads only final Wave1 `D`; it never reads Wave2 E7, a mid-run checkpoint, or a mid-run E event.

Each selected cell keeps its Wave1 seed, plain actor, reward/event definitions, mirror setting, 1024 environments, reset ratios, `a2_pull_v6_stage4_bank_enabled=false`, `a2_pull_v61_late_state_bank_enabled=false`, and native learning-rate behavior. It loads its own final Wave1 `model_step_006000.pt` with `checkpoint_load_mode=full`, then sets `algo.trl.num_total_batches=9000`. The trainer therefore restores `global_step=6000` and performs exactly batches 6001 through 9000.

Full loading restores policy, critic, optimizer, scheduler, and trainer state. The online staged-reset buffers are not serialized by the current environment state writer, so a new Wave2 process begins accumulating those samples again. This is a protocol limit, not a new bank or loader behavior.

Milestones are 6750, 7500, 8250, and 9000. Each selected cell is evaluated serially on GPU0 with exact64 LEFT and RIGHT first natural episodes, the float Stage0-only ratios `[1.0,0.0,0.0,0.0,0.0,0.0]`, both v6 bank switches false, birth traces, six reward diagnostics, and `checkpoint_load_mode=full`.

The final typed label is `PULL_FULL_CHAIN_BILATERAL` only if both selected seeds have LEFT and RIGHT `E7 >= 32/64` at step9000. Otherwise it is `PULL_FULL_CHAIN_PARTIAL`.
