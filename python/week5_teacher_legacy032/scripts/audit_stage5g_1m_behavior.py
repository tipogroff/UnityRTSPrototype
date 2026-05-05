#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import traceback
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

ACTION_TYPE_ORDER: List[Tuple[int, str]] = [
    (0, "noop"),
    (1, "move"),
    (2, "harvest"),
    (3, "return"),
    (4, "produce"),
    (5, "attack"),
]


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


class Legacy032Policy(nn.Module):
    def __init__(
        self,
        obs_channels: int,
        nvec: Sequence[int],
        mapsize: int,
        obs_hw: Tuple[int, int],
    ):
        super().__init__()
        self.mapsize = int(mapsize)
        self.nvec = [int(v) for v in nvec]
        output_channels = int(sum(self.nvec[1:]))

        self.encoder = Encoder(obs_channels)
        self.actor = ResolutionAwareDecoder(output_channels, target_hw=obs_hw)
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
class EvalSpec:
    eval_id: str
    deterministic: bool
    episodes: int
    max_steps_per_episode: int
    seed: int


def _now_compact() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _resolve_path(path_str: str) -> Path:
    p = Path(path_str)
    if p.is_absolute():
        return p
    return (_repo_root() / p).resolve()


def _parse_nvec_from_metadata(value: Any) -> List[int]:
    nums = [int(x) for x in re.findall(r"\d+", str(value))]
    if len(nums) < 2:
        raise AuditError(f"Cannot parse action nvec from metadata value: {value}")
    return nums


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

    if isinstance(payload, dict) and payload.get("checkpoint_kind") == "full_training_state":
        state_dict = payload.get("agent_state_dict")
        if not isinstance(state_dict, dict):
            raise AuditError("Full checkpoint missing agent_state_dict.")
        return state_dict

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

    map_path = str(metadata.get("map_path", "")).strip()
    if map_path != EXPECTED_MAP_PATH:
        raise AuditError(f"Metadata map_path mismatch. expected={EXPECTED_MAP_PATH}, actual={map_path}")

    return {
        "observation_space": obs_shape,
        "raw_action_nvec": nvec,
        "architecture_name": arch,
        "map_path": map_path,
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


def _hist_template() -> Dict[str, int]:
    return {name: 0 for _, name in ACTION_TYPE_ORDER}


def _shares(counts: Dict[str, int]) -> Dict[str, Optional[float]]:
    total = int(sum(int(v) for v in counts.values()))
    if total <= 0:
        return {k: None for k in counts.keys()}
    return {k: float(v) / float(total) for k, v in counts.items()}


def _effective_activity_share(noop_share: Optional[float]) -> Optional[float]:
    if noop_share is None:
        return None
    return float(1.0 - float(noop_share))


def _safe_std(values: List[float]) -> Optional[float]:
    if not values:
        return None
    arr = np.asarray(values, dtype=np.float64)
    return float(arr.std())


def _safe_mean(values: List[float]) -> Optional[float]:
    if not values:
        return None
    arr = np.asarray(values, dtype=np.float64)
    return float(arr.mean())


def _derive_outcome_counts(returns: List[float]) -> Tuple[int, int, int, Optional[float]]:
    if not returns:
        return 0, 0, 0, None
    win = int(sum(1 for r in returns if float(r) > 0.0))
    loss = int(sum(1 for r in returns if float(r) < 0.0))
    draw = int(sum(1 for r in returns if float(r) == 0.0))
    total = win + loss + draw
    if total <= 0:
        return win, loss, draw, None
    return win, loss, draw, float(win) / float(total)


def _extract_env_max_steps(env: Any) -> Optional[int]:
    candidates = ["max_steps", "maxSteps", "_max_steps", "horizon"]
    for name in candidates:
        if hasattr(env, name):
            try:
                v = getattr(env, name)
                return int(v)
            except Exception:
                pass
    if hasattr(env, "vec_client"):
        vc = getattr(env, "vec_client")
        for name in candidates:
            if hasattr(vc, name):
                try:
                    v = getattr(vc, name)
                    return int(v)
                except Exception:
                    pass
    return None


def _run_eval_mode(
    policy: Legacy032Policy,
    env: Any,
    nvec: Sequence[int],
    device: torch.device,
    spec: EvalSpec,
    strict_load_status: str,
    checkpoint_load_ok: bool,
    policy_architecture_load_ok: bool,
    inference_ok_precheck: bool,
    env_matches_training_metadata: bool,
) -> Dict[str, Any]:
    torch.manual_seed(int(spec.seed))
    np.random.seed(int(spec.seed))

    obs = _safe_reset_env(env=env, seed=int(spec.seed))

    env_obs_shape = [int(v) for v in env.observation_space.shape]
    env_nvec = [int(v) for v in env.action_space.nvec.tolist()]
    env_matches_target_24x24 = bool(env_obs_shape == EXPECTED_OBS_SHAPE and env_nvec == EXPECTED_RAW_ACTION_NVEC)

    if not env_matches_target_24x24:
        raise AuditError(
            "Runtime env contract mismatch. "
            f"obs={env_obs_shape} nvec={env_nvec} expected_obs={EXPECTED_OBS_SHAPE} expected_nvec={EXPECTED_RAW_ACTION_NVEC}"
        )

    num_envs = int(obs.shape[0])
    mapsize = int(nvec[0])
    mask_dim = int(1 + sum(int(v) for v in nvec[1:]))

    ep_returns = np.zeros((num_envs,), dtype=np.float64)
    ep_lengths = np.zeros((num_envs,), dtype=np.int64)

    episodes_done = 0
    total_steps = 0
    mask_seen_any_step = False

    episode_returns: List[float] = []
    episode_lengths: List[int] = []
    episode_end_reason_counts = {
        "env_done": 0,
        "env_truncated": 0,
        "outer_loop_limit": 0,
        "unknown": 0,
    }

    all_counts = _hist_template()
    source_counts = _hist_template()

    total_cells_observed = 0
    source_valid_cell_count = 0

    mask_source = "unavailable"

    while episodes_done < int(spec.episodes):
        obs_t = torch.as_tensor(obs.astype(np.float32, copy=False), device=device)

        mask_np, mask_available, mask_source = _read_action_mask(
            env=env,
            num_envs=num_envs,
            mapsize=mapsize,
            mask_dim=mask_dim,
        )
        if not mask_available or mask_np is None:
            raise AuditError("Action mask unavailable during eval.")

        mask_seen_any_step = True
        mask_t = torch.as_tensor(mask_np.astype(np.float32, copy=False), device=device)

        with torch.no_grad():
            logits = policy.infer_logits(obs_t)
            actions_t = _select_actions(
                logits=logits,
                nvec=nvec,
                action_mask=mask_t,
                deterministic=bool(spec.deterministic),
            )

        actions_np = actions_t.detach().cpu().numpy().astype(np.int32)
        action_types = actions_np[:, :, 0]

        for k, name in ACTION_TYPE_ORDER:
            all_counts[name] += int(np.count_nonzero(action_types == k))

        # Conservative proxy: source-valid cell is inferred from mask[:, :, 0] > 0.
        source_valid = mask_np[:, :, 0] > 0
        for k, name in ACTION_TYPE_ORDER:
            source_counts[name] += int(np.count_nonzero((action_types == k) & source_valid))

        total_cells_observed += int(action_types.size)
        source_valid_cell_count += int(np.count_nonzero(source_valid))

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

        total_steps += int(action_types.shape[0])
        ep_returns += rewards
        ep_lengths += 1

        for i in range(num_envs):
            env_done = bool(dones.reshape(-1)[i])
            env_trunc = bool(truncs.reshape(-1)[i])
            outer_limit = int(ep_lengths[i]) >= int(spec.max_steps_per_episode)
            done = env_done or env_trunc or outer_limit
            if not done:
                continue

            if env_done:
                episode_end_reason_counts["env_done"] += 1
            elif env_trunc:
                episode_end_reason_counts["env_truncated"] += 1
            elif outer_limit:
                episode_end_reason_counts["outer_loop_limit"] += 1
            else:
                episode_end_reason_counts["unknown"] += 1

            episode_returns.append(float(ep_returns[i]))
            episode_lengths.append(int(ep_lengths[i]))
            episodes_done += 1

            ep_returns[i] = 0.0
            ep_lengths[i] = 0

            if episodes_done >= int(spec.episodes):
                break

        obs = next_obs

    all_shares = _shares(all_counts)
    source_shares = _shares(source_counts)

    win_count, loss_count, draw_count, win_rate = _derive_outcome_counts(episode_returns)

    observed_max_episode_length = max(episode_lengths) if episode_lengths else None
    all_ended_env_done = (
        bool(episode_lengths)
        and int(episode_end_reason_counts["env_done"]) == int(len(episode_lengths))
    )

    return {
        "eval_id": spec.eval_id,
        "deterministic": bool(spec.deterministic),
        "seed": int(spec.seed),
        "seeds": [int(spec.seed)],
        "episodes_requested": int(spec.episodes),
        "episodes_completed": int(len(episode_returns)),
        "max_steps_per_episode_requested": int(spec.max_steps_per_episode),
        "env_max_steps": _extract_env_max_steps(env),
        "observed_episode_lengths": [int(x) for x in episode_lengths],
        "observed_max_episode_length": int(observed_max_episode_length) if observed_max_episode_length is not None else None,
        "episode_end_reason_counts": episode_end_reason_counts,
        "episode_returns": [float(x) for x in episode_returns],
        "mean_return": _safe_mean(episode_returns),
        "std_return": _safe_std(episode_returns),
        "win_count": int(win_count),
        "loss_count": int(loss_count),
        "draw_count": int(draw_count),
        "win_rate": win_rate,
        "total_steps": int(total_steps),
        "mask_seen_any_step": bool(mask_seen_any_step),
        "mask_source": mask_source,
        "mask_used_during_eval": bool(mask_seen_any_step),
        "checkpoint_load_ok": bool(checkpoint_load_ok),
        "strict_load_status": strict_load_status,
        "policy_architecture_load_ok": bool(policy_architecture_load_ok),
        "inference_ok": bool(inference_ok_precheck),
        "env_matches_target_24x24": bool(env_matches_target_24x24),
        "env_matches_training_metadata": bool(env_matches_training_metadata),
        "all_episodes_ended_with_env_done_before_outer_limit": bool(all_ended_env_done),
        "all_cell_action_distribution": {
            "action_type_counts": all_counts,
            "noop_share": all_shares.get("noop"),
            "move_share": all_shares.get("move"),
            "harvest_share": all_shares.get("harvest"),
            "return_share": all_shares.get("return"),
            "produce_share": all_shares.get("produce"),
            "attack_share": all_shares.get("attack"),
            "effective_activity_share": _effective_activity_share(all_shares.get("noop")),
        },
        "source_valid_cell_distribution": {
            "source_valid_proxy_logic": "mask[:,:,0] > 0 (conservative proxy, semantics may be runtime-dependent)",
            "source_valid_cell_count": int(source_valid_cell_count),
            "source_valid_cell_share": (
                float(source_valid_cell_count) / float(total_cells_observed)
                if total_cells_observed > 0
                else None
            ),
            "source_valid_action_type_counts": source_counts,
            "source_valid_noop_share": source_shares.get("noop"),
            "source_valid_move_share": source_shares.get("move"),
            "source_valid_harvest_share": source_shares.get("harvest"),
            "source_valid_return_share": source_shares.get("return"),
            "source_valid_produce_share": source_shares.get("produce"),
            "source_valid_attack_share": source_shares.get("attack"),
            "source_valid_effective_activity_share": _effective_activity_share(source_shares.get("noop")),
        },
    }


def _horizon_cap_diagnostics(results: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    det_6k = results.get("A_deterministic_6000")
    stoch_6k = results.get("B_stochastic_6000")
    det_12k = results.get("C_deterministic_12000")
    stoch_12k = results.get("D_stochastic_12000")

    max_6k_candidates = [
        x.get("observed_max_episode_length")
        for x in [det_6k, stoch_6k]
        if isinstance(x, dict) and x.get("observed_max_episode_length") is not None
    ]
    max_12k_candidates = [
        x.get("observed_max_episode_length")
        for x in [det_12k, stoch_12k]
        if isinstance(x, dict) and x.get("observed_max_episode_length") is not None
    ]

    max_6k = max(max_6k_candidates) if max_6k_candidates else None
    max_12k = max(max_12k_candidates) if max_12k_candidates else None

    increased = False
    if max_6k is not None and max_12k is not None:
        increased = bool(int(max_12k) > int(max_6k))

    all_6k_env_done = all(
        bool(r.get("all_episodes_ended_with_env_done_before_outer_limit", False))
        for r in [det_6k, stoch_6k]
        if isinstance(r, dict)
    )
    all_12k_env_done = all(
        bool(r.get("all_episodes_ended_with_env_done_before_outer_limit", False))
        for r in [det_12k, stoch_12k]
        if isinstance(r, dict)
    )

    likely_internal_cap = bool((not increased) and all_6k_env_done and all_12k_env_done)

    if likely_internal_cap:
        evidence = (
            "Observed max episode length did not increase when requested horizon changed 6000->12000, "
            "and episodes ended via env_done before outer loop limit in all core modes."
        )
    elif increased:
        evidence = (
            "Observed max episode length increased under 12000 request, suggesting horizon influenced episode completion."
        )
    else:
        evidence = (
            "No strong internal-cap signal from core modes; verify per-mode lengths and end reasons."
        )

    return {
        "requested_horizons": [6000, 12000],
        "observed_max_episode_length_at_6000_modes": max_6k,
        "observed_max_episode_length_at_12000_modes": max_12k,
        "observed_max_episode_length_increased_with_12000": bool(increased),
        "all_episodes_env_done_before_outer_limit_at_6000": bool(all_6k_env_done),
        "all_episodes_env_done_before_outer_limit_at_12000": bool(all_12k_env_done),
        "likely_internal_cap_detected": bool(likely_internal_cap),
        "internal_cap_evidence": evidence,
    }


def _source_valid_is_near_uniform(stoch_core: Dict[str, Any], tolerance: float = 0.03) -> Optional[bool]:
    sv = (stoch_core.get("source_valid_cell_distribution") or {})
    keys = [
        "source_valid_noop_share",
        "source_valid_move_share",
        "source_valid_harvest_share",
        "source_valid_return_share",
        "source_valid_produce_share",
        "source_valid_attack_share",
    ]
    vals: List[float] = []
    for k in keys:
        v = sv.get(k)
        if v is None:
            return None
        vals.append(float(v))
    target = 1.0 / 6.0
    return bool(all(abs(v - target) <= tolerance for v in vals))


def _compute_behavior_decision(results: Dict[str, Dict[str, Any]], horizon_diag: Dict[str, Any]) -> Tuple[str, str, List[str]]:
    det_core = results.get("A_deterministic_6000") or {}
    stoch_core = results.get("B_stochastic_6000") or {}

    det_win = det_core.get("win_rate")
    stoch_win = stoch_core.get("win_rate")
    if det_win is None:
        det_win = 0.0
    if stoch_win is None:
        stoch_win = 0.0

    det_noop = ((det_core.get("all_cell_action_distribution") or {}).get("noop_share"))
    stoch_uniform = _source_valid_is_near_uniform(stoch_core)
    stoch_source_effective = ((stoch_core.get("source_valid_cell_distribution") or {}).get("source_valid_effective_activity_share"))

    reasons: List[str] = []

    if float(det_win) >= 0.10 or float(stoch_win) >= 0.10:
        reasons.append("At least one core mode achieved win_rate >= 0.10.")
        return "PROCEED_CANDIDATE_TO_CONTINUED_TRAINING", "STAGE5G_BEHAVIOR_AUDIT_PASS_READY_TO_CONTINUE", reasons

    no_win_both = float(det_win) == 0.0 and float(stoch_win) == 0.0
    horizon_increased = bool(horizon_diag.get("observed_max_episode_length_increased_with_12000", False))

    if no_win_both and (not horizon_increased):
        reasons.append("Both deterministic and stochastic win_rate are 0.0.")
        reasons.append("Observed episode horizon did not increase under 12000 request.")
        if det_noop is not None and float(det_noop) > 0.95 and stoch_uniform is True:
            reasons.append("Deterministic is near-NoOp and stochastic source-valid distribution is near-uniform.")
            return "POLICY_NOT_READY", "STAGE5G_POLICY_NOT_READY", reasons
        return "ZERO_WIN_WITH_EARLY_ENV_DONE", "STAGE5G_ZERO_WIN_EARLY_ENV_DONE", reasons

    if no_win_both and horizon_increased:
        reasons.append("Both deterministic and stochastic win_rate are 0.0.")
        reasons.append("Observed episode horizon increased under 12000 request.")
        return "ZERO_WIN_BUT_HORIZON_WAS_BINDING", "STAGE5G_ZERO_WIN_BUT_HORIZON_BINDING", reasons

    if det_noop is not None and float(det_noop) > 0.95:
        if stoch_uniform is False and stoch_source_effective is not None and float(stoch_source_effective) > 0.15:
            reasons.append("Deterministic remains near-NoOp while stochastic source-valid behavior is active/non-uniform.")
            return "STOCHASTIC_ONLY_CANDIDATE", "STAGE5G_POLICY_NOT_READY", reasons
        if stoch_uniform is True:
            reasons.append("Deterministic near-NoOp and stochastic source-valid distribution near-uniform.")
            return "POLICY_NOT_READY", "STAGE5G_POLICY_NOT_READY", reasons

    reasons.append("Did not meet ready-to-continue criteria.")
    return "POLICY_NOT_READY", "STAGE5G_POLICY_NOT_READY", reasons


def _build_eval_specs(seed: int, include_optional_20k: bool) -> List[EvalSpec]:
    specs = [
        EvalSpec("A_deterministic_6000", True, 16, 6000, seed),
        EvalSpec("B_stochastic_6000", False, 16, 6000, seed),
        EvalSpec("C_deterministic_12000", True, 16, 12000, seed),
        EvalSpec("D_stochastic_12000", False, 16, 12000, seed),
    ]
    if include_optional_20k:
        specs.extend(
            [
                EvalSpec("E_deterministic_20000", True, 8, 20000, seed),
                EvalSpec("F_stochastic_20000", False, 8, 20000, seed),
            ]
        )
    return specs


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Stage5G 1M behavior / win-rate / horizon audit for Legacy032 teacher.")
    p.add_argument(
        "--checkpoint-path",
        default=(
            "python/week5_teacher_legacy032/teacher_models/"
            "legacy032_24x24_teacher_resume_1m_20260504T231107Z/stage_001000000/agent_final.pt"
        ),
    )
    p.add_argument(
        "--model-metadata-path",
        default=(
            "python/week5_teacher_legacy032/teacher_models/"
            "legacy032_24x24_teacher_resume_1m_20260504T231107Z/stage_001000000/model_metadata.json"
        ),
    )
    p.add_argument("--device", choices=["cpu", "cuda"], default="cpu")
    p.add_argument("--seed", type=int, default=17)
    p.add_argument("--strict-load", action="store_true", default=True)
    p.add_argument("--no-strict-load", dest="strict_load", action="store_false")
    p.add_argument("--include-optional-20k", action="store_true", default=False)
    p.add_argument("--output-dir", default="python/week5_teacher_legacy032/reports")
    p.add_argument("--run-label", default="stage5g_1m_behavior_audit")
    return p.parse_args()


def main() -> int:
    args = parse_args()

    checkpoint_path = _resolve_path(args.checkpoint_path)
    metadata_path = _resolve_path(args.model_metadata_path)
    output_dir = _resolve_path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    ts = _now_compact()
    run_id = f"{args.run_label}_{ts}"
    json_path = output_dir / f"{run_id}.json"
    md_path = output_dir / f"{run_id}.md"
    consolidated_md = output_dir / "STAGE5G_1M_BEHAVIOR_AUDIT_REPORT.md"

    report: Dict[str, Any] = {
        "timestamp": _now_iso(),
        "run_id": run_id,
        "checkpoint_path": str(checkpoint_path),
        "model_metadata_path": str(metadata_path),
        "expected_contract": {
            "observation_space": EXPECTED_OBS_SHAPE,
            "raw_action_nvec": EXPECTED_RAW_ACTION_NVEC,
            "map_path": EXPECTED_MAP_PATH,
        },
        "strict_load": bool(args.strict_load),
        "strict_load_status": "STRICT_LOAD_ENFORCED" if args.strict_load else "STRICT_LOAD_OPT_OUT",
        "checkpoint_load_ok": False,
        "policy_architecture_load_ok": False,
        "inference_ok": False,
        "mask_used_during_eval": False,
        "env_matches_target_24x24": False,
        "env_matches_training_metadata": False,
        "audit_matrix": {},
        "horizon_diagnostics": {},
        "behavior_decision": None,
        "classification": None,
        "decision_reasons": [],
        "warnings": [],
        "errors": [],
    }

    try:
        if not checkpoint_path.exists():
            raise AuditError(f"Checkpoint path does not exist: {checkpoint_path}")
        if not metadata_path.exists():
            raise AuditError(f"Model metadata path does not exist: {metadata_path}")

        device = torch.device("cuda" if args.device == "cuda" and torch.cuda.is_available() else "cpu")
        metadata = _load_json(metadata_path)
        contract = _assert_contract(metadata)

        md_obs = [int(v) for v in metadata.get("observation_space", [])]
        md_nvec = [int(v) for v in metadata.get("action_space_nvec", [])]
        report["env_matches_training_metadata"] = bool(md_obs == EXPECTED_OBS_SHAPE and md_nvec == EXPECTED_RAW_ACTION_NVEC)

        nvec = [int(v) for v in contract["raw_action_nvec"]]
        mapsize = int(nvec[0])
        policy = Legacy032Policy(
            obs_channels=int(contract["observation_space"][2]),
            nvec=nvec,
            mapsize=mapsize,
            obs_hw=(int(contract["observation_space"][0]), int(contract["observation_space"][1])),
        ).to(device)

        state_dict = _load_checkpoint_payload(checkpoint_path, device)
        report["checkpoint_load_ok"] = True

        if args.strict_load:
            policy.load_state_dict(state_dict, strict=True)
        else:
            policy.load_state_dict(state_dict, strict=False)
            report["warnings"].append("strict_load disabled by --no-strict-load")

        report["policy_architecture_load_ok"] = True
        report["inference_ok"] = True

        specs = _build_eval_specs(seed=int(args.seed), include_optional_20k=bool(args.include_optional_20k))
        env_cache: Dict[int, Any] = {}
        try:
            for spec in specs:
                horizon = int(spec.max_steps_per_episode)
                if horizon not in env_cache:
                    env_cache[horizon] = _create_target_24x24_gridmode_env(metadata=metadata, max_steps=horizon)

                report["audit_matrix"][spec.eval_id] = _run_eval_mode(
                    policy=policy,
                    env=env_cache[horizon],
                    nvec=nvec,
                    device=device,
                    spec=spec,
                    strict_load_status=report["strict_load_status"],
                    checkpoint_load_ok=bool(report["checkpoint_load_ok"]),
                    policy_architecture_load_ok=bool(report["policy_architecture_load_ok"]),
                    inference_ok_precheck=bool(report["inference_ok"]),
                    env_matches_training_metadata=bool(report["env_matches_training_metadata"]),
                )
        finally:
            for e in env_cache.values():
                try:
                    e.close()
                except Exception:
                    pass

        core_modes = [
            report["audit_matrix"].get("A_deterministic_6000", {}),
            report["audit_matrix"].get("B_stochastic_6000", {}),
            report["audit_matrix"].get("C_deterministic_12000", {}),
            report["audit_matrix"].get("D_stochastic_12000", {}),
        ]
        report["mask_used_during_eval"] = bool(all(bool(m.get("mask_used_during_eval", False)) for m in core_modes))
        report["env_matches_target_24x24"] = bool(all(bool(m.get("env_matches_target_24x24", False)) for m in core_modes))

        report["horizon_diagnostics"] = _horizon_cap_diagnostics(report["audit_matrix"])
        behavior_decision, classification, reasons = _compute_behavior_decision(
            results=report["audit_matrix"],
            horizon_diag=report["horizon_diagnostics"],
        )
        report["behavior_decision"] = behavior_decision
        report["classification"] = classification
        report["decision_reasons"] = reasons

    except Exception as exc:
        report["errors"].append(str(exc))
        report["classification"] = "STAGE5G_AUDIT_FAILED"
        report["behavior_decision"] = "AUDIT_FAILED"

    json_path.write_text(json.dumps(report, indent=2, ensure_ascii=True), encoding="utf-8")

    md_lines: List[str] = [
        "# Stage5G 1M Behavior Audit",
        "",
        f"- run_id: {report.get('run_id')}",
        f"- timestamp: {report.get('timestamp')}",
        f"- checkpoint_path: {report.get('checkpoint_path')}",
        f"- model_metadata_path: {report.get('model_metadata_path')}",
        f"- strict_load_status: {report.get('strict_load_status')}",
        f"- checkpoint_load_ok: {report.get('checkpoint_load_ok')}",
        f"- policy_architecture_load_ok: {report.get('policy_architecture_load_ok')}",
        f"- inference_ok: {report.get('inference_ok')}",
        f"- mask_used_during_eval: {report.get('mask_used_during_eval')}",
        f"- env_matches_target_24x24: {report.get('env_matches_target_24x24')}",
        f"- env_matches_training_metadata: {report.get('env_matches_training_metadata')}",
        "",
        "## Core Decision",
        "",
        f"- classification: {report.get('classification')}",
        f"- behavior_decision: {report.get('behavior_decision')}",
        "",
        "## Horizon Diagnostics",
        "",
        f"- observed_max_episode_length_at_6000_modes: {((report.get('horizon_diagnostics') or {}).get('observed_max_episode_length_at_6000_modes'))}",
        f"- observed_max_episode_length_at_12000_modes: {((report.get('horizon_diagnostics') or {}).get('observed_max_episode_length_at_12000_modes'))}",
        f"- observed_max_episode_length_increased_with_12000: {((report.get('horizon_diagnostics') or {}).get('observed_max_episode_length_increased_with_12000'))}",
        f"- likely_internal_cap_detected: {((report.get('horizon_diagnostics') or {}).get('likely_internal_cap_detected'))}",
        f"- internal_cap_evidence: {((report.get('horizon_diagnostics') or {}).get('internal_cap_evidence'))}",
        "",
        "## Audit Matrix Summary",
        "",
    ]

    for eval_id, item in (report.get("audit_matrix") or {}).items():
        all_cell = item.get("all_cell_action_distribution") or {}
        src = item.get("source_valid_cell_distribution") or {}
        md_lines.extend(
            [
                f"### {eval_id}",
                "",
                f"- deterministic: {item.get('deterministic')}",
                f"- episodes_requested: {item.get('episodes_requested')}",
                f"- episodes_completed: {item.get('episodes_completed')}",
                f"- max_steps_per_episode_requested: {item.get('max_steps_per_episode_requested')}",
                f"- env_max_steps: {item.get('env_max_steps')}",
                f"- observed_max_episode_length: {item.get('observed_max_episode_length')}",
                f"- episode_end_reason_counts: {item.get('episode_end_reason_counts')}",
                f"- mean_return: {item.get('mean_return')}",
                f"- std_return: {item.get('std_return')}",
                f"- win_rate: {item.get('win_rate')}",
                f"- all_cell.noop_share: {all_cell.get('noop_share')}",
                f"- all_cell.move_share: {all_cell.get('move_share')}",
                f"- all_cell.effective_activity_share: {all_cell.get('effective_activity_share')}",
                f"- source_valid.source_valid_cell_share: {src.get('source_valid_cell_share')}",
                f"- source_valid.source_valid_noop_share: {src.get('source_valid_noop_share')}",
                f"- source_valid.source_valid_move_share: {src.get('source_valid_move_share')}",
                f"- source_valid.source_valid_effective_activity_share: {src.get('source_valid_effective_activity_share')}",
                "",
            ]
        )

    md_lines.extend(["## Decision Reasons", ""])
    if report.get("decision_reasons"):
        md_lines.extend([f"- {x}" for x in report.get("decision_reasons", [])])
    else:
        md_lines.append("- none")

    md_lines.extend(["", "## Errors", ""])
    if report.get("errors"):
        md_lines.extend([f"- {x}" for x in report.get("errors", [])])
    else:
        md_lines.append("- none")

    md_lines.extend(["", "## Warnings", ""])
    if report.get("warnings"):
        md_lines.extend([f"- {x}" for x in report.get("warnings", [])])
    else:
        md_lines.append("- none")

    md_lines.extend([
        "",
        f"- json_report: {json_path}",
        f"- markdown_report: {md_path}",
    ])

    md_text = "\n".join(md_lines)
    md_path.write_text(md_text, encoding="utf-8")
    consolidated_md.write_text(md_text, encoding="utf-8")

    print(
        json.dumps(
            {
                "classification": report.get("classification"),
                "behavior_decision": report.get("behavior_decision"),
                "json_report": str(json_path),
                "markdown_report": str(md_path),
                "consolidated_report": str(consolidated_md),
                "errors": report.get("errors"),
            },
            indent=2,
        )
    )

    if report.get("classification") == "STAGE5G_AUDIT_FAILED":
        return 1
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception:
        traceback.print_exc()
        raise SystemExit(1)
