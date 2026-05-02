from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional

from torch import Tensor, nn

from student_branch_contract import (
    BRANCH_SPECS,
    TARGET_INDEX_TO_HEAD,
    validate_student_branch_contract_consistency,
)


@dataclass(frozen=True)
class StudentArchitectureTransferConfig:
    """Week 6 Day 3 student architecture config.

    This config stays aligned to the BC-ready Unity-side contract:
    - primary input: [24, 24, 27]
    - per-cell branch heads: [576, 7 branches]

    Day 3 scope note:
    - this defines architecture and transfer-aware structure only;
    - it does not claim runtime transfer correctness;
    - it does not imply Unity export is complete.
    """

    input_channels: int = 27
    stem_channels: int = 64
    backbone_channels: int = 96

    # Optional auxiliary global path (diagnostic-only by policy contract).
    enable_global_auxiliary: bool = False
    global_aux_dim: int = 32


class ResidualSpatialBlock(nn.Module):
    def __init__(self, channels: int) -> None:
        super().__init__()
        self.block = nn.Sequential(
            nn.Conv2d(channels, channels, kernel_size=3, padding=1, bias=False),
            nn.BatchNorm2d(channels),
            nn.SiLU(inplace=True),
            nn.Conv2d(channels, channels, kernel_size=3, padding=1, bias=False),
            nn.BatchNorm2d(channels),
        )
        self.act = nn.SiLU(inplace=True)

    def forward(self, x: Tensor) -> Tensor:
        return self.act(x + self.block(x))


class StudentBCTransferModel(nn.Module):
    """Week 6 Day 3 transfer-aware BC student architecture.

    Architectural decomposition (explicit Day 3 requirement):
    - spatial_stem
    - encoder_backbone
    - shared_spatial_features
    - per-branch heads aligned to Unity-side BC targets

    Transfer posture:
    - encoder/backbone are the primary transfer candidates;
    - branch heads remain student-side contract heads and are transfer-gated;
    - optional global path is auxiliary only and never mandatory.
    """

    def __init__(self, config: StudentArchitectureTransferConfig | None = None) -> None:
        super().__init__()
        cfg = config or StudentArchitectureTransferConfig()
        self.config = cfg

        # 1) Spatial stem: early local feature extraction over [24,24,27].
        self.spatial_stem = nn.Sequential(
            nn.Conv2d(cfg.input_channels, cfg.stem_channels, kernel_size=3, padding=1, bias=False),
            nn.BatchNorm2d(cfg.stem_channels),
            nn.SiLU(inplace=True),
            nn.Conv2d(cfg.stem_channels, cfg.backbone_channels, kernel_size=3, padding=1, bias=False),
            nn.BatchNorm2d(cfg.backbone_channels),
            nn.SiLU(inplace=True),
        )

        # 2) Encoder/backbone: shared spatial representation.
        self.encoder_backbone = nn.Sequential(
            ResidualSpatialBlock(cfg.backbone_channels),
            ResidualSpatialBlock(cfg.backbone_channels),
            nn.Conv2d(cfg.backbone_channels, cfg.backbone_channels, kernel_size=3, padding=1, bias=False),
            nn.BatchNorm2d(cfg.backbone_channels),
            nn.SiLU(inplace=True),
        )

        # 3) Shared features consumed by all branch heads.
        self.shared_spatial_features = nn.Sequential(
            nn.Conv2d(cfg.backbone_channels, cfg.backbone_channels, kernel_size=1, bias=False),
            nn.BatchNorm2d(cfg.backbone_channels),
            nn.SiLU(inplace=True),
        )

        # 4) Branch heads (authoritative sizes/order from branch contract).
        self.branch_heads = nn.ModuleDict(
            {
                spec.head_name: nn.Conv2d(cfg.backbone_channels, spec.branch_size, kernel_size=1)
                for spec in BRANCH_SPECS
            }
        )

        # Optional attribute aliases keep head names explicit and discoverable.
        for spec in BRANCH_SPECS:
            setattr(self, spec.head_name, self.branch_heads[spec.head_name])

        # Optional auxiliary global path for diagnostics/ablation only.
        if cfg.enable_global_auxiliary:
            self.global_aux_pool = nn.AdaptiveAvgPool2d((1, 1))
            self.global_aux_mlp = nn.Sequential(
                nn.Flatten(),
                nn.Linear(cfg.backbone_channels, cfg.backbone_channels),
                nn.SiLU(inplace=True),
                nn.Linear(cfg.backbone_channels, cfg.global_aux_dim),
            )
        else:
            self.global_aux_pool = None
            self.global_aux_mlp = None

        validate_student_branch_contract_consistency(
            model_logits_keys=self.output_logits_keys_in_order(),
            target_index_to_head=TARGET_INDEX_TO_HEAD,
        )

    @staticmethod
    def _to_cell_logits(logits_bchw: Tensor) -> Tensor:
        b, c, h, w = logits_bchw.shape
        return logits_bchw.permute(0, 2, 3, 1).reshape(b, h * w, c)

    @staticmethod
    def output_logits_keys_in_order() -> tuple[str, ...]:
        return tuple(spec.logits_key for spec in BRANCH_SPECS)

    def forward(self, x: Tensor) -> Dict[str, Tensor]:
        """Forward pass with per-cell branch logits.

        Args:
            x: [B, 24, 24, 27] float tensor.

        Returns:
            Dict[str, Tensor]:
                - action_type_logits: [B, 576, 6]
                - move_dir_logits: [B, 576, 4]
                - harvest_dir_logits: [B, 576, 4]
                - return_dir_logits: [B, 576, 4]
                - produce_dir_logits: [B, 576, 4]
                - produce_unit_type_logits: [B, 576, 7]
                - attack_target_local_logits: [B, 576, 49]
                - global_aux_embedding (optional): [B, global_aux_dim]
        """
        if x.ndim != 4:
            raise ValueError(f"Expected input rank 4 [B,24,24,27], got ndim={x.ndim}")

        x_bchw = x.permute(0, 3, 1, 2)
        stem = self.spatial_stem(x_bchw)
        encoded = self.encoder_backbone(stem)
        shared = self.shared_spatial_features(encoded)

        outputs: Dict[str, Tensor] = {}
        for spec in BRANCH_SPECS:
            head = self.branch_heads[spec.head_name]
            outputs[spec.logits_key] = self._to_cell_logits(head(shared))

        if self.global_aux_pool is not None and self.global_aux_mlp is not None:
            pooled = self.global_aux_pool(shared)
            outputs["global_aux_embedding"] = self.global_aux_mlp(pooled)

        return outputs


def build_day3_student_model(
    config: Optional[StudentArchitectureTransferConfig] = None,
) -> StudentBCTransferModel:
    """Factory helper for Week 6 Day 3 architecture experiments."""
    return StudentBCTransferModel(config=config)
