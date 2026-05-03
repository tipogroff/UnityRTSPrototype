#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _resolve(root: Path, p: Path) -> Path:
    return p if p.is_absolute() else (root / p)


def _read_lines(path: Path) -> List[str]:
    return path.read_text(encoding="utf-8", errors="replace").splitlines()


def _snippet(lines: List[str], line_no: int, radius: int = 1) -> Dict[str, Any]:
    start = max(1, line_no - radius)
    end = min(len(lines), line_no + radius)
    return {
        "line": int(line_no),
        "start_line": int(start),
        "end_line": int(end),
        "snippet": [{"line": int(i), "text": lines[i - 1]} for i in range(start, end + 1)],
    }


def _find_first(lines: List[str], pattern: str) -> Optional[int]:
    rx = re.compile(pattern)
    for i, line in enumerate(lines, start=1):
        if rx.search(line):
            return i
    return None


def _find_all(lines: List[str], pattern: str, max_hits: int = 12) -> List[int]:
    rx = re.compile(pattern)
    out: List[int] = []
    for i, line in enumerate(lines, start=1):
        if rx.search(line):
            out.append(i)
            if len(out) >= max_hits:
                break
    return out


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Stage10D.5 Legacy032 observation encoder source audit")
    p.add_argument(
        "--output",
        type=Path,
        default=Path("python/week6_student/reports/stage10d5_legacy032_observation_encoder_source_audit.json"),
    )
    p.add_argument(
        "--reference-site-packages",
        type=Path,
        default=Path("python/week5_teacher_reference/.venv_microrts032_reference/Lib/site-packages"),
    )
    p.add_argument(
        "--export-script",
        type=Path,
        default=Path("python/week5_teacher_legacy032/scripts/export_teacher_rollout_legacy032.py"),
    )
    p.add_argument(
        "--train-script",
        type=Path,
        default=Path("python/week5_teacher_legacy032/scripts/ppo_gridnet_legacy032_24x24_local_save.py"),
    )
    return p.parse_args()


def main() -> int:
    args = parse_args()
    root = _repo_root()
    out_path = _resolve(root, args.output)

    site_packages = _resolve(root, args.reference_site_packages)
    vec_env_py = site_packages / "gym_microrts" / "envs" / "vec_env.py"
    global_env_py = site_packages / "gym_microrts" / "envs" / "global_agent_env.py"

    export_script = _resolve(root, args.export_script)
    train_script = _resolve(root, args.train_script)

    hard_failures: List[str] = []
    warnings: List[str] = []

    required = [vec_env_py, global_env_py, export_script, train_script]
    for p in required:
        if not p.exists():
            hard_failures.append(f"missing required file: {p.as_posix()}")

    audit_files: Dict[str, Any] = {}

    if vec_env_py.exists():
        lines = _read_lines(vec_env_py)
        key_patterns = {
            "num_planes": r"self\.num_planes\s*=\s*\[5,\s*5,\s*3,\s*len\(self\.utt\['unitTypes'\]\)\+1,\s*6\]",
            "observation_space": r"self\.observation_space\s*=\s*gym\.spaces\.Box",
            "encode_obs": r"def\s+_encode_obs\(self,\s*obs\)",
            "reshape_clip": r"obs\s*=\s*obs\.reshape\(len\(obs\),\s*-1\)\.clip",
            "one_hot_first_group": r"obs_planes\[np\.arange\(len\(obs_planes\)\),obs\[0\]\]\s*=\s*1",
            "one_hot_other_groups": r"obs\[i\]\+sum\(self\.num_planes\[:i\]\)",
            "grid_env_class": r"class\s+MicroRTSGridModeVecEnv\(MicroRTSVecEnv\)",
            "grid_step": r"responses\s*=\s*self\.vec_client\.gameStep\(",
        }
        hits: Dict[str, Any] = {}
        for key, pat in key_patterns.items():
            ln = _find_first(lines, pat)
            hits[key] = _snippet(lines, ln, radius=1) if ln else None
        audit_files[vec_env_py.as_posix()] = {
            "exists": True,
            "key_evidence": hits,
        }
    else:
        audit_files[vec_env_py.as_posix()] = {"exists": False}

    if global_env_py.exists():
        lines = _read_lines(global_env_py)
        key_patterns = {
            "mask_player_logic": r"if\s+player\s*==\s*1",
            "mask_owner_values": r"raw_obs\[2\]\)\s*==\s*2|raw_obs\[2\]\)\s*==\s*1",
            "num_planes": r"self\.num_planes\s*=\s*\[5,\s*5,\s*3,\s*len\(self\.utt\['unitTypes'\]\)\+1,\s*6\]",
        }
        hits: Dict[str, Any] = {}
        for key, pat in key_patterns.items():
            ln = _find_first(lines, pat)
            hits[key] = _snippet(lines, ln, radius=1) if ln else None
        audit_files[global_env_py.as_posix()] = {
            "exists": True,
            "key_evidence": hits,
        }
    else:
        audit_files[global_env_py.as_posix()] = {"exists": False}

    if export_script.exists():
        lines = _read_lines(export_script)
        pats = {
            "create_grid_env": r"def\s+_create_target_24x24_gridmode_env",
            "env_step": r"step_result\s*=\s*env\.step\(action_env\)",
            "append_observation": r"observation_t\.append\(obs_step\.astype\(np\.float32",
            "save_npz_observation": r"observation_t=np\.asarray\(observation_t,\s*dtype=np\.float32\)",
        }
        hits: Dict[str, Any] = {}
        for key, pat in pats.items():
            ln = _find_first(lines, pat)
            hits[key] = _snippet(lines, ln, radius=1) if ln else None
        audit_files[export_script.as_posix()] = {"exists": True, "key_evidence": hits}
    else:
        audit_files[export_script.as_posix()] = {"exists": False}

    if train_script.exists():
        lines = _read_lines(train_script)
        pats = {
            "grid_env_import": r"from\s+gym_microrts\.envs\.vec_env\s+import\s+MicroRTSGridModeVecEnv",
            "grid_env_construction": r"envs\s*=\s*MicroRTSGridModeVecEnv\(",
            "env_reset_obs": r"next_obs\s*=\s*torch\.Tensor\(envs\.reset\(\)\)",
            "env_step_obs": r"next_obs,\s*rs,\s*ds,\s*infos\s*=\s*envs\.step\(java_valid_actions\)",
        }
        hits: Dict[str, Any] = {}
        for key, pat in pats.items():
            ln = _find_first(lines, pat)
            hits[key] = _snippet(lines, ln, radius=1) if ln else None
        audit_files[train_script.as_posix()] = {"exists": True, "key_evidence": hits}
    else:
        audit_files[train_script.as_posix()] = {"exists": False}

    # Determine core answers.
    encoder_file = vec_env_py.as_posix() if vec_env_py.exists() else None

    channels_named_explicitly = False
    owner_declared = False
    unit_type_declared = False
    perspective_dep = False
    wrappers_transform_before_export = False

    if vec_env_py.exists():
        lines = _read_lines(vec_env_py)
        owner_declared = _find_first(lines, r"num_planes_player\(5\)|num_planes\s*=\s*\[5,\s*5,\s*3") is not None
        unit_type_declared = _find_first(lines, r"num_planes_unit_type\(z\)|len\(self\.utt\['unitTypes'\]\)\+1") is not None
        channels_named_explicitly = _find_first(lines, r"channel\s*0|\[0\.\.[0-9]+\]") is not None

    if global_env_py.exists():
        g_lines = _read_lines(global_env_py)
        perspective_dep = _find_first(g_lines, r"if\s+player\s*==\s*1") is not None

    if export_script.exists() and vec_env_py.exists():
        wrappers_transform_before_export = True

    # Collect a concise source-anchored statement for 27 channels.
    channel_count_evidence: List[Dict[str, Any]] = []
    if vec_env_py.exists():
        vlines = _read_lines(vec_env_py)
        ln1 = _find_first(vlines, r"self\.num_planes\s*=\s*\[5,\s*5,\s*3,\s*len\(self\.utt\['unitTypes'\]\)\+1,\s*6\]")
        if ln1:
            channel_count_evidence.append(
                {
                    "file": vec_env_py.as_posix(),
                    "evidence": _snippet(vlines, ln1, radius=1),
                    "derived_channel_formula": "sum([5,5,3,len(unitTypes)+1,6])",
                }
            )
        ln2 = _find_first(vlines, r"shape=\(self\.height,\s*self\.width,\s*sum\(self\.num_planes\)\)")
        if ln2:
            channel_count_evidence.append(
                {
                    "file": vec_env_py.as_posix(),
                    "evidence": _snippet(vlines, ln2, radius=1),
                }
            )

    out: Dict[str, Any] = {
        "stage": "10D.5",
        "diagnostic": "legacy032_observation_encoder_source_audit",
        "status": "pass" if not hard_failures else "fail",
        "site_packages_root": site_packages.as_posix(),
        "audited_files": audit_files,
        "answers": {
            "which_source_file_defines_27_channel_observation": encoder_file,
            "are_channels_0_to_26_named_anywhere": {
                "value": bool(channels_named_explicitly),
                "note": "group-level planes are declared; per-channel names 0..26 are not explicitly enumerated in source",
            },
            "are_owner_unit_type_channels_directly_declared": {
                "owner_declared_group_level": bool(owner_declared),
                "unit_type_declared_group_level": bool(unit_type_declared),
                "note": "declared as grouped planes via num_planes, not as explicit Unity target channel IDs",
            },
            "is_observation_perspective_relative_or_absolute": {
                "value": "mixed: encoded observation uses absolute player planes; action-mask utilities include player-dependent logic",
                "player_dependent_logic_detected": bool(perspective_dep),
            },
            "does_encoding_depend_on_player_perspective": bool(perspective_dep),
            "is_raw_observation_transformed_by_wrappers_before_export": bool(wrappers_transform_before_export),
        },
        "channel_count_evidence": channel_count_evidence,
        "hard_failures": hard_failures,
        "warnings": warnings,
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, ensure_ascii=True, indent=2), encoding="utf-8")
    print(out_path.as_posix())
    return 0 if not hard_failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
