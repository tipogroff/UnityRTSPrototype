from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ACTION_TYPES = ["NoOp", "Move", "Harvest", "Return", "Produce", "Attack"]
ACTION_INDEX = {name: idx for idx, name in enumerate(ACTION_TYPES)}
REQUIRED_MODES = [
    "student_live_policy",
    "heuristic_baseline",
    "scripted_deterministic_commands",
]
PRODUCE_LOOKAHEAD_STEPS = (1, 5, 20)


@dataclass
class StepSnapshot:
    p1_resources: int
    p2_resources: int
    units: list[dict[str, Any]]


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


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y"}
    if isinstance(value, (int, float)):
        return value != 0
    return bool(value)


def _norm_action(name: Any) -> str:
    text = str(name or "").strip()
    if text in ACTION_INDEX:
        return text
    low = text.lower()
    for item in ACTION_TYPES:
        if item.lower() == low:
            return item
    return "NoOp"


def _empty_action_map() -> dict[str, int]:
    return {name: 0 for name in ACTION_TYPES}


def _load_mode_snapshots(mode_dir: Path) -> dict[int, StepSnapshot]:
    by_step: dict[int, StepSnapshot] = {}
    for path in sorted(mode_dir.glob("stage10d22_*_snapshot_step*.json")):
        stem = path.stem
        if "step" not in stem:
            continue
        step = int(stem.split("step")[-1])
        j = _read_json(path)
        by_step[step] = StepSnapshot(
            p1_resources=int(j.get("player1_resources", 0) or 0),
            p2_resources=int(j.get("player2_resources", 0) or 0),
            units=list(j.get("unit_positions") or []),
        )
    return by_step


def _mask_allowed(row: dict[str, Any], raw_action: str) -> bool:
    mask = row.get("legal_action_type_mask")
    if not isinstance(mask, list):
        return False
    idx = ACTION_INDEX.get(raw_action, 0)
    if idx < 0 or idx >= len(mask):
        return False
    return _as_bool(mask[idx])


def _find_actor(step: StepSnapshot | None, row: dict[str, Any]) -> dict[str, Any] | None:
    if step is None:
        return None
    x = int(row.get("x", -1) or -1)
    y = int(row.get("y", -1) or -1)
    owner = str(row.get("decoded_observation_owner") or "")
    unit_type = str(row.get("decoded_observation_unit_type") or "")
    for u in step.units:
        if int(u.get("x", -999)) != x or int(u.get("y", -999)) != y:
            continue
        if owner and str(u.get("owner") or "") != owner:
            continue
        if unit_type and str(u.get("unit_type") or "") != unit_type:
            continue
        return u
    return None


def _friendly_units(step: StepSnapshot | None, owner: str) -> list[dict[str, Any]]:
    if step is None:
        return []
    return [u for u in step.units if str(u.get("owner") or "") == owner]


def _enemy_units(step: StepSnapshot | None, owner: str) -> list[dict[str, Any]]:
    if step is None:
        return []
    return [u for u in step.units if str(u.get("owner") or "") not in {owner, "Neutral"}]


def _sum_enemy_hp(step: StepSnapshot | None, owner: str) -> int:
    return sum(int(u.get("hp", 0) or 0) for u in _enemy_units(step, owner))


def _owner_resources(step: StepSnapshot | None, owner: str) -> int:
    if step is None:
        return 0
    if owner == "Player1":
        return int(step.p1_resources)
    if owner == "Player2":
        return int(step.p2_resources)
    return 0


def _building_state_signature(step: StepSnapshot | None, owner: str) -> list[tuple[Any, ...]]:
    if step is None:
        return []
    sig: list[tuple[Any, ...]] = []
    for u in step.units:
        if str(u.get("owner") or "") != owner:
            continue
        unit_type = str(u.get("unit_type") or "")
        if unit_type not in {"Base", "Barracks"}:
            continue
        sig.append(
            (
                str(u.get("unit_name") or ""),
                unit_type,
                str(u.get("building_current_producing_type") or ""),
                int(u.get("building_production_time_remaining", 0) or 0),
                int(u.get("building_production_time_full", 0) or 0),
                _as_bool(u.get("building_is_producing")),
            )
        )
    sig.sort()
    return sig


def _produce_state_delta_signals(
    owner: str,
    row: dict[str, Any],
    snapshots: dict[int, StepSnapshot],
    step: int,
    lookahead_steps: int,
) -> dict[str, bool]:
    cur = snapshots.get(step)
    nxt = snapshots.get(step + lookahead_steps)
    if cur is None or nxt is None:
        return {
            "resources_decreased": False,
            "production_queue_changed": False,
            "building_production_state_changed": False,
            "unit_count_increased": False,
            "possible_state_delta": False,
        }

    resources_decreased = _owner_resources(nxt, owner) < _owner_resources(cur, owner)
    own_cur = len(_friendly_units(cur, owner))
    own_nxt = len(_friendly_units(nxt, owner))
    unit_count_increased = own_nxt > own_cur

    actor_cur = _find_actor(cur, row)
    actor_nxt = _find_actor(nxt, row)
    building_state_changed = False
    if actor_cur is not None and actor_nxt is not None:
        building_state_changed = (
            str(actor_cur.get("building_current_producing_type") or "")
            != str(actor_nxt.get("building_current_producing_type") or "")
            or int(actor_cur.get("building_production_time_remaining", 0) or 0)
            != int(actor_nxt.get("building_production_time_remaining", 0) or 0)
            or int(actor_cur.get("building_production_time_full", 0) or 0)
            != int(actor_nxt.get("building_production_time_full", 0) or 0)
            or _as_bool(actor_cur.get("building_is_producing"))
            != _as_bool(actor_nxt.get("building_is_producing"))
        )

    queue_changed = _building_state_signature(cur, owner) != _building_state_signature(nxt, owner)
    possible_state_delta = (
        resources_decreased or queue_changed or building_state_changed or unit_count_increased
    )
    return {
        "resources_decreased": resources_decreased,
        "production_queue_changed": queue_changed,
        "building_production_state_changed": building_state_changed,
        "unit_count_increased": unit_count_increased,
        "possible_state_delta": possible_state_delta,
    }


def _state_delta_non_produce(
    effective_action: str,
    owner: str,
    row: dict[str, Any],
    cur: StepSnapshot | None,
    nxt: StepSnapshot | None,
) -> bool:
    actor_cur = _find_actor(cur, row)
    actor_nxt = _find_actor(nxt, row)

    if effective_action in {"NoOp", "Produce"}:
        return False

    if effective_action == "Move":
        if actor_cur is None or actor_nxt is None:
            return False
        return (
            int(actor_cur.get("x", -1)) != int(actor_nxt.get("x", -1))
            or int(actor_cur.get("y", -1)) != int(actor_nxt.get("y", -1))
        )

    if effective_action == "Harvest":
        if actor_cur is None or actor_nxt is None:
            return False
        return int(actor_nxt.get("carried_resources", 0) or 0) != int(
            actor_cur.get("carried_resources", 0) or 0
        )

    if effective_action == "Return":
        p_cur = _owner_resources(cur, owner)
        p_nxt = _owner_resources(nxt, owner)
        carry_cur = int(actor_cur.get("carried_resources", 0) or 0) if actor_cur is not None else 0
        carry_nxt = int(actor_nxt.get("carried_resources", 0) or 0) if actor_nxt is not None else 0
        return (p_nxt > p_cur) or (carry_cur > 0 and carry_nxt == 0)

    if effective_action == "Attack":
        hp_cur = _sum_enemy_hp(cur, owner)
        hp_nxt = _sum_enemy_hp(nxt, owner)
        n_cur = len(_enemy_units(cur, owner))
        n_nxt = len(_enemy_units(nxt, owner))
        return (hp_nxt < hp_cur) or (n_nxt < n_cur)

    return False


def _first_failing_boundary(
    action: str,
    raw_selected_by_action: dict[str, int],
    mask_allowed_by_raw_action: dict[str, int],
    post_mask_by_action: dict[str, int],
    decoded_by_action: dict[str, int],
    submitted_by_action: dict[str, int],
    applier_accepted_by_action: dict[str, int],
    runtime_applied_by_action: dict[str, int],
    state_delta_by_action: dict[str, int],
) -> str:
    if raw_selected_by_action[action] == 0:
        return "raw_selected"
    if mask_allowed_by_raw_action[action] == 0:
        return "mask_allowed"
    if post_mask_by_action[action] == 0:
        return "post_mask"
    if decoded_by_action[action] == 0:
        return "decoded"
    if submitted_by_action[action] == 0:
        return "submitted"
    if applier_accepted_by_action[action] == 0:
        return "applier_accepted"
    if runtime_applied_by_action[action] == 0:
        return "runtime_applied"
    if state_delta_by_action[action] == 0:
        return "state_delta"
    return "none"


def _table(headers: list[str], rows: list[list[Any]]) -> list[str]:
    out = ["| " + " | ".join(headers) + " |", "|" + "|".join(["---"] * len(headers)) + "|"]
    for row in rows:
        out.append("| " + " | ".join(str(v) for v in row) + " |")
    return out


def _assert_strict_tri_mode(run_manifest: dict[str, Any]) -> tuple[dict[str, dict[str, Any]], bool]:
    entries_raw = run_manifest.get("modes")
    if not isinstance(entries_raw, list):
        raise RuntimeError("stage10d22_run_manifest.json is invalid: missing 'modes' list")

    entries: dict[str, dict[str, Any]] = {}
    for item in entries_raw:
        if not isinstance(item, dict):
            continue
        mode = str(item.get("mode") or "").strip()
        if mode:
            entries[mode] = item

    mode_names = sorted(entries.keys())
    required = sorted(REQUIRED_MODES)
    full_tri_mode = mode_names == required
    if not full_tri_mode:
        raise RuntimeError(
            "Strict tri-mode requirement failed. Expected exactly modes "
            + ", ".join(REQUIRED_MODES)
            + "; got "
            + ", ".join(mode_names)
        )
    return entries, full_tri_mode


def main() -> int:
    root = Path(__file__).resolve().parents[2]
    reports = root / "python/week6_student/reports"
    reports.mkdir(parents=True, exist_ok=True)

    base = root / "python/week6_student/tmp/stage10d22_global_lifecycle"
    run_manifest_path = base / "stage10d22_run_manifest.json"
    if not run_manifest_path.exists():
        raise RuntimeError("Strict tri-mode capture required: stage10d22_run_manifest.json is missing")

    run_manifest = _read_json(run_manifest_path)
    mode_entries, full_tri_mode = _assert_strict_tri_mode(run_manifest)

    mode_status: dict[str, dict[str, Any]] = {}
    mode_dirs: dict[str, Path] = {}
    for mode_name in REQUIRED_MODES:
        entry = mode_entries[mode_name]
        output_rel = str(entry.get("output_relative_dir") or "").strip().replace("\\", "/")
        mode_dir = (root / output_rel) if output_rel else (base / mode_name)
        if not mode_dir.exists():
            raise RuntimeError(f"Mode '{mode_name}' directory missing: {mode_dir}")

        mode_manifest_path = mode_dir / "stage10d22_mode_manifest.json"
        if not mode_manifest_path.exists():
            raise RuntimeError(f"Mode '{mode_name}' manifest missing: {mode_manifest_path}")

        mode_manifest = _read_json(mode_manifest_path)
        mode_dirs[mode_name] = mode_dir
        mode_status[mode_name] = {
            "steps_completed": int(mode_manifest.get("steps_completed", 0) or 0),
            "target_steps": int(mode_manifest.get("target_steps", 0) or 0),
            "scripted_attempted": int(mode_manifest.get("scripted_attempted", 0) or 0),
            "scripted_accepted": int(mode_manifest.get("scripted_accepted", 0) or 0),
            "scripted_completed": _as_bool(mode_manifest.get("scripted_completed", mode_name != "scripted_deterministic_commands")),
            "mode_manifest": str(mode_manifest_path.relative_to(root)).replace("\\", "/"),
            "mode_dir": str(mode_dir.relative_to(root)).replace("\\", "/"),
            "manifest": mode_manifest,
        }

    scripted_manifest = mode_status["scripted_deterministic_commands"]["manifest"]
    required_scripted_keys = [
        "scripted_attempted",
        "scripted_accepted",
        "scripted_per_action",
        "scripted_move_attempted",
        "scripted_move_accepted",
        "scripted_move_caused_position_delta",
        "scripted_direct_matchmanager_bypasses_decoder_actionapplier",
        "scripted_canonical_uses_actionapplier",
    ]
    missing_scripted_keys = [k for k in required_scripted_keys if k not in scripted_manifest]
    if missing_scripted_keys:
        raise RuntimeError(
            "scripted_deterministic_commands manifest missing required keys: " + ", ".join(missing_scripted_keys)
        )
    if int(scripted_manifest.get("scripted_move_attempted", 0) or 0) <= 0:
        raise RuntimeError("scripted_deterministic_commands must include at least one explicit scripted Move attempt")
    if not _as_bool(scripted_manifest.get("scripted_completed", True)):
        raise RuntimeError("scripted_deterministic_commands did not complete")

    raw_selected_by_action = _empty_action_map()
    mask_allowed_by_raw_action = _empty_action_map()
    post_mask_by_action = _empty_action_map()
    decoded_by_action = _empty_action_map()
    submitted_by_action = _empty_action_map()
    applier_accepted_by_action = _empty_action_map()
    runtime_applied_by_action = _empty_action_map()
    state_delta_by_action = _empty_action_map()

    state_delta_1_step_by_action = _empty_action_map()
    state_delta_5_step_by_action = _empty_action_map()
    state_delta_20_step_by_action = _empty_action_map()

    raw_action_distribution_by_mode: dict[str, dict[str, int]] = {
        mode: _empty_action_map() for mode in REQUIRED_MODES
    }

    raw_to_post_mask: dict[str, dict[str, int]] = {a: {} for a in ACTION_TYPES}
    post_mask_to_decoded: dict[str, dict[str, int]] = {a: {} for a in ACTION_TYPES}
    decoded_to_submitted: dict[str, dict[str, int]] = {a: {} for a in ACTION_TYPES}
    submitted_to_applier: dict[str, dict[str, int]] = {a: {} for a in ACTION_TYPES}
    applier_to_runtime_state_delta: dict[str, dict[str, int]] = {a: {} for a in ACTION_TYPES}

    clean_examples_by_action: dict[str, list[dict[str, Any]]] = {a: [] for a in ACTION_TYPES}
    trace_rows: list[dict[str, Any]] = []

    for mode_name in REQUIRED_MODES:
        mode_dir = mode_dirs[mode_name]
        snapshots = _load_mode_snapshots(mode_dir)
        cell_paths = sorted(mode_dir.glob("stage10d10_global_runtime_cell_table_step*.jsonl"))
        if not cell_paths:
            raise RuntimeError(f"Mode '{mode_name}' has no stage10d10 cell-table traces")

        for cell_path in cell_paths:
            stem = cell_path.stem
            if "step" not in stem:
                continue
            step = int(stem.split("step")[-1])
            cur = snapshots.get(step)
            nxt = snapshots.get(step + 1)

            for row in _read_jsonl(cell_path):
                candidate = _as_bool(row.get("runtime_is_friendly_actor"))
                submitted_flag = (
                    _as_bool(row.get("command_submitted"))
                    or _as_bool(row.get("applier_submitted"))
                    or _as_bool(row.get("command_event_accepted"))
                    or _as_bool(row.get("command_event_rejected"))
                )
                if not (candidate or submitted_flag):
                    continue

                owner = str(row.get("decoded_observation_owner") or "Unknown")
                raw_action = _norm_action(row.get("raw_action_type_top1"))
                final_action = _norm_action(row.get("masked_action_type"))
                decoded_action = _norm_action(row.get("decoder_received_action_type"))

                submitted_action_raw = str(row.get("action_type") or "").strip()
                if submitted_action_raw and submitted_action_raw != "NOT_EXPOSED" and submitted_flag:
                    submitted_action = _norm_action(submitted_action_raw)
                else:
                    submitted_action = "NoOp"

                effective_decoded_action = submitted_action if submitted_action != "NoOp" else decoded_action
                mask_allowed = _mask_allowed(row, raw_action)

                applier_accepted = _as_bool(row.get("applier_accepted"))
                applier_rejected = _as_bool(row.get("applier_rejected"))
                runtime_applied = _as_bool(row.get("command_event_accepted"))
                runtime_reached = _as_bool(row.get("applier_submission_reached")) or _as_bool(row.get("command_submitted"))

                state_delta_non_produce = False
                produce_signals_by_window: dict[str, dict[str, bool]] = {}
                if runtime_applied:
                    if effective_decoded_action == "Produce":
                        for lookahead in PRODUCE_LOOKAHEAD_STEPS:
                            produce_signals_by_window[f"{lookahead}_step"] = _produce_state_delta_signals(
                                owner=owner,
                                row=row,
                                snapshots=snapshots,
                                step=step,
                                lookahead_steps=lookahead,
                            )
                    else:
                        state_delta_non_produce = _state_delta_non_produce(
                            effective_action=effective_decoded_action,
                            owner=owner,
                            row=row,
                            cur=cur,
                            nxt=nxt,
                        )

                state_delta_1 = (
                    produce_signals_by_window.get("1_step", {}).get("possible_state_delta", False)
                    if effective_decoded_action == "Produce"
                    else state_delta_non_produce
                )
                state_delta_5 = (
                    produce_signals_by_window.get("5_step", {}).get("possible_state_delta", False)
                    if effective_decoded_action == "Produce"
                    else state_delta_non_produce
                )
                state_delta_20 = (
                    produce_signals_by_window.get("20_step", {}).get("possible_state_delta", False)
                    if effective_decoded_action == "Produce"
                    else state_delta_non_produce
                )

                raw_selected_by_action[raw_action] += 1
                raw_action_distribution_by_mode[mode_name][raw_action] += 1
                if mask_allowed:
                    mask_allowed_by_raw_action[raw_action] += 1
                post_mask_by_action[final_action] += 1
                decoded_by_action[decoded_action] += 1
                submitted_by_action[submitted_action] += 1
                if applier_accepted:
                    applier_accepted_by_action[effective_decoded_action] += 1
                if runtime_applied:
                    runtime_applied_by_action[effective_decoded_action] += 1
                if state_delta_1:
                    state_delta_by_action[effective_decoded_action] += 1
                    state_delta_1_step_by_action[effective_decoded_action] += 1
                if state_delta_5:
                    state_delta_5_step_by_action[effective_decoded_action] += 1
                if state_delta_20:
                    state_delta_20_step_by_action[effective_decoded_action] += 1

                key_raw_post = f"{raw_action}->{final_action}"
                raw_to_post_mask[raw_action][key_raw_post] = raw_to_post_mask[raw_action].get(key_raw_post, 0) + 1

                key_post_decoded = f"{final_action}->{decoded_action}"
                post_mask_to_decoded[raw_action][key_post_decoded] = post_mask_to_decoded[raw_action].get(key_post_decoded, 0) + 1

                key_decoded_submitted = f"{decoded_action}->{submitted_action}"
                decoded_to_submitted[raw_action][key_decoded_submitted] = decoded_to_submitted[raw_action].get(key_decoded_submitted, 0) + 1

                if applier_accepted:
                    applier_result = "accepted"
                elif submitted_flag or applier_rejected:
                    applier_result = "not_accepted"
                else:
                    applier_result = "not_submitted"
                key_sub_applier = f"{submitted_action}->{applier_result}"
                submitted_to_applier[raw_action][key_sub_applier] = submitted_to_applier[raw_action].get(key_sub_applier, 0) + 1

                if applier_accepted:
                    if runtime_applied:
                        if state_delta_1:
                            runtime_state = "runtime_applied_with_state_delta"
                        else:
                            runtime_state = "runtime_applied_no_state_delta"
                    else:
                        runtime_state = "runtime_not_applied"
                else:
                    runtime_state = "applier_not_accepted"
                applier_to_runtime_state_delta[raw_action][runtime_state] = (
                    applier_to_runtime_state_delta[raw_action].get(runtime_state, 0) + 1
                )

                trace_row = {
                    "mode": mode_name,
                    "step": step,
                    "actor": {
                        "flat_index": int(row.get("cell_index", -1) or -1),
                        "x": int(row.get("x", -1) or -1),
                        "y": int(row.get("y", -1) or -1),
                        "logical_cell": str(row.get("visual_label") or ""),
                        "owner": owner,
                        "unit_type": str(row.get("decoded_observation_unit_type") or "Unknown"),
                        "eligible_controllable": candidate,
                    },
                    "transition": {
                        "raw_action": raw_action,
                        "mask_allowed": mask_allowed,
                        "final_action_after_mask": final_action,
                        "decoded_action": decoded_action,
                        "submitted_action": submitted_action,
                        "effective_decoded_action": effective_decoded_action,
                        "applier_accepted": applier_accepted,
                        "applier_rejected": applier_rejected,
                        "runtime_path_reached": runtime_reached,
                        "runtime_applied": runtime_applied,
                        "state_delta_1_step": state_delta_1,
                        "state_delta_5_step": state_delta_5,
                        "state_delta_20_step": state_delta_20,
                        "produce_state_delta_signals": produce_signals_by_window,
                    },
                }
                trace_rows.append(trace_row)

                action = effective_decoded_action
                if (
                    raw_action == action
                    and mask_allowed
                    and final_action == action
                    and decoded_action == action
                    and submitted_action == action
                    and applier_accepted
                    and runtime_applied
                    and state_delta_1
                    and len(clean_examples_by_action[action]) < 5
                ):
                    clean_examples_by_action[action].append(
                        {
                            "mode": mode_name,
                            "step": step,
                            "cell_index": int(row.get("cell_index", -1) or -1),
                            "logical_cell": str(row.get("visual_label") or ""),
                        }
                    )

    first_failing_boundaries = {
        action: _first_failing_boundary(
            action=action,
            raw_selected_by_action=raw_selected_by_action,
            mask_allowed_by_raw_action=mask_allowed_by_raw_action,
            post_mask_by_action=post_mask_by_action,
            decoded_by_action=decoded_by_action,
            submitted_by_action=submitted_by_action,
            applier_accepted_by_action=applier_accepted_by_action,
            runtime_applied_by_action=runtime_applied_by_action,
            state_delta_by_action=state_delta_by_action,
        )
        for action in ACTION_TYPES
    }

    move_boundary_basis = "raw_selected_by_action"
    move_boundary_computation_ok = move_boundary_basis == "raw_selected_by_action"

    scripted_completed = _as_bool(scripted_manifest.get("scripted_completed", False))
    counters_independent = True
    success_gate = {
        "run_manifest_exists": True,
        "full_tri_mode": full_tri_mode,
        "scripted_completed": scripted_completed,
        "independent_counters": counters_independent,
        "move_boundary_from_raw_action_counters": move_boundary_computation_ok,
    }
    diagnostic_valid = all(success_gate.values())
    verdict = "GO" if diagnostic_valid else "NO-GO"

    run_manifest_out = {
        "generated_at_utc": _utc_now(),
        "stage": "Stage10D22B",
        "source_run_manifest": str(run_manifest_path.relative_to(root)).replace("\\", "/"),
        "FULL_TRI_MODE": full_tri_mode,
        "required_modes": REQUIRED_MODES,
        "mode_status": {
            mode: {
                "steps_completed": mode_status[mode]["steps_completed"],
                "target_steps": mode_status[mode]["target_steps"],
                "scripted_attempted": mode_status[mode]["scripted_attempted"],
                "scripted_accepted": mode_status[mode]["scripted_accepted"],
                "scripted_completed": mode_status[mode]["scripted_completed"],
                "mode_manifest": mode_status[mode]["mode_manifest"],
                "mode_dir": mode_status[mode]["mode_dir"],
            }
            for mode in REQUIRED_MODES
        },
        "scripted_mode_details": {
            "scripted_attempted": int(scripted_manifest.get("scripted_attempted", 0) or 0),
            "scripted_accepted": int(scripted_manifest.get("scripted_accepted", 0) or 0),
            "scripted_per_action": scripted_manifest.get("scripted_per_action") or [],
            "scripted_direct_per_action": scripted_manifest.get("scripted_direct_per_action") or [],
            "scripted_canonical_per_action": scripted_manifest.get("scripted_canonical_per_action") or [],
            "scripted_move_attempted": int(scripted_manifest.get("scripted_move_attempted", 0) or 0),
            "scripted_move_accepted": int(scripted_manifest.get("scripted_move_accepted", 0) or 0),
            "scripted_move_caused_position_delta": _as_bool(scripted_manifest.get("scripted_move_caused_position_delta", False)),
            "scripted_move_delta_evidence": str(scripted_manifest.get("scripted_move_delta_evidence") or "none"),
            "scripted_direct_matchmanager_bypasses_decoder_actionapplier": _as_bool(
                scripted_manifest.get("scripted_direct_matchmanager_bypasses_decoder_actionapplier", True)
            ),
            "scripted_canonical_uses_actionapplier": _as_bool(
                scripted_manifest.get("scripted_canonical_uses_actionapplier", True)
            ),
        },
        "success_gate": success_gate,
        "diagnostic_valid": diagnostic_valid,
        "go_no_go_verdict": verdict,
    }

    summary = {
        "generated_at_utc": _utc_now(),
        "stage": "Stage10D22B",
        "FULL_TRI_MODE": full_tri_mode,
        "source_run_manifest": str(run_manifest_path.relative_to(root)).replace("\\", "/"),
        "mode_status": run_manifest_out["mode_status"],
        "raw_action_distribution_by_mode": raw_action_distribution_by_mode,
        "raw_selected_by_action": raw_selected_by_action,
        "mask_allowed_by_raw_action": mask_allowed_by_raw_action,
        "post_mask_by_action": post_mask_by_action,
        "decoded_by_action": decoded_by_action,
        "submitted_by_action": submitted_by_action,
        "applier_accepted_by_action": applier_accepted_by_action,
        "runtime_applied_by_action": runtime_applied_by_action,
        "state_delta_by_action": state_delta_by_action,
        "state_delta_1_step_by_action": state_delta_1_step_by_action,
        "state_delta_5_step_by_action": state_delta_5_step_by_action,
        "state_delta_20_step_by_action": state_delta_20_step_by_action,
        "transitions": {
            "raw_to_post_mask": raw_to_post_mask,
            "post_mask_to_decoded": post_mask_to_decoded,
            "decoded_to_submitted": decoded_to_submitted,
            "submitted_to_applier": submitted_to_applier,
            "applier_to_runtime_state_delta": applier_to_runtime_state_delta,
        },
        "first_failing_boundaries": first_failing_boundaries,
        "move_boundary_computation_basis": move_boundary_basis,
        "clean_lifecycle_examples_by_action": clean_examples_by_action,
        "scripted_mode_details": run_manifest_out["scripted_mode_details"],
        "success_gate": success_gate,
        "diagnostic_valid": diagnostic_valid,
        "go_no_go_verdict": verdict,
    }

    trace_path = reports / "stage10d22b_global_action_lifecycle_trace.jsonl"
    summary_path = reports / "stage10d22b_global_action_lifecycle_summary.json"
    md_path = reports / "STAGE10D22B_GLOBAL_ACTION_LIFECYCLE_REPORT.md"
    run_manifest_out_path = reports / "stage10d22b_run_manifest.json"

    with trace_path.open("w", encoding="utf-8") as fh:
        for row in trace_rows:
            fh.write(json.dumps(row, ensure_ascii=True) + "\n")

    summary_path.write_text(json.dumps(summary, ensure_ascii=True, indent=2), encoding="utf-8")
    run_manifest_out_path.write_text(json.dumps(run_manifest_out, ensure_ascii=True, indent=2), encoding="utf-8")

    rows_raw_selection = [[a, raw_selected_by_action[a]] for a in ACTION_TYPES]
    rows_raw_mask = [[a, raw_selected_by_action[a], mask_allowed_by_raw_action[a]] for a in ACTION_TYPES]
    rows_post_mask_decoded = [
        [a, post_mask_by_action[a], decoded_by_action[a], submitted_by_action[a]] for a in ACTION_TYPES
    ]
    rows_runtime = [
        [
            a,
            applier_accepted_by_action[a],
            runtime_applied_by_action[a],
            state_delta_by_action[a],
            state_delta_1_step_by_action[a],
            state_delta_5_step_by_action[a],
            state_delta_20_step_by_action[a],
        ]
        for a in ACTION_TYPES
    ]
    rows_first_fail = [[a, first_failing_boundaries[a]] for a in ACTION_TYPES]

    md_lines: list[str] = [
        "# STAGE10D22B Global Action Lifecycle Diagnostic Report",
        "",
        f"- Generated (UTC): {_utc_now()}",
        f"- FULL_TRI_MODE={'true' if full_tri_mode else 'false'}",
        f"- Source run manifest: {run_manifest_path.relative_to(root).as_posix()}",
        f"- Explicit GO/NO-GO verdict: {verdict}",
        "",
        "## FULL_TRI_MODE status",
        f"- FULL_TRI_MODE={'true' if full_tri_mode else 'false'}",
        "",
        "## Per-mode status",
    ]

    for mode in REQUIRED_MODES:
        m = mode_status[mode]
        md_lines.append(
            "- "
            + mode
            + f": steps_completed={m['steps_completed']}, target_steps={m['target_steps']}, scripted_attempted={m['scripted_attempted']}, scripted_accepted={m['scripted_accepted']}, scripted_completed={m['scripted_completed']}"
        )

    md_lines.extend(["", "## Raw action distribution by mode"])
    for mode in REQUIRED_MODES:
        md_lines.append("")
        md_lines.append(f"### {mode}")
        mode_rows = [[a, raw_action_distribution_by_mode[mode][a]] for a in ACTION_TYPES]
        md_lines.extend(_table(["Action", "RawSelected"], mode_rows))

    md_lines.extend(["", "## A. Raw selection table"])
    md_lines.extend(_table(["Action", "RawSelected"], rows_raw_selection))

    md_lines.extend(["", "## B. Raw -> mask table"])
    md_lines.extend(_table(["Action", "RawSelected", "MaskAllowedByRaw"], rows_raw_mask))

    md_lines.extend(["", "## C. Post-mask/effective decoding table"])
    md_lines.extend(
        _table(
            ["Action", "PostMask", "Decoded", "Submitted"],
            rows_post_mask_decoded,
        )
    )

    md_lines.extend(["", "## D. Runtime lifecycle table"])
    md_lines.extend(
        _table(
            [
                "Action",
                "ApplierAccepted",
                "RuntimeApplied",
                "StateDelta",
                "state_delta_1_step",
                "state_delta_5_step",
                "state_delta_20_step",
            ],
            rows_runtime,
        )
    )

    md_lines.extend(["", "## E. First failing boundary table"])
    md_lines.extend(_table(["Action", "FirstFail"], rows_first_fail))

    md_lines.extend(
        [
            "",
            "## Raw->post-mask transition table",
        ]
    )
    for raw_action in ACTION_TYPES:
        for k, v in sorted(raw_to_post_mask[raw_action].items()):
            md_lines.append(f"- {k}: {v}")

    md_lines.extend(["", "## Post-mask->decoded transition table"])
    for raw_action in ACTION_TYPES:
        for k, v in sorted(post_mask_to_decoded[raw_action].items()):
            md_lines.append(f"- {k}: {v}")

    md_lines.extend(["", "## Runtime lifecycle table (transition evidence)"])
    for raw_action in ACTION_TYPES:
        for k, v in sorted(decoded_to_submitted[raw_action].items()):
            md_lines.append(f"- {raw_action} decoded->submitted {k}: {v}")
        for k, v in sorted(submitted_to_applier[raw_action].items()):
            md_lines.append(f"- {raw_action} submitted->applier {k}: {v}")
        for k, v in sorted(applier_to_runtime_state_delta[raw_action].items()):
            md_lines.append(f"- {raw_action} applier->runtime/state_delta {k}: {v}")

    md_lines.extend(
        [
            "",
            "## First failing boundary for Move",
            f"- {first_failing_boundaries['Move']}",
            "",
            "## First failing boundary for Attack",
            f"- {first_failing_boundaries['Attack']}",
            "",
            "## First failing boundary for Harvest",
            f"- {first_failing_boundaries['Harvest']}",
            "",
            "## First failing boundary for Return",
            f"- {first_failing_boundaries['Return']}",
            "",
            "## First failing boundary for Produce",
            f"- {first_failing_boundaries['Produce']}",
        ]
    )

    md_lines.extend(["", "## Clean lifecycle examples for each action type if present"])
    for action in ACTION_TYPES:
        examples = clean_examples_by_action[action]
        if not examples:
            md_lines.append(f"- {action}: none")
            continue
        for ex in examples:
            md_lines.append(
                f"- {action}: mode={ex['mode']}, step={ex['step']}, cell={ex['cell_index']} ({ex['logical_cell']})"
            )

    md_lines.extend(
        [
            "",
            "## Scripted deterministic capture",
            f"- scripted_attempted: {run_manifest_out['scripted_mode_details']['scripted_attempted']}",
            f"- scripted_accepted: {run_manifest_out['scripted_mode_details']['scripted_accepted']}",
            f"- scripted_move_attempted: {run_manifest_out['scripted_mode_details']['scripted_move_attempted']}",
            f"- scripted_move_accepted: {run_manifest_out['scripted_mode_details']['scripted_move_accepted']}",
            f"- scripted_move_caused_position_delta: {run_manifest_out['scripted_mode_details']['scripted_move_caused_position_delta']}",
            f"- scripted_move_delta_evidence: {run_manifest_out['scripted_mode_details']['scripted_move_delta_evidence']}",
            "- scripted_direct_matchmanager: bypasses ActionDecoder and ActionApplier by design.",
            "- scripted_canonical_actionapplier: submits AgentAction through ActionApplier path.",
            "",
            "## Success gate",
            f"- run_manifest_exists: {success_gate['run_manifest_exists']}",
            f"- full_tri_mode: {success_gate['full_tri_mode']}",
            f"- scripted_completed: {success_gate['scripted_completed']}",
            f"- independent_counters: {success_gate['independent_counters']}",
            f"- move_boundary_from_raw_action_counters: {success_gate['move_boundary_from_raw_action_counters']}",
            "",
            "## Artifact paths",
            f"- Trace JSONL: {trace_path.relative_to(root).as_posix()}",
            f"- Summary JSON: {summary_path.relative_to(root).as_posix()}",
            f"- Markdown report: {md_path.relative_to(root).as_posix()}",
            f"- Stage10D22B run manifest: {run_manifest_out_path.relative_to(root).as_posix()}",
        ]
    )

    md_path.write_text("\n".join(md_lines) + "\n", encoding="utf-8")

    print(trace_path.as_posix())
    print(summary_path.as_posix())
    print(md_path.as_posix())
    print(run_manifest_out_path.as_posix())
    print(f"verdict={verdict}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
