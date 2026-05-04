# STAGE10D21B4R-S Occupant Coordinate Consistency Audit

- Generated (UTC): 2026-05-04T00:00:13.195672+00:00
- Commands analyzed: 4
- Audit gate: PASS
- Stage10D.21B5 gate: GO_FOR_STAGE10D21B5_DYNAMIC_OCCUPANCY_MASK_ENRICHMENT
- Stage10D.21C gate: NO-GO

## Consistency Buckets
- consistent_direct_occupant: 0
- instrumentation_wrote_target_as_occupant_cell: 0
- stale_occupancy_map_reference: 0
- occupant_logical_position_mismatch: 0
- coordinate_mapping_mismatch: 0
- visual_name_coordinate_mismatch: 4
- not_exposed: 0
- unknown_inconsistent: 0

## Final Answers
- Q1 target cell queried by command: {"cmd:106": 43, "cmd:120": 42, "cmd:142": 39, "cmd:78": 46}
- Q2 TryGetOccupant result object: {"cmd:106": {"occupant_name": "Player2_Light_(23, 21)#-121806", "occupant_instance_id": -121806, "occupant_owner": "Player2", "occupant_type": "Light"}, "cmd:120": {"occupant_name": "Player2_Light_(22, 21)#-121842", "occupant_instance_id": -121842, "occupant_owner": "Player2", "occupant_type": "Light"}, "cmd:142": {"occupant_name": "Player2_Light_(22, 21)#-121842", "occupant_instance_id": -121842, "occupant_owner": "Player2", "occupant_type": "Light"}, "cmd:78": {"occupant_name": "Player2_Light_(23, 21)#-121806", "occupant_instance_id": -121806, "occupant_owner": "Player2", "occupant_type": "Light"}}
- Q3 occupant logical coordinates/flat: {"cmd:106": {"logical_x": 19, "logical_y": 1, "logical_cell": 43}, "cmd:120": {"logical_x": 18, "logical_y": 1, "logical_cell": 42}, "cmd:142": {"logical_x": 15, "logical_y": 1, "logical_cell": 39}, "cmd:78": {"logical_x": 22, "logical_y": 1, "logical_cell": 46}}
- Q4 logical flat equals target: {"cmd:106": true, "cmd:120": true, "cmd:142": true, "cmd:78": true}
- Q5 logical flat equals previous occupant_cell_at_target: {"cmd:106": true, "cmd:120": true, "cmd:142": true, "cmd:78": true}
- Q6 instrumentation wrote target as occupant cell: False
- Q7 GridManager occupancy consistency: True
- Q8 Player2 actually occupies 39/42/43/46: True
- Q9 Stage10D.21B5 status: GO_FOR_STAGE10D21B5_DYNAMIC_OCCUPANCY_MASK_ENRICHMENT
- Q10 Stage10D.21C status: NO-GO

## Adjudication
- target_occupied is real and consistent: False
- target_occupied is real but attribution exported incorrectly: True
- GridManager occupancy is stale/wrong: False
- evidence remains inconclusive: False

## Artifacts
- Trace: python/week6_student/reports/stage10d21b4r_s_occupant_coordinate_consistency_trace.jsonl
- JSON report: python/week6_student/reports/stage10d21b4r_s_occupant_coordinate_consistency_report.json
- Markdown report: python/week6_student/reports/STAGE10D21B4R_S_OCCUPANT_COORDINATE_CONSISTENCY_REPORT.md
