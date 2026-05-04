#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import tempfile
import traceback
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.distributions.categorical import Categorical

EXPECTED_OBS_SHAPE = [24, 24, 27]
EXPECTED_RAW_ACTION_NVEC = [576, 6, 4, 4, 4, 4, 7, 49]
EXPECTED_ARCHITECTURE = "legacy032_resolution_aware_gridnet_v1"
EXPECTED_MAP_PATH = "maps/24x24/basesWorkers24x24.xml"
EXPECTED_MAX_STEPS = 6000

ACTION_TYPE_NAMES = {
    0: "NoOp",
    1: "Move",
    2: "Harvest",
    3: "Return",
    4: "Produce",
    5: "Attack",
}


class AuditError(RuntimeError):
    pass


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
            x = F.interpolate(x, size=self.target_hw, mode="bilinear", align_corners=False)
        x = self.final_conv(x)
        return x.permute(0, 2, 3, 1)


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


class Legacy032Policy(nn.Module):
    def __init__(
        self,
        obs_channels: int,
        nvec: Sequence[int],
        mapsize: int,
        obs_hw: Tuple[int, int],
        architecture_name: str,
    ):
        super().__init__()
        self.mapsize = int(mapsize)
        self.nvec = [int(v) for v in nvec]
        output_channels = int(sum(self.nvec[1:]))

        self.encoder = Encoder(obs_channels)
        if architecture_name == EXPECTED_ARCHITECTURE:
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

    def infer_logits(self, obs_tensor: torch.Tensor) -> torch.Tensor:
        return self.actor(self.forward(obs_tensor))


@dataclass
class EpisodeProxy:
    episode_index: int
    reward: float
    episode_length: int
    terminal_reason: str
    movement_action_count: int
    production_action_count: int
    harvest_action_count: int
    return_action_count: int
    attack_action_count: int
    state_delta_mean_abs: Optional[float]
    state_changed_step_share: Optional[float]


def _now_compact() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _parse_nvec_from_metadata(value: Any) -> List[int]:
    nums = [int(x) for x in re.findall(r"\d+", str(value))]
    if len(nums) < 2:
        raise AuditError(f"Cannot parse action nvec from metadata value: {value}")
    return nums


def _resolve_path(path_str: str) -> Path:
    p = Path(path_str)
    if p.is_absolute():
        return p
    return (_repo_root() / p).resolve()


def _load_json(path: Path) -> Dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise AuditError(f"Failed to parse JSON: {path} ({exc})") from exc


def _load_checkpoint_payload(path: Path, device: torch.device) -> Dict[str, Any]:
    try:
        payload = torch.load(str(path), map_location=device)
    except Exception as exc:
        raise AuditError(f"Failed to load checkpoint: {path} ({exc})") from exc

    if isinstance(payload, dict) and "state_dict" in payload and isinstance(payload["state_dict"], dict):
        return payload["state_dict"]
    if isinstance(payload, dict):
        return payload
    raise AuditError("Checkpoint payload is not state_dict-compatible.")


def _assert_contract(metadata: Dict[str, Any]) -> Dict[str, Any]:
    obs_shape = [int(v) for v in (metadata.get("observation_space") or [])]
    if obs_shape != EXPECTED_OBS_SHAPE:
        raise AuditError(f"Metadata observation_space mismatch. expected={EXPECTED_OBS_SHAPE}, actual={obs_shape}")

    if isinstance(metadata.get("action_space_nvec"), list):
        nvec = [int(v) for v in metadata["action_space_nvec"]]
    elif isinstance(metadata.get("gridmode_expected_nvec"), list):
        nvec = [int(v) for v in metadata["gridmode_expected_nvec"]]
    else:
        nvec = _parse_nvec_from_metadata(metadata.get("action_space"))

    if nvec != EXPECTED_RAW_ACTION_NVEC:
        raise AuditError(
            "Metadata raw action nvec mismatch. "
            f"expected={EXPECTED_RAW_ACTION_NVEC}, actual={nvec}"
        )

    arch = str(metadata.get("architecture_name", "")).strip()
    if arch != EXPECTED_ARCHITECTURE:
        raise AuditError(f"Metadata architecture mismatch. expected={EXPECTED_ARCHITECTURE}, actual={arch}")

    return {
        "observation_space": obs_shape,
        "raw_action_nvec": nvec,
        "architecture_name": arch,
    }


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
        max_steps=int(max_steps),
        render_theme=2,
        ai2s=_build_ai2s(num_bot),
        map_path=EXPECTED_MAP_PATH,
        reward_weight=np.array([10.0, 1.0, 1.0, 0.2, 1.0, 4.0]),
    )
    return env


def _safe_reset_env(env: Any, seed: int) -> np.ndarray:
    try:
        obs = env.reset(seed=seed)
    except TypeError:
        obs = env.reset()
    except Exception:
        obs = env.reset()

    if isinstance(obs, tuple):
        obs = obs[0]
    arr = np.asarray(obs)
    if arr.ndim != 4:
        raise AuditError(f"Unexpected reset observation shape: {list(arr.shape)}")
    return arr


def _normalize_mask_array(raw_mask: Any, num_envs: int, mapsize: int, mask_dim: int) -> np.ndarray:
    arr = np.asarray(raw_mask)
    if arr.ndim == 2:
        if arr.shape == (num_envs * mapsize, mask_dim):
            return arr.reshape(num_envs, mapsize, mask_dim)
        raise AuditError(f"Unexpected 2D mask shape: {tuple(arr.shape)}")
    if arr.ndim == 3:
        if arr.shape == (num_envs, mapsize, mask_dim):
            return arr
        if arr.shape == (num_envs * mapsize, 1, mask_dim):
            return arr.reshape(num_envs, mapsize, mask_dim)
        raise AuditError(f"Unexpected 3D mask shape: {tuple(arr.shape)}")
    if arr.ndim == 4:
        if arr.shape[0] == num_envs and arr.shape[1] * arr.shape[2] == mapsize and arr.shape[3] == mask_dim:
            return arr.reshape(num_envs, mapsize, mask_dim)
        raise AuditError(f"Unexpected 4D mask shape: {tuple(arr.shape)}")
    raise AuditError(f"Unsupported mask rank: shape={tuple(arr.shape)}")


def _read_action_mask(env: Any, num_envs: int, mapsize: int, mask_dim: int) -> Tuple[Optional[np.ndarray], bool, str]:
    if hasattr(env, "vec_client") and hasattr(env.vec_client, "getMasks"):
        try:
            raw = env.vec_client.getMasks(0)
            return _normalize_mask_array(raw, num_envs, mapsize, mask_dim), True, "env.vec_client.getMasks(0)"
        except Exception:
            pass

    if hasattr(env, "get_action_mask"):
        try:
            raw = env.get_action_mask()
            return _normalize_mask_array(raw, num_envs, mapsize, mask_dim), True, "env.get_action_mask"
        except Exception:
            pass

    if hasattr(env, "action_masks"):
        try:
            raw = env.action_masks() if callable(env.action_masks) else env.action_masks
            return _normalize_mask_array(raw, num_envs, mapsize, mask_dim), True, "env.action_masks"
        except Exception:
            pass

    return None, False, "unavailable"


def _split_logits_and_masks(
    logits: torch.Tensor,
    nvec: Sequence[int],
    action_mask: Optional[torch.Tensor],
) -> Tuple[List[torch.Tensor], List[torch.Tensor]]:
    split_sizes = [int(v) for v in nvec[1:]]
    grid_logits = logits.reshape(-1, sum(split_sizes))
    split_logits = list(torch.split(grid_logits, split_sizes, dim=1))

    if action_mask is not None:
        mask_flat = action_mask.view(-1, action_mask.shape[-1])
        split_masks = list(torch.split(mask_flat[:, 1:], split_sizes, dim=1))
    else:
        split_masks = [torch.ones_like(sl, device=sl.device) for sl in split_logits]

    return split_logits, split_masks


def _select_actions(
    logits: torch.Tensor,
    nvec: Sequence[int],
    action_mask: Optional[torch.Tensor],
    deterministic: bool,
) -> torch.Tensor:
    split_logits, split_masks = _split_logits_and_masks(logits=logits, nvec=nvec, action_mask=action_mask)
    multi = [CategoricalMasked(logits=sl, masks=sm) for sl, sm in zip(split_logits, split_masks)]

    if deterministic:
        action_branches = [torch.argmax(c.logits, dim=1) for c in multi]
    else:
        action_branches = [c.sample() for c in multi]

    mapsize = int(nvec[0])
    action = torch.stack(action_branches).T.view(-1, mapsize, len(split_logits))
    return action


def _action_hist_template() -> Dict[str, int]:
    return {name: 0 for name in ACTION_TYPE_NAMES.values()}


def _shares_from_counts(counts: Dict[str, int]) -> Dict[str, Optional[float]]:
    total = int(sum(int(v) for v in counts.values()))
    if total <= 0:
        return {k: None for k in counts.keys()}
    return {k: float(v) / float(total) for k, v in counts.items()}


def _update_hist(counts: Dict[str, int], action_types: np.ndarray) -> None:
    for k, name in ACTION_TYPE_NAMES.items():
        counts[name] += int(np.count_nonzero(action_types == k))


def _run_eval_mode(
    policy: Legacy032Policy,
    env,
    nvec: Sequence[int],
    device: torch.device,
    deterministic: bool,
    episodes: int,
    seed: int,
    max_steps_per_episode: int,
) -> Dict[str, Any]:
    torch.manual_seed(int(seed))
    np.random.seed(int(seed))

    obs = _safe_reset_env(env, seed=int(seed))
    num_envs = int(obs.shape[0])
    mapsize = int(nvec[0])
    mask_dim = int(1 + sum(int(v) for v in nvec[1:]))

    ep_returns = np.zeros((num_envs,), dtype=np.float64)
    ep_lengths = np.zeros((num_envs,), dtype=np.int64)

    prev_obs = obs.copy()
    per_env_state_delta_sum = np.zeros((num_envs,), dtype=np.float64)
    per_env_state_delta_count = np.zeros((num_envs,), dtype=np.int64)
    per_env_state_changed = np.zeros((num_envs,), dtype=np.int64)

    per_env_move = np.zeros((num_envs,), dtype=np.int64)
    per_env_prod = np.zeros((num_envs,), dtype=np.int64)
    per_env_harvest = np.zeros((num_envs,), dtype=np.int64)
    per_env_return = np.zeros((num_envs,), dtype=np.int64)
    per_env_attack = np.zeros((num_envs,), dtype=np.int64)

    episodes_done = 0
    next_episode_idx = 0

    counts_all = _action_hist_template()
    counts_source_valid = _action_hist_template()

    episode_proxies: List[EpisodeProxy] = []

    while episodes_done < int(episodes):
        obs_t = torch.as_tensor(obs.astype(np.float32, copy=False), device=device)

        mask_np, mask_available, _ = _read_action_mask(
            env=env,
            num_envs=num_envs,
            mapsize=mapsize,
            mask_dim=mask_dim,
        )
        if not mask_available or mask_np is None:
            raise AuditError("Action mask is unavailable during evaluation; cannot compute source-valid-cell shares.")

        mask_t = torch.as_tensor(mask_np.astype(np.float32, copy=False), device=device)

        with torch.no_grad():
            logits = policy.infer_logits(obs_t)
            actions_t = _select_actions(
                logits=logits,
                nvec=nvec,
                action_mask=mask_t,
                deterministic=bool(deterministic),
            )

        actions_np = actions_t.detach().cpu().numpy().astype(np.int32)
        action_types = actions_np[:, :, 0]

        _update_hist(counts_all, action_types)

        source_valid = mask_np[:, :, 0] > 0
        for k, name in ACTION_TYPE_NAMES.items():
            counts_source_valid[name] += int(np.count_nonzero((action_types == k) & source_valid))

        per_env_move += np.sum(action_types == 1, axis=1)
        per_env_harvest += np.sum(action_types == 2, axis=1)
        per_env_return += np.sum(action_types == 3, axis=1)
        per_env_prod += np.sum(action_types == 4, axis=1)
        per_env_attack += np.sum(action_types == 5, axis=1)

        step_result = env.step(actions_np)
        if len(step_result) == 4:
            next_obs, rewards, dones, infos = step_result
            truncs = np.zeros_like(dones)
        elif len(step_result) == 5:
            next_obs, rewards, dones, truncs, infos = step_result
        else:
            raise AuditError(f"Unexpected env.step return arity: {len(step_result)}")

        next_obs = np.asarray(next_obs)
        rewards = np.asarray(rewards)
        dones = np.asarray(dones)
        truncs = np.asarray(truncs)

        # State-delta proxy is based on observation change from previous to next state.
        delta = np.mean(np.abs(next_obs - prev_obs), axis=(1, 2, 3))
        changed = np.any(np.not_equal(next_obs, prev_obs), axis=(1, 2, 3))
        per_env_state_delta_sum += delta
        per_env_state_delta_count += 1
        per_env_state_changed += changed.astype(np.int64)

        ep_returns += rewards
        ep_lengths += 1

        for i in range(num_envs):
            env_done = bool(dones.reshape(-1)[i])
            env_trunc = bool(truncs.reshape(-1)[i])
            reached_limit = int(ep_lengths[i]) >= int(max_steps_per_episode)
            done = env_done or env_trunc or reached_limit
            if not done:
                continue

            if env_done:
                terminal_reason = "env_done"
            elif env_trunc:
                terminal_reason = "env_truncated"
            else:
                terminal_reason = "max_steps_limit"

            state_delta_mean = (
                float(per_env_state_delta_sum[i] / max(1, per_env_state_delta_count[i]))
                if per_env_state_delta_count[i] > 0
                else None
            )
            state_changed_share = (
                float(per_env_state_changed[i] / max(1, per_env_state_delta_count[i]))
                if per_env_state_delta_count[i] > 0
                else None
            )

            episode_proxies.append(
                EpisodeProxy(
                    episode_index=int(next_episode_idx),
                    reward=float(ep_returns[i]),
                    episode_length=int(ep_lengths[i]),
                    terminal_reason=terminal_reason,
                    movement_action_count=int(per_env_move[i]),
                    production_action_count=int(per_env_prod[i]),
                    harvest_action_count=int(per_env_harvest[i]),
                    return_action_count=int(per_env_return[i]),
                    attack_action_count=int(per_env_attack[i]),
                    state_delta_mean_abs=state_delta_mean,
                    state_changed_step_share=state_changed_share,
                )
            )

            next_episode_idx += 1
            episodes_done += 1

            ep_returns[i] = 0.0
            ep_lengths[i] = 0
            per_env_state_delta_sum[i] = 0.0
            per_env_state_delta_count[i] = 0
            per_env_state_changed[i] = 0
            per_env_move[i] = 0
            per_env_prod[i] = 0
            per_env_harvest[i] = 0
            per_env_return[i] = 0
            per_env_attack[i] = 0

            if episodes_done >= int(episodes):
                break

        obs = next_obs
        prev_obs = next_obs.copy()

    ep_rewards = [float(ep.reward) for ep in episode_proxies]
    ep_lengths_list = [int(ep.episode_length) for ep in episode_proxies]

    return {
        "mode": "deterministic" if deterministic else "stochastic",
        "episodes_requested": int(episodes),
        "episodes_completed": int(len(episode_proxies)),
        "all_cell_action_counts": counts_all,
        "all_cell_action_shares": _shares_from_counts(counts_all),
        "source_valid_cell_action_counts": counts_source_valid,
        "source_valid_cell_action_shares": _shares_from_counts(counts_source_valid),
        "mean_reward": float(np.mean(ep_rewards)) if ep_rewards else None,
        "std_reward": float(np.std(np.asarray(ep_rewards, dtype=np.float64))) if ep_rewards else None,
        "mean_episode_length": float(np.mean(ep_lengths_list)) if ep_lengths_list else None,
        "episode_behavior_proxies": [ep.__dict__ for ep in episode_proxies],
    }


def _path_confirmed(checkpoint_path: Path, metadata: Dict[str, Any]) -> bool:
    if not checkpoint_path.exists():
        return False
    md_final = metadata.get("final_model_path")
    if not md_final:
        return False
    try:
        md_path = Path(str(md_final)).resolve()
        return str(md_path).lower() == str(checkpoint_path.resolve()).lower()
    except Exception:
        return False


def _inspect_resume_support(trainer_script: Path, checkpoint_dir: Path) -> Dict[str, Any]:
    text = trainer_script.read_text(encoding="utf-8", errors="ignore")

    has_local_resume_flag = bool(re.search(r"--resume", text))
    has_wandb_resume = "wandb.run.resumed" in text
    saves_optimizer_state = "optimizer.state_dict()" in text and "torch.save" in text
    saves_rng_state = any(
        x in text
        for x in ["torch.get_rng_state", "torch.cuda.get_rng_state", "np.random.get_state", "random.getstate"]
    )
    saves_global_step_in_checkpoint = bool(re.search(r"global_step.*torch\.save", text, flags=re.IGNORECASE))

    step_ckpts = sorted(checkpoint_dir.glob("agent_step_*.pt"))

    if has_local_resume_flag:
        classification = "RESUME_SUPPORTED"
    elif has_wandb_resume:
        classification = "RESUME_NOT_SUPPORTED"
    else:
        classification = "RESUME_NOT_TESTED"

    return {
        "classification": classification,
        "has_local_resume_flag": has_local_resume_flag,
        "has_wandb_resume_branch": has_wandb_resume,
        "saves_optimizer_state": saves_optimizer_state,
        "saves_rng_state": saves_rng_state,
        "saves_global_step_in_checkpoint": saves_global_step_in_checkpoint,
        "agent_step_checkpoint_count": int(len(step_ckpts)),
        "agent_step_checkpoint_examples": [p.name for p in step_ckpts[:5]],
    }


def _strict_false_occurrences(repo_root: Path) -> Dict[str, List[int]]:
    targets = [
        repo_root / "python" / "week5_teacher_legacy032" / "scripts" / "evaluate_teacher_legacy032.py",
        repo_root / "python" / "week5_teacher_legacy032" / "scripts" / "export_teacher_rollout_legacy032.py",
        repo_root / "python" / "week5_teacher_legacy032" / "scripts" / "evaluate_teacher_large_map_diagnostics.py",
        repo_root / "python" / "week5_teacher_legacy032" / "scripts" / "evaluate_teacher_large_map_win_diagnostics.py",
        repo_root / "python" / "week5_teacher_legacy032" / "scripts" / "run_legacy032_3m_visual_single_episode.py",
    ]

    out: Dict[str, List[int]] = {}
    for path in targets:
        if not path.exists():
            continue
        lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
        hits: List[int] = []
        for idx, line in enumerate(lines, start=1):
            if "strict=False" in line:
                hits.append(idx)
        if hits:
            out[str(path)] = hits
    return out


def _roundtrip_compare(
    state_dict: Dict[str, Any],
    policy_a: Legacy032Policy,
    policy_b: Legacy032Policy,
    obs_batch: np.ndarray,
    nvec: Sequence[int],
    action_mask_np: np.ndarray,
    device: torch.device,
    stochastic_seed: int,
) -> Dict[str, Any]:
    obs_t = torch.as_tensor(obs_batch.astype(np.float32, copy=False), device=device)
    mask_t = torch.as_tensor(action_mask_np.astype(np.float32, copy=False), device=device)

    with torch.no_grad():
        logits_a = policy_a.infer_logits(obs_t)
        det_a = _select_actions(logits=logits_a, nvec=nvec, action_mask=mask_t, deterministic=True)

        torch.manual_seed(int(stochastic_seed))
        stoch_a = _select_actions(logits=logits_a, nvec=nvec, action_mask=mask_t, deterministic=False)

    with tempfile.TemporaryDirectory(prefix="legacy032_roundtrip_") as td:
        tmp_dir = Path(td)
        copied_path = tmp_dir / "roundtrip_checkpoint.pt"
        torch.save(state_dict, str(copied_path))

        strict_load_ok = True
        strict_load_error = None
        try:
            policy_b.load_state_dict(torch.load(str(copied_path), map_location=device), strict=True)
        except Exception as exc:
            strict_load_ok = False
            strict_load_error = str(exc)

        with torch.no_grad():
            logits_b = policy_b.infer_logits(obs_t)
            det_b = _select_actions(logits=logits_b, nvec=nvec, action_mask=mask_t, deterministic=True)

            torch.manual_seed(int(stochastic_seed))
            stoch_b = _select_actions(logits=logits_b, nvec=nvec, action_mask=mask_t, deterministic=False)

        abs_diff = torch.abs(logits_a - logits_b)

        return {
            "copied_checkpoint_path": str(copied_path),
            "copy_load_strict_true_ok": strict_load_ok,
            "copy_load_strict_true_error": strict_load_error,
            "logits_max_abs_diff": float(abs_diff.max().item()),
            "logits_mean_abs_diff": float(abs_diff.mean().item()),
            "logits_allclose_atol_0_rtol_0": bool(torch.allclose(logits_a, logits_b, atol=0.0, rtol=0.0)),
            "logits_allclose_atol_1e-7": bool(torch.allclose(logits_a, logits_b, atol=1e-7, rtol=0.0)),
            "deterministic_actions_equal": bool(torch.equal(det_a, det_b)),
            "stochastic_actions_equal_fixed_seed": bool(torch.equal(stoch_a, stoch_b)),
            "deterministic_vs_stochastic_equal_on_model_a": bool(torch.equal(det_a, stoch_a)),
            "deterministic_vs_stochastic_equal_on_model_b": bool(torch.equal(det_b, stoch_b)),
        }


def _classify_next_action(
    save_load_ok: bool,
    path_confirmed: bool,
    det_stoch_mismatch: bool,
) -> str:
    if not save_load_ok:
        return "FIX_CHECKPOINT_SERIALIZATION_OR_POLICY_BINDING"
    if not path_confirmed:
        return "VERIFY_CHECKPOINT_PATH_AND_METADATA_BINDING"
    if det_stoch_mismatch:
        return "ALIGN_DETERMINISTIC_AND_STOCHASTIC_EVAL_PATHS_AND_COMPARE_BOTH"
    return "PROCEED_TO_MASK_AND_ACTION_SELECTION_PATH_AUDIT"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Evidence-grade Legacy032 checkpoint roundtrip audit.")
    p.add_argument(
        "--checkpoint-path",
        default=(
            "python/week5_teacher_legacy032/teacher_models/"
            "legacy032_24x24_teacher_main_20260430T130208Z/stage_003000000/agent_final.pt"
        ),
    )
    p.add_argument(
        "--model-metadata-path",
        default=(
            "python/week5_teacher_legacy032/teacher_models/"
            "legacy032_24x24_teacher_main_20260430T130208Z/stage_003000000/model_metadata.json"
        ),
    )
    p.add_argument("--episodes", type=int, default=4)
    p.add_argument("--seed", type=int, default=17)
    p.add_argument("--stochastic-seed", type=int, default=1701)
    p.add_argument("--device", choices=["cpu", "cuda"], default="cpu")
    p.add_argument("--max-steps", type=int, default=EXPECTED_MAX_STEPS)
    p.add_argument("--output-dir", default="python/week5_teacher_legacy032/reports")
    p.add_argument("--run-label", default="legacy032_checkpoint_roundtrip_audit")
    return p.parse_args()


def main() -> int:
    args = parse_args()

    repo_root = _repo_root()
    checkpoint_path = _resolve_path(args.checkpoint_path)
    metadata_path = _resolve_path(args.model_metadata_path)
    output_dir = _resolve_path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    ts = _now_compact()
    base_name = f"{args.run_label}_{ts}"
    json_path = output_dir / f"{base_name}.json"
    md_path = output_dir / f"{base_name}.md"

    report: Dict[str, Any] = {
        "timestamp": _now_iso(),
        "run_label": args.run_label,
        "checkpoint_path": str(checkpoint_path),
        "model_metadata_path": str(metadata_path),
        "expected_contract": {
            "observation_space": EXPECTED_OBS_SHAPE,
            "raw_action_nvec": EXPECTED_RAW_ACTION_NVEC,
            "architecture_name": EXPECTED_ARCHITECTURE,
            "map_path": EXPECTED_MAP_PATH,
            "max_steps": EXPECTED_MAX_STEPS,
        },
        "status": "RUNNING",
        "errors": [],
        "contract": None,
        "checkpoint_path_confirmed": False,
        "strict_load": {},
        "roundtrip": {},
        "deterministic_eval": {},
        "stochastic_eval": {},
        "strict_false_occurrences": {},
        "trainer_pipeline": {},
        "classifications": {},
    }

    try:
        if not checkpoint_path.exists():
            raise AuditError(f"Checkpoint path does not exist: {checkpoint_path}")
        if not metadata_path.exists():
            raise AuditError(f"Metadata path does not exist: {metadata_path}")

        device = torch.device("cuda" if args.device == "cuda" and torch.cuda.is_available() else "cpu")

        metadata = _load_json(metadata_path)
        contract = _assert_contract(metadata)
        report["contract"] = contract

        report["checkpoint_path_confirmed"] = _path_confirmed(checkpoint_path, metadata)

        nvec = [int(v) for v in contract["raw_action_nvec"]]
        mapsize = int(nvec[0])

        policy = Legacy032Policy(
            obs_channels=int(contract["observation_space"][2]),
            nvec=nvec,
            mapsize=mapsize,
            obs_hw=(int(contract["observation_space"][0]), int(contract["observation_space"][1])),
            architecture_name=str(contract["architecture_name"]),
        ).to(device)

        state_dict = _load_checkpoint_payload(checkpoint_path, device)

        strict_ok = True
        strict_error = None
        missing_keys: List[str] = []
        unexpected_keys: List[str] = []

        try:
            policy.load_state_dict(state_dict, strict=True)
        except Exception as exc:
            strict_ok = False
            strict_error = str(exc)

        if not strict_ok:
            report["strict_load"] = {
                "strict_true_ok": False,
                "strict_true_error": strict_error,
                "missing_keys": missing_keys,
                "unexpected_keys": unexpected_keys,
            }
            raise AuditError(f"strict=True checkpoint load failed: {strict_error}")

        report["strict_load"] = {
            "strict_true_ok": True,
            "strict_true_error": None,
            "missing_keys": missing_keys,
            "unexpected_keys": unexpected_keys,
        }

        env = None
        try:
            env = _create_target_24x24_gridmode_env(metadata=metadata, max_steps=int(args.max_steps))
            obs_batch = _safe_reset_env(env=env, seed=int(args.seed))

            env_obs_shape = [int(v) for v in env.observation_space.shape]
            env_nvec = [int(v) for v in env.action_space.nvec.tolist()]
            if env_obs_shape != EXPECTED_OBS_SHAPE:
                raise AuditError(
                    f"Runtime env observation contract mismatch. expected={EXPECTED_OBS_SHAPE}, actual={env_obs_shape}"
                )
            if env_nvec != EXPECTED_RAW_ACTION_NVEC:
                raise AuditError(
                    f"Runtime env nvec contract mismatch. expected={EXPECTED_RAW_ACTION_NVEC}, actual={env_nvec}"
                )

            mask_np, mask_available, mask_source = _read_action_mask(
                env=env,
                num_envs=int(obs_batch.shape[0]),
                mapsize=int(mapsize),
                mask_dim=int(1 + sum(int(v) for v in nvec[1:])),
            )
            if not mask_available or mask_np is None:
                raise AuditError("Action mask unavailable at fixed-batch probe; cannot perform evidence-grade comparisons.")

            fresh_policy = Legacy032Policy(
                obs_channels=int(contract["observation_space"][2]),
                nvec=nvec,
                mapsize=mapsize,
                obs_hw=(int(contract["observation_space"][0]), int(contract["observation_space"][1])),
                architecture_name=str(contract["architecture_name"]),
            ).to(device)

            roundtrip = _roundtrip_compare(
                state_dict=state_dict,
                policy_a=policy,
                policy_b=fresh_policy,
                obs_batch=obs_batch,
                nvec=nvec,
                action_mask_np=mask_np,
                device=device,
                stochastic_seed=int(args.stochastic_seed),
            )
            roundtrip["fixed_batch_shape"] = list(obs_batch.shape)
            roundtrip["fixed_mask_shape"] = list(mask_np.shape)
            roundtrip["fixed_mask_source"] = mask_source
            report["roundtrip"] = roundtrip

            det_eval = _run_eval_mode(
                policy=policy,
                env=env,
                nvec=nvec,
                device=device,
                deterministic=True,
                episodes=int(args.episodes),
                seed=int(args.seed),
                max_steps_per_episode=int(args.max_steps),
            )
            report["deterministic_eval"] = det_eval

            stoch_eval = _run_eval_mode(
                policy=policy,
                env=env,
                nvec=nvec,
                device=device,
                deterministic=False,
                episodes=int(args.episodes),
                seed=int(args.seed),
                max_steps_per_episode=int(args.max_steps),
            )
            report["stochastic_eval"] = stoch_eval

        finally:
            if env is not None:
                try:
                    env.close()
                except Exception:
                    pass

        trainer_script = repo_root / "python" / "week5_teacher_legacy032" / "scripts" / "ppo_gridnet_legacy032_24x24_local_save.py"
        report["trainer_pipeline"] = _inspect_resume_support(
            trainer_script=trainer_script,
            checkpoint_dir=checkpoint_path.parent,
        )

        report["strict_false_occurrences"] = _strict_false_occurrences(repo_root)

        save_load_ok = bool(
            report["strict_load"].get("strict_true_ok")
            and report["roundtrip"].get("copy_load_strict_true_ok")
            and bool(report["roundtrip"].get("logits_allclose_atol_0_rtol_0"))
            and bool(report["roundtrip"].get("deterministic_actions_equal"))
            and bool(report["roundtrip"].get("stochastic_actions_equal_fixed_seed"))
        )

        det_stoch_mismatch = bool(
            not bool(report["roundtrip"].get("deterministic_vs_stochastic_equal_on_model_a"))
        )

        checkpoint_path_confirmed = bool(report["checkpoint_path_confirmed"])

        resume_classification = str(report["trainer_pipeline"].get("classification", "RESUME_NOT_TESTED"))

        report["classifications"] = {
            "SAVE_LOAD": "SAVE_LOAD_OK" if save_load_ok else "SAVE_LOAD_FAIL",
            "RESUME": resume_classification,
            "DETERMINISTIC_STOCHASTIC_MISMATCH": (
                "DETERMINISTIC_STOCHASTIC_MISMATCH_YES"
                if det_stoch_mismatch
                else "DETERMINISTIC_STOCHASTIC_MISMATCH_NO"
            ),
            "CHECKPOINT_PATH": (
                "CHECKPOINT_PATH_CONFIRMED"
                if checkpoint_path_confirmed
                else "CHECKPOINT_PATH_NOT_CONFIRMED"
            ),
            "NEXT_ACTION": _classify_next_action(
                save_load_ok=save_load_ok,
                path_confirmed=checkpoint_path_confirmed,
                det_stoch_mismatch=det_stoch_mismatch,
            ),
        }

        report["status"] = "OK"

    except Exception as exc:
        report["status"] = "ERROR"
        report["errors"].append(str(exc))
        report["errors"].append(traceback.format_exc())

        resume_fallback = "RESUME_NOT_TESTED"
        report["classifications"] = {
            "SAVE_LOAD": "SAVE_LOAD_FAIL",
            "RESUME": resume_fallback,
            "DETERMINISTIC_STOCHASTIC_MISMATCH": "DETERMINISTIC_STOCHASTIC_MISMATCH_NO",
            "CHECKPOINT_PATH": (
                "CHECKPOINT_PATH_CONFIRMED" if report.get("checkpoint_path_confirmed") else "CHECKPOINT_PATH_NOT_CONFIRMED"
            ),
            "NEXT_ACTION": "FIX_BLOCKING_AUDIT_ERROR_AND_RERUN",
        }

    json_path.write_text(json.dumps(report, indent=2, ensure_ascii=True), encoding="utf-8")

    c = report.get("classifications", {})
    md_lines = [
        "# Legacy032 Checkpoint Roundtrip Audit",
        "",
        f"- timestamp_utc: {_now_iso()}",
        f"- checkpoint_path: {report.get('checkpoint_path')}",
        f"- metadata_path: {report.get('model_metadata_path')}",
        f"- status: {report.get('status')}",
        "",
        "## Contract Assertions",
        "",
        f"- expected_observation_space: {EXPECTED_OBS_SHAPE}",
        f"- expected_raw_action_nvec: {EXPECTED_RAW_ACTION_NVEC}",
        f"- expected_architecture: {EXPECTED_ARCHITECTURE}",
        f"- expected_map_path: {EXPECTED_MAP_PATH}",
        f"- expected_max_steps: {EXPECTED_MAX_STEPS}",
        f"- metadata_contract: {report.get('contract')}",
        "",
        "## Strict Load And Roundtrip",
        "",
        f"- strict_true_load_ok: {report.get('strict_load', {}).get('strict_true_ok')}",
        f"- copy_load_strict_true_ok: {report.get('roundtrip', {}).get('copy_load_strict_true_ok')}",
        f"- logits_max_abs_diff: {report.get('roundtrip', {}).get('logits_max_abs_diff')}",
        f"- logits_mean_abs_diff: {report.get('roundtrip', {}).get('logits_mean_abs_diff')}",
        f"- logits_allclose_exact: {report.get('roundtrip', {}).get('logits_allclose_atol_0_rtol_0')}",
        f"- deterministic_actions_equal: {report.get('roundtrip', {}).get('deterministic_actions_equal')}",
        (
            "- stochastic_actions_equal_fixed_seed: "
            f"{report.get('roundtrip', {}).get('stochastic_actions_equal_fixed_seed')}"
        ),
        "",
        "## Deterministic vs Stochastic Eval",
        "",
        f"- deterministic_all_cell_action_shares: {report.get('deterministic_eval', {}).get('all_cell_action_shares')}",
        (
            "- deterministic_source_valid_cell_action_shares: "
            f"{report.get('deterministic_eval', {}).get('source_valid_cell_action_shares')}"
        ),
        f"- stochastic_all_cell_action_shares: {report.get('stochastic_eval', {}).get('all_cell_action_shares')}",
        (
            "- stochastic_source_valid_cell_action_shares: "
            f"{report.get('stochastic_eval', {}).get('source_valid_cell_action_shares')}"
        ),
        "",
        "## Final Classifications",
        "",
        f"- SAVE_LOAD: {c.get('SAVE_LOAD')}",
        f"- RESUME: {c.get('RESUME')}",
        f"- DETERMINISTIC_STOCHASTIC_MISMATCH: {c.get('DETERMINISTIC_STOCHASTIC_MISMATCH')}",
        f"- CHECKPOINT_PATH: {c.get('CHECKPOINT_PATH')}",
        f"- NEXT_ACTION: {c.get('NEXT_ACTION')}",
    ]

    if report.get("errors"):
        md_lines.extend(["", "## Errors", ""])
        for err in report["errors"]:
            md_lines.append(f"- {err}")

    md_path.write_text("\n".join(md_lines), encoding="utf-8")

    print(str(json_path))
    print(str(md_path))
    return 0 if report.get("status") == "OK" else 1


if __name__ == "__main__":
    raise SystemExit(main())
