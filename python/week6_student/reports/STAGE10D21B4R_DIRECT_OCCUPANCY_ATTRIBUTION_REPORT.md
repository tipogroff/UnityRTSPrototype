# STAGE10D21B4R Direct Occupancy Attribution Validation

- Generated (UTC): 2026-05-03T23:41:56.177811+00:00
- Commands analyzed: 4
- Stage10D.21B4R gate: PASS
- Stage10D.21B5 decision: GO_FOR_STAGE10D21B5_DYNAMIC_OCCUPANCY_MASK_ENRICHMENT
- Stage10D.21C gate: NO-GO

## Occupancy Outcomes
- A_RUNTIME_OCCUPIED_WITH_DIRECT_OCCUPANT: 4

## Required Answers
- Q1 source/target by command: [{"command_id": "cmd:106", "source_cell": 42, "target_cell": 43}, {"command_id": "cmd:120", "source_cell": 41, "target_cell": 42}, {"command_id": "cmd:142", "source_cell": 38, "target_cell": 39}, {"command_id": "cmd:78", "source_cell": 45, "target_cell": 46}]
- Q2 roundtrip pass: {"cmd:106": true, "cmd:120": true, "cmd:142": true, "cmd:78": true}
- Q3 reconstructed target matches: {"cmd:106": true, "cmd:120": true, "cmd:142": true, "cmd:78": true}
- Q4 direct runtime target_occupied: {"cmd:106": true, "cmd:120": true, "cmd:142": true, "cmd:78": true}
- Q5 direct runtime occupant tuples: {"cmd:106": {"occupant_id": "Player2_Light_(23, 21)#-121806", "occupant_owner": "Player2", "occupant_type": "Light", "occupant_cell": 43}, "cmd:120": {"occupant_id": "Player2_Light_(22, 21)#-121842", "occupant_owner": "Player2", "occupant_type": "Light", "occupant_cell": 42}, "cmd:142": {"occupant_id": "Player2_Light_(22, 21)#-121842", "occupant_owner": "Player2", "occupant_type": "Light", "occupant_cell": 39}, "cmd:78": {"occupant_id": "Player2_Light_(23, 21)#-121806", "occupant_owner": "Player2", "occupant_type": "Light", "occupant_cell": 46}}
- Q6 direct runtime vs snapshot/post-hoc: {"cmd:106": true, "cmd:120": true, "cmd:142": true, "cmd:78": true}
- Q7 Player2 claims: {"directly_proven": ["cmd:106", "cmd:120", "cmd:142", "cmd:78"], "directly_disproven_or_unproven": []}
- Q8 B4 target_occupied still valid: True
- Q9 occupant attribution validity: valid
- Q10 Stage10D.21B5 gate: GO_FOR_STAGE10D21B5_DYNAMIC_OCCUPANCY_MASK_ENRICHMENT
- Q11 Stage10D.21C gate: NO-GO

## Artifacts
- Trace: python/week6_student/reports/stage10d21b4r_direct_occupancy_attribution_trace.jsonl
- JSON: python/week6_student/reports/stage10d21b4r_direct_occupancy_attribution_report.json
- Markdown: python/week6_student/reports/STAGE10D21B4R_DIRECT_OCCUPANCY_ATTRIBUTION_REPORT.md
