from __future__ import annotations

import argparse
import json
import re
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
SOURCE_CELL_AMBIGUOUS_WARNING = "source-cell metrics unavailable because mask bit semantics are ambiguous."


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
        split_masks = None

        try:
            raw_masks = np.array(env.vec_client.getMasks(0))
            mask_tensor = torch.tensor(raw_masks, dtype=torch.float32, device=device)
            mask_tensor = mask_tensor.view(-1, mask_tensor.shape[-1])
            split_masks = torch.split(mask_tensor[:, 1:], split_sizes, dim=1)
            mask_available = True
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


def load_legacy032_policy_checkpoint(path: Path, device: torch.device, strict_load: bool = True) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    payload = torch.load(str(path), map_location=device)
    details: Dict[str, Any] = {
        "checkpoint_format": None,
        "strict_load": bool(strict_load),
        "strict_load_status": "STRICT_LOAD_ENFORCED" if strict_load else "STRICT_LOAD_OPT_OUT",
    }
    if isinstance(payload, dict) and payload.get("checkpoint_kind") == "full_training_state":
        state_dict = payload.get("agent_state_dict")
        if not isinstance(state_dict, dict):
            raise ValueError("Full training checkpoint is missing agent_state_dict")
        details["checkpoint_format"] = "full_training_checkpoint"
        return state_dict, details
    if isinstance(payload, dict) and "state_dict" in payload and isinstance(payload["state_dict"], dict):
        details["checkpoint_format"] = "wrapped_state_dict"
        return payload["state_dict"], details
    if isinstance(payload, dict):
        details["checkpoint_format"] = "weights_only_state_dict"
        return payload, details
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


def _extract_info_value(info: Any, key: str) -> Optional[float]:
    if not isinstance(info, dict):
        return None
    if key not in info:
        return None
    value = info.get(key)
    if isinstance(value, (int, float, np.number)):
        return float(value)
    return None


def _safe_div(a: float, b: float) -> Optional[float]:
    if b <= 0:
        return None
    return float(a / b)


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
    sample_frame_interval: int,
    action_trace_path: Optional[Path],
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
    ep_attack_seen = np.zeros((num_envs,), dtype=np.bool_)

    episodes_done = 0
    episode_returns: List[float] = []
    episode_lengths: List[int] = []
    episodes_with_attack_action = 0
    total_steps = 0

    action_type_counts = {name: 0 for name in ACTION_TYPE_NAMES.values()}
    source_valid_running: List[float] = []
    entropy_running: List[float] = []
    repeated_same_total = 0
    repeated_same_count = 0

    first_produce_step: Optional[int] = None
    first_attack_step: Optional[int] = None
    first_barracks_or_unit_production_step: Optional[int] = None

    attack_action_count = 0
    produce_action_count = 0
    harvest_action_count = 0
    return_action_count = 0

    produce_type_branch_available = True
    produce_unit_type_counts: Dict[str, int] = {}

    worker_count_samples: List[float] = []
    base_count_samples: List[float] = []
    barracks_count_samples: List[float] = []
    resource_samples: List[float] = []

    worker_count_reason = "not present in env info payload"
    base_count_reason = "not present in env info payload"
    barracks_count_reason = "not present in env info payload"
    resource_reason = "not present in env info payload"

    last_action_flat: Optional[np.ndarray] = None
    action_trace_records = 0
    trace_handle = None

    if write_action_trace and action_trace_path is not None:
        action_trace_path.parent.mkdir(parents=True, exist_ok=True)
        trace_handle = action_trace_path.open("a", encoding="utf-8")

    try:
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

            step_attack = int((action_types == 5).sum())
            step_produce = int((action_types == 4).sum())
            step_harvest = int((action_types == 2).sum())
            step_return = int((action_types == 3).sum())

            attack_action_count += step_attack
            produce_action_count += step_produce
            harvest_action_count += step_harvest
            return_action_count += step_return

            if first_attack_step is None and step_attack > 0:
                first_attack_step = int(total_steps)
            if first_produce_step is None and step_produce > 0:
                first_produce_step = int(total_steps)
            if first_barracks_or_unit_production_step is None and step_produce > 0:
                first_barracks_or_unit_production_step = int(total_steps)

            per_env_attack = (action_np[:, :, 0] == 5).any(axis=1)
            ep_attack_seen = ep_attack_seen | per_env_attack

            if action_np.shape[-1] >= 6:
                produce_branch = action_np[:, :, 5].reshape(-1)
                produce_mask = action_types == 4
                if produce_mask.shape[0] == produce_branch.shape[0]:
                    selected = produce_branch[produce_mask]
                    for v in selected.tolist():
                        key = str(int(v))
                        produce_unit_type_counts[key] = produce_unit_type_counts.get(key, 0) + 1
                else:
                    produce_type_branch_available = False
            else:
                produce_type_branch_available = False

            if diag.get("source_cell_valid_share_step") is not None:
                source_valid_running.append(float(diag["source_cell_valid_share_step"]))
            if diag.get("policy_entropy_proxy_step") is not None:
                entropy_running.append(float(diag["policy_entropy_proxy_step"]))

            action_flat = action_np.reshape(-1)
            if last_action_flat is not None and last_action_flat.shape == action_flat.shape:
                repeated_same_total += int(np.sum(last_action_flat == action_flat))
                repeated_same_count += int(action_flat.size)
            last_action_flat = action_flat.copy()

            info_list = infos if isinstance(infos, (list, tuple)) else [infos for _ in range(num_envs)]
            for i, info_i in enumerate(info_list):
                worker_val = _extract_info_value(info_i, "worker_count")
                if worker_val is not None:
                    worker_count_samples.append(worker_val)
                    worker_count_reason = "available from env info: worker_count"

                base_val = _extract_info_value(info_i, "base_count")
                if base_val is not None:
                    base_count_samples.append(base_val)
                    base_count_reason = "available from env info: base_count"

                barracks_val = _extract_info_value(info_i, "barracks_count")
                if barracks_val is not None:
                    barracks_count_samples.append(barracks_val)
                    barracks_count_reason = "available from env info: barracks_count"

                resource_val = _extract_info_value(info_i, "resource")
                if resource_val is not None:
                    resource_samples.append(resource_val)
                    resource_reason = "available from env info: resource"

                env_done = bool(dones[i]) or bool(truncs[i])
                outer_limit_done = int(ep_lengths[i]) >= max_steps_per_episode
                done = env_done or outer_limit_done
                if done:
                    episode_returns.append(float(ep_returns[i]))
                    episode_lengths.append(int(ep_lengths[i]))
                    if bool(ep_attack_seen[i]):
                        episodes_with_attack_action += 1

                    ep_returns[i] = 0.0
                    ep_lengths[i] = 0
                    ep_attack_seen[i] = False
                    episodes_done += 1
                    if episodes_done >= episodes:
                        break

            if trace_handle is not None and sample_frame_interval > 0 and (total_steps % sample_frame_interval == 0):
                trace_record = {
                    "mode": "deterministic" if deterministic else "stochastic",
                    "global_step": int(total_steps),
                    "episodes_completed": int(episodes_done),
                    "action_type_counts_step": {
                        name: int((action_types == k).sum()) for k, name in ACTION_TYPE_NAMES.items()
                    },
                    "policy_entropy_proxy_step": float(entropy_t.mean().item()),
                    "source_cell_valid_share_step": diag.get("source_cell_valid_share_step"),
                }
                trace_handle.write(json.dumps(trace_record, ensure_ascii=True) + "\n")
                action_trace_records += 1

            obs = next_obs

            if episodes_done == 0 and total_steps > (max_steps_per_episode * num_envs * 2):
                warnings.add("No completed episode observed in expected horizon; evaluation may be stuck.")
                break
    finally:
        if trace_handle is not None:
            trace_handle.close()

    total_action_count = int(sum(action_type_counts.values()))
    action_type_share_all_cells = {
        k: (float(v) / total_action_count if total_action_count > 0 else None)
        for k, v in action_type_counts.items()
    }
    noop_share = action_type_share_all_cells.get("noop")
    non_noop_share = None if noop_share is None else float(1.0 - noop_share)

    source_semantics_confirmed = False
    if not source_semantics_confirmed:
        warnings.add(SOURCE_CELL_AMBIGUOUS_WARNING)

    source_cell_metrics = {
        "source_cell_valid_share_mean": None,
        "source_cell_count_mean": None,
        "noop_share_on_source_cells": None,
        "non_noop_share_on_source_cells": None,
        "action_type_share_on_source_cells": None,
        "move_share_on_source_cells": None,
        "harvest_share_on_source_cells": None,
        "return_share_on_source_cells": None,
        "produce_share_on_source_cells": None,
        "attack_share_on_source_cells": None,
        "unavailable_reason": SOURCE_CELL_AMBIGUOUS_WARNING,
    }

    all_cell_metrics = {
        "global_noop_share_all_cells": noop_share,
        "global_non_noop_share_all_cells": non_noop_share,
        "action_type_share_all_cells": action_type_share_all_cells,
        "repeated_same_action_share": (
            float(repeated_same_total / repeated_same_count) if repeated_same_count > 0 else None
        ),
        "policy_entropy_proxy": float(np.mean(entropy_running)) if entropy_running else None,
        "source_cell_valid_share_observed_mask_bit0": float(np.mean(source_valid_running)) if source_valid_running else None,
    }

    economy_metrics = {
        "harvest_action_count": int(harvest_action_count),
        "return_action_count": int(return_action_count),
        "produce_action_count": int(produce_action_count),
        "first_produce_step": first_produce_step,
        "economy_activity_present": bool((harvest_action_count + return_action_count + produce_action_count) > 0),
        "worker_count_proxy": float(np.mean(worker_count_samples)) if worker_count_samples else None,
        "worker_count_proxy_reason": worker_count_reason,
        "base_count_proxy": float(np.mean(base_count_samples)) if base_count_samples else None,
        "base_count_proxy_reason": base_count_reason,
        "barracks_count_proxy": float(np.mean(barracks_count_samples)) if barracks_count_samples else None,
        "barracks_count_proxy_reason": barracks_count_reason,
        "resource_proxy": float(np.mean(resource_samples)) if resource_samples else None,
        "resource_proxy_reason": resource_reason,
        "first_barracks_or_unit_production_step": first_barracks_or_unit_production_step,
    }

    production_metrics = {
        "produce_action_count": int(produce_action_count),
        "produce_action_share": _safe_div(float(produce_action_count), float(total_action_count)),
        "produce_unit_type_distribution": (
            {k: v for k, v in sorted(produce_unit_type_counts.items(), key=lambda x: int(x[0]))}
            if produce_type_branch_available and produce_unit_type_counts
            else None
        ),
        "first_produce_step": first_produce_step,
        "unit_production_diversity_proxy": int(len(produce_unit_type_counts)) if produce_unit_type_counts else 0,
        "produce_unit_type_distribution_reason": (
            "produce branch unavailable in action tensor"
            if not produce_type_branch_available
            else "derived from produce_type branch index (legacy032 gridmode)"
        ),
    }

    episodes_completed = len(episode_returns)
    episodes_with_no_attack = max(0, episodes_completed - int(episodes_with_attack_action))
    combat_metrics = {
        "attack_action_count": int(attack_action_count),
        "attack_action_share": _safe_div(float(attack_action_count), float(total_action_count)),
        "first_attack_step": first_attack_step,
        "episodes_with_attack_action": int(episodes_with_attack_action),
        "combat_activity_present": bool(attack_action_count > 0),
        "contact_seen": None,
        "first_contact_step": None,
        "episodes_with_contact": None,
        "timeout_or_no_contact_episode_count": int(episodes_with_no_attack),
        "contact_limitation": "contact cannot be determined exactly from available info; attack_action_count is used as weak proxy.",
    }

    limitations: List[str] = [
        SOURCE_CELL_AMBIGUOUS_WARNING,
        "contact cannot be determined exactly from available info; attack_action_count is used as weak proxy.",
    ]

    return {
        "episodes_requested": int(episodes),
        "episodes_completed": int(episodes_completed),
        "episode_lengths": episode_lengths,
        "observed_max_episode_length": (max(episode_lengths) if episode_lengths else None),
        "mean_return": float(np.mean(episode_returns)) if episode_returns else None,
        "std_return": float(np.std(np.array(episode_returns, dtype=np.float64))) if episode_returns else None,
        "all_cell_metrics": all_cell_metrics,
        "source_cell_metrics": source_cell_metrics,
        "economy_metrics": economy_metrics,
        "production_metrics": production_metrics,
        "combat_contact_metrics": combat_metrics,
        "limitations": limitations,
        "action_trace_records_written": int(action_trace_records),
    }


def _interpret(mode_result: Dict[str, Any]) -> str:
    all_cell = mode_result.get("all_cell_metrics", {})
    economy = mode_result.get("economy_metrics", {})
    production = mode_result.get("production_metrics", {})
    combat = mode_result.get("combat_contact_metrics", {})

    non_noop = all_cell.get("global_non_noop_share_all_cells")
    econ = bool(economy.get("economy_activity_present"))
    prod = int(production.get("produce_action_count") or 0) > 0
    attack = int(combat.get("attack_action_count") or 0) > 0

    if (non_noop is not None and non_noop < 0.02) and not econ and not prod and not attack:
        return "agent appears idle"
    if (econ or prod) and not attack:
        return "agent has economy/production activity but sparse combat"
    if (econ or prod) and attack:
        return "agent has economy/production activity but sparse combat"
    return "diagnostics inconclusive"


def _recommendation(interpretation: str) -> str:
    if interpretation == "agent appears idle":
        return "Run final comparison against a known active baseline and inspect sampled action trace for policy collapse patterns."
    if interpretation == "agent has economy/production activity but sparse combat":
        return "For final comparison, prioritize economy/production progression and first-attack timing, not only all-cell noop_share or return."
    return "Collect additional diagnostics with longer horizon and manual replay spot-check before final comparison."


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Extended large-map diagnostics for Stage 5C 1M checkpoint.")
    parser.add_argument("--checkpoint-path", required=True)
    parser.add_argument("--model-metadata-path", required=True)
    parser.add_argument("--run-label", default="stage5c_large_map_diagnostics")
    parser.add_argument("--episodes", type=int, default=8)
    parser.add_argument("--seed", type=int, default=101)
    parser.add_argument("--device", default="cpu", choices=["cpu", "cuda"])
    parser.add_argument("--output-dir", default="python/week5_teacher_legacy032/reports")
    parser.add_argument("--env-mode", default="target_24x24_gridmode", choices=["target_24x24_gridmode"])
    parser.add_argument("--require-mask", type=_parse_bool, default=True)
    parser.add_argument("--max-steps-per-episode", type=int, default=6000)
    parser.add_argument("--eval-mode", default="both", choices=["deterministic", "stochastic", "both"])
    parser.add_argument("--write-action-trace", action="store_true", default=False)
    parser.add_argument("--sample-frame-interval", type=int, default=25)
    parser.add_argument("--strict-load", type=_parse_bool, default=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    ts = _now_ts()
    repo_root = _repo_root()

    checkpoint_path = Path(args.checkpoint_path)
    if not checkpoint_path.is_absolute():
        checkpoint_path = (repo_root / checkpoint_path).resolve()

    metadata_path = Path(args.model_metadata_path)
    if not metadata_path.is_absolute():
        metadata_path = (repo_root / metadata_path).resolve()

    output_dir = Path(args.output_dir)
    if not output_dir.is_absolute():
        output_dir = (repo_root / output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    json_path = output_dir / f"stage5c_large_map_diagnostics_{ts}.json"
    md_path = output_dir / f"stage5c_large_map_diagnostics_{ts}.md"
    trace_path = output_dir / f"stage5c_large_map_action_trace_{ts}.jsonl"
    summary_path = output_dir / "STAGE5C_LARGE_MAP_DIAGNOSTICS_REPORT.md"

    run: Dict[str, Any] = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "run_label": args.run_label,
        "checkpoint_path": str(checkpoint_path),
        "model_metadata_path": str(metadata_path),
        "eval_env_id": PREFLIGHT_24_ENV_ID,
        "eval_map_path": PREFLIGHT_24_MAP,
        "max_steps_per_episode": int(args.max_steps_per_episode),
        "eval_mode": args.eval_mode,
        "env_mode": args.env_mode,
        "require_mask": bool(args.require_mask),
        "episodes": int(args.episodes),
        "sample_frame_interval": int(args.sample_frame_interval),
        "warnings": [],
        "errors": [],
        "eval_results": {},
        "interpretation": None,
        "recommendation_for_final_comparison": None,
        "action_trace_path": str(trace_path) if args.write_action_trace else None,
        "strict_load": bool(args.strict_load),
        "strict_load_status": "STRICT_LOAD_ENFORCED" if args.strict_load else "STRICT_LOAD_OPT_OUT",
    }

    warn = EvalWarnings(warnings=[])
    device = torch.device("cuda" if args.device == "cuda" and torch.cuda.is_available() else "cpu")

    if not checkpoint_path.exists():
        run["errors"].append("Checkpoint path does not exist.")
    if not metadata_path.exists():
        run["errors"].append("Model metadata path does not exist.")

    metadata = None
    state_dict = None
    env = None
    policy = None

    if not run["errors"]:
        try:
            metadata = _load_metadata(metadata_path)
            md_obs = metadata.get("observation_space")
            md_nvec = _parse_action_space_from_metadata(str(metadata.get("action_space")))
            if md_obs != [24, 24, 27] or md_nvec != [576, 6, 4, 4, 4, 4, 7, 49]:
                warn.add(
                    "Metadata contract differs from expected target_24x24_gridmode [24,24,27] + [576,6,4,4,4,4,7,49]."
                )
            run["metadata_contract"] = {
                "observation_space": md_obs,
                "action_space_nvec_parsed": md_nvec,
                "architecture_name": metadata.get("architecture_name"),
            }
        except Exception as exc:
            run["errors"].append(f"Failed to load metadata: {exc}")

    if not run["errors"]:
        try:
            state_dict, checkpoint_details = load_legacy032_policy_checkpoint(
                checkpoint_path,
                device,
                strict_load=bool(args.strict_load),
            )
            run["checkpoint_format"] = checkpoint_details.get("checkpoint_format")
            run["strict_load_status"] = checkpoint_details.get("strict_load_status")
        except Exception as exc:
            run["errors"].append(f"Failed to load checkpoint: {exc}")

    if not run["errors"] and metadata is not None and state_dict is not None:
        try:
            md_obs = metadata.get("observation_space")
            md_nvec = _parse_action_space_from_metadata(str(metadata.get("action_space")))
            mapsize = int(md_obs[0] * md_obs[1])
            architecture_name = str(metadata.get("architecture_name") or ARCH_OLD)
            policy = Legacy032Policy(
                obs_channels=int(md_obs[2]),
                nvec=md_nvec,
                mapsize=mapsize,
                obs_hw=(int(md_obs[0]), int(md_obs[1])),
                architecture_name=architecture_name,
            ).to(device)
            if args.strict_load:
                policy.load_state_dict(state_dict, strict=True)
            else:
                missing, unexpected = policy.load_state_dict(state_dict, strict=False)
                warn.add(f"STRICT_LOAD_STATUS=STRICT_LOAD_OPT_OUT missing={len(missing)} unexpected={len(unexpected)}")

            env = _create_target_24x24_gridmode_env(metadata, int(args.max_steps_per_episode))

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
                    episodes=int(args.episodes),
                    seed=int(args.seed),
                    device=device,
                    deterministic=deterministic,
                    require_mask=bool(args.require_mask),
                    max_steps_per_episode=int(args.max_steps_per_episode),
                    write_action_trace=bool(args.write_action_trace),
                    sample_frame_interval=max(1, int(args.sample_frame_interval)),
                    action_trace_path=trace_path if args.write_action_trace else None,
                    warnings=warn,
                )
                run["eval_results"][mode_name] = result

            primary_key = "stochastic" if "stochastic" in run["eval_results"] else next(iter(run["eval_results"].keys()))
            primary_result = run["eval_results"][primary_key]
            interpretation = _interpret(primary_result)
            recommendation = _recommendation(interpretation)
            run["interpretation"] = interpretation
            run["recommendation_for_final_comparison"] = recommendation

        except Exception as exc:
            run["errors"].append(f"Evaluation failed: {exc}")
            run["errors"].append(traceback.format_exc())
        finally:
            if env is not None:
                try:
                    env.close()
                except Exception:
                    pass

    run["warnings"].extend(warn.warnings)

    json_path.write_text(json.dumps(run, indent=2, ensure_ascii=True), encoding="utf-8")

    md_lines: List[str] = [
        "# Stage5C Large-Map Diagnostics",
        "",
        f"- run_label: {args.run_label}",
        f"- checkpoint_path: {checkpoint_path}",
        f"- model_metadata_path: {metadata_path}",
        f"- max_steps_per_episode: {args.max_steps_per_episode}",
        f"- eval_mode: {args.eval_mode}",
        "",
    ]

    if run.get("eval_results"):
        for mode_name, result in run["eval_results"].items():
            md_lines.extend(
                [
                    f"## {mode_name}",
                    "",
                    "### All-cell metrics",
                    "",
                    f"- {result.get('all_cell_metrics')}",
                    "",
                    "### Source-cell metrics",
                    "",
                    f"- {result.get('source_cell_metrics')}",
                    "",
                    "### Economy metrics",
                    "",
                    f"- {result.get('economy_metrics')}",
                    "",
                    "### Production metrics",
                    "",
                    f"- {result.get('production_metrics')}",
                    "",
                    "### Combat/contact metrics",
                    "",
                    f"- {result.get('combat_contact_metrics')}",
                    "",
                    "### Limitations",
                    "",
                ]
            )
            limits = result.get("limitations") or []
            if limits:
                md_lines.extend([f"- {x}" for x in limits])
            else:
                md_lines.append("- none")
            md_lines.append("")

    md_lines.extend(
        [
            "## Interpretation",
            "",
            f"- {run.get('interpretation')}",
            "",
            "## Recommendation for final comparison",
            "",
            f"- {run.get('recommendation_for_final_comparison')}",
            "",
            "## Warnings",
            "",
        ]
    )
    if run["warnings"]:
        md_lines.extend([f"- {w}" for w in run["warnings"]])
    else:
        md_lines.append("- none")

    md_lines.extend(["", "## Errors", ""])
    if run["errors"]:
        md_lines.extend([f"- {e}" for e in run["errors"]])
    else:
        md_lines.append("- none")

    md_path.write_text("\n".join(md_lines), encoding="utf-8")

    summary_lines = [
        "# STAGE5C LARGE MAP DIAGNOSTICS REPORT",
        "",
        f"- checkpoint path: {checkpoint_path}",
        f"- metadata path: {metadata_path}",
        f"- max_steps_per_episode={args.max_steps_per_episode}",
        f"- eval mode: {args.eval_mode}",
        "",
    ]

    primary_key = "stochastic" if "stochastic" in run.get("eval_results", {}) else next(iter(run.get("eval_results", {})), None)
    primary_result = run.get("eval_results", {}).get(primary_key) if primary_key else None

    if primary_result:
        summary_lines.extend(
            [
                "## All-cell metrics",
                "",
                f"- {primary_result.get('all_cell_metrics')}",
                "",
                "## Source-cell metrics",
                "",
                f"- {primary_result.get('source_cell_metrics')}",
                "",
                "## Economy metrics",
                "",
                f"- {primary_result.get('economy_metrics')}",
                "",
                "## Production metrics",
                "",
                f"- {primary_result.get('production_metrics')}",
                "",
                "## Combat/contact metrics",
                "",
                f"- {primary_result.get('combat_contact_metrics')}",
                "",
            ]
        )

    summary_lines.extend(["## Limitations", ""])
    summary_limitations: List[str] = []
    if primary_result:
        for item in primary_result.get("limitations") or []:
            if item not in summary_limitations:
                summary_limitations.append(str(item))
    for item in run.get("warnings") or []:
        if item not in summary_limitations:
            summary_limitations.append(str(item))
    if summary_limitations:
        summary_lines.extend([f"- {x}" for x in summary_limitations])
    else:
        summary_lines.append("- none")

    summary_lines.extend(
        [
            "",
            "## Interpretation",
            "",
            f"- {run.get('interpretation')}",
            "",
            "## Recommendation for final comparison",
            "",
            f"- {run.get('recommendation_for_final_comparison')}",
            "",
            f"- json_output: {json_path}",
            f"- md_output: {md_path}",
            f"- action_trace_output: {trace_path if args.write_action_trace else 'not requested'}",
        ]
    )
    summary_path.write_text("\n".join(summary_lines), encoding="utf-8")

    print(
        json.dumps(
            {
                "json_report": str(json_path),
                "md_report": str(md_path),
                "summary_report": str(summary_path),
                "action_trace": str(trace_path) if args.write_action_trace else None,
                "interpretation": run.get("interpretation"),
                "errors": run.get("errors"),
            },
            indent=2,
        )
    )

    return 0 if not run["errors"] else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception:
        traceback.print_exc()
        raise SystemExit(1)
