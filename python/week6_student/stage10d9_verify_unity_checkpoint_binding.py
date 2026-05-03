from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import torch

from student_architecture_transfer import build_day3_student_model
from student_branch_contract import EXPECTED_BC_BRANCH_SIZES

TARGET_SCENE = Path("Assets/Scenes/Week6_StudentVisualInspection.unity")
TARGET_CHECKPOINT = Path(
    "python/week6_student/runs/legacy032_v2_semantic_bc_stage10d8_20260503T093718Z/student_bc_semantic_best.pt"
)
OLD_CHECKPOINT = Path(
    "python/week6_student/runs/legacy032_v2_bc_minimal_20260501T195501Z/student_bc_transfer_best.pt"
)
OUT_JSON = Path("python/week6_student/reports/stage10d9_checkpoint_binding_verification.json")
EXPECTED_BRANCH_SIZES = list(EXPECTED_BC_BRANCH_SIZES)
EXPECTED_STAGE_PREFIX = "10D.8"


@dataclass
class Check:
    name: str
    ok: bool
    details: Any


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _extract_scene_checkpoint(scene_text: str) -> str | None:
    marker = "_checkpointRelativePath:"
    for line in scene_text.splitlines():
        line = line.strip()
        if line.startswith(marker):
            return line.split(":", 1)[1].strip()
    return None


def _to_rel(repo_root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(repo_root.resolve()).as_posix()
    except Exception:
        return path.as_posix()


def _state_dict_branch_sizes(model_state: dict[str, Any]) -> dict[str, int]:
    sizes: dict[str, int] = {}
    key_map = {
        "action_type": "branch_heads.action_type_head.weight",
        "move_dir": "branch_heads.move_dir_head.weight",
        "harvest_dir": "branch_heads.harvest_dir_head.weight",
        "return_dir": "branch_heads.return_dir_head.weight",
        "produce_dir": "branch_heads.produce_dir_head.weight",
        "produce_unit_type": "branch_heads.produce_unit_type_head.weight",
        "attack_target_local": "branch_heads.attack_target_local_head.weight",
    }
    for name, key in key_map.items():
        tensor = model_state.get(key)
        if tensor is None:
            sizes[name] = -1
        else:
            sizes[name] = int(tensor.shape[0])
    return sizes


def main() -> int:
    repo_root = Path(__file__).resolve().parents[2]
    scene_abs = repo_root / TARGET_SCENE
    checkpoint_abs = repo_root / TARGET_CHECKPOINT
    old_checkpoint_abs = repo_root / OLD_CHECKPOINT

    checks: list[Check] = []

    scene_exists = scene_abs.exists()
    checks.append(Check("scene_exists", scene_exists, TARGET_SCENE.as_posix()))

    checkpoint_exists = checkpoint_abs.exists()
    checks.append(Check("new_checkpoint_exists", checkpoint_exists, TARGET_CHECKPOINT.as_posix()))

    old_checkpoint_exists = old_checkpoint_abs.exists()
    checks.append(Check("old_checkpoint_exists", old_checkpoint_exists, OLD_CHECKPOINT.as_posix()))

    scene_checkpoint = None
    if scene_exists:
        scene_checkpoint = _extract_scene_checkpoint(_read_text(scene_abs))

    checks.append(
        Check(
            "scene_binding_points_to_new_checkpoint",
            scene_checkpoint == TARGET_CHECKPOINT.as_posix(),
            {
                "scene_checkpoint": scene_checkpoint,
                "expected": TARGET_CHECKPOINT.as_posix(),
            },
        )
    )

    checks.append(
        Check(
            "old_checkpoint_not_active_in_scene",
            scene_checkpoint != OLD_CHECKPOINT.as_posix(),
            {
                "scene_checkpoint": scene_checkpoint,
                "old_checkpoint": OLD_CHECKPOINT.as_posix(),
            },
        )
    )

    payload: dict[str, Any] | None = None
    payload_load_error = None
    if checkpoint_exists:
        try:
            payload_obj = torch.load(checkpoint_abs, map_location="cpu")
            if isinstance(payload_obj, dict):
                payload = payload_obj
            else:
                payload_load_error = f"checkpoint payload type is {type(payload_obj)!r}, expected dict"
        except Exception as exc:
            payload_load_error = f"checkpoint load failed: {exc}"

    checks.append(Check("checkpoint_payload_loaded", payload is not None, payload_load_error or "ok"))

    checkpoint_stage = None
    checkpoint_scope = None
    strict_load_ok = False
    strict_load_error = None
    strict_missing: list[str] = []
    strict_unexpected: list[str] = []
    inferred_branch_sizes: dict[str, int] = {}

    if payload is not None:
        checkpoint_stage = payload.get("stage")
        checkpoint_scope = payload.get("scope")
        checks.append(
            Check(
                "checkpoint_stage_compatible_with_10D8",
                isinstance(checkpoint_stage, str) and checkpoint_stage.startswith(EXPECTED_STAGE_PREFIX),
                {
                    "checkpoint_stage": checkpoint_stage,
                    "expected_prefix": EXPECTED_STAGE_PREFIX,
                },
            )
        )

        model_state = payload.get("model_state_dict")
        if isinstance(model_state, dict):
            inferred_branch_sizes = _state_dict_branch_sizes(model_state)
            inferred_list = [
                inferred_branch_sizes.get("action_type", -1),
                inferred_branch_sizes.get("move_dir", -1),
                inferred_branch_sizes.get("harvest_dir", -1),
                inferred_branch_sizes.get("return_dir", -1),
                inferred_branch_sizes.get("produce_dir", -1),
                inferred_branch_sizes.get("produce_unit_type", -1),
                inferred_branch_sizes.get("attack_target_local", -1),
            ]
            checks.append(
                Check(
                    "branch_sizes_match_unity_v2_contract",
                    inferred_list == EXPECTED_BRANCH_SIZES,
                    {
                        "actual": inferred_list,
                        "expected": EXPECTED_BRANCH_SIZES,
                    },
                )
            )

            model = build_day3_student_model()
            try:
                missing, unexpected = model.load_state_dict(model_state, strict=True)
                strict_missing = [str(x) for x in list(missing)]
                strict_unexpected = [str(x) for x in list(unexpected)]
                strict_load_ok = len(strict_missing) == 0 and len(strict_unexpected) == 0
            except Exception as exc:
                strict_load_ok = False
                strict_load_error = str(exc)

            checks.append(
                Check(
                    "model_state_dict_strict_load",
                    strict_load_ok,
                    {
                        "missing_keys": strict_missing,
                        "unexpected_keys": strict_unexpected,
                        "error": strict_load_error,
                    },
                )
            )
        else:
            checks.append(
                Check(
                    "model_state_dict_present",
                    False,
                    "checkpoint missing model_state_dict",
                )
            )
            checks.append(
                Check(
                    "branch_sizes_match_unity_v2_contract",
                    False,
                    "cannot infer branch sizes without model_state_dict",
                )
            )
            checks.append(
                Check(
                    "model_state_dict_strict_load",
                    False,
                    "cannot strict-load without model_state_dict",
                )
            )
    else:
        checks.append(
            Check(
                "checkpoint_stage_compatible_with_10D8",
                False,
                "checkpoint payload not available",
            )
        )
        checks.append(
            Check(
                "branch_sizes_match_unity_v2_contract",
                False,
                "checkpoint payload not available",
            )
        )
        checks.append(
            Check(
                "model_state_dict_strict_load",
                False,
                "checkpoint payload not available",
            )
        )

    all_ok = all(c.ok for c in checks)

    report = {
        "stage": "10D.9",
        "task": "checkpoint_binding_verification",
        "generated_at_utc": _utc_now(),
        "status": "pass" if all_ok else "fail",
        "target_scene": TARGET_SCENE.as_posix(),
        "new_checkpoint": TARGET_CHECKPOINT.as_posix(),
        "old_checkpoint": OLD_CHECKPOINT.as_posix(),
        "scene_binding": {
            "path": TARGET_SCENE.as_posix(),
            "field": "_checkpointRelativePath",
            "resolved_value": scene_checkpoint,
        },
        "checkpoint_metadata": {
            "stage": checkpoint_stage,
            "scope": checkpoint_scope,
            "inferred_branch_sizes_by_head": inferred_branch_sizes,
        },
        "strict_load": {
            "ok": strict_load_ok,
            "missing_keys": strict_missing,
            "unexpected_keys": strict_unexpected,
            "error": strict_load_error,
        },
        "checks": [
            {
                "name": c.name,
                "ok": c.ok,
                "details": c.details,
            }
            for c in checks
        ],
        "notes": [
            "No retraining, no PPO, no checkpoint mutation.",
            "Verification is read-only for checkpoint and model contract.",
        ],
        "paths": {
            "scene": _to_rel(repo_root, scene_abs),
            "new_checkpoint": _to_rel(repo_root, checkpoint_abs),
            "old_checkpoint": _to_rel(repo_root, old_checkpoint_abs),
        },
    }

    out_abs = repo_root / OUT_JSON
    out_abs.parent.mkdir(parents=True, exist_ok=True)
    out_abs.write_text(json.dumps(report, ensure_ascii=True, indent=2), encoding="utf-8")

    print(out_abs.as_posix())
    print(f"status={report['status']}")
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
