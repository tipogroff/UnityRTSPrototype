#!/usr/bin/env python3
"""Gridnet teacher rollout exporter.

Exports trajectories from a Branch B Gridnet checkpoint into the Day 3 raw
batch format consumed by python/week5_teacher/adapt_teacher_dataset.py
(day4_dataset_adapter.py).

Output layout:
  <output-dir>/<batch-label>/
    episode_00000.npz    (raw per-episode arrays, adapter-compatible)
    episode_00000.jsonl  (optional debug, one JSON line per step)
    batch.summary.json   (adapter contract — must contain batch_name, policy_source_id, ...)
    rollout_summary.json (exporter-native detail)
    rollout_summary.md

JPype / JVM limitation: a single Python process cannot restart the JVM.
Therefore per_episode opponent sampling across episodes is not supported.
The exporter uses a single env for all episodes (static opponent).
This is documented in batch.summary.json under notes.
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import torch

from gridnet_model import Agent


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ACTION_NAMES = {
    0: "NoOp",
    1: "Move",
    2: "Harvest",
    3: "Return",
    4: "Produce",
    5: "Attack",
}

MAPSIZE = 576  # 24 × 24


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=(
            "Export Gridnet teacher rollouts into Day 3 raw batch format "
            "for downstream adapt_teacher_dataset.py."
        )
    )
    p.add_argument("--checkpoint", type=Path, required=True)
    p.add_argument("--model-metadata", type=Path, required=True)
    p.add_argument("--episodes", type=int, default=8)
    p.add_argument("--max-steps", type=int, default=512)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--map-path", default="maps/24x24/basesWorkers24x24.xml")
    p.add_argument(
        "--opponent-pool",
        default="randomBiasedAI",
        help="Comma-separated opponents. Due to JVM limitation only the first is used.",
    )
    p.add_argument(
        "--opponent-sampling",
        choices=("static", "per_episode"),
        default="static",
        help="Only 'static' is supported in single-process mode (JVM restart limitation).",
    )
    p.add_argument(
        "--deterministic",
        choices=("true", "false"),
        default="true",
        help="true=argmax, false=sample from masked categorical.",
    )
    p.add_argument("--device", default="cpu")
    p.add_argument("--output-dir", type=Path, required=True,
                   help="Parent directory; batch is written to <output-dir>/<batch-label>/.")
    p.add_argument(
        "--batch-label",
        default=None,
        help="Batch subdirectory name. Auto-generated if omitted.",
    )
    p.add_argument("--write-debug-jsonl", action="store_true")
    return p.parse_args()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def utc_compact() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=True)


def load_agent(checkpoint: Path, metadata_path: Path,
               device: torch.device) -> Tuple[Agent, Dict[str, Any]]:
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    obs_shape = tuple(int(v) for v in metadata["observation_shape"])
    action_nvec = [int(v) for v in metadata["action_nvec"]]
    agent = Agent(obs_shape, action_nvec).to(device)
    state_dict = torch.load(checkpoint, map_location=device)
    agent.load_state_dict(state_dict)
    agent.eval()
    return agent, metadata


def build_env(map_path: str, max_steps: int, opponent_name: str) -> Any:
    from gym_microrts import microrts_ai
    from gym_microrts.envs.vec_env import MicroRTSGridModeVecEnv
    opponent = getattr(microrts_ai, opponent_name, None)
    if opponent is None:
        raise RuntimeError(f"Unknown opponent: '{opponent_name}'")
    return MicroRTSGridModeVecEnv(
        num_selfplay_envs=0,
        num_bot_envs=1,
        ai2s=[opponent],
        map_paths=[map_path],
        max_steps=max_steps,
        autobuild=False,
    )


def read_action_mask(env: Any) -> np.ndarray:
    if hasattr(env, "get_action_mask"):
        action_mask = np.asarray(env.get_action_mask())
        source_mask = np.asarray(env.source_unit_mask).reshape(
            action_mask.shape[0], action_mask.shape[1], 1
        )
        return np.concatenate([source_mask, action_mask], axis=2)
    if hasattr(env, "vec_client") and hasattr(env.vec_client, "getMasks"):
        raw = np.asarray(env.vec_client.getMasks(0))
    elif hasattr(env, "action_masks"):
        maybe = getattr(env, "action_masks")
        raw = np.asarray(maybe() if callable(maybe) else maybe)
    else:
        raise RuntimeError("No action mask provider on environment.")
    if raw.ndim == 4:
        n, h, w, k = raw.shape
        return raw.reshape(n, h * w, k)
    if raw.ndim == 3:
        return raw
    raise RuntimeError(f"Unexpected action mask shape: {tuple(raw.shape)}")


# ---------------------------------------------------------------------------
# Rollout
# ---------------------------------------------------------------------------

def run_episode(
    episode_id: int,
    agent: Agent,
    env: Any,
    max_steps: int,
    device: torch.device,
    deterministic: bool,
    write_debug_jsonl: bool,
    batch_dir: Path,
) -> Dict[str, Any]:
    """Run one episode and write episode_<id>.npz (+ optional .jsonl)."""
    step_observations: List[np.ndarray] = []
    step_actions: List[np.ndarray] = []
    step_rewards: List[float] = []
    step_dones: List[bool] = []
    step_ids: List[int] = []
    step_masks: List[np.ndarray] = []  # stored for provenance, not required by adapter
    debug_lines: List[Dict[str, Any]] = []

    action_counter: Counter = Counter()

    obs = np.asarray(env.reset(), dtype=np.float32)
    done = False
    step_id = 0

    while not done and step_id < max_steps:
        obs_t = torch.as_tensor(obs, device=device, dtype=torch.float32)
        mask_np = read_action_mask(env)
        mask_t = torch.as_tensor(mask_np, device=device)

        with torch.no_grad():
            action_t, _lp, _ent, _used_mask = agent.get_action(
                obs_t,
                invalid_action_masks=mask_t,
                action=None,
                deterministic=deterministic,
            )

        # obs per step: [1, H, W, C] → [H, W, C]
        obs_step = obs[0].astype(np.float32)  # (24, 24, 27)

        # action per step: [1, H*W, 7] → [H*W, 7]  ← matrix_576x7: adapter supported_exact
        action_step = action_t[0].detach().cpu().numpy().astype(np.int64)  # (576, 7)

        # mask per step: [1, H*W, 1+78] → [H*W, 79]
        mask_step = mask_np[0].astype(np.uint8)  # (576, 79)

        action_env = action_t.detach().cpu().numpy().astype(np.int32)
        next_obs, reward_arr, done_arr, info_arr = env.step(action_env)
        reward = float(np.asarray(reward_arr).reshape(-1)[0])
        done = bool(np.asarray(done_arr).reshape(-1)[0])

        step_observations.append(obs_step)
        step_actions.append(action_step)
        step_rewards.append(reward)
        step_dones.append(done)
        step_ids.append(step_id)
        step_masks.append(mask_step)

        action_types = action_step[:, 0]
        action_counter.update(int(v) for v in action_types.tolist())

        if write_debug_jsonl:
            debug_lines.append({
                "episode_id": episode_id,
                "step_id": step_id,
                "reward": reward,
                "done": done,
                "action_type_counts": {
                    ACTION_NAMES.get(k, str(k)): int(v)
                    for k, v in sorted(
                        Counter(int(v) for v in action_types.tolist()).items()
                    )
                },
            })

        obs = np.asarray(next_obs, dtype=np.float32)
        step_id += 1

    # Write npz — layout matches what day4_dataset_adapter.adapt_episode() reads.
    npz_path = batch_dir / f"episode_{episode_id:05d}.npz"
    np.savez_compressed(
        npz_path,
        episode_id=np.asarray([episode_id], dtype=np.int64),
        step_id=np.asarray(step_ids, dtype=np.int64),
        observation_t=np.stack(step_observations, axis=0),   # (T, 24, 24, 27)
        action_t=np.stack(step_actions, axis=0),              # (T, 576, 7)
        reward_t=np.asarray(step_rewards, dtype=np.float32),
        done_t=np.asarray(step_dones, dtype=np.bool_),
        action_mask_t=np.stack(step_masks, axis=0),           # (T, 576, 79) – provenance
    )

    if write_debug_jsonl:
        jsonl_path = batch_dir / f"episode_{episode_id:05d}.jsonl"
        with jsonl_path.open("w", encoding="utf-8") as fh:
            for line in debug_lines:
                fh.write(json.dumps(line, ensure_ascii=True) + "\n")

    episode_return = float(sum(step_rewards))
    return {
        "episode_id": episode_id,
        "steps": step_id,
        "episode_return": episode_return,
        "done": done,
        "action_type_counts": {
            ACTION_NAMES.get(k, str(k)): int(v)
            for k, v in sorted(action_counter.items())
        },
        "npz_path": str(npz_path),
    }


# ---------------------------------------------------------------------------
# Output writers
# ---------------------------------------------------------------------------

def write_batch_summary(
    path: Path,
    batch_name: str,
    batch_label: str,
    batch_dir: Path,
    checkpoint: Path,
    metadata: Dict[str, Any],
    opponent: str,
    deterministic: bool,
    map_path: str,
    seed: int,
    episodes_meta: List[Dict[str, Any]],
    timestamp_compact: str,
) -> None:
    """Write batch.summary.json in the format expected by day4_dataset_adapter."""
    total_steps = sum(e["steps"] for e in episodes_meta)
    returns = [e["episode_return"] for e in episodes_meta]
    mean_return = float(np.mean(returns)) if returns else 0.0
    std_return = float(np.std(returns)) if returns else 0.0
    mean_len = float(np.mean([e["steps"] for e in episodes_meta])) if episodes_meta else 0.0

    # Build action surface histogram in the same style as existing batches
    action_hist: Counter = Counter()
    for ep in episodes_meta:
        for atype, cnt in ep.get("action_type_counts", {}).items():
            action_hist[atype] += cnt

    all_npz = [ep["npz_path"] for ep in episodes_meta]
    all_jsonl = [
        str(batch_dir / f"episode_{ep['episode_id']:05d}.jsonl")
        for ep in episodes_meta
        if (batch_dir / f"episode_{ep['episode_id']:05d}.jsonl").exists()
    ]

    payload: Dict[str, Any] = {
        "timestamp_utc": timestamp_compact,
        "status": "success",
        "batch_name": batch_name,
        "batch_mode": "gridnet_teacher_rollout",
        "batch_label": batch_label,
        "format": {
            "primary": "npz",
            "debug": "jsonl" if all_jsonl else "none",
        },
        # Provenance — identifies this as a Gridnet Branch B export
        "policy_source_id": f"gridnet_branchB:{checkpoint.name}",
        "checkpoint_path": str(checkpoint),
        "checkpoint_name": checkpoint.name,
        "deterministic_mode": deterministic,
        "action_nvec": metadata.get("action_nvec"),
        "observation_shape": metadata.get("observation_shape"),
        # env info
        "env_id": "MicroRTSGridModeVecEnv_gridnet",
        "map_path": map_path,
        "opponent": opponent,
        "opponent_sampling_mode": "static",
        "jvm_limitation_note": (
            "Per-episode opponent sampling not supported in single-process mode "
            "due to JPype JVM restart limitation. Single fixed opponent used for all episodes."
        ),
        "seed_metadata": {
            "rollout_seed": seed,
        },
        # Action layout declared explicitly for adapter
        "action_layout_declared": "matrix_576x7",
        "action_layout_adapter_support": "supported_exact",
        "source_action_branch_sizes": metadata.get("action_nvec", [576, 6, 4, 4, 4, 4, 7, 49])[1:],
        # Batch stats
        "batch_statistics": {
            "episodes": len(episodes_meta),
            "steps": total_steps,
            "mean_episode_length": mean_len,
            "mean_episode_return": mean_return,
            "std_episode_return": std_return,
            "reward_mean": mean_return,
            "reward_std": std_return,
            "action_type_counts": {
                k: int(v) for k, v in sorted(action_hist.items())
            },
        },
        "artifacts": {
            "batch_dir": str(batch_dir),
            "npz_files": all_npz,
            "jsonl_files": all_jsonl,
        },
        "notes": [
            "Raw Gridnet Branch B rollout; no Gym->Unity remap applied here.",
            "action_t per step is shape (576, 7) — matrix_576x7 layout (supported_exact by day4_dataset_adapter).",
            "observation_t per step is shape (24, 24, 27) — no spatial transforms applied.",
            "action_mask_t is stored for provenance only; day4_dataset_adapter ignores it.",
            "Use adapt_teacher_dataset.py to convert to Unity-contract-aligned adapted batch.",
            "Semantic weakening expected: source produce branch has 7 entries vs Unity 4; attack target 49 vs 9.",
        ],
    }
    write_json(path, payload)


def write_rollout_summary(
    json_path: Path,
    md_path: Path,
    batch_name: str,
    batch_dir: Path,
    checkpoint: Path,
    metadata: Dict[str, Any],
    opponent: str,
    deterministic: bool,
    episodes_meta: List[Dict[str, Any]],
    total_steps: int,
    timestamp: str,
) -> None:
    """Write rollout_summary.json/md — exporter-native detail."""
    all_action_counts: Counter = Counter()
    for ep in episodes_meta:
        for atype, cnt in ep.get("action_type_counts", {}).items():
            all_action_counts[atype] += cnt

    action_total = sum(all_action_counts.values())
    move_share = all_action_counts.get("Move", 0) / max(action_total, 1)
    noop_share = all_action_counts.get("NoOp", 0) / max(action_total, 1)

    payload: Dict[str, Any] = {
        "schema": "gridnet_rollout_export.v1",
        "timestamp_utc": timestamp,
        "batch_name": batch_name,
        "batch_dir": str(batch_dir),
        "checkpoint": str(checkpoint),
        "opponent": opponent,
        "deterministic_mode": deterministic,
        "episodes": len(episodes_meta),
        "total_steps": total_steps,
        "action_type_distribution": {k: int(v) for k, v in sorted(all_action_counts.items())},
        "move_share": move_share,
        "noop_share_full_grid": noop_share,
        "per_episode": episodes_meta,
    }
    write_json(json_path, payload)

    lines = [
        "# Gridnet Teacher Rollout Export Summary",
        "",
        f"- batch_name: {batch_name}",
        f"- checkpoint: {checkpoint.name}",
        f"- deterministic_mode: {deterministic}",
        f"- opponent: {opponent}",
        f"- episodes: {len(episodes_meta)}",
        f"- total_steps: {total_steps}",
        "",
        "## Action Distribution (full grid)",
        "",
    ]
    for atype, cnt in sorted(all_action_counts.items()):
        share = cnt / max(action_total, 1)
        lines.append(f"- {atype}: {cnt} ({share:.4f})")
    lines += [
        "",
        "## Per-Episode",
        "",
        "| episode | steps | return | done |",
        "|---------|-------|--------|------|",
    ]
    for ep in episodes_meta:
        lines.append(
            f"| {ep['episode_id']} | {ep['steps']} | {ep['episode_return']:.3f} | {ep['done']} |"
        )
    lines += [
        "",
        "## Notes",
        "- action_t shape per step: (576, 7) — matrix_576x7, supported_exact by adapter.",
        "- observation_t shape per step: (24, 24, 27).",
        "- Run adapt_teacher_dataset.py on this batch dir for Unity-contract-aligned output.",
        "- Semantic weakening expected: Gridnet produce branch=7, attack branch=49 vs Unity 4/9.",
    ]
    md_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    args = parse_args()

    checkpoint = args.checkpoint.resolve()
    metadata_path = args.model_metadata.resolve()

    if not checkpoint.is_file():
        print(f"[export] ERROR: checkpoint not found: {checkpoint}", file=sys.stderr)
        sys.exit(1)
    if not metadata_path.is_file():
        print(f"[export] ERROR: model_metadata not found: {metadata_path}", file=sys.stderr)
        sys.exit(1)

    deterministic = args.deterministic != "false"
    timestamp = utc_now()
    timestamp_compact = utc_compact()

    # Batch name
    det_tag = "det" if deterministic else "stoch"
    batch_label = args.batch_label or f"gridnet_export_{det_tag}_{timestamp_compact}"
    batch_dir = args.output_dir.resolve() / batch_label
    batch_dir.mkdir(parents=True, exist_ok=True)

    device = torch.device(
        "cuda" if torch.cuda.is_available() and args.device.lower() == "cuda" else "cpu"
    )

    print(f"[export] Checkpoint  : {checkpoint}")
    print(f"[export] Batch dir   : {batch_dir}")
    print(f"[export] Episodes    : {args.episodes}, max_steps={args.max_steps}")
    print(f"[export] Deterministic: {deterministic}")

    agent, metadata = load_agent(checkpoint, metadata_path, device)

    # Parse opponent pool; use first due to JVM limitation
    pool = [o.strip() for o in args.opponent_pool.split(",") if o.strip()]
    if not pool:
        print("[export] ERROR: empty opponent pool.", file=sys.stderr)
        sys.exit(1)
    opponent = pool[0]
    if args.opponent_sampling == "per_episode" and len(pool) > 1:
        print(
            f"[export] WARNING: per_episode sampling requested but JVM cannot restart. "
            f"Using fixed opponent '{opponent}'.",
            file=sys.stderr,
        )

    random.seed(args.seed)
    np.random.seed(args.seed)
    torch.manual_seed(args.seed)

    env = build_env(args.map_path, args.max_steps, opponent)
    episodes_meta: List[Dict[str, Any]] = []

    try:
        for ep_id in range(args.episodes):
            print(f"[export]   episode {ep_id+1}/{args.episodes} ...", end="", flush=True)
            ep_meta = run_episode(
                episode_id=ep_id,
                agent=agent,
                env=env,
                max_steps=args.max_steps,
                device=device,
                deterministic=deterministic,
                write_debug_jsonl=args.write_debug_jsonl,
                batch_dir=batch_dir,
            )
            episodes_meta.append(ep_meta)
            print(
                f" steps={ep_meta['steps']}, return={ep_meta['episode_return']:.2f}, "
                f"done={ep_meta['done']}"
            )
    finally:
        env.close()

    total_steps = sum(e["steps"] for e in episodes_meta)

    # batch.summary.json — adapter contract
    write_batch_summary(
        path=batch_dir / "batch.summary.json",
        batch_name=batch_label,
        batch_label=batch_label,
        batch_dir=batch_dir,
        checkpoint=checkpoint,
        metadata=metadata,
        opponent=opponent,
        deterministic=deterministic,
        map_path=args.map_path,
        seed=args.seed,
        episodes_meta=episodes_meta,
        timestamp_compact=timestamp_compact,
    )

    # rollout_summary.json/md — exporter native
    write_rollout_summary(
        json_path=batch_dir / "rollout_summary.json",
        md_path=batch_dir / "rollout_summary.md",
        batch_name=batch_label,
        batch_dir=batch_dir,
        checkpoint=checkpoint,
        metadata=metadata,
        opponent=opponent,
        deterministic=deterministic,
        episodes_meta=episodes_meta,
        total_steps=total_steps,
        timestamp=timestamp,
    )

    print(f"[export] Done. Total steps: {total_steps}")
    print(f"[export] Batch dir: {batch_dir}")
    print(f"[export] batch.summary.json: {batch_dir / 'batch.summary.json'}")
    print(f"[export] rollout_summary.json: {batch_dir / 'rollout_summary.json'}")


if __name__ == "__main__":
    main()
