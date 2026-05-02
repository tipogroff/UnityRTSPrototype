from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

TARGET_CHECKPOINT_REL = Path(
    "python/week6_student/runs/legacy032_v2_bc_minimal_20260501T195501Z/student_bc_transfer_best.pt"
)
TARGET_SCENE_REL = Path("Assets/Scenes/Week6_StudentVisualInspection.unity")
TARGET_SCENE_DISPLAY_NAME = "Week 6_student Visual Inspection"

EXPECTED_MODEL_VARIANT = "transfer"
EXPECTED_TARGET_ACTION_CONTRACT = "unity_v2_legacy032_gridnet"
EXPECTED_BRANCH_SIZES = [6, 4, 4, 4, 4, 7, 49]
EXPECTED_DIRECT_WEIGHT_TRANSFER_CLAIM = False
EXPECTED_SEMANTIC_PARITY_CLAIM = False
EXPECTED_SCENARIO_PRESET = 4

STALE_TERMS = [
    "day3_transfer_bc_main_20260423",
    "legacy032_v2_bc_smoke_20260501T181043Z",
]

SCAN_ROOTS = [
    Path("Assets"),
    Path("python/week6_student"),
]

SCAN_EXTENSIONS = {
    ".cs",
    ".unity",
    ".prefab",
    ".asset",
    ".json",
    ".md",
    ".py",
}


@dataclass
class CheckResult:
    name: str
    ok: bool
    details: Any


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _line_numbers(text: str, needle: str) -> list[int]:
    lines: list[int] = []
    for idx, line in enumerate(text.splitlines(), start=1):
        if needle in line:
            lines.append(idx)
    return lines


def _extract_first_match(text: str, pattern: str) -> str | None:
    m = re.search(pattern, text, flags=re.MULTILINE)
    if not m:
        return None
    return m.group(1).strip()


def _scan_terms(repo_root: Path, terms: list[str]) -> dict[str, list[dict[str, Any]]]:
    found: dict[str, list[dict[str, Any]]] = {term: [] for term in terms}
    for root in SCAN_ROOTS:
        abs_root = repo_root / root
        if not abs_root.exists():
            continue
        for path in abs_root.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in SCAN_EXTENSIONS:
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except Exception:
                continue
            rel = path.relative_to(repo_root).as_posix()
            for term in terms:
                ln = _line_numbers(text, term)
                if ln:
                    found[term].append({"path": rel, "lines": ln})
    return found


def _classify_ref(path: str) -> str:
    if path == "Assets/Scenes/Week6_StudentVisualInspection.unity":
        return "active"
    if path.startswith("Assets/Scenes/"):
        return "inactive_other_scene"
    if path.startswith("Assets/_Recovery/"):
        return "historical_recovery"
    if "/reports/" in path or path.endswith(".md"):
        return "historical_report"
    if "/tmp/" in path:
        return "historical_tmp"
    return "code_or_data"


def _load_checkpoint_metadata(repo_root: Path, checkpoint_abs: Path) -> dict[str, Any]:
    result: dict[str, Any] = {
        "torch_available": False,
        "load_ok": False,
        "error": None,
    }

    try:
        import torch  # type: ignore
    except Exception as exc:  # pragma: no cover
        result["error"] = f"torch import failed: {exc}"
        return result

    result["torch_available"] = True

    try:
        payload = torch.load(checkpoint_abs, map_location="cpu")
    except Exception as exc:  # pragma: no cover
        result["error"] = f"checkpoint load failed: {exc}"
        return result

    if not isinstance(payload, dict):
        result["error"] = f"checkpoint payload type is {type(payload)!r}, expected dict"
        return result

    config = payload.get("config") if isinstance(payload.get("config"), dict) else {}
    bc_ready_raw = str(config.get("bc_ready_dir", "")).strip()
    bc_ready_rel = Path(bc_ready_raw.replace("\\", "/")) if bc_ready_raw else None
    manifest_abs = (repo_root / bc_ready_rel / "bc_manifest.json").resolve() if bc_ready_rel else None

    manifest: dict[str, Any] = {}
    if manifest_abs and manifest_abs.exists():
        try:
            manifest = json.loads(manifest_abs.read_text(encoding="utf-8"))
        except Exception:
            manifest = {}

    result.update(
        {
            "load_ok": True,
            "epoch": payload.get("epoch"),
            "model_variant": config.get("model_variant"),
            "checkpoint_config_keys": sorted(config.keys()),
            "bc_ready_dir": bc_ready_rel.as_posix() if bc_ready_rel else None,
            "manifest_path": manifest_abs.relative_to(repo_root).as_posix() if manifest_abs and manifest_abs.exists() else None,
            "manifest_target_action_contract": manifest.get("target_action_contract"),
            "manifest_branch_sizes": manifest.get("branch_sizes"),
            "manifest_direct_weight_transfer_claim": manifest.get("direct_weight_transfer_claim"),
            "manifest_semantic_parity_claim": manifest.get("semantic_parity_claim"),
        }
    )
    return result


def main() -> int:
    repo_root = Path(__file__).resolve().parents[2]

    scene_abs = repo_root / TARGET_SCENE_REL
    checkpoint_abs = (repo_root / TARGET_CHECKPOINT_REL).resolve()

    checks: list[CheckResult] = []

    scene_exists = scene_abs.exists()
    checks.append(CheckResult("scene_exists", scene_exists, str(TARGET_SCENE_REL.as_posix())))

    checkpoint_exists = checkpoint_abs.exists()
    checks.append(CheckResult("checkpoint_exists", checkpoint_exists, str(TARGET_CHECKPOINT_REL.as_posix())))

    scene_text = _read_text(scene_abs) if scene_exists else ""

    scene_checkpoint_value = _extract_first_match(scene_text, r"^\s*_checkpointRelativePath:\s*(.+?)\s*$") if scene_text else None
    checks.append(
        CheckResult(
            "scene_checkpoint_matches_target",
            scene_checkpoint_value == TARGET_CHECKPOINT_REL.as_posix(),
            {
                "scene_value": scene_checkpoint_value,
                "expected": TARGET_CHECKPOINT_REL.as_posix(),
            },
        )
    )

    scene_preset = _extract_first_match(scene_text, r"^\s*_scenarioPreset:\s*(-?\d+)\s*$") if scene_text else None
    checks.append(
        CheckResult(
            "scene_preset_is_stage9_micro_rts_like",
            scene_preset == str(EXPECTED_SCENARIO_PRESET),
            {
                "actual": scene_preset,
                "expected": EXPECTED_SCENARIO_PRESET,
            },
        )
    )

    vis_autostart = _extract_first_match(scene_text, r"^\s*_autoStartOnPlay:\s*(\d+)\s*$") if scene_text else None
    checks.append(
        CheckResult(
            "visual_runner_autostart_disabled",
            vis_autostart == "0",
            {
                "actual": vis_autostart,
                "expected": 0,
            },
        )
    )

    policy_cs = repo_root / "Assets/Scripts/ML/Week6StudentPolicyAdapter.cs"
    day4_cs = repo_root / "Assets/Scripts/ML/Week6Day4StudentInferenceDryRun.cs"
    global_smoke_cs = repo_root / "Assets/Scripts/ML/ActionContractV2GlobalSmokeRunner.cs"

    policy_text = _read_text(policy_cs)
    day4_text = _read_text(day4_cs)
    global_smoke_text = _read_text(global_smoke_cs)

    policy_default = _extract_first_match(policy_text, r"_checkpointRelativePath\s*=\s*\"([^\"]+)\"")
    day4_default = _extract_first_match(day4_text, r"_checkpointRelativePath\s*=\s*\"([^\"]+)\"")
    global_default = _extract_first_match(global_smoke_text, r"ReadPrivateStringField\([^\)]*\"([^\"]+student_bc_transfer_best\.pt)\"\)")

    checks.append(
        CheckResult(
            "policy_adapter_default_matches_target",
            policy_default == TARGET_CHECKPOINT_REL.as_posix(),
            {"actual": policy_default, "expected": TARGET_CHECKPOINT_REL.as_posix()},
        )
    )
    checks.append(
        CheckResult(
            "day4_dryrun_default_matches_target",
            day4_default == TARGET_CHECKPOINT_REL.as_posix(),
            {"actual": day4_default, "expected": TARGET_CHECKPOINT_REL.as_posix()},
        )
    )
    checks.append(
        CheckResult(
            "global_smoke_fallback_matches_target",
            global_default == TARGET_CHECKPOINT_REL.as_posix(),
            {"actual": global_default, "expected": TARGET_CHECKPOINT_REL.as_posix()},
        )
    )

    checkpoint_meta = _load_checkpoint_metadata(repo_root, checkpoint_abs) if checkpoint_exists else {
        "torch_available": False,
        "load_ok": False,
        "error": "checkpoint missing",
    }

    checks.append(
        CheckResult(
            "checkpoint_model_variant_is_transfer",
            checkpoint_meta.get("model_variant") == EXPECTED_MODEL_VARIANT,
            {
                "actual": checkpoint_meta.get("model_variant"),
                "expected": EXPECTED_MODEL_VARIANT,
            },
        )
    )
    checks.append(
        CheckResult(
            "manifest_target_action_contract_matches",
            checkpoint_meta.get("manifest_target_action_contract") == EXPECTED_TARGET_ACTION_CONTRACT,
            {
                "actual": checkpoint_meta.get("manifest_target_action_contract"),
                "expected": EXPECTED_TARGET_ACTION_CONTRACT,
            },
        )
    )
    checks.append(
        CheckResult(
            "manifest_branch_sizes_match",
            list(checkpoint_meta.get("manifest_branch_sizes") or []) == EXPECTED_BRANCH_SIZES,
            {
                "actual": checkpoint_meta.get("manifest_branch_sizes"),
                "expected": EXPECTED_BRANCH_SIZES,
            },
        )
    )
    checks.append(
        CheckResult(
            "manifest_direct_weight_transfer_claim_false",
            checkpoint_meta.get("manifest_direct_weight_transfer_claim") is EXPECTED_DIRECT_WEIGHT_TRANSFER_CLAIM,
            {
                "actual": checkpoint_meta.get("manifest_direct_weight_transfer_claim"),
                "expected": EXPECTED_DIRECT_WEIGHT_TRANSFER_CLAIM,
            },
        )
    )
    checks.append(
        CheckResult(
            "manifest_semantic_parity_claim_false",
            checkpoint_meta.get("manifest_semantic_parity_claim") is EXPECTED_SEMANTIC_PARITY_CLAIM,
            {
                "actual": checkpoint_meta.get("manifest_semantic_parity_claim"),
                "expected": EXPECTED_SEMANTIC_PARITY_CLAIM,
            },
        )
    )

    scan_results = _scan_terms(repo_root, STALE_TERMS)
    classified_scan: dict[str, list[dict[str, Any]]] = {}
    for term, refs in scan_results.items():
        classified_scan[term] = []
        for ref in refs:
            ref_copy = dict(ref)
            ref_copy["classification"] = _classify_ref(ref["path"])
            classified_scan[term].append(ref_copy)

    checks.append(
        CheckResult(
            "no_day3_reference_in_target_scene",
            not any(
                ref["path"] == TARGET_SCENE_REL.as_posix()
                for ref in classified_scan["day3_transfer_bc_main_20260423"]
            ),
            classified_scan["day3_transfer_bc_main_20260423"],
        )
    )

    checks.append(
        CheckResult(
            "no_smoke_reference_in_target_scene",
            not any(
                ref["path"] == TARGET_SCENE_REL.as_posix()
                for ref in classified_scan["legacy032_v2_bc_smoke_20260501T181043Z"]
            ),
            classified_scan["legacy032_v2_bc_smoke_20260501T181043Z"],
        )
    )

    all_ok = all(check.ok for check in checks)

    result = {
        "scope": {
            "stage": "8.5_unity_side_checkpoint_binding_verification",
            "unity_scene_run_performed": False,
            "play_mode_run_performed": False,
            "match_started": False,
            "training_performed": False,
            "dataset_modified": False,
            "checkpoint_modified": False,
        },
        "target_scene": {
            "path": TARGET_SCENE_REL.as_posix(),
            "display_name": TARGET_SCENE_DISPLAY_NAME,
        },
        "target_checkpoint": {
            "relative_path": TARGET_CHECKPOINT_REL.as_posix(),
            "exists": checkpoint_exists,
        },
        "binding_sources": {
            "scene_serialized_field": {
                "file": TARGET_SCENE_REL.as_posix(),
                "field": "_checkpointRelativePath",
                "value": scene_checkpoint_value,
            },
            "script_defaults": {
                "Week6StudentPolicyAdapter": policy_default,
                "Week6Day4StudentInferenceDryRun": day4_default,
                "ActionContractV2GlobalSmokeRunner_fallback": global_default,
            },
        },
        "checkpoint_metadata": checkpoint_meta,
        "stale_reference_scan": classified_scan,
        "checks": [
            {"name": c.name, "ok": c.ok, "details": c.details} for c in checks
        ],
        "decision": "GO_FOR_UNITY_SCENE_DRY_RUN" if all_ok else "GO_FOR_BINDING_REMEDIATION",
    }

    out_json = repo_root / "python/week6_student/reports/LEGACY032_UNITY_V2_UNITY_CHECKPOINT_BINDING_VALIDATION.json"
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(result, ensure_ascii=True, indent=2), encoding="utf-8")

    print(out_json.as_posix())
    print(f"decision={result['decision']}")
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
