from __future__ import annotations

from dataclasses import dataclass
from typing import Dict

from torch import Tensor, nn

from student_branch_contract import BRANCH_SPECS, validate_student_branch_contract_consistency


@dataclass(frozen=True)
class StudentBCModelConfig:
    input_channels: int = 27
    hidden_channels: int = 64


class StudentBCModelMinimal(nn.Module):
    """Day 2 minimal supervised BC student policy.

    This model is intentionally small and training-oriented only.
    It is not the final Week 6 architecture and has no Unity inference integration.
    """

    def __init__(self, config: StudentBCModelConfig | None = None) -> None:
        super().__init__()
        cfg = config or StudentBCModelConfig()

        self.encoder = nn.Sequential(
            nn.Conv2d(cfg.input_channels, cfg.hidden_channels, kernel_size=3, padding=1),
            nn.ReLU(inplace=True),
            nn.Conv2d(cfg.hidden_channels, cfg.hidden_channels, kernel_size=3, padding=1),
            nn.ReLU(inplace=True),
        )

        self.head_action_type = nn.Conv2d(cfg.hidden_channels, 6, kernel_size=1)
        self.head_move_dir = nn.Conv2d(cfg.hidden_channels, 4, kernel_size=1)
        self.head_harvest_dir = nn.Conv2d(cfg.hidden_channels, 4, kernel_size=1)
        self.head_return_dir = nn.Conv2d(cfg.hidden_channels, 4, kernel_size=1)
        self.head_produce_dir = nn.Conv2d(cfg.hidden_channels, 4, kernel_size=1)
        self.head_produce_unit_type = nn.Conv2d(cfg.hidden_channels, 4, kernel_size=1)
        self.head_attack_target_local = nn.Conv2d(cfg.hidden_channels, 9, kernel_size=1)

        validate_student_branch_contract_consistency()

    @staticmethod
    def _to_cell_logits(logits_bchw: Tensor) -> Tensor:
        b, c, h, w = logits_bchw.shape
        return logits_bchw.permute(0, 2, 3, 1).reshape(b, h * w, c)

    def forward(self, x: Tensor) -> Dict[str, Tensor]:
        """Forward pass.

        Args:
            x: Spatial input tensor of shape [B, 24, 24, 27].

        Returns:
            Dict of branch logits with shape [B, 576, branch_size].
        """
        if x.ndim != 4:
            raise ValueError(f"Expected input rank 4 [B,24,24,27], got ndim={x.ndim}")

        x_bchw = x.permute(0, 3, 1, 2)
        features = self.encoder(x_bchw)

        heads_by_name = {
            "action_type_head": self.head_action_type,
            "move_dir_head": self.head_move_dir,
            "harvest_dir_head": self.head_harvest_dir,
            "return_dir_head": self.head_return_dir,
            "produce_dir_head": self.head_produce_dir,
            "produce_unit_type_head": self.head_produce_unit_type,
            "attack_target_local_head": self.head_attack_target_local,
        }

        outputs: Dict[str, Tensor] = {}
        for spec in BRANCH_SPECS:
            outputs[spec.logits_key] = self._to_cell_logits(heads_by_name[spec.head_name](features))
        return outputs
