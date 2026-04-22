#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict

from student_bc_contract import BCContractError
from student_bc_loader import load_bc_ready_dataset


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Week 6 Day 1: inspect canonical BC-ready train/validation artifacts and "
            "validate student-side BC training contract."
        )
    )
    parser.add_argument(
        "--bc-ready-dir",
        type=Path,
        required=True,
        help="Path to BC-ready run directory containing bc_manifest.json, bc_train.npz, bc_validation.npz.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=64,
        help="Batch size for smoke iteration over loaded split objects.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print summary as JSON only.",
    )
    return parser.parse_args()


def _split_summary(split: Any) -> Dict[str, Any]:
    return {
        "path": str(split.path),
        "samples": split.samples,
        "input_tensor_shape": list(split.input_tensor.shape),
        "input_tensor_dtype": str(split.input_tensor.dtype),
        "target_action_branches_shape": list(split.target_action_branches.shape),
        "target_action_branches_dtype": str(split.target_action_branches.dtype),
        "target_action_branch_sizes": [int(x) for x in split.target_action_branch_sizes.tolist()],
        "mask_available": split.mask_available,
        "has_optional_mask_flag": split.has_optional_mask_flag,
        "schema_version_from_file": split.schema_version_from_file,
    }


def build_summary(dataset: Any, batch_size: int) -> Dict[str, Any]:
    batch_size = max(1, int(batch_size))

    train_batch = next(dataset.train.iter_batches(batch_size=batch_size))
    val_batch = next(dataset.validation.iter_batches(batch_size=batch_size))

    diagnostics = {
        "train_keys": sorted(dataset.train.diagnostic_arrays.keys()),
        "validation_keys": sorted(dataset.validation.diagnostic_arrays.keys()),
    }

    summary: Dict[str, Any] = {
        "status": "pass",
        "bc_ready_dir": str(dataset.run_dir),
        "manifest_path": str(dataset.manifest_path),
        "schema_version": dataset.contract.schema_version,
        "scope": {
            "uses_bc_ready_dataset_only": True,
            "uses_raw_or_adapted_dataset_as_training_input": False,
            "changes_week5_schema": False,
        },
        "input_contract": {
            "primary_input_key": dataset.contract.input_key,
            "primary_input_shape_per_sample": list(dataset.contract.input_shape_per_sample),
            "primary_input_dtype": dataset.contract.input_dtype,
            "global_features_mode": "optional_auxiliary_only_if_present; not required primary input",
        },
        "target_contract": {
            "target_key": dataset.contract.target_key,
            "target_shape_per_sample": list(dataset.contract.target_shape_per_sample),
            "target_dtype": dataset.contract.target_dtype,
            "target_branch_names": list(dataset.contract.target_branch_names),
            "target_branch_sizes": list(dataset.contract.target_branch_sizes),
            "active_inactive_policy_day1": (
                "Day1 only validates contract; Day2 branch-wise objective must avoid penalizing inactive branches"
            ),
        },
        "optional_mask_contract": {
            "manifest_declared_present": dataset.contract.optional_mask_declared_present,
            "manifest_note": dataset.contract.optional_mask_note,
            "train_mask_available": dataset.train.mask_available,
            "validation_mask_available": dataset.validation.mask_available,
            "missing_mask_implies_all_valid": False,
        },
        "metadata_contract": {
            "required_metadata_keys": list(dataset.contract.required_metadata_keys),
            "diagnostic_only_keys": list(dataset.contract.diagnostic_only_keys),
            "manifest_warnings": list(dataset.manifest_diagnostic_warnings),
            "diagnostic_arrays_found": diagnostics,
            "metadata_used_as_training_target": False,
            "metadata_used_as_model_input": False,
        },
        "splits": {
            "train": _split_summary(dataset.train),
            "validation": _split_summary(dataset.validation),
        },
        "smoke_batches": {
            "batch_size": batch_size,
            "train_input_batch_shape": list(train_batch.input_tensor.shape),
            "train_target_batch_shape": list(train_batch.target_action_branches.shape),
            "validation_input_batch_shape": list(val_batch.input_tensor.shape),
            "validation_target_batch_shape": list(val_batch.target_action_branches.shape),
            "train_batch_mask_present": train_batch.optional_mask is not None,
            "validation_batch_mask_present": val_batch.optional_mask is not None,
            "train_sample_id_preview": [str(x) for x in train_batch.sample_id[:3].tolist()],
            "validation_sample_id_preview": [str(x) for x in val_batch.sample_id[:3].tolist()],
        },
    }
    return summary


def print_human_summary(summary: Dict[str, Any]) -> None:
    print("=== Week 6 Day 1 BC-ready inspection ===")
    print(f"BC-ready dir: {summary['bc_ready_dir']}")
    print(f"Manifest: {summary['manifest_path']}")
    print(f"Schema version: {summary['schema_version']}")

    print("\nSplits:")
    for split_name in ("train", "validation"):
        split = summary["splits"][split_name]
        print(
            f"- {split_name}: samples={split['samples']} "
            f"input={split['input_tensor_shape']} ({split['input_tensor_dtype']}) "
            f"target={split['target_action_branches_shape']} ({split['target_action_branches_dtype']})"
        )

    target = summary["target_contract"]
    print("\nTargets:")
    print(f"- branch_names: {target['target_branch_names']}")
    print(f"- branch_sizes: {target['target_branch_sizes']}")

    mask = summary["optional_mask_contract"]
    print("\nOptional mask:")
    print(f"- manifest_declared_present: {mask['manifest_declared_present']}")
    print(f"- train_mask_available: {mask['train_mask_available']}")
    print(f"- validation_mask_available: {mask['validation_mask_available']}")

    metadata = summary["metadata_contract"]
    print("\nMetadata and diagnostics:")
    print(f"- required_metadata_keys: {metadata['required_metadata_keys']}")
    print(f"- diagnostic_only_keys: {metadata['diagnostic_only_keys']}")
    print(f"- diagnostic_arrays_found: {metadata['diagnostic_arrays_found']}")
    if metadata["manifest_warnings"]:
        print(f"- manifest_warnings: {metadata['manifest_warnings']}")
    else:
        print("- manifest_warnings: none")

    smoke = summary["smoke_batches"]
    print("\nSmoke batches:")
    print(f"- batch_size: {smoke['batch_size']}")
    print(f"- train_input_batch_shape: {smoke['train_input_batch_shape']}")
    print(f"- train_target_batch_shape: {smoke['train_target_batch_shape']}")
    print(f"- validation_input_batch_shape: {smoke['validation_input_batch_shape']}")
    print(f"- validation_target_batch_shape: {smoke['validation_target_batch_shape']}")
    print(f"- train_sample_id_preview: {smoke['train_sample_id_preview']}")
    print(f"- validation_sample_id_preview: {smoke['validation_sample_id_preview']}")


def main() -> int:
    args = parse_args()
    try:
        dataset = load_bc_ready_dataset(args.bc_ready_dir)
        summary = build_summary(dataset=dataset, batch_size=args.batch_size)
    except (BCContractError, FileNotFoundError, ValueError, KeyError) as exc:
        print(f"[FAIL] {exc}")
        return 1

    if args.json:
        print(json.dumps(summary, ensure_ascii=True, indent=2))
    else:
        print_human_summary(summary)
        print("\n--- JSON summary ---")
        print(json.dumps(summary, ensure_ascii=True, indent=2))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
