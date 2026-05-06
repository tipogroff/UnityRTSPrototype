from __future__ import annotations

import json
import re
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
BRANCH_SIZES = [6, 4, 4, 4, 4, 7, 49]
BRANCH_NAMES = [
    "action_type",
    "move_dir",
    "harvest_dir",
    "return_dir",
    "produce_dir",
    "produce_unit_type",
    "attack_target",
]


class Legacy032ActionPathError(RuntimeError):
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
        architecture_name: str = EXPECTED_ARCHITECTURE,
    ):
        super().__init__()
        self.mapsize = int(mapsize)
        self.nvec = [int(v) for v in nvec]
        self.architecture_name = str(architecture_name)
        if self.architecture_name != EXPECTED_ARCHITECTURE:
            raise Legacy032ActionPathError(
                f"Unsupported architecture for canonical path: {self.architecture_name}. "
                f"Expected {EXPECTED_ARCHITECTURE}."
            )

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


def _parse_nvec_from_metadata(value: Any) -> List[int]:
    nums = [int(x) for x in re.findall(r"\d+", str(value))]
    if len(nums) < 2:
        raise Legacy032ActionPathError(f"Cannot parse action nvec from metadata value: {value}")
    return nums


def load_metadata(metadata_path: Path | str) -> Dict[str, Any]:
    path = Path(metadata_path)
    if not path.exists():
        raise Legacy032ActionPathError(f"Metadata path does not exist: {path}")
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise Legacy032ActionPathError(f"Failed to parse metadata JSON: {path} ({exc})") from exc

    if not isinstance(raw, dict):
        raise Legacy032ActionPathError("Metadata must be a JSON object")

    obs_shape = [int(v) for v in (raw.get("observation_space") or [])]
    if isinstance(raw.get("action_space_nvec"), list):
        nvec = [int(v) for v in raw["action_space_nvec"]]
    elif isinstance(raw.get("gridmode_expected_nvec"), list):
        nvec = [int(v) for v in raw["gridmode_expected_nvec"]]
    else:
        nvec = _parse_nvec_from_metadata(raw.get("action_space"))

    architecture_name = str(raw.get("architecture_name", "")).strip()
    map_path = str(raw.get("map_path", "")).strip() or EXPECTED_MAP_PATH

    normalized = dict(raw)
    normalized["observation_space"] = obs_shape
    normalized["action_space_nvec"] = nvec
    normalized["architecture_name"] = architecture_name
    normalized["map_path"] = map_path
    return normalized


def assert_legacy032_contract(metadata: Dict[str, Any]) -> Dict[str, Any]:
    obs_shape = [int(v) for v in (metadata.get("observation_space") or [])]
    nvec = [int(v) for v in (metadata.get("action_space_nvec") or [])]
    architecture_name = str(metadata.get("architecture_name", "")).strip()
    map_path = str(metadata.get("map_path", "")).strip() or EXPECTED_MAP_PATH

    if obs_shape != EXPECTED_OBS_SHAPE:
        raise Legacy032ActionPathError(
            f"Observation contract mismatch: expected={EXPECTED_OBS_SHAPE}, actual={obs_shape}"
        )
    if nvec != EXPECTED_RAW_ACTION_NVEC:
        raise Legacy032ActionPathError(
            f"Action nvec contract mismatch: expected={EXPECTED_RAW_ACTION_NVEC}, actual={nvec}"
        )
    if architecture_name != EXPECTED_ARCHITECTURE:
        raise Legacy032ActionPathError(
            f"Architecture mismatch: expected={EXPECTED_ARCHITECTURE}, actual={architecture_name}"
        )
    if map_path != EXPECTED_MAP_PATH:
        raise Legacy032ActionPathError(
            f"Map contract mismatch: expected={EXPECTED_MAP_PATH}, actual={map_path}"
        )

    return {
        "observation_space": obs_shape,
        "action_space_nvec": nvec,
        "architecture_name": architecture_name,
        "map_path": map_path,
        "mapsize": int(nvec[0]),
        "mask_dim": int(1 + sum(nvec[1:])),
        "branch_sizes": list(BRANCH_SIZES),
    }


def build_policy_from_metadata(
    metadata: Dict[str, Any],
    device: torch.device,
    allow_fallback_architecture: bool = False,
) -> Tuple[Legacy032Policy, Dict[str, Any]]:
    contract = assert_legacy032_contract(metadata)
    arch = str(contract["architecture_name"])
    if (not allow_fallback_architecture) and arch != EXPECTED_ARCHITECTURE:
        raise Legacy032ActionPathError(
            f"Fallback architecture disabled; expected={EXPECTED_ARCHITECTURE}, actual={arch}"
        )

    policy = Legacy032Policy(
        obs_channels=int(contract["observation_space"][2]),
        nvec=contract["action_space_nvec"],
        mapsize=int(contract["mapsize"]),
        obs_hw=(int(contract["observation_space"][0]), int(contract["observation_space"][1])),
        architecture_name=arch,
    ).to(device)
    report = {
        "architecture": arch,
        "mapsize": int(contract["mapsize"]),
        "obs_shape": list(contract["observation_space"]),
        "nvec": list(contract["action_space_nvec"]),
        "fallback_architecture_used": False,
    }
    return policy, report


def load_policy_checkpoint_strict(
    policy: nn.Module,
    checkpoint_path: Path | str,
    device: torch.device,
    strict: bool = True,
) -> Dict[str, Any]:
    path = Path(checkpoint_path)
    if not path.exists():
        raise Legacy032ActionPathError(f"Checkpoint path does not exist: {path}")

    payload = torch.load(str(path), map_location=device)

    checkpoint_format = None
    if isinstance(payload, dict) and payload.get("checkpoint_kind") == "full_training_state":
        state_dict = payload.get("agent_state_dict")
        checkpoint_format = "full_training_checkpoint"
        if not isinstance(state_dict, dict):
            raise Legacy032ActionPathError("Full checkpoint missing agent_state_dict")
    elif isinstance(payload, dict) and "state_dict" in payload and isinstance(payload["state_dict"], dict):
        state_dict = payload["state_dict"]
        checkpoint_format = "wrapped_state_dict"
    elif isinstance(payload, dict):
        state_dict = payload
        checkpoint_format = "weights_only_state_dict"
    else:
        raise Legacy032ActionPathError("Checkpoint payload is not state_dict-compatible")

    if strict:
        incompatible = policy.load_state_dict(state_dict, strict=False)
        missing = list(incompatible.missing_keys)
        unexpected = [k for k in incompatible.unexpected_keys if not k.startswith("critic.")]
        if missing or unexpected:
            raise Legacy032ActionPathError(
                "Strict checkpoint load failed: "
                f"missing_keys={missing[:8]} unexpected_keys={unexpected[:8]}"
            )
        policy.load_state_dict(state_dict, strict=False)
    else:
        incompatible = policy.load_state_dict(state_dict, strict=False)
        missing = list(incompatible.missing_keys)
        unexpected = list(incompatible.unexpected_keys)

    return {
        "checkpoint_path": str(path),
        "checkpoint_format": checkpoint_format,
        "strict": bool(strict),
        "strict_load_status": "STRICT_LOAD_ENFORCED" if strict else "STRICT_LOAD_OPT_OUT",
        "missing_keys": missing,
        "unexpected_keys": unexpected,
    }


def normalize_action_mask(raw_mask: Any, num_envs: int, mapsize: int, mask_dim: int) -> np.ndarray:
    arr = np.asarray(raw_mask)
    if arr.ndim == 2 and arr.shape == (num_envs * mapsize, mask_dim):
        out = arr.reshape(num_envs, mapsize, mask_dim)
    elif arr.ndim == 3 and arr.shape == (num_envs, mapsize, mask_dim):
        out = arr
    elif arr.ndim == 4 and arr.shape[0] == num_envs and arr.shape[1] * arr.shape[2] == mapsize and arr.shape[3] == mask_dim:
        out = arr.reshape(num_envs, mapsize, mask_dim)
    else:
        raise Legacy032ActionPathError(
            f"Unsupported action mask shape: got={tuple(arr.shape)} expected one of "
            f"[(N*{mapsize},{mask_dim}), (N,{mapsize},{mask_dim}), (N,H,W,{mask_dim})]"
        )

    if out.shape != (num_envs, mapsize, mask_dim):
        raise Legacy032ActionPathError(
            f"Normalized mask shape mismatch: got={tuple(out.shape)} expected={(num_envs, mapsize, mask_dim)}"
        )
    return out.astype(np.float32, copy=False)


def read_action_mask(
    env: Any,
    num_envs: int,
    mapsize: int,
    mask_dim: int,
    require_mask: bool = True,
) -> Tuple[np.ndarray, str]:
    errors: List[str] = []

    if hasattr(env, "vec_client") and hasattr(env.vec_client, "getMasks"):
        try:
            raw = env.vec_client.getMasks(0)
            return normalize_action_mask(raw, num_envs, mapsize, mask_dim), "env.vec_client.getMasks(0)"
        except Exception as exc:
            errors.append(f"env.vec_client.getMasks(0) failed: {exc}")

    if hasattr(env, "get_action_mask"):
        try:
            raw = env.get_action_mask()
            return normalize_action_mask(raw, num_envs, mapsize, mask_dim), "env.get_action_mask"
        except Exception as exc:
            errors.append(f"env.get_action_mask failed: {exc}")

    if hasattr(env, "action_masks"):
        try:
            raw = env.action_masks() if callable(env.action_masks) else env.action_masks
            return normalize_action_mask(raw, num_envs, mapsize, mask_dim), "env.action_masks"
        except Exception as exc:
            errors.append(f"env.action_masks failed: {exc}")

    if require_mask:
        raise Legacy032ActionPathError("Action mask unavailable: " + " | ".join(errors or ["no mask API found"]))

    ones = np.ones((num_envs, mapsize, mask_dim), dtype=np.float32)
    return ones, "fallback_ones_mask"


def infer_logits(policy: nn.Module, obs_tensor: torch.Tensor) -> torch.Tensor:
    logits = policy.actor(policy.forward(obs_tensor))
    if logits.ndim != 4:
        raise Legacy032ActionPathError(f"Logits rank mismatch: expected 4D, got shape={list(logits.shape)}")

    n, h, w, c = [int(v) for v in logits.shape]
    if [h, w] != [EXPECTED_OBS_SHAPE[0], EXPECTED_OBS_SHAPE[1]]:
        raise Legacy032ActionPathError(
            f"Logits spatial shape mismatch: expected={[EXPECTED_OBS_SHAPE[0], EXPECTED_OBS_SHAPE[1]]}, actual={[h, w]}"
        )
    if c != sum(BRANCH_SIZES):
        raise Legacy032ActionPathError(f"Logits channel mismatch: expected={sum(BRANCH_SIZES)}, actual={c}")
    if n <= 0:
        raise Legacy032ActionPathError("Logits batch is empty")
    return logits


def split_logits_and_masks(
    logits: torch.Tensor,
    nvec: Sequence[int],
    action_mask: Optional[torch.Tensor],
) -> Tuple[List[torch.Tensor], List[torch.Tensor]]:
    split_sizes = [int(v) for v in nvec[1:]]
    if split_sizes != BRANCH_SIZES:
        raise Legacy032ActionPathError(f"Unexpected branch sizes from nvec: {split_sizes}")

    grid_logits = logits.reshape(-1, sum(split_sizes))
    split_logits = list(torch.split(grid_logits, split_sizes, dim=1))

    if action_mask is not None:
        mask_flat = action_mask.view(-1, action_mask.shape[-1])
        if int(mask_flat.shape[-1]) != int(1 + sum(split_sizes)):
            raise Legacy032ActionPathError(
                f"Mask width mismatch: expected={1 + sum(split_sizes)}, actual={int(mask_flat.shape[-1])}"
            )
        split_masks = list(torch.split(mask_flat[:, 1:], split_sizes, dim=1))
    else:
        split_masks = [torch.ones_like(sl, device=sl.device) for sl in split_logits]

    return split_logits, split_masks


def select_action_deterministic(
    logits: torch.Tensor,
    nvec: Sequence[int],
    action_mask: Optional[torch.Tensor],
) -> torch.Tensor:
    split_logits, split_masks = split_logits_and_masks(logits=logits, nvec=nvec, action_mask=action_mask)
    multi = [CategoricalMasked(logits=sl, masks=sm) for sl, sm in zip(split_logits, split_masks)]
    branches = [torch.argmax(c.logits, dim=1) for c in multi]
    action = torch.stack(branches).T.view(-1, int(nvec[0]), len(split_logits))
    return action


def select_action_stochastic(
    logits: torch.Tensor,
    nvec: Sequence[int],
    action_mask: Optional[torch.Tensor],
    seed: Optional[int] = None,
) -> torch.Tensor:
    if seed is not None:
        torch.manual_seed(int(seed))

    split_logits, split_masks = split_logits_and_masks(logits=logits, nvec=nvec, action_mask=action_mask)
    multi = [CategoricalMasked(logits=sl, masks=sm) for sl, sm in zip(split_logits, split_masks)]
    branches = [c.sample() for c in multi]
    action = torch.stack(branches).T.view(-1, int(nvec[0]), len(split_logits))
    return action


def format_env_action(action_tensor: torch.Tensor | np.ndarray) -> np.ndarray:
    if isinstance(action_tensor, torch.Tensor):
        arr = action_tensor.detach().cpu().numpy()
    else:
        arr = np.asarray(action_tensor)

    if arr.ndim != 3:
        raise Legacy032ActionPathError(f"Action rank mismatch: expected=3, actual={arr.ndim}")
    if arr.shape[1] != EXPECTED_RAW_ACTION_NVEC[0] or arr.shape[2] != len(BRANCH_SIZES):
        raise Legacy032ActionPathError(
            f"Action shape mismatch: expected=[N,{EXPECTED_RAW_ACTION_NVEC[0]},{len(BRANCH_SIZES)}], actual={list(arr.shape)}"
        )

    arr_i64 = arr.astype(np.int64, copy=False)
    bounds = [6, 4, 4, 4, 4, 7, 49]
    for i, bound in enumerate(bounds):
        col = arr_i64[:, :, i]
        if int(col.min()) < 0 or int(col.max()) >= bound:
            raise Legacy032ActionPathError(
                f"Branch bounds failed for {BRANCH_NAMES[i]}: min={int(col.min())}, max={int(col.max())}, bound={bound}"
            )

    out = np.ascontiguousarray(arr_i64.astype(np.int32, copy=False))
    if out.dtype != np.int32 or not out.flags["C_CONTIGUOUS"]:
        raise Legacy032ActionPathError("Formatted env action is not int32 contiguous")
    return out


def build_source_indexed_real_action(action_tensor: torch.Tensor | np.ndarray, mapsize: int) -> np.ndarray:
    arr = format_env_action(action_tensor)
    expected_mapsize = int(mapsize)
    if arr.shape[1] != expected_mapsize:
        raise Legacy032ActionPathError(
            f"mapsize mismatch for source-indexed action: mapsize={expected_mapsize}, action_shape={list(arr.shape)}"
        )

    num_envs = int(arr.shape[0])
    source_indices = np.arange(expected_mapsize, dtype=np.int32).reshape(1, expected_mapsize, 1)
    source_indices = np.broadcast_to(source_indices, (num_envs, expected_mapsize, 1))
    real_action = np.concatenate([source_indices, arr], axis=2)
    real_action = np.ascontiguousarray(real_action.astype(np.int32, copy=False))
    if real_action.shape != (num_envs, expected_mapsize, 8):
        raise Legacy032ActionPathError(
            f"source-indexed action shape mismatch: expected={[num_envs, expected_mapsize, 8]}, actual={list(real_action.shape)}"
        )
    return real_action


def filter_source_valid_real_actions(real_action: np.ndarray, action_mask: np.ndarray) -> Tuple[np.ndarray, np.ndarray, Dict[str, Any]]:
    real = np.asarray(real_action)
    mask = np.asarray(action_mask)

    if real.ndim != 3 or real.shape[2] != 8:
        raise Legacy032ActionPathError(
            f"real_action shape mismatch: expected=[N,mapsize,8], actual={list(real.shape)}"
        )
    if mask.ndim != 3 or mask.shape[0] != real.shape[0] or mask.shape[1] != real.shape[1]:
        raise Legacy032ActionPathError(
            f"action_mask shape mismatch for filtering: real_action={list(real.shape)} mask={list(mask.shape)}"
        )

    source_valid = mask[:, :, 0] > 0
    valid_actions = np.ascontiguousarray(real[source_valid].astype(np.int32, copy=False))
    valid_actions_counts = source_valid.sum(axis=1).astype(np.int32, copy=False)

    if valid_actions.size > 0:
        action_types = valid_actions[:, 1].astype(np.int32, copy=False)
    else:
        action_types = np.zeros((0,), dtype=np.int32)

    action_type_hist = {str(k): int(np.count_nonzero(action_types == k)) for k in range(6)}
    source_valid_total = int(valid_actions_counts.sum(dtype=np.int64))
    source_valid_non_noop_count = int(np.count_nonzero(action_types != 0)) if source_valid_total > 0 else 0

    debug = {
        "source_valid_total": source_valid_total,
        "valid_actions_counts": [int(v) for v in valid_actions_counts.tolist()],
        "first_valid_actions": valid_actions[:8].tolist(),
        "source_valid_non_noop_count": source_valid_non_noop_count,
        "action_type_histogram_source_valid": action_type_hist,
    }
    return valid_actions, valid_actions_counts, debug


def build_java_valid_actions(valid_actions: np.ndarray, valid_actions_counts: np.ndarray):
    from jpype.types import JArray, JInt

    valid_actions_np = np.asarray(valid_actions, dtype=np.int32)
    counts_np = np.asarray(valid_actions_counts, dtype=np.int32).reshape(-1)
    java_valid_actions = []
    valid_action_idx = 0

    for valid_action_count in counts_np:
        java_valid_action = []
        for _ in range(int(valid_action_count)):
            java_valid_action += [JArray(JInt)(valid_actions_np[valid_action_idx])]
            valid_action_idx += 1
        java_valid_actions += [JArray(JArray(JInt))(java_valid_action)]

    if valid_action_idx != int(valid_actions_np.shape[0]):
        raise Legacy032ActionPathError(
            "valid action cursor mismatch while building Java payload: "
            f"used={valid_action_idx} total={int(valid_actions_np.shape[0])}"
        )

    return JArray(JArray(JArray(JInt)))(java_valid_actions)


def format_training_compatible_java_actions(
    action_tensor: torch.Tensor | np.ndarray,
    action_mask: np.ndarray,
    mapsize: int,
) -> Dict[str, Any]:
    env_action = format_env_action(action_tensor)
    real_action = build_source_indexed_real_action(env_action, mapsize=int(mapsize))
    valid_actions, valid_actions_counts, debug = filter_source_valid_real_actions(real_action=real_action, action_mask=action_mask)
    java_valid_actions = build_java_valid_actions(valid_actions=valid_actions, valid_actions_counts=valid_actions_counts)

    return {
        "java_actions": java_valid_actions,
        "real_action": real_action,
        "valid_actions_counts": valid_actions_counts,
        "debug": debug,
    }


def step_env_training_compatible(
    env: Any,
    action_tensor: torch.Tensor | np.ndarray,
    action_mask: np.ndarray,
    mapsize: int,
) -> Tuple[Any, Dict[str, Any]]:
    payload = format_training_compatible_java_actions(
        action_tensor=action_tensor,
        action_mask=action_mask,
        mapsize=int(mapsize),
    )
    step_result = env.step(payload["java_actions"])
    debug = {
        "java_payload_used": True,
        "valid_actions_counts": [int(v) for v in np.asarray(payload["valid_actions_counts"]).tolist()],
        "first_valid_actions": payload["debug"].get("first_valid_actions", []),
        "source_valid_total": int(payload["debug"].get("source_valid_total", 0)),
        "source_valid_non_noop_count": int(payload["debug"].get("source_valid_non_noop_count", 0)),
        "action_type_histogram_source_valid": payload["debug"].get("action_type_histogram_source_valid", {}),
    }
    return step_result, debug


def summarize_action_distribution(action_tensor: torch.Tensor | np.ndarray, mask: Optional[np.ndarray] = None) -> Dict[str, Any]:
    arr = format_env_action(action_tensor)
    types = arr[:, :, 0].reshape(-1)

    all_counts = {str(k): int(np.count_nonzero(types == k)) for k in range(6)}
    total = int(types.size)
    all_shares = {k: float(v / max(1, total)) for k, v in all_counts.items()}

    out: Dict[str, Any] = {
        "all_cell_action_type_counts": all_counts,
        "all_cell_action_type_shares": all_shares,
    }

    if mask is not None:
        mask_np = np.asarray(mask)
        if mask_np.ndim != 3 or mask_np.shape[0] != arr.shape[0] or mask_np.shape[1] != arr.shape[1]:
            raise Legacy032ActionPathError(
                f"Mask shape mismatch for summary: action_shape={list(arr.shape)}, mask_shape={list(mask_np.shape)}"
            )
        source_valid = mask_np[:, :, 0].reshape(-1) > 0
        sv_types = types[source_valid]
        sv_counts = {str(k): int(np.count_nonzero(sv_types == k)) for k in range(6)}
        sv_total = int(sv_types.size)
        sv_shares = {k: (float(v / max(1, sv_total)) if sv_total > 0 else None) for k, v in sv_counts.items()}
        out["source_valid_action_type_counts"] = sv_counts
        out["source_valid_action_type_shares"] = sv_shares
        out["source_valid_non_noop_count"] = int(np.count_nonzero(sv_types != 0))
        out["source_valid_total"] = int(sv_total)

    return out


def validate_required_branch_parameters(action_tensor: torch.Tensor | np.ndarray, mask: np.ndarray) -> Dict[str, Any]:
    arr = format_env_action(action_tensor)
    mask_np = np.asarray(mask)
    if mask_np.ndim != 3 or mask_np.shape[0] != arr.shape[0] or mask_np.shape[1] != arr.shape[1]:
        raise Legacy032ActionPathError(
            f"Mask shape mismatch for branch validation: action_shape={list(arr.shape)}, mask_shape={list(mask_np.shape)}"
        )
    if int(mask_np.shape[2]) != 1 + sum(BRANCH_SIZES):
        raise Legacy032ActionPathError(
            f"Mask width mismatch for branch validation: expected={1 + sum(BRANCH_SIZES)}, actual={int(mask_np.shape[2])}"
        )

    mask_flat = mask_np.reshape(-1, mask_np.shape[-1])
    arr_flat = arr.reshape(-1, arr.shape[-1])

    split_masks = []
    start = 1
    for sz in BRANCH_SIZES:
        split_masks.append(mask_flat[:, start:start + sz])
        start += sz

    source_valid = mask_flat[:, 0] > 0
    source_indices = np.where(source_valid)[0].tolist()

    invalid_required = 0
    rows: List[Dict[str, Any]] = []
    for idx in source_indices:
        a = arr_flat[idx]
        action_type = int(a[0])
        req_move = action_type == 1
        req_harvest = action_type == 2
        req_return = action_type == 3
        req_produce = action_type == 4
        req_attack = action_type == 5

        checks = {
            "move_dir": bool(split_masks[1][idx, int(a[1])] > 0) if int(a[1]) < split_masks[1].shape[1] else False,
            "harvest_dir": bool(split_masks[2][idx, int(a[2])] > 0) if int(a[2]) < split_masks[2].shape[1] else False,
            "return_dir": bool(split_masks[3][idx, int(a[3])] > 0) if int(a[3]) < split_masks[3].shape[1] else False,
            "produce_dir": bool(split_masks[4][idx, int(a[4])] > 0) if int(a[4]) < split_masks[4].shape[1] else False,
            "produce_unit_type": bool(split_masks[5][idx, int(a[5])] > 0) if int(a[5]) < split_masks[5].shape[1] else False,
            "attack_target": bool(split_masks[6][idx, int(a[6])] > 0) if int(a[6]) < split_masks[6].shape[1] else False,
        }

        required_valid = True
        if req_move:
            required_valid = required_valid and checks["move_dir"]
        if req_harvest:
            required_valid = required_valid and checks["harvest_dir"]
        if req_return:
            required_valid = required_valid and checks["return_dir"]
        if req_produce:
            required_valid = required_valid and checks["produce_dir"] and checks["produce_unit_type"]
        if req_attack:
            required_valid = required_valid and checks["attack_target"]

        effective_noop_candidate = bool(action_type != 0 and not required_valid)
        if effective_noop_candidate:
            invalid_required += 1

        rows.append(
            {
                "flat_cell_index": int(idx),
                "action_type": int(action_type),
                "branches": [int(v) for v in a.tolist()],
                "required_valid": bool(required_valid),
                "effective_noop_candidate": effective_noop_candidate,
                "parameter_validity": checks,
            }
        )

    return {
        "source_valid_total": len(source_indices),
        "effective_noop_candidate_count": int(invalid_required),
        "effective_noop_candidate_share": float(invalid_required / max(1, len(source_indices))),
        "rows": rows,
    }
