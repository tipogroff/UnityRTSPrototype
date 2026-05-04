"""Stage10D24 — Mode Isolation and Offline-vs-Live Policy Audit.

Parts:
  A: Heuristic mode isolation verdict (from existing stage10d22 snapshots).
  B: Offline BC validation vs Unity live observation policy comparison.
  C: Checkpoint lineage audit across available student checkpoints.
  D: Selector ablation on captured live logits (diagnostic only).

Outputs:
  reports/stage10d24_mode_isolation_and_offline_live_audit.json
  reports/stage10d24_policy_offline_validation_trace.jsonl
  reports/stage10d24_live_observation_policy_trace.jsonl
  reports/STAGE10D24_MODE_ISOLATION_AND_OFFLINE_LIVE_AUDIT.md

Run from project root with .venv Python:
  .venv\\Scripts\\python.exe python/week6_student/stage10d24_mode_isolation_and_offline_live_audit.py
"""
from __future__ import annotations

import json
import math
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import torch
import torch.nn.functional as F

# ---------------------------------------------------------------------------
# Path setup — allow importing week6_student modules
# ---------------------------------------------------------------------------
_ROOT = Path(__file__).resolve().parents[2]
_WEEK6 = Path(__file__).resolve().parent
if str(_WEEK6) not in sys.path:
    sys.path.insert(0, str(_WEEK6))

from load_student_checkpoint import load_student_transfer_checkpoint  # noqa: E402

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
ACTION_TYPES = ["NoOp", "Move", "Harvest", "Return", "Produce", "Attack"]
ACTION_INDEX = {name: idx for idx, name in enumerate(ACTION_TYPES)}
NUM_ACTIONS = len(ACTION_TYPES)
BRANCH_SIZES = [6, 4, 4, 4, 4, 7, 49]

STUDENT_MODE = "student_live_policy"
HEURISTIC_MODE = "heuristic_baseline"

# Paths
STAGE10D22_DIR = _ROOT / "python/week6_student/tmp/stage10d22_global_lifecycle"
BC_READY_DIR = _ROOT / "python/week6_student/bc_ready"
RUNS_DIR = _ROOT / "python/week6_student/runs"
REPORTS_DIR = _ROOT / "python/week6_student/reports"

STAGE10D14_CHECKPOINT = (
    RUNS_DIR
    / "legacy032_v2_stage10d14_unity_like_augmented_bc_20260503T1455Z"
    / "student_bc_stage10d14_augmented_best.pt"
)

STAGE10D14_BC_READY = (
    BC_READY_DIR
    / "legacy032_3m_unity_v2_stage10d14_unity_like_augmented_bc_ready_20260503T145301Z"
)

CHECKPOINT_LINEAGE: list[dict[str, Any]] = [
    {
        "name": "stage10d14_augmented_best",
        "stage": "10D.14",
        "path": str(
            RUNS_DIR
            / "legacy032_v2_stage10d14_unity_like_augmented_bc_20260503T1455Z"
            / "student_bc_stage10d14_augmented_best.pt"
        ),
        "bc_ready_dir": str(STAGE10D14_BC_READY),
        "is_current": True,
        "selection_json": str(
            RUNS_DIR
            / "legacy032_v2_stage10d14_unity_like_augmented_bc_20260503T1455Z"
            / "stage10d14_training_selection.json"
        ),
    },
    {
        "name": "stage10d17_movement_best",
        "stage": "10D.17",
        "path": str(
            RUNS_DIR
            / "legacy032_v2_stage10d17_movement_augmented_bc_20260503T164734Z"
            / "student_bc_stage10d17_movement_augmented_best.pt"
        ),
        "bc_ready_dir": str(
            BC_READY_DIR / "legacy032_v2_stage10d17_movement_augmented_bc_ready_20260503T162905Z"
        ),
        "is_current": False,
        "selection_json": str(
            RUNS_DIR
            / "legacy032_v2_stage10d17_movement_augmented_bc_20260503T164734Z"
            / "stage10d17_training_selection.json"
        ),
    },
    {
        "name": "stage10d19b_valid_move_best",
        "stage": "10D.19b",
        "path": str(
            RUNS_DIR
            / "legacy032_v2_stage10d19b_valid_move_augmented_bc_20260503T192454Z"
            / "student_bc_stage10d19b_valid_move_best.pt"
        ),
        "bc_ready_dir": str(
            BC_READY_DIR
            / "legacy032_v2_stage10d19b_valid_move_augmented_bc_ready_20260503T191829Z"
        ),
        "is_current": False,
        "selection_json": str(
            RUNS_DIR
            / "legacy032_v2_stage10d19b_valid_move_augmented_bc_20260503T192454Z"
            / "stage10d19b_training_selection.json"
        ),
    },
    {
        "name": "stage10d19c_mask_aware_best",
        "stage": "10D.19c",
        "path": str(
            RUNS_DIR
            / "legacy032_v2_stage10d19c_mask_aware_failure_augmented_bc_20260503T202258Z"
            / "student_bc_stage10d19c_mask_aware_best.pt"
        ),
        "bc_ready_dir": str(
            BC_READY_DIR
            / "legacy032_v2_stage10d19c_mask_aware_failure_augmented_bc_ready_20260503T200935Z"
        ),
        "is_current": False,
        "selection_json": str(
            RUNS_DIR
            / "legacy032_v2_stage10d19c_mask_aware_failure_augmented_bc_20260503T202258Z"
            / "stage10d19c_training_selection.json"
        ),
    },
]


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def _as_bool(v: Any) -> bool:
    if isinstance(v, bool):
        return v
    if isinstance(v, str):
        return v.strip().lower() in {"1", "true", "yes", "y"}
    return bool(v)


def _softmax(logits: list[float]) -> list[float]:
    m = max(logits)
    exps = [math.exp(x - m) for x in logits]
    s = sum(exps)
    return [e / s for e in exps]


def _ranked_actions(logits: list[float]) -> list[tuple[str, int, float]]:
    """Return list of (action_name, rank_1based, probability) sorted by prob desc."""
    probs = _softmax(logits)
    ranked = sorted(enumerate(probs), key=lambda kv: kv[1], reverse=True)
    result = []
    for rank, (idx, prob) in enumerate(ranked, start=1):
        result.append((ACTION_TYPES[idx], rank, prob))
    return result


def _action_rank(logits: list[float], action_name: str) -> tuple[int, float]:
    """Return (rank_1based, probability) for a given action."""
    ranked = _ranked_actions(logits)
    for name, rank, prob in ranked:
        if name == action_name:
            return rank, prob
    return len(ACTION_TYPES), 0.0


def _empty_dist() -> dict[str, int]:
    return {k: 0 for k in ACTION_TYPES}


def _norm_action(v: Any) -> str:
    text = str(v or "").strip()
    if text in ACTION_INDEX:
        return text
    low = text.lower()
    for a in ACTION_TYPES:
        if a.lower() == low:
            return a
    return "NoOp"


# ---------------------------------------------------------------------------
# Part A — Heuristic Mode Isolation
# ---------------------------------------------------------------------------

@dataclass
class HeuristicIsolationResult:
    heuristic_uses_student_checkpoint: bool
    heuristic_checkpoint_path: str
    student_checkpoint_path: str
    checkpoint_paths_identical: bool
    heuristic_adapter_invoked: bool
    student_adapter_invoked: bool
    heuristic_inference_request_count: int
    student_inference_request_count: int
    logits_identical_step1: bool
    actor_logits_identical_step1: bool
    raw_dist_heuristic: dict[str, int]
    raw_dist_student: dict[str, int]
    distributions_identical: bool
    all_row_hashes_identical: bool
    actor_row_hashes_identical: bool
    steps_compared: int
    isolation_verdict: str  # "ISOLATED" | "NOT_ISOLATED" | "UNDETERMINED"
    isolation_failure_evidence: list[str]
    telemetry: dict[str, Any]


def _collect_mode_actor_rows(mode_dir: Path, max_steps: int = 80) -> list[dict[str, Any]]:
    """Collect all friendly-actor rows from cell table files."""
    actor_rows: list[dict[str, Any]] = []
    for step in range(1, max_steps + 1):
        path = mode_dir / f"stage10d10_global_runtime_cell_table_step{step:04d}.jsonl"
        if not path.exists():
            break
        for row in _read_jsonl(path):
            owner = str(row.get("decoded_observation_owner") or "")
            unit_type = str(row.get("decoded_observation_unit_type") or "")
            if "Player1" in owner and unit_type not in ("", "None", "Empty"):
                actor_rows.append(dict(row, _step=step))
    return actor_rows


def run_part_a() -> HeuristicIsolationResult:
    print("[D24 PartA] Heuristic mode isolation audit...")

    h_dir = STAGE10D22_DIR / HEURISTIC_MODE
    s_dir = STAGE10D22_DIR / STUDENT_MODE

    # Load first snapshot for both modes
    h_snap = _read_json(h_dir / "stage10d22_heuristic_baseline_snapshot_step0001.json")
    s_snap = _read_json(s_dir / "stage10d22_student_live_policy_snapshot_step0001.json")

    h_ckpt = str(h_snap.get("checkpoint") or h_snap.get("checkpoint_path_used_at_inference") or "")
    s_ckpt = str(s_snap.get("checkpoint") or s_snap.get("checkpoint_path_used_at_inference") or "")

    h_adapter = _as_bool(h_snap.get("adapter_invoked"))
    s_adapter = _as_bool(s_snap.get("adapter_invoked"))
    h_inf_count = int(h_snap.get("inference_request_count") or 0)
    s_inf_count = int(s_snap.get("inference_request_count") or 0)

    # Compare logits step 1
    h_rows_s1 = _read_jsonl(h_dir / "stage10d10_global_runtime_cell_table_step0001.jsonl")
    s_rows_s1 = _read_jsonl(s_dir / "stage10d10_global_runtime_cell_table_step0001.jsonl")

    # Check if logits_snapshot has adapter_invoked (some snapshots store it differently)
    h_logits_snap = _read_json(h_dir / "stage10d10_global_runtime_logits_snapshot_step0001.json")
    s_logits_snap = _read_json(s_dir / "stage10d10_global_runtime_logits_snapshot_step0001.json")
    if not h_adapter:
        h_adapter = _as_bool(h_logits_snap.get("adapter_invoked"))
    if not s_adapter:
        s_adapter = _as_bool(s_logits_snap.get("adapter_invoked"))
    if h_inf_count == 0:
        h_inf_count = int(h_logits_snap.get("inference_request_count") or 0)
    if s_inf_count == 0:
        s_inf_count = int(s_logits_snap.get("inference_request_count") or 0)

    # Extract logits
    h_logits_r0 = h_rows_s1[0].get("action_type_logits", []) if h_rows_s1 else []
    s_logits_r0 = s_rows_s1[0].get("action_type_logits", []) if s_rows_s1 else []
    logits_identical_step1 = h_logits_r0 == s_logits_r0

    # Compare actor rows
    h_actors = [r for r in h_rows_s1 if "Player1" in str(r.get("decoded_observation_owner", ""))
                and str(r.get("decoded_observation_unit_type", "")) not in ("", "None", "Empty")]
    s_actors = [r for r in s_rows_s1 if "Player1" in str(r.get("decoded_observation_owner", ""))
                and str(r.get("decoded_observation_unit_type", "")) not in ("", "None", "Empty")]
    actor_logits_identical = False
    if h_actors and s_actors and len(h_actors) == len(s_actors):
        actor_logits_identical = all(
            h_actors[i].get("action_type_logits") == s_actors[i].get("action_type_logits")
            for i in range(len(h_actors))
        )

    # Aggregate raw distributions across all steps
    raw_dist_h = _empty_dist()
    raw_dist_s = _empty_dist()
    h_all_hashes: list[str] = []
    s_all_hashes: list[str] = []
    h_actor_hashes: list[str] = []
    s_actor_hashes: list[str] = []
    steps_compared = 0

    for step in range(1, 81):
        h_path = h_dir / f"stage10d10_global_runtime_cell_table_step{step:04d}.jsonl"
        s_path = s_dir / f"stage10d10_global_runtime_cell_table_step{step:04d}.jsonl"
        if not h_path.exists() or not s_path.exists():
            break
        steps_compared += 1
        h_rows = _read_jsonl(h_path)
        s_rows = _read_jsonl(s_path)

        for row in h_rows:
            raw_dist_h[_norm_action(row.get("raw_action_type_top1"))] += 1
            key = json.dumps([
                row.get("cell_index"), row.get("action_type_logits"),
                row.get("raw_action_type_top1"),
            ], sort_keys=True)
            h_all_hashes.append(key)
            if "Player1" in str(row.get("decoded_observation_owner", "")) and \
               str(row.get("decoded_observation_unit_type", "")) not in ("", "None", "Empty"):
                h_actor_hashes.append(key)

        for row in s_rows:
            raw_dist_s[_norm_action(row.get("raw_action_type_top1"))] += 1
            key = json.dumps([
                row.get("cell_index"), row.get("action_type_logits"),
                row.get("raw_action_type_top1"),
            ], sort_keys=True)
            s_all_hashes.append(key)
            if "Player1" in str(row.get("decoded_observation_owner", "")) and \
               str(row.get("decoded_observation_unit_type", "")) not in ("", "None", "Empty"):
                s_actor_hashes.append(key)

    all_rows_identical = h_all_hashes == s_all_hashes
    actor_rows_identical = h_actor_hashes == s_actor_hashes
    dist_identical = raw_dist_h == raw_dist_s
    ckpt_identical = (h_ckpt == s_ckpt) and bool(h_ckpt)

    # Check whether heuristic checkpoint path appears to be a student checkpoint path
    h_ckpt_is_student = "student_bc" in h_ckpt.lower() or "stage10d" in h_ckpt.lower()
    heuristic_uses_student_checkpoint = ckpt_identical and h_ckpt_is_student

    # Collect failure evidence
    failure_evidence: list[str] = []
    if ckpt_identical:
        failure_evidence.append(
            f"checkpoint_path_identical=true: both modes use '{h_ckpt}'"
        )
    if h_ckpt_is_student:
        failure_evidence.append("heuristic_checkpoint_path contains 'student_bc': student model loaded in heuristic mode")
    if h_adapter:
        failure_evidence.append(f"heuristic_adapter_invoked=true (inference_count={h_inf_count})")
    if logits_identical_step1:
        failure_evidence.append("action_type_logits identical at step=1 row=0")
    if actor_logits_identical:
        failure_evidence.append("actor cell logits identical at step=1")
    if all_rows_identical:
        failure_evidence.append(f"all raw row hashes identical across {steps_compared} steps")
    if actor_rows_identical:
        failure_evidence.append(f"actor row hashes identical across {steps_compared} steps")

    isolation_verdict: str
    if failure_evidence:
        isolation_verdict = "NOT_ISOLATED"
    elif h_ckpt and not h_ckpt_is_student and not h_adapter and not logits_identical_step1:
        isolation_verdict = "ISOLATED"
    else:
        isolation_verdict = "UNDETERMINED"

    telemetry = {
        "mode": HEURISTIC_MODE,
        "policy_source": "student_checkpoint" if heuristic_uses_student_checkpoint else "unknown",
        "inference_source": "python_adapter" if h_adapter else "none_recorded",
        "uses_student_checkpoint": heuristic_uses_student_checkpoint,
        "uses_python_adapter": h_adapter,
        "uses_heuristic_policy": not heuristic_uses_student_checkpoint,
        "uses_scripted_injection": False,
        "action_buffer_source": "student_inference_logits" if heuristic_uses_student_checkpoint else "heuristic_direct",
        "checkpoint_path_in_snapshot": h_ckpt,
        "student_checkpoint_path": s_ckpt,
        "adapter_invoked_in_snapshot": h_adapter,
        "inference_request_count_in_snapshot": h_inf_count,
    }

    return HeuristicIsolationResult(
        heuristic_uses_student_checkpoint=heuristic_uses_student_checkpoint,
        heuristic_checkpoint_path=h_ckpt,
        student_checkpoint_path=s_ckpt,
        checkpoint_paths_identical=ckpt_identical,
        heuristic_adapter_invoked=h_adapter,
        student_adapter_invoked=s_adapter,
        heuristic_inference_request_count=h_inf_count,
        student_inference_request_count=s_inf_count,
        logits_identical_step1=logits_identical_step1,
        actor_logits_identical_step1=actor_logits_identical,
        raw_dist_heuristic=raw_dist_h,
        raw_dist_student=raw_dist_s,
        distributions_identical=dist_identical,
        all_row_hashes_identical=all_rows_identical,
        actor_row_hashes_identical=actor_rows_identical,
        steps_compared=steps_compared,
        isolation_verdict=isolation_verdict,
        isolation_failure_evidence=failure_evidence,
        telemetry=telemetry,
    )


# ---------------------------------------------------------------------------
# Part B — Offline BC validation inference
# ---------------------------------------------------------------------------

@dataclass
class OfflineValidationResult:
    checkpoint_path: str
    bc_ready_dir: str
    num_samples: int
    num_actor_cells: int
    label_distribution: dict[str, int]
    predicted_top1_distribution: dict[str, int]
    move_label_count: int
    move_predicted_top1_count: int
    attack_label_count: int
    attack_predicted_top1_count: int
    per_class_precision: dict[str, float]
    per_class_recall: dict[str, float]
    confusion_matrix: list[list[int]]  # [true][predicted]
    avg_move_rank: float
    avg_attack_rank: float
    avg_move_prob: float
    avg_attack_prob: float
    move_rank_distribution: dict[str, int]
    attack_rank_distribution: dict[str, int]
    checkpoint_epoch: int | None
    checkpoint_metrics_summary: dict[str, Any]


def _run_offline_validation(
    checkpoint_path: str,
    bc_ready_dir: str,
    *,
    max_samples: int = 8985,
    batch_size: int = 64,
    actor_only: bool = True,
) -> OfflineValidationResult:
    """Run offline BC validation with the given checkpoint on bc_validation.npz."""
    ckpt_p = Path(checkpoint_path)
    bc_p = Path(bc_ready_dir)

    model, meta = load_student_transfer_checkpoint(str(ckpt_p), device="cpu")
    model.eval()

    val_npz = np.load(str(bc_p / "bc_validation.npz"), allow_pickle=False)
    obs = val_npz["observations"]        # (N, 576, 27)
    acts = val_npz["target_action_branches"] if "target_action_branches" in val_npz else val_npz["actions"]  # (N, 576, 7)

    N = min(len(obs), max_samples)
    obs = obs[:N]
    acts = acts[:N]

    # action_type labels are branch 0
    # obs shape is (N, 576, 27) → need to reshape to (N, 24, 24, 27)
    obs_4d = obs.reshape(N, 24, 24, 27)

    label_dist = _empty_dist()
    pred_top1_dist = _empty_dist()
    confusion = [[0] * NUM_ACTIONS for _ in range(NUM_ACTIONS)]
    true_pos = {k: 0 for k in ACTION_TYPES}
    false_pos = {k: 0 for k in ACTION_TYPES}
    false_neg = {k: 0 for k in ACTION_TYPES}

    move_rank_sum = 0.0
    move_prob_sum = 0.0
    move_rank_count = 0
    attack_rank_sum = 0.0
    attack_prob_sum = 0.0
    attack_rank_count = 0
    move_rank_hist: dict[str, int] = {str(i): 0 for i in range(1, NUM_ACTIONS + 1)}
    attack_rank_hist: dict[str, int] = {str(i): 0 for i in range(1, NUM_ACTIONS + 1)}

    actor_cell_count = 0
    total_cells_processed = 0

    for batch_start in range(0, N, batch_size):
        batch_end = min(batch_start + batch_size, N)
        obs_batch = torch.from_numpy(obs_4d[batch_start:batch_end]).float()  # (B, 24, 24, 27)
        acts_batch = acts[batch_start:batch_end].astype(np.int64)             # (B, 576, 7)

        with torch.no_grad():
            logits_dict = model(obs_batch)

        at_logits = logits_dict["action_type_logits"]  # (B, 576, 6)
        at_logits_np = at_logits.cpu().numpy()        # (B, 576, 6)
        at_labels_np = acts_batch[:, :, 0]           # (B, 576)

        B_sz = batch_end - batch_start
        for b in range(B_sz):
            for cell in range(576):
                label_idx = int(at_labels_np[b, cell])
                logits_cell = at_logits_np[b, cell].tolist()
                pred_idx = int(np.argmax(at_logits_np[b, cell]))

                # Only count actor cells (label != 0 → non-NoOp label)
                is_actor = label_idx != 0
                if actor_only and not is_actor:
                    continue
                total_cells_processed += 1
                if is_actor:
                    actor_cell_count += 1

                label_name = ACTION_TYPES[label_idx] if label_idx < NUM_ACTIONS else "NoOp"
                pred_name = ACTION_TYPES[pred_idx]

                label_dist[label_name] += 1
                pred_top1_dist[pred_name] += 1
                confusion[label_idx][pred_idx] += 1

                if label_idx == pred_idx:
                    true_pos[label_name] += 1
                else:
                    false_neg[label_name] += 1
                    false_pos[pred_name] += 1

                # Move/Attack rank stats — on all actor cells
                if is_actor:
                    probs = _softmax(logits_cell)
                    ranked = sorted(enumerate(probs), key=lambda kv: kv[1], reverse=True)
                    move_rank = next((r + 1 for r, (idx, _) in enumerate(ranked) if idx == ACTION_INDEX["Move"]), NUM_ACTIONS)
                    attack_rank = next((r + 1 for r, (idx, _) in enumerate(ranked) if idx == ACTION_INDEX["Attack"]), NUM_ACTIONS)
                    move_prob = probs[ACTION_INDEX["Move"]]
                    attack_prob = probs[ACTION_INDEX["Attack"]]

                    move_rank_sum += move_rank
                    move_prob_sum += move_prob
                    move_rank_count += 1
                    attack_rank_sum += attack_rank
                    attack_prob_sum += attack_prob
                    attack_rank_count += 1

                    move_rank_hist[str(min(move_rank, NUM_ACTIONS))] = move_rank_hist.get(str(min(move_rank, NUM_ACTIONS)), 0) + 1
                    attack_rank_hist[str(min(attack_rank, NUM_ACTIONS))] = attack_rank_hist.get(str(min(attack_rank, NUM_ACTIONS)), 0) + 1

    # Compute precision/recall
    precision: dict[str, float] = {}
    recall: dict[str, float] = {}
    for a in ACTION_TYPES:
        tp = true_pos[a]
        fp = false_pos[a]
        fn = false_neg[a]
        precision[a] = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall[a] = tp / (tp + fn) if (tp + fn) > 0 else 0.0

    avg_move_rank = move_rank_sum / move_rank_count if move_rank_count > 0 else float("nan")
    avg_attack_rank = attack_rank_sum / attack_rank_count if attack_rank_count > 0 else float("nan")
    avg_move_prob = move_prob_sum / move_rank_count if move_rank_count > 0 else float("nan")
    avg_attack_prob = attack_prob_sum / attack_rank_count if attack_rank_count > 0 else float("nan")

    return OfflineValidationResult(
        checkpoint_path=checkpoint_path,
        bc_ready_dir=bc_ready_dir,
        num_samples=N,
        num_actor_cells=actor_cell_count,
        label_distribution=label_dist,
        predicted_top1_distribution=pred_top1_dist,
        move_label_count=label_dist["Move"],
        move_predicted_top1_count=pred_top1_dist["Move"],
        attack_label_count=label_dist["Attack"],
        attack_predicted_top1_count=pred_top1_dist["Attack"],
        per_class_precision=precision,
        per_class_recall=recall,
        confusion_matrix=confusion,
        avg_move_rank=avg_move_rank,
        avg_attack_rank=avg_attack_rank,
        avg_move_prob=avg_move_prob,
        avg_attack_prob=avg_attack_prob,
        move_rank_distribution=move_rank_hist,
        attack_rank_distribution=attack_rank_hist,
        checkpoint_epoch=meta.get("epoch"),
        checkpoint_metrics_summary={
            k: v for k, v in meta.get("metrics", {}).items()
            if "action_type" in k or "recall" in k or "accuracy" in k or "loss" in k
        },
    )


# ---------------------------------------------------------------------------
# Part B — Live observation policy audit
# ---------------------------------------------------------------------------

@dataclass
class LiveObservationResult:
    mode: str
    steps_processed: int
    total_cells: int
    friendly_actor_cells: int
    predicted_top1_distribution: dict[str, int]
    move_top1: int
    move_top2: int
    move_top3: int
    attack_top1: int
    attack_top2: int
    attack_top3: int
    avg_move_rank: float
    avg_move_prob: float
    avg_attack_rank: float
    avg_attack_prob: float
    move_legal_not_selected: int
    attack_legal_not_selected: int
    per_step_actor_counts: list[int]


def run_part_b_live(mode: str = STUDENT_MODE) -> LiveObservationResult:
    print(f"[D24 PartB-Live] Analyzing live observations from mode={mode}...")
    mode_dir = STAGE10D22_DIR / mode

    pred_dist = _empty_dist()
    move_top1 = move_top2 = move_top3 = 0
    attack_top1 = attack_top2 = attack_top3 = 0
    move_rank_sum = move_prob_sum = 0.0
    attack_rank_sum = attack_prob_sum = 0.0
    total_cells = 0
    actor_cells = 0
    move_legal_not_selected = 0
    attack_legal_not_selected = 0
    per_step_actor_counts: list[int] = []
    steps_processed = 0

    for step in range(1, 81):
        path = mode_dir / f"stage10d10_global_runtime_cell_table_step{step:04d}.jsonl"
        if not path.exists():
            break
        rows = _read_jsonl(path)
        steps_processed += 1
        step_actors = 0

        for row in rows:
            total_cells += 1
            owner = str(row.get("decoded_observation_owner") or "")
            unit_type = str(row.get("decoded_observation_unit_type") or "")
            is_actor = "Player1" in owner and unit_type not in ("", "None", "Empty")

            if not is_actor:
                continue

            actor_cells += 1
            step_actors += 1

            raw_top1 = _norm_action(row.get("raw_action_type_top1"))
            pred_dist[raw_top1] += 1

            logits = row.get("action_type_logits", [])
            if logits and len(logits) >= NUM_ACTIONS:
                probs = _softmax([float(x) for x in logits])
                ranked = sorted(enumerate(probs), key=lambda kv: kv[1], reverse=True)
                idx_to_rank = {idx: r + 1 for r, (idx, _) in enumerate(ranked)}

                move_rank = idx_to_rank.get(ACTION_INDEX["Move"], NUM_ACTIONS)
                attack_rank = idx_to_rank.get(ACTION_INDEX["Attack"], NUM_ACTIONS)
                move_prob = probs[ACTION_INDEX["Move"]]
                attack_prob = probs[ACTION_INDEX["Attack"]]

                move_rank_sum += move_rank
                move_prob_sum += move_prob
                attack_rank_sum += attack_rank
                attack_prob_sum += attack_prob

                if move_rank == 1:
                    move_top1 += 1
                elif move_rank == 2:
                    move_top2 += 1
                elif move_rank == 3:
                    move_top3 += 1

                if attack_rank == 1:
                    attack_top1 += 1
                elif attack_rank == 2:
                    attack_top2 += 1
                elif attack_rank == 3:
                    attack_top3 += 1

            # Legal but not selected
            mask = row.get("legal_action_type_mask", [])
            if mask and len(mask) >= NUM_ACTIONS:
                move_legal = _as_bool(mask[ACTION_INDEX["Move"]])
                attack_legal = _as_bool(mask[ACTION_INDEX["Attack"]])
                if move_legal and raw_top1 != "Move":
                    move_legal_not_selected += 1
                if attack_legal and raw_top1 != "Attack":
                    attack_legal_not_selected += 1

        per_step_actor_counts.append(step_actors)

    avg_move_rank = move_rank_sum / actor_cells if actor_cells > 0 else float("nan")
    avg_attack_rank = attack_rank_sum / actor_cells if actor_cells > 0 else float("nan")
    avg_move_prob = move_prob_sum / actor_cells if actor_cells > 0 else float("nan")
    avg_attack_prob = attack_prob_sum / actor_cells if actor_cells > 0 else float("nan")

    return LiveObservationResult(
        mode=mode,
        steps_processed=steps_processed,
        total_cells=total_cells,
        friendly_actor_cells=actor_cells,
        predicted_top1_distribution=pred_dist,
        move_top1=move_top1,
        move_top2=move_top2,
        move_top3=move_top3,
        attack_top1=attack_top1,
        attack_top2=attack_top2,
        attack_top3=attack_top3,
        avg_move_rank=avg_move_rank,
        avg_move_prob=avg_move_prob,
        avg_attack_rank=avg_attack_rank,
        avg_attack_prob=avg_attack_prob,
        move_legal_not_selected=move_legal_not_selected,
        attack_legal_not_selected=attack_legal_not_selected,
        per_step_actor_counts=per_step_actor_counts,
    )


# ---------------------------------------------------------------------------
# Part C — Checkpoint lineage audit
# ---------------------------------------------------------------------------

@dataclass
class CheckpointLineageEntry:
    name: str
    stage: str
    checkpoint_path: str
    checkpoint_exists: bool
    is_current: bool
    bc_ready_dir: str
    bc_ready_exists: bool
    selection_json_exists: bool
    selection_epoch: int | None
    # From selection JSON if available
    val_total_loss: float | None
    val_action_type_loss: float | None
    val_actor_cell_action_type_accuracy: float | None
    val_actor_cell_non_noop_recall: float | None
    val_attack_proxy_count: int | None
    val_attack_proxy_accuracy: float | None
    train_attack_proxy_count: int | None
    train_attack_proxy_accuracy: float | None
    # From offline validation (if bc_ready exists + checkpoint exists)
    offline: OfflineValidationResult | None
    offline_error: str | None


def run_part_c() -> list[CheckpointLineageEntry]:
    print("[D24 PartC] Checkpoint lineage audit...")
    results: list[CheckpointLineageEntry] = []

    for ckpt_info in CHECKPOINT_LINEAGE:
        name = ckpt_info["name"]
        print(f"  Auditing checkpoint: {name}")
        ckpt_path = ckpt_info["path"]
        bc_dir = ckpt_info["bc_ready_dir"]
        sel_path = ckpt_info["selection_json"]

        ckpt_exists = Path(ckpt_path).exists()
        bc_exists = Path(bc_dir).exists()
        sel_exists = Path(sel_path).exists()

        sel_epoch = None
        val_total_loss = None
        val_action_type_loss = None
        val_accuracy = None
        val_recall = None
        val_attack_count = None
        val_attack_acc = None
        train_attack_count = None
        train_attack_acc = None

        if sel_exists:
            sel = _read_json(Path(sel_path))
            sel_epoch = sel.get("selected_epoch")
            bm = sel.get("best_metrics", {})
            if bm:
                val_total_loss = bm.get("val_total_loss")
                val_action_type_loss = bm.get("val_action_type_loss")
                val_accuracy = bm.get("val_actor_cell_action_type_accuracy")
                val_recall = bm.get("val_actor_cell_non_noop_recall")
                val_attack_count = bm.get("val_attack_proxy_count")
                val_attack_acc = bm.get("val_attack_proxy_accuracy")
                train_attack_count = bm.get("train_attack_proxy_count")
                train_attack_acc = bm.get("train_attack_proxy_accuracy")

        # Run offline validation if resources available
        offline_result = None
        offline_error = None
        if ckpt_exists and bc_exists and (Path(bc_dir) / "bc_validation.npz").exists():
            try:
                offline_result = _run_offline_validation(ckpt_path, bc_dir)
            except Exception as exc:
                offline_error = str(exc)
                print(f"    Offline validation error for {name}: {exc}")
        else:
            if not ckpt_exists:
                offline_error = f"checkpoint_not_found: {ckpt_path}"
            elif not bc_exists:
                offline_error = f"bc_ready_dir_not_found: {bc_dir}"
            else:
                offline_error = "bc_validation.npz_not_found"

        results.append(CheckpointLineageEntry(
            name=name,
            stage=ckpt_info["stage"],
            checkpoint_path=ckpt_path,
            checkpoint_exists=ckpt_exists,
            is_current=ckpt_info["is_current"],
            bc_ready_dir=bc_dir,
            bc_ready_exists=bc_exists,
            selection_json_exists=sel_exists,
            selection_epoch=sel_epoch,
            val_total_loss=val_total_loss,
            val_action_type_loss=val_action_type_loss,
            val_actor_cell_action_type_accuracy=val_accuracy,
            val_actor_cell_non_noop_recall=val_recall,
            val_attack_proxy_count=val_attack_count,
            val_attack_proxy_accuracy=val_attack_acc,
            train_attack_proxy_count=train_attack_count,
            train_attack_proxy_accuracy=train_attack_acc,
            offline=offline_result,
            offline_error=offline_error,
        ))

    return results


# ---------------------------------------------------------------------------
# Part D — Selector ablation on live logits
# ---------------------------------------------------------------------------

@dataclass
class SelectorAblationResult:
    selector_name: str
    description: str
    predicted_distribution: dict[str, int]
    move_count: int
    attack_count: int
    noop_count: int
    invalid_masked_count: int
    total_actor_cells: int
    move_share: float
    attack_share: float


def _sample_categorical(probs: list[float]) -> int:
    r = float(np.random.rand())
    cum = 0.0
    for i, p in enumerate(probs):
        cum += p
        if r < cum:
            return i
    return len(probs) - 1


def run_part_d(live_result: LiveObservationResult) -> list[SelectorAblationResult]:
    """Selector ablation on live logits from stage10d22 cell tables."""
    print("[D24 PartD] Selector ablation on live logits...")

    # Collect all actor cell logits and masks from stage10d22
    actor_logits_list: list[list[float]] = []
    actor_masks_list: list[list[bool]] = []

    mode_dir = STAGE10D22_DIR / STUDENT_MODE
    for step in range(1, 81):
        path = mode_dir / f"stage10d10_global_runtime_cell_table_step{step:04d}.jsonl"
        if not path.exists():
            break
        for row in _read_jsonl(path):
            owner = str(row.get("decoded_observation_owner") or "")
            unit_type = str(row.get("decoded_observation_unit_type") or "")
            if "Player1" not in owner or unit_type in ("", "None", "Empty"):
                continue
            logits = row.get("action_type_logits", [])
            if not logits or len(logits) < NUM_ACTIONS:
                continue
            mask_raw = row.get("legal_action_type_mask", [])
            if mask_raw and len(mask_raw) >= NUM_ACTIONS:
                mask = [_as_bool(mask_raw[i]) for i in range(NUM_ACTIONS)]
            else:
                mask = [True] * NUM_ACTIONS
            actor_logits_list.append([float(x) for x in logits[:NUM_ACTIONS]])
            actor_masks_list.append(mask)

    total = len(actor_logits_list)
    if total == 0:
        return []

    selectors: list[tuple[str, str]] = [
        ("greedy_argmax", "Greedy argmax over all action logits, no mask"),
        ("legal_masked_argmax", "Argmax over legal actions only (illegal masked to -inf)"),
        ("topk_sampling_legal", "Top-k (k=3) sampling among legal actions by prob"),
        ("temperature_sampling_legal", "Temperature (T=1.0) sampling among legal actions"),
    ]

    ablation_results: list[SelectorAblationResult] = []

    np.random.seed(42)
    for sel_name, sel_desc in selectors:
        dist = _empty_dist()
        invalid_count = 0

        for logits, mask in zip(actor_logits_list, actor_masks_list):
            chosen: int

            if sel_name == "greedy_argmax":
                chosen = int(np.argmax(logits))

            elif sel_name == "legal_masked_argmax":
                masked = [logits[i] if mask[i] else float("-inf") for i in range(NUM_ACTIONS)]
                max_val = max(masked)
                if max_val == float("-inf"):
                    chosen = 0  # fallback to NoOp
                    invalid_count += 1
                else:
                    chosen = int(np.argmax(masked))

            elif sel_name == "topk_sampling_legal":
                k = 3
                legal_indices = [i for i, m in enumerate(mask) if m]
                if not legal_indices:
                    chosen = 0
                    invalid_count += 1
                else:
                    legal_logits = [(i, logits[i]) for i in legal_indices]
                    legal_logits.sort(key=lambda x: x[1], reverse=True)
                    topk = legal_logits[:k]
                    topk_logit_vals = [x[1] for x in topk]
                    topk_probs = _softmax(topk_logit_vals)
                    sampled_k = _sample_categorical(topk_probs)
                    chosen = topk[sampled_k][0]

            elif sel_name == "temperature_sampling_legal":
                T = 1.0
                legal_indices = [i for i, m in enumerate(mask) if m]
                if not legal_indices:
                    chosen = 0
                    invalid_count += 1
                else:
                    legal_logits_vals = [logits[i] / T for i in legal_indices]
                    probs = _softmax(legal_logits_vals)
                    sampled_k = _sample_categorical(probs)
                    chosen = legal_indices[sampled_k]

            else:
                chosen = 0

            dist[ACTION_TYPES[chosen]] += 1

        ablation_results.append(SelectorAblationResult(
            selector_name=sel_name,
            description=sel_desc,
            predicted_distribution=dict(dist),
            move_count=dist["Move"],
            attack_count=dist["Attack"],
            noop_count=dist["NoOp"],
            invalid_masked_count=invalid_count,
            total_actor_cells=total,
            move_share=dist["Move"] / total if total > 0 else 0.0,
            attack_share=dist["Attack"] / total if total > 0 else 0.0,
        ))

    return ablation_results


# ---------------------------------------------------------------------------
# Offline-vs-Live Comparison Table
# ---------------------------------------------------------------------------

def _build_comparison_table(
    offline: OfflineValidationResult,
    live: LiveObservationResult,
) -> list[dict[str, Any]]:
    actor_n = live.friendly_actor_cells if live.friendly_actor_cells > 0 else 1
    rows = []
    for action in ACTION_TYPES:
        off_label = offline.label_distribution.get(action, 0)
        off_pred = offline.predicted_top1_distribution.get(action, 0)
        live_pred = live.predicted_top1_distribution.get(action, 0)
        off_avg_prob = offline.avg_move_prob if action == "Move" else (offline.avg_attack_prob if action == "Attack" else None)
        live_avg_prob = live.avg_move_prob if action == "Move" else (live.avg_attack_prob if action == "Attack" else None)
        off_avg_rank = offline.avg_move_rank if action == "Move" else (offline.avg_attack_rank if action == "Attack" else None)
        live_avg_rank = live.avg_move_rank if action == "Move" else (live.avg_attack_rank if action == "Attack" else None)
        rows.append({
            "action": action,
            "offline_label_count": off_label,
            "offline_predicted_top1_count": off_pred,
            "live_predicted_top1_count": live_pred,
            "offline_avg_probability": round(off_avg_prob, 6) if off_avg_prob is not None and not math.isnan(off_avg_prob) else None,
            "live_avg_probability": round(live_avg_prob, 6) if live_avg_prob is not None and not math.isnan(live_avg_prob) else None,
            "offline_avg_rank": round(off_avg_rank, 3) if off_avg_rank is not None and not math.isnan(off_avg_rank) else None,
            "live_avg_rank": round(live_avg_rank, 3) if live_avg_rank is not None and not math.isnan(live_avg_rank) else None,
        })
    return rows


# ---------------------------------------------------------------------------
# Decision logic
# ---------------------------------------------------------------------------

def _make_go_nogo_recommendation(
    offline: OfflineValidationResult,
    live: LiveObservationResult,
    part_a: HeuristicIsolationResult,
    lineage: list[CheckpointLineageEntry],
) -> dict[str, Any]:
    """Apply decision logic from the spec."""
    decisions: list[str] = []
    reasoning: list[str] = []

    off_move_top1 = offline.move_predicted_top1_count
    off_move_label = offline.move_label_count
    live_move_top1 = live.move_top1
    live_move_top2 = live.move_top2
    live_move_top3 = live.move_top3
    off_attack_top1 = offline.attack_predicted_top1_count
    off_attack_label = offline.attack_label_count
    live_attack_top1 = live.attack_top1

    # Decision 1: Offline Move prediction
    if off_move_label > 0 and off_move_top1 == 0:
        decisions.append("RETRAIN_OR_ADJUST_BC_OBJECTIVE")
        reasoning.append(
            f"Offline Move top1=0 despite Move_label={off_move_label}: suspect class imbalance or BC objective suppression of Move."
        )
    elif off_move_label > 0 and off_move_top1 > 0 and live_move_top1 == 0:
        decisions.append("FIX_OBSERVATION_DOMAIN_MISMATCH")
        reasoning.append(
            f"Offline Move top1={off_move_top1} > 0 but Unity live Move top1=0: suspect observation/domain mismatch."
        )
    elif off_move_label == 0:
        decisions.append("RETRAIN_OR_ADJUST_BC_OBJECTIVE")
        reasoning.append(
            "BC validation dataset has zero Move labels: model cannot learn Move from this data."
        )

    # Decision 2: Move rank
    live_move_top23 = live_move_top2 + live_move_top3
    if live_move_top1 == 0 and live_move_top23 > 0:
        decisions.append("TEST_NON_GREEDY_SELECTOR")
        reasoning.append(
            f"Move appears as top2/top3 {live_move_top23} times live but never top1: "
            "greedy argmax may be suppressing Move due to NoOp/Harvest dominance."
        )

    # Decision 3: Heuristic wiring
    if part_a.isolation_verdict == "NOT_ISOLATED":
        decisions.append("FIX_HEURISTIC_MODE_WIRING")
        reasoning.append(
            "Heuristic baseline is NOT isolated: it uses the student checkpoint. "
            "Heuristic comparison is invalid until isolation is fixed."
        )

    # Decision 4: Checkpoint lineage
    current_entry = next((e for e in lineage if e.is_current), None)
    better_entries = [e for e in lineage if not e.is_current and e.offline is not None]
    if current_entry and current_entry.offline:
        cur_off = current_entry.offline
        for alt in better_entries:
            if alt.offline and alt.offline.move_predicted_top1_count > cur_off.move_predicted_top1_count:
                decisions.append("SWITCH_CHECKPOINT")
                reasoning.append(
                    f"Checkpoint {alt.name} predicts Move top1={alt.offline.move_predicted_top1_count} "
                    f"> current {cur_off.move_predicted_top1_count}: consider switching."
                )
                break

    if not decisions:
        decisions.append("CONTINUE_WITH_CURRENT_CHECKPOINT")
        reasoning.append("No clear signal to switch checkpoint or retrain.")

    # Deduplicate
    decisions = list(dict.fromkeys(decisions))

    return {
        "decisions": decisions,
        "reasoning": reasoning,
        "offline_move_label_count": off_move_label,
        "offline_move_top1_count": off_move_top1,
        "live_move_top1": live_move_top1,
        "live_move_top2": live_move_top2,
        "live_move_top3": live_move_top3,
        "offline_attack_label_count": off_attack_label,
        "offline_attack_top1_count": off_attack_top1,
        "live_attack_top1": live_attack_top1,
        "heuristic_isolation_verdict": part_a.isolation_verdict,
    }


# ---------------------------------------------------------------------------
# Serialization helpers
# ---------------------------------------------------------------------------

def _nan_safe(v: Any) -> Any:
    if isinstance(v, float) and math.isnan(v):
        return None
    return v


def _dataclass_to_dict(obj: Any) -> Any:
    if isinstance(obj, (int, str, bool, type(None))):
        return obj
    if isinstance(obj, float):
        return _nan_safe(obj)
    if isinstance(obj, list):
        return [_dataclass_to_dict(x) for x in obj]
    if isinstance(obj, dict):
        return {k: _dataclass_to_dict(v) for k, v in obj.items()}
    if hasattr(obj, "__dataclass_fields__"):
        return {k: _dataclass_to_dict(getattr(obj, k)) for k in obj.__dataclass_fields__}
    return obj


# ---------------------------------------------------------------------------
# Report writers
# ---------------------------------------------------------------------------

def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def _generate_live_trace_jsonl(live_result: LiveObservationResult) -> list[dict[str, Any]]:
    """Re-read actor rows and emit trace rows for the JSONL output."""
    trace_rows: list[dict[str, Any]] = []
    mode_dir = STAGE10D22_DIR / STUDENT_MODE
    for step in range(1, live_result.steps_processed + 1):
        path = mode_dir / f"stage10d10_global_runtime_cell_table_step{step:04d}.jsonl"
        if not path.exists():
            break
        for row in _read_jsonl(path):
            owner = str(row.get("decoded_observation_owner") or "")
            unit_type = str(row.get("decoded_observation_unit_type") or "")
            if "Player1" not in owner or unit_type in ("", "None", "Empty"):
                continue
            logits = [float(x) for x in (row.get("action_type_logits") or [])]
            probs = _softmax(logits) if len(logits) >= NUM_ACTIONS else []
            if probs:
                ranked = sorted(enumerate(probs), key=lambda kv: kv[1], reverse=True)
                move_rank, move_prob = next(((r + 1, probs[ACTION_INDEX["Move"]]) for r, (i, _) in enumerate(ranked) if i == ACTION_INDEX["Move"]), (NUM_ACTIONS, 0.0))
                attack_rank, attack_prob = next(((r + 1, probs[ACTION_INDEX["Attack"]]) for r, (i, _) in enumerate(ranked) if i == ACTION_INDEX["Attack"]), (NUM_ACTIONS, 0.0))
            else:
                move_rank = move_prob = attack_rank = attack_prob = None
            trace_rows.append({
                "step": step,
                "cell_index": row.get("cell_index"),
                "x": row.get("x"),
                "y": row.get("y"),
                "unit_type": unit_type,
                "raw_action_type_top1": row.get("raw_action_type_top1"),
                "action_type_logits": logits,
                "action_type_probs": [round(p, 6) for p in probs],
                "move_rank": move_rank,
                "move_prob": round(float(move_prob), 6) if move_prob is not None else None,
                "attack_rank": attack_rank,
                "attack_prob": round(float(attack_prob), 6) if attack_prob is not None else None,
                "legal_action_type_mask": row.get("legal_action_type_mask"),
            })
    return trace_rows


def _generate_offline_trace_jsonl(offline: OfflineValidationResult) -> list[dict[str, Any]]:
    """Re-run inference on first batch for trace output."""
    trace_rows: list[dict[str, Any]] = []
    ckpt_p = Path(offline.checkpoint_path)
    bc_p = Path(offline.bc_ready_dir)

    model, _ = load_student_transfer_checkpoint(str(ckpt_p), device="cpu")
    model.eval()

    val_npz = np.load(str(bc_p / "bc_validation.npz"), allow_pickle=False)
    obs = val_npz["observations"][:64].reshape(64, 24, 24, 27)
    acts = val_npz["target_action_branches"][:64] if "target_action_branches" in val_npz else val_npz["actions"][:64]

    obs_t = torch.from_numpy(obs.astype(np.float32))
    with torch.no_grad():
        logits_dict = model(obs_t)
    at_logits = logits_dict["action_type_logits"].cpu().numpy()  # (64, 576, 6)

    for b in range(64):
        for cell in range(576):
            label_idx = int(acts[b, cell, 0])
            if label_idx == 0:
                continue  # skip NoOp labels in trace
            logits = at_logits[b, cell].tolist()
            probs = _softmax(logits)
            pred_idx = int(np.argmax(logits))
            move_rank = next((r + 1 for r, (i, _) in enumerate(sorted(enumerate(probs), key=lambda kv: kv[1], reverse=True)) if i == ACTION_INDEX["Move"]), NUM_ACTIONS)
            attack_rank = next((r + 1 for r, (i, _) in enumerate(sorted(enumerate(probs), key=lambda kv: kv[1], reverse=True)) if i == ACTION_INDEX["Attack"]), NUM_ACTIONS)
            trace_rows.append({
                "sample_idx": b,
                "cell_index": cell,
                "label_action": ACTION_TYPES[label_idx],
                "predicted_top1": ACTION_TYPES[pred_idx],
                "correct": label_idx == pred_idx,
                "action_type_logits": [round(x, 4) for x in logits],
                "action_type_probs": [round(p, 6) for p in probs],
                "move_rank": move_rank,
                "move_prob": round(probs[ACTION_INDEX["Move"]], 6),
                "attack_rank": attack_rank,
                "attack_prob": round(probs[ACTION_INDEX["Attack"]], 6),
            })
    return trace_rows


def _build_markdown_report(
    part_a: HeuristicIsolationResult,
    offline: OfflineValidationResult,
    live: LiveObservationResult,
    comparison: list[dict[str, Any]],
    lineage: list[CheckpointLineageEntry],
    ablation: list[SelectorAblationResult],
    recommendation: dict[str, Any],
    generated_at: str,
) -> str:
    lines: list[str] = []

    def h(level: int, text: str) -> None:
        lines.append("#" * level + " " + text)
        lines.append("")

    def p(*args: str) -> None:
        lines.append(" ".join(args))
        lines.append("")

    def table(headers: list[str], rows: list[list[Any]]) -> None:
        lines.append("| " + " | ".join(headers) + " |")
        lines.append("|" + "|".join(["---"] * len(headers)) + "|")
        for row in rows:
            lines.append("| " + " | ".join(str(x) if x is not None else "N/A" for x in row) + " |")
        lines.append("")

    def bullet(items: list[str], prefix: str = "- ") -> None:
        for item in items:
            lines.append(prefix + item)
        lines.append("")

    h(1, "STAGE10D24 — Mode Isolation and Offline-vs-Live Policy Audit")
    p(f"Generated: {generated_at}")

    # ------- Section 1 -------
    h(2, "1. Heuristic Mode Isolation Verdict")
    p(f"**Verdict: {part_a.isolation_verdict}**")
    if part_a.isolation_failure_evidence:
        p("Failure evidence:")
        bullet(part_a.isolation_failure_evidence)
    h(3, "Telemetry")
    tel = part_a.telemetry
    table(
        ["Field", "Value"],
        [[k, str(v)] for k, v in tel.items()],
    )
    p(
        "**Action required**: The heuristic baseline must be re-implemented without student inference. "
        "Heuristic comparisons from Stage10D22/D23 are invalid as both modes use identical student logits."
    )

    # ------- Section 2 -------
    h(2, "2. Checkpoint Lineage and Loaded Checkpoint Confirmation")
    p(f"Current checkpoint: `{offline.checkpoint_path}`")
    p(f"Checkpoint exists: {Path(offline.checkpoint_path).exists()}")
    p(f"BC validation dataset: `{offline.bc_ready_dir}`")
    p(f"Validation samples: {offline.num_samples}")
    p(f"Actor cells in validation: {offline.num_actor_cells}")
    table(
        ["Name", "Stage", "Current", "Exists", "Val Loss", "Val AccType", "Val Recall", "Train Attack#", "Train Attack Acc"],
        [
            [
                e.name,
                e.stage,
                str(e.is_current),
                str(e.checkpoint_exists),
                f"{e.val_total_loss:.6f}" if e.val_total_loss else "N/A",
                f"{e.val_actor_cell_action_type_accuracy:.4f}" if e.val_actor_cell_action_type_accuracy else "N/A",
                f"{e.val_actor_cell_non_noop_recall:.4f}" if e.val_actor_cell_non_noop_recall else "N/A",
                str(e.train_attack_proxy_count) if e.train_attack_proxy_count is not None else "N/A",
                f"{e.train_attack_proxy_accuracy:.4f}" if e.train_attack_proxy_accuracy else "N/A",
            ]
            for e in lineage
        ],
    )

    # ------- Section 3 -------
    h(2, "3. Offline Validation Action Distribution")
    table(
        ["Action", "Label Count", "Predicted Top1 Count", "Precision", "Recall"],
        [
            [
                a,
                offline.label_distribution.get(a, 0),
                offline.predicted_top1_distribution.get(a, 0),
                f"{offline.per_class_precision.get(a, 0):.4f}",
                f"{offline.per_class_recall.get(a, 0):.4f}",
            ]
            for a in ACTION_TYPES
        ],
    )
    p(
        f"Average Move rank (offline, actor cells): {offline.avg_move_rank:.3f}  |  "
        f"Average Attack rank (offline, actor cells): {offline.avg_attack_rank:.3f}"
    )
    p(
        f"Average Move probability (offline): {offline.avg_move_prob:.6f}  |  "
        f"Average Attack probability (offline): {offline.avg_attack_prob:.6f}"
    )
    p(f"Move rank distribution: {dict(offline.move_rank_distribution)}")
    p(f"Attack rank distribution: {dict(offline.attack_rank_distribution)}")

    # ------- Section 4 -------
    h(2, "4. Offline Prediction Confusion Matrix")
    p("Rows = true label, columns = predicted label.")
    table(
        ["True \\ Pred"] + ACTION_TYPES,
        [[ACTION_TYPES[i]] + offline.confusion_matrix[i] for i in range(NUM_ACTIONS)],
    )

    # ------- Section 5 -------
    h(2, "5. Unity Live Prediction Distribution")
    p(f"Mode: {live.mode}, Steps: {live.steps_processed}, Actor cells: {live.friendly_actor_cells}")
    table(
        ["Action", "Live Predicted Top1 Count"],
        [[a, live.predicted_top1_distribution.get(a, 0)] for a in ACTION_TYPES],
    )
    p(f"Move top1: {live.move_top1} | top2: {live.move_top2} | top3: {live.move_top3}")
    p(f"Attack top1: {live.attack_top1} | top2: {live.attack_top2} | top3: {live.attack_top3}")
    p(f"Move avg rank: {live.avg_move_rank:.3f} | Move avg prob: {live.avg_move_prob:.6f}")
    p(f"Attack avg rank: {live.avg_attack_rank:.3f} | Attack avg prob: {live.avg_attack_prob:.6f}")
    p(f"Move legal but not selected: {live.move_legal_not_selected}")
    p(f"Attack legal but not selected: {live.attack_legal_not_selected}")

    # ------- Section 6 -------
    h(2, "6. Offline-vs-Live Comparison")
    table(
        ["Action", "Offline Label#", "Offline Pred Top1#", "Live Pred Top1#", "Off Avg Prob", "Live Avg Prob", "Off Avg Rank", "Live Avg Rank"],
        [
            [
                r["action"],
                r["offline_label_count"],
                r["offline_predicted_top1_count"],
                r["live_predicted_top1_count"],
                r["offline_avg_probability"],
                r["live_avg_probability"],
                r["offline_avg_rank"],
                r["live_avg_rank"],
            ]
            for r in comparison
        ],
    )

    # ------- Section 7 -------
    h(2, "7. Move Diagnosis")
    move_comp = next((r for r in comparison if r["action"] == "Move"), {})
    off_move_label = offline.move_label_count
    off_move_pred = offline.move_predicted_top1_count
    live_move_pred = live.move_top1

    if off_move_label == 0:
        p("**CRITICAL**: BC validation dataset contains ZERO Move labels. "
          "The model cannot learn to predict Move from this dataset regardless of architecture or training hyperparameters. "
          "The high val_accuracy=1.0 is misleading — the model is perfectly predicting on a dataset that has no Move samples.")
    elif off_move_pred == 0 and off_move_label > 0:
        p(f"**Offline Move top1=0** despite {off_move_label} Move labels. "
          "This indicates the model is not learning to predict Move in the offline validation data. "
          "Possible causes: severe class imbalance (NoOp/Harvest/Produce dominate), "
          "BC cross-entropy loss not weighted for rare classes, Move labels may come from invalid/masked-out contexts.")
    elif off_move_pred > 0 and live_move_pred == 0:
        p(f"**Offline Move top1={off_move_pred}** but **Live Move top1=0**. "
          "This is strong evidence of observation/domain mismatch between BC dataset and Unity live observations.")
    else:
        p(f"Offline Move top1={off_move_pred}, Live Move top1={live_move_pred}.")

    p(f"Move appears in top-2 live: {live.move_top2}, top-3 live: {live.move_top3}. "
      f"Avg rank={live.avg_move_rank:.3f}, avg prob={live.avg_move_prob:.6f}.")

    # ------- Section 8 -------
    h(2, "8. Attack Diagnosis")
    off_attack_label = offline.attack_label_count
    off_attack_pred = offline.attack_predicted_top1_count
    live_attack_pred = live.attack_top1

    if off_attack_label == 0:
        p("**CRITICAL**: BC validation dataset contains ZERO Attack labels. "
          "Model cannot predict Attack from this dataset.")
    elif off_attack_pred == 0 and off_attack_label > 0:
        p(f"**Offline Attack top1=0** despite {off_attack_label} Attack labels. "
          "Class imbalance or training configuration issue suspected.")
    elif off_attack_pred > 0 and live_attack_pred == 0:
        p(f"**Offline Attack top1={off_attack_pred}** but **Live Attack top1=0**. "
          "Domain mismatch between BC dataset and Unity live observations.")
    else:
        p(f"Offline Attack top1={off_attack_pred}, Live Attack top1={live_attack_pred}.")

    p(f"Attack in top-2 live: {live.attack_top2}, top-3 live: {live.attack_top3}. "
      f"Avg rank={live.avg_attack_rank:.3f}, avg prob={live.avg_attack_prob:.6f}.")

    # ------- Section 9 -------
    h(2, "9. Selector Ablation Results")
    if ablation:
        table(
            ["Selector", "Move#", "Attack#", "NoOp#", "Invalid/Masked#", "Move Share", "Attack Share"],
            [
                [
                    a.selector_name,
                    a.move_count,
                    a.attack_count,
                    a.noop_count,
                    a.invalid_masked_count,
                    f"{a.move_share:.4f}",
                    f"{a.attack_share:.4f}",
                ]
                for a in ablation
            ],
        )
        for a in ablation:
            p(f"**{a.selector_name}**: {a.description}")
            p(f"  Distribution: {a.predicted_distribution}")
    else:
        p("No ablation data available.")

    # ------- Section 10 -------
    h(2, "10. GO/NO-GO Recommendation")
    p(f"**Decisions**: {', '.join(recommendation['decisions'])}")
    p("Reasoning:")
    bullet(recommendation["reasoning"])
    table(
        ["Decision", "Meaning"],
        [
            ["CONTINUE_WITH_CURRENT_CHECKPOINT", "Current checkpoint is adequate for current goals"],
            ["SWITCH_CHECKPOINT", "A different checkpoint predicts Move/Attack better offline"],
            ["FIX_OBSERVATION_DOMAIN_MISMATCH", "Offline predicts Move but live does not — fix observation semantics"],
            ["RETRAIN_OR_ADJUST_BC_OBJECTIVE", "BC dataset lacks Move/Attack or model is suppressing them — need retraining"],
            ["TEST_NON_GREEDY_SELECTOR", "Move appears in top2/top3 — non-greedy selector may expose it"],
            ["FIX_HEURISTIC_MODE_WIRING", "Heuristic mode incorrectly uses student inference — fix C# wiring"],
        ],
    )

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    generated_at = _utc_now()
    print(f"[D24] Stage10D24 audit started at {generated_at}")

    # Part A
    part_a = run_part_a()
    print(f"[D24 PartA] Isolation verdict: {part_a.isolation_verdict}")
    print(f"  Evidence: {part_a.isolation_failure_evidence[:2]}")

    # Part B — offline
    print("[D24 PartB] Running offline BC validation...")
    offline = _run_offline_validation(
        str(STAGE10D14_CHECKPOINT),
        str(STAGE10D14_BC_READY),
    )
    print(f"  Actor cells: {offline.num_actor_cells}, Move labels: {offline.move_label_count}, "
          f"Move pred top1: {offline.move_predicted_top1_count}, Attack labels: {offline.attack_label_count}")

    # Part B — live
    live = run_part_b_live(STUDENT_MODE)
    print(f"[D24 PartB-Live] Actor cells: {live.friendly_actor_cells}, Move top1: {live.move_top1}, Attack top1: {live.attack_top1}")

    # Comparison table
    comparison = _build_comparison_table(offline, live)

    # Part C
    lineage = run_part_c()
    for e in lineage:
        msg = f"  {e.name}: exists={e.checkpoint_exists}"
        if e.offline:
            msg += f", off_move={e.offline.move_predicted_top1_count}, off_attack={e.offline.attack_predicted_top1_count}"
        elif e.offline_error:
            msg += f", error={e.offline_error[:60]}"
        print(msg)

    # Part D
    ablation = run_part_d(live)
    for a in ablation:
        print(f"  [{a.selector_name}] Move={a.move_count}, Attack={a.attack_count}, NoOp={a.noop_count}")

    # Recommendation
    recommendation = _make_go_nogo_recommendation(offline, live, part_a, lineage)
    print(f"[D24] Decisions: {recommendation['decisions']}")

    # Build JSON output
    audit_json: dict[str, Any] = {
        "stage": "10D.24",
        "generated_at_utc": generated_at,
        "checkpoint_audited": str(STAGE10D14_CHECKPOINT),
        "part_a_heuristic_isolation": _dataclass_to_dict(part_a),
        "part_b_offline_validation": _dataclass_to_dict(offline),
        "part_b_live_observation": _dataclass_to_dict(live),
        "part_b_comparison_table": comparison,
        "part_c_lineage": [_dataclass_to_dict(e) for e in lineage],
        "part_d_selector_ablation": [_dataclass_to_dict(a) for a in ablation],
        "recommendation": recommendation,
    }

    out_json = REPORTS_DIR / "stage10d24_mode_isolation_and_offline_live_audit.json"
    out_json.write_text(json.dumps(audit_json, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[D24] Written: {out_json}")

    # JSONL traces
    print("[D24] Generating offline trace JSONL...")
    offline_trace = _generate_offline_trace_jsonl(offline)
    out_off_trace = REPORTS_DIR / "stage10d24_policy_offline_validation_trace.jsonl"
    _write_jsonl(out_off_trace, offline_trace)
    print(f"[D24] Written: {out_off_trace} ({len(offline_trace)} rows)")

    print("[D24] Generating live trace JSONL...")
    live_trace = _generate_live_trace_jsonl(live)
    out_live_trace = REPORTS_DIR / "stage10d24_live_observation_policy_trace.jsonl"
    _write_jsonl(out_live_trace, live_trace)
    print(f"[D24] Written: {out_live_trace} ({len(live_trace)} rows)")

    # Markdown report
    print("[D24] Generating Markdown report...")
    md = _build_markdown_report(
        part_a=part_a,
        offline=offline,
        live=live,
        comparison=comparison,
        lineage=lineage,
        ablation=ablation,
        recommendation=recommendation,
        generated_at=generated_at,
    )
    out_md = REPORTS_DIR / "STAGE10D24_MODE_ISOLATION_AND_OFFLINE_LIVE_AUDIT.md"
    out_md.write_text(md, encoding="utf-8")
    print(f"[D24] Written: {out_md}")

    print(f"\n[D24] Stage10D24 complete. Outputs in: {REPORTS_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
