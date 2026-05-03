# STAGE10D20R_MASK_MOVE_ALIGNMENT_REPORT

## Summary
- masked Move events traced: 4

## Mismatch category counts
- A_report_uses_raw_or_unmasked_branch_values: 0
- B_selector_not_applying_branch_move_dir_mask: 4
- C_direction_or_coordinate_mapping_mismatch: 0
- D_stale_occupancy_snapshot: 1
- E_actiondecoder_or_applier_value_mismatch: 4
- F_accepted_move_not_physically_applied: 4
- G_movement_tracking_or_identity_issue: 0

## First mismatch point counts
- selector_stage:move_dir_selected_not_legal_under_move_dir_mask: 4

## Per-event alignment table
|idx|step|unit|src_flat|raw_action|raw_dir|masked_action|masked_dir|dir_legal|target_free_before|submitted|accepted|rejected|moved|first_mismatch|
|---:|---:|---|---:|---|---|---|---|---:|---:|---:|---:|---:|---:|---|
|1|30|Worker_003|45|Move|E|Move|E|False|False|True|True|True|False|selector_stage:move_dir_selected_not_legal_under_move_dir_mask|
|2|37|Worker_005|42|Move|E|Move|E|False|False|True|True|True|False|selector_stage:move_dir_selected_not_legal_under_move_dir_mask|
|3|41|Worker_006|41|Move|E|Move|E|False|False|True|True|True|False|selector_stage:move_dir_selected_not_legal_under_move_dir_mask|
|4|48|Worker_008|38|Move|E|Move|E|False|False|True|True|True|False|selector_stage:move_dir_selected_not_legal_under_move_dir_mask|

## GO/NO-GO recommendations
- mask logic fix: GO (Masked Move events selected move_dir E while legal move_dir mask disabled E on every traced event.)
- report builder fix: GO (Stage10D.20 infers masked action through command_built side effects; Stage10D.20R requires explicit mask-stage fields.)
- ActionDecoder audit: GO (ActionApplier flags show accepted and rejected both true on traced events, requiring value/contract audit.)
- ActionApplier/MatchManager movement application audit: GO (All traced accepted Move commands show no displacement by unit-id tracking.)

## Acceptance criteria mapping
- A) report using raw/unmasked branch values: traced via report-inferred masked action contract and category counters.
- B) selector not applying branch-level move_dir mask: traced by selected move_dir legality against [N,E,S,W] mask.
- C) direction/coordinate mapping mismatch: traced by target chain alignment fields.
- D) stale occupancy snapshot: traced by target occupancy before vs after AdvanceStep.
- E) ActionDecoder receiving different values than report records: traced by built/submitted/accepted/rejected consistency checks.
- F) accepted Move not physically applied: traced by accepted-without-displacement counters.
- G) movement tracking/unit identity issue: traced by unit-id stability and position-based movement checks.
