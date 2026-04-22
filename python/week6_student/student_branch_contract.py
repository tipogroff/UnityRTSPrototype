from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping, Optional, Sequence


@dataclass(frozen=True)
class StudentBranchSpec:
    branch_name: str
    target_index: int
    logits_key: str
    head_name: str
    branch_size: int
    action_type_gate_value: int | None


BRANCH_SPECS: tuple[StudentBranchSpec, ...] = (
    StudentBranchSpec(
        branch_name="action_type",
        target_index=0,
        logits_key="action_type_logits",
        head_name="action_type_head",
        branch_size=6,
        action_type_gate_value=None,
    ),
    StudentBranchSpec(
        branch_name="move_dir",
        target_index=1,
        logits_key="move_dir_logits",
        head_name="move_dir_head",
        branch_size=4,
        action_type_gate_value=1,
    ),
    StudentBranchSpec(
        branch_name="harvest_dir",
        target_index=2,
        logits_key="harvest_dir_logits",
        head_name="harvest_dir_head",
        branch_size=4,
        action_type_gate_value=2,
    ),
    StudentBranchSpec(
        branch_name="return_dir",
        target_index=3,
        logits_key="return_dir_logits",
        head_name="return_dir_head",
        branch_size=4,
        action_type_gate_value=3,
    ),
    StudentBranchSpec(
        branch_name="produce_dir",
        target_index=4,
        logits_key="produce_dir_logits",
        head_name="produce_dir_head",
        branch_size=4,
        action_type_gate_value=4,
    ),
    StudentBranchSpec(
        branch_name="produce_unit_type",
        target_index=5,
        logits_key="produce_unit_type_logits",
        head_name="produce_unit_type_head",
        branch_size=4,
        action_type_gate_value=4,
    ),
    StudentBranchSpec(
        branch_name="attack_target_local",
        target_index=6,
        logits_key="attack_target_local_logits",
        head_name="attack_target_local_head",
        branch_size=9,
        action_type_gate_value=5,
    ),
)

EXPECTED_BC_BRANCH_SIZES: tuple[int, ...] = (6, 4, 4, 4, 4, 4, 9)
ACTION_TYPE_TARGET_INDEX: int = 0

BRANCH_ORDER: tuple[str, ...] = tuple(spec.branch_name for spec in BRANCH_SPECS)
BRANCH_SIZES: Dict[str, int] = {spec.branch_name: spec.branch_size for spec in BRANCH_SPECS}
BRANCH_LOGITS_KEYS: tuple[str, ...] = tuple(spec.logits_key for spec in BRANCH_SPECS)
TARGET_INDEX_TO_HEAD: Dict[int, str] = {spec.target_index: spec.head_name for spec in BRANCH_SPECS}
HEAD_NAME_TO_TARGET_INDEX: Dict[str, int] = {spec.head_name: spec.target_index for spec in BRANCH_SPECS}
BRANCH_NAME_TO_SPEC: Dict[str, StudentBranchSpec] = {spec.branch_name: spec for spec in BRANCH_SPECS}
LOGITS_KEY_TO_SPEC: Dict[str, StudentBranchSpec] = {spec.logits_key: spec for spec in BRANCH_SPECS}


def get_branch_contract_summary() -> Dict[str, Any]:
    return {
        "branch_order": list(BRANCH_ORDER),
        "expected_bc_branch_sizes": list(EXPECTED_BC_BRANCH_SIZES),
        "branch_specs": [asdict(spec) for spec in BRANCH_SPECS],
        "branch_sizes": dict(BRANCH_SIZES),
        "branch_logits_keys": list(BRANCH_LOGITS_KEYS),
        "target_index_to_head": dict(TARGET_INDEX_TO_HEAD),
        "head_name_to_target_index": dict(HEAD_NAME_TO_TARGET_INDEX),
        "action_type_target_index": ACTION_TYPE_TARGET_INDEX,
    }


def validate_student_branch_contract_consistency(
    *,
    expected_bc_branch_sizes: Sequence[int] = EXPECTED_BC_BRANCH_SIZES,
    model_logits_keys: Optional[Iterable[str]] = None,
    target_index_to_head: Optional[Mapping[int, str]] = None,
) -> None:
    branch_names = [spec.branch_name for spec in BRANCH_SPECS]
    if len(set(branch_names)) != len(branch_names):
        raise ValueError(f"Branch order contains duplicates: {branch_names}")

    target_indices = [spec.target_index for spec in BRANCH_SPECS]
    expected_indices = list(range(len(BRANCH_SPECS)))
    if sorted(target_indices) != expected_indices:
        raise ValueError(
            f"Target indices mismatch. Expected contiguous {expected_indices}, got {target_indices}"
        )

    spec_sizes = tuple(spec.branch_size for spec in BRANCH_SPECS)
    expected_sizes_tuple = tuple(int(x) for x in expected_bc_branch_sizes)
    if spec_sizes != expected_sizes_tuple:
        raise ValueError(
            f"Branch sizes mismatch. Expected {expected_sizes_tuple}, got {spec_sizes}"
        )

    logits_keys = [spec.logits_key for spec in BRANCH_SPECS]
    if len(set(logits_keys)) != len(logits_keys):
        raise ValueError(f"Duplicate logits keys in contract: {logits_keys}")

    head_names = [spec.head_name for spec in BRANCH_SPECS]
    if len(set(head_names)) != len(head_names):
        raise ValueError(f"Duplicate head names in contract: {head_names}")

    canonical_target_index_to_head = {spec.target_index: spec.head_name for spec in BRANCH_SPECS}
    if target_index_to_head is not None and dict(target_index_to_head) != canonical_target_index_to_head:
        raise ValueError(
            "BC target->head mapping mismatch. "
            f"Expected {canonical_target_index_to_head}, got {dict(target_index_to_head)}"
        )

    if model_logits_keys is not None:
        model_logits_key_list = list(model_logits_keys)
        canonical_logits_key_order = [spec.logits_key for spec in BRANCH_SPECS]
        if model_logits_key_list != canonical_logits_key_order:
            raise ValueError(
                "Model logits key order mismatch. "
                f"Expected {canonical_logits_key_order}, got {model_logits_key_list}"
            )


def render_branch_contract_markdown() -> str:
    lines = [
        "| branch order | target index | logits key | head name | size | action_type gate |",
        "|---:|---:|---|---|---:|---:|",
    ]
    for order, spec in enumerate(BRANCH_SPECS):
        gate = "always" if spec.action_type_gate_value is None else str(spec.action_type_gate_value)
        lines.append(
            f"| {order} | {spec.target_index} | {spec.logits_key} | {spec.head_name} | {spec.branch_size} | {gate} |"
        )
    return "\n".join(lines)


def dump_branch_contract_json(path: str | Path) -> Path:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(get_branch_contract_summary(), ensure_ascii=True, indent=2),
        encoding="utf-8",
    )
    return output_path
