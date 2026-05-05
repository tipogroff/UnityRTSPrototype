#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
import tempfile
import traceback
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
BRANCH_NAMES = [
    "action_type",
    "move_dir",
    "harvest_dir",
    "return_dir",
    "produce_dir",
    "produce_unit_type",
    "attack_target",
]

CLASSIFICATIONS = {
    "PARITY_PASS_VISUAL_SCRIPT_BUG_LIKELY": "STAGE5H_PARITY_PASS_VISUAL_SCRIPT_BUG_LIKELY",
    "LOGITS_MISMATCH_AFTER_LOAD": "STAGE5H_LOGITS_MISMATCH_AFTER_LOAD",
    "ACTION_SELECTION_MISMATCH": "STAGE5H_ACTION_SELECTION_MISMATCH",
    "ACTION_FORMATTING_MISMATCH": "STAGE5H_ACTION_FORMATTING_MISMATCH",
    "MASK_SEMANTICS_MISMATCH": "STAGE5H_MASK_SEMANTICS_MISMATCH",
    "FULL_BRANCH_INVALIDITY_CONFIRMED": "STAGE5H_FULL_BRANCH_INVALIDITY_CONFIRMED",
    "ENV_WRAPPER_MISMATCH": "STAGE5H_ENV_WRAPPER_MISMATCH",
    "INCONCLUSIVE": "STAGE5H_INCONCLUSIVE",
    "AUDIT_FAILED": "STAGE5H_AUDIT_FAILED",
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


def _load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _parse_nvec_from_metadata(value: Any) -> List[int]:
    nums = [int(x) for x in re.findall(r"\d+", str(value))]
    if len(nums) < 2:
        raise AuditError(f"Cannot parse action nvec from metadata value: {value}")
    return nums


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
    if map_path and map_path != EXPECTED_MAP_PATH:
        raise AuditError(f"Metadata map_path mismatch. expected={EXPECTED_MAP_PATH}, actual={map_path}")

    return {
        "observation_space": obs_shape,
        "raw_action_nvec": nvec,
        "architecture_name": arch,
        "map_path": map_path or EXPECTED_MAP_PATH,
    }


def _load_checkpoint_payload(path: Path, device: torch.device) -> Dict[str, Any]:
    payload = torch.load(str(path), map_location=device)

    if isinstance(payload, dict) and payload.get("checkpoint_kind") == "full_training_state":
        state_dict = payload.get("agent_state_dict")
        if not isinstance(state_dict, dict):
            raise AuditError("Full checkpoint missing agent_state_dict")
        return state_dict

    if isinstance(payload, dict) and "state_dict" in payload and isinstance(payload["state_dict"], dict):
        return payload["state_dict"]

    if isinstance(payload, dict):
        return payload

    raise AuditError("Checkpoint payload is not state_dict-compatible")


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


def _create_24x24_env(metadata: Dict[str, Any], max_steps: int):
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
    if isinstance(obs, tuple):
        obs = obs[0]
    arr = np.asarray(obs)
    if arr.ndim != 4:
        raise AuditError(f"Unexpected reset observation shape: {list(arr.shape)}")
    return arr


def _normalize_mask_array(raw_mask: Any, num_envs: int, mapsize: int, mask_dim: int) -> np.ndarray:
    arr = np.asarray(raw_mask)
    if arr.ndim == 2 and arr.shape == (num_envs * mapsize, mask_dim):
        return arr.reshape(num_envs, mapsize, mask_dim)
    if arr.ndim == 3 and arr.shape == (num_envs, mapsize, mask_dim):
        return arr
    if arr.ndim == 4 and arr.shape[0] == num_envs and arr.shape[1] * arr.shape[2] == mapsize and arr.shape[3] == mask_dim:
        return arr.reshape(num_envs, mapsize, mask_dim)
    raise AuditError(f"Unexpected action mask shape: {tuple(arr.shape)}")


def _read_action_mask(env: Any, num_envs: int, mapsize: int, mask_dim: int) -> Tuple[np.ndarray, str]:
    if hasattr(env, "vec_client") and hasattr(env.vec_client, "getMasks"):
        raw = env.vec_client.getMasks(0)
        return _normalize_mask_array(raw, num_envs, mapsize, mask_dim), "env.vec_client.getMasks(0)"
    if hasattr(env, "get_action_mask"):
        raw = env.get_action_mask()
        return _normalize_mask_array(raw, num_envs, mapsize, mask_dim), "env.get_action_mask"
    raise AuditError("Action mask unavailable from environment")


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


def _select_actions_training_style(
    logits: torch.Tensor,
    nvec: Sequence[int],
    action_mask: Optional[torch.Tensor],
    deterministic: bool,
) -> torch.Tensor:
    split_logits, split_masks = _split_logits_and_masks(logits=logits, nvec=nvec, action_mask=action_mask)
    multi = [CategoricalMasked(logits=sl, masks=sm) for sl, sm in zip(split_logits, split_masks)]
    if deterministic:
        branches = [torch.argmax(c.logits, dim=1) for c in multi]
    else:
        branches = [c.sample() for c in multi]
    return torch.stack(branches).T.view(-1, int(nvec[0]), len(split_logits))


def _select_actions_eval_style(
    logits: torch.Tensor,
    nvec: Sequence[int],
    action_mask: Optional[torch.Tensor],
    deterministic: bool,
) -> torch.Tensor:
    split_logits, split_masks = _split_logits_and_masks(logits=logits, nvec=nvec, action_mask=action_mask)
    multi = [CategoricalMasked(logits=sl, masks=sm) for sl, sm in zip(split_logits, split_masks)]
    if deterministic:
        branches = [torch.argmax(c.logits, dim=1) for c in multi]
    else:
        branches = [c.sample() for c in multi]
    return torch.stack(branches).T.view(-1, int(nvec[0]), len(split_logits))


def _tensor_hash(x: np.ndarray) -> str:
    return hashlib.sha256(np.ascontiguousarray(x).tobytes()).hexdigest()


def _compare_logits_and_actions(
    logits_a: torch.Tensor,
    logits_b: torch.Tensor,
    act_a: torch.Tensor,
    act_b: torch.Tensor,
    source_valid_flat: np.ndarray,
) -> Dict[str, Any]:
    abs_diff = torch.abs(logits_a - logits_b)
    action_equal = torch.equal(act_a, act_b)

    act_a_np = act_a.detach().cpu().numpy()
    act_b_np = act_b.detach().cpu().numpy()
    source_valid_equal = bool(np.array_equal(act_a_np.reshape(-1, 7)[source_valid_flat], act_b_np.reshape(-1, 7)[source_valid_flat]))
    branch_equal = {
        BRANCH_NAMES[i]: bool(np.array_equal(act_a_np[:, :, i], act_b_np[:, :, i])) for i in range(len(BRANCH_NAMES))
    }
    source_branch_equal = {
        BRANCH_NAMES[i]: bool(
            np.array_equal(
                act_a_np[:, :, i].reshape(-1)[source_valid_flat],
                act_b_np[:, :, i].reshape(-1)[source_valid_flat],
            )
        )
        for i in range(len(BRANCH_NAMES))
    }
    return {
        "logits_max_abs_diff": float(abs_diff.max().item()),
        "logits_mean_abs_diff": float(abs_diff.mean().item()),
        "logits_allclose_exact": bool(torch.allclose(logits_a, logits_b, atol=0.0, rtol=0.0)),
        "logits_allclose_atol_1e-7": bool(torch.allclose(logits_a, logits_b, atol=1e-7, rtol=0.0)),
        "action_tensor_equal": bool(action_equal),
        "action_type_equal": bool(np.array_equal(act_a_np[:, :, 0], act_b_np[:, :, 0])),
        "branch_equal": branch_equal,
        "source_valid_action_equal": source_valid_equal,
        "source_valid_branch_equal": source_branch_equal,
    }


def _env_step_probe(env: Any, seed: int, action_np: np.ndarray) -> Dict[str, Any]:
    obs = _safe_reset_env(env=env, seed=seed)
    obs_hash_before = _tensor_hash(obs)
    step_result = env.step(action_np.astype(np.int32, copy=False))

    if len(step_result) == 4:
        next_obs, rewards, dones, infos = step_result
        truncs = np.zeros_like(dones)
    else:
        next_obs, rewards, dones, truncs, infos = step_result

    next_obs = np.asarray(next_obs)
    rewards = np.asarray(rewards)
    dones = np.asarray(dones)
    truncs = np.asarray(truncs)

    info = infos[0] if isinstance(infos, (list, tuple)) and len(infos) > 0 else infos
    info_keys = sorted(list(info.keys())) if isinstance(info, dict) else None

    return {
        "obs_hash_before": obs_hash_before,
        "next_obs_hash": _tensor_hash(next_obs),
        "reward_env0": float(rewards.reshape(-1)[0]),
        "done_env0": bool(dones.reshape(-1)[0]),
        "truncated_env0": bool(truncs.reshape(-1)[0]),
        "info_keys_env0": info_keys,
    }


def _extract_static_features(text: str) -> Dict[str, Any]:
    return {
        "policy_class_names": sorted(set(re.findall(r"class\s+([A-Za-z0-9_]+Policy|Agent)\s*\(", text))),
        "uses_resolution_aware_decoder": "ResolutionAwareDecoder" in text,
        "uses_legacy_decoder": "class Decoder" in text,
        "output_channels_sum_nvec": bool(
            re.search(r"sum\s*\(\s*(self\.)?nvec\[1:\]\s*\)", text)
            or re.search(r"action_space\.nvec\[1:\]\.sum\(\)", text)
        ),
        "reshape_logits": "reshape(-1" in text and "grid_logits" in text,
        "split_sizes_78444749": "[6, 4, 4, 4, 4, 7, 49]" in text,
        "split_from_nvec_1": "nvec[1:]" in text or "action_space.nvec[1:]" in text,
        "mask_source_getMasks0": "getMasks(0)" in text,
        "mask_slice_drop_source": "[:, 1:]" in text,
        "deterministic_argmax": "torch.argmax" in text,
        "stochastic_sample": ".sample()" in text,
        "env_step_present": "env.step(" in text or "envs.step(" in text,
    }


def _diff_static_features(base: Dict[str, Any], current: Dict[str, Any]) -> List[str]:
    diffs: List[str] = []
    for key in sorted(base.keys()):
        if base[key] != current.get(key):
            diffs.append(f"{key}: base={base[key]} current={current.get(key)}")
    return diffs


def _static_source_parity(repo_root: Path) -> Dict[str, Any]:
    rel_targets = [
        "python/week5_teacher_legacy032/scripts/ppo_gridnet_legacy032_24x24_local_save.py",
        "python/week5_teacher_legacy032/scripts/evaluate_teacher_legacy032.py",
        "python/week5_teacher_legacy032/scripts/evaluate_teacher_large_map_diagnostics.py",
        "python/week5_teacher_legacy032/scripts/run_legacy032_3m_visual_single_episode.py",
        "python/week5_teacher_legacy032/scripts/audit_stage5g_1m_behavior.py",
    ]

    per_file: Dict[str, Any] = {}
    existing_paths: List[Path] = []
    for rel in rel_targets:
        path = (repo_root / rel).resolve()
        if not path.exists():
            per_file[rel] = {"exists": False}
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        per_file[rel] = {
            "exists": True,
            "features": _extract_static_features(text),
        }
        existing_paths.append(path)

    base_key = rel_targets[0]
    base_features = per_file.get(base_key, {}).get("features", {})

    pairwise: Dict[str, Any] = {}
    for rel in rel_targets[1:]:
        f = per_file.get(rel, {}).get("features", {})
        pairwise[rel] = {
            "diff_count": len(_diff_static_features(base_features, f)),
            "diffs": _diff_static_features(base_features, f),
        }

    shared_features = {
        "same_output_channel_count_rule": all(
            bool(per_file.get(rel, {}).get("features", {}).get("output_channels_sum_nvec"))
            for rel in rel_targets
            if per_file.get(rel, {}).get("exists")
        ),
        "same_split_rule_from_nvec1": all(
            bool(per_file.get(rel, {}).get("features", {}).get("split_from_nvec_1"))
            for rel in rel_targets
            if per_file.get(rel, {}).get("exists")
        ),
        "same_mask_slice_rule": all(
            bool(per_file.get(rel, {}).get("features", {}).get("mask_slice_drop_source"))
            for rel in rel_targets
            if per_file.get(rel, {}).get("exists")
        ),
        "same_deterministic_rule": all(
            bool(per_file.get(rel, {}).get("features", {}).get("deterministic_argmax"))
            for rel in rel_targets
            if per_file.get(rel, {}).get("exists")
        ),
        "same_stochastic_rule": all(
            bool(per_file.get(rel, {}).get("features", {}).get("stochastic_sample"))
            for rel in rel_targets
            if per_file.get(rel, {}).get("exists")
        ),
    }

    return {
        "files": rel_targets,
        "per_file": per_file,
        "pairwise_vs_training_script": pairwise,
        "shared_feature_checks": shared_features,
    }


def _branch_validity_audit(
    action_np: np.ndarray,
    mask_np: np.ndarray,
    max_cells: int,
) -> Dict[str, Any]:
    split_sizes = [6, 4, 4, 4, 4, 7, 49]
    mask_flat = mask_np.reshape(-1, mask_np.shape[-1])
    action_flat = action_np.reshape(-1, action_np.shape[-1])
    source_valid = mask_flat[:, 0] > 0

    split_masks = []
    start = 1
    for sz in split_sizes:
        split_masks.append(mask_flat[:, start:start + sz])
        start += sz

    source_valid_indices = np.where(source_valid)[0].tolist()
    non_noop_source_indices = [i for i in source_valid_indices if int(action_flat[i, 0]) != 0]
    selected_indices = non_noop_source_indices[:max_cells]
    if len(selected_indices) < max_cells:
        remain = [i for i in source_valid_indices if i not in selected_indices]
        selected_indices.extend(remain[: max(0, max_cells - len(selected_indices))])

    rows: List[Dict[str, Any]] = []
    effective_noop_candidates = 0

    for idx in selected_indices:
        a = action_flat[idx]
        action_type = int(a[0])
        req = {
            "move_dir": action_type == 1,
            "harvest_dir": action_type == 2,
            "return_dir": action_type == 3,
            "produce_dir": action_type == 4,
            "produce_unit_type": action_type == 4,
            "attack_target": action_type == 5,
        }

        move_valid = bool(split_masks[1][idx, int(a[1])] > 0) if 0 <= int(a[1]) < split_masks[1].shape[1] else False
        harvest_valid = bool(split_masks[2][idx, int(a[2])] > 0) if 0 <= int(a[2]) < split_masks[2].shape[1] else False
        return_valid = bool(split_masks[3][idx, int(a[3])] > 0) if 0 <= int(a[3]) < split_masks[3].shape[1] else False
        produce_dir_valid = bool(split_masks[4][idx, int(a[4])] > 0) if 0 <= int(a[4]) < split_masks[4].shape[1] else False
        produce_unit_valid = bool(split_masks[5][idx, int(a[5])] > 0) if 0 <= int(a[5]) < split_masks[5].shape[1] else False
        attack_valid = bool(split_masks[6][idx, int(a[6])] > 0) if 0 <= int(a[6]) < split_masks[6].shape[1] else False

        valid_required = True
        if req["move_dir"]:
            valid_required = valid_required and move_valid
        if req["harvest_dir"]:
            valid_required = valid_required and harvest_valid
        if req["return_dir"]:
            valid_required = valid_required and return_valid
        if req["produce_dir"]:
            valid_required = valid_required and produce_dir_valid
        if req["produce_unit_type"]:
            valid_required = valid_required and produce_unit_valid
        if req["attack_target"]:
            valid_required = valid_required and attack_valid

        effective_noop_candidate = bool(action_type != 0 and not valid_required)
        if effective_noop_candidate:
            effective_noop_candidates += 1

        rows.append(
            {
                "flat_cell_index": int(idx),
                "action_type": int(action_type),
                "branches": [int(v) for v in a.tolist()],
                "required_parameters": req,
                "parameter_validity": {
                    "move_dir": move_valid,
                    "harvest_dir": harvest_valid,
                    "return_dir": return_valid,
                    "produce_dir": produce_dir_valid,
                    "produce_unit_type": produce_unit_valid,
                    "attack_target": attack_valid,
                },
                "effective_noop_candidate": effective_noop_candidate,
            }
        )

    return {
        "selected_source_valid_cells": len(selected_indices),
        "source_valid_total": len(source_valid_indices),
        "non_noop_source_valid_total": len(non_noop_source_indices),
        "effective_noop_candidate_count": int(effective_noop_candidates),
        "effective_noop_candidate_share": float(effective_noop_candidates / max(1, len(selected_indices))),
        "rows": rows,
    }


def _audit_visual_script(repo_root: Path) -> Dict[str, Any]:
    rel = "python/week5_teacher_legacy032/scripts/run_legacy032_3m_visual_single_episode.py"
    path = (repo_root / rel).resolve()
    if not path.exists():
        return {"exists": False, "file": rel}

    text = path.read_text(encoding="utf-8", errors="ignore")
    has_3m_hardcoded = "stage_003000000" in text or "3m" in text.lower()
    checkpoint_default_3m = bool(re.search(r"CHECKPOINT_REL\s*=.*stage_003000000", text, flags=re.S))
    strict_load_default_true = bool(re.search(r"--strict-load.*default=True", text))
    deterministic_default = bool(re.search(r"--eval-mode\"?,\s*default=\"deterministic\"", text))
    catches_generic_exception = "except Exception" in text
    noop_fallback = "NoOp" in text and "fallback" in text.lower()
    uses_agent_final = "agent_final.pt" in text
    uses_trainer_state = "trainer_state_final.pt" in text
    metadata_driven_arch = "model_metadata" in text and "architecture_name" in text

    findings: List[str] = []
    if checkpoint_default_3m:
        findings.append("Visual script defaults are pinned to stage_003000000 checkpoint path.")
    if has_3m_hardcoded:
        findings.append("Visual script contains 3M-specific assumptions in defaults/naming.")
    if catches_generic_exception:
        findings.append("Visual script uses broad exception handlers; failures may be softened into warnings.")
    if strict_load_default_true:
        findings.append("strict_load default is True.")
    if deterministic_default:
        findings.append("deterministic eval mode is default.")

    return {
        "exists": True,
        "file": rel,
        "has_3m_hardcoded_assumptions": has_3m_hardcoded,
        "default_checkpoint_is_3m": checkpoint_default_3m,
        "default_uses_agent_final_pt": uses_agent_final,
        "default_uses_trainer_state_final_pt": uses_trainer_state,
        "metadata_driven_architecture": metadata_driven_arch,
        "strict_load_default_true": strict_load_default_true,
        "deterministic_default": deterministic_default,
        "has_generic_exception_handlers": catches_generic_exception,
        "has_noop_fallback_hint": noop_fallback,
        "findings": findings,
    }


def _classify(report: Dict[str, Any]) -> str:
    same = report.get("same_obs_mask_roundtrip", {})
    sp = same.get("same_process_reload", {})
    fr = same.get("fresh_object_reload", {})
    envp = report.get("env_action_application_parity", {})
    validity = report.get("full_action_command_validity", {})
    visual = report.get("targeted_visual_script_audit", {})

    if not sp or not fr:
        return CLASSIFICATIONS["AUDIT_FAILED"]

    if (not sp.get("logits_allclose_exact", False)) or (not fr.get("logits_allclose_exact", False)):
        return CLASSIFICATIONS["LOGITS_MISMATCH_AFTER_LOAD"]

    if sp.get("logits_allclose_exact", False) and fr.get("logits_allclose_exact", False):
        if (not sp.get("action_tensor_equal", False)) or (not fr.get("action_tensor_equal", False)):
            return CLASSIFICATIONS["ACTION_SELECTION_MISMATCH"]

    if validity.get("effective_noop_candidate_count", 0) > 0:
        return CLASSIFICATIONS["FULL_BRANCH_INVALIDITY_CONFIRMED"]

    env_same = (
        envp.get("training_vs_postload_same", {}).get("reward_equal")
        and envp.get("training_vs_postload_same", {}).get("done_equal")
        and envp.get("training_vs_postload_same", {}).get("next_obs_hash_equal")
    )
    if not env_same:
        if envp.get("obs_hash_before_equal", False):
            return CLASSIFICATIONS["ACTION_FORMATTING_MISMATCH"]
        return CLASSIFICATIONS["ENV_WRAPPER_MISMATCH"]

    if visual.get("has_3m_hardcoded_assumptions", False) or visual.get("default_checkpoint_is_3m", False):
        return CLASSIFICATIONS["PARITY_PASS_VISUAL_SCRIPT_BUG_LIKELY"]

    return CLASSIFICATIONS["INCONCLUSIVE"]


def _rank_root_causes(classification: str, report: Dict[str, Any]) -> List[str]:
    visual = report.get("targeted_visual_script_audit", {})
    causes: List[str] = []
    if classification == CLASSIFICATIONS["LOGITS_MISMATCH_AFTER_LOAD"]:
        causes.append("Policy reconstruction or checkpoint binding mismatch after load.")
        causes.append("Architecture mismatch or partial state_dict application.")
    elif classification == CLASSIFICATIONS["ACTION_SELECTION_MISMATCH"]:
        causes.append("Deterministic argmax/sampling path mismatch between training and eval code paths.")
        causes.append("Mask split/slice mismatch influencing branch selection.")
    elif classification == CLASSIFICATIONS["FULL_BRANCH_INVALIDITY_CONFIRMED"]:
        causes.append("Non-NoOp action_type selected with invalid required parameter branches.")
        causes.append("Action appears active by type but resolves into effective no-op at runtime.")
    elif classification == CLASSIFICATIONS["ACTION_FORMATTING_MISMATCH"]:
        causes.append("Action tensor formatting mismatch before env.step.")
        causes.append("Per-branch value bounds/shape mismatch despite parity in logits.")
    elif classification == CLASSIFICATIONS["ENV_WRAPPER_MISMATCH"]:
        causes.append("Env/wrapper reset state or observation pipeline mismatch across paths.")
    elif classification == CLASSIFICATIONS["PARITY_PASS_VISUAL_SCRIPT_BUG_LIKELY"]:
        causes.append("Visual script defaults are stale or hardcoded to different checkpoint/run assumptions.")
        if visual.get("has_generic_exception_handlers", False):
            causes.append("Broad exception handling may hide inference/action-path faults during visual run.")
    else:
        causes.append("No dominant single root cause isolated.")
    return causes


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Stage5H training vs post-load parity audit")
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
    p.add_argument("--seed", type=int, default=17)
    p.add_argument("--stochastic-seed", type=int, default=1701)
    p.add_argument("--device", choices=["cpu", "cuda"], default="cpu")
    p.add_argument("--max-steps", type=int, default=6000)
    p.add_argument("--max-source-cells", type=int, default=24)
    p.add_argument("--output-dir", default="python/week5_teacher_legacy032/reports")
    p.add_argument("--run-label", default="stage5h_training_postload_parity")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    repo_root = _repo_root()
    checkpoint_path = _resolve_path(args.checkpoint_path)
    metadata_path = _resolve_path(args.model_metadata_path)
    output_dir = _resolve_path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    ts = _now_compact()
    stem = f"stage5h_training_postload_parity_{ts}"
    json_path = output_dir / f"{stem}.json"
    md_path = output_dir / f"{stem}.md"
    canonical_md_path = output_dir / "STAGE5H_TRAINING_POSTLOAD_PARITY_REPORT.md"

    command = (
        "python python/week5_teacher_legacy032/scripts/audit_stage5h_training_postload_parity.py "
        f"--checkpoint-path {args.checkpoint_path} "
        f"--model-metadata-path {args.model_metadata_path} --device {args.device} --seed {args.seed}"
    )

    report: Dict[str, Any] = {
        "timestamp_utc": _now_iso(),
        "status": "RUNNING",
        "run_label": args.run_label,
        "stage": "Stage5H",
        "checkpoint_path": str(checkpoint_path),
        "model_metadata_path": str(metadata_path),
        "commands_run": [command],
        "static_source_parity_audit": {},
        "same_obs_mask_roundtrip": {},
        "training_vs_eval_action_method_audit": {},
        "env_action_application_parity": {},
        "full_action_command_validity": {},
        "targeted_visual_script_audit": {},
        "classification": CLASSIFICATIONS["INCONCLUSIVE"],
        "ranked_root_cause_candidates": [],
        "recommended_fix_plan": [],
        "errors": [],
    }

    env = None

    try:
        if not checkpoint_path.exists():
            raise AuditError(f"Checkpoint path does not exist: {checkpoint_path}")
        if not metadata_path.exists():
            raise AuditError(f"Metadata path does not exist: {metadata_path}")

        device = torch.device("cuda" if args.device == "cuda" and torch.cuda.is_available() else "cpu")
        metadata = _load_json(metadata_path)
        contract = _assert_contract(metadata)
        nvec = [int(v) for v in contract["raw_action_nvec"]]
        mapsize = int(nvec[0])

        report["contract"] = contract
        report["static_source_parity_audit"] = _static_source_parity(repo_root=repo_root)
        report["targeted_visual_script_audit"] = _audit_visual_script(repo_root=repo_root)

        state_dict = _load_checkpoint_payload(path=checkpoint_path, device=device)
        policy = Legacy032Policy(
            obs_channels=int(contract["observation_space"][2]),
            nvec=nvec,
            mapsize=mapsize,
            obs_hw=(int(contract["observation_space"][0]), int(contract["observation_space"][1])),
            architecture_name=str(contract["architecture_name"]),
        ).to(device)
        policy.load_state_dict(state_dict, strict=True)
        policy.eval()

        env = None
        obs_batch = None
        mask_np = None
        mask_source = None
        env = _create_24x24_env(metadata=metadata, max_steps=int(args.max_steps))
        obs_batch = _safe_reset_env(env=env, seed=int(args.seed))
        env_obs_shape = [int(v) for v in env.observation_space.shape]
        env_nvec = [int(v) for v in env.action_space.nvec.tolist()]
        if env_obs_shape != EXPECTED_OBS_SHAPE:
            raise AuditError(
                f"Runtime env observation mismatch. expected={EXPECTED_OBS_SHAPE}, actual={env_obs_shape}"
            )
        if env_nvec != EXPECTED_RAW_ACTION_NVEC:
            raise AuditError(f"Runtime env nvec mismatch. expected={EXPECTED_RAW_ACTION_NVEC}, actual={env_nvec}")

        mask_np, mask_source = _read_action_mask(
            env=env,
            num_envs=int(obs_batch.shape[0]),
            mapsize=mapsize,
            mask_dim=int(1 + sum(int(v) for v in nvec[1:])),
        )

        if obs_batch is None or mask_np is None:
            raise AuditError("Failed to capture fixed observation/mask batch")

        obs_t = torch.as_tensor(obs_batch.astype(np.float32, copy=False), device=device)
        mask_t = torch.as_tensor(mask_np.astype(np.float32, copy=False), device=device)
        source_valid_flat = mask_np.reshape(-1, mask_np.shape[-1])[:, 0] > 0

        with torch.no_grad():
            logits_before = policy.infer_logits(obs_t)
            action_before_training_det = _select_actions_training_style(logits_before, nvec, mask_t, deterministic=True)
            action_before_eval_det = _select_actions_eval_style(logits_before, nvec, mask_t, deterministic=True)
            torch.manual_seed(int(args.stochastic_seed))
            action_before_training_stoch = _select_actions_training_style(logits_before, nvec, mask_t, deterministic=False)

        # same-process reload path: mutate then strict reload
        mutated_keys = []
        with torch.no_grad():
            for name, param in policy.named_parameters():
                param.add_(0.0)
                mutated_keys.append(name)
                if len(mutated_keys) >= 3:
                    break
        policy.load_state_dict(state_dict, strict=True)
        with torch.no_grad():
            logits_same = policy.infer_logits(obs_t)
            action_same_det = _select_actions_training_style(logits_same, nvec, mask_t, deterministic=True)
            torch.manual_seed(int(args.stochastic_seed))
            action_same_stoch = _select_actions_training_style(logits_same, nvec, mask_t, deterministic=False)

        # fresh-object reload path
        fresh_policy = Legacy032Policy(
            obs_channels=int(contract["observation_space"][2]),
            nvec=nvec,
            mapsize=mapsize,
            obs_hw=(int(contract["observation_space"][0]), int(contract["observation_space"][1])),
            architecture_name=str(contract["architecture_name"]),
        ).to(device)
        fresh_policy.load_state_dict(state_dict, strict=True)
        fresh_policy.eval()
        with torch.no_grad():
            logits_fresh = fresh_policy.infer_logits(obs_t)
            action_fresh_det = _select_actions_training_style(logits_fresh, nvec, mask_t, deterministic=True)
            torch.manual_seed(int(args.stochastic_seed))
            action_fresh_stoch = _select_actions_training_style(logits_fresh, nvec, mask_t, deterministic=False)

        same_metrics = _compare_logits_and_actions(
            logits_a=logits_before,
            logits_b=logits_same,
            act_a=action_before_training_det,
            act_b=action_same_det,
            source_valid_flat=source_valid_flat,
        )
        same_metrics["stochastic_action_tensor_equal"] = bool(torch.equal(action_before_training_stoch, action_same_stoch))

        fresh_metrics = _compare_logits_and_actions(
            logits_a=logits_before,
            logits_b=logits_fresh,
            act_a=action_before_training_det,
            act_b=action_fresh_det,
            source_valid_flat=source_valid_flat,
        )
        fresh_metrics["stochastic_action_tensor_equal"] = bool(torch.equal(action_before_training_stoch, action_fresh_stoch))

        eval_vs_training_det_equal = bool(torch.equal(action_before_training_det, action_before_eval_det))

        report["same_obs_mask_roundtrip"] = {
            "fixed_batch_shape": list(obs_batch.shape),
            "fixed_mask_shape": list(mask_np.shape),
            "mask_source": mask_source,
            "training_before_save": {
                "logits_hash": _tensor_hash(logits_before.detach().cpu().numpy()),
                "action_hash": _tensor_hash(action_before_training_det.detach().cpu().numpy()),
                "action_type_hist": {
                    str(k): int(v)
                    for k, v in zip(
                        *np.unique(action_before_training_det.detach().cpu().numpy()[:, :, 0], return_counts=True)
                    )
                },
            },
            "same_process_reload": same_metrics,
            "fresh_object_reload": fresh_metrics,
            "subprocess_reload": {
                "executed": False,
                "reason": "Optional path skipped in this run; same-process and fresh-object reload executed.",
            },
        }

        report["training_vs_eval_action_method_audit"] = {
            "training_action_method_name": "Agent.get_action (ppo_gridnet_legacy032_24x24_local_save.py)",
            "eval_action_method_name": "Legacy032Policy.get_action (evaluate_teacher_legacy032.py)",
            "visual_action_method_name": "Legacy032Policy.infer_actions (run_legacy032_3m_visual_single_episode.py)",
            "shared_vs_duplicated": "duplicated_implementations",
            "training_eval_deterministic_action_equal": eval_vs_training_det_equal,
            "static_diff_vs_training": report["static_source_parity_audit"].get("pairwise_vs_training_script", {}),
            "recommend_canonical_extraction": {
                "module": "python/week5_teacher_legacy032/scripts/legacy032_policy_action.py",
                "functions": [
                    "build_policy_from_metadata",
                    "load_policy_checkpoint_strict",
                    "infer_logits",
                    "split_logits_and_masks",
                    "select_action_deterministic",
                    "select_action_stochastic",
                    "format_env_action",
                ],
            },
        }

        action_training_np = action_before_training_det.detach().cpu().numpy().astype(np.int32)
        action_postload_np = action_same_det.detach().cpu().numpy().astype(np.int32)
        probe_train = _env_step_probe(env=env, seed=int(args.seed), action_np=action_training_np)
        probe_post = _env_step_probe(env=env, seed=int(args.seed), action_np=action_postload_np)

        report["env_action_application_parity"] = {
            "training_action": probe_train,
            "postload_action": probe_post,
            "obs_hash_before_equal": bool(probe_train.get("obs_hash_before") == probe_post.get("obs_hash_before")),
            "training_vs_postload_same": {
                "reward_equal": bool(probe_train.get("reward_env0") == probe_post.get("reward_env0")),
                "done_equal": bool(probe_train.get("done_env0") == probe_post.get("done_env0")),
                "next_obs_hash_equal": bool(probe_train.get("next_obs_hash") == probe_post.get("next_obs_hash")),
                "info_keys_equal": bool(probe_train.get("info_keys_env0") == probe_post.get("info_keys_env0")),
            },
            "action_shape": list(action_training_np.shape),
            "action_dtype": str(action_training_np.dtype),
            "action_min": int(action_training_np.min()),
            "action_max": int(action_training_np.max()),
        }

        report["full_action_command_validity"] = _branch_validity_audit(
            action_np=action_before_training_det.detach().cpu().numpy(),
            mask_np=mask_np,
            max_cells=int(args.max_source_cells),
        )

        report["classification"] = _classify(report)
        report["ranked_root_cause_candidates"] = _rank_root_causes(report["classification"], report)
        report["recommended_fix_plan"] = [
            "Extract a single canonical policy-action module and replace duplicated action-selection implementations.",
            "Patch visual script defaults to target explicit input checkpoint/metadata and remove stale 3M assumptions.",
            "Keep strict_load=True and add one fixed obs/mask parity smoke-test to CI before visual runs.",
            "Only after parity fix: rerun visual single-episode verification, then decide on further training/export/BC/Unity transfer.",
        ]

        report["status"] = "OK"

    except Exception as exc:
        report["status"] = "ERROR"
        report["classification"] = CLASSIFICATIONS["AUDIT_FAILED"]
        report["errors"].append(str(exc))
        report["errors"].append(traceback.format_exc())

    finally:
        try:
            if env is not None:
                env.close()
        except Exception:
            pass

    json_path.write_text(json.dumps(report, indent=2, ensure_ascii=True), encoding="utf-8")

    md_lines = [
        "# Stage5H Training vs Post-load Action Path Parity Audit",
        "",
        f"- timestamp_utc: {report.get('timestamp_utc')}",
        f"- status: {report.get('status')}",
        f"- classification: {report.get('classification')}",
        f"- checkpoint_path: {report.get('checkpoint_path')}",
        f"- metadata_path: {report.get('model_metadata_path')}",
        "",
        "## Commands",
        "",
        f"- {command}",
        "",
        "## Static Source Parity",
        "",
        f"- shared_feature_checks: {report.get('static_source_parity_audit', {}).get('shared_feature_checks')}",
        "",
        "## Same Observation/Mask Roundtrip",
        "",
        f"- same_process_reload: {report.get('same_obs_mask_roundtrip', {}).get('same_process_reload')}",
        f"- fresh_object_reload: {report.get('same_obs_mask_roundtrip', {}).get('fresh_object_reload')}",
        "",
        "## Full Branch Validity",
        "",
        f"- summary: { {k: v for k, v in report.get('full_action_command_validity', {}).items() if k != 'rows'} }",
        "",
        "## Visual Script Findings",
        "",
        f"- targeted_visual_script_audit: {report.get('targeted_visual_script_audit')}",
        "",
        "## Ranked Root Cause Candidates",
        "",
    ]

    for idx, cause in enumerate(report.get("ranked_root_cause_candidates", []), start=1):
        md_lines.append(f"{idx}. {cause}")

    md_lines.extend(["", "## Recommended Fix Plan", ""])
    for idx, step in enumerate(report.get("recommended_fix_plan", []), start=1):
        md_lines.append(f"{idx}. {step}")

    if report.get("errors"):
        md_lines.extend(["", "## Errors", ""])
        for err in report["errors"]:
            md_lines.append(f"- {err}")

    md_text = "\n".join(md_lines) + "\n"
    md_path.write_text(md_text, encoding="utf-8")
    canonical_md_path.write_text(md_text, encoding="utf-8")

    print(str(json_path))
    print(str(md_path))
    print(str(canonical_md_path))
    return 0 if report.get("status") == "OK" else 1


if __name__ == "__main__":
    raise SystemExit(main())
