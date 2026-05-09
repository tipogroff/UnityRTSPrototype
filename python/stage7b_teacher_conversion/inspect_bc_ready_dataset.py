#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np


DEFAULT_DATASET_DIR = Path(
    "python/week5_teacher_legacy032/teacher_exports_bc/"
    "day6_bc_ready_legacy032_3m_unity_v2_20260501T164317Z"
)


def _read_manifest(dataset_dir: Path) -> Tuple[Path | None, Dict[str, Any] | None]:
    path = dataset_dir / "bc_manifest.json"
    if not path.exists():
        return None, None
    try:
        return path, json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return path, None


def _extract_branch_sizes(manifest: Dict[str, Any] | None) -> List[int]:
    if not manifest:
        return []

    direct = manifest.get("branch_sizes")
    if isinstance(direct, list) and direct:
        return [int(v) for v in direct]

    schema = manifest.get("schema", {})
    sample_structure = schema.get("sample_structure", {})
    required = sample_structure.get("required", {})
    target = required.get("target_action_branches", {})
    sizes = target.get("branch_sizes")
    if isinstance(sizes, list) and sizes:
        return [int(v) for v in sizes]

    split_summary = manifest.get("split_summary", {})
    for key in ("train", "validation", "debug"):
        s = split_summary.get(key, {})
        maybe = s.get("target_action_branch_sizes")
        if isinstance(maybe, list) and maybe:
            return [int(v) for v in maybe]

    return []


def _summarize_npz(path: Path) -> Dict[str, Any]:
    out: Dict[str, Any] = {
        "file": str(path),
        "exists": path.exists(),
        "keys": [],
        "arrays": {},
    }
    if not path.exists():
        return out

    with np.load(path, allow_pickle=True) as npz:
        keys = list(npz.keys())
        out["keys"] = keys
        required = {"observations", "actions"}
        missing = sorted(required.difference(set(keys)))
        out["missing_required_keys"] = missing
        arrays: Dict[str, Any] = {}
        for key in keys:
            arr = np.asarray(npz[key])
            arrays[key] = {
                "shape": [int(v) for v in arr.shape],
                "dtype": str(arr.dtype),
            }
        out["arrays"] = arrays
    return out


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Inspect BC-ready dataset schema for Stage7B conversion preflight.")
    parser.add_argument("--dataset-dir", type=Path, default=DEFAULT_DATASET_DIR)
    parser.add_argument("--output-json", type=Path, default=None)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    dataset_dir = args.dataset_dir

    manifest_path, manifest = _read_manifest(dataset_dir)
    probe: Dict[str, Any] = {
        "dataset_dir": str(dataset_dir),
        "manifest_path": str(manifest_path) if manifest_path else None,
        "manifest_valid": manifest is not None,
        "strict_format": {
            "manifest_file": "bc_manifest.json",
            "observation_key": "observations",
            "action_key": "actions",
        },
        "manifest_branch_sizes": _extract_branch_sizes(manifest),
        "split_npz": {
            "train": _summarize_npz(dataset_dir / "bc_train.npz"),
            "validation": _summarize_npz(dataset_dir / "bc_validation.npz"),
            "debug": _summarize_npz(dataset_dir / "bc_debug.npz"),
        },
    }

    text = json.dumps(probe, ensure_ascii=True, indent=2)
    print(text)
    if args.output_json:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(text + "\n", encoding="utf-8")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
