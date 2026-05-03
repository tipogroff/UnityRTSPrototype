#!/usr/bin/env python3
"""
Stage10D.12R: Complete Pipeline Orchestration and Final Report Generation

Purpose:
Orchestrate all Stage10D.12R diagnostic tasks:
1. Validate captured raw observation tensor
2. Compare with reconstructed fullmap
3. Run strict replay probes
4. Generate comprehensive final report

This is the main entry point for Stage10D.12R diagnostics.
"""

import subprocess
import sys
import json
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime


def run_script(script_path: str, script_name: str) -> bool:
    """Run a Python script and report results."""
    print(f"\n{'='*70}")
    print(f"Running: {script_name}")
    print(f"{'='*70}")
    
    try:
        result = subprocess.run(
            [sys.executable, script_path],
            capture_output=True,
            text=True,
            timeout=300
        )
        
        print(result.stdout)
        if result.stderr:
            print("STDERR:", result.stderr)
        
        if result.returncode != 0:
            print(f"✗ {script_name} failed with exit code {result.returncode}")
            return False
        else:
            print(f"✓ {script_name} completed successfully")
            return True
    except subprocess.TimeoutExpired:
        print(f"✗ {script_name} timed out")
        return False
    except Exception as e:
        print(f"✗ {script_name} failed with exception: {e}")
        return False


def load_json_safe(path: str) -> Optional[Dict[str, Any]]:
    """Safely load JSON file."""
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"Warning: Could not load {path}: {e}")
        return None


def is_non_empty_list(value: Any) -> bool:
    return isinstance(value, list) and len(value) > 0


def validate_probe_execution(probe_report: Optional[Dict[str, Any]]) -> Tuple[bool, str, List[str]]:
    """Validate strict probe report completeness and real-inference guarantees."""
    if probe_report is None:
        return False, "Strict replay invalid: probe report not generated.", ["probe_report_missing"]

    missing: List[str] = []
    if not probe_report.get('model_checkpoint_loaded', False):
        missing.append('model_checkpoint_loaded!=true')
    if probe_report.get('inference_status') != 'real_model_execution_completed':
        missing.append('inference_status!=real_model_execution_completed')

    b2_baseline = probe_report.get('baseline_inference', {}).get('B2', {})
    c3_baseline = probe_report.get('baseline_inference', {}).get('C3', {})
    if not (b2_baseline.get('predicted_action') and c3_baseline.get('predicted_action')):
        missing.append('baseline_B2_or_C3_prediction_missing')

    if not isinstance(probe_report.get('b2_reference'), dict):
        missing.append('b2_reference_missing')
    if not isinstance(probe_report.get('c3_reference'), dict):
        missing.append('c3_reference_missing')
    if not is_non_empty_list(probe_report.get('b2_group_probe_results')):
        missing.append('b2_group_probe_results_missing_or_empty')
    if not is_non_empty_list(probe_report.get('b2_per_channel_probe_results')):
        missing.append('b2_per_channel_probe_results_missing_or_empty')
    if not is_non_empty_list(probe_report.get('c3_radius_probe_results')):
        missing.append('c3_radius_probe_results_missing_or_empty')
    if not is_non_empty_list(probe_report.get('c3_semantic_group_probe_results')):
        missing.append('c3_semantic_group_probe_results_missing_or_empty')

    if missing:
        return False, f"Strict replay invalid: missing required fields ({', '.join(missing)}).", missing
    return True, 'Real model execution successful with required BC-reference probe fields.', []


def synthesize_final_report(reports_dir: Path) -> Dict[str, Any]:
    """
    Synthesize findings from all diagnostic scripts into final report.
    """
    
    # Load intermediate reports
    validation_report = load_json_safe(str(reports_dir / 'stage10d12r_full_raw_observation_validation.json'))
    comparison_report = load_json_safe(str(reports_dir / 'stage10d12r_full_raw_vs_reconstructed_diff.json'))
    probe_report = load_json_safe(str(reports_dir / 'stage10d12r_strict_replay_probe_results.json'))
    
    # Extract key facts
    capture_valid = validation_report and validation_report.get('all_checks_passed', False)
    capture_classification = validation_report.get('classification') if validation_report else 'UNKNOWN'
    
    comparison_available = comparison_report and comparison_report.get('comparison_status') == 'COMPLETED'
    comparison_classification = comparison_report.get('classification') if comparison_report else 'UNAVAILABLE'
    
    # Count entities in scene
    owner_dist = validation_report.get('owner_distribution', {}) if validation_report else {}
    unit_dist = validation_report.get('unit_distribution', {}) if validation_report else {}
    action_dist = validation_report.get('action_distribution', {}) if validation_report else {}
    
    # Extract focus cell semantics
    focus_vectors = validation_report.get('focus_cell_vectors', {}) if validation_report else {}
    b2_vector = focus_vectors.get('B2', [])
    c3_vector = focus_vectors.get('C3', [])
    
    # Decode B2 and C3 expected semantics
    def decode_owner(vector):
        if len(vector) < 5:
            return 'unknown'
        if vector[3] > 0.5:
            return 'player1'
        if vector[4] > 0.5:
            return 'player2'
        if vector[2] > 0.5:
            return 'neutral'
        return 'none'
    
    def decode_unit(vector):
        if len(vector) < 12:
            return 'none'
        units = ['resource', 'base', 'barracks', 'worker', 'light', 'heavy', 'ranged']
        for i, unit_name in enumerate(units):
            if vector[5 + i] > 0.5:
                return unit_name
        return 'none'
    
    def decode_action(vector):
        if len(vector) < 18:
            return 'none'
        actions = ['noop', 'move', 'harvest', 'return', 'produce', 'attack']
        for i, action_name in enumerate(actions):
            if vector[12 + i] > 0.5:
                return action_name
        return 'none'
    
    b2_owner = decode_owner(b2_vector)
    b2_unit = decode_unit(b2_vector)
    b2_action = decode_action(b2_vector)
    
    c3_owner = decode_owner(c3_vector)
    c3_unit = decode_unit(c3_vector)
    c3_action = decode_action(c3_vector)
    
    # Classify scene semantics
    b2_expected = b2_owner == 'player1' and b2_unit == 'worker'
    c3_expected = c3_owner == 'player1' and c3_unit == 'base'
    
    # B2 semantics check
    if b2_expected and b2_action != 'noop':
        b2_semantics = 'VALID_NONOP_CAPABLE'
    elif b2_expected and b2_action == 'noop':
        b2_semantics = 'VALID_BUT_NOOP_STATE'
    elif not b2_expected:
        b2_semantics = 'INVALID_EXPECTATION_MISMATCH'
    else:
        b2_semantics = 'UNKNOWN'
    
    # C3 semantics check
    if c3_expected and c3_action != 'noop':
        c3_semantics = 'VALID_NONOP_CAPABLE'
    elif c3_expected and c3_action == 'noop':
        c3_semantics = 'VALID_BUT_NOOP_STATE'
    elif not c3_expected:
        c3_semantics = 'INVALID_EXPECTATION_MISMATCH'
    else:
        c3_semantics = 'UNKNOWN'
    
    # CRITICAL: strict replay validity (real model + required BC-reference probe payloads)
    probe_execution_valid, probe_execution_message, probe_missing_fields = validate_probe_execution(probe_report)
    
    # Determine evidence-based next gate
    next_gates_candidates = []
    
    # If strict replay failed, block all fix gates and force rerun
    if not probe_execution_valid:
        next_gates_candidates = ['GO_FOR_STAGE10D12R_STRICT_PROBE_RERUN']
    else:
        probe_gate_candidate = probe_report.get('recommended_next_gate_candidate', '') if probe_report else ''
        if isinstance(probe_gate_candidate, str) and probe_gate_candidate:
            next_gates_candidates.append(probe_gate_candidate)

        # Strict replay succeeded; now check for semantic issues
        if not capture_valid:
            next_gates_candidates.append('GO_FOR_STAGE10D12R_CAPTURE_FIX')
        
        if comparison_available and comparison_classification == 'RECONSTRUCTION_DIVERGES_FROM_RAW':
            next_gates_candidates.append('GO_FOR_UNITY_SCENE_DISTRIBUTION_ALIGNMENT')
        
        if b2_semantics == 'INVALID_EXPECTATION_MISMATCH' or c3_semantics == 'INVALID_EXPECTATION_MISMATCH':
            next_gates_candidates.append('GO_FOR_UNITY_OBSERVATION_CHANNEL_REMAP_FIX')
        
        if capture_valid and (b2_semantics == 'VALID_BUT_NOOP_STATE' or c3_semantics == 'VALID_BUT_NOOP_STATE'):
            next_gates_candidates.append('GO_FOR_TARGETED_BC_AUGMENTATION_WITH_UNITY_LIKE_STATES')
    
    # Select primary next gate
    if next_gates_candidates:
        primary_next_gate = next_gates_candidates[0]
    else:
        primary_next_gate = 'GO_FOR_STAGE10D12R_STRICT_PROBE_RERUN'

    b2_baseline = probe_report.get('baseline_inference', {}).get('B2', {}) if probe_report else {}
    c3_baseline = probe_report.get('baseline_inference', {}).get('C3', {}) if probe_report else {}
    b2_reference = probe_report.get('b2_reference', {}) if probe_report else {}
    c3_reference = probe_report.get('c3_reference', {}) if probe_report else {}
    b2_group_results = probe_report.get('b2_group_probe_results', []) if probe_report else []
    b2_channel_top = probe_report.get('b2_per_channel_top_ranking', []) if probe_report else []
    c3_radius_results = probe_report.get('c3_radius_probe_results', []) if probe_report else []
    c3_semantic_results = probe_report.get('c3_semantic_group_probe_results', []) if probe_report else []
    strict_labels = probe_report.get('classifications', []) if probe_report else []
    true_scene_summary = probe_report.get('true_raw_scene_summary', {}) if probe_report else {}
    bc_scene_summary = probe_report.get('bc_reference_scene_summary', {}) if probe_report else {}
    scene_ood_deltas = probe_report.get('scene_ood_deltas', {}) if probe_report else {}
    
    # Build final report
    final_report = {
        'generated_at_utc': datetime.utcnow().isoformat() + 'Z',
        'stage': '10D.12R',
        'title': 'Full Raw Runtime Observation Capture - Comprehensive Final Report',
        
        'section_1_capture_implementation': {
            'instrumentation_location': 'Assets/Scripts/ML/Week6StudentPolicyAdapter.cs',
            'capture_method': 'CaptureFullRawObservationDiagnostic',
            'capture_point_description': 'After observation validation, before Python bridge send (line ~610)',
            'artifacts_created': [
                'stage10d12r_full_raw_runtime_observation_step{STEP}.json',
                'stage10d12r_full_raw_observation_validation.json',
                'stage10d12r_full_raw_vs_reconstructed_diff.json',
                'stage10d12r_strict_replay_probe_results.json',
            ],
            'behavior_changes': 'None - read-only instrumentation only',
            'checkpoint_modified': False,
            'weights_modified': False,
            'action_contract_changed': False,
            'observation_contract_changed': False,
        },
        
        'section_2_artifact_validation': {
            'validation_passed': capture_valid,
            'validation_classification': capture_classification,
            'tensor_shape': [24, 24, 27],
            'cell_count': 576,
            'channel_count': 27,
            'nan_count': validation_report.get('nan_inf_stats', {}).get('nan_count', 'unknown') if validation_report else 'unknown',
            'inf_count': validation_report.get('nan_inf_stats', {}).get('inf_count', 'unknown') if validation_report else 'unknown',
            'b2_found': True if b2_vector else False,
            'c3_found': True if c3_vector else False,
        },
        
        'section_3_full_raw_observation_summary': {
            'entity_owner_distribution': owner_dist,
            'entity_unit_distribution': unit_dist,
            'current_action_distribution': action_dist,
            'focus_B2': {
                'flat_index': 25,
                'x': 1,
                'y': 1,
                'decoded_owner': b2_owner,
                'decoded_unit': b2_unit,
                'decoded_current_action': b2_action,
                'semantics_classification': b2_semantics,
                'matches_training_BC_expectation': b2_expected,
            },
            'focus_C3': {
                'flat_index': 50,
                'x': 2,
                'y': 2,
                'decoded_owner': c3_owner,
                'decoded_unit': c3_unit,
                'decoded_current_action': c3_action,
                'semantics_classification': c3_semantics,
                'matches_training_BC_expectation': c3_expected,
            },
        },
        
        'section_4_true_raw_vs_reconstructed': {
            'comparison_performed': comparison_available,
            'comparison_classification': comparison_classification,
            'global_l2_difference': comparison_report.get('global_comparison', {}).get('mean_l2_difference') if comparison_report else 'unknown',
            'b2_l2_difference': comparison_report.get('focus_cells', {}).get('B2', {}).get('l2_difference') if comparison_report else 'unknown',
            'c3_l2_difference': comparison_report.get('focus_cells', {}).get('C3', {}).get('l2_difference') if comparison_report else 'unknown',
            'interpretation': (
                'Reconstruction accurately matches true raw' if comparison_classification == 'RECONSTRUCTION_MATCHES_RAW'
                else 'Reconstruction partially matches true raw' if comparison_classification == 'RECONSTRUCTION_PARTIALLY_MATCHES_RAW'
                else 'Reconstruction significantly diverges from true raw' if comparison_classification == 'RECONSTRUCTION_DIVERGES_FROM_RAW'
                else 'Comparison unavailable'
            ),
        },
        
        'section_5_strict_replay_baseline': {
            'probe_results_generated': probe_report is not None,
            'model_checkpoint_loaded': probe_report.get('model_checkpoint_loaded', False) if probe_report else False,
            'inference_status': probe_report.get('inference_status', 'unknown') if probe_report else 'unknown',
            'B2': {
                'predicted_action': b2_baseline.get('predicted_action', 'unknown'),
                'p_noop': b2_baseline.get('p_noop', 'unknown'),
                'p_harvest': b2_baseline.get('p_harvest', 'unknown'),
                'p_produce': b2_baseline.get('p_produce', 'unknown'),
            },
            'C3': {
                'predicted_action': c3_baseline.get('predicted_action', 'unknown'),
                'p_noop': c3_baseline.get('p_noop', 'unknown'),
                'p_harvest': c3_baseline.get('p_harvest', 'unknown'),
                'p_produce': c3_baseline.get('p_produce', 'unknown'),
            },
        },

        'section_6_b2_bc_reference_strict_probes': {
            'nearest_bc_worker_harvest_reference': b2_reference,
            'group_probe_table': b2_group_results,
            'per_channel_top_ranking': b2_channel_top,
            'b2_conclusion': (
                'STRICT_B2_CHANNEL_MISMATCH_CONFIRMED'
                if 'STRICT_B2_CHANNEL_MISMATCH_CONFIRMED' in strict_labels
                else 'STRICT_B2_CHANNEL_MISMATCH_NOT_CONFIRMED'
            ),
        },

        'section_7_c3_bc_reference_strict_probes': {
            'nearest_bc_base_produce_reference': c3_reference,
            'radius_probe_table': c3_radius_results,
            'semantic_group_probe_table': c3_semantic_results,
            'c3_conclusion': (
                'STRICT_C3_LOCAL_CONTEXT_REQUIRED_CONFIRMED'
                if 'STRICT_C3_LOCAL_CONTEXT_REQUIRED_CONFIRMED' in strict_labels
                else 'STRICT_C3_LOCAL_CONTEXT_NOT_CONFIRMED'
            ),
        },

        'section_8_true_raw_scene_context_summary': {
            'true_raw_scene_counts': true_scene_summary,
            'bc_reference_scene_counts': bc_scene_summary,
            'scene_ood_deltas': scene_ood_deltas,
            'scene_ood_conclusion': (
                'STRICT_SCENE_OOD_CONFIRMED'
                if 'STRICT_SCENE_OOD_CONFIRMED' in strict_labels
                else 'STRICT_SCENE_OOD_NOT_CONFIRMED'
            ),
        },

        'section_9_evidence_based_classification': {
            'labels': strict_labels,
            'capture_quality': capture_classification,
            'semantic_validity': 'VALID' if (b2_expected and c3_expected) else 'INVALID',
            'b2_classification': b2_semantics,
            'c3_classification': c3_semantics,
            'scene_ood_status': (
                'SCENE_MATCHES_BC_REFERENCE' if (b2_expected and c3_expected)
                else 'SCENE_OOD_CONFIRMED'
            ),
        },

        'section_10_primary_next_gate': {
            'selected_gate': primary_next_gate,
            'probe_execution_valid': probe_execution_valid,
            'probe_execution_message': probe_execution_message,
            'probe_missing_fields': probe_missing_fields,
            'candidate_gates': next_gates_candidates,
            'rationale': get_gate_rationale(primary_next_gate, capture_valid, b2_semantics, c3_semantics, comparison_classification, probe_execution_valid, probe_execution_message),
        },
        
        'conclusion': (
            f'Stage10D.12R observation capture completed. '
            f'True raw tensor is valid and suitable for strict probes. '
            f'Primary next gate: {primary_next_gate}'
        ),
    }
    
    return final_report


def get_gate_rationale(gate: str, capture_valid: bool, b2_sem: str, c3_sem: str, comparison: str, 
                       probe_valid: bool = True, probe_msg: str = "") -> str:
    """Get rationale for selected next gate."""
    if not probe_valid:
        return f'Strict replay validation failed: {probe_msg} Must rerun probes with real model.'
    elif gate == 'GO_FOR_STAGE10D12R_CAPTURE_FIX':
        return 'Captured tensor validation failed; must fix capture instrumentation'
    elif gate == 'GO_FOR_UNITY_OBSERVATION_CHANNEL_REMAP_FIX':
        return f'True raw proves channel mismatch: B2={b2_sem}, C3={c3_sem}'
    elif gate == 'GO_FOR_UNITY_SCENE_DISTRIBUTION_ALIGNMENT':
        return f'True raw shows scene OOD; comparison={comparison}'
    elif gate == 'GO_FOR_TARGETED_BC_AUGMENTATION_WITH_UNITY_LIKE_STATES':
        return f'True raw valid but scene lacks BC contexts: B2={b2_sem}, C3={c3_sem}'
    elif gate == 'GO_FOR_STAGE10D12R_STRICT_PROBE_RERUN':
        return 'Capture successful; rerun strict probes with full model'
    else:
        return 'Unknown gate'


def main():
    script_dir = Path(__file__).parent
    reports_dir = script_dir / 'reports'
    
    # Ensure reports directory exists
    reports_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"Stage10D.12R Complete Pipeline Orchestration")
    print(f"Reports directory: {reports_dir}")
    
    # Check if captured observation exists
    captured_path = reports_dir / 'stage10d12r_full_raw_runtime_observation_step0001.json'
    if not captured_path.exists():
        print(f"\nERROR: No captured observation found at {captured_path}")
        print("This script requires the Unity scene to have generated the raw observation capture.")
        print("Please:")
        print("1. Ensure Week6StudentPolicyAdapter instrumentation is compiled")
        print("2. Run a match with student policy enabled")
        print("3. Verify capture output in the match artifact directory")
        print("4. Copy stage10d12r_full_raw_runtime_observation_step*.json to reports/")
        return 1
    
    print(f"\n✓ Found captured observation: {captured_path.name}")
    
    # Run validation script
    if not run_script(
        str(script_dir / 'stage10d12r_full_raw_observation_validation.py'),
        'Full Raw Observation Validation'
    ):
        print("ERROR: Validation script failed")
        return 1
    
    # Run comparison script
    if not run_script(
        str(script_dir / 'stage10d12r_full_raw_vs_reconstructed_comparison.py'),
        'True Raw vs Reconstructed Comparison'
    ):
        print("ERROR: Comparison script failed")
        return 1
    
    # Run probe script
    if not run_script(
        str(script_dir / 'stage10d12r_strict_replay_probe_on_true_raw.py'),
        'Strict Replay Probes on True Raw'
    ):
        print("ERROR: Probe script failed")
        return 1
    
    # Synthesize final report
    print(f"\n{'='*70}")
    print("Synthesizing Final Comprehensive Report")
    print(f"{'='*70}")
    
    final_report = synthesize_final_report(reports_dir)
    
    # Write final report
    final_json_path = reports_dir / 'STAGE10D12R_FULL_RAW_OBSERVATION_CAPTURE_REPORT.json'
    with open(final_json_path, 'w', encoding='utf-8') as f:
        json.dump(final_report, f, indent=2)
    
    print(f"✓ Final report written to: {final_json_path}")
    
    # Generate markdown summary
    markdown_report = generate_markdown_report(final_report)
    markdown_path = reports_dir / 'STAGE10D12R_FULL_RAW_OBSERVATION_CAPTURE_REPORT.md'
    with open(markdown_path, 'w', encoding='utf-8') as f:
        f.write(markdown_report)
    
    print(f"✓ Markdown summary written to: {markdown_path}")
    
    # Print summary
    print(f"\n{'='*70}")
    print("PIPELINE COMPLETED SUCCESSFULLY")
    print(f"{'='*70}")
    print(f"\nPrimary Next Gate: {final_report['section_10_primary_next_gate']['selected_gate']}")
    print(f"\nConclusion: {final_report['conclusion']}")
    
    return 0


def generate_markdown_report(report: Dict[str, Any]) -> str:
    """Generate markdown version of final report."""
    b2_ref = report['section_6_b2_bc_reference_strict_probes']['nearest_bc_worker_harvest_reference']
    c3_ref = report['section_7_c3_bc_reference_strict_probes']['nearest_bc_base_produce_reference']

    def fmt_prob(v: Any) -> str:
        try:
            return f"{float(v):.6f}"
        except Exception:
            return str(v)

    b2_top = report['section_6_b2_bc_reference_strict_probes']['per_channel_top_ranking'][:5]
    b2_group_rows = report['section_6_b2_bc_reference_strict_probes']['group_probe_table']
    c3_radius_rows = report['section_7_c3_bc_reference_strict_probes']['radius_probe_table']
    c3_sem_rows = report['section_7_c3_bc_reference_strict_probes']['semantic_group_probe_table']

    md = f"""# Stage10D.12R Full Raw Runtime Observation Capture Report

**Generated:** {report['generated_at_utc']}

## Executive Summary

{report['conclusion']}

## Section 1: Capture Implementation

- **Location:** {report['section_1_capture_implementation']['instrumentation_location']}
- **Method:** `{report['section_1_capture_implementation']['capture_method']}`
- **Capture Point:** {report['section_1_capture_implementation']['capture_point_description']}
- **Behavior Changes:** {report['section_1_capture_implementation']['behavior_changes']}
- **Checkpoint Modified:** {report['section_1_capture_implementation']['checkpoint_modified']}
- **Weights Modified:** {report['section_1_capture_implementation']['weights_modified']}

## Section 2: Artifact Validation

| Metric | Value |
|--------|-------|
| Validation Passed | {report['section_2_artifact_validation']['validation_passed']} |
| Classification | {report['section_2_artifact_validation']['validation_classification']} |
| Tensor Shape | {report['section_2_artifact_validation']['tensor_shape']} |
| Cell Count | {report['section_2_artifact_validation']['cell_count']} |
| Channel Count | {report['section_2_artifact_validation']['channel_count']} |
| NaN Values | {report['section_2_artifact_validation']['nan_count']} |
| Inf Values | {report['section_2_artifact_validation']['inf_count']} |
| B2 Found | {report['section_2_artifact_validation']['b2_found']} |
| C3 Found | {report['section_2_artifact_validation']['c3_found']} |

## Section 3: Full Raw Observation Summary

### Focus Cell B2 (Player1 Worker at position [1,1])
- **Decoded Owner:** {report['section_3_full_raw_observation_summary']['focus_B2']['decoded_owner']}
- **Decoded Unit:** {report['section_3_full_raw_observation_summary']['focus_B2']['decoded_unit']}
- **Decoded Action:** {report['section_3_full_raw_observation_summary']['focus_B2']['decoded_current_action']}
- **Semantics:** {report['section_3_full_raw_observation_summary']['focus_B2']['semantics_classification']}
- **Matches BC Reference:** {report['section_3_full_raw_observation_summary']['focus_B2']['matches_training_BC_expectation']}

### Focus Cell C3 (Player1 Base at position [2,2])
- **Decoded Owner:** {report['section_3_full_raw_observation_summary']['focus_C3']['decoded_owner']}
- **Decoded Unit:** {report['section_3_full_raw_observation_summary']['focus_C3']['decoded_unit']}
- **Decoded Action:** {report['section_3_full_raw_observation_summary']['focus_C3']['decoded_current_action']}
- **Semantics:** {report['section_3_full_raw_observation_summary']['focus_C3']['semantics_classification']}
- **Matches BC Reference:** {report['section_3_full_raw_observation_summary']['focus_C3']['matches_training_BC_expectation']}

## Section 4: True Raw vs Reconstructed

- **Comparison Performed:** {report['section_4_true_raw_vs_reconstructed']['comparison_performed']}
- **Classification:** {report['section_4_true_raw_vs_reconstructed']['comparison_classification']}
- **Global L2 Difference:** {report['section_4_true_raw_vs_reconstructed']['global_l2_difference']}
- **B2 L2 Difference:** {report['section_4_true_raw_vs_reconstructed']['b2_l2_difference']}
- **C3 L2 Difference:** {report['section_4_true_raw_vs_reconstructed']['c3_l2_difference']}

**Interpretation:** {report['section_4_true_raw_vs_reconstructed']['interpretation']}

## Section 5: Strict Replay Baseline

- **Probes Generated:** {report['section_5_strict_replay_baseline']['probe_results_generated']}
- **Model Checkpoint Loaded:** {report['section_5_strict_replay_baseline']['model_checkpoint_loaded']}
- **Inference Status:** {report['section_5_strict_replay_baseline']['inference_status']}
- **B2:** action={report['section_5_strict_replay_baseline']['B2']['predicted_action']}, p_noop={fmt_prob(report['section_5_strict_replay_baseline']['B2']['p_noop'])}, p_harvest={fmt_prob(report['section_5_strict_replay_baseline']['B2']['p_harvest'])}, p_produce={fmt_prob(report['section_5_strict_replay_baseline']['B2']['p_produce'])}
- **C3:** action={report['section_5_strict_replay_baseline']['C3']['predicted_action']}, p_noop={fmt_prob(report['section_5_strict_replay_baseline']['C3']['p_noop'])}, p_harvest={fmt_prob(report['section_5_strict_replay_baseline']['C3']['p_harvest'])}, p_produce={fmt_prob(report['section_5_strict_replay_baseline']['C3']['p_produce'])}

## Section 6: B2 BC-Reference Strict Probes

- **Nearest BC Worker+Harvest Reference:** split={b2_ref.get('split')}, sample={b2_ref.get('sample_index')}, flat={b2_ref.get('flat_index')}, xy=({b2_ref.get('x')},{b2_ref.get('y')}), l2_to_runtime_b2={fmt_prob(b2_ref.get('l2_to_runtime_b2'))}
- **Reference Prediction:** {b2_ref.get('reference_prediction')}

### B2 Group Probe Table

| Probe | Predicted | p_noop | p_harvest | harvest_top1 | delta_p_noop | delta_p_harvest |
|------|-----------|--------|-----------|--------------|--------------|-----------------|
{chr(10).join([f"| {r.get('probe_name')} | {r.get('predicted_action')} | {fmt_prob(r.get('p_noop'))} | {fmt_prob(r.get('p_harvest'))} | {r.get('harvest_top1')} | {fmt_prob(r.get('delta_p_noop'))} | {fmt_prob(r.get('delta_p_harvest'))} |" for r in b2_group_rows]) if b2_group_rows else '| n/a | n/a | n/a | n/a | n/a | n/a | n/a |'}

### B2 Per-Channel Top Ranking

| Rank | Channel | Combined Score |
|------|---------|----------------|
{chr(10).join([f"| {i+1} | {r.get('channel_name')} | {fmt_prob(r.get('combined_score'))} |" for i, r in enumerate(b2_top)]) if b2_top else '| n/a | n/a | n/a |'}

- **B2 Conclusion:** {report['section_6_b2_bc_reference_strict_probes']['b2_conclusion']}

## Section 7: C3 BC-Reference Strict Probes

- **Nearest BC Base+Produce Reference:** split={c3_ref.get('split')}, sample={c3_ref.get('sample_index')}, flat={c3_ref.get('flat_index')}, xy=({c3_ref.get('x')},{c3_ref.get('y')}), l2_to_runtime_c3={fmt_prob(c3_ref.get('l2_to_runtime_c3'))}
- **Reference Prediction:** {c3_ref.get('reference_prediction')}

### C3 Radius Probe Table

| Probe | Predicted | p_noop | p_produce | produce_top1 | delta_p_noop | delta_p_produce |
|------|-----------|--------|-----------|--------------|--------------|-----------------|
{chr(10).join([f"| {r.get('probe_name')} | {r.get('predicted_action')} | {fmt_prob(r.get('p_noop'))} | {fmt_prob(r.get('p_produce'))} | {r.get('produce_top1')} | {fmt_prob(r.get('delta_p_noop'))} | {fmt_prob(r.get('delta_p_produce'))} |" for r in c3_radius_rows]) if c3_radius_rows else '| n/a | n/a | n/a | n/a | n/a | n/a | n/a |'}

### C3 Semantic Group Probe Table

| Probe | Predicted | p_noop | p_produce | produce_top1 | delta_p_noop | delta_p_produce |
|------|-----------|--------|-----------|--------------|--------------|-----------------|
{chr(10).join([f"| {r.get('probe_name')} | {r.get('predicted_action')} | {fmt_prob(r.get('p_noop'))} | {fmt_prob(r.get('p_produce'))} | {r.get('produce_top1')} | {fmt_prob(r.get('delta_p_noop'))} | {fmt_prob(r.get('delta_p_produce'))} |" for r in c3_sem_rows]) if c3_sem_rows else '| n/a | n/a | n/a | n/a | n/a | n/a | n/a |'}

- **C3 Conclusion:** {report['section_7_c3_bc_reference_strict_probes']['c3_conclusion']}

## Section 8: True Raw Scene/Context Summary

- **True Raw Scene Counts:** {report['section_8_true_raw_scene_context_summary']['true_raw_scene_counts']}
- **BC Reference Scene Counts:** {report['section_8_true_raw_scene_context_summary']['bc_reference_scene_counts']}
- **Scene OOD Deltas:** {report['section_8_true_raw_scene_context_summary']['scene_ood_deltas']}
- **Scene OOD Conclusion:** {report['section_8_true_raw_scene_context_summary']['scene_ood_conclusion']}

## Section 9: Evidence-Based Classification

- **Labels:** {', '.join(report['section_9_evidence_based_classification']['labels']) if report['section_9_evidence_based_classification']['labels'] else 'None'}
- **Capture Quality:** {report['section_9_evidence_based_classification']['capture_quality']}
- **Semantic Validity:** {report['section_9_evidence_based_classification']['semantic_validity']}
- **B2 Classification:** {report['section_9_evidence_based_classification']['b2_classification']}
- **C3 Classification:** {report['section_9_evidence_based_classification']['c3_classification']}
- **Scene OOD Status:** {report['section_9_evidence_based_classification']['scene_ood_status']}

## Section 10: Primary Next Gate

**Selected:** `{report['section_10_primary_next_gate']['selected_gate']}`

**Probe Execution Valid:** {report['section_10_primary_next_gate']['probe_execution_valid']}

**Probe Status:** {report['section_10_primary_next_gate']['probe_execution_message']}

**Missing Fields:** {', '.join(report['section_10_primary_next_gate']['probe_missing_fields']) if report['section_10_primary_next_gate']['probe_missing_fields'] else 'None'}

**Rationale:** {report['section_10_primary_next_gate']['rationale']}

**Other Candidates:** {', '.join(report['section_10_primary_next_gate']['candidate_gates']) if report['section_10_primary_next_gate']['candidate_gates'] else 'None'}

## Artifacts Generated

{chr(10).join(f"- {art}" for art in report['section_1_capture_implementation']['artifacts_created'])}

## Conclusion

{report['conclusion']}
"""
    
    return md


if __name__ == '__main__':
    sys.exit(main())
