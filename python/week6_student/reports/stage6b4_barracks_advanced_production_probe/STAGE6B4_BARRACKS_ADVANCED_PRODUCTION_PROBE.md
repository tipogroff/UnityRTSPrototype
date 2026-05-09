# Stage6B4 Barracks Advanced Production Probe

- generated_at_utc: 2026-05-08T19:31:36.9121098Z
- scene: Week6_StudentStaticHarvestLayout
- checkpoint_relative_path: python/week6_student/checkpoints/Stage6B3_SemanticObservationFix/legacy032_v2_bc_source_valid_semantic_obs_fix_final.pt
- json_report: C:\Projects\UnityRTSPrototype\UnityRTSPrototype\python\week6_student\reports\stage6b4_barracks_advanced_production_probe\stage6b4_barracks_advanced_production_probe.json
- loss_layer: no_forced_path_failure_detected_live_student_inconclusive_or_policy_selection

## Forced Runtime Path
| unit | accepted | queue_started | completed | spawned | reason |
| --- | --- | --- | --- | --- | --- |
| Light | True | True | True | True | none |
| Heavy | True | True | True | True | none |
| Ranged | True | True | True | True | none |

## Mask Probe
- Produce enabled: True
- produce_dir enabled: 0,1,2,3
- produce_unit_type enabled: 4=Light,5=Heavy,6=Ranged
- resources: 5000
- queue_busy: False
- free adjacent cardinal / 8-neighbor: 4 / 8
- UnitDefinition reasons: 4=Light:ok cost=3 time=6 affordable=True | 5=Heavy:ok cost=2 time=10 affordable=True | 6=Ranged:ok cost=2 time=10 affordable=True

## Forced ML Pipeline Path
| unit | accepted | queue_started | completed | spawned | reason |
| --- | --- | --- | --- | --- | --- |
| Light | True | True | True | True | none |
| Heavy | True | True | True | True | none |
| Ranged | True | True | True | True | none |

## Live Student
- captured Barracks steps: 3
- command events: 8
- production events: 8

## GO/NO-GO
- A) Unity Barracks production broken: NO-GO - Runtime-only MatchCommand path completed and spawned Light/Heavy/Ranged.
- B) mask blocks advanced production: NO-GO - Mask enables Produce and produce_unit_type indices 4/5/6 for Barracks.
- C) decoder/applier mapping broken: NO-GO - Fake actionFlat Produce with indices 4/5/6 decodes through mask-aware decoder, ActionApplier, MatchManager, and spawns units.
- D) student never selects advanced production: INCONCLUSIVE - Live rows contain raw advanced Produce intent.
- E) student selects it but runtime rejects: INCONCLUSIVE - Postmask advanced Produce was observed without rejection evidence.
- F) production starts but spawn fails: NO-GO - Forced production starts and spawned units on both runtime-only and ML-pipeline paths.
