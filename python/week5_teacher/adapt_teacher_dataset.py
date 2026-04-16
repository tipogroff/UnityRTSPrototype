#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path

from day4_dataset_adapter import AdaptationConfig, run_adaptation


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Week 5 Day 4 adapter: convert Day 3 raw teacher rollouts into Unity-contract-aligned "
            "adapted dataset artifacts with explicit conversion reporting."
        )
    )
    parser.add_argument(
        "--input-batch-dir",
        type=Path,
        required=True,
        help="Path to Day 3 raw batch directory (must contain episode_*.npz and batch.summary.json).",
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=None,
        help="Output root directory. Defaults to <project>/python/week5_teacher/teacher_exports.",
    )
    parser.add_argument(
        "--output-batch-name",
        default=None,
        help="Optional output batch folder name. Defaults to teacher_adapted_<raw_batch_name>_<timestamp>.",
    )
    parser.add_argument(
        "--allow-spatial-resize",
        action="store_true",
        help="Allow approximate spatial crop/pad when observation HxW is not exactly 24x24.",
    )
    parser.add_argument(
        "--write-debug-jsonl",
        action="store_true",
        help="Write per-step conversion_debug.jsonl for diagnostics.",
    )
    parser.add_argument(
        "--hp-divisor",
        type=float,
        default=None,
        help="Optional explicit divisor for observation HP normalization channel [0].",
    )
    parser.add_argument(
        "--resource-divisor",
        type=float,
        default=None,
        help="Optional explicit divisor for observation resources normalization channel [1].",
    )
    return parser.parse_args()


def default_output_root(input_batch_dir: Path) -> Path:
    return input_batch_dir.parent.parent / "teacher_exports"


def build_output_batch_name(raw_batch_name: str) -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"teacher_adapted_{raw_batch_name}_{timestamp}"


def main() -> None:
    args = parse_args()
    input_batch_dir = args.input_batch_dir.resolve()
    if not input_batch_dir.exists():
        raise FileNotFoundError(f"Input batch directory does not exist: {input_batch_dir}")

    output_root = (args.output_root.resolve() if args.output_root is not None else default_output_root(input_batch_dir))
    raw_batch_name = input_batch_dir.name
    output_batch_name = args.output_batch_name or build_output_batch_name(raw_batch_name)
    output_batch_dir = output_root / output_batch_name

    config = AdaptationConfig(
        allow_spatial_resize=bool(args.allow_spatial_resize),
        write_debug_jsonl=bool(args.write_debug_jsonl),
        hp_divisor=args.hp_divisor,
        resource_divisor=args.resource_divisor,
    )

    result = run_adaptation(
        input_batch_dir=input_batch_dir,
        output_batch_dir=output_batch_dir,
        config=config,
    )

    print("Day 4 adaptation completed.")
    print(f"Input batch: {result['input_batch_dir']}")
    print(f"Output batch: {result['output_batch_dir']}")
    print(f"Report: {result['conversion_report_path']}")
    if result.get("conversion_debug_jsonl_path"):
        print(f"Debug JSONL: {result['conversion_debug_jsonl_path']}")


if __name__ == "__main__":
    main()
