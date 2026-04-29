from __future__ import annotations

import argparse
import json
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np
import torch
import torch.nn as nn
from torch.distributions.categorical import Categorical

EXPECTED_OBS = [24, 24, 27]
GLOBAL_SINGLE_ACTION_24X24_NVEC = [576, 6, 4, 4, 4, 4, 7, 576]
GRIDMODE_24X24_NVEC = [576, 6, 4, 4, 4, 4, 7, 49]
UNITY_V2_BRANCH_SIZES = [6, 4, 4, 4, 4, 7, 49]


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
            # Resolution-aware head: explicit resize to env HxW, avoiding silent crop.
            x = torch.nn.functional.interpolate(x, size=self.target_hw, mode="bilinear", align_corners=False)
        x = self.final_conv(x)
        return x.permute(0, 2, 3, 1)


class Legacy032Policy(nn.Module):
    def __init__(self, obs_channels: int, nvec: List[int], mapsize: int, target_hw: Tuple[int, int]):
        super().__init__()
        self.mapsize = mapsize
        self.nvec = nvec
        self.encoder = Encoder(obs_channels)
        self.actor = ResolutionAwareDecoder(int(sum(nvec[1:])), target_hw=target_hw)

    def forward(self, obs: torch.Tensor) -> torch.Tensor:
        return self.encoder(obs)

    def sample_action(self, obs: torch.Tensor, raw_masks: np.ndarray, device: torch.device):
        logits = self.actor(self.forward(obs))
        split_sizes = self.nvec[1:]
        flat_logits = logits.reshape(-1, int(sum(split_sizes)))
        split_logits = torch.split(flat_logits, split_sizes, dim=1)

        mask_tensor = torch.tensor(raw_masks, dtype=torch.float32, device=device)
        mask_tensor = mask_tensor.view(-1, mask_tensor.shape[-1])
        split_masks = torch.split(mask_tensor[:, 1:], split_sizes, dim=1)

        cats = [CategoricalMasked(logits=sl, masks=sm) for sl, sm in zip(split_logits, split_masks)]
        sampled = torch.stack([c.sample() for c in cats])
        action = sampled.T.view(-1, self.mapsize, len(split_sizes))
        return action, logits


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify Stage 4 legacy032 24x24 training contract.")
    parser.add_argument("--map-path", default="maps/24x24/basesWorkers24x24.xml")
    parser.add_argument("--num-bot-envs", type=int, default=6)
    parser.add_argument("--num-selfplay-envs", type=int, default=0)
    parser.add_argument("--seed", type=int, default=17)
    parser.add_argument(
        "--output-json",
        default="python/week5_teacher_legacy032/reports/stage4r_24x24_contract_probe.json",
    )
    return parser.parse_args()


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


def _main() -> int:
    args = _parse_args()
    repo_root = _repo_root()
    out_path = Path(args.output_json)
    if not out_path.is_absolute():
        out_path = (repo_root / out_path).resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)

    report: Dict[str, Any] = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": "INCONCLUSIVE_NEEDS_MANUAL_CHECK",
        "representation_mode": "MICRORTS_GRIDMODE_PER_CELL",
        "map_path": args.map_path,
        "expected_observation_space": EXPECTED_OBS,
        "expected_gridmode_nvec": GRIDMODE_24X24_NVEC,
        "global_single_action_nvec_reference": GLOBAL_SINGLE_ACTION_24X24_NVEC,
        "unity_v2_branch_sizes": UNITY_V2_BRANCH_SIZES,
        "gridmode_attack_target_semantics": "local_7x7_49",
        "contract_gridmode_matches_expected": False,
        "observation_space": None,
        "observed_nvec": None,
        "action_space_nvec": None,
        "mapsize": None,
        "mask_available": False,
        "mask_source": None,
        "mask_shape": None,
        "policy_forward_ok": False,
        "masked_action_sample_ok": False,
        "env_step_ok": False,
        "policy_actor_output_shape": None,
        "errors": [],
        "warnings": [],
    }

    env = None
    device = torch.device("cpu")

    try:
        from gym_microrts.envs.vec_env import MicroRTSGridModeVecEnv

        np.random.seed(args.seed)
        torch.manual_seed(args.seed)

        env = MicroRTSGridModeVecEnv(
            num_selfplay_envs=args.num_selfplay_envs,
            num_bot_envs=args.num_bot_envs,
            max_steps=2000,
            render_theme=2,
            ai2s=_build_ai2s(args.num_bot_envs),
            map_path=args.map_path,
            reward_weight=np.array([10.0, 1.0, 1.0, 0.2, 1.0, 4.0]),
        )

        obs_shape = [int(x) for x in env.observation_space.shape]
        nvec = [int(x) for x in env.action_space.nvec.tolist()]
        report["observation_space"] = obs_shape
        report["observed_nvec"] = nvec
        report["action_space_nvec"] = nvec
        report["mapsize"] = int(obs_shape[0] * obs_shape[1])

        obs_ok = obs_shape == EXPECTED_OBS
        nvec_ok = nvec == GRIDMODE_24X24_NVEC
        report["contract_gridmode_matches_expected"] = bool(nvec_ok)

        if not nvec_ok:
            report["status"] = "BLOCKED_CONTRACT_MISMATCH"
            report["errors"].append(
                f"action_space.nvec mismatch: expected={GRIDMODE_24X24_NVEC}, actual={nvec}"
            )

        if not obs_ok:
            report["status"] = "BLOCKED_CONTRACT_MISMATCH"
            report["errors"].append(
                f"observation_space mismatch: expected={EXPECTED_OBS}, actual={obs_shape}"
            )

        obs = env.reset()
        raw_masks = np.array(env.vec_client.getMasks(0))
        report["mask_available"] = True
        report["mask_source"] = "env.vec_client.getMasks(0)"
        report["mask_shape"] = [int(x) for x in raw_masks.shape]

        policy = Legacy032Policy(
            obs_channels=obs_shape[2],
            nvec=nvec,
            mapsize=int(obs_shape[0] * obs_shape[1]),
            target_hw=(obs_shape[0], obs_shape[1]),
        ).to(device)

        obs_t = torch.tensor(obs, dtype=torch.float32, device=device)

        with torch.no_grad():
            action_t, logits_t = policy.sample_action(obs_t, raw_masks=raw_masks, device=device)
            report["policy_actor_output_shape"] = [int(x) for x in logits_t.shape]
            report["policy_forward_ok"] = True
            report["masked_action_sample_ok"] = True

        # 1-5 masked eval steps without training
        action_np = action_t.detach().cpu().numpy().astype(np.int32)
        step_ok = False
        for _ in range(5):
            step_result = env.step(action_np)
            if len(step_result) not in (4, 5):
                raise RuntimeError(f"Unexpected step tuple length: {len(step_result)}")
            step_ok = True
        report["env_step_ok"] = step_ok

        if report["policy_actor_output_shape"][1:3] != obs_shape[:2]:
            report["status"] = "BLOCKED_POLICY_ARCHITECTURE_SHAPE"
            report["errors"].append(
                "Encoder/decoder actor output HxW does not match env observation HxW;"
                " this architecture cannot be used safely for target map without structural fix."
            )
            report["warnings"].append(
                "Minimal fix: use resolution-aware encoder/decoder (adaptive pooling and/or resize head) so actor output exactly matches map HxW."
            )

        if report["status"] not in {"BLOCKED_CONTRACT_MISMATCH", "BLOCKED_POLICY_ARCHITECTURE_SHAPE"}:
            if (
                report["mask_available"]
                and report["policy_forward_ok"]
                and report["masked_action_sample_ok"]
                and report["env_step_ok"]
                and obs_ok
                and nvec_ok
            ):
                report["status"] = "PASS"
            else:
                report["status"] = "INCONCLUSIVE_NEEDS_MANUAL_CHECK"

    except Exception as exc:
        report["errors"].append(f"Probe failed: {exc}")
        report["errors"].append(traceback.format_exc())
        if report.get("status") == "INCONCLUSIVE_NEEDS_MANUAL_CHECK":
            report["status"] = "BLOCKED_POLICY_ARCHITECTURE_SHAPE"
    finally:
        if env is not None:
            try:
                env.close()
            except Exception:
                pass

    out_path.write_text(json.dumps(report, indent=2, ensure_ascii=True), encoding="utf-8")
    print(json.dumps({"status": report["status"], "output_json": str(out_path)}, indent=2))

    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(_main())
