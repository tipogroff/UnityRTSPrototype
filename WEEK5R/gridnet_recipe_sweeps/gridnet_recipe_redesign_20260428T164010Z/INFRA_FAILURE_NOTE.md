# Infrastructure Failure Note

- Sweep: gridnet_recipe_redesign_20260428T164010Z
- Date: 2026-04-28

## What happened

- `B_entropy_decay`, `C_passive_warmup_entropy_decay`, and `D_activity_shaping_mild` failed during training due to Windows TensorBoard path handling (`FileNotFoundError` / `WinError 206`, path length issues).
- These failures are infrastructure failures, not behavioral recipe outcomes.

## Validity of prior decision

- The reported decision `REJECT_CURRENT_GRIDNET_RECIPE` in this sweep is partial/invalid for full recipe comparison because only `A_low_entropy` completed.
- Only `A_low_entropy` metrics from this sweep are behaviorally valid.

## Required follow-up

- Apply TensorBoard path robustness fix.
- Re-run failed configs: `B_entropy_decay`, `C_passive_warmup_entropy_decay`, `D_activity_shaping_mild`.
- Re-evaluate final decision only after those configs complete.
