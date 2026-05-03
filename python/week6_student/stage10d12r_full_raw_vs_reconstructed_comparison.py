#!/usr/bin/env python3
"""
Stage10D.12R: True Raw vs Reconstructed Fullmap Comparison

Purpose:
Compare the true full raw runtime observation tensor with reconstructed fullmap
used in Stage10D.11/D.12 audits to identify discrepancies.

Artifact inputs:
- stage10d12r_full_raw_runtime_observation_step0001.json (true raw tensor)
- stage10d11_runtime_vs_bc_channel_delta.json (reference channel data)
- stage10d12_raw_fullmap_observation_availability_audit.json (availability status)

Outputs:
- stage10d12r_full_raw_vs_reconstructed_diff.json (comprehensive comparison)
"""

import json
import math
import sys
from pathlib import Path
from typing import Dict, List, Tuple, Any, Optional


def load_json_safe(path: str) -> Optional[Dict[str, Any]]:
    """Safely load JSON file."""
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"Warning: Could not load {path}: {e}")
        return None


def extract_true_raw_tensor(captured_data: Dict[str, Any]) -> Optional[List[List[float]]]:
    """Extract [576, 27] tensor from captured JSON."""
    cells = captured_data.get('cells', [])
    if len(cells) != 576:
        return None
    
    tensor = []
    for cell in cells:
        channels = cell.get('raw_channel_vector', [])
        if len(channels) != 27:
            return None
        tensor.append(channels)
    
    return tensor


def reconstruct_fullmap_from_legacy_focus():
    """
    Attempt to reconstruct fullmap from legacy focus cell data if available.
    This is a fallback for comparison purposes.
    """
    # Try to load stage10d11 data
    reports_dir = Path(__file__).parent / 'reports'
    delta_path = reports_dir / 'stage10d11_runtime_vs_bc_channel_delta.json'
    
    if not delta_path.exists():
        return None
    
    try:
        with open(delta_path, 'r', encoding='utf-8') as f:
            delta_data = json.load(f)
        
        # This would contain reconstructed fullmap if available
        return delta_data.get('reconstructed_fullmap')
    except:
        return None


def compute_per_cell_l2_difference(true_tensor: List[List[float]], 
                                   recon_tensor: List[List[float]]) -> Tuple[List[float], float]:
    """Compute L2 difference for each cell."""
    if len(true_tensor) != len(recon_tensor):
        return [], float('inf')
    
    l2_diffs = []
    for true_cell, recon_cell in zip(true_tensor, recon_tensor):
        if len(true_cell) != len(recon_cell):
            l2_diffs.append(float('inf'))
            continue
        
        sum_sq = sum((t - r) ** 2 for t, r in zip(true_cell, recon_cell))
        l2 = math.sqrt(sum_sq)
        l2_diffs.append(l2)
    
    mean_l2 = sum(l2_diffs) / len(l2_diffs) if l2_diffs else 0
    return l2_diffs, mean_l2


def compute_per_channel_difference(true_tensor: List[List[float]], 
                                   recon_tensor: List[List[float]]) -> Dict[int, Dict[str, float]]:
    """Compute per-channel mean absolute difference."""
    if len(true_tensor) != len(recon_tensor):
        return {}
    
    channel_stats = {}
    for ch in range(27):
        true_vals = [true_tensor[i][ch] if ch < len(true_tensor[i]) else 0 
                     for i in range(len(true_tensor))]
        recon_vals = [recon_tensor[i][ch] if ch < len(recon_tensor[i]) else 0 
                      for i in range(len(recon_tensor))]
        
        diffs = [abs(t - r) for t, r in zip(true_vals, recon_vals)]
        mean_abs_diff = sum(diffs) / len(diffs) if diffs else 0
        max_diff = max(diffs) if diffs else 0
        
        channel_stats[ch] = {
            'mean_abs_diff': mean_abs_diff,
            'max_diff': max_diff,
            'std_dev': compute_std_dev(diffs),
        }
    
    return channel_stats


def compute_std_dev(values: List[float]) -> float:
    """Compute standard deviation."""
    if not values:
        return 0
    mean = sum(values) / len(values)
    var = sum((x - mean) ** 2 for x in values) / len(values)
    return math.sqrt(var)


def find_top_differing_cells(l2_diffs: List[float], 
                             true_tensor: List[List[float]],
                             recon_tensor: List[List[float]],
                             top_k: int = 10) -> List[Dict[str, Any]]:
    """Find cells with largest L2 differences."""
    if not l2_diffs:
        return []
    
    # Create list of (index, l2_diff)
    indexed_diffs = [(i, l2_diffs[i]) for i in range(len(l2_diffs))]
    indexed_diffs.sort(key=lambda x: x[1], reverse=True)
    
    top_cells = []
    for idx, l2_diff in indexed_diffs[:top_k]:
        y = idx // 24
        x = idx % 24
        
        true_cell = true_tensor[idx]
        recon_cell = recon_tensor[idx] if idx < len(recon_tensor) else []
        
        top_cells.append({
            'flat_index': idx,
            'x': x,
            'y': y,
            'l2_difference': l2_diff,
            'true_sample': true_cell[:5],  # Show first 5 channels
            'recon_sample': recon_cell[:5] if recon_cell else [],
        })
    
    return top_cells


def main():
    # Determine input file path
    reports_dir = Path(__file__).parent / 'reports'
    captured_json_path = str(reports_dir / 'stage10d12r_full_raw_runtime_observation_step0001.json')
    
    if not Path(captured_json_path).exists():
        print(f"ERROR: Captured observation file not found: {captured_json_path}")
        sys.exit(1)
    
    print("Loading true raw observation...")
    captured_data = load_json_safe(captured_json_path)
    if not captured_data:
        print("ERROR: Could not load captured observation")
        sys.exit(1)
    
    true_tensor = extract_true_raw_tensor(captured_data)
    if not true_tensor:
        print("ERROR: Could not extract true tensor from captured data")
        sys.exit(1)
    
    print(f"Extracted true tensor: {len(true_tensor)} cells x {len(true_tensor[0])} channels")
    
    # Try to reconstruct or load comparison data
    print("Attempting to load reconstructed fullmap...")
    recon_tensor = reconstruct_fullmap_from_legacy_focus()
    
    if not recon_tensor:
        print("WARNING: Could not find reconstructed fullmap for comparison")
        comparison_result = {
            'generated_at_utc': __import__('datetime').datetime.utcnow().isoformat() + 'Z',
            'comparison_status': 'UNAVAILABLE',
            'true_raw_cells': len(true_tensor),
            'reconstructed_tensor_available': False,
            'message': 'Reconstructed fullmap not found in Stage10D.11/D.12 artifacts',
            'classification': 'RECONSTRUCTION_COMPARISON_UNAVAILABLE',
        }
    else:
        print(f"Loaded reconstructed tensor: {len(recon_tensor)} cells x {len(recon_tensor[0])} channels")
        
        # Compute differences
        print("Computing per-cell L2 differences...")
        l2_diffs, mean_l2 = compute_per_cell_l2_difference(true_tensor, recon_tensor)
        
        print("Computing per-channel differences...")
        channel_diffs = compute_per_channel_difference(true_tensor, recon_tensor)
        
        # Find problematic cells
        print("Identifying top differing cells...")
        top_cells = find_top_differing_cells(l2_diffs, true_tensor, recon_tensor, top_k=10)
        
        # Focus cell analysis
        print("Analyzing B2 and C3 differences...")
        b2_l2 = l2_diffs[25] if len(l2_diffs) > 25 else 0
        c3_l2 = l2_diffs[50] if len(l2_diffs) > 50 else 0
        
        # Determine classification
        if mean_l2 < 0.01:
            classification = "RECONSTRUCTION_MATCHES_RAW"
            match_quality = "high"
        elif mean_l2 < 0.1:
            classification = "RECONSTRUCTION_PARTIALLY_MATCHES_RAW"
            match_quality = "moderate"
        else:
            classification = "RECONSTRUCTION_DIVERGES_FROM_RAW"
            match_quality = "low"
        
        comparison_result = {
            'generated_at_utc': __import__('datetime').datetime.utcnow().isoformat() + 'Z',
            'comparison_status': 'COMPLETED',
            'true_raw_cells': len(true_tensor),
            'reconstructed_cells': len(recon_tensor),
            'global_comparison': {
                'mean_l2_difference': mean_l2,
                'max_l2_difference': max(l2_diffs) if l2_diffs else 0,
                'min_l2_difference': min(l2_diffs) if l2_diffs else 0,
                'match_quality': match_quality,
            },
            'per_channel_comparison': {
                str(ch): stats for ch, stats in channel_diffs.items()
            },
            'focus_cells': {
                'B2': {
                    'flat_index': 25,
                    'x': 1,
                    'y': 1,
                    'l2_difference': b2_l2,
                },
                'C3': {
                    'flat_index': 50,
                    'x': 2,
                    'y': 2,
                    'l2_difference': c3_l2,
                },
            },
            'top_10_differing_cells': top_cells,
            'top_differing_channels': sorted(
                [
                    {'channel': ch, 'mean_abs_diff': stats['mean_abs_diff'], 'max_diff': stats['max_diff']}
                    for ch, stats in channel_diffs.items()
                ],
                key=lambda x: x['mean_abs_diff'],
                reverse=True
            )[:10],
            'classification': classification,
        }
    
    # Write comparison report
    output_path = reports_dir / 'stage10d12r_full_raw_vs_reconstructed_diff.json'
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(comparison_result, f, indent=2)
    
    print(f"\nComparison report written to: {output_path}")
    print(f"Classification: {comparison_result.get('classification', 'N/A')}")
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
