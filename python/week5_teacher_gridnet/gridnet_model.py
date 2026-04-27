#!/usr/bin/env python3
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Optional, Sequence, Tuple

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.distributions.categorical import Categorical


NEG_INF = -1e8


class CategoricalMasked(Categorical):
    """Categorical distribution that applies invalid-action masks to logits."""

    def __init__(
        self,
        *,
        probs: Optional[torch.Tensor] = None,
        logits: Optional[torch.Tensor] = None,
        validate_args: Optional[bool] = None,
        masks: Optional[torch.Tensor] = None,
    ) -> None:
        self.masks = None if masks is None else masks.bool()
        if self.masks is None:
            super().__init__(probs=probs, logits=logits, validate_args=validate_args)
            return

        if logits is None:
            raise ValueError("CategoricalMasked requires logits when masks are provided.")
        masked_logits = torch.where(
            self.masks,
            logits,
            torch.full_like(logits, NEG_INF),
        )
        super().__init__(probs=probs, logits=masked_logits, validate_args=validate_args)

    def entropy(self) -> torch.Tensor:
        if self.masks is None:
            return super().entropy()
        p_log_p = self.logits * self.probs
        p_log_p = torch.where(self.masks, p_log_p, torch.zeros_like(p_log_p))
        return -p_log_p.sum(-1)


class Transpose(nn.Module):
    def __init__(self, permutation: Tuple[int, int, int, int]) -> None:
        super().__init__()
        self.permutation = permutation

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return x.permute(self.permutation)


def layer_init(layer: nn.Module, std: float = np.sqrt(2.0), bias_const: float = 0.0) -> nn.Module:
    torch.nn.init.orthogonal_(layer.weight, std)
    torch.nn.init.constant_(layer.bias, bias_const)
    return layer


class Encoder(nn.Module):
    def __init__(self, input_channels: int) -> None:
        super().__init__()
        self.net = nn.Sequential(
            Transpose((0, 3, 1, 2)),
            layer_init(nn.Conv2d(input_channels, 32, kernel_size=3, padding=1)),
            nn.MaxPool2d(3, stride=2, padding=1),
            nn.ReLU(),
            layer_init(nn.Conv2d(32, 64, kernel_size=3, padding=1)),
            nn.MaxPool2d(3, stride=2, padding=1),
            nn.ReLU(),
            layer_init(nn.Conv2d(64, 128, kernel_size=3, padding=1)),
            nn.MaxPool2d(3, stride=2, padding=1),
            nn.ReLU(),
            layer_init(nn.Conv2d(128, 256, kernel_size=3, padding=1)),
            nn.AdaptiveAvgPool2d((1, 1)),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.net(x)


class Decoder(nn.Module):
    def __init__(self, output_channels: int) -> None:
        super().__init__()
        out_ch = int(output_channels)
        self.net = nn.Sequential(
            layer_init(nn.ConvTranspose2d(256, 128, 3, stride=2, padding=1, output_padding=1)),
            nn.ReLU(),
            layer_init(nn.ConvTranspose2d(128, 64, 3, stride=2, padding=1, output_padding=1)),
            nn.ReLU(),
            layer_init(nn.ConvTranspose2d(64, 32, 3, stride=2, padding=1, output_padding=1)),
            nn.ReLU(),
            layer_init(nn.Conv2d(32, out_ch, kernel_size=1), std=1.0),
        )

    def forward(self, x: torch.Tensor, height: int, width: int) -> torch.Tensor:
        y = self.net(x)
        y = F.interpolate(y, size=(height, width), mode="bilinear", align_corners=False)
        return y.permute(0, 2, 3, 1)


@dataclass(frozen=True)
class ActionLayout:
    branch_sizes: Tuple[int, ...]

    @property
    def branch_count(self) -> int:
        return len(self.branch_sizes)

    @property
    def actor_output_channels(self) -> int:
        return int(sum(self.branch_sizes))


class Agent(nn.Module):
    """Project-compatible Gridnet actor-critic (architecture port, dynamic map size)."""

    def __init__(
        self,
        observation_shape: Sequence[int],
        action_nvec: Iterable[int],
    ) -> None:
        super().__init__()

        if len(tuple(observation_shape)) != 3:
            raise ValueError(f"Expected observation shape [H,W,C], got {tuple(observation_shape)}")
        h, w, c = [int(v) for v in observation_shape]
        if h <= 0 or w <= 0 or c <= 0:
            raise ValueError(f"Observation dimensions must be positive, got {(h, w, c)}")

        nvec = [int(v) for v in action_nvec]
        if len(nvec) < 2:
            raise ValueError(f"Expected MultiDiscrete nvec with source index + branches, got {nvec}")

        self.height = h
        self.width = w
        self.channels = c
        self.mapsize = h * w
        self.action_layout = ActionLayout(branch_sizes=tuple(nvec[1:]))

        self.encoder = Encoder(c)
        self.actor = Decoder(self.action_layout.actor_output_channels)
        self.critic = nn.Sequential(
            nn.Flatten(),
            layer_init(nn.Linear(256, 128), std=1.0),
            nn.ReLU(),
            layer_init(nn.Linear(128, 1), std=1.0),
        )

    def encode(self, obs_bhwc: torch.Tensor) -> torch.Tensor:
        return self.encoder(obs_bhwc)

    def get_value(self, obs_bhwc: torch.Tensor) -> torch.Tensor:
        return self.critic(self.encode(obs_bhwc))

    def _split_logits(self, obs_bhwc: torch.Tensor) -> List[torch.Tensor]:
        features = self.encode(obs_bhwc)
        logits = self.actor(features, self.height, self.width)
        grid_logits = logits.reshape(-1, self.action_layout.actor_output_channels)
        return list(torch.split(grid_logits, list(self.action_layout.branch_sizes), dim=1))

    def get_action(
        self,
        obs_bhwc: torch.Tensor,
        *,
        invalid_action_masks: torch.Tensor,
        action: Optional[torch.Tensor] = None,
        deterministic: bool = False,
    ) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor]:
        """
        Returns:
          action: [B, H*W, branch_count]
          logprob_sum: [B]
          entropy_sum: [B]
          invalid_action_masks: [B, H*W, 1 + sum(branch_sizes)]
        """
        split_logits = self._split_logits(obs_bhwc)
        bsz = int(obs_bhwc.shape[0])

        mask = invalid_action_masks.view(-1, invalid_action_masks.shape[-1])
        split_masks = torch.split(mask[:, 1:], list(self.action_layout.branch_sizes), dim=1)
        categoricals = [
            CategoricalMasked(logits=branch_logits, masks=branch_mask)
            for branch_logits, branch_mask in zip(split_logits, split_masks)
        ]

        if action is None:
            if deterministic:
                sampled = []
                for branch_logits, branch_mask in zip(split_logits, split_masks):
                    masked_logits = torch.where(branch_mask.bool(), branch_logits, torch.full_like(branch_logits, NEG_INF))
                    sampled.append(torch.argmax(masked_logits, dim=1))
                action_t = torch.stack(sampled)
            else:
                action_t = torch.stack([cat.sample() for cat in categoricals])
        else:
            action_t = action.view(-1, action.shape[-1]).T

        logprob = torch.stack([cat.log_prob(a) for a, cat in zip(action_t, categoricals)])
        entropy = torch.stack([cat.entropy() for cat in categoricals])

        num_branches = self.action_layout.branch_count
        action_out = action_t.T.view(-1, self.mapsize, num_branches)
        logprob_out = logprob.T.view(-1, self.mapsize, num_branches).sum(1).sum(1)
        entropy_out = entropy.T.view(-1, self.mapsize, num_branches).sum(1).sum(1)
        mask_out = mask.view(-1, self.mapsize, self.action_layout.actor_output_channels + 1)

        if int(action_out.shape[0]) != bsz:
            raise RuntimeError("Action reshape mismatch; verify map/action dimensions.")

        return action_out, logprob_out, entropy_out, mask_out
