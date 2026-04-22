#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Dict, List

import numpy as np


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Week 5 Day 6 minimal BC loader dry run. "
            "Validates BC-ready split files can be loaded with expected shape and branch semantics."
        )
    )
    parser.add_argument(
        "--bc-ready-dir",
        type=Path,
        required=True,
        help="Path to Day 6 BC-ready dataset directory that contains bc_manifest.json and split NPZ files.",
    )
    parser.add_argument("--batch-size", type=int, default=64, help="Batch size used for dry-run shape checks.")
    return parser.parse_args()


def read_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")


def require_keys(keys: List[str], expected: List[str], split_name: str) -> List[str]:
    present = set(keys)
    missing = [k for k in expected if k not in present]
    return [f"{split_name}: missing required key '{k}'" for k in missing]


def validate_branch_ranges(
    action_branches: np.ndarray,
    branch_sizes: np.ndarray,
    split_name: str,
) -> List[str]:
    errors: List[str] = []
    if action_branches.ndim != 3:
        return [f"{split_name}: target_action_branches must be 3D, got ndim={action_branches.ndim}"]

    if branch_sizes.ndim != 1:
        return [f"{split_name}: target_action_branch_sizes must be 1D"]

    if action_branches.shape[2] != branch_sizes.shape[0]:
        return [
            (
                f"{split_name}: target_action_branches branch count mismatch "
                f"(data={action_branches.shape[2]}, branch_sizes={branch_sizes.shape[0]})"
            )
        ]

    for branch_idx, branch_size in enumerate(branch_sizes.tolist()):
        values = action_branches[..., branch_idx]
        min_v = int(np.min(values)) if values.size > 0 else 0
        max_v = int(np.max(values)) if values.size > 0 else 0
        if min_v < 0 or max_v >= int(branch_size):
            errors.append(
                (
                    f"{split_name}: branch {branch_idx} values out of range "
                    f"[0,{int(branch_size) - 1}] (min={min_v}, max={max_v})"
                )
            )
    return errors


def run_split_check(split_name: str, split_path: Path, batch_size: int) -> Dict[str, Any]:
    required_fields = [
        "schema_version",
        "split",
        "input_tensor",
        "target_action_branches",
        "sample_id",
        "episode_id",
        "step_id",
        "source_episode_file",
        "target_action_branch_sizes",
        "has_optional_mask",
    ]

    errors: List[str] = []
    warnings: List[str] = []

    with np.load(split_path, allow_pickle=True) as data:
        keys = list(data.files)
        errors.extend(require_keys(keys, required_fields, split_name))
        if errors:
            return {
                "split": split_name,
                "path": str(split_path),
                "status": "fail",
                "errors": errors,
                "warnings": warnings,
            }

        input_tensor = np.asarray(data["input_tensor"])
        target = np.asarray(data["target_action_branches"])
        sample_id = np.asarray(data["sample_id"])
        episode_id = np.asarray(data["episode_id"])
        step_id = np.asarray(data["step_id"])
        source_episode_file = np.asarray(data["source_episode_file"])
        branch_sizes = np.asarray(data["target_action_branch_sizes"])
        has_optional_mask = bool(np.asarray(data["has_optional_mask"]).reshape(-1)[0])

        n = int(input_tensor.shape[0])
        if target.shape[0] != n:
            errors.append(f"{split_name}: target_action_branches sample count mismatch")
        if sample_id.shape[0] != n:
            errors.append(f"{split_name}: sample_id length mismatch")
        if episode_id.shape[0] != n:
            errors.append(f"{split_name}: episode_id length mismatch")
        if step_id.shape[0] != n:
            errors.append(f"{split_name}: step_id length mismatch")
        if source_episode_file.shape[0] != n:
            errors.append(f"{split_name}: source_episode_file length mismatch")

        if input_tensor.ndim != 4:
            errors.append(f"{split_name}: input_tensor must be 4D [N,H,W,C], got {input_tensor.shape}")
        if target.ndim != 3:
            errors.append(f"{split_name}: target_action_branches must be 3D [N,576,7], got {target.shape}")

        errors.extend(validate_branch_ranges(target, branch_sizes, split_name))

        if has_optional_mask:
            if "optional_mask" not in data.files:
                errors.append(f"{split_name}: has_optional_mask=true but optional_mask key is missing")
            else:
                optional_mask = np.asarray(data["optional_mask"])
                if optional_mask.shape != target.shape:
                    errors.append(
                        (
                            f"{split_name}: optional_mask shape mismatch. "
                            f"expected {target.shape}, got {optional_mask.shape}"
                        )
                    )
        else:
            if "optional_mask" in data.files:
                warnings.append(f"{split_name}: optional_mask exists but has_optional_mask=false")

        if n == 0:
            warnings.append(f"{split_name}: split is empty")

        b = min(max(1, int(batch_size)), max(1, n))
        x_batch = input_tensor[:b]
        y_batch = target[:b]

        dry_run_batch = {
            "batch_size": int(b),
            "input_batch_shape": list(x_batch.shape),
            "target_batch_shape": list(y_batch.shape),
            "sample_ids_preview": sample_id[: min(3, n)].astype(str).tolist(),
        }

        return {
            "split": split_name,
            "path": str(split_path),
            "status": "pass" if not errors else "fail",
            "samples": n,
            "input_shape": list(input_tensor.shape),
            "target_shape": list(target.shape),
            "branch_sizes": [int(v) for v in branch_sizes.tolist()],
            "has_optional_mask": has_optional_mask,
            "dry_run_batch": dry_run_batch,
            "errors": errors,
            "warnings": warnings,
        }


def main() -> int:
    args = parse_args()
    bc_ready_dir = args.bc_ready_dir.resolve()
    manifest_path = bc_ready_dir / "bc_manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError(f"Missing bc_manifest.json: {manifest_path}")

    manifest = read_json(manifest_path)
    split_files = manifest.get("split_files", {})
    required_splits = ["train", "validation"]

    checks: List[Dict[str, Any]] = []
    top_errors: List[str] = []

    for split_name in required_splits + (["debug"] if "debug" in split_files else []):
        path_raw = split_files.get(split_name)
        if not path_raw:
            top_errors.append(f"manifest: missing split_files.{split_name}")
            continue

        split_path = Path(path_raw)
        if not split_path.exists():
            top_errors.append(f"{split_name}: split path does not exist: {split_path}")
            continue

        check = run_split_check(split_name=split_name, split_path=split_path, batch_size=int(args.batch_size))
        checks.append(check)

    for item in checks:
        top_errors.extend(item.get("errors", []))

    result = {
        "status": "pass" if len(top_errors) == 0 else "fail",
        "generated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "bc_ready_dir": str(bc_ready_dir),
        "schema_version": manifest.get("schema_version"),
        "checks": checks,
        "errors": top_errors,
    }

    output_path = bc_ready_dir / "dry_run_bc_loader_report.json"
    write_json(output_path, result)
    print(json.dumps(result, ensure_ascii=True, indent=2))
    print(f"Dry run report: {output_path}")
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
