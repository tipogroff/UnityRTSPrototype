#!/usr/bin/env python3
"""Resume teacher training from a checkpoint."""

import argparse
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from run_teacher_rollout import (
    RolloutError,
    SeedBundle,
    build_environment,
    import_runtime_modules,
    seed_process,
)
from train_teacher_smoke import wrap_legacy_vec_env_for_sb3, configure_logger, build_seed_bundle


def resume_training(
    checkpoint_path: Path,
    output_root: Path,
    total_additional_timesteps: int,
    num_bot_envs: int = 4,
    checkpoint_interval: int = 20000,
    device: str = "cuda",
    env_id: str = "MicrortsSelfPlayShapedReward-v1",
    map_path: str = "maps/24x24/basesWorkers24x24.xml",
    seed: int = 17,
    learning_rate: float = 1e-4,
    n_epochs: int = 2,
    batch_size: int = 256,
    target_kl: float = 0.01,
    max_grad_norm: float = 0.3,
    clip_range: float = 0.1,
    progress_log_interval: int = 2048,
) -> Path:
    """Resume training from checkpoint."""
    
    if not checkpoint_path.exists():
        raise FileNotFoundError(f"Checkpoint not found: {checkpoint_path}")
    
    output_root = output_root.resolve()
    models_dir = output_root / "teacher_models"
    logs_dir = output_root / "teacher_logs"
    
    models_dir.mkdir(parents=True, exist_ok=True)
    logs_dir.mkdir(parents=True, exist_ok=True)
    
    run_timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_label = f"resume_{run_timestamp}"
    log_path = logs_dir / f"{run_label}.log"
    logger = configure_logger(log_path)
    
    logger.info(f"Resuming training from checkpoint: {checkpoint_path}")
    logger.info(f"Additional timesteps to train: {total_additional_timesteps}")
    logger.info(
        "Resume tuning: lr=%s n_epochs=%s batch_size=%s target_kl=%s max_grad_norm=%s clip_range=%s progress_log_interval=%s",
        learning_rate,
        n_epochs,
        batch_size,
        target_kl,
        max_grad_norm,
        clip_range,
        progress_log_interval,
    )
    
    modules, versions = import_runtime_modules()
    sb3_module = modules.get("stable_baselines3")
    if sb3_module is None:
        raise RolloutError("Stable-Baselines3 is not installed.")
    
    seed_bundle = build_seed_bundle(argparse.Namespace(
        seed=seed, env_seed=None, rollout_seed=None
    ))
    seed_process(seed_bundle, modules)
    
    # Build environment
    env_args = argparse.Namespace(
        env_id=env_id,
        map_path=map_path,
        rollout_step_limit=2000,
        num_bot_envs=num_bot_envs,
    )
    
    env, initial_observation, reset_info, env_summary = build_environment(
        args=env_args,
        seed_bundle=seed_bundle,
        modules=modules,
        logger=logger,
    )
    
    env_for_training = wrap_legacy_vec_env_for_sb3(env)
    
    logger.info(f"Loaded environment: {env_id}, num_envs={env_for_training.num_envs}")
    
    # Load model from checkpoint
    ppo_class = sb3_module.PPO
    model = ppo_class.load(
        str(checkpoint_path),
        env=env_for_training,
        device=device,
        print_system_info=False,
    )

    # Stabilize resumed training and reduce optimizer work per rollout.
    model.learning_rate = learning_rate
    model.lr_schedule = lambda _: learning_rate
    model.n_epochs = int(n_epochs)
    model.batch_size = int(batch_size)
    model.target_kl = float(target_kl)
    model.max_grad_norm = float(max_grad_norm)
    model.clip_range = lambda _: float(clip_range)
    
    logger.info(f"Model loaded from checkpoint. Current timesteps: {model.num_timesteps}")
    
    # Setup checkpoint directory
    checkpoint_dir_parent = checkpoint_path.parent.parent
    checkpoint_dir = checkpoint_dir_parent / "checkpoints"
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    
    # Callback for periodic checkpoints
    class PeriodicCheckpointCallback(sb3_module.common.callbacks.BaseCallback):
        def __init__(
            self,
            interval_timesteps: int,
            target_dir: Path,
            base_name: str,
            run_logger: logging.Logger,
            progress_interval_timesteps: int,
        ):
            super().__init__(verbose=0)
            self.interval_timesteps = max(int(interval_timesteps), 0)
            self.target_dir = target_dir
            self.base_name = base_name
            self.run_logger = run_logger
            self._last_saved_timestep = 0
            self.progress_interval_timesteps = max(int(progress_interval_timesteps), 0)
            self._last_progress_timestep = 0
            self._progress_start_wall_time = 0.0

        def _on_training_start(self) -> None:
            # When resuming, start counters from the current model timestep.
            self._last_saved_timestep = int(self.num_timesteps)
            self._last_progress_timestep = int(self.num_timesteps)
            self._progress_start_wall_time = float(self.model.start_time)
        
        def _on_step(self) -> bool:
            if self.progress_interval_timesteps > 0 and (self.num_timesteps - self._last_progress_timestep) >= self.progress_interval_timesteps:
                current_wall_time = float(self.model.start_time)
                delta_steps = self.num_timesteps - self._last_progress_timestep
                # Stable-Baselines stores start_time as wall-clock at learn start; use python time for elapsed.
                elapsed = max(float(__import__("time").time()) - current_wall_time, 1e-6)
                approx_fps = int(self.num_timesteps / elapsed)
                self.run_logger.info(
                    "Progress: total_timesteps=%d (+%d), approx_fps=%d",
                    self.num_timesteps,
                    delta_steps,
                    approx_fps,
                )
                self._last_progress_timestep = self.num_timesteps

            if self.interval_timesteps <= 0:
                return True
            if (self.num_timesteps - self._last_saved_timestep) < self.interval_timesteps:
                return True
            
            save_base = self.target_dir / f"{self.base_name}_step_{self.num_timesteps:09d}"
            self.model.save(str(save_base))
            checkpoint_path = save_base.with_suffix(".zip")
            self._last_saved_timestep = self.num_timesteps
            
            latest_pointer = self.target_dir / "LATEST_INTERVAL_CHECKPOINT.txt"
            latest_pointer.write_text(str(checkpoint_path), encoding="utf-8")
            self.run_logger.info(f"Checkpoint saved at timestep={self.num_timesteps}: {checkpoint_path}")
            return True
    
    callback = PeriodicCheckpointCallback(
        interval_timesteps=checkpoint_interval,
        target_dir=checkpoint_dir,
        base_name="teacher_sb3_ppo",
        run_logger=logger,
        progress_interval_timesteps=progress_log_interval,
    )
    
    # Resume training
    logger.info(f"Starting resumed training for {total_additional_timesteps} additional timesteps...")
    try:
        model.learn(total_timesteps=total_additional_timesteps, progress_bar=False, callback=callback, reset_num_timesteps=False)
        logger.info(f"Training completed successfully. Final timesteps: {model.num_timesteps}")
    except Exception as e:
        logger.exception(f"Training failed: {e}")
        raise
    finally:
        if hasattr(env, "close"):
            env.close()
    
    # Save final model
    final_checkpoint = checkpoint_dir_parent / "teacher_sb3_ppo_final_resumed.zip"
    model.save(str(final_checkpoint))
    logger.info(f"Final model saved: {final_checkpoint}")
    
    return final_checkpoint


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Resume teacher training from checkpoint")
    parser.add_argument(
        "--checkpoint",
        type=Path,
        required=True,
        help="Path to checkpoint to resume from",
    )
    parser.add_argument(
        "--additional-timesteps",
        type=int,
        default=20000,
        help="Additional timesteps to train",
    )
    parser.add_argument(
        "--num-bot-envs",
        type=int,
        default=4,
        help="Number of parallel environments",
    )
    parser.add_argument(
        "--checkpoint-interval",
        type=int,
        default=20000,
        help="Save checkpoint every N timesteps",
    )
    parser.add_argument(
        "--device",
        default="cuda",
        help="Device to train on (cuda or cpu)",
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=Path(__file__).resolve().parent,
        help="Output root directory",
    )
    parser.add_argument("--learning-rate", type=float, default=1e-4, help="Resume learning rate")
    parser.add_argument("--n-epochs", type=int, default=2, help="PPO epochs per update")
    parser.add_argument("--batch-size", type=int, default=256, help="PPO mini-batch size")
    parser.add_argument("--target-kl", type=float, default=0.01, help="Early stop PPO update at KL")
    parser.add_argument("--max-grad-norm", type=float, default=0.3, help="Gradient clipping threshold")
    parser.add_argument("--clip-range", type=float, default=0.1, help="PPO clip range")
    parser.add_argument("--progress-log-interval", type=int, default=2048, help="Log progress every N timesteps")
    
    args = parser.parse_args()
    
    final_ckpt = resume_training(
        checkpoint_path=args.checkpoint,
        output_root=args.output_root,
        total_additional_timesteps=args.additional_timesteps,
        num_bot_envs=args.num_bot_envs,
        checkpoint_interval=args.checkpoint_interval,
        device=args.device,
        learning_rate=args.learning_rate,
        n_epochs=args.n_epochs,
        batch_size=args.batch_size,
        target_kl=args.target_kl,
        max_grad_norm=args.max_grad_norm,
        clip_range=args.clip_range,
        progress_log_interval=args.progress_log_interval,
    )
    
    print(f"\n✅ Resume training completed!")
    print(f"Final checkpoint: {final_ckpt}")
