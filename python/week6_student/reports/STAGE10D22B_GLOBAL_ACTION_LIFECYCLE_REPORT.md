# STAGE10D22B Global Action Lifecycle Diagnostic Report

- Generated (UTC): 2026-05-04T05:40:28.458855+00:00
- FULL_TRI_MODE=true
- Source run manifest: python/week6_student/tmp/stage10d22_global_lifecycle/stage10d22_run_manifest.json
- Explicit GO/NO-GO verdict: GO

## FULL_TRI_MODE status
- FULL_TRI_MODE=true

## Per-mode status
- student_live_policy: steps_completed=80, target_steps=80, scripted_attempted=0, scripted_accepted=0, scripted_completed=True
- heuristic_baseline: steps_completed=80, target_steps=80, scripted_attempted=0, scripted_accepted=0, scripted_completed=True
- scripted_deterministic_commands: steps_completed=80, target_steps=80, scripted_attempted=80, scripted_accepted=65, scripted_completed=True

## Raw action distribution by mode

### student_live_policy
| Action | RawSelected |
|---|---|
| NoOp | 272 |
| Move | 0 |
| Harvest | 124 |
| Return | 0 |
| Produce | 86 |
| Attack | 0 |

### heuristic_baseline
| Action | RawSelected |
|---|---|
| NoOp | 272 |
| Move | 0 |
| Harvest | 124 |
| Return | 0 |
| Produce | 86 |
| Attack | 0 |

### scripted_deterministic_commands
| Action | RawSelected |
|---|---|
| NoOp | 313 |
| Move | 0 |
| Harvest | 93 |
| Return | 0 |
| Produce | 108 |
| Attack | 0 |

## A. Raw selection table
| Action | RawSelected |
|---|---|
| NoOp | 857 |
| Move | 0 |
| Harvest | 341 |
| Return | 0 |
| Produce | 280 |
| Attack | 0 |

## B. Raw -> mask table
| Action | RawSelected | MaskAllowedByRaw |
|---|---|---|
| NoOp | 857 | 800 |
| Move | 0 | 0 |
| Harvest | 341 | 209 |
| Return | 0 | 0 |
| Produce | 280 | 81 |
| Attack | 0 | 0 |

## C. Post-mask/effective decoding table
| Action | PostMask | Decoded | Submitted |
|---|---|---|---|
| NoOp | 1196 | 1146 | 1382 |
| Move | 0 | 33 | 33 |
| Harvest | 208 | 220 | 23 |
| Return | 0 | 2 | 2 |
| Produce | 74 | 77 | 38 |
| Attack | 0 | 0 | 0 |

## D. Runtime lifecycle table
| Action | ApplierAccepted | RuntimeApplied | StateDelta | state_delta_1_step | state_delta_5_step | state_delta_20_step |
|---|---|---|---|---|---|---|
| NoOp | 0 | 0 | 0 | 0 | 0 | 0 |
| Move | 33 | 33 | 0 | 0 | 0 | 0 |
| Harvest | 23 | 23 | 5 | 5 | 5 | 5 |
| Return | 2 | 2 | 0 | 0 | 0 | 0 |
| Produce | 36 | 36 | 3 | 3 | 27 | 24 |
| Attack | 0 | 0 | 0 | 0 | 0 | 0 |

## E. First failing boundary table
| Action | FirstFail |
|---|---|
| NoOp | applier_accepted |
| Move | raw_selected |
| Harvest | none |
| Return | raw_selected |
| Produce | none |
| Attack | raw_selected |

## Raw->post-mask transition table
- NoOp->NoOp: 857
- Harvest->Harvest: 208
- Harvest->NoOp: 133
- Produce->NoOp: 206
- Produce->Produce: 74

## Post-mask->decoded transition table
- NoOp->Harvest: 1
- NoOp->Move: 19
- NoOp->NoOp: 837
- Harvest->Harvest: 206
- Harvest->Move: 1
- Harvest->NoOp: 1
- NoOp->Harvest: 13
- NoOp->Move: 5
- NoOp->NoOp: 114
- NoOp->Return: 1
- NoOp->Move: 7
- NoOp->NoOp: 194
- NoOp->Produce: 5
- Produce->Move: 1
- Produce->Produce: 72
- Produce->Return: 1

## Runtime lifecycle table (transition evidence)
- NoOp decoded->submitted Harvest->Harvest: 1
- NoOp decoded->submitted Move->Move: 19
- NoOp decoded->submitted NoOp->NoOp: 837
- NoOp submitted->applier Harvest->accepted: 1
- NoOp submitted->applier Move->accepted: 19
- NoOp submitted->applier NoOp->not_submitted: 837
- NoOp applier->runtime/state_delta applier_not_accepted: 837
- NoOp applier->runtime/state_delta runtime_applied_no_state_delta: 19
- NoOp applier->runtime/state_delta runtime_applied_with_state_delta: 1
- Harvest decoded->submitted Harvest->Harvest: 22
- Harvest decoded->submitted Harvest->NoOp: 197
- Harvest decoded->submitted Move->Move: 6
- Harvest decoded->submitted NoOp->NoOp: 115
- Harvest decoded->submitted Return->Return: 1
- Harvest submitted->applier Harvest->accepted: 22
- Harvest submitted->applier Move->accepted: 6
- Harvest submitted->applier NoOp->not_accepted: 312
- Harvest submitted->applier Return->accepted: 1
- Harvest applier->runtime/state_delta applier_not_accepted: 312
- Harvest applier->runtime/state_delta runtime_applied_no_state_delta: 25
- Harvest applier->runtime/state_delta runtime_applied_with_state_delta: 4
- Produce decoded->submitted Move->Move: 8
- Produce decoded->submitted NoOp->NoOp: 194
- Produce decoded->submitted Produce->NoOp: 39
- Produce decoded->submitted Produce->Produce: 38
- Produce decoded->submitted Return->Return: 1
- Produce submitted->applier Move->accepted: 8
- Produce submitted->applier NoOp->not_accepted: 233
- Produce submitted->applier Produce->accepted: 36
- Produce submitted->applier Produce->not_accepted: 2
- Produce submitted->applier Return->accepted: 1
- Produce applier->runtime/state_delta applier_not_accepted: 235
- Produce applier->runtime/state_delta runtime_applied_no_state_delta: 42
- Produce applier->runtime/state_delta runtime_applied_with_state_delta: 3

## First failing boundary for Move
- raw_selected

## First failing boundary for Attack
- raw_selected

## First failing boundary for Harvest
- none

## First failing boundary for Return
- raw_selected

## First failing boundary for Produce
- none

## Clean lifecycle examples for each action type if present
- NoOp: none
- Move: none
- Harvest: mode=scripted_deterministic_commands, step=36, cell=25 (B2)
- Harvest: mode=scripted_deterministic_commands, step=39, cell=25 (B2)
- Harvest: mode=scripted_deterministic_commands, step=75, cell=25 (B2)
- Return: none
- Produce: none
- Attack: none

## Scripted deterministic capture
- scripted_attempted: 80
- scripted_accepted: 65
- scripted_move_attempted: 38
- scripted_move_accepted: 33
- scripted_move_caused_position_delta: True
- scripted_move_delta_evidence: step=71, from=(2,1), to=(3,1), path=scripted_canonical_actionapplier
- scripted_direct_matchmanager: bypasses ActionDecoder and ActionApplier by design.
- scripted_canonical_actionapplier: submits AgentAction through ActionApplier path.

## Success gate
- run_manifest_exists: True
- full_tri_mode: True
- scripted_completed: True
- independent_counters: True
- move_boundary_from_raw_action_counters: True

## Artifact paths
- Trace JSONL: python/week6_student/reports/stage10d22b_global_action_lifecycle_trace.jsonl
- Summary JSON: python/week6_student/reports/stage10d22b_global_action_lifecycle_summary.json
- Markdown report: python/week6_student/reports/STAGE10D22B_GLOBAL_ACTION_LIFECYCLE_REPORT.md
- Stage10D22B run manifest: python/week6_student/reports/stage10d22b_run_manifest.json
