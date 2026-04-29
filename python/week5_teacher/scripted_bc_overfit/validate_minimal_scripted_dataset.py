#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List

import numpy as np

from scripted_bc_utils import (
    DEFAULT_DATASET,
    DEFAULT_MANIFEST,
    DEFAULT_VALIDATION,
    branch_slices,
    choose_dataset_decision,
    class_presence_from_hist,
    load_dataset_npz,
    utc_now,
    write_json,
)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Validate minimal scripted dataset for overfit gate.")
    p.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    p.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    p.add_argument("--output", type=Path, default=DEFAULT_VALIDATION)
    return p.parse_args()


def main() -> int:
    args = parse_args()

    warnings: List[str] = []
    errors: List[str] = []
    manifest_payload: Dict[str, Any] = {}

    if args.manifest.is_file():
        try:
            manifest_payload = json.loads(args.manifest.read_text(encoding="utf-8"))
        except Exception as exc:
            warnings.append(f"manifest_read_error:{type(exc).__name__}")

    try:
        data = load_dataset_npz(args.dataset)
    except Exception as exc:
        payload = {
            "schema": "week5_minimal_scripted_dataset_validation.v1",
            "generated_at_utc": utc_now(),
            "decision": "FAIL_DATASET_SHAPE",
            "fatal_shape_error": True,
            "warnings": warnings,
            "errors": [f"{type(exc).__name__}: {exc}"],
        }
        write_json(args.output, payload)
        print(args.output)
        return 2

    obs = np.asarray(data.get("obs"))
    actions = np.asarray(data.get("actions"))
    masks = np.asarray(data.get("masks"))
    actor_valid = np.asarray(data.get("actor_valid"))

    fatal_shape_error = False
    if obs.ndim != 4:
        fatal_shape_error = True
        errors.append(f"obs ndim expected 4, got {obs.ndim}")
    if actions.ndim != 4:
        fatal_shape_error = True
        errors.append(f"actions ndim expected 4, got {actions.ndim}")
    if masks.ndim != 4:
        fatal_shape_error = True
        errors.append(f"masks ndim expected 4, got {masks.ndim}")
    if actor_valid.ndim != 3:
        fatal_shape_error = True
        errors.append(f"actor_valid ndim expected 3, got {actor_valid.ndim}")

    if not fatal_shape_error:
        if actions.shape[-1] != 7:
            fatal_shape_error = True
            errors.append(f"actions last dim expected 7, got {actions.shape[-1]}")
        if masks.shape[-1] != 79:
            fatal_shape_error = True
            errors.append(f"masks last dim expected 79, got {masks.shape[-1]}")
        if obs.shape[:3] != actions.shape[:3] or obs.shape[:3] != masks.shape[:3] or obs.shape[:3] != actor_valid.shape:
            fatal_shape_error = True
            errors.append("obs/actions/masks/actor_valid spatial dimensions mismatch")

    action_hist: Dict[str, int] = {}
    invalid_action_count = 0
    active_actor_samples = 0

    if not fatal_shape_error:
        slices = branch_slices()
        n, h, w, _ = actions.shape
        for i in range(n):
            for y in range(h):
                for x in range(w):
                    if not bool(actor_valid[i, y, x]):
                        continue
                    active_actor_samples += 1
                    at = int(actions[i, y, x, 0])
                    name = {
                        0: "noop",
                        1: "move",
                        2: "harvest",
                        3: "return",
                        4: "produce",
                        5: "attack",
                    }.get(at, f"unknown_{at}")
                    action_hist[name] = int(action_hist.get(name, 0)) + 1

                    relevant = [0]
                    if at == 1:
                        relevant.append(1)
                    elif at == 2:
                        relevant.append(2)
                    elif at == 3:
                        relevant.append(3)
                    elif at == 4:
                        relevant.extend([4, 5])
                    elif at == 5:
                        relevant.append(6)

                    for b in relevant:
                        s, e = slices[b]
                        idx = int(actions[i, y, x, b])
                        pos = s + idx
                        if idx < 0 or (s + idx) >= e:
                            invalid_action_count += 1
                            continue
                        if pos < 0 or pos >= masks.shape[-1]:
                            invalid_action_count += 1
                            continue
                        if masks[i, y, x, pos] <= 0:
                            invalid_action_count += 1

    non_noop_count = sum(v for k, v in action_hist.items() if k != "noop")
    total_actions = sum(action_hist.values())
    non_noop_share = float(non_noop_count / total_actions) if total_actions > 0 else 0.0

    class_presence = class_presence_from_hist(action_hist)
    missing_classes = [k for k, present in class_presence.items() if (not present) and k != "noop"]
    if missing_classes:
        warnings.append("class_missing:" + ",".join(missing_classes))

    payload = {
        "schema": "week5_minimal_scripted_dataset_validation.v1",
        "generated_at_utc": utc_now(),
        "dataset_path": str(args.dataset),
        "manifest_path": str(args.manifest),
        "shapes": {
            "obs": [int(v) for v in obs.shape] if hasattr(obs, "shape") else None,
            "actions": [int(v) for v in actions.shape] if hasattr(actions, "shape") else None,
            "masks": [int(v) for v in masks.shape] if hasattr(masks, "shape") else None,
            "actor_valid": [int(v) for v in actor_valid.shape] if hasattr(actor_valid, "shape") else None,
        },
        "branch_layout": [6, 4, 4, 4, 4, 7, 49],
        "fatal_shape_error": bool(fatal_shape_error),
        "invalid_action_count": int(invalid_action_count),
        "action_type_histogram": {k: int(v) for k, v in sorted(action_hist.items())},
        "non_noop_share": float(non_noop_share),
        "active_actor_sample_count": int(active_actor_samples),
        "class_presence": class_presence,
        "missing_classes": missing_classes,
        "per_mode_sample_count": manifest_payload.get("per_mode_sample_count", {}),
        "per_mode_action_histogram": manifest_payload.get("per_mode_action_histogram", {}),
        "per_mode_missing_classes": manifest_payload.get("per_mode_missing_classes", {}),
        "inactive_branch_policy_note": "Inactive branches may be zero and should be ignored by downstream gated loss.",
        "warnings": warnings,
        "errors": errors,
    }

    payload["decision"] = choose_dataset_decision(payload)
    write_json(args.output, payload)
    print(args.output)
    return 0 if str(payload["decision"]).startswith("PASS") or str(payload["decision"]).startswith("PARTIAL_PASS") else 2


if __name__ == "__main__":
    raise SystemExit(main())
