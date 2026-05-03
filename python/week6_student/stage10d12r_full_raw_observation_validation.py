#!/usr/bin/env python3
"""
Stage10D.12R: Full Raw Runtime Observation Validation Script

Purpose:
Validate the full raw runtime observation tensor captured from Unity.
Ensure shape, data integrity, semantic correctness, and presence of focus cells.

Artifact inputs:
- stage10d12r_full_raw_runtime_observation_step0001.json (captured tensor with metadata)

Outputs:
- stage10d12r_full_raw_observation_validation.json (comprehensive validation report)
"""

import json
import math
import sys
from pathlib import Path
from typing import Dict, List, Tuple, Any


def load_captured_observation(json_path: str) -> Dict[str, Any]:
    """Load the captured full raw observation tensor."""
    with open(json_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def validate_tensor_shape(data: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """Validate tensor shape is [24,24,27]."""
    issues = []
    
    expected_h, expected_w, expected_c = 24, 24, 27
    
    if 'tensor_shape' not in data:
        issues.append("Missing tensor_shape field")
        return False, issues
    
    shape = data.get('tensor_shape', [])
    if len(shape) != 3:
        issues.append(f"Tensor shape has wrong dimensionality: {len(shape)} (expected 3)")
        return False, issues
    
    h, w, c = shape
    if h != expected_h or w != expected_w or c != expected_c:
        issues.append(f"Tensor shape mismatch: got [{h},{w},{c}], expected [{expected_h},{expected_w},{expected_c}]")
        return False, issues
    
    return True, issues


def validate_cell_count(data: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """Validate exactly 576 cells present."""
    issues = []
    
    cells = data.get('cells', [])
    if len(cells) != 576:
        issues.append(f"Cell count mismatch: got {len(cells)}, expected 576")
        return False, issues
    
    return True, issues


def validate_channel_integrity(data: Dict[str, Any]) -> Tuple[bool, List[str], Dict[str, int]]:
    """Validate all cells have 27 channels with valid values."""
    issues = []
    nan_inf_counts = {
        'nan_count': 0,
        'inf_count': 0,
        'total_values': 0,
    }
    
    cells = data.get('cells', [])
    for cell_idx, cell in enumerate(cells):
        channels = cell.get('raw_channel_vector', [])
        
        if len(channels) != 27:
            issues.append(f"Cell {cell_idx} has wrong channel count: {len(channels)} (expected 27)")
            continue
        
        for ch_idx, val in enumerate(channels):
            nan_inf_counts['total_values'] += 1
            if math.isnan(val):
                nan_inf_counts['nan_count'] += 1
                if nan_inf_counts['nan_count'] <= 5:  # Log first 5
                    issues.append(f"NaN at cell {cell_idx}, channel {ch_idx}")
            elif math.isinf(val):
                nan_inf_counts['inf_count'] += 1
                if nan_inf_counts['inf_count'] <= 5:  # Log first 5
                    issues.append(f"Inf at cell {cell_idx}, channel {ch_idx}")
    
    is_valid = nan_inf_counts['nan_count'] == 0 and nan_inf_counts['inf_count'] == 0
    return is_valid, issues, nan_inf_counts


def validate_focus_cells_present(data: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """Validate focus cells B2 and C3 are present."""
    issues = []
    
    # B2: flat=25 (x=1, y=1)
    # C3: flat=50 (x=2, y=2)
    cells = data.get('cells', [])
    
    b2_found = False
    c3_found = False
    
    for cell in cells:
        flat = cell.get('flat_index', -1)
        if flat == 25:
            b2_found = True
            if cell.get('x') != 1 or cell.get('y') != 1:
                issues.append(f"B2 cell (flat=25) has wrong coordinates: x={cell.get('x')}, y={cell.get('y')}")
        elif flat == 50:
            c3_found = True
            if cell.get('x') != 2 or cell.get('y') != 2:
                issues.append(f"C3 cell (flat=50) has wrong coordinates: x={cell.get('x')}, y={cell.get('y')}")
    
    if not b2_found:
        issues.append("Focus cell B2 (flat=25) not found")
    if not c3_found:
        issues.append("Focus cell C3 (flat=50) not found")
    
    return b2_found and c3_found, issues


def validate_owner_semantics(data: Dict[str, Any]) -> Tuple[bool, List[str], Dict[str, int]]:
    """Validate owner channels are one-hot (or zero)."""
    issues = []
    stats = {
        'owner_neutral': 0,
        'owner_self': 0,
        'owner_enemy': 0,
        'owner_none': 0,
        'owner_multi': 0,  # Multiple set (invalid)
        'owner_invalid': 0,
    }
    
    cells = data.get('cells', [])
    for cell_idx, cell in enumerate(cells):
        channels = cell.get('raw_channel_vector', [])
        if len(channels) < 5:
            continue
        
        # Channels 2-4: owner_neutral, owner_self, owner_enemy
        owner_neutral = channels[2] > 0.5
        owner_self = channels[3] > 0.5
        owner_enemy = channels[4] > 0.5
        
        owner_count = sum([owner_neutral, owner_self, owner_enemy])
        
        if owner_count == 0:
            stats['owner_none'] += 1
        elif owner_count == 1:
            if owner_neutral:
                stats['owner_neutral'] += 1
            elif owner_self:
                stats['owner_self'] += 1
            else:
                stats['owner_enemy'] += 1
        else:
            stats['owner_multi'] += 1
            issues.append(f"Cell {cell_idx}: Multiple owner bits set")
    
    is_valid = stats['owner_multi'] == 0
    return is_valid, issues, stats


def validate_unit_semantics(data: Dict[str, Any]) -> Tuple[bool, List[str], Dict[str, int]]:
    """Validate unit channels are one-hot (or zero)."""
    issues = []
    stats = {
        'unit_resource': 0,
        'unit_base': 0,
        'unit_barracks': 0,
        'unit_worker': 0,
        'unit_light': 0,
        'unit_heavy': 0,
        'unit_ranged': 0,
        'unit_none': 0,
        'unit_multi': 0,  # Multiple set (invalid)
    }
    
    cells = data.get('cells', [])
    for cell_idx, cell in enumerate(cells):
        channels = cell.get('raw_channel_vector', [])
        if len(channels) < 12:
            continue
        
        # Channels 5-11: unit types
        unit_bits = [channels[i] > 0.5 for i in range(5, 12)]
        unit_count = sum(unit_bits)
        
        if unit_count == 0:
            stats['unit_none'] += 1
        elif unit_count == 1:
            for i in range(7):
                if unit_bits[i]:
                    unit_types = ['unit_resource', 'unit_base', 'unit_barracks', 'unit_worker', 
                                 'unit_light', 'unit_heavy', 'unit_ranged']
                    stats[unit_types[i]] += 1
        else:
            stats['unit_multi'] += 1
            issues.append(f"Cell {cell_idx}: Multiple unit bits set")
    
    is_valid = stats['unit_multi'] == 0
    return is_valid, issues, stats


def validate_action_semantics(data: Dict[str, Any]) -> Tuple[bool, List[str], Dict[str, int]]:
    """Validate current action channels are one-hot (or zero)."""
    issues = []
    stats = {
        'action_noop': 0,
        'action_move': 0,
        'action_harvest': 0,
        'action_return': 0,
        'action_produce': 0,
        'action_attack': 0,
        'action_none': 0,
        'action_multi': 0,  # Multiple set (invalid)
    }
    
    cells = data.get('cells', [])
    for cell_idx, cell in enumerate(cells):
        channels = cell.get('raw_channel_vector', [])
        if len(channels) < 18:
            continue
        
        # Channels 12-17: current action
        action_bits = [channels[i] > 0.5 for i in range(12, 18)]
        action_count = sum(action_bits)
        
        if action_count == 0:
            stats['action_none'] += 1
        elif action_count == 1:
            for i in range(6):
                if action_bits[i]:
                    action_types = ['action_noop', 'action_move', 'action_harvest', 'action_return',
                                   'action_produce', 'action_attack']
                    stats[action_types[i]] += 1
        else:
            stats['action_multi'] += 1
            issues.append(f"Cell {cell_idx}: Multiple action bits set")
    
    is_valid = stats['action_multi'] == 0
    return is_valid, issues, stats


def extract_focus_cell_vectors(data: Dict[str, Any]) -> Dict[str, List[float]]:
    """Extract full channel vectors for B2 and C3."""
    vectors = {'B2': [], 'C3': []}
    
    cells = data.get('cells', [])
    for cell in cells:
        flat = cell.get('flat_index', -1)
        channels = cell.get('raw_channel_vector', [])
        
        if flat == 25:  # B2
            vectors['B2'] = channels
        elif flat == 50:  # C3
            vectors['C3'] = channels
    
    return vectors


def main():
    # Determine input file path
    if len(sys.argv) > 1:
        captured_json_path = sys.argv[1]
    else:
        # Default: look for step0001
        reports_dir = Path(__file__).parent / 'reports'
        captured_json_path = str(reports_dir / 'stage10d12r_full_raw_runtime_observation_step0001.json')
    
    if not Path(captured_json_path).exists():
        print(f"ERROR: Captured observation file not found: {captured_json_path}")
        sys.exit(1)
    
    print(f"Loading captured observation from: {captured_json_path}")
    data = load_captured_observation(captured_json_path)
    
    # Run validation checks
    all_issues = []
    
    print("Validating tensor shape...")
    shape_valid, shape_issues = validate_tensor_shape(data)
    all_issues.extend(shape_issues)
    
    print("Validating cell count...")
    cell_valid, cell_issues = validate_cell_count(data)
    all_issues.extend(cell_issues)
    
    print("Validating channel integrity...")
    channel_valid, channel_issues, nan_inf_stats = validate_channel_integrity(data)
    all_issues.extend(channel_issues)
    
    print("Validating focus cells...")
    focus_valid, focus_issues = validate_focus_cells_present(data)
    all_issues.extend(focus_issues)
    
    print("Validating owner semantics...")
    owner_valid, owner_issues, owner_stats = validate_owner_semantics(data)
    all_issues.extend(owner_issues)
    
    print("Validating unit semantics...")
    unit_valid, unit_issues, unit_stats = validate_unit_semantics(data)
    all_issues.extend(unit_issues)
    
    print("Validating action semantics...")
    action_valid, action_issues, action_stats = validate_action_semantics(data)
    all_issues.extend(action_issues)
    
    print("Extracting focus cell vectors...")
    focus_vectors = extract_focus_cell_vectors(data)
    
    # Determine overall status
    all_valid = shape_valid and cell_valid and channel_valid and focus_valid and \
                owner_valid and unit_valid and action_valid
    
    if all_valid:
        print("✓ All validation checks passed!")
        classification = "FULL_RAW_576_CAPTURED"
    else:
        print("✗ Some validation checks failed!")
        if not channel_valid:
            classification = "RAW_CAPTURE_CONTAINS_NAN_INF"
        elif not shape_valid:
            classification = "RAW_CAPTURE_SHAPE_INVALID"
        elif not focus_valid:
            classification = "RAW_CAPTURE_FOCUS_MISMATCH"
        else:
            classification = "RAW_CAPTURE_SEMANTIC_ISSUES"
    
    # Build validation report
    validation_report = {
        'generated_at_utc': __import__('datetime').datetime.utcnow().isoformat() + 'Z',
        'input_file': captured_json_path,
        'classification': classification,
        'all_checks_passed': all_valid,
        'summary': {
            'total_issues': len(all_issues),
            'shape_valid': shape_valid,
            'cell_count_valid': cell_valid,
            'channels_valid': channel_valid,
            'focus_cells_valid': focus_valid,
            'owner_valid': owner_valid,
            'unit_valid': unit_valid,
            'action_valid': action_valid,
        },
        'nan_inf_stats': nan_inf_stats,
        'owner_distribution': owner_stats,
        'unit_distribution': unit_stats,
        'action_distribution': action_stats,
        'focus_cell_vectors': {
            'B2': focus_vectors.get('B2', []),
            'C3': focus_vectors.get('C3', []),
        },
        'issues': all_issues[:100],  # Cap at 100 for readability
        'issues_truncated': len(all_issues) > 100,
    }
    
    # Write validation report
    output_path = Path(captured_json_path).parent / 'stage10d12r_full_raw_observation_validation.json'
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(validation_report, f, indent=2)
    
    print(f"\nValidation report written to: {output_path}")
    print(f"Classification: {classification}")
    
    return 0 if all_valid else 1


if __name__ == '__main__':
    sys.exit(main())
