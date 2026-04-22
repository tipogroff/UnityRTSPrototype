from __future__ import annotations

from dataclasses import dataclass
from typing import Dict

import torch
from torch import Tensor, nn


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

        return {
            "action_type_logits": self._to_cell_logits(self.head_action_type(features)),
            "move_dir_logits": self._to_cell_logits(self.head_move_dir(features)),
            "harvest_dir_logits": self._to_cell_logits(self.head_harvest_dir(features)),
            "return_dir_logits": self._to_cell_logits(self.head_return_dir(features)),
            "produce_dir_logits": self._to_cell_logits(self.head_produce_dir(features)),
            "produce_unit_type_logits": self._to_cell_logits(self.head_produce_unit_type(features)),
            "attack_target_local_logits": self._to_cell_logits(self.head_attack_target_local(features)),
        }
