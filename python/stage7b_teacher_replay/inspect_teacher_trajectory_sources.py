#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np


DEFAULT_ROOT = Path("python/week5_teacher_legacy032")
DEFAULT_OUTPUT = Path("python/stage7b_teacher_replay/stage7b_teacher_replay_source_inventory.json")

SOURCE_GROUPS = (
    "teacher_rollouts",
    "teacher_exports",
    "teacher_adapted",
    "teacher_exports_bc",
)


@dataclass
class SourceInfo:
    path: str
    group: str
    format: str
    npz_file: str | None
    manifest_file: str | None
    npz_keys: list[str]
    episodes_count: int | None
    steps_count: int | None
    has_full_state: bool
    has_raw_teacher_action: bool
    has_action_mask: bool
    has_reset_terminal_metadata: bool
    replay_ready: bool
    replay_ready_reason: str
    metadata: dict[str, Any]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build Stage7B teacher trajectory source inventory.")
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def classify_format(group: str, npz_keys: list[str], manifest: dict[str, Any]) -> str:
    schema_version = str(manifest.get("schema_version", "")).strip().lower()

    if group == "teacher_rollouts" or "teacher_rollout_raw" in schema_version:
        return "legacy032_teacher_rollout_raw"
    if group in ("teacher_exports", "teacher_adapted") or "adapted" in schema_version:
        return "legacy032_unity_v2_adapted"
    if group == "teacher_exports_bc" or "bc_ready" in schema_version:
        return "legacy032_unity_v2_bc_ready"

    if "per_cell_action_t" in npz_keys:
        return "unknown_rollout_like"
    if "actions" in npz_keys and "observations" in npz_keys:
        return "unknown_adapted_like"
    return "unknown"


def detect_full_state(npz_keys: list[str], sample_info: dict[str, Any]) -> bool:
    # Replay-ready full state would need explicit unit/state snapshot fields.
    explicit_state_keys = {
        "runtime_state_t",
        "unit_state_t",
        "units_t",
        "grid_state_t",
        "match_state_t",
        "command_queue_t",
        "player_state_t",
    }
    if any(k in explicit_state_keys for k in npz_keys):
        return True

    # Existing info_t_json in legacy exports contains rewards only, not authoritative runtime state.
    info_preview = str(sample_info.get("info_preview", ""))
    if info_preview:
        lowered = info_preview.lower()
        if "units" in lowered and "positions" in lowered and "owner" in lowered:
            return True

    return False


def score_source(info: SourceInfo) -> int:
    score = 0
    if info.group == "teacher_rollouts":
        score += 80
    if info.format == "legacy032_teacher_rollout_raw":
        score += 60
    if info.has_raw_teacher_action:
        score += 40
    if info.has_action_mask:
        score += 20
    if info.steps_count:
        score += min(info.steps_count // 1000, 200)
    if info.group == "teacher_exports_bc":
        score -= 120
    return score


def load_manifest(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def load_npz_metadata(npz_path: Path) -> tuple[list[str], int | None, int | None, dict[str, Any]]:
    keys: list[str] = []
    episodes_count: int | None = None
    steps_count: int | None = None
    meta: dict[str, Any] = {}

    with np.load(npz_path, allow_pickle=True) as npz:
        keys = sorted(list(npz.keys()))

        if "step_id" in npz:
            steps_count = int(np.asarray(npz["step_id"]).shape[0])
        elif len(npz.files) > 0:
            first_key = npz.files[0]
            steps_count = int(np.asarray(npz[first_key]).shape[0]) if np.asarray(npz[first_key]).ndim > 0 else None

        if "episode_id" in npz:
            episode_id = np.asarray(npz["episode_id"])
            if episode_id.size > 0:
                episodes_count = int(np.unique(episode_id).shape[0])

        if "info_t_json" in npz:
            info_arr = np.asarray(npz["info_t_json"])
            if info_arr.size > 0:
                meta["info_preview"] = str(info_arr.reshape(-1)[0])[:500]

        if "observation_t" in npz:
            obs = np.asarray(npz["observation_t"])
            meta["observation_shape"] = list(obs.shape)
        elif "observations" in npz:
            obs = np.asarray(npz["observations"])
            meta["observation_shape"] = list(obs.shape)

        if "per_cell_action_t" in npz:
            act = np.asarray(npz["per_cell_action_t"])
            meta["action_shape"] = list(act.shape)
        elif "actions" in npz:
            act = np.asarray(npz["actions"])
            meta["action_shape"] = list(act.shape)

    return keys, episodes_count, steps_count, meta


def inspect_source(group_dir: Path, source_dir: Path) -> SourceInfo | None:
    npz_files = sorted(source_dir.glob("*.npz"))
    if not npz_files:
        return None

    preferred_npz = None
    if (source_dir / "teacher_rollout_raw.npz").exists():
        preferred_npz = source_dir / "teacher_rollout_raw.npz"
    elif (source_dir / "adapted_dataset.npz").exists():
        preferred_npz = source_dir / "adapted_dataset.npz"
    elif (source_dir / "bc_debug.npz").exists():
        preferred_npz = source_dir / "bc_debug.npz"
    else:
        preferred_npz = npz_files[0]

    manifest_candidates = sorted(source_dir.glob("*manifest*.json"))
    manifest_file = manifest_candidates[0] if manifest_candidates else None
    manifest = load_manifest(manifest_file) if manifest_file else {}

    npz_keys, episodes_count, steps_count, npz_meta = load_npz_metadata(preferred_npz)
    source_format = classify_format(group_dir.name, npz_keys, manifest)

    has_raw_teacher_action = "per_cell_action_t" in npz_keys or "actions" in npz_keys
    has_action_mask = (
        "action_mask_t" in npz_keys
        or "action_mask_available_t" in npz_keys
        or "source_valid_action_mask_t" in npz_keys
        or "source_valid_action_mask" in npz_keys
    )

    has_reset_terminal_metadata = all(
        k in npz_keys for k in ("episode_id", "step_id", "done_t", "terminated_t", "truncated_t")
    )

    has_full_state = detect_full_state(npz_keys, npz_meta)

    replay_ready = has_full_state and has_raw_teacher_action and has_reset_terminal_metadata
    if replay_ready:
        replay_ready_reason = "contains state + action + reset/terminal metadata"
    elif not has_full_state:
        replay_ready_reason = "missing authoritative runtime state fields for Unity sync"
    elif not has_raw_teacher_action:
        replay_ready_reason = "missing teacher action fields"
    else:
        replay_ready_reason = "missing reset/terminal metadata"

    metadata: dict[str, Any] = {
        "schema_version": manifest.get("schema_version"),
        "teacher_lineage": manifest.get("teacher_lineage"),
        "step_mode": manifest.get("step_mode"),
        "branch_sizes": manifest.get("branch_sizes") or manifest.get("stored_action_branch_sizes") or manifest.get("exported_per_cell_branch_sizes"),
    }
    metadata.update(npz_meta)

    return SourceInfo(
        path=str(source_dir.as_posix()),
        group=group_dir.name,
        format=source_format,
        npz_file=str(preferred_npz.name),
        manifest_file=str(manifest_file.name) if manifest_file else None,
        npz_keys=npz_keys,
        episodes_count=episodes_count,
        steps_count=steps_count,
        has_full_state=has_full_state,
        has_raw_teacher_action=has_raw_teacher_action,
        has_action_mask=has_action_mask,
        has_reset_terminal_metadata=has_reset_terminal_metadata,
        replay_ready=replay_ready,
        replay_ready_reason=replay_ready_reason,
        metadata=metadata,
    )


def resolve_path(path: Path) -> Path:
    if path.is_absolute():
        return path
    return (Path.cwd() / path).resolve()


def main() -> int:
    args = parse_args()
    root = resolve_path(args.root)
    output = resolve_path(args.output)

    sources: list[SourceInfo] = []

    for group in SOURCE_GROUPS:
        group_dir = root / group
        if not group_dir.exists():
            continue

        for child in sorted(group_dir.iterdir()):
            if not child.is_dir():
                continue
            info = inspect_source(group_dir, child)
            if info is not None:
                sources.append(info)

    sources.sort(key=lambda s: (s.group, s.path))

    replay_ready_sources = [s for s in sources if s.replay_ready]

    selected: SourceInfo | None = None
    if sources:
        selected = sorted(sources, key=score_source, reverse=True)[0]

    payload: dict[str, Any] = {
        "generated_at_utc": now_iso(),
        "root": str(root.as_posix()),
        "source_count": len(sources),
        "sources": [asdict(s) for s in sources],
        "selected_source_path": selected.path if selected else None,
        "selected_source_format": selected.format if selected else None,
        "selected_source_replay_ready": bool(selected.replay_ready) if selected else False,
        "selected_source_replay_ready_reason": selected.replay_ready_reason if selected else "no source found",
        "replay_ready_source_count": len(replay_ready_sources),
        "selection_note": "Selection prefers raw rollout sources with per-step teacher actions and larger step coverage; bc_ready is intentionally deprioritized for replay truth.",
        "no_go_required": len(replay_ready_sources) == 0,
        "no_go_reason": (
            "No source contains replay-ready authoritative runtime state + teacher action + reset metadata. New teacher rollout export with Unity replay fields is required."
            if len(replay_ready_sources) == 0
            else None
        ),
    }

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")

    print(f"[Stage7B][TeacherReplay] Source inventory written: {output.as_posix()}")
    print(f"[Stage7B][TeacherReplay] Sources scanned: {len(sources)}")
    print(f"[Stage7B][TeacherReplay] Replay-ready sources: {len(replay_ready_sources)}")
    if selected is not None:
        print(f"[Stage7B][TeacherReplay] Selected source: {selected.path}")
        print(f"[Stage7B][TeacherReplay] Selected replay-ready: {selected.replay_ready}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
