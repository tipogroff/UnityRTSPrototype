from __future__ import annotations

import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

MAP_W = 24
MAP_H = 24
ACTION_NAMES = ["NoOp", "Move", "Harvest", "Return", "Produce", "Attack"]
COMBAT_TYPES = {"Worker", "Light", "Heavy", "Ranged"}


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def resolve(path: str | Path) -> Path:
    p = Path(path)
    return p if p.is_absolute() else repo_root() / p


def load_json(path: str | Path) -> dict[str, Any]:
    p = resolve(path)
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return json.loads(p.read_text(encoding="utf-8-sig"))


def load_jsonl(path: str | Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    p = resolve(path)
    for line in p.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def write_json(path: str | Path, payload: dict[str, Any]) -> Path:
    p = resolve(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")
    return p


def flat_to_xy(flat: int) -> tuple[int, int]:
    return int(flat % MAP_W), int(flat // MAP_W)


def xy_to_flat(x: int, y: int) -> int:
    return int(y * MAP_W + x)


def in_bounds(x: int, y: int) -> bool:
    return 0 <= x < MAP_W and 0 <= y < MAP_H


def manhattan(a: tuple[int, int], b: tuple[int, int]) -> int:
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def p_bucket(p: float) -> str:
    if p < 0.2:
        return "0.0-0.2"
    if p < 0.5:
        return "0.2-0.5"
    if p < 0.8:
        return "0.5-0.8"
    return "0.8-1.0"


def top_competing_action(probs: dict[str, Any]) -> str:
    vals = {
        "NoOp": float(probs.get("noop") or 0.0),
        "Harvest": float(probs.get("harvest") or 0.0),
        "Produce": float(probs.get("produce") or 0.0),
        "Attack": float(probs.get("attack") or 0.0),
    }
    return max(vals.items(), key=lambda kv: kv[1])[0]


def safe_float(v: Any) -> float:
    try:
        return float(v)
    except Exception:
        return 0.0


def safe_int(v: Any, default: int = 0) -> int:
    try:
        return int(v)
    except Exception:
        return default


def load_stage10d18rr_inputs() -> dict[str, Any]:
    base = Path("python/week6_student/reports")
    return {
        "binding": load_json(base / "stage10d18rr_checkpoint_binding_verification.json"),
        "trace": load_jsonl(base / "stage10d18rr_runtime_redeploy_trace.jsonl"),
        "lifecycle": load_json(base / "stage10d18rr_produced_unit_lifecycle.json"),
        "move": load_json(base / "stage10d18rr_movement_command_path_audit.json"),
        "action_dist": load_json(base / "stage10d18rr_action_distribution_over_time.json"),
        "off_actor": load_json(base / "stage10d18rr_off_actor_safety_audit.json"),
        "summary": load_json(base / "stage10d18rr_visual_behavior_summary.json"),
    }


def get_sparse_rerun_snapshot_paths() -> list[Path]:
    d = resolve("python/week6_student/tmp/stage10d18_runtime_redeploy_rerun")
    if not d.exists():
        return []
    return sorted(d.glob("stage10d18_snapshot_step*.json"))


def get_sparse_rerun_cell_tables() -> list[Path]:
    d = resolve("python/week6_student/tmp/stage10d18_runtime_redeploy_rerun")
    if not d.exists():
        return []
    return sorted(d.glob("stage10d10_global_runtime_cell_table_step*.jsonl"))


def to_step_from_name(path: Path) -> int:
    stem = path.stem
    digits = "".join(ch for ch in stem if ch.isdigit())
    return safe_int(digits, 0)


def summarize_unit_counts(rows: Iterable[dict[str, Any]]) -> dict[str, int]:
    c = Counter()
    for row in rows:
        c[str(row.get("unit_type") or "Unknown")] += 1
    return dict(sorted(c.items()))


def update_nested_count(root: dict[str, Any], k1: str, k2: str, delta: int = 1) -> None:
    if k1 not in root:
        root[k1] = {}
    if k2 not in root[k1]:
        root[k1][k2] = 0
    root[k1][k2] += int(delta)


def empty_action_counter() -> dict[str, int]:
    return {a: 0 for a in ACTION_NAMES}


def default_counter_map(keys: Iterable[str]) -> dict[str, dict[str, int]]:
    return {k: empty_action_counter() for k in keys}


def ratio(num: float, den: float) -> float:
    return float(num) / float(den) if den else 0.0


def classify_cell_type(row: dict[str, Any]) -> str:
    if bool(row.get("runtime_is_friendly_actor")):
        return "friendly_actor"
    if bool(row.get("runtime_is_enemy")):
        return "enemy"
    if bool(row.get("runtime_is_resource")):
        return "resource"
    if bool(row.get("runtime_is_empty")):
        return "empty"
    owner = str(row.get("decoded_observation_owner") or "Unknown")
    return owner.lower()


def nearest_distance(p: tuple[int, int], targets: list[tuple[int, int]]) -> int | None:
    if not targets:
        return None
    return min(manhattan(p, t) for t in targets)


@dataclass
class StepAggregate:
    step: int
    actor_count: int = 0
    produced_count: int = 0
    combat_count: int = 0
    off_actor_non_noop_count: int = 0
