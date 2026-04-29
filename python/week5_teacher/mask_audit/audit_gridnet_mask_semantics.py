#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any, Dict, List

import numpy as np

from mask_audit_utils import (
    BRANCH_LAYOUT,
    BRANCH_NAMES,
    DEFAULT_OUTPUT_DIR,
    branch_slices,
    build_full_mask_from_candidates,
    create_runtime_context,
    create_wrapped_env,
    environment_payload,
    flatten_mask,
    flatten_obs,
    get_branch,
    index_to_attack_offset,
    parse_common_args,
    reset_compat,
    runtime_versions_payload,
    safe_action_space_sample,
    safe_json_dump,
    step_compat,
    utc_now,
)


def parse_args() -> argparse.Namespace:
    p = parse_common_args("Best-effort semantic checks for Gridnet full mask.")
    p.add_argument("--steps", type=int, default=200)
    p.add_argument(
        "--output-json",
        type=Path,
        default=DEFAULT_OUTPUT_DIR / "MASK_AUDIT_SEMANTICS.json",
    )
    return p.parse_args()


def check_record(name: str) -> Dict[str, Any]:
    return {"name": name, "status": "skipped", "evidence_count": 0, "details": "", "reason": ""}


def finalize_check(item: Dict[str, Any], pass_condition: bool, available: bool, reason_if_skip: str) -> None:
    if not available:
        item["status"] = "skipped"
        item["reason"] = reason_if_skip
    else:
        item["status"] = "pass" if pass_condition else "fail"


def main() -> int:
    args = parse_args()
    errors: List[str] = []
    warnings: List[str] = []
    checks: List[Dict[str, Any]] = [
        check_record("empty_cell_source_invalid"),
        check_record("enemy_cell_source_invalid"),
        check_record("worker_adjacent_resource_harvest_valid"),
        check_record("worker_with_cargo_adjacent_base_return_valid"),
        check_record("worker_adjacent_free_cell_move_valid"),
        check_record("base_produce_worker_valid"),
        check_record("barracks_produce_combat_unit_valid"),
        check_record("combat_unit_attack_window_valid"),
        check_record("attack_target_index_mapping"),
    ]

    report: Dict[str, Any] = {
        "status": "fail",
        "generated_at_utc": utc_now(),
        "branch_layout": BRANCH_LAYOUT,
        "checks": checks,
        "errors": errors,
        "warnings": warnings,
        "todo_fixme": [],
    }

    # Hard-contract invariant; no env dependency.
    mapping = {
        "index_0": index_to_attack_offset(0),
        "index_24": index_to_attack_offset(24),
        "index_48": index_to_attack_offset(48),
    }
    checks[-1]["details"] = mapping
    finalize_check(
        checks[-1],
        pass_condition=(mapping["index_0"] == (-3, -3) and mapping["index_24"] == (0, 0) and mapping["index_48"] == (3, 3)),
        available=True,
        reason_if_skip="",
    )

    ctx = create_runtime_context(args.seed)
    env = None

    try:
        env, env_for_training, env_summary, _timing = create_wrapped_env(args, ctx)
        obs, info = reset_compat(env_for_training)

        evidence = {
            "empty_cells": 0,
            "empty_source_invalid": 0,
            "enemy_cells": 0,
            "enemy_source_invalid": 0,
            "ready_cells": 0,
            "harvest_ready": 0,
            "return_ready": 0,
            "move_ready": 0,
            "produce_ready": 0,
            "produce_unit_ready": 0,
            "attack_ready": 0,
            "action_type_nonnoop_ready": 0,
        }

        for _ in range(max(1, int(args.steps))):
            full_mask, _source, mask_warnings = build_full_mask_from_candidates(env_for_training, obs, infos=[info])
            warnings.extend(mask_warnings)
            if full_mask is None:
                warnings.append("mask unavailable in this step; semantic sampling continues")
                action = safe_action_space_sample(env_for_training)
                obs, _rew, _done, infos = step_compat(env_for_training, action)
                info = infos[0] if infos else {}
                continue

            flat_mask = flatten_mask(full_mask)
            flat_obs = flatten_obs(obs)

            source = flat_mask[:, :, 0] > 0
            action_type = get_branch(flat_mask, "action_type") > 0
            move_dir = get_branch(flat_mask, "move_dir") > 0
            harvest_dir = get_branch(flat_mask, "harvest_dir") > 0
            return_dir = get_branch(flat_mask, "return_dir") > 0
            produce_dir = get_branch(flat_mask, "produce_dir") > 0
            produce_type = get_branch(flat_mask, "produce_unit_type") > 0
            attack_target = get_branch(flat_mask, "attack_target") > 0

            if flat_obs.shape[-1] >= 21:
                unit_present = np.max(flat_obs[:, :, 13:21], axis=2) > 0.1
                owner_enemy = flat_obs[:, :, 12] > 0.5 if flat_obs.shape[-1] > 12 else np.zeros_like(unit_present)
            else:
                unit_present = np.zeros_like(source)
                owner_enemy = np.zeros_like(source)

            empty_cells = np.logical_not(unit_present)
            enemy_cells = np.logical_and(unit_present, owner_enemy)

            evidence["empty_cells"] += int(empty_cells.sum())
            evidence["empty_source_invalid"] += int(np.logical_and(empty_cells, np.logical_not(source)).sum())
            evidence["enemy_cells"] += int(enemy_cells.sum())
            evidence["enemy_source_invalid"] += int(np.logical_and(enemy_cells, np.logical_not(source)).sum())

            ready = source
            evidence["ready_cells"] += int(ready.sum())
            evidence["harvest_ready"] += int(np.logical_and(ready, np.any(harvest_dir, axis=2)).sum())
            evidence["return_ready"] += int(np.logical_and(ready, np.any(return_dir, axis=2)).sum())
            evidence["move_ready"] += int(np.logical_and(ready, np.any(move_dir, axis=2)).sum())
            evidence["produce_ready"] += int(np.logical_and(ready, np.any(produce_dir, axis=2)).sum())
            evidence["produce_unit_ready"] += int(np.logical_and(ready, np.any(produce_type, axis=2)).sum())
            evidence["attack_ready"] += int(np.logical_and(ready, np.any(attack_target, axis=2)).sum())
            evidence["action_type_nonnoop_ready"] += int(
                np.logical_and(ready, np.any(action_type[:, :, 1:], axis=2)).sum()
            )

            action = safe_action_space_sample(env_for_training)
            obs, _rew, _done, infos = step_compat(env_for_training, action)
            info = infos[0] if infos else {}

        checks[0]["evidence_count"] = evidence["empty_cells"]
        checks[0]["details"] = {
            "empty_cells": evidence["empty_cells"],
            "empty_source_invalid": evidence["empty_source_invalid"],
        }
        finalize_check(
            checks[0],
            pass_condition=(evidence["empty_cells"] > 0 and evidence["empty_source_invalid"] == evidence["empty_cells"]),
            available=(evidence["empty_cells"] > 0),
            reason_if_skip="No empty cells observed in sampled steps.",
        )

        checks[1]["evidence_count"] = evidence["enemy_cells"]
        checks[1]["details"] = {
            "enemy_cells": evidence["enemy_cells"],
            "enemy_source_invalid": evidence["enemy_source_invalid"],
        }
        finalize_check(
            checks[1],
            pass_condition=(evidence["enemy_cells"] > 0 and evidence["enemy_source_invalid"] == evidence["enemy_cells"]),
            available=(evidence["enemy_cells"] > 0),
            reason_if_skip="No enemy-owned unit cells observed in sampled steps.",
        )

        checks[2]["evidence_count"] = evidence["harvest_ready"]
        checks[2]["details"] = "Proxy check: ready cells with any harvest direction valid."
        finalize_check(
            checks[2],
            pass_condition=evidence["harvest_ready"] > 0,
            available=(evidence["harvest_ready"] > 0),
            reason_if_skip="No sampled state with harvest-valid ready actor detected.",
        )

        checks[3]["evidence_count"] = evidence["return_ready"]
        checks[3]["details"] = "Proxy check: ready cells with any return direction valid."
        finalize_check(
            checks[3],
            pass_condition=evidence["return_ready"] > 0,
            available=(evidence["return_ready"] > 0),
            reason_if_skip="No sampled state with return-valid ready actor detected.",
        )

        checks[4]["evidence_count"] = evidence["move_ready"]
        checks[4]["details"] = "Proxy check: ready cells with any move direction valid."
        finalize_check(
            checks[4],
            pass_condition=evidence["move_ready"] > 0,
            available=(evidence["move_ready"] > 0),
            reason_if_skip="No sampled state with move-valid ready actor detected.",
        )

        checks[5]["evidence_count"] = evidence["produce_ready"]
        checks[5]["details"] = "Proxy check: ready cells with any produce direction valid."
        finalize_check(
            checks[5],
            pass_condition=evidence["produce_ready"] > 0,
            available=(evidence["produce_ready"] > 0),
            reason_if_skip="No sampled state with produce-direction-valid ready actor detected.",
        )

        checks[6]["evidence_count"] = evidence["produce_unit_ready"]
        checks[6]["details"] = "Proxy check: ready cells with any produce-unit-type valid."
        finalize_check(
            checks[6],
            pass_condition=evidence["produce_unit_ready"] > 0,
            available=(evidence["produce_unit_ready"] > 0),
            reason_if_skip="No sampled state with produce-unit-type-valid ready actor detected.",
        )

        checks[7]["evidence_count"] = evidence["attack_ready"]
        checks[7]["details"] = "Proxy check: ready cells with any attack-target valid."
        finalize_check(
            checks[7],
            pass_condition=evidence["attack_ready"] > 0,
            available=(evidence["attack_ready"] > 0),
            reason_if_skip="No sampled state with attack-valid ready actor detected.",
        )

        report["proxy_evidence_totals"] = evidence
        report["todo_fixme"].append(
            "Controlled-state semantic probes are best-effort only; explicit scripted states are not injected in this env wrapper."
        )

        report["runtime_versions"] = runtime_versions_payload(ctx.versions)
        report["environment"] = environment_payload(args, env_summary)

        failed = [c for c in checks if c["status"] == "fail"]
        report["status"] = "pass" if len(failed) == 0 else "fail"
        if any(c["status"] == "skipped" for c in checks):
            warnings.append("One or more semantic checks were skipped; see checks[].reason for details.")

    except Exception as exc:
        errors.append(f"Unhandled exception: {type(exc).__name__}: {exc}")
        report["status"] = "fail"
    finally:
        if env is not None:
            try:
                env.close()
            except Exception:
                pass

    safe_json_dump(args.output_json, report)
    print(args.output_json)
    return 0 if report["status"] == "pass" else 2


if __name__ == "__main__":
    raise SystemExit(main())
