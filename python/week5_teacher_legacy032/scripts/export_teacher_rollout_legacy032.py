#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import traceback
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np
import torch
import torch.nn as nn
from torch.distributions.categorical import Categorical


EXPECTED_OBS_SHAPE = [24, 24, 27]
EXPECTED_RAW_ACTION_NVEC = [576, 6, 4, 4, 4, 4, 7, 49]
EXPECTED_PER_CELL_ACTION_SHAPE = [576, 7]
EXPECTED_PER_CELL_BRANCH_SIZES = [6, 4, 4, 4, 4, 7, 49]
EXPECTED_ATTACK_SEMANTICS = "local_7x7_49"
EXPECTED_ARCHITECTURES = {
    "legacy032_reference_gridnet_v0",
    "legacy032_resolution_aware_gridnet_v1",
}
PREFLIGHT_24_MAP = "maps/24x24/basesWorkers24x24.xml"

ACTION_TYPE_NAMES = {
    0: "noop",
    1: "move",
    2: "harvest",
    3: "return",
    4: "produce",
    5: "attack",
}


class ExportError(RuntimeError):
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
            x = torch.nn.functional.interpolate(x, size=self.target_hw, mode="bilinear", align_corners=False)
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
        if architecture_name == "legacy032_resolution_aware_gridnet_v1":
            self.actor = ResolutionAwareDecoder(output_channels, target_hw=obs_hw)
        else:
            self.actor = Decoder(output_channels)

    def forward(self, x):
        return self.encoder(x)

    def infer_actions(
        self,
        obs_tensor: torch.Tensor,
        action_mask: Optional[torch.Tensor],
        device: torch.device,
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        logits = self.actor(self.forward(obs_tensor))
        split_sizes = self.nvec[1:]
        grid_logits = logits.reshape(-1, sum(split_sizes))
        split_logits = torch.split(grid_logits, split_sizes, dim=1)

        if action_mask is not None:
            mask_flat = action_mask.view(-1, action_mask.shape[-1])
            split_masks = torch.split(mask_flat[:, 1:], split_sizes, dim=1)
        else:
            split_masks = [torch.ones_like(sl, device=device) for sl in split_logits]

        multi = [CategoricalMasked(logits=sl, masks=sm) for sl, sm in zip(split_logits, split_masks)]
        action_branches = [torch.argmax(c.logits, dim=1) for c in multi]
        action = torch.stack(action_branches).T.view(-1, self.mapsize, len(split_sizes))
        entropy = torch.stack([c.entropy() for c in multi]).T
        return action, entropy


@dataclass
class EpisodeStats:
    episode_id: int
    steps: int
    reward_sum: float
    ended_by_done: bool
    ended_by_truncated: bool
    ended_by_step_limit: bool


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _now_compact() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_bool(value: str) -> bool:
    v = str(value).strip().lower()
    if v in {"1", "true", "yes", "y", "on"}:
        return True
    if v in {"0", "false", "no", "n", "off"}:
        return False
    raise argparse.ArgumentTypeError(f"Invalid boolean value: {value}")


def _parse_nvec_from_str(value: str) -> List[int]:
    nums = [int(x) for x in re.findall(r"\d+", value)]
    if len(nums) < 2:
        raise ExportError(f"Cannot parse action nvec from metadata value: {value}")
    return nums


def _resolve_path(path_str: str) -> Path:
    p = Path(path_str)
    if p.is_absolute():
        return p
    return (_repo_root() / p).resolve()


def _json_dump(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")


def _json_line(payload: Dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=True, sort_keys=True)


def _load_metadata(path: Path) -> Dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ExportError(f"Failed to parse metadata JSON: {path} ({exc})") from exc


def _extract_raw_nvec(metadata: Dict[str, Any]) -> List[int]:
    if isinstance(metadata.get("action_space_nvec"), list):
        return [int(v) for v in metadata["action_space_nvec"]]
    if isinstance(metadata.get("gridmode_expected_nvec"), list):
        return [int(v) for v in metadata["gridmode_expected_nvec"]]
    action_space = metadata.get("action_space")
    if action_space is None:
        raise ExportError("Metadata missing action space fields (action_space_nvec/gridmode_expected_nvec/action_space).")
    return _parse_nvec_from_str(str(action_space))


def _validate_metadata_contract(metadata: Dict[str, Any]) -> Tuple[str, str, List[int]]:
    obs_shape = metadata.get("observation_space")
    if [int(v) for v in (obs_shape or [])] != EXPECTED_OBS_SHAPE:
        raise ExportError(
            f"Metadata observation contract mismatch. expected={EXPECTED_OBS_SHAPE}, actual={obs_shape}"
        )

    raw_nvec = _extract_raw_nvec(metadata)
    if raw_nvec != EXPECTED_RAW_ACTION_NVEC:
        raise ExportError(
            "Metadata raw action nvec mismatch. "
            f"expected={EXPECTED_RAW_ACTION_NVEC}, actual={raw_nvec}"
        )

    architecture_name = str(metadata.get("architecture_name", "")).strip()
    if not architecture_name:
        raise ExportError("Metadata missing architecture_name.")
    if architecture_name not in EXPECTED_ARCHITECTURES:
        raise ExportError(
            "Unsupported architecture_name for Legacy032 exporter: "
            f"{architecture_name}. expected one of {sorted(EXPECTED_ARCHITECTURES)}"
        )

    attack_semantics = str(metadata.get("attack_target_semantics", "")).strip()
    if attack_semantics and attack_semantics != EXPECTED_ATTACK_SEMANTICS:
        raise ExportError(
            "Metadata attack_target_semantics mismatch. "
            f"expected={EXPECTED_ATTACK_SEMANTICS}, actual={attack_semantics}"
        )

    run_id = str(metadata.get("exp_name", "")).strip()
    if not run_id:
        run_id = "unknown_run_id"

    return run_id, architecture_name, raw_nvec


def _load_checkpoint_state_dict(path: Path, device: torch.device) -> Dict[str, Any]:
    try:
        payload = torch.load(str(path), map_location=device)
    except Exception as exc:
        raise ExportError(f"Failed to load checkpoint: {path} ({exc})") from exc

    if isinstance(payload, dict) and "state_dict" in payload and isinstance(payload["state_dict"], dict):
        return payload["state_dict"]
    if isinstance(payload, dict):
        return payload
    raise ExportError("Checkpoint payload is not state_dict-compatible.")


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


def _normalize_mask_array(raw_mask: Any, num_envs: int, mapsize: int, mask_dim: int) -> np.ndarray:
    arr = np.asarray(raw_mask)
    if arr.ndim == 2:
        if arr.shape == (num_envs * mapsize, mask_dim):
            return arr.reshape(num_envs, mapsize, mask_dim)
        raise ExportError(f"Unexpected 2D mask shape: {tuple(arr.shape)}")
    if arr.ndim == 3:
        if arr.shape[0] == num_envs and arr.shape[1] == mapsize and arr.shape[2] == mask_dim:
            return arr
        if arr.shape[0] == num_envs * mapsize and arr.shape[1] == 1 and arr.shape[2] == mask_dim:
            return arr.reshape(num_envs, mapsize, mask_dim)
        raise ExportError(f"Unexpected 3D mask shape: {tuple(arr.shape)}")
    if arr.ndim == 4:
        if arr.shape[0] == num_envs and arr.shape[1] * arr.shape[2] == mapsize and arr.shape[3] == mask_dim:
            return arr.reshape(num_envs, mapsize, mask_dim)
        raise ExportError(f"Unexpected 4D mask shape: {tuple(arr.shape)}")
    raise ExportError(f"Unsupported mask rank: shape={tuple(arr.shape)}")


def _read_action_mask(env: Any, num_envs: int, mapsize: int, mask_dim: int) -> Tuple[Optional[np.ndarray], bool, str]:
    # Preferred legacy032 source.
    if hasattr(env, "vec_client") and hasattr(env.vec_client, "getMasks"):
        try:
            raw = env.vec_client.getMasks(0)
            return _normalize_mask_array(raw, num_envs, mapsize, mask_dim), True, "env.vec_client.getMasks(0)"
        except Exception:
            pass

    # Fallback provider.
    if hasattr(env, "get_action_mask"):
        try:
            raw = env.get_action_mask()
            return _normalize_mask_array(raw, num_envs, mapsize, mask_dim), True, "env.get_action_mask"
        except Exception:
            pass

    # Another fallback provider.
    if hasattr(env, "action_masks"):
        try:
            attr = getattr(env, "action_masks")
            raw = attr() if callable(attr) else attr
            return _normalize_mask_array(raw, num_envs, mapsize, mask_dim), True, "env.action_masks"
        except Exception:
            pass

    return None, False, "unavailable"


def _validate_per_cell_action_bounds(per_cell_action: np.ndarray) -> None:
    if per_cell_action.shape != tuple(EXPECTED_PER_CELL_ACTION_SHAPE):
        raise ExportError(
            "per_cell_action shape mismatch. "
            f"expected={EXPECTED_PER_CELL_ACTION_SHAPE}, actual={list(per_cell_action.shape)}"
        )

    if per_cell_action.dtype.kind not in {"i", "u"}:
        raise ExportError(f"per_cell_action dtype must be integer, got {per_cell_action.dtype}")

    for branch_idx, branch_size in enumerate(EXPECTED_PER_CELL_BRANCH_SIZES):
        col = per_cell_action[:, branch_idx]
        min_v = int(col.min())
        max_v = int(col.max())
        if min_v < 0 or max_v >= branch_size:
            raise ExportError(
                "per_cell_action out of branch bounds at branch "
                f"{branch_idx}: min={min_v}, max={max_v}, size={branch_size}"
            )


def _raw_action_to_per_cell(raw_action: Any) -> np.ndarray:
    arr = np.asarray(raw_action)

    if arr.ndim == 3 and arr.shape[0] == 1:
        arr = arr[0]

    # Native gridmode per-cell format.
    if arr.ndim == 2 and arr.shape == tuple(EXPECTED_PER_CELL_ACTION_SHAPE):
        return arr.astype(np.int32, copy=False)

    # Flattened per-cell format.
    if arr.ndim == 1 and arr.shape[0] == EXPECTED_PER_CELL_ACTION_SHAPE[0] * EXPECTED_PER_CELL_ACTION_SHAPE[1]:
        return arr.reshape(EXPECTED_PER_CELL_ACTION_SHAPE).astype(np.int32, copy=False)

    # Global/single-action style [source_cell, action_type, ... 6 branches] => [8].
    if arr.ndim == 1 and arr.shape[0] == 8:
        src = int(arr[0])
        if src < 0 or src >= EXPECTED_PER_CELL_ACTION_SHAPE[0]:
            raise ExportError(f"source-cell index out of bounds in raw action: {src}")
        per_cell = np.zeros(tuple(EXPECTED_PER_CELL_ACTION_SHAPE), dtype=np.int32)
        per_cell[src, :] = arr[1:8].astype(np.int32, copy=False)
        return per_cell

    if arr.ndim == 2 and arr.shape == (1, 8):
        return _raw_action_to_per_cell(arr.reshape(8))

    raise ExportError(f"Unsupported raw_action_t shape for per-cell conversion: {list(arr.shape)}")


def _action_type_name(action_type: int) -> str:
    return ACTION_TYPE_NAMES.get(int(action_type), str(int(action_type)))


def _hist_to_sorted_dict(counter: Counter) -> Dict[str, int]:
    return {str(k): int(counter[k]) for k in sorted(counter.keys())}


def _apply_reproducibility_seed(seed: int, use_cuda: bool) -> None:
    np.random.seed(seed)
    torch.manual_seed(seed)
    if use_cuda and torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def _try_seed_env(env: Any, seed: int, warnings: List[str]) -> None:
    # Legacy gym_microrts variants expose different seeding APIs;
    # try common options without hard-failing unsupported paths.
    if hasattr(env, "seed"):
        try:
            env.seed(seed)
        except Exception as exc:
            warnings.append(f"env.seed({seed}) failed: {exc}")

    if hasattr(env, "action_space") and hasattr(env.action_space, "seed"):
        try:
            env.action_space.seed(seed)
        except Exception as exc:
            warnings.append(f"env.action_space.seed({seed}) failed: {exc}")


def _safe_reset_env(env: Any, seed: int) -> Any:
    try:
        return env.reset(seed=seed)
    except TypeError:
        return env.reset()
    except Exception:
        return env.reset()


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=(
            "Legacy032 raw rollout exporter for trained 3M teacher. "
            "Exports raw trajectories only (no Unity adaptation performed)."
        )
    )
    p.add_argument("--checkpoint-path", required=True)
    p.add_argument("--model-metadata-path", required=True)
    p.add_argument("--run-label", required=True)
    p.add_argument("--episodes", type=int, default=16)
    p.add_argument("--seed", type=int, default=17)
    p.add_argument("--device", default="cpu", choices=("cpu", "cuda"))
    p.add_argument(
        "--env-mode",
        default="target_24x24_gridmode",
        choices=("target_24x24_gridmode",),
        help="Current exporter scope is target_24x24_gridmode only.",
    )
    p.add_argument("--require-mask", type=_parse_bool, default=True)
    p.add_argument("--max-steps-per-episode", type=int, default=6000)
    p.add_argument("--output-dir", required=True)
    p.add_argument(
        "--write-jsonl",
        default="never",
        choices=("debug", "never"),
        help="Write teacher_rollout_debug.jsonl when set to debug.",
    )
    return p.parse_args()


def main() -> int:
    args = parse_args()

    checkpoint_path = _resolve_path(args.checkpoint_path)
    metadata_path = _resolve_path(args.model_metadata_path)
    output_root = _resolve_path(args.output_dir)

    if not checkpoint_path.exists():
        raise ExportError(f"Checkpoint not found: {checkpoint_path}")
    if not metadata_path.exists():
        raise ExportError(f"Model metadata not found: {metadata_path}")

    metadata = _load_metadata(metadata_path)
    run_id, architecture_name, raw_nvec = _validate_metadata_contract(metadata)

    # Additional anti-v1 guard.
    if raw_nvec[6] == 9 or raw_nvec[6] == 4:
        raise ExportError(
            "Detected v1-like action branches in metadata; refusing export to prevent v1 remap path. "
            f"raw_action_nvec={raw_nvec}"
        )

    # Device selection.
    use_cuda = args.device == "cuda" and torch.cuda.is_available()
    device = torch.device("cuda" if use_cuda else "cpu")

    # Reproducibility controls (seed must be applied, not only accepted as CLI arg).
    _apply_reproducibility_seed(seed=int(args.seed), use_cuda=bool(use_cuda))

    # Build policy and load checkpoint.
    state_dict = _load_checkpoint_state_dict(checkpoint_path, device)
    policy = Legacy032Policy(
        obs_channels=EXPECTED_OBS_SHAPE[2],
        nvec=raw_nvec,
        mapsize=EXPECTED_PER_CELL_ACTION_SHAPE[0],
        obs_hw=(EXPECTED_OBS_SHAPE[0], EXPECTED_OBS_SHAPE[1]),
        architecture_name=architecture_name,
    ).to(device)
    missing, unexpected = policy.load_state_dict(state_dict, strict=False)
    policy.eval()

    warnings: List[str] = []
    if missing or unexpected:
        warnings.append(
            f"Checkpoint loaded with non-strict key diff: missing={len(missing)}, unexpected={len(unexpected)}"
        )

    export_dir = output_root / f"{args.run_label}_{_now_compact()}"
    export_dir.mkdir(parents=True, exist_ok=False)

    # Runtime outputs.
    raw_out_npz = export_dir / "teacher_rollout_raw.npz"
    manifest_json = export_dir / "teacher_rollout_manifest.json"
    summary_json = export_dir / "teacher_rollout_summary.json"
    summary_md = export_dir / "teacher_rollout_summary.md"
    debug_jsonl = export_dir / "teacher_rollout_debug.jsonl"
    write_debug = args.write_jsonl == "debug"

    # Aggregated dataset buffers (per step).
    episode_id_t: List[int] = []
    step_id_t: List[int] = []
    observation_t: List[np.ndarray] = []
    raw_action_t: List[Any] = []
    per_cell_action_t: List[np.ndarray] = []
    reward_t: List[float] = []
    done_t: List[bool] = []
    terminated_t: List[bool] = []
    truncated_t: List[bool] = []
    info_t_json: List[str] = []
    action_mask_t: List[Any] = []
    action_mask_available_t: List[bool] = []

    steps_per_episode: List[int] = []
    episode_stats: List[EpisodeStats] = []

    action_type_hist: Counter = Counter()
    produce_type_hist: Counter = Counter()
    attack_target_hist: Counter = Counter()

    total_cells = 0
    total_noop_cells = 0
    mask_available_steps = 0

    env = None
    try:
        env = _create_target_24x24_gridmode_env(metadata, int(args.max_steps_per_episode))
        _try_seed_env(env=env, seed=int(args.seed), warnings=warnings)

        # Hard contract check on runtime env.
        env_obs_shape = [int(v) for v in env.observation_space.shape]
        env_nvec = [int(v) for v in env.action_space.nvec.tolist()]
        if env_obs_shape != EXPECTED_OBS_SHAPE:
            raise ExportError(
                f"Environment observation shape mismatch. expected={EXPECTED_OBS_SHAPE}, actual={env_obs_shape}"
            )
        if env_nvec != EXPECTED_RAW_ACTION_NVEC:
            raise ExportError(
                f"Environment action nvec mismatch. expected={EXPECTED_RAW_ACTION_NVEC}, actual={env_nvec}"
            )

        for ep in range(int(args.episodes)):
            obs = _safe_reset_env(env, seed=int(args.seed) + int(ep))
            if isinstance(obs, tuple):
                obs = obs[0]
            obs = np.asarray(obs)

            if obs.ndim != 4:
                raise ExportError(f"Unexpected reset observation rank: shape={list(obs.shape)}")
            if [int(v) for v in obs.shape[1:]] != EXPECTED_OBS_SHAPE:
                raise ExportError(
                    "Reset observation shape mismatch. "
                    f"expected=[N,{EXPECTED_OBS_SHAPE[0]},{EXPECTED_OBS_SHAPE[1]},{EXPECTED_OBS_SHAPE[2]}], "
                    f"actual={list(obs.shape)}"
                )

            ep_reward_sum = 0.0
            ep_steps = 0
            ep_done = False
            ep_truncated = False
            ep_step_limit = False

            for step in range(int(args.max_steps_per_episode)):
                num_envs = int(obs.shape[0])
                mask_dim = int(1 + sum(EXPECTED_PER_CELL_BRANCH_SIZES))
                mask_np, mask_available, mask_source = _read_action_mask(
                    env=env,
                    num_envs=num_envs,
                    mapsize=EXPECTED_PER_CELL_ACTION_SHAPE[0],
                    mask_dim=mask_dim,
                )

                if args.require_mask and not mask_available:
                    raise ExportError(
                        "--require-mask true but action mask is unavailable. "
                        f"episode={ep}, step={step}, source={mask_source}"
                    )

                if mask_available:
                    mask_available_steps += 1
                    mask_tensor = torch.as_tensor(mask_np, device=device, dtype=torch.float32)
                else:
                    mask_tensor = None

                obs_f32 = obs.astype(np.float32, copy=False)
                obs_tensor = torch.as_tensor(obs_f32, device=device, dtype=torch.float32)

                with torch.no_grad():
                    action_torch, entropy_torch = policy.infer_actions(
                        obs_tensor=obs_tensor,
                        action_mask=mask_tensor,
                        device=device,
                    )

                action_env = action_torch.detach().cpu().numpy().astype(np.int32)

                if action_env.ndim != 3 or list(action_env.shape[1:]) != EXPECTED_PER_CELL_ACTION_SHAPE:
                    raise ExportError(
                        "Policy action tensor shape mismatch. "
                        f"expected=[N,{EXPECTED_PER_CELL_ACTION_SHAPE[0]},{EXPECTED_PER_CELL_ACTION_SHAPE[1]}], "
                        f"actual={list(action_env.shape)}"
                    )

                step_result = env.step(action_env)
                if len(step_result) == 4:
                    next_obs, reward_arr, done_arr, info_arr = step_result
                    trunc_arr = np.zeros_like(done_arr)
                elif len(step_result) == 5:
                    next_obs, reward_arr, done_arr, trunc_arr, info_arr = step_result
                else:
                    raise ExportError(f"Unexpected env.step() return arity: {len(step_result)}")

                reward_arr = np.asarray(reward_arr, dtype=np.float32)
                done_arr = np.asarray(done_arr)
                trunc_arr = np.asarray(trunc_arr)

                reward_scalar = float(reward_arr.reshape(-1)[0])
                done_scalar = bool(done_arr.reshape(-1)[0])
                trunc_scalar = bool(trunc_arr.reshape(-1)[0])
                term_scalar = bool(done_scalar and not trunc_scalar)

                raw_action_step = action_env[0].copy()
                per_cell_step = _raw_action_to_per_cell(raw_action_step)
                _validate_per_cell_action_bounds(per_cell_step)

                # Explicit anti-remap guards.
                if int(per_cell_step[:, 5].max()) > 6:
                    raise ExportError("produce_unit_type exceeds allowed v2 range 0..6")
                if int(per_cell_step[:, 6].max()) > 48:
                    raise ExportError("attack_target_local exceeds allowed v2 range 0..48")

                obs_step = obs_f32[0]
                if list(obs_step.shape) != EXPECTED_OBS_SHAPE:
                    raise ExportError(
                        "Per-step observation shape mismatch. "
                        f"expected={EXPECTED_OBS_SHAPE}, actual={list(obs_step.shape)}"
                    )

                # Collect step records.
                episode_id_t.append(int(ep))
                step_id_t.append(int(step))
                observation_t.append(obs_step.astype(np.float32, copy=False))
                raw_action_t.append(raw_action_step.astype(np.int32, copy=False))
                per_cell_action_t.append(per_cell_step.astype(np.int16, copy=False))
                reward_t.append(reward_scalar)
                done_t.append(done_scalar)
                terminated_t.append(term_scalar)
                truncated_t.append(trunc_scalar)

                info_payload = info_arr[0] if isinstance(info_arr, (list, tuple)) and len(info_arr) > 0 else info_arr
                try:
                    info_t_json.append(_json_line(info_payload if isinstance(info_payload, dict) else {"raw": str(info_payload)}))
                except Exception:
                    info_t_json.append(_json_line({"raw": str(info_payload)}))

                if mask_available and mask_np is not None:
                    action_mask_t.append(mask_np[0].astype(np.uint8, copy=False))
                else:
                    action_mask_t.append(None)
                action_mask_available_t.append(bool(mask_available))

                # Stats.
                action_type_col = per_cell_step[:, 0].astype(np.int32, copy=False)
                total_cells += int(action_type_col.shape[0])
                total_noop_cells += int(np.count_nonzero(action_type_col == 0))
                action_type_hist.update(int(v) for v in action_type_col.tolist())

                produce_mask = action_type_col == 4
                if np.any(produce_mask):
                    produce_vals = per_cell_step[:, 5][produce_mask]
                    produce_type_hist.update(int(v) for v in produce_vals.tolist())

                attack_mask = action_type_col == 5
                if np.any(attack_mask):
                    attack_vals = per_cell_step[:, 6][attack_mask]
                    attack_target_hist.update(int(v) for v in attack_vals.tolist())

                if write_debug:
                    debug_entry = {
                        "episode_id": int(ep),
                        "step_id": int(step),
                        "reward": reward_scalar,
                        "done": done_scalar,
                        "terminated": term_scalar,
                        "truncated": trunc_scalar,
                        "mask_available": bool(mask_available),
                        "mask_source": mask_source,
                        "policy_entropy_proxy": float(entropy_torch.mean().item()),
                        "action_type_counts": {
                            _action_type_name(k): int(v)
                            for k, v in sorted(Counter(action_type_col.tolist()).items())
                        },
                    }
                    with debug_jsonl.open("a", encoding="utf-8") as fh:
                        fh.write(json.dumps(debug_entry, ensure_ascii=True) + "\n")

                ep_reward_sum += reward_scalar
                ep_steps += 1

                obs = np.asarray(next_obs)

                if done_scalar or trunc_scalar:
                    ep_done = done_scalar
                    ep_truncated = trunc_scalar
                    break

            if not ep_done and not ep_truncated and ep_steps >= int(args.max_steps_per_episode):
                ep_step_limit = True

            steps_per_episode.append(ep_steps)
            episode_stats.append(
                EpisodeStats(
                    episode_id=int(ep),
                    steps=int(ep_steps),
                    reward_sum=float(ep_reward_sum),
                    ended_by_done=bool(ep_done),
                    ended_by_truncated=bool(ep_truncated),
                    ended_by_step_limit=bool(ep_step_limit),
                )
            )

    finally:
        if env is not None:
            try:
                env.close()
            except Exception:
                pass

    if not observation_t:
        raise ExportError("No rollout data collected (zero steps exported).")

    # Serialize NPZ.
    raw_action_obj = np.empty((len(raw_action_t),), dtype=object)
    for i, item in enumerate(raw_action_t):
        raw_action_obj[i] = item

    mask_obj = np.empty((len(action_mask_t),), dtype=object)
    for i, item in enumerate(action_mask_t):
        mask_obj[i] = item

    np.savez_compressed(
        raw_out_npz,
        episode_id=np.asarray(episode_id_t, dtype=np.int32),
        step_id=np.asarray(step_id_t, dtype=np.int32),
        observation_t=np.asarray(observation_t, dtype=np.float32),
        raw_action_t=raw_action_obj,
        per_cell_action_t=np.asarray(per_cell_action_t, dtype=np.int16),
        reward_t=np.asarray(reward_t, dtype=np.float32),
        done_t=np.asarray(done_t, dtype=np.bool_),
        terminated_t=np.asarray(terminated_t, dtype=np.bool_),
        truncated_t=np.asarray(truncated_t, dtype=np.bool_),
        info_t_json=np.asarray(info_t_json, dtype=object),
        action_mask_t=mask_obj,
        action_mask_available_t=np.asarray(action_mask_available_t, dtype=np.bool_),
    )

    # Build manifest.
    manifest = {
        "generated_at_utc": _now_iso(),
        "teacher_lineage": "legacy032",
        "source_pipeline": "gym_microrts==0.3.2",
        "checkpoint_path": str(checkpoint_path),
        "model_metadata_path": str(metadata_path),
        "run_id": run_id,
        "architecture_name": architecture_name,
        "observation_shape": EXPECTED_OBS_SHAPE,
        "raw_action_nvec": EXPECTED_RAW_ACTION_NVEC,
        "exported_per_cell_action_shape": EXPECTED_PER_CELL_ACTION_SHAPE,
        "exported_per_cell_branch_sizes": EXPECTED_PER_CELL_BRANCH_SIZES,
        "attack_target_semantics": EXPECTED_ATTACK_SEMANTICS,
        "direct_weight_transfer_claim": False,
        "semantic_parity_claim": False,
        "notes": "Raw rollout export only; Unity adaptation is not performed in this step.",
    }
    _json_dump(manifest_json, manifest)

    # Build summary.
    rewards_arr = np.asarray(reward_t, dtype=np.float64)
    mask_share = float(np.mean(np.asarray(action_mask_available_t, dtype=np.float64)))
    noop_share = float(total_noop_cells / max(1, total_cells))

    terminal_done_count = int(sum(1 for e in episode_stats if e.ended_by_done))
    terminal_truncated_count = int(sum(1 for e in episode_stats if e.ended_by_truncated))
    terminal_step_limit_count = int(sum(1 for e in episode_stats if e.ended_by_step_limit))

    attack_total = int(sum(attack_target_hist.values()))
    attack_diversity = {
        "count": attack_total,
        "unique_targets": int(len(attack_target_hist)),
        "max_target_index": int(max(attack_target_hist.keys())) if attack_target_hist else None,
    }

    summary_warnings = list(warnings)
    if args.require_mask and mask_share < 1.0:
        # This should normally be unreachable because require-mask causes hard fail,
        # but we still surface explicit warning if partial availability somehow occurs.
        summary_warnings.append("Mask is not available on all steps while --require-mask true.")
    if noop_share >= 0.98:
        summary_warnings.append(
            f"Actions are almost fully noop (noop_share={noop_share:.6f})."
        )

    contract_shape_ok = (
        True
        if np.asarray(observation_t, dtype=np.float32).shape[1:] == tuple(EXPECTED_OBS_SHAPE)
        and np.asarray(per_cell_action_t, dtype=np.int16).shape[1:] == tuple(EXPECTED_PER_CELL_ACTION_SHAPE)
        else False
    )
    if not contract_shape_ok:
        summary_warnings.append("Exported tensor shapes differ from expected contract.")

    summary = {
        "generated_at_utc": _now_iso(),
        "status": "success",
        "run_label": args.run_label,
        "output_dir": str(export_dir),
        "number_of_episodes": int(args.episodes),
        "total_steps": int(len(step_id_t)),
        "steps_per_episode": [int(v) for v in steps_per_episode],
        "reward_summary": {
            "mean": float(rewards_arr.mean()),
            "std": float(rewards_arr.std()),
            "min": float(rewards_arr.min()),
            "max": float(rewards_arr.max()),
            "sum": float(rewards_arr.sum()),
        },
        "done_terminated_truncated_counts": {
            "done_t_true_steps": int(np.count_nonzero(np.asarray(done_t, dtype=np.bool_))),
            "terminated_t_true_steps": int(np.count_nonzero(np.asarray(terminated_t, dtype=np.bool_))),
            "truncated_t_true_steps": int(np.count_nonzero(np.asarray(truncated_t, dtype=np.bool_))),
            "episode_terminal_done_count": terminal_done_count,
            "episode_terminal_truncated_count": terminal_truncated_count,
            "episode_step_limit_count": terminal_step_limit_count,
        },
        "action_mask_available_share": mask_share,
        "basic_action_type_histogram": {
            _action_type_name(int(k)): int(v)
            for k, v in sorted(action_type_hist.items())
        },
        "produce_unit_type_histogram": _hist_to_sorted_dict(produce_type_hist),
        "attack_target_local": {
            "histogram": _hist_to_sorted_dict(attack_target_hist),
            "diversity": attack_diversity,
        },
        "contract_checks": {
            "observation_shape_expected": EXPECTED_OBS_SHAPE,
            "per_cell_action_shape_expected": EXPECTED_PER_CELL_ACTION_SHAPE,
            "per_cell_branch_sizes_expected": EXPECTED_PER_CELL_BRANCH_SIZES,
            "shape_match_expected_contract": bool(contract_shape_ok),
        },
        "warnings": summary_warnings,
    }
    _json_dump(summary_json, summary)

    # Build summary markdown.
    lines = [
        "# Legacy032 Raw Rollout Export Summary",
        "",
        f"- run_label: {args.run_label}",
        f"- output_dir: {export_dir}",
        f"- checkpoint_path: {checkpoint_path}",
        f"- model_metadata_path: {metadata_path}",
        f"- number_of_episodes: {summary['number_of_episodes']}",
        f"- total_steps: {summary['total_steps']}",
        "",
        "## Reward Summary",
        "",
        f"- mean: {summary['reward_summary']['mean']:.6f}",
        f"- std: {summary['reward_summary']['std']:.6f}",
        f"- min: {summary['reward_summary']['min']:.6f}",
        f"- max: {summary['reward_summary']['max']:.6f}",
        f"- sum: {summary['reward_summary']['sum']:.6f}",
        "",
        "## Contract and Mask",
        "",
        f"- action_mask_available_share: {summary['action_mask_available_share']:.6f}",
        f"- shape_match_expected_contract: {summary['contract_checks']['shape_match_expected_contract']}",
        "",
        "## Action Histograms",
        "",
        "### action_type",
    ]
    for k, v in summary["basic_action_type_histogram"].items():
        lines.append(f"- {k}: {v}")

    lines += ["", "### produce_unit_type"]
    if summary["produce_unit_type_histogram"]:
        for k, v in summary["produce_unit_type_histogram"].items():
            lines.append(f"- {k}: {v}")
    else:
        lines.append("- none")

    lines += ["", "### attack_target_local"]
    if summary["attack_target_local"]["histogram"]:
        for k, v in summary["attack_target_local"]["histogram"].items():
            lines.append(f"- {k}: {v}")
    else:
        lines.append("- none")

    lines += [
        "",
        "## Warnings",
    ]
    if summary_warnings:
        for w in summary_warnings:
            lines.append(f"- {w}")
    else:
        lines.append("- none")

    summary_md.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(json.dumps({
        "status": "success",
        "output_dir": str(export_dir),
        "teacher_rollout_raw": str(raw_out_npz),
        "teacher_rollout_manifest": str(manifest_json),
        "teacher_rollout_summary": str(summary_json),
        "teacher_rollout_summary_md": str(summary_md),
        "teacher_rollout_debug_jsonl": str(debug_jsonl) if write_debug else None,
    }, ensure_ascii=True, indent=2))

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception as exc:
        traceback.print_exc()
        raise SystemExit(f"[export_teacher_rollout_legacy032] ERROR: {exc}")
