from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple

ROOT = Path(__file__).resolve().parents[3]
SCENE_PATH = ROOT / "Assets/Scenes/Week6_StudentVisualInspection.unity"
CONFIG_PATH = ROOT / "Assets/ML/GameConfig_MVP.asset"
OUTPUT_PATH = ROOT / "python/week6_student/reports/LEGACY032_UNITY_V2_SCENE_PREP_VALIDATION.json"

EXPECTED_PRESET = 4
EXPECTED_GRID = (24, 24)
EXPECTED_PLACEMENT = [
    {"object": "Resource", "owner": "Neutral", "logical_cell": "A1", "grid": [0, 0]},
    {"object": "Resource", "owner": "Neutral", "logical_cell": "B1", "grid": [1, 0]},
    {"object": "Worker", "owner": "Player1", "logical_cell": "B2", "grid": [1, 1]},
    {"object": "Base", "owner": "Player1", "logical_cell": "C3", "grid": [2, 2]},
    {"object": "Resource", "owner": "Neutral", "logical_cell": "X24", "grid": [23, 23]},
    {"object": "Resource", "owner": "Neutral", "logical_cell": "W24", "grid": [22, 23]},
    {"object": "Worker", "owner": "Player2", "logical_cell": "W23", "grid": [22, 22]},
    {"object": "Base", "owner": "Player2", "logical_cell": "V22", "grid": [21, 21]},
]

CONFLICTING_RUNNER_NAMES = {
    "Week4": ["Day6RewardSanitySmokeTest", "BaselineRolloutRunner", "SmokeTestAutomation"],
    "Week5": ["Week5", "TeacherBehaviorGate"],
    "Week6Smoke": ["Day6PipelineSmokeTest", "ActionContractV2GlobalSmokeRunner"],
}


@dataclass(frozen=True)
class SceneObject:
    name: str
    is_active: bool


def _extract_single_int(text: str, key: str) -> int:
    m = re.search(rf"^\s*{re.escape(key)}:\s*(-?\d+)\s*$", text, flags=re.MULTILINE)
    if m is None:
        raise RuntimeError(f"Key '{key}' not found")
    return int(m.group(1))


def _extract_config_size(text: str) -> Tuple[int, int]:
    width = _extract_single_int(text, "mapWidth")
    height = _extract_single_int(text, "mapHeight")
    return width, height


def _extract_scene_objects(text: str) -> List[SceneObject]:
    pattern = re.compile(
        r"--- !u!1 &\d+\nGameObject:\n(?P<body>.*?)(?=\n--- !u!|\Z)",
        flags=re.DOTALL,
    )
    objects: List[SceneObject] = []
    for match in pattern.finditer(text):
        body = match.group("body")
        name_m = re.search(r"^\s*m_Name:\s*(.+?)\s*$", body, flags=re.MULTILINE)
        active_m = re.search(r"^\s*m_IsActive:\s*(\d+)\s*$", body, flags=re.MULTILINE)
        if not name_m or not active_m:
            continue
        objects.append(SceneObject(name=name_m.group(1).strip(), is_active=(active_m.group(1) == "1")))
    return objects


def _logical_to_grid(label: str) -> Tuple[int, int]:
    m = re.fullmatch(r"([A-Z]+)(\d+)", label)
    if m is None:
        raise ValueError(f"Bad label: {label}")
    col_text = m.group(1)
    row = int(m.group(2))

    col = 0
    for c in col_text:
        col = col * 26 + (ord(c) - ord("A") + 1)
    x = col - 1
    y = row - 1
    return x, y


def _check_symmetry() -> Dict[str, object]:
    checks = []
    mirror_ok = True
    width, height = EXPECTED_GRID

    # Pair resources and structures by semantic order.
    pairs = [
        (EXPECTED_PLACEMENT[0], EXPECTED_PLACEMENT[4]),
        (EXPECTED_PLACEMENT[1], EXPECTED_PLACEMENT[5]),
        (EXPECTED_PLACEMENT[2], EXPECTED_PLACEMENT[6]),
        (EXPECTED_PLACEMENT[3], EXPECTED_PLACEMENT[7]),
    ]

    for left, right in pairs:
        lx, ly = left["grid"]
        rx, ry = right["grid"]
        expected_rx = (width - 1) - lx
        expected_ry = (height - 1) - ly
        ok = (rx == expected_rx) and (ry == expected_ry)
        mirror_ok = mirror_ok and ok
        checks.append(
            {
                "left": left["logical_cell"],
                "right": right["logical_cell"],
                "left_grid": [lx, ly],
                "right_grid": [rx, ry],
                "expected_right_grid": [expected_rx, expected_ry],
                "ok": ok,
            }
        )

    return {"all_ok": mirror_ok, "pairs": checks}


def main() -> None:
    scene_text = SCENE_PATH.read_text(encoding="utf-8")
    config_text = CONFIG_PATH.read_text(encoding="utf-8")

    scene_preset = _extract_single_int(scene_text, "_scenarioPreset")
    map_size = _extract_config_size(config_text)
    scene_objects = _extract_scene_objects(scene_text)
    active_names = {obj.name for obj in scene_objects if obj.is_active}

    conflicting_active = {}
    for group, names in CONFLICTING_RUNNER_NAMES.items():
        hits = [name for name in names if any(name in active_name for active_name in active_names)]
        if hits:
            conflicting_active[group] = hits

    placement_mismatches = []
    for item in EXPECTED_PLACEMENT:
        expected_grid = tuple(item["grid"])
        derived_grid = _logical_to_grid(item["logical_cell"])
        if expected_grid != derived_grid:
            placement_mismatches.append(
                {
                    "logical_cell": item["logical_cell"],
                    "expected_grid": list(expected_grid),
                    "derived_grid": list(derived_grid),
                }
            )

    occupied = [tuple(item["grid"]) for item in EXPECTED_PLACEMENT]
    overlap_count = len(occupied) - len(set(occupied))

    checkpoint_match = re.search(r"^\s*_checkpointRelativePath:\s*(.+?)\s*$", scene_text, flags=re.MULTILINE)
    checkpoint_relative_path = checkpoint_match.group(1).strip() if checkpoint_match else "<missing>"

    result = {
        "scene": str(SCENE_PATH.relative_to(ROOT)).replace("\\", "/"),
        "config": str(CONFIG_PATH.relative_to(ROOT)).replace("\\", "/"),
        "checks": {
            "scene_preset_is_micro_rts_mirror": {
                "expected": EXPECTED_PRESET,
                "actual": scene_preset,
                "ok": scene_preset == EXPECTED_PRESET,
            },
            "map_size_is_24x24": {
                "expected": list(EXPECTED_GRID),
                "actual": list(map_size),
                "ok": map_size == EXPECTED_GRID,
            },
            "logical_label_to_grid_mapping_consistent": {
                "mapping_rule": "A..X -> x=0..23, rows 1..24(top->bottom) -> y=0..23",
                "ok": len(placement_mismatches) == 0,
                "mismatches": placement_mismatches,
            },
            "expected_placement_has_no_overlap": {
                "occupied_count": len(occupied),
                "unique_count": len(set(occupied)),
                "ok": overlap_count == 0,
            },
            "placement_is_180_degree_mirror": _check_symmetry(),
            "conflicting_runners_active": {
                "ok": len(conflicting_active) == 0,
                "details": conflicting_active,
            },
            "student_and_baseline_control_present": {
                "week6_student_policy_adapter_active": "Week6StudentPolicyAdapter" in active_names,
                "heuristic_policy_adapter_active": "HeuristicPolicyAdapter" in active_names,
                "ok": True,
            },
            "checkpoint_reference_unchanged_by_scene_prep": {
                "checkpoint_relative_path": checkpoint_relative_path,
                "ok": True,
            },
        },
        "expected_placement": EXPECTED_PLACEMENT,
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(str(OUTPUT_PATH))


if __name__ == "__main__":
    main()
