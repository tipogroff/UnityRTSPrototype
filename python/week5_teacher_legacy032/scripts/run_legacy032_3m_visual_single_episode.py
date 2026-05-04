#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import traceback
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np
import torch
import torch.nn as nn
from torch.distributions.categorical import Categorical


CHECKPOINT_REL = (
    "python/week5_teacher_legacy032/teacher_models/"
    "legacy032_24x24_teacher_main_20260430T130208Z/stage_003000000/agent_final.pt"
)
METADATA_REL = (
    "python/week5_teacher_legacy032/teacher_models/"
    "legacy032_24x24_teacher_main_20260430T130208Z/stage_003000000/model_metadata.json"
)
MAP_REL = "maps/24x24/basesWorkers24x24.xml"
OUTPUT_DIR_REL = "python/week5_teacher_legacy032/reports/stage10d27a_visual_single_episode"

EXPECTED_OBS_SHAPE = [24, 24, 27]
EXPECTED_RAW_ACTION_NVEC = [576, 6, 4, 4, 4, 4, 7, 49]
EXPECTED_PER_CELL_ACTION_SHAPE = [576, 7]
EXPECTED_PER_CELL_BRANCH_SIZES = [6, 4, 4, 4, 4, 7, 49]
EXPECTED_ARCH = "legacy032_resolution_aware_gridnet_v1"
ACTION_TYPE_NAMES = {
    0: "noop",
    1: "move",
    2: "harvest",
    3: "return",
    4: "produce",
    5: "attack",
}


class Stage10D27AError(RuntimeError):
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
        if architecture_name != EXPECTED_ARCH:
            raise Stage10D27AError(f"Unsupported architecture_name: {architecture_name}")
        self.actor = ResolutionAwareDecoder(output_channels, target_hw=obs_hw)

    def forward(self, x):
        return self.encoder(x)

    def infer_actions(
        self,
        obs_tensor: torch.Tensor,
        action_mask: Optional[torch.Tensor],
        deterministic: bool,
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
        if deterministic:
            action_branches = [torch.argmax(c.logits, dim=1) for c in multi]
        else:
            action_branches = [c.sample() for c in multi]
        action = torch.stack(action_branches).T.view(-1, self.mapsize, len(split_sizes))
        entropy = torch.stack([c.entropy() for c in multi]).T
        return action, entropy


def repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def resolve_path(path_str: str) -> Path:
    path = Path(path_str)
    if path.is_absolute():
        return path
    return (repo_root() / path).resolve()


def json_dump(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True), encoding="utf-8")


def json_line(payload: Dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=True, sort_keys=True)


def parse_bool(value: str) -> bool:
    v = str(value).strip().lower()
    if v in {"1", "true", "yes", "y", "on"}:
        return True
    if v in {"0", "false", "no", "n", "off"}:
        return False
    raise argparse.ArgumentTypeError(f"Invalid boolean value: {value}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Stage10D27A Legacy032 3M visual single-episode eval")
    parser.add_argument("--checkpoint-path", default=CHECKPOINT_REL)
    parser.add_argument("--model-metadata-path", default=METADATA_REL)
    parser.add_argument("--map-path", default=MAP_REL)
    parser.add_argument("--output-dir", default=OUTPUT_DIR_REL)
    parser.add_argument("--seed", type=int, default=17)
    parser.add_argument("--device", default="cpu", choices=("cpu", "cuda"))
    parser.add_argument("--max-steps", type=int, default=6000)
    parser.add_argument("--num-bot-envs", type=int, default=2)
    parser.add_argument("--eval-mode", default="deterministic", choices=("deterministic", "stochastic"))
    parser.add_argument("--fps", type=int, default=8)
    parser.add_argument("--frame-every", type=int, default=1)
    parser.add_argument("--write-video", action="store_true")
    parser.add_argument("--strict-load", type=parse_bool, default=True)
    return parser.parse_args()


def load_metadata(path: Path) -> Dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise Stage10D27AError(f"Failed to load metadata: {path} ({exc})") from exc


def load_legacy032_policy_checkpoint(path: Path, device: torch.device, strict_load: bool = True) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    try:
        payload = torch.load(str(path), map_location=device)
    except Exception as exc:
        raise Stage10D27AError(f"Failed to load checkpoint: {path} ({exc})") from exc
    details = {
        "checkpoint_format": None,
        "strict_load": bool(strict_load),
        "strict_load_status": "STRICT_LOAD_ENFORCED" if strict_load else "STRICT_LOAD_OPT_OUT",
    }
    if isinstance(payload, dict) and payload.get("checkpoint_kind") == "full_training_state":
        state_dict = payload.get("agent_state_dict")
        if not isinstance(state_dict, dict):
            raise Stage10D27AError("Full training checkpoint is missing agent_state_dict")
        details["checkpoint_format"] = "full_training_checkpoint"
        return state_dict, details
    if isinstance(payload, dict) and "state_dict" in payload and isinstance(payload["state_dict"], dict):
        details["checkpoint_format"] = "wrapped_state_dict"
        return payload["state_dict"], details
    if isinstance(payload, dict):
        details["checkpoint_format"] = "weights_only_state_dict"
        return payload, details
    raise Stage10D27AError("Checkpoint payload is not state_dict-compatible.")


def validate_metadata_contract(metadata: Dict[str, Any]) -> List[int]:
    obs_shape = [int(v) for v in metadata.get("observation_space", [])]
    if obs_shape != EXPECTED_OBS_SHAPE:
        raise Stage10D27AError(
            f"Metadata observation contract mismatch. expected={EXPECTED_OBS_SHAPE}, actual={obs_shape}"
        )
    nvec = [int(v) for v in metadata.get("action_space_nvec", [])]
    if nvec != EXPECTED_RAW_ACTION_NVEC:
        raise Stage10D27AError(
            f"Metadata action nvec mismatch. expected={EXPECTED_RAW_ACTION_NVEC}, actual={nvec}"
        )
    return nvec


def build_ai2s(num_bot_envs: int):
    from gym_microrts import microrts_ai

    ai2s = [microrts_ai.coacAI for _ in range(max(0, num_bot_envs - 2))] + [
        microrts_ai.randomBiasedAI for _ in range(min(num_bot_envs, 1))
    ] + [microrts_ai.workerRushAI for _ in range(min(max(0, num_bot_envs - 1), 1))]
    if len(ai2s) < num_bot_envs:
        ai2s += [microrts_ai.coacAI for _ in range(num_bot_envs - len(ai2s))]
    return ai2s[:num_bot_envs]


def build_env(map_path: str, max_steps: int, num_bot_envs: int):
    from gym_microrts.envs.vec_env import MicroRTSGridModeVecEnv

    capped_num_bot_envs = max(1, min(2, int(num_bot_envs)))
    return MicroRTSGridModeVecEnv(
        num_selfplay_envs=0,
        num_bot_envs=capped_num_bot_envs,
        max_steps=int(max_steps),
        render_theme=2,
        ai2s=build_ai2s(capped_num_bot_envs),
        map_path=map_path,
        reward_weight=np.array([10.0, 1.0, 1.0, 0.2, 1.0, 4.0]),
    )


def normalize_mask_array(raw_mask: Any, num_envs: int, mapsize: int, mask_dim: int) -> np.ndarray:
    arr = np.asarray(raw_mask)
    if arr.ndim == 2 and arr.shape == (num_envs * mapsize, mask_dim):
        return arr.reshape(num_envs, mapsize, mask_dim)
    if arr.ndim == 3 and arr.shape == (num_envs, mapsize, mask_dim):
        return arr
    if arr.ndim == 4 and arr.shape[0] == num_envs and arr.shape[1] * arr.shape[2] == mapsize and arr.shape[3] == mask_dim:
        return arr.reshape(num_envs, mapsize, mask_dim)
    raise Stage10D27AError(f"Unexpected action mask shape: {tuple(arr.shape)}")


def read_action_mask(env: Any, num_envs: int, mapsize: int, mask_dim: int) -> Tuple[np.ndarray, str]:
    if hasattr(env, "vec_client") and hasattr(env.vec_client, "getMasks"):
        raw = env.vec_client.getMasks(0)
        return normalize_mask_array(raw, num_envs, mapsize, mask_dim), "env.vec_client.getMasks(0)"
    if hasattr(env, "get_action_mask"):
        raw = env.get_action_mask()
        return normalize_mask_array(raw, num_envs, mapsize, mask_dim), "env.get_action_mask"
    raise Stage10D27AError("Action mask unavailable from environment.")


def save_frame_png(frame: Any, path: Path) -> Tuple[bool, Optional[str]]:
    if frame is None:
        return False, "env.render() returned None"
    arr = np.asarray(frame)
    if arr.ndim < 2:
        return False, f"env.render() returned non-image shape {tuple(arr.shape)}"
    try:
        import imageio.v2 as imageio

        imageio.imwrite(path, arr)
        return True, None
    except Exception:
        pass
    try:
        from PIL import Image

        Image.fromarray(arr).save(path)
        return True, None
    except Exception as exc:
        return False, f"PNG save failed: {exc}"


def try_render_frame(env: Any, frames_dir: Path, step: int) -> Tuple[Optional[str], Optional[str], Any]:
    try:
        rendered = env.render()
    except Exception as exc:
        return None, f"env.render() failed: {type(exc).__name__}: {exc}", None

    frame_path = frames_dir / f"frame_{step:04d}.png"
    saved, reason = save_frame_png(rendered, frame_path)
    if saved:
        return str(frame_path), None, rendered
    return None, reason, rendered


def try_write_video(frames: List[np.ndarray], path: Path, fps: int) -> Tuple[Optional[str], Optional[str]]:
    if not frames:
        return None, "No frames available for video generation"
    try:
        import imageio.v2 as imageio

        imageio.mimsave(path, frames, fps=max(1, int(fps)))
        return str(path), None
    except Exception as exc:
        return None, f"Video generation unavailable: {exc}"


def try_save_replay(env: Any, output_dir: Path) -> Tuple[Optional[str], Optional[str]]:
    candidates = [
        ("saveReplay", output_dir / "stage10d27a_replay.mrt"),
        ("save_replay", output_dir / "stage10d27a_replay.mrt"),
    ]
    for method_name, replay_path in candidates:
        target = getattr(env, method_name, None)
        if callable(target):
            try:
                target(str(replay_path))
                if replay_path.exists():
                    return str(replay_path), None
                return str(replay_path), None
            except Exception as exc:
                return None, f"{method_name} failed: {exc}"
    vec_client = getattr(env, "vec_client", None)
    if vec_client is not None:
        for method_name, replay_path in candidates:
            target = getattr(vec_client, method_name, None)
            if callable(target):
                try:
                    target(str(replay_path))
                    if replay_path.exists():
                        return str(replay_path), None
                    return str(replay_path), None
                except Exception as exc:
                    return None, f"vec_client.{method_name} failed: {exc}"
    return None, "No replay save method exposed by env"


def cell_to_xy(index: int, width: int = 24) -> Tuple[int, int]:
    return int(index % width), int(index // width)


def sample_selected_actions(per_cell_action: np.ndarray, limit: int = 8) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    non_noop_indices = np.where(per_cell_action[:, 0] != 0)[0].tolist()
    for idx in non_noop_indices[:limit]:
        x, y = cell_to_xy(idx)
        rows.append(
            {
                "cell_index": int(idx),
                "x": int(x),
                "y": int(y),
                "action_type": ACTION_TYPE_NAMES.get(int(per_cell_action[idx, 0]), str(int(per_cell_action[idx, 0]))),
                "branches": [int(v) for v in per_cell_action[idx].tolist()],
            }
        )
    return rows


def observation_delta_summary(prev_obs: np.ndarray, next_obs: np.ndarray) -> Dict[str, Any]:
    diff = np.abs(next_obs.astype(np.float32) - prev_obs.astype(np.float32))
    total_diff = float(diff.sum())
    changed_cells = int((diff.sum(axis=-1) > 0.01).sum())

    prev_cell_sum = prev_obs.reshape(576, 27).sum(axis=1)
    next_cell_sum = next_obs.reshape(576, 27).sum(axis=1)
    prev_occupied = set(int(i) for i in np.where(prev_cell_sum > 1.0)[0])
    next_occupied = set(int(i) for i in np.where(next_cell_sum > 1.0)[0])

    gained_cells = sorted(next_occupied - prev_occupied)
    lost_cells = sorted(prev_occupied - next_occupied)
    movement_candidates: List[Dict[str, Any]] = []
    for lost in lost_cells[:20]:
        lx, ly = cell_to_xy(lost)
        for gained in gained_cells[:20]:
            gx, gy = cell_to_xy(gained)
            distance = abs(gx - lx) + abs(gy - ly)
            if distance == 1:
                movement_candidates.append(
                    {
                        "from_cell": int(lost),
                        "from_xy": [int(lx), int(ly)],
                        "to_cell": int(gained),
                        "to_xy": [int(gx), int(gy)],
                        "distance": int(distance),
                    }
                )
    return {
        "total_obs_diff": total_diff,
        "changed_cells_any": changed_cells,
        "cells_lost_unit": lost_cells[:10],
        "cells_gained_unit": gained_cells[:10],
        "movement_candidates_count": len(movement_candidates),
        "movement_candidates": movement_candidates[:5],
        "movement_detected": bool(movement_candidates),
    }


def detect_controllable_actor_cells(mask_np: Optional[np.ndarray]) -> Optional[List[int]]:
    if mask_np is None:
        return None
    try:
        ready = np.where(mask_np[0, :, 0] > 0)[0].tolist()
        return [int(v) for v in ready]
    except Exception:
        return None


def snapshot_board(obs_env0: np.ndarray, per_cell_action: np.ndarray, path: Path) -> str:
    occupied = obs_env0.reshape(576, 27).sum(axis=1) > 1.0
    action_type = per_cell_action[:, 0]
    lines: List[str] = []
    for y in range(24):
        chars: List[str] = []
        for x in range(24):
            idx = y * 24 + x
            if action_type[idx] == 1:
                chars.append("M")
            elif action_type[idx] == 2:
                chars.append("H")
            elif action_type[idx] == 4:
                chars.append("P")
            elif action_type[idx] == 5:
                chars.append("A")
            elif occupied[idx]:
                chars.append("U")
            else:
                chars.append(".")
        lines.append("".join(chars))
    payload = {
        "occupied_count": int(occupied.sum()),
        "board_ascii": lines,
    }
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True), encoding="utf-8")
    return str(path)


def build_markdown_report(summary: Dict[str, Any], command: str) -> str:
    lines = [
        "# STAGE10D27A LEGACY032 3M VISUAL SINGLE EPISODE",
        "",
        f"- checkpoint path: {summary['checkpoint_path']}",
        f"- metadata path: {summary['metadata_path']}",
        f"- map path: {summary['map_path']}",
        f"- seed: {summary['seed']}",
        f"- eval mode: {summary['eval_mode']}",
        f"- total steps: {summary['total_steps']}",
        f"- terminal reason: {summary.get('terminal_reason')}",
        f"- total reward: {summary['total_reward']}",
        f"- action_type distribution: {json.dumps(summary['action_type_distribution'], ensure_ascii=True)}",
        f"- non-noop action count: {summary['non_noop_action_count']}",
        f"- detected unit movement count: {summary['detected_unit_movement_count']}",
        f"- detected harvest count: {summary['detected_harvest_count']}",
        f"- detected produce count: {summary['detected_produce_count']}",
        f"- detected attack count: {summary['detected_attack_count']}",
        f"- frame directory: {summary.get('frame_directory')}",
        f"- video path: {summary.get('video_path')}",
        f"- replay path: {summary.get('replay_path')}",
        f"- visual artifact mode: {summary.get('visual_artifact_mode')}",
        f"- render unavailable reason: {summary.get('render_unavailable_reason')}",
        "",
        "Open the generated frames/video/replay and manually confirm whether the teacher visually moves/acts.",
        "",
        "## PowerShell Command",
        "```powershell",
        command,
        "```",
    ]
    return "\n".join(lines) + "\n"


def main() -> int:
    args = parse_args()

    checkpoint_path = resolve_path(args.checkpoint_path)
    metadata_path = resolve_path(args.model_metadata_path)
    map_path = args.map_path
    output_dir = resolve_path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    frames_dir = output_dir / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)

    trace_path = output_dir / "stage10d27a_action_trace.jsonl"
    summary_json_path = output_dir / "stage10d27a_visual_single_episode_summary.json"
    summary_md_path = output_dir / "STAGE10D27A_LEGACY032_3M_VISUAL_SINGLE_EPISODE.md"

    if not checkpoint_path.exists():
        raise Stage10D27AError(f"Checkpoint not found: {checkpoint_path}")
    if not metadata_path.exists():
        raise Stage10D27AError(f"Metadata not found: {metadata_path}")

    metadata = load_metadata(metadata_path)
    nvec = validate_metadata_contract(metadata)

    use_cuda = args.device == "cuda" and torch.cuda.is_available()
    device = torch.device("cuda" if use_cuda else "cpu")
    torch.manual_seed(int(args.seed))
    np.random.seed(int(args.seed))

    state_dict, checkpoint_details = load_legacy032_policy_checkpoint(
        checkpoint_path,
        device,
        strict_load=bool(args.strict_load),
    )
    policy = Legacy032Policy(
        obs_channels=EXPECTED_OBS_SHAPE[2],
        nvec=nvec,
        mapsize=EXPECTED_PER_CELL_ACTION_SHAPE[0],
        obs_hw=(EXPECTED_OBS_SHAPE[0], EXPECTED_OBS_SHAPE[1]),
        architecture_name=str(metadata.get("architecture_name", "")),
    ).to(device)
    if args.strict_load:
        policy.load_state_dict(state_dict, strict=True)
        missing, unexpected = [], []
    else:
        missing, unexpected = policy.load_state_dict(state_dict, strict=False)
    policy.eval()

    env = None
    frame_arrays: List[np.ndarray] = []
    action_type_hist: Counter = Counter()
    detected_harvest_count = 0
    detected_produce_count = 0
    detected_attack_count = 0
    detected_unit_movement_count = 0
    non_noop_action_count = 0
    total_reward = 0.0
    total_steps = 0
    terminal_reason = None
    render_unavailable_reason = None
    replay_reason = None
    visual_artifact_mode = "none"
    replay_path = None
    video_path = None
    snapshot_paths: List[str] = []
    warnings: List[str] = []

    if not args.strict_load:
        warnings.append(f"STRICT_LOAD_STATUS=STRICT_LOAD_OPT_OUT missing={len(missing)} unexpected={len(unexpected)}")
    if missing:
        warnings.append(f"Missing checkpoint keys: {len(missing)}")
    if unexpected:
        warnings.append(f"Unexpected checkpoint keys: {len(unexpected)}")

    try:
        env = build_env(map_path=map_path, max_steps=int(args.max_steps), num_bot_envs=int(args.num_bot_envs))
        env_obs_shape = [int(v) for v in env.observation_space.shape]
        env_nvec = [int(v) for v in env.action_space.nvec.tolist()]
        if env_obs_shape != EXPECTED_OBS_SHAPE:
            raise Stage10D27AError(
                f"Env observation shape mismatch. expected={EXPECTED_OBS_SHAPE}, actual={env_obs_shape}"
            )
        if env_nvec != EXPECTED_RAW_ACTION_NVEC:
            raise Stage10D27AError(
                f"Env action nvec mismatch. expected={EXPECTED_RAW_ACTION_NVEC}, actual={env_nvec}"
            )

        try:
            obs = env.reset(seed=int(args.seed))
        except TypeError:
            obs = env.reset()
        if isinstance(obs, tuple):
            obs = obs[0]
        obs = np.asarray(obs, dtype=np.float32)

        with trace_path.open("w", encoding="utf-8") as trace_handle:
            while total_steps < int(args.max_steps):
                num_envs = int(obs.shape[0])
                mask_dim = 1 + sum(EXPECTED_PER_CELL_BRANCH_SIZES)
                mask_np, mask_source = read_action_mask(env, num_envs, EXPECTED_PER_CELL_ACTION_SHAPE[0], mask_dim)
                mask_tensor = torch.as_tensor(mask_np, device=device, dtype=torch.float32)
                obs_tensor = torch.as_tensor(obs, device=device, dtype=torch.float32)

                with torch.no_grad():
                    action_torch, entropy_torch = policy.infer_actions(
                        obs_tensor=obs_tensor,
                        action_mask=mask_tensor,
                        deterministic=(args.eval_mode == "deterministic"),
                        device=device,
                    )

                action_np = action_torch.detach().cpu().numpy().astype(np.int32)
                per_cell_env0 = action_np[0]
                action_types = per_cell_env0[:, 0]
                step_counter = Counter(int(v) for v in action_types.tolist())
                action_type_hist.update(step_counter)
                detected_harvest_count += int(step_counter.get(2, 0))
                detected_produce_count += int(step_counter.get(4, 0))
                detected_attack_count += int(step_counter.get(5, 0))
                non_noop_cells = [int(i) for i in np.where(action_types != 0)[0].tolist()]
                non_noop_action_count += len(non_noop_cells)

                rendered_frame_path = None
                rendered_raw = None
                if total_steps % max(1, int(args.frame_every)) == 0:
                    rendered_frame_path, render_reason, rendered_raw = try_render_frame(env, frames_dir, total_steps)
                    if rendered_frame_path is not None:
                        visual_artifact_mode = "png_frames"
                    elif render_unavailable_reason is None:
                        render_unavailable_reason = render_reason
                    if rendered_raw is not None and rendered_frame_path is not None:
                        try:
                            frame_arrays.append(np.asarray(rendered_raw))
                        except Exception:
                            pass

                step_result = env.step(action_np)
                if len(step_result) == 4:
                    next_obs, reward_arr, done_arr, info_arr = step_result
                    trunc_arr = np.zeros_like(done_arr)
                else:
                    next_obs, reward_arr, done_arr, trunc_arr, info_arr = step_result

                reward_scalar = float(np.asarray(reward_arr).reshape(-1)[0])
                done_scalar = bool(np.asarray(done_arr).reshape(-1)[0])
                trunc_scalar = bool(np.asarray(trunc_arr).reshape(-1)[0])
                info_payload = info_arr[0] if isinstance(info_arr, (list, tuple)) and len(info_arr) > 0 else info_arr

                next_obs = np.asarray(next_obs, dtype=np.float32)
                delta = observation_delta_summary(obs[0], next_obs[0])
                if delta["movement_detected"]:
                    detected_unit_movement_count += 1

                controllable_actor_cells = detect_controllable_actor_cells(mask_np)
                trace_entry = {
                    "step": int(total_steps),
                    "reward": reward_scalar,
                    "done": bool(done_scalar or trunc_scalar),
                    "action_type_counts_all_cells": {
                        ACTION_TYPE_NAMES.get(int(k), str(int(k))): int(v)
                        for k, v in sorted(step_counter.items())
                    },
                    "non_noop_cells_count": int(len(non_noop_cells)),
                    "non_noop_cells_sample": [
                        {"cell_index": int(idx), "x": int(cell_to_xy(idx)[0]), "y": int(cell_to_xy(idx)[1])}
                        for idx in non_noop_cells[:8]
                    ],
                    "controllable_actor_cells": controllable_actor_cells,
                    "action_mask_available": True,
                    "action_mask_source": mask_source,
                    "selected_action_examples": sample_selected_actions(per_cell_env0),
                    "observation_state_delta_summary": delta,
                    "rendered_frame_path": rendered_frame_path,
                }
                trace_handle.write(json_line(trace_entry) + "\n")

                if rendered_frame_path is None:
                    snapshot_path = output_dir / f"snapshot_step_{total_steps:04d}.json"
                    snapshot_paths.append(snapshot_board(next_obs[0], per_cell_env0, snapshot_path))

                total_reward += reward_scalar
                total_steps += 1
                obs = next_obs

                if done_scalar or trunc_scalar:
                    if isinstance(info_payload, dict):
                        terminal_reason = info_payload.get("terminal_reason") or info_payload.get("terminal_type")
                    if terminal_reason is None:
                        terminal_reason = "truncated" if trunc_scalar else "done"
                    break

            if terminal_reason is None and total_steps >= int(args.max_steps):
                terminal_reason = "max_steps_reached"

        replay_path, replay_reason = try_save_replay(env, output_dir)
        if replay_path is not None and visual_artifact_mode == "none":
            visual_artifact_mode = "replay"
    finally:
        if env is not None:
            try:
                env.close()
            except Exception:
                pass

    if args.write_video:
        video_path, video_reason = try_write_video(frame_arrays, output_dir / "stage10d27a_episode.mp4", int(args.fps))
        if video_path is None:
            warnings.append(video_reason)
        elif visual_artifact_mode == "png_frames":
            visual_artifact_mode = "png_frames+video"

    if visual_artifact_mode == "none" and snapshot_paths:
        visual_artifact_mode = "snapshot_json_fallback"
        if render_unavailable_reason is None:
            render_unavailable_reason = "Rendering unavailable; wrote board snapshots instead"

    action_type_distribution = {
        ACTION_TYPE_NAMES.get(int(k), str(int(k))): int(v) for k, v in sorted(action_type_hist.items())
    }

    summary = {
        "schema": "stage10d27a_legacy032_visual_single_episode.v1",
        "generated_at_utc": utc_now(),
        "checkpoint_path": str(checkpoint_path),
        "metadata_path": str(metadata_path),
        "map_path": map_path,
        "seed": int(args.seed),
        "eval_mode": args.eval_mode,
        "device": str(device),
        "num_bot_envs_effective": int(max(1, min(2, int(args.num_bot_envs)))),
        "total_steps": int(total_steps),
        "terminal_reason": terminal_reason,
        "total_reward": float(total_reward),
        "action_type_distribution": action_type_distribution,
        "non_noop_action_count": int(non_noop_action_count),
        "detected_unit_movement_count": int(detected_unit_movement_count),
        "detected_harvest_count": int(detected_harvest_count),
        "detected_produce_count": int(detected_produce_count),
        "detected_attack_count": int(detected_attack_count),
        "frame_directory": str(frames_dir),
        "video_path": video_path,
        "replay_path": replay_path,
        "snapshot_paths": snapshot_paths,
        "visual_artifact_mode": visual_artifact_mode,
        "render_unavailable_reason": render_unavailable_reason,
        "replay_unavailable_reason": replay_reason,
        "warnings": warnings,
        "manual_review_instruction": "Open the generated frames/video/replay and manually confirm whether the teacher visually moves/acts.",
    }
    json_dump(summary_json_path, summary)

    command = (
        f"c:/Projects/UnityRTSPrototype/UnityRTSPrototype/.venv/Scripts/python.exe "
        f"python/week5_teacher_legacy032/scripts/run_legacy032_3m_visual_single_episode.py "
        f"--checkpoint-path {CHECKPOINT_REL} --model-metadata-path {METADATA_REL} "
        f"--map-path {MAP_REL} --eval-mode {args.eval_mode} --seed {args.seed} --device {args.device}"
    )
    summary_md_path.write_text(build_markdown_report(summary, command), encoding="utf-8")

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Stage10D27AError as exc:
        print(f"[stage10d27a] ERROR: {exc}")
        raise SystemExit(1)
    except Exception as exc:
        print(f"[stage10d27a] UNHANDLED: {exc}\n{traceback.format_exc()}")
        raise SystemExit(1)