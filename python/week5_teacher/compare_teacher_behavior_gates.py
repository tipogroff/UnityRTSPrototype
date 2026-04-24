#!/usr/bin/env python3
"""
compare_teacher_behavior_gates.py

Comparison table across multiple teacher_behavior_gate.py JSON outputs.

Usage
-----
    python compare_teacher_behavior_gates.py gate_A.json gate_B.json [gate_C.json ...]
    python compare_teacher_behavior_gates.py WEEK5R/gate_*.json

Output: sorted comparison table (PASS > SUSPICIOUS > FAIL) printed to stdout.
Optional: --output-md to write a Markdown version.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

# Status sort order: lower number = better / displayed first
_STATUS_ORDER = {
    "PASS": 0,
    "SUSPICIOUS": 1,
    "FAIL_COLLAPSED_NOOP": 2,
    "FAIL_FALSE_FULL_TENSOR_MOVE": 3,
    "FAIL_NO_EFFECT_BEHAVIOR": 4,
}
_UNKNOWN_ORDER = 9


def status_rank(status: str) -> int:
    return _STATUS_ORDER.get(status, _UNKNOWN_ORDER)


def load_gate(path: Path) -> Dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {
            "_load_error": str(exc),
            "_path": str(path),
            "schema_version": "unknown",
            "checkpoint": str(path),
            "status": "LOAD_ERROR",
            "fail_reasons": [],
            "warnings": [],
            "actor_level": {},
            "effective_behavior": {},
        }
    data["_path"] = str(path)
    return data


def extract_row(g: Dict[str, Any]) -> Dict[str, Any]:
    """Extract flat comparison fields from a gate JSON."""
    actor = g.get("actor_level", {})
    eff = g.get("effective_behavior", {})

    full_move = actor.get("full_tensor_move_share", float("nan"))
    actor_move = actor.get("actor_level_move_share", float("nan"))
    actor_noop = actor.get("actor_noop_share", float("nan"))

    gap = float("nan")
    try:
        if full_move == full_move and actor_move == actor_move:  # not NaN
            gap = full_move - actor_move
    except Exception:
        pass

    pos_delta = eff.get("effective_position_delta_count", -1)
    no_eff = eff.get("no_effect_action_share", float("nan"))

    ckpt = g.get("checkpoint", g.get("_path", "unknown"))
    # Shorten checkpoint path to last two components for display
    try:
        ckpt_short = "/".join(Path(ckpt).parts[-2:])
    except Exception:
        ckpt_short = ckpt

    status = g.get("status", "UNKNOWN")
    fail_reasons = g.get("fail_reasons", [])
    fail_short = "; ".join(
        r.split(":")[0] for r in fail_reasons
    ) if fail_reasons else ""

    return {
        "checkpoint": ckpt_short,
        "checkpoint_full": ckpt,
        "status": status,
        "actor_level_move_share": actor_move,
        "actor_noop_share": actor_noop,
        "full_tensor_move_share": full_move,
        "full_vs_actor_move_gap": gap,
        "effective_position_delta_count": pos_delta,
        "no_effect_action_share": no_eff,
        "fail_short": fail_short,
        "_status_rank": status_rank(status),
    }


def pct(v: Any) -> str:
    try:
        if v != v:  # NaN
            return "n/a"
        return f"{float(v) * 100.0:.2f}%"
    except Exception:
        return str(v)


def fmt_int(v: Any) -> str:
    if v == -1:
        return "n/a"
    try:
        return str(int(v))
    except Exception:
        return str(v)


def build_table_lines(rows: List[Dict[str, Any]], verbose: bool = False) -> List[str]:
    lines: List[str] = []

    # Header
    lines.append(
        f"{'checkpoint':<40}  {'status':<30}  "
        f"{'actor_move':>10}  {'actor_noop':>10}  "
        f"{'full_move':>10}  {'gap(f-a)':>10}  "
        f"{'pos_delta':>9}  {'no_eff':>8}"
    )
    lines.append("-" * 145)

    for row in rows:
        ckpt = row["checkpoint"]
        if len(ckpt) > 38:
            ckpt = "…" + ckpt[-37:]
        status = row["status"]
        lines.append(
            f"{ckpt:<40}  {status:<30}  "
            f"{pct(row['actor_level_move_share']):>10}  "
            f"{pct(row['actor_noop_share']):>10}  "
            f"{pct(row['full_tensor_move_share']):>10}  "
            f"{pct(row['full_vs_actor_move_gap']):>10}  "
            f"{fmt_int(row['effective_position_delta_count']):>9}  "
            f"{pct(row['no_effect_action_share']):>8}"
        )
        if row["fail_short"]:
            lines.append(f"    ↳ FAIL: {row['fail_short']}")
        if verbose and row.get("checkpoint_full") != row.get("checkpoint"):
            lines.append(f"    path: {row['checkpoint_full']}")

    return lines


def build_markdown(rows: List[Dict[str, Any]]) -> str:
    lines: List[str] = []
    lines.append("# Teacher Behavior Gate — Comparison Table")
    lines.append("")
    lines.append(
        "| checkpoint | status | actor_move | actor_noop | "
        "full_move | gap(full−actor) | pos_delta | no_eff_share |"
    )
    lines.append(
        "|---|---|---|---|---|---|---|---|"
    )
    for row in rows:
        ckpt = row["checkpoint"]
        status = row["status"]
        fail_note = f" ← {row['fail_short']}" if row["fail_short"] else ""
        lines.append(
            f"| {ckpt} | **{status}**{fail_note} | "
            f"{pct(row['actor_level_move_share'])} | "
            f"{pct(row['actor_noop_share'])} | "
            f"{pct(row['full_tensor_move_share'])} | "
            f"{pct(row['full_vs_actor_move_gap'])} | "
            f"{fmt_int(row['effective_position_delta_count'])} | "
            f"{pct(row['no_effect_action_share'])} |"
        )
    lines.append("")
    lines.append("**Sort order**: PASS → SUSPICIOUS → FAIL_COLLAPSED_NOOP → "
                 "FAIL_FALSE_FULL_TENSOR_MOVE → FAIL_NO_EFFECT_BEHAVIOR")
    lines.append("")
    lines.append("**gap(full−actor)**: positive gap indicates spurious full-tensor Move signal "
                 "not reflected in actor-level chosen behavior.")
    lines.append("")
    lines.append(
        "> **Note**: Actor-level Move share is the authoritative signal. "
        "Full-tensor Move share alone is NOT evidence of real movement. "
        "This table does not claim Gym→Unity semantic parity."
    )
    return "\n".join(lines) + "\n"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Compare multiple teacher behavior gate JSON outputs."
    )
    p.add_argument(
        "gate_jsons",
        nargs="+",
        type=Path,
        metavar="GATE_JSON",
        help="One or more gate JSON files produced by teacher_behavior_gate.py.",
    )
    p.add_argument(
        "--output-md",
        type=Path,
        default=None,
        help="Optional: write Markdown comparison table to this file.",
    )
    p.add_argument(
        "--verbose",
        action="store_true",
        help="Print full checkpoint paths in console table.",
    )
    return p.parse_args()


def main() -> int:
    args = parse_args()

    gate_paths = list(args.gate_jsons)
    if not gate_paths:
        print("[compare] No gate JSON files provided.", file=sys.stderr)
        return 1

    loaded = [load_gate(p) for p in gate_paths]
    rows = [extract_row(g) for g in loaded]
    rows.sort(key=lambda r: (r["_status_rank"], r["checkpoint"]))

    # Console output
    print(f"\nTeacher Behavior Gate — Comparison ({len(rows)} checkpoint(s))\n")
    for line in build_table_lines(rows, verbose=args.verbose):
        print(line)
    print()

    # Count by status
    from collections import Counter
    status_counts: Counter = Counter(r["status"] for r in rows)
    print("Summary:")
    for st, n in sorted(status_counts.items(), key=lambda x: status_rank(x[0])):
        print(f"  {st}: {n}")
    print()

    # Markdown output
    if args.output_md:
        args.output_md.parent.mkdir(parents=True, exist_ok=True)
        args.output_md.write_text(build_markdown(rows), encoding="utf-8")
        print(f"wrote markdown  = {args.output_md}")

    # Exit code: 0 if at least one PASS, 2 if all are FAIL, 1 otherwise
    has_pass = any(r["status"] == "PASS" for r in rows)
    all_fail = all(r["status"].startswith("FAIL") for r in rows)
    if has_pass:
        return 0
    if all_fail:
        return 2
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
