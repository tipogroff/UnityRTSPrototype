from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict

from load_student_checkpoint import load_student_transfer_checkpoint
from student_branch_contract import ACTION_CONTRACT_VERSION
from student_inference_adapter import _load_observation, run_inference_with_loaded_model


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Week 6 Day 5 persistent student inference bridge: "
            "loads checkpoint once and serves repeated Unity observation requests"
        )
    )
    parser.add_argument("--checkpoint", type=Path, required=True, help="Path to student_bc_transfer_best.pt")
    parser.add_argument("--device", type=str, default="cpu", help="Torch device for inference (default: cpu)")
    return parser.parse_args()


def write_result(path: Path, result: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, ensure_ascii=True, indent=2), encoding="utf-8")


def print_json(payload: Dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=True), flush=True)


def main() -> int:
    args = parse_args()

    try:
        model, checkpoint_meta = load_student_transfer_checkpoint(args.checkpoint, device=args.device)
    except Exception as exc:
        print_json(
            {
                "status": "error",
                "error": f"Failed to load checkpoint: {exc}",
            }
        )
        return 1

    print_json(
        {
            "status": "ready",
            "action_contract_version": ACTION_CONTRACT_VERSION,
            "checkpoint_path": str(args.checkpoint.resolve()),
            "checkpoint_epoch": checkpoint_meta.get("epoch"),
            "checkpoint_model_variant": checkpoint_meta.get("model_variant"),
        }
    )

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue

        request_id = -1
        try:
            request = json.loads(line)
            request_id = int(request.get("request_id", -1))
            command = str(request.get("command", "infer"))

            if command == "shutdown":
                print_json({"status": "ok", "request_id": request_id, "message": "shutdown"})
                return 0

            observation_bin = Path(request["observation_bin"])
            output_json = Path(request["output_json"])

            obs_hwc = _load_observation(observation_bin)
            result = run_inference_with_loaded_model(model, checkpoint_meta, obs_hwc, device=args.device)
            result["checkpoint_path"] = str(args.checkpoint.resolve())
            result["observation_bin"] = str(observation_bin.resolve())
            write_result(output_json, result)

            if result["status"] != "ok":
                print_json(
                    {
                        "status": "error",
                        "request_id": request_id,
                        "output_json": str(output_json.resolve()),
                        "error": result.get("error", "unknown inference error"),
                    }
                )
                continue

            print_json(
                {
                    "status": "ok",
                    "request_id": request_id,
                    "output_json": str(output_json.resolve()),
                }
            )
        except Exception as exc:
            print_json(
                {
                    "status": "error",
                    "request_id": request_id,
                    "error": str(exc),
                }
            )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())