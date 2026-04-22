# WEEK6 Day 2 Student Input Source (Pinned)

Date pinned (UTC): 2026-04-22
Purpose: Prevent lineage confusion for student BC training inputs.

## Current canonical BC-ready source for Day 2

Run directory:
python/week5_teacher/teacher_exports_bc/day6_bc_ready_teacher_adapted_day5_hardened_v2_teacher_candidate_corrective_sl2000_ep8_cpu_20260422T085809Z

Required files present:
- bc_train.npz
- bc_validation.npz
- bc_manifest.json
- dry_run_bc_loader_report.json

Dry run status:
- pass

Schema expectations:
- schema_version: day6.bc_ready.v1
- input_tensor per sample: [24, 24, 27], float32
- target_action_branches per sample: [576, 7], int16
- branch_sizes: [6, 4, 4, 4, 4, 4, 9]
- optional_mask: absent by design (optional), not treated as runtime truth

## Scope guardrails

- Day 2 uses BC-ready artifacts only.
- Day 2 must not read raw/adapted artifacts as student training input.
- No schema edits are allowed for this lineage pin.
- Day 1 rerun/revalidation pass is a compatibility checkpoint, not BC success proof.

## Change policy

Do not change this source path silently.
Switch to another lineage only via an explicit baseline-switch note and rerun of:
1. inspect_bc_dataset.py
2. dry_run_bc_loader.py report check
3. Week 5 handoff completeness check
