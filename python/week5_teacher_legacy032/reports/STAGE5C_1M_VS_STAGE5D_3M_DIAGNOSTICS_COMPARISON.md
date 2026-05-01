# STAGE5C 1M vs STAGE5D 3M Diagnostics Comparison

## Scope

- Stage 5C source: `python/week5_teacher_legacy032/reports/stage5c_large_map_diagnostics_20260430T123128Z.json`
- Stage 5D source: `python/week5_teacher_legacy032/reports/stage5d_large_map_win_diagnostics_20260501T083049Z.json`
- Comparison mode priority: stochastic metrics for behavior trend, deterministic metrics for collapse/noop checks.

## Technical compatibility

- Stage 5C (1M): metadata and env contract matched target 24x24 gridmode.
- Stage 5D (3M): `checkpoint_load_ok=true`, `policy_architecture_load_ok=true`, `inference_ok=true`, `env_matches_target_24x24=true`, `mask_used_during_eval=true`.
- Conclusion: technical compatibility remains stable.

## Core metric table

| metric | Stage 5C 1M | Stage 5D 3M | interpretation |
|---|---:|---:|---|
| stochastic mean_return | -10.0 | -10.0 | no improvement |
| deterministic mean_return | -10.0 | -10.0 | no improvement |
| deterministic noop_share (all-cell) | 0.9965651659384103 | 0.9965708654198753 | remains near-total |
| stochastic noop_share (all-cell) | 0.16629684899084476 | 0.16628151356802348 | stable |
| stochastic effective_activity_share (all-cell non-noop) | 0.8337031510091553 | 0.8337184864319765 | stable, nonzero |
| stochastic policy_entropy_proxy | 0.00058693477333006 | 0.0006555096716573923 | no entropy-collapse signal |
| stochastic repeated_same_action_share | 0.19117039091345134 | 0.19113433983493908 | stable/slightly improved |
| stochastic produce_action_count | 824616 | 1462346 | increased; partly episode-count dependent (8 vs 16) |
| stochastic unit_production_diversity_proxy | 7 | 7 | stable diversity |
| stochastic attack_action_count | 817054 | 1449229 | increased; episode-count dependent (8 vs 16) |
| stochastic episodes_with_attack_action | 8 | 16 | all episodes show attack action proxy |

## Production distribution

- Stage 5C 1M produce_unit_type_distribution:
  - {0: 116803, 1: 116875, 2: 116293, 3: 124256, 4: 116696, 5: 116989, 6: 116704}
- Stage 5D 3M produce_unit_type_distribution:
  - {0: 207006, 1: 207898, 2: 206418, 3: 220355, 4: 206937, 5: 207127, 6: 206605}
- Interpretation:
  - diversity remains broad and non-collapsed in stochastic mode.

## Outcome and base-destruction metrics

- Stage 5C 1M diagnostics:
  - explicit win/loss/draw and base-destruction fields were not part of the script payload.
- Stage 5D 3M win diagnostics:
  - terminal-derived counts: win=0, loss=0, draw=16
  - enemy_base_destroyed_count: n/a (null)
  - own_base_destroyed_count: n/a (null)
  - first_enemy_base_damage_step: n/a (null)
  - first_enemy_base_destroyed_step: n/a (null)
  - episodes_with_contact: n/a (null)
  - reason: current env info payload does not expose sufficient base/contact semantics in a reliable way.

## Deterministic vs stochastic behavior

- Deterministic:
  - near-total noop pattern persists and move_share remains zero.
  - attack/produce exist but at very low share.
- Stochastic:
  - all-cell activity remains high and balanced across action types.
  - economy/production/attack proxies remain nonzero and stable.

## Manual visual observation cross-check

Supporting context (non-strict):

- manual observation indicates late-training improvement,
- eventual enemy-base destruction,
- near-end episodes potentially destroying base around T~2000 or earlier.

Diagnostics cross-check:

- confirmed_by_metrics: partial
- matching evidence:
  - economy/production timing is consistently active,
  - attack proxy is consistently nonzero.
- contradictions:
  - return remains flat at -10.0,
  - terminal outcomes remain draws in available metrics.
- unresolved:
  - exact base destruction and contact timing are not confirmed by current machine-readable payload.

## Limitations

- source-cell metrics unavailable because mask bit semantics are ambiguous.
- contact cannot be determined exactly from available info; attack_action_count is weak proxy only.
- base destruction cannot be determined exactly from available info payload; fields remain null when not detectable.
- movement_toward_enemy_base_proxy cannot be determined safely without trustworthy enemy-base direction semantics.

## Decision for next prompt

HOLD_FOR_REWARD_OR_EVAL_DIAGNOSTICS

Rationale:

- technical compatibility is stable and non-collapsed stochastic behavior is present,
- but key decision-critical outcome metrics (base destruction/contact/time-to-kill) are still not directly observable in reliable machine-readable form,
- therefore evidence is insufficient for a robust READY_FOR_5M_WITH_WARNINGS decision.

## Exact next action

- Improve evaluation instrumentation for terminal outcomes/base destruction/contact in the legacy032 diagnostics path and rerun Stage 5D diagnostics before any 5M decision.
