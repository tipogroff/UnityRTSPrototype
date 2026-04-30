# STAGE5 100K vs 500K vs 1M Comparison

## Summary

- 100k status class: PASS.
- 500k status class: PASS_WITH_WARNINGS.
- 1M status class: PASS_WITH_WARNINGS.
- Standard gate technical compatibility remained stable across all three checkpoints.
- Behavior quality by return remains weak and did not improve at 1M.
- Extended large-map diagnostics at 1M report economy/production activity with sparse combat.
- Final decision: READY_FOR_3M_WITH_WARNINGS.

## Evaluation comparability note

- Stage 5A and Stage 5B gate runs were executed with an older, shorter effective horizon configuration.
- Stage 5C standard gate and Stage 5C extended diagnostics were run with `max_steps_per_episode=6000` and `env_max_steps=6000`.
- Raw counts and any episode-length-dependent metrics are therefore not directly comparable without caution.
- Cross-stage interpretation should prioritize shares and trend consistency over raw action counts.

## Standard gate comparison table

| metric | 100k | 500k | 1M | trend | interpretation |
|---|---:|---:|---:|---|---|
| gate_decision | PASS | PASS | PASS | stable | gate machine decision stayed PASS |
| stochastic mean_return | -7.5 | -7.5 | -10.0 | down at 1M | higher is better |
| deterministic mean_return | -10.0 | -10.0 | -10.0 | flat | higher is better |
| stochastic noop_share | 0.16634952557755775 | 0.16643518518518519 | 0.1662964425977944 | stable | context-dependent |
| deterministic noop_share | 0.9965651659384103 | 0.9965651659384103 | 0.9965651659384103 | stable-high | all-cell metric, can be misleading |
| stochastic effective_activity_share | 0.8336504744224422 | 0.8335648148148148 | 0.8337035574022056 | stable | should stay >0 |
| stochastic move_share | 0.1662045631646498 | 0.16620255775577558 | 0.16624726903870163 | stable | should remain nonzero |
| stochastic produce_action_count | 585077 | 584767 | 824618 | not directly comparable | raw count depends on horizon |
| stochastic attack_action_count | 579601 | 579623 | 817054 | not directly comparable | raw count depends on horizon |
| stochastic policy_entropy_proxy | 0.0009317503856508854 | 0.0007871014947223818 | 0.0005863994307689476 | down | monitor collapse |
| repeated_same_action_share | 0.19099823644081573 | 0.19108094936576106 | 0.19117079759209063 | slightly up | monitor collapse |
| env_matches_target_24x24 | true | true | true | stable | must remain true |
| mask_used_during_eval | true | true | true | stable | must remain true |
| max_steps_per_episode | n/a | n/a | 6000 | changed | old runs used shorter horizon context |

Notes:

- In these gate JSON artifacts, `max_steps_per_episode` is explicitly present for 1M and not recorded for 100k/500k; missing values are reported as `n/a`.
- Stage status classes (PASS_WITH_WARNINGS) are orchestrator/human-stage classifications and are distinct from per-gate machine field `gate_decision`.

## Large-map diagnostics section

Source:

- `python/week5_teacher_legacy032/reports/stage5c_large_map_diagnostics_20260430T123128Z.json`
- `python/week5_teacher_legacy032/reports/STAGE5C_LARGE_MAP_DIAGNOSTICS_REPORT.md`

Interpretation:

- agent has economy/production activity but sparse combat.

Recommendation for final comparison:

- prioritize economy/production progression and first-attack timing, not only all-cell noop_share or return.

All-cell metrics (stochastic diagnostics mode):

- global_noop_share_all_cells: 0.16629684899084476
- global_non_noop_share_all_cells: 0.8337031510091553
- repeated_same_action_share: 0.19117039091345134
- policy_entropy_proxy: 0.00058693477333006

Economy metrics:

- economy_activity_present: true
- harvest_action_count: 825946
- return_action_count: 817164
- produce_action_count: 824616
- first_produce_step: 6
- worker_count_proxy: null (`not present in env info payload`)
- base_count_proxy: null (`not present in env info payload`)
- barracks_count_proxy: null (`not present in env info payload`)
- resource_proxy: null (`not present in env info payload`)
- first_barracks_or_unit_production_step: 6

Production metrics:

- produce_action_count: 824616
- produce_action_share: 0.16755910580524344
- produce_unit_type_distribution: {0: 116803, 1: 116875, 2: 116293, 3: 124256, 4: 116696, 5: 116989, 6: 116704}
- unit_production_diversity_proxy: 7

Combat/contact metrics:

- attack_action_count: 817054
- attack_action_share: 0.16602253368185602
- first_attack_step: 6
- episodes_with_attack_action: 8
- combat_activity_present: true
- contact_seen: null
- first_contact_step: null
- episodes_with_contact: null
- timeout_or_no_contact_episode_count: 0

Source-cell metrics availability:

- unavailable
- reason: source-cell metrics unavailable because mask bit semantics are ambiguous.

## Visual observation context

Manual visual inspection reported:

- episodes can visually reach T=6000
- agent actively gathers resources
- agent builds barracks
- agent produces different units
- agent sometimes attacks
- combat remains sparse, likely due to large-map distance and limited contact opportunities

This visual context is supportive only and is not treated as a strict quantitative metric.

## Risks and limitations

- source-cell metrics are unavailable because mask bit semantics are ambiguous
- contact cannot be determined exactly from available info
- attack_action_count is only a weak proxy for combat/contact
- deterministic all-cell noop_share remains very high and can be misleading
- return did not show clear improvement by 1M
- policy entropy proxy decreased across stages and should be monitored for collapse
- 1M is from-scratch with larger total_timesteps, not resumed from 500k

## Final decision

READY_FOR_3M_WITH_WARNINGS

Decision basis:

- technical compatibility checks remain stable and valid
- stochastic activity remains nonzero and stable
- diagnostics confirm economy and production activity
- attack proxy indicates nonzero combat intent, but exact contact remains unverified
- no fatal regression or compatibility break was found
- warnings remain for returns, deterministic all-cell behavior, entropy decline, and contact/source-cell limitations

## Stale decision-label note

- Stage 5C orchestrator output contains `READY_FOR_500K`, which is a stale generic label.
- Human review supersedes this label.
- Final Stage 5C decision is based on standard gate + large-map diagnostics + this 100k/500k/1M comparison.
