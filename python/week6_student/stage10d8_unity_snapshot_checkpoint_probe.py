#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Mapping, Tuple

import numpy as np
import torch

from student_architecture_transfer import build_day3_student_model


ACTION_NAMES = ["NoOp", "Move", "Harvest", "Return", "Produce", "Attack"]


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _resolve(root: Path, p: Path) -> Path:
    return p if p.is_absolute() else (root / p)


def _to_rel(root: Path, p: Path) -> str:
    try:
        return str(p.resolve().relative_to(root.resolve())).replace("\\", "/")
    except Exception:
        return p.as_posix()


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Stage10D.8 Unity snapshot checkpoint probe")
    p.add_argument("--checkpoint", type=Path, required=True)
    p.add_argument(
        "--snapshot-json",
        type=Path,
        default=Path("python/week6_student/reports/stage10r_noop_collapse_snapshot_step0001.json"),
    )
    p.add_argument("--device", type=str, default="cpu")
    p.add_argument(
        "--output-json",
        type=Path,
        default=Path("python/week6_student/reports/stage10d8_unity_snapshot_checkpoint_probe.json"),
    )
    return p.parse_args()


def _extract_cells(snapshot: Mapping[str, Any]) -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}
    for section in ("focus_cell_diagnostics", "actor_cells"):
        rows = snapshot.get(section, [])
        if not isinstance(rows, list):
            continue
        for row in rows:
            if not isinstance(row, Mapping):
                continue
            label = str(row.get("logical_label") or row.get("logical_cell") or "").strip()
            channels = row.get("cell_observation_channels")
            flat_index = row.get("flat_index")
            if label in ("B2", "C3") and isinstance(channels, list) and len(channels) == 27 and isinstance(flat_index, int):
                out[label] = {
                    "flat_index": int(flat_index),
                    "channels": [float(x) for x in channels],
                }
    return out


def _build_sparse_observation(cells: Mapping[str, Dict[str, Any]]) -> Tuple[np.ndarray, int]:
    obs = np.zeros((24, 24, 27), dtype=np.float32)
    filled = 0
    for info in cells.values():
        flat = int(info["flat_index"])
        r = flat // 24
        c = flat % 24
        obs[r, c, :] = np.asarray(info["channels"], dtype=np.float32)
        filled += 1
    return obs, filled


def _topk(prob: np.ndarray, k: int = 3) -> List[Dict[str, Any]]:
    idx = np.argsort(-prob)[:k]
    out: List[Dict[str, Any]] = []
    for i in idx.tolist():
        out.append(
            {
                "class_id": int(i),
                "class_name": ACTION_NAMES[i] if 0 <= i < len(ACTION_NAMES) else str(i),
                "probability": float(prob[i]),
            }
        )
    return out


def main() -> int:
    args = parse_args()
    root = _repo_root()

    checkpoint = _resolve(root, args.checkpoint).resolve()
    snapshot_path = _resolve(root, args.snapshot_json).resolve()
    output_json = _resolve(root, args.output_json).resolve()

    checks: Dict[str, Any] = {}
    hard_failures: List[str] = []
    status = "pass"

    if not checkpoint.exists():
        hard_failures.append(f"checkpoint_not_found: {checkpoint.as_posix()}")
    if not snapshot_path.exists():
        status = "skipped"

    snapshot: Dict[str, Any] = {}
    if status != "skipped":
        try:
            snapshot = json.loads(snapshot_path.read_text(encoding="utf-8-sig"))
        except Exception as exc:
            hard_failures.append(f"snapshot_load_failed: {exc}")

    details: Dict[str, Any] = {
        "checkpoint": _to_rel(root, checkpoint),
        "snapshot_json": _to_rel(root, snapshot_path),
        "snapshot_available": bool(snapshot_path.exists()),
    }

    if status == "skipped":
        payload = {
            "stage": "10D.8",
            "diagnostic": "unity_snapshot_checkpoint_probe",
            "generated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "status": "skipped",
            "checks": {
                "snapshot_available": False,
            },
            "details": details,
            "hard_failures": [],
            "explicit_non_claims": [
                "No Unity launch occurred.",
                "Dry-run probe only.",
            ],
        }
        output_json.parent.mkdir(parents=True, exist_ok=True)
        output_json.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")
        print(output_json.as_posix())
        return 0

    if hard_failures:
        payload = {
            "stage": "10D.8",
            "diagnostic": "unity_snapshot_checkpoint_probe",
            "generated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "status": "fail",
            "checks": checks,
            "details": details,
            "hard_failures": hard_failures,
            "explicit_non_claims": [
                "No Unity launch occurred.",
                "Dry-run probe only.",
            ],
        }
        output_json.parent.mkdir(parents=True, exist_ok=True)
        output_json.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")
        print(output_json.as_posix())
        return 1

    cells = _extract_cells(snapshot)
    checks["has_B2"] = "B2" in cells
    checks["has_C3"] = "C3" in cells

    if not checks["has_B2"] or not checks["has_C3"]:
        hard_failures.append("snapshot_missing_B2_or_C3_cell_observation_channels")

    observation, filled_cells = _build_sparse_observation(cells)
    checks["observation_shape_24x24x27"] = tuple(observation.shape) == (24, 24, 27)
    checks["filled_cells_gt_0"] = filled_cells > 0

    if hard_failures:
        payload = {
            "stage": "10D.8",
            "diagnostic": "unity_snapshot_checkpoint_probe",
            "generated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "status": "fail",
            "checks": checks,
            "details": {**details, "filled_cells": int(filled_cells)},
            "hard_failures": hard_failures,
            "explicit_non_claims": [
                "No Unity launch occurred.",
                "Dry-run probe only.",
            ],
        }
        output_json.parent.mkdir(parents=True, exist_ok=True)
        output_json.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")
        print(output_json.as_posix())
        return 1

    device = torch.device(args.device)
    model = build_day3_student_model().to(device=device)
    ckpt = torch.load(checkpoint, map_location=device)

    if not isinstance(ckpt, Mapping) or "model_state_dict" not in ckpt:
        hard_failures.append("checkpoint_payload_invalid_or_missing_model_state_dict")
    else:
        missing, unexpected = model.load_state_dict(ckpt["model_state_dict"], strict=True)
        if missing or unexpected:
            hard_failures.append(f"state_dict_mismatch: missing={missing}, unexpected={unexpected}")

    if hard_failures:
        payload = {
            "stage": "10D.8",
            "diagnostic": "unity_snapshot_checkpoint_probe",
            "generated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "status": "fail",
            "checks": checks,
            "details": {**details, "filled_cells": int(filled_cells)},
            "hard_failures": hard_failures,
            "explicit_non_claims": [
                "No Unity launch occurred.",
                "Dry-run probe only.",
            ],
        }
        output_json.parent.mkdir(parents=True, exist_ok=True)
        output_json.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")
        print(output_json.as_posix())
        return 1

    model.eval()
    with torch.no_grad():
        x = torch.from_numpy(observation[None, ...]).to(device=device, dtype=torch.float32)
        logits = model(x)
        probs = torch.softmax(logits["action_type_logits"], dim=-1).detach().cpu().numpy()[0]

    b2_flat = int(cells["B2"]["flat_index"])
    c3_flat = int(cells["C3"]["flat_index"])

    b2_prob = probs[b2_flat]
    c3_prob = probs[c3_flat]

    b2_noop_prob = float(b2_prob[0])
    c3_noop_prob = float(c3_prob[0])

    # "strongly NoOp-only" threshold for probe interpretation.
    strong_noop_threshold = 0.90
    checks["B2_not_strongly_noop_only"] = b2_noop_prob < strong_noop_threshold
    checks["C3_not_strongly_noop_only"] = c3_noop_prob < strong_noop_threshold

    for key, passed in checks.items():
        if not bool(passed):
            hard_failures.append(f"check_failed: {key}")

    status = "pass" if not hard_failures else "fail"

    payload = {
        "stage": "10D.8",
        "diagnostic": "unity_snapshot_checkpoint_probe",
        "generated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "status": status,
        "checks": checks,
        "details": {
            **details,
            "filled_cells": int(filled_cells),
            "input_mode": "sparse_snapshot_cells_into_24x24x27",
            "strong_noop_threshold": strong_noop_threshold,
            "B2": {
                "flat_index": b2_flat,
                "action_type_probabilities": [float(x) for x in b2_prob.tolist()],
                "action_type_top3": _topk(b2_prob, k=3),
            },
            "C3": {
                "flat_index": c3_flat,
                "action_type_probabilities": [float(x) for x in c3_prob.tolist()],
                "action_type_top3": _topk(c3_prob, k=3),
            },
        },
        "hard_failures": hard_failures,
        "explicit_non_claims": [
            "Dry-run only; this is not proof of Unity runtime behavior.",
            "No Unity launch occurred.",
            "No checkpoint mutation.",
        ],
    }

    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")
    print(output_json.as_posix())
    return 0 if status == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
