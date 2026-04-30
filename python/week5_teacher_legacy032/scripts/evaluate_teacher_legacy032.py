from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
import traceback
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import torch
import torch.nn as nn
from torch.distributions.categorical import Categorical


ACTION_TYPE_NAMES = {
    0: "noop",
    1: "move",
    2: "harvest",
    3: "return",
    4: "produce",
    5: "attack",
}

PREFLIGHT_24_ENV_ID = "MicrortsRandomEnemyShapedReward1-v1"
PREFLIGHT_24_MAP = "maps/24x24/basesWorkers24x24.xml"
ARCH_OLD = "legacy032_reference_gridnet_v0"
ARCH_RES_AWARE = "legacy032_resolution_aware_gridnet_v1"


@dataclass
class EvalWarnings:
    warnings: List[str]

    def add(self, msg: str) -> None:
        if msg not in self.warnings:
            self.warnings.append(msg)


class CategoricalMasked(Categorical):
    def __init__(self, probs=None, logits=None, validate_args=None, masks=None):
        if masks is None:
            masks = []
        self.masks = masks
        if len(self.masks) == 0:
            super().__init__(probs=probs, logits=logits, validate_args=validate_args)
        else:
            self.masks = masks.bool()
            logits = torch.where(self.masks, logits, torch.tensor(-1e8, device=logits.device))
            super().__init__(probs=probs, logits=logits, validate_args=validate_args)


class Transpose(nn.Module):
    def __init__(self, permutation: Tuple[int, int, int, int]):
        super().__init__()
        self.permutation = permutation

    def forward(self, x):
        return x.permute(self.permutation)


def layer_init(layer, std=np.sqrt(2), bias_const=0.0):
    torch.nn.init.orthogonal_(layer.weight, std)
    torch.nn.init.constant_(layer.bias, bias_const)
    return layer


class Encoder(nn.Module):
    def __init__(self, input_channels: int):
        super().__init__()
        self._encoder = nn.Sequential(
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
            nn.MaxPool2d(3, stride=2, padding=1),
        )

    def forward(self, x):
        return self._encoder(x)


class Decoder(nn.Module):
    def __init__(self, output_channels: int):
        super().__init__()
        self.deconv = nn.Sequential(
            layer_init(nn.ConvTranspose2d(256, 128, 3, stride=2, padding=1, output_padding=1)),
            nn.ReLU(),
            layer_init(nn.ConvTranspose2d(128, 64, 3, stride=2, padding=1, output_padding=1)),
            nn.ReLU(),
            layer_init(nn.ConvTranspose2d(64, 32, 3, stride=2, padding=1, output_padding=1)),
            nn.ReLU(),
            layer_init(nn.ConvTranspose2d(32, output_channels, 3, stride=2, padding=1, output_padding=1)),
            Transpose((0, 2, 3, 1)),
        )

    def forward(self, x):
        return self.deconv(x)


class ResolutionAwareDecoder(nn.Module):
    def __init__(self, output_channels: int, target_hw: Tuple[int, int]):
        super().__init__()
        self.target_hw = (int(target_hw[0]), int(target_hw[1]))
        self.backbone = nn.Sequential(
            layer_init(nn.ConvTranspose2d(256, 128, 3, stride=2, padding=1, output_padding=1)),
            nn.ReLU(),
            layer_init(nn.ConvTranspose2d(128, 64, 3, stride=2, padding=1, output_padding=1)),
            nn.ReLU(),
            layer_init(nn.ConvTranspose2d(64, 32, 3, stride=2, padding=1, output_padding=1)),
            nn.ReLU(),
        )
        self.final_conv = layer_init(nn.Conv2d(32, output_channels, kernel_size=1), std=0.01)

    def forward(self, x):
        x = self.backbone(x)
        if tuple(x.shape[-2:]) != self.target_hw:
            x = torch.nn.functional.interpolate(x, size=self.target_hw, mode="bilinear", align_corners=False)
        x = self.final_conv(x)
        return x.permute(0, 2, 3, 1)


class Legacy032Policy(nn.Module):
    def __init__(
        self,
        obs_channels: int,
        nvec: List[int],
        mapsize: int,
        obs_hw: Tuple[int, int],
        architecture_name: str = ARCH_OLD,
    ):
        super().__init__()
        self.mapsize = mapsize
        self.nvec = nvec
        output_channels = int(sum(nvec[1:]))
        self.architecture_name = architecture_name

        self.encoder = Encoder(obs_channels)
        if architecture_name == ARCH_RES_AWARE:
            self.actor = ResolutionAwareDecoder(output_channels, target_hw=obs_hw)
        else:
            self.actor = Decoder(output_channels)
        self.critic = nn.Sequential(
            nn.AdaptiveAvgPool2d((1, 1)),
            nn.Flatten(),
            layer_init(nn.Linear(256, 128), std=1),
            nn.ReLU(),
            layer_init(nn.Linear(128, 1), std=1),
        )

    def forward(self, x):
        return self.encoder(x)

    def get_action(
        self,
        obs_tensor: torch.Tensor,
        env,
        deterministic: bool,
        require_mask: bool,
        device: torch.device,
    ) -> Tuple[torch.Tensor, torch.Tensor, Dict[str, Any]]:
        logits = self.actor(self.forward(obs_tensor))
        split_sizes = self.nvec[1:]
        grid_logits = logits.reshape(-1, sum(split_sizes))
        split_logits = torch.split(grid_logits, split_sizes, dim=1)

        mask_tensor = None
        mask_available = False
        mask_source = None
        split_masks = None

        try:
            raw_masks = np.array(env.vec_client.getMasks(0))
            mask_tensor = torch.tensor(raw_masks, dtype=torch.float32, device=device)
            mask_tensor = mask_tensor.view(-1, mask_tensor.shape[-1])
            split_masks = torch.split(mask_tensor[:, 1:], split_sizes, dim=1)
            mask_available = True
            mask_source = "env.vec_client.getMasks(0)"
        except Exception:
            mask_available = False

        if require_mask and not mask_available:
            raise RuntimeError("Mask is required but could not be retrieved from env.vec_client.getMasks(0).")

        if split_masks is None:
            split_masks = [torch.ones_like(sl, device=device) for sl in split_logits]

        multi = [CategoricalMasked(logits=sl, masks=sm) for sl, sm in zip(split_logits, split_masks)]
        if deterministic:
            action_branches = [torch.argmax(c.logits, dim=1) for c in multi]
        else:
            action_branches = [c.sample() for c in multi]

        action = torch.stack(action_branches).T.view(-1, self.mapsize, len(split_sizes))
        entropies = torch.stack([c.entropy() for c in multi]).T

        source_valid_share = None
        if mask_tensor is not None:
            source_valid_share = float((mask_tensor[:, 0] > 0).float().mean().item())

        diag = {
            "mask_available": mask_available,
            "mask_source": mask_source,
            "mask_used_during_eval": bool(mask_available or not require_mask),
            "selected_action_mask_valid_share_step": None,
            "masked_invalid_prevented_count_step": None,
            "source_cell_valid_share_step": source_valid_share,
            "policy_entropy_proxy_step": float(entropies.mean().item()),
        }
        return action, entropies, diag


def _now_ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _parse_bool(value: str) -> bool:
    if isinstance(value, bool):
        return value
    v = value.strip().lower()
    if v in {"1", "true", "yes", "y", "on"}:
        return True
    if v in {"0", "false", "no", "n", "off"}:
        return False
    raise argparse.ArgumentTypeError(f"Invalid boolean value: {value}")


def _parse_action_space_from_metadata(value: str) -> List[int]:
    nums = [int(x) for x in re.findall(r"\d+", value)]
    if len(nums) < 2:
        raise ValueError(f"Could not parse action space from metadata: {value}")
    return nums


def _load_metadata(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_checkpoint(path: Path, device: torch.device) -> Dict[str, Any]:
    payload = torch.load(str(path), map_location=device)
    if isinstance(payload, dict) and "state_dict" in payload and isinstance(payload["state_dict"], dict):
        return payload["state_dict"]
    if isinstance(payload, dict):
        return payload
    raise ValueError("Checkpoint payload is not a state_dict-compatible dictionary.")


def _build_ai2s(num_bot_envs: int):
    from gym_microrts import microrts_ai

    ai2s = [microrts_ai.coacAI for _ in range(max(0, num_bot_envs - 6))] + [
        microrts_ai.randomBiasedAI for _ in range(min(num_bot_envs, 2))
    ] + [microrts_ai.lightRushAI for _ in range(min(num_bot_envs, 2))] + [
        microrts_ai.workerRushAI for _ in range(min(num_bot_envs, 2))
    ]
    if len(ai2s) < num_bot_envs:
        ai2s += [microrts_ai.coacAI for _ in range(num_bot_envs - len(ai2s))]
    return ai2s[:num_bot_envs]


def _create_reference_internal_env(metadata: Dict[str, Any]):
    from gym_microrts.envs.vec_env import MicroRTSGridModeVecEnv

    md_args = metadata.get("args", {}) if isinstance(metadata.get("args"), dict) else {}
    num_selfplay = int(md_args.get("num_selfplay_envs", 0))
    num_bot = int(md_args.get("num_bot_envs", 6))

    env = MicroRTSGridModeVecEnv(
        num_selfplay_envs=num_selfplay,
        num_bot_envs=num_bot,
        max_steps=2000,
        render_theme=2,
        ai2s=_build_ai2s(num_bot),
        map_path="maps/16x16/basesWorkers16x16.xml",
        reward_weight=np.array([10.0, 1.0, 1.0, 0.2, 1.0, 4.0]),
    )
    return env


def _create_target_24x24_gridmode_env(metadata: Dict[str, Any], max_steps: int):
    from gym_microrts.envs.vec_env import MicroRTSGridModeVecEnv

    md_args = metadata.get("args", {}) if isinstance(metadata.get("args"), dict) else {}
    num_selfplay = int(md_args.get("num_selfplay_envs", 0))
    num_bot = int(md_args.get("num_bot_envs", 6))

    env = MicroRTSGridModeVecEnv(
        num_selfplay_envs=num_selfplay,
        num_bot_envs=num_bot,
        max_steps=max_steps,
        render_theme=2,
        ai2s=_build_ai2s(num_bot),
        map_path=PREFLIGHT_24_MAP,
        reward_weight=np.array([10.0, 1.0, 1.0, 0.2, 1.0, 4.0]),
    )
    return env


def _metadata_contract(metadata: Dict[str, Any]) -> Tuple[Optional[List[int]], Optional[List[int]]]:
    md_obs = metadata.get("observation_space")
    md_nvec = None
    try:
        md_nvec = _parse_action_space_from_metadata(str(metadata.get("action_space")))
    except Exception:
        md_nvec = None
    if not isinstance(md_obs, list):
        md_obs = None
    return md_obs, md_nvec


def _decode_checkpoint_step(path: Path) -> Optional[int]:
    m = re.search(r"agent_step_(\d+)\.pt$", path.name)
    if not m:
        return None
    return int(m.group(1))


def _safe_std(values: List[float]) -> Optional[float]:
    if not values:
        return None
    arr = np.array(values, dtype=np.float64)
    return float(arr.std())


def _compatibility_checks(metadata: Dict[str, Any]) -> Dict[str, Any]:
    checks: Dict[str, Any] = {
        "training_metadata_env_id": metadata.get("env_id"),
        "training_metadata_observation_shape": metadata.get("observation_space"),
        "training_metadata_action_space": metadata.get("action_space"),
        "preflight_24x24_global_single_expected_nvec": [576, 6, 4, 4, 4, 4, 7, 576],
        "target_24x24_gridmode_expected_nvec": [576, 6, 4, 4, 4, 4, 7, 49],
        "reference_internal_expected_nvec": [256, 6, 4, 4, 4, 4, 7, 49],
        "reference_internal_compatible": False,
        "target_24x24_gridmode_compatible": False,
        "target_24x24_gridmode_reason": None,
    }

    md_obs = metadata.get("observation_space")
    md_action_str = metadata.get("action_space")
    try:
        md_nvec = _parse_action_space_from_metadata(str(md_action_str))
    except Exception:
        md_nvec = None

    if md_obs == [16, 16, 27] and md_nvec == checks["reference_internal_expected_nvec"]:
        checks["reference_internal_compatible"] = True

    if md_obs == [24, 24, 27] and md_nvec == checks["target_24x24_gridmode_expected_nvec"]:
        checks["target_24x24_gridmode_compatible"] = True
    else:
        checks["target_24x24_gridmode_reason"] = (
            "Checkpoint architecture/training metadata correspond to reference internal 16x16 grid mode "
            "(MultiDiscrete [256,6,4,4,4,4,7,49]), or to a non-gridmode target, not target 24x24 gridmode "
            "(MultiDiscrete [576,6,4,4,4,4,7,49])."
        )

    checks["metadata_nvec_parsed"] = md_nvec
    return checks


def _run_single_eval_mode(
    policy: Legacy032Policy,
    env,
    episodes: int,
    seed: int,
    device: torch.device,
    deterministic: bool,
    require_mask: bool,
    max_steps_per_episode: int,
    write_action_trace: bool,
    warnings: EvalWarnings,
) -> Dict[str, Any]:
    np.random.seed(seed)
    torch.manual_seed(seed)

    obs = env.reset()
    if isinstance(obs, tuple):
        obs = obs[0]

    num_envs = int(obs.shape[0])
    ep_returns = np.zeros((num_envs,), dtype=np.float64)
    ep_lengths = np.zeros((num_envs,), dtype=np.int64)

    episodes_done = 0
    episode_returns: List[float] = []
    episode_lengths: List[int] = []
    episode_end_reason_counts = {"env_done": 0, "outer_loop_limit": 0, "unknown": 0}
    terminal_types: List[Any] = []
    total_steps = 0

    action_type_counts = {name: 0 for name in ACTION_TYPE_NAMES.values()}
    selected_valid_num = 0.0
    selected_valid_den = 0
    masked_invalid_prevented_count: Optional[int] = None
    source_valid_running: List[float] = []
    entropy_running: List[float] = []
    mask_seen = False
    mask_metric_warning_emitted = False
    repeated_same_total = 0
    repeated_same_count = 0

    attack_action_count = 0
    produce_action_count = 0

    win = 0
    loss = 0
    draw = 0

    last_action_flat: Optional[np.ndarray] = None
    action_trace: List[Dict[str, Any]] = []

    while episodes_done < episodes:
        obs_t = torch.tensor(obs, dtype=torch.float32, device=device)
        with torch.no_grad():
            action_t, entropy_t, diag = policy.get_action(
                obs_tensor=obs_t,
                env=env,
                deterministic=deterministic,
                require_mask=require_mask,
                device=device,
            )

        action_np = action_t.detach().cpu().numpy().astype(np.int32)
        step_result = env.step(action_np)

        if len(step_result) == 4:
            next_obs, rewards, dones, infos = step_result
            truncs = np.zeros_like(dones)
        else:
            next_obs, rewards, dones, truncs, infos = step_result

        rewards = np.asarray(rewards)
        dones = np.asarray(dones)
        truncs = np.asarray(truncs)

        total_steps += int(action_np.shape[0])
        ep_returns += rewards
        ep_lengths += 1

        action_types = action_np[:, :, 0].reshape(-1)
        for k, name in ACTION_TYPE_NAMES.items():
            action_type_counts[name] += int((action_types == k).sum())

        attack_action_count += int((action_types == 5).sum())
        produce_action_count += int((action_types == 4).sum())

        if diag.get("selected_action_mask_valid_share_step") is not None:
            selected_valid_num += float(diag["selected_action_mask_valid_share_step"])
            selected_valid_den += 1
        if diag.get("masked_invalid_prevented_count_step") is not None:
            if masked_invalid_prevented_count is None:
                masked_invalid_prevented_count = 0
            masked_invalid_prevented_count += int(diag["masked_invalid_prevented_count_step"])
        else:
            if not mask_metric_warning_emitted:
                warnings.add(
                    "selected_action_mask_valid_share and masked_invalid_prevented_count are set to null because mask bit semantics are ambiguous in this legacy runtime."
                )
                mask_metric_warning_emitted = True
        if diag.get("source_cell_valid_share_step") is not None:
            source_valid_running.append(float(diag["source_cell_valid_share_step"]))
            mask_seen = True
        if diag.get("policy_entropy_proxy_step") is not None:
            entropy_running.append(float(diag["policy_entropy_proxy_step"]))

        action_flat = action_np.reshape(-1)
        if last_action_flat is not None and last_action_flat.shape == action_flat.shape:
            repeated_same_total += int(np.sum(last_action_flat == action_flat))
            repeated_same_count += int(action_flat.size)
        last_action_flat = action_flat.copy()

        if write_action_trace and len(action_trace) < 200:
            action_trace.append(
                {
                    "step": len(action_trace),
                    "deterministic": deterministic,
                    "action_type_counts_step": {
                        name: int((action_types == k).sum()) for k, name in ACTION_TYPE_NAMES.items()
                    },
                    "entropy": float(entropy_t.mean().item()),
                }
            )

        for i in range(num_envs):
            env_done = bool(dones[i]) or bool(truncs[i])
            outer_limit_done = int(ep_lengths[i]) >= max_steps_per_episode
            done = env_done or outer_limit_done
            if done:
                if env_done:
                    episode_end_reason_counts["env_done"] += 1
                elif outer_limit_done:
                    episode_end_reason_counts["outer_loop_limit"] += 1
                else:
                    episode_end_reason_counts["unknown"] += 1
                episode_returns.append(float(ep_returns[i]))
                episode_lengths.append(int(ep_lengths[i]))
                episodes_done += 1
                if isinstance(infos, (list, tuple)) and i < len(infos):
                    info_i = infos[i]
                else:
                    info_i = infos

                if isinstance(info_i, dict):
                    if "terminal_type" in info_i:
                        terminal_types.append(info_i.get("terminal_type"))
                    raw_rewards = info_i.get("raw_rewards")
                    if isinstance(raw_rewards, (list, tuple, np.ndarray)) and len(raw_rewards) > 0:
                        try:
                            last_reward = float(raw_rewards[-1])
                            if last_reward > 0:
                                win += 1
                            elif last_reward < 0:
                                loss += 1
                            else:
                                draw += 1
                        except Exception:
                            pass

                ep_returns[i] = 0.0
                ep_lengths[i] = 0

                if episodes_done >= episodes:
                    break

        obs = next_obs

        if episodes_done == 0 and total_steps > (max_steps_per_episode * num_envs * 2):
            warnings.add("No completed episode observed in expected horizon; evaluation may be stuck.")
            break

    total_action_count = int(sum(action_type_counts.values()))
    action_type_share = {
        k: (float(v) / total_action_count if total_action_count > 0 else None)
        for k, v in action_type_counts.items()
    }

    noop_share = action_type_share.get("noop")
    non_noop_share = None
    if noop_share is not None:
        non_noop_share = float(1.0 - noop_share)

    harvest = action_type_counts.get("harvest", 0)
    returns = action_type_counts.get("return", 0)
    harvest_return_balance = None
    if returns > 0:
        harvest_return_balance = float(harvest) / float(returns)

    return {
        "episodes_requested": episodes,
        "episodes_completed": len(episode_returns),
        "episode_lengths": episode_lengths,
        "episode_end_reason_counts": episode_end_reason_counts,
        "observed_max_episode_length": (max(episode_lengths) if episode_lengths else None),
        "episode_returns": episode_returns,
        "mean_return": float(np.mean(episode_returns)) if episode_returns else None,
        "std_return": _safe_std(episode_returns),
        "terminal_types": terminal_types if terminal_types else None,
        "win_count": win if (win + loss + draw) > 0 else None,
        "loss_count": loss if (win + loss + draw) > 0 else None,
        "draw_count": draw if (win + loss + draw) > 0 else None,
        "total_steps": total_steps,
        "action_type_counts": action_type_counts,
        "action_type_share": action_type_share,
        "src_cell_valid_share": float(np.mean(source_valid_running)) if source_valid_running else None,
        "src_cell_unit_share": None,
        "masked_invalid_prevented_count": masked_invalid_prevented_count,
        "selected_action_mask_valid_share": (
            float(selected_valid_num / selected_valid_den) if selected_valid_den > 0 else None
        ),
        "attack_action_count": attack_action_count,
        "produce_action_count": produce_action_count,
        "harvest_return_balance": harvest_return_balance,
        "effective_activity_share": non_noop_share,
        "repeated_same_action_share": (
            float(repeated_same_total / repeated_same_count) if repeated_same_count > 0 else None
        ),
        "policy_entropy_proxy": float(np.mean(entropy_running)) if entropy_running else None,
        "move_share": action_type_share.get("move"),
        "noop_share": noop_share,
        "mask_seen_any_step": mask_seen,
        "action_trace": action_trace if write_action_trace else None,
    }


def _decide_gate(
    run: Dict[str, Any],
    require_mask: bool,
    warnings: List[str],
) -> Tuple[str, List[str]]:
    reasons: List[str] = []

    if not run.get("checkpoint_load_ok", False):
        reasons.append("checkpoint not loadable")
    if not run.get("policy_architecture_load_ok", False):
        reasons.append("policy architecture reconstruction failed")
    if not run.get("inference_ok", False):
        reasons.append("policy inference failed")

    eval_result = run.get("eval_result") or {}
    if not eval_result:
        reasons.append("action distribution not recorded")
    else:
        if eval_result.get("episodes_completed", 0) < 1:
            reasons.append("evaluation completed zero episodes")
        if eval_result.get("action_type_counts") is None:
            reasons.append("action distribution not recorded")
        if require_mask and not run.get("mask_used_during_eval", False):
            reasons.append("mask required but not used")

    if reasons:
        return "FAIL", reasons

    non_noop_share = None
    move_share = None
    if eval_result:
        non_noop_share = eval_result.get("effective_activity_share")
        move_share = eval_result.get("move_share")

    severe_warning = any("only on reference internal env" in w.lower() for w in warnings)

    if (
        non_noop_share is not None
        and non_noop_share > 0.05
        and ((move_share is not None and move_share > 0.01) or (eval_result.get("attack_action_count", 0) > 0))
        and not severe_warning
    ):
        return "PASS", []

    if eval_result:
        return "PASS_WITH_WARNINGS", []

    return "INCONCLUSIVE", []


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate legacy032 teacher checkpoint with behavior gate.")
    parser.add_argument("--checkpoint-path", required=True)
    parser.add_argument("--model-metadata-path", default=None)
    parser.add_argument("--run-label", default="stage3_behavior_gate")
    parser.add_argument("--episodes", type=int, default=8)
    parser.add_argument("--seed", type=int, default=101)
    parser.add_argument("--device", default="cpu", choices=["cpu", "cuda"])
    parser.add_argument("--output-dir", default="python/week5_teacher_legacy032/reports")
    parser.add_argument("--eval-mode", default="both", choices=["deterministic", "stochastic", "both"])
    parser.add_argument(
        "--env-mode",
        default="auto",
        choices=["reference_internal", "preflight_24x24", "target_24x24_gridmode", "auto"],
    )
    parser.add_argument("--require-mask", type=_parse_bool, default=True)
    parser.add_argument("--max-steps-per-episode", type=int, default=2000)
    parser.add_argument(
        "--env-max-steps",
        type=int,
        default=None,
        help="Internal env max_steps passed to MicroRTSGridModeVecEnv. Default: match --max-steps-per-episode.",
    )
    parser.add_argument("--write-action-trace", action="store_true", default=False)
    parser.add_argument("--dry-run", action="store_true", default=False)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    ts = _now_ts()
    repo_root = _repo_root()

    checkpoint_path = Path(args.checkpoint_path)
    if not checkpoint_path.is_absolute():
        checkpoint_path = (repo_root / checkpoint_path).resolve()

    if args.model_metadata_path:
        metadata_path = Path(args.model_metadata_path)
        if not metadata_path.is_absolute():
            metadata_path = (repo_root / metadata_path).resolve()
    else:
        metadata_path = checkpoint_path.parent / "model_metadata.json"

    output_dir = Path(args.output_dir)
    if not output_dir.is_absolute():
        output_dir = (repo_root / output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    run = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "run_label": args.run_label,
        "checkpoint_path": str(checkpoint_path),
        "model_metadata_path": str(metadata_path),
        "checkpoint_load_ok": False,
        "policy_architecture_load_ok": False,
        "inference_ok": False,
        "eval_env_id": None,
        "eval_map_path": None,
        "eval_observation_shape": None,
        "eval_action_space": None,
        "eval_action_representation": None,
        "mask_available": None,
        "mask_source": None,
        "mask_used_during_eval": False,
        "max_steps_per_episode": int(args.max_steps_per_episode),
        "env_max_steps": None,
        "env_matches_training_metadata": False,
        "env_matches_target_24x24": False,
        "warnings": [],
        "errors": [],
        "eval_results": {},
        "eval_result": None,
    }

    warn = EvalWarnings(warnings=[])

    if args.dry_run:
        warn.add("Dry-run enabled; evaluation was not executed.")

    env_max_steps = int(args.max_steps_per_episode) if args.env_max_steps is None else int(args.env_max_steps)
    run["env_max_steps"] = env_max_steps

    if not checkpoint_path.exists():
        run["errors"].append("Checkpoint path does not exist.")
    if not metadata_path.exists():
        run["errors"].append("Model metadata path does not exist.")

    metadata = None
    compatibility = None
    device = torch.device("cuda" if args.device == "cuda" and torch.cuda.is_available() else "cpu")

    if not run["errors"]:
        try:
            metadata = _load_metadata(metadata_path)
            compatibility = _compatibility_checks(metadata)
            run["compatibility"] = compatibility
            run["env_matches_training_metadata"] = False
            run["env_matches_target_24x24"] = False
            if not compatibility.get("target_24x24_gridmode_compatible", False):
                warn.add(
                    "Checkpoint is evaluable only on reference internal env/action space, not target 24x24 preflight env."
                )
        except Exception as exc:
            run["errors"].append(f"Failed to load or parse metadata: {exc}")

    state_dict = None
    if not run["errors"]:
        try:
            state_dict = _load_checkpoint(checkpoint_path, device)
            run["checkpoint_load_ok"] = True
        except Exception as exc:
            run["errors"].append(f"Failed to load checkpoint: {exc}")

    policy = None
    env = None
    eval_env_mode = args.env_mode

    if not run["errors"] and metadata is not None and state_dict is not None:
        try:
            md_obs = metadata.get("observation_space")
            md_nvec = _parse_action_space_from_metadata(str(metadata.get("action_space")))
            if not isinstance(md_obs, list) or len(md_obs) != 3:
                raise ValueError(f"Invalid metadata observation_space: {md_obs}")

            mapsize = int(md_obs[0] * md_obs[1])
            architecture_name = str(metadata.get("architecture_name") or ARCH_OLD)
            policy = Legacy032Policy(
                obs_channels=int(md_obs[2]),
                nvec=md_nvec,
                mapsize=mapsize,
                obs_hw=(int(md_obs[0]), int(md_obs[1])),
                architecture_name=architecture_name,
            ).to(device)
            missing, unexpected = policy.load_state_dict(state_dict, strict=False)
            if missing or unexpected:
                warn.add(f"State dict loaded with non-strict diffs; missing={len(missing)} unexpected={len(unexpected)}")
            run["policy_architecture_load_ok"] = True
        except Exception as exc:
            run["errors"].append(f"Failed to reconstruct policy architecture: {exc}")

    if not run["errors"] and not args.dry_run:
        try:
            if eval_env_mode == "auto":
                eval_env_mode = (
                    "target_24x24_gridmode"
                    if compatibility and compatibility.get("target_24x24_gridmode_compatible", False)
                    else "reference_internal"
                )

            if eval_env_mode == "target_24x24_gridmode" or eval_env_mode == "preflight_24x24":
                if compatibility and not compatibility.get("target_24x24_gridmode_compatible", False):
                    raise RuntimeError(
                        "target_24x24_gridmode requested but checkpoint metadata is 16x16 reference-internal. "
                        + (
                            compatibility.get("target_24x24_gridmode_reason")
                            or "Checkpoint is incompatible with target 24x24 action/observation space."
                        )
                    )
                env = _create_target_24x24_gridmode_env(metadata, env_max_steps)
                run["eval_env_id"] = PREFLIGHT_24_ENV_ID
                run["eval_map_path"] = PREFLIGHT_24_MAP
            else:
                env = _create_reference_internal_env(metadata)
                run["eval_env_id"] = metadata.get("env_id", "MicrortsDefeatCoacAIShaped-v3")
                run["eval_map_path"] = "maps/16x16/basesWorkers16x16.xml"

            obs_shape = list(env.observation_space.shape)
            nvec = [int(x) for x in env.action_space.nvec.tolist()]
            run["eval_observation_shape"] = obs_shape
            run["eval_action_space"] = nvec
            run["eval_action_representation"] = "GYM_MICRORTS_032_REFERENCE_GRIDMODE"

            md_obs, md_nvec = _metadata_contract(metadata)
            run["env_matches_training_metadata"] = bool(md_obs == obs_shape and md_nvec == nvec)
            run["env_matches_target_24x24"] = bool(obs_shape == [24, 24, 27] and nvec == [576, 6, 4, 4, 4, 4, 7, 49])

            eval_modes: List[Tuple[str, bool]]
            if args.eval_mode == "both":
                eval_modes = [("deterministic", True), ("stochastic", False)]
            elif args.eval_mode == "deterministic":
                eval_modes = [("deterministic", True)]
            else:
                eval_modes = [("stochastic", False)]

            for mode_name, deterministic in eval_modes:
                result = _run_single_eval_mode(
                    policy=policy,
                    env=env,
                    episodes=args.episodes,
                    seed=args.seed,
                    device=device,
                    deterministic=deterministic,
                    require_mask=args.require_mask,
                    max_steps_per_episode=args.max_steps_per_episode,
                    write_action_trace=args.write_action_trace,
                    warnings=warn,
                )
                run["eval_results"][mode_name] = result

            observed_lengths = [
                int(v.get("observed_max_episode_length"))
                for v in run["eval_results"].values()
                if isinstance(v, dict) and v.get("observed_max_episode_length") is not None
            ]
            run["observed_max_episode_length"] = max(observed_lengths) if observed_lengths else None
            if (
                int(args.max_steps_per_episode) >= 6000
                and run["observed_max_episode_length"] is not None
                and int(run["observed_max_episode_length"]) <= 2000
            ):
                warn.add(
                    "Observed max episode length is <= 2000 while max_steps_per_episode=6000; this suggests an additional internal cap."
                )

            primary_key = "stochastic" if "stochastic" in run["eval_results"] else next(iter(run["eval_results"].keys()), None)
            run["eval_result"] = run["eval_results"].get(primary_key) if primary_key else None

            if run["eval_result"] is not None:
                run["inference_ok"] = True
                run["mask_available"] = bool(run["eval_result"].get("mask_seen_any_step", False))
                run["mask_source"] = "env.vec_client.getMasks(0)"
                run["mask_used_during_eval"] = bool(run["mask_available"])

        except Exception as exc:
            run["errors"].append(f"Evaluation failed: {exc}")
            run["inference_ok"] = False
        finally:
            if env is not None:
                try:
                    env.close()
                except Exception:
                    pass

    run["warnings"].extend(warn.warnings)

    if run.get("eval_result") is None and run.get("eval_results"):
        run["eval_result"] = next(iter(run["eval_results"].values()))

    decision, decision_reasons = _decide_gate(run=run, require_mask=args.require_mask, warnings=run["warnings"])
    run["gate_decision"] = decision
    run["gate_reasons"] = decision_reasons

    checkpoint_step = _decode_checkpoint_step(checkpoint_path)
    filename_prefix = f"{args.run_label}_{ts}"
    if "smoke" in args.run_label.lower():
        filename_prefix = f"stage3_smoke_checkpoint_behavior_gate_{ts}"

    json_path = output_dir / f"{filename_prefix}.json"
    md_path = output_dir / f"{filename_prefix}.md"

    json_path.write_text(json.dumps(run, indent=2, ensure_ascii=True), encoding="utf-8")

    summary_eval = run.get("eval_result") or {}
    md_lines = [
        "# Stage 3 Behavior Gate Report",
        "",
        f"- run_label: {args.run_label}",
        f"- checkpoint_path: {checkpoint_path}",
        f"- metadata_path: {metadata_path}",
        f"- checkpoint_step: {checkpoint_step}",
        f"- gate_decision: {run['gate_decision']}",
        "",
        "## Compatibility",
        "",
        f"- env_matches_training_metadata: {run['env_matches_training_metadata']}",
        f"- env_matches_target_24x24: {run['env_matches_target_24x24']}",
        f"- eval_env_id: {run['eval_env_id']}",
        f"- eval_map_path: {run['eval_map_path']}",
        f"- eval_observation_shape: {run['eval_observation_shape']}",
        f"- eval_action_space: {run['eval_action_space']}",
        f"- eval_action_representation: {run['eval_action_representation']}",
        "",
        "## Core checks",
        "",
        f"- checkpoint_load_ok: {run['checkpoint_load_ok']}",
        f"- policy_architecture_load_ok: {run['policy_architecture_load_ok']}",
        f"- inference_ok: {run['inference_ok']}",
        f"- mask_available: {run['mask_available']}",
        f"- mask_source: {run['mask_source']}",
        f"- mask_used_during_eval: {run['mask_used_during_eval']}",
        f"- max_steps_per_episode: {run['max_steps_per_episode']}",
        f"- env_max_steps: {run['env_max_steps']}",
        f"- observed_max_episode_length: {run.get('observed_max_episode_length')}",
        "",
        "## Behavior metrics (primary eval mode)",
        "",
        f"- episodes_requested: {summary_eval.get('episodes_requested')}",
        f"- episodes_completed: {summary_eval.get('episodes_completed')}",
        f"- episode_end_reason_counts: {summary_eval.get('episode_end_reason_counts')}",
        f"- observed_max_episode_length: {summary_eval.get('observed_max_episode_length')}",
        f"- mean_return: {summary_eval.get('mean_return')}",
        f"- std_return: {summary_eval.get('std_return')}",
        f"- noop_share: {summary_eval.get('noop_share')}",
        f"- move_share: {summary_eval.get('move_share')}",
        f"- effective_activity_share: {summary_eval.get('effective_activity_share')}",
        f"- attack_action_count: {summary_eval.get('attack_action_count')}",
        f"- produce_action_count: {summary_eval.get('produce_action_count')}",
        f"- policy_entropy_proxy: {summary_eval.get('policy_entropy_proxy')}",
        f"- action_type_counts: {summary_eval.get('action_type_counts')}",
        "",
        "## Gate reasons",
        "",
    ]

    if run["gate_reasons"]:
        md_lines.extend([f"- {x}" for x in run["gate_reasons"]])
    else:
        md_lines.append("- none")

    md_lines.extend(["", "## Warnings", ""])
    if run["warnings"]:
        md_lines.extend([f"- {w}" for w in run["warnings"]])
    else:
        md_lines.append("- none")

    md_lines.extend(["", "## Errors", ""])
    if run["errors"]:
        md_lines.extend([f"- {e}" for e in run["errors"]])
    else:
        md_lines.append("- none")

    md_lines.extend(["", f"- json_report: {json_path}"])
    md_path.write_text("\n".join(md_lines), encoding="utf-8")

    print(
        json.dumps(
            {
                "gate_decision": run["gate_decision"],
                "json_report": str(json_path),
                "md_report": str(md_path),
                "checkpoint_load_ok": run["checkpoint_load_ok"],
                "policy_architecture_load_ok": run["policy_architecture_load_ok"],
                "inference_ok": run["inference_ok"],
            },
            indent=2,
        )
    )

    if run["gate_decision"] in {"PASS", "PASS_WITH_WARNINGS"}:
        return 0
    if run["gate_decision"] == "INCONCLUSIVE":
        return 2
    return 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception:
        traceback.print_exc()
        raise SystemExit(1)
