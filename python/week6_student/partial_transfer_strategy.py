from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import List

from student_branch_contract import BRANCH_SPECS, validate_student_branch_contract_consistency


class TransferMode(str, Enum):
    DIRECT_TRANSFER_CANDIDATE = "direct_transfer_candidate"
    PARTIAL_TRANSFER_CANDIDATE = "partial_transfer_candidate"
    NO_DIRECT_TRANSFER = "no_direct_transfer"
    EXPERIMENTAL_PARTIAL_ONLY = "experimental_partial_only"


@dataclass(frozen=True)
class TransferModuleRule:
    module: str
    transfer_mode: TransferMode
    rationale: str


@dataclass(frozen=True)
class BCBranchHeadMapping:
    target_index: int
    target_name: str
    branch_size: int
    student_head: str
    structurally_aligned: bool
    canonical_transfer_init_allowed: bool
    note: str


def build_day3_transfer_rules() -> List[TransferModuleRule]:
    """Week 6 Day 3 transfer policy.

    Policy is architecture-aware and honesty-first:
    - no full direct transfer claim is made;
    - transfer is allowed only with verified semantic and tensor compatibility;
    - PPO/optimizer/mask internals are outside canonical student initialization.
    """
    return [
        TransferModuleRule(
            module="input_stem",
            transfer_mode=TransferMode.PARTIAL_TRANSFER_CANDIDATE,
            rationale=(
                "Only if early teacher conv filters can be tensor-aligned and channel semantics are compatible; "
                "otherwise initialize student stem from scratch."
            ),
        ),
        TransferModuleRule(
            module="spatial_backbone_encoder",
            transfer_mode=TransferMode.DIRECT_TRANSFER_CANDIDATE,
            rationale=(
                "Primary transfer candidate when tensor shapes and feature semantics align without silent reshaping hacks."
            ),
        ),
        TransferModuleRule(
            module="action_type_head",
            transfer_mode=TransferMode.PARTIAL_TRANSFER_CANDIDATE,
            rationale=(
                "Possible only if class meaning and ordering exactly match and output dimensionality is compatible."
            ),
        ),
        TransferModuleRule(
            module="move_dir_head",
            transfer_mode=TransferMode.PARTIAL_TRANSFER_CANDIDATE,
            rationale="Candidate only when directional class ordering and gating semantics match exactly.",
        ),
        TransferModuleRule(
            module="harvest_dir_head",
            transfer_mode=TransferMode.PARTIAL_TRANSFER_CANDIDATE,
            rationale="Candidate only when directional class ordering and branch intent are verified equivalent.",
        ),
        TransferModuleRule(
            module="return_dir_head",
            transfer_mode=TransferMode.PARTIAL_TRANSFER_CANDIDATE,
            rationale="Candidate only when directional class ordering and branch intent are verified equivalent.",
        ),
        TransferModuleRule(
            module="produce_dir_head",
            transfer_mode=TransferMode.PARTIAL_TRANSFER_CANDIDATE,
            rationale="Candidate only when produce-direction semantics and class order are proven aligned.",
        ),
        TransferModuleRule(
            module="produce_unit_type_head",
            transfer_mode=TransferMode.PARTIAL_TRANSFER_CANDIDATE,
            rationale=(
                "Likely subset-only transfer because teacher may encode broader producible class space; "
                "clean subset mapping is required."
            ),
        ),
        TransferModuleRule(
            module="attack_target_local_head",
            transfer_mode=TransferMode.NO_DIRECT_TRANSFER,
            rationale=(
                "Treat as non-canonical for direct init unless target parameterization is proven equivalent. "
                "At most experimental_partial_only under explicit experiments."
            ),
        ),
        TransferModuleRule(
            module="value_or_critic_head",
            transfer_mode=TransferMode.NO_DIRECT_TRANSFER,
            rationale="PPO/value-specific tensors are not canonical student BC policy initialization targets.",
        ),
        TransferModuleRule(
            module="mask_related_logic",
            transfer_mode=TransferMode.NO_DIRECT_TRANSFER,
            rationale="Mask logic is execution/training logic, not policy-weight transfer target.",
        ),
        TransferModuleRule(
            module="global_feature_path",
            transfer_mode=TransferMode.NO_DIRECT_TRANSFER,
            rationale=(
                "Global feature path is optional auxiliary/diagnostic only in Day 3 and must not be mandatory."
            ),
        ),
        TransferModuleRule(
            module="optimizer_or_trainer_state",
            transfer_mode=TransferMode.NO_DIRECT_TRANSFER,
            rationale="Optimizer/trainer state is not valid student policy initialization.",
        ),
    ]


def get_week5_bc_to_student_head_mapping() -> List[BCBranchHeadMapping]:
    """1:1 branch mapping from BC-ready targets to Day 3 student heads."""
    validate_student_branch_contract_consistency()

    notes_by_branch: dict[str, str] = {
        "action_type": "Structurally aligned for supervision; transfer init still gated by class-order equivalence checks.",
        "move_dir": "Structurally aligned for supervision; transfer init requires class-order confirmation.",
        "harvest_dir": "Structurally aligned for supervision; transfer init requires class-order confirmation.",
        "return_dir": "Structurally aligned for supervision; transfer init requires class-order confirmation.",
        "produce_dir": "Structurally aligned for supervision; transfer init requires branch semantic parity evidence.",
        "produce_unit_type": "Structurally aligned for supervision; transfer init may be subset-only when teacher class space is broader.",
        "attack_target_local": "Structurally aligned for supervision; canonical direct transfer disallowed until target parameterization equivalence is proven.",
    }

    return [
        BCBranchHeadMapping(
            target_index=spec.target_index,
            target_name=spec.branch_name,
            branch_size=spec.branch_size,
            student_head=spec.head_name,
            structurally_aligned=True,
            canonical_transfer_init_allowed=False,
            note=notes_by_branch[spec.branch_name],
        )
        for spec in BRANCH_SPECS
    ]


def render_transfer_table_markdown(rules: List[TransferModuleRule]) -> str:
    lines = [
        "| module | transfer_mode | rationale |",
        "|---|---|---|",
    ]
    for rule in rules:
        lines.append(f"| {rule.module} | {rule.transfer_mode.value} | {rule.rationale} |")
    return "\n".join(lines)


def render_mapping_table_markdown(mappings: List[BCBranchHeadMapping]) -> str:
    lines = [
        "| target index | target name | branch size | student head | structurally aligned | canonical transfer init allowed | note |",
        "|---:|---|---:|---|---|---|---|",
    ]
    for m in mappings:
        lines.append(
            "| "
            f"{m.target_index} | {m.target_name} | {m.branch_size} | {m.student_head} | "
            f"{str(m.structurally_aligned).lower()} | {str(m.canonical_transfer_init_allowed).lower()} | {m.note} |"
        )
    return "\n".join(lines)
