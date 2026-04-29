#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np
import torch
import torch.nn.functional as F

BRANCH_LAYOUT: List[int] = [6, 4, 4, 4, 4, 7, 49]
OWNER_NEUTRAL_CH = 2
OWNER_PLAYER1_CH = 3
OWNER_PLAYER2_CH = 4
UNIT_RESOURCE_CH = 5
UNIT_BASE_CH = 6
UNIT_BARRACKS_CH = 7
UNIT_WORKER_CH = 8
UNIT_LIGHT_CH = 9
UNIT_HEAVY_CH = 10
UNIT_RANGED_CH = 11
ACTION_NOOP_CH = 12
ACTION_MOVE_CH = 13
ACTION_HARVEST_CH = 14
ACTION_RETURN_CH = 15
ACTION_PRODUCE_CH = 16
ACTION_ATTACK_CH = 17
DIR_NORTH_CH = 18
DIR_EAST_CH = 19
DIR_SOUTH_CH = 20
DIR_WEST_CH = 21
PRODUCE_WORKER_CH = 22
PRODUCE_LIGHT_CH = 23
PRODUCE_HEAVY_CH = 24
PRODUCE_RANGED_CH = 25
ATTACK_TARGET_CH = 26
ACTION_TYPE_NAMES: Dict[int, str] = {
    0: "noop",
    1: "move",
    2: "harvest",
    3: "return",
    4: "produce",
    5: "attack",
}

DEFAULT_OUT_DIR = Path("python/week5_teacher/scripted_bc_overfit")
DEFAULT_DATASET = DEFAULT_OUT_DIR / "minimal_scripted_dataset.npz"
DEFAULT_MANIFEST = DEFAULT_OUT_DIR / "minimal_scripted_dataset_manifest.json"
DEFAULT_VALIDATION = DEFAULT_OUT_DIR / "minimal_scripted_dataset_validation.json"
DEFAULT_CHECKPOINT = DEFAULT_OUT_DIR / "overfit_checkpoint.pt"
DEFAULT_TRAIN_HISTORY = DEFAULT_OUT_DIR / "OVERFIT_TRAIN_HISTORY.json"
DEFAULT_EVAL_REPORT = DEFAULT_OUT_DIR / "OVERFIT_EVAL_REPORT.json"
DEFAULT_OVERFIT_REPORT = DEFAULT_OUT_DIR / "OVERFIT_REPORT.md"
DEFAULT_OVERFIT_SUMMARY = DEFAULT_OUT_DIR / "OVERFIT_REPORT_SUMMARY.json"


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True), encoding="utf-8")


def write_md(path: Path, lines: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")


def bootstrap_paths() -> None:
    here = Path(__file__).resolve()
    week5_dir = here.parent.parent
    root = week5_dir.parent.parent
    gridnet_dir = root / "python" / "week5_teacher_gridnet"
    mask_audit_dir = week5_dir / "mask_audit"
    reward_audit_dir = week5_dir / "reward_audit"
    for candidate in [root, week5_dir, gridnet_dir, mask_audit_dir, reward_audit_dir]:
        raw = str(candidate)
        if raw not in sys.path:
            sys.path.insert(0, raw)


bootstrap_paths()

from gridnet_model import Agent  # noqa: E402
from mask_audit_utils import (  # noqa: E402
    build_full_mask_from_candidates,
    create_runtime_context,
    create_wrapped_env,
    flatten_mask,
    reset_compat,
    step_compat,
)
from reward_audit_utils import (  # noqa: E402
    build_scripted_probe_action,
    flatten_obs,
    to_env_action_shape,
    validate_action_against_mask,
)


def branch_slices() -> List[Tuple[int, int]]:
    out = []
    start = 1
    for size in BRANCH_LAYOUT:
        out.append((start, start + size))
        start += size
    return out


def action_histogram(actions: np.ndarray, actor_valid: np.ndarray) -> Dict[str, int]:
    c = Counter()
    if actions.ndim != 4:
        return {}
    n = int(actions.shape[0])
    h = int(actions.shape[1])
    w = int(actions.shape[2])
    for i in range(n):
        for y in range(h):
            for x in range(w):
                if not bool(actor_valid[i, y, x]):
                    continue
                at = int(actions[i, y, x, 0])
                c[ACTION_TYPE_NAMES.get(at, f"unknown_{at}")] += 1
    return {k: int(v) for k, v in sorted(c.items())}


def flatten_nhwk(x: np.ndarray) -> np.ndarray:
    n, h, w, k = x.shape
    return x.reshape(n * h * w, k)


def flatten_nhw(x: np.ndarray) -> np.ndarray:
    n, h, w = x.shape
    return x.reshape(n * h * w)


def ensure_full_mask(mask_nhwk: np.ndarray) -> np.ndarray:
    if mask_nhwk.ndim != 4:
        raise RuntimeError(f"Expected full mask [N,H,W,79], got {tuple(mask_nhwk.shape)}")
    if int(mask_nhwk.shape[-1]) != 79:
        raise RuntimeError(f"Expected mask depth 79 after reconstruction, got {mask_nhwk.shape[-1]}")
    return mask_nhwk


def fallback_fill_invalid_actions(actions_ncw7: np.ndarray, mask_flat: np.ndarray) -> Tuple[np.ndarray, Dict[str, int]]:
    counters = {
        "fallback_to_valid_count": 0,
        "fallback_to_noop_count": 0,
        "invalid_after_generation_count": 0,
    }
    fixed = np.asarray(actions_ncw7).copy()
    slices = branch_slices()
    n, cells, _ = fixed.shape

    for env_i in range(n):
        for cell in range(cells):
            if mask_flat[env_i, cell, 0] <= 0:
                fixed[env_i, cell, :] = 0
                continue
            for b in range(7):
                s, e = slices[b]
                idx = int(fixed[env_i, cell, b])
                pos = s + idx
                valid = np.where(mask_flat[env_i, cell, s:e] > 0)[0]
                if pos < s or pos >= e or mask_flat[env_i, cell, pos] <= 0:
                    if valid.size > 0:
                        fixed[env_i, cell, b] = int(valid[0])
                        counters["fallback_to_valid_count"] += 1
                    else:
                        fixed[env_i, cell, b] = 0
                        counters["fallback_to_noop_count"] += 1

    counters["invalid_after_generation_count"] = int(validate_action_against_mask(fixed, mask_flat))
    return fixed, counters


def class_presence_from_hist(hist: Dict[str, int]) -> Dict[str, bool]:
    out = {}
    for name in ["noop", "move", "harvest", "return", "produce", "attack"]:
        out[name] = int(hist.get(name, 0)) > 0
    return out


def choose_dataset_decision(validation: Dict[str, Any]) -> str:
    if not validation:
        return "INCONCLUSIVE_NEEDS_MANUAL_CHECK"
    if validation.get("fatal_shape_error"):
        return "FAIL_DATASET_SHAPE"
    if int(validation.get("invalid_action_count", 0)) > 0:
        return "FAIL_DATASET_INVALID_ACTIONS"
    class_presence = validation.get("class_presence", {})
    has_move = bool(class_presence.get("move", False))
    nonnoop_share = float(validation.get("non_noop_share", 0.0))
    if has_move and nonnoop_share > 0.0:
        required = ["move", "harvest", "return", "produce", "attack"]
        missing = [k for k in required if not bool(class_presence.get(k, False))]
        if missing:
            return "PARTIAL_PASS_DATASET_LIMITED_CLASSES"
        return "PASS_DATASET_READY"
    return "INCONCLUSIVE_NEEDS_MANUAL_CHECK"


def mask_argmax(logits: torch.Tensor, mask: torch.Tensor) -> torch.Tensor:
    masked_logits = torch.where(mask > 0, logits, torch.full_like(logits, -1e8))
    return torch.argmax(masked_logits, dim=-1)


def branch_loss(
    logits: torch.Tensor,
    targets: torch.Tensor,
    mask: torch.Tensor,
    active: torch.Tensor,
    class_weights: Optional[torch.Tensor] = None,
) -> torch.Tensor:
    # Keep loss on active cells only and ignore invalid classes via mask.
    if logits.numel() == 0:
        return torch.zeros([], device=logits.device)
    masked_logits = torch.where(mask > 0, logits, torch.full_like(logits, -1e8))
    ce = F.cross_entropy(masked_logits, targets, reduction="none", weight=class_weights)
    denom = torch.clamp(active.float().sum(), min=1.0)
    return (ce * active.float()).sum() / denom


def extract_branch_masks(mask_nhw79: np.ndarray) -> List[np.ndarray]:
    slices = branch_slices()
    out = []
    for s, e in slices:
        out.append(mask_nhw79[:, :, :, s:e])
    return out


def calc_nonnoop_recall(pred_action_type: np.ndarray, gt_action_type: np.ndarray, active: np.ndarray) -> float:
    idx = np.logical_and(active, gt_action_type != 0)
    denom = int(idx.sum())
    if denom <= 0:
        return 1.0
    return float((pred_action_type[idx] == gt_action_type[idx]).sum() / denom)


def per_branch_acc(pred: np.ndarray, gt: np.ndarray, cond: np.ndarray) -> Optional[float]:
    denom = int(cond.sum())
    if denom <= 0:
        return None
    return float((pred[cond] == gt[cond]).sum() / denom)


def load_dataset_npz(path: Path) -> Dict[str, np.ndarray]:
    if not path.is_file():
        raise FileNotFoundError(f"Dataset not found: {path}")
    data = np.load(path, allow_pickle=False)
    out = {k: np.asarray(data[k]) for k in data.files}
    return out


def make_env_once(args: Any) -> Tuple[Any, Any, Any, Dict[str, Any], np.ndarray, Dict[str, Any], Dict[str, Any], List[str]]:
    warnings: List[str] = []
    ctx = create_runtime_context(int(args.seed))
    env, env_for_training, env_summary, _timing = create_wrapped_env(args, ctx)
    obs, info = reset_compat(env_for_training)

    mask_nhwk, mask_source, mask_warn = build_full_mask_from_candidates(env_for_training, obs, infos=[info])
    warnings.extend(mask_warn)
    if mask_nhwk is None:
        raise RuntimeError("Could not retrieve action mask for scripted dataset export.")

    mask_meta = {
        "mask_shape": list(np.asarray(mask_nhwk).shape),
        "mask_source": mask_source,
        "mask_source_depth": int(np.asarray(mask_nhwk).shape[-1]),
        "reconstructed_source_channel": "inferred_source_from_action_type" in str(mask_source),
    }
    return ctx, env, env_for_training, env_summary, np.asarray(obs), info if isinstance(info, dict) else {}, mask_meta, warnings


def to_spatial_action(action_ncw7: np.ndarray, h: int, w: int) -> np.ndarray:
    n = action_ncw7.shape[0]
    return action_ncw7.reshape(n, h, w, 7)
