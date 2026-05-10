from __future__ import annotations

import argparse
import json
import math
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np
import torch

from legacy032_policy_action import (
    BRANCH_SIZES,
    EXPECTED_ARCHITECTURE,
    EXPECTED_MAP_PATH,
    EXPECTED_OBS_SHAPE,
    EXPECTED_RAW_ACTION_NVEC,
    assert_legacy032_contract,
    build_policy_from_metadata,
    format_env_action,
    infer_logits,
    load_metadata,
    load_policy_checkpoint_strict,
    read_action_mask,
    select_action_deterministic,
    select_action_stochastic,
    step_env_training_compatible,
)

DEFAULT_CHECKPOINT_PATH = (
    "python/week5_teacher_legacy032/teacher_models/"
    "legacy032_24x24_teacher_resume_3m_from_1m_postfix/agent_final.pt"
)
DEFAULT_MODEL_METADATA_PATH = (
    "python/week5_teacher_legacy032/teacher_models/"
    "legacy032_24x24_teacher_resume_3m_from_1m_postfix/model_metadata.json"
)
DEFAULT_OUTPUT_ROOT = "python/week5_teacher_legacy032/teacher_replay_exports"

EXPECTED_BRANCH_SIZES = [6, 4, 4, 4, 4, 7, 49]
EXPECTED_ATTACK_TARGET_SIZE = 49
EXPECTED_ATTACK_TARGET_CENTER = 24
EXPECTED_ACTION_SHAPE = [576, 7]
EXPECTED_TERMINAL_METADATA_KEYS = ["done_t", "terminated_t", "truncated_t", "reward_t"]
REQUIRED_RUNTIME_STATE_FIELDS = [
    "initial_state_json",
    "runtime_state_t_json",
    "runtime_state_tp1_json",
]


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _resolve(path_str: str) -> Path:
    p = Path(path_str)
    if p.is_absolute():
        return p
    return (_repo_root() / p).resolve()


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


def _json_dump(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")


def _json_lines_dump(path: Path, rows: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=True) + "\n")


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


def _create_env(max_steps: int, map_path: str, num_bot_envs: int):
    from gym_microrts.envs.vec_env import MicroRTSGridModeVecEnv

    env = MicroRTSGridModeVecEnv(
        num_selfplay_envs=0,
        num_bot_envs=int(num_bot_envs),
        max_steps=int(max_steps),
        render_theme=2,
        ai2s=_build_ai2s(int(num_bot_envs)),
        map_path=str(map_path),
        reward_weight=np.array([10.0, 1.0, 1.0, 0.2, 1.0, 4.0]),
    )
    return env


def _safe_reset(env: Any, seed: int) -> np.ndarray:
    try:
        obs = env.reset(seed=seed)
    except TypeError:
        obs = env.reset()
    if isinstance(obs, tuple):
        obs = obs[0]
    return np.asarray(obs, dtype=np.float32)


def _choose_action(
    export_mode: str,
    logits: torch.Tensor,
    action_mask: torch.Tensor,
    nvec: List[int],
) -> torch.Tensor:
    if export_mode == "deterministic":
        return select_action_deterministic(logits=logits, nvec=nvec, action_mask=action_mask)
    return select_action_stochastic(logits=logits, nvec=nvec, action_mask=action_mask, seed=None)


def _build_teacher_commands(action_576x7: np.ndarray) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    actions = np.asarray(action_576x7, dtype=np.int32)
    nonnoop_idx = np.flatnonzero(actions[:, 0] != 0)
    commands: List[Dict[str, Any]] = []

    for actor_flat in sorted(nonnoop_idx.tolist()):
        actor_x = int(actor_flat % 24)
        actor_y = int(actor_flat // 24)

        action_type = int(actions[actor_flat, 0])
        move_dir = int(actions[actor_flat, 1])
        harvest_dir = int(actions[actor_flat, 2])
        return_dir = int(actions[actor_flat, 3])
        produce_dir = int(actions[actor_flat, 4])
        produce_unit_type = int(actions[actor_flat, 5])
        attack_target_local = int(actions[actor_flat, 6])

        target_x = None
        target_y = None
        if 0 <= attack_target_local < 49:
            local_dx = int(attack_target_local % 7) - 3
            local_dy = int(attack_target_local // 7) - 3
            target_x = int(actor_x + local_dx)
            target_y = int(actor_y + local_dy)

        commands.append(
            {
                "actor_flat": int(actor_flat),
                "actor_x": int(actor_x),
                "actor_y": int(actor_y),
                "action_type": int(action_type),
                "move_dir": int(move_dir),
                "harvest_dir": int(harvest_dir),
                "return_dir": int(return_dir),
                "produce_dir": int(produce_dir),
                "produce_unit_type": int(produce_unit_type),
                "attack_target_local": int(attack_target_local),
                "target_x": target_x,
                "target_y": target_y,
                "source_valid": None,
                "executable": None,
            }
        )

    hist = Counter(int(actions[i, 0]) for i in nonnoop_idx.tolist())
    diagnostics = {
        "nonoop_actor_count": int(len(nonnoop_idx)),
        "teacher_action_type_histogram": {str(k): int(v) for k, v in sorted(hist.items())},
    }
    return commands, diagnostics


def _runtime_state_status(available: bool, sample_state: Dict[str, Any] | None = None) -> Dict[str, Any]:
    missing = [
        "map_width",
        "map_height",
        "players",
        "units",
        "resource_nodes",
        "building_queues",
        "terminal",
        "step",
    ]
    if available:
        return {
            "available": True,
            "reason": "runtime state JSON bridge detected in vec_env/JNIGridnetVecClient",
            "missing_fields": [],
            "sample_state_preview": sample_state or {},
        }

    return {
        "available": False,
        "reason": (
            "gym_microrts wrapper did not provide authoritative runtime state fields in infos; "
            "export remains honest and replay_ready stays false."
        ),
        "missing_fields": missing,
        "instrumentation_hint": {
            "where": "python/week5_teacher_reference/.venv_microrts032_reference/lib/site-packages/gym_microrts/envs/vec_env.py",
            "how": [
                "Expose getRuntimeStateBatchJSON from JNI bridge.",
                "Inject initial_state_json/runtime_state_t_json/runtime_state_tp1_json into step infos.",
            ],
        },
    }


def _validate_export(
    manifest: Dict[str, Any],
    episode_paths: List[Path],
) -> Dict[str, Any]:
    errors: List[str] = []
    warnings: List[str] = []

    if manifest.get("branch_sizes") != EXPECTED_BRANCH_SIZES:
        errors.append("branch_sizes mismatch; expected [6,4,4,4,4,7,49]")
    if int(manifest.get("attack_target_size", -1)) != EXPECTED_ATTACK_TARGET_SIZE:
        errors.append("attack_target_size mismatch; expected 49")
    if int(manifest.get("attack_target_center_index", -1)) != EXPECTED_ATTACK_TARGET_CENTER:
        errors.append("attack_target_center_index mismatch; expected 24")
    if list(manifest.get("observation_shape", [])) != EXPECTED_OBS_SHAPE:
        errors.append("manifest observation_shape mismatch; expected [24,24,27]")
    if list(manifest.get("action_shape", [])) != EXPECTED_ACTION_SHAPE:
        errors.append("manifest action_shape mismatch; expected [576,7]")

    has_initial = bool(manifest.get("contains_initial_state", False))
    has_pre = bool(manifest.get("contains_pre_state", False))
    has_post = bool(manifest.get("contains_post_state", False))
    has_cmd = bool(manifest.get("contains_teacher_command_list", False))
    has_terminal = bool(manifest.get("contains_terminal_metadata", False))

    if not has_initial:
        errors.append("initial_state missing")
    if not has_pre:
        errors.append("runtime_state_t missing")
    if not has_post:
        errors.append("runtime_state_tp1 missing")
    if not has_cmd:
        errors.append("teacher_commands_t_json missing")
    if not has_terminal:
        errors.append("terminal metadata missing")

    total_steps = 0
    nonnoop_steps = 0
    multiple_nonnoop_steps = 0
    command_count_sum = 0
    action_hist: Counter[int] = Counter()

    for ep_path in episode_paths:
        with np.load(str(ep_path), allow_pickle=True) as npz:
            required_keys = [
                "episode_id",
                "step_id",
                "done_t",
                "terminated_t",
                "truncated_t",
                "reward_t",
                "observation_t",
                "per_cell_action_t",
                "action_mask_available_t",
                "teacher_command_count_t",
                "teacher_commands_t_json",
                "nonoop_actor_count_t",
                "teacher_action_type_histogram_t_json",
                "initial_state_json",
                "runtime_state_t_json",
                "runtime_state_tp1_json",
            ]
            for key in required_keys:
                if key not in npz:
                    errors.append(f"{ep_path.name}: missing key {key}")

            if "observation_t" in npz:
                obs = np.asarray(npz["observation_t"], dtype=np.float32)
                if obs.ndim != 4 or list(obs.shape[1:]) != EXPECTED_OBS_SHAPE:
                    errors.append(f"{ep_path.name}: invalid observation_t shape {list(obs.shape)}")
                if np.isnan(obs).any() or np.isinf(obs).any():
                    errors.append(f"{ep_path.name}: observation_t contains NaN/Inf")

            if "per_cell_action_t" in npz:
                act = np.asarray(npz["per_cell_action_t"], dtype=np.int32)
                if act.ndim != 3 or list(act.shape[1:]) != EXPECTED_ACTION_SHAPE:
                    errors.append(f"{ep_path.name}: invalid per_cell_action_t shape {list(act.shape)}")
                else:
                    attack = act[:, :, 6]
                    if int(np.min(attack)) < 0 or int(np.max(attack)) > 48:
                        errors.append(f"{ep_path.name}: attack_target out of range 0..48")
                    flat_action_types = act[:, :, 0]
                    for t in range(flat_action_types.shape[0]):
                        step_nonnoop = int(np.count_nonzero(flat_action_types[t] != 0))
                        if step_nonnoop > 0:
                            nonnoop_steps += 1
                        if step_nonnoop > 1:
                            multiple_nonnoop_steps += 1
                        if step_nonnoop > 0:
                            actor_idx = np.flatnonzero(flat_action_types[t] != 0)
                            for idx in actor_idx.tolist():
                                action_hist[int(flat_action_types[t, idx])] += 1

            if "reward_t" in npz:
                rew = np.asarray(npz["reward_t"], dtype=np.float32)
                if np.isnan(rew).any() or np.isinf(rew).any():
                    errors.append(f"{ep_path.name}: reward_t contains NaN/Inf")

            if "teacher_command_count_t" in npz:
                counts = np.asarray(npz["teacher_command_count_t"], dtype=np.int32)
                command_count_sum += int(np.sum(counts, dtype=np.int64))
                total_steps += int(counts.shape[0])

            for key in EXPECTED_TERMINAL_METADATA_KEYS:
                if key not in npz:
                    errors.append(f"{ep_path.name}: missing terminal metadata key {key}")

            for key in REQUIRED_RUNTIME_STATE_FIELDS:
                if key not in npz:
                    warnings.append(f"{ep_path.name}: {key} not exported")

    replay_ready_expected = has_initial and has_pre and has_post and has_cmd and has_terminal and len(errors) == 0
    replay_ready_manifest = bool(manifest.get("replay_ready", False))
    if replay_ready_manifest != replay_ready_expected:
        errors.append(
            f"replay_ready flag mismatch; expected={replay_ready_expected} manifest={replay_ready_manifest}"
        )

    mean_commands = float(command_count_sum / max(1, total_steps))

    return {
        "episodes_exported": int(len(episode_paths)),
        "steps_exported": int(total_steps),
        "observation_shape": list(EXPECTED_OBS_SHAPE),
        "action_shape": list(EXPECTED_ACTION_SHAPE),
        "branch_sizes": list(EXPECTED_BRANCH_SIZES),
        "attack_target_size": int(EXPECTED_ATTACK_TARGET_SIZE),
        "initial_state_present": bool(has_initial),
        "pre_state_present": bool(has_pre),
        "post_state_present": bool(has_post),
        "teacher_command_list_present": bool(has_cmd),
        "terminal_metadata_present": bool(has_terminal),
        "replay_ready": bool(replay_ready_manifest),
        "nonoop_steps": int(nonnoop_steps),
        "multiple_nonnoop_steps": int(multiple_nonnoop_steps),
        "mean_teacher_command_count_per_step": float(mean_commands),
        "action_type_histogram": {str(k): int(v) for k, v in sorted(action_hist.items())},
        "validation_errors": errors,
        "validation_warnings": warnings,
    }


def _markdown_report(report: Dict[str, Any], run_dir: Path) -> str:
    lines = [
        "# Stage7B Replay-Ready Teacher Export Report",
        "",
        f"- generated_at_utc: {report.get('generated_at_utc')}",
        f"- run_dir: {run_dir.as_posix()}",
        f"- episodes_exported: {report.get('episodes_exported')}",
        f"- steps_exported: {report.get('steps_exported')}",
        f"- replay_ready: {report.get('replay_ready')}",
        "",
        "## Contracts",
        f"- observation_shape: {report.get('observation_shape')}",
        f"- action_shape: {report.get('action_shape')}",
        f"- branch_sizes: {report.get('branch_sizes')}",
        f"- attack_target_size: {report.get('attack_target_size')}",
        "",
        "## Presence Flags",
        f"- initial_state_present: {report.get('initial_state_present')}",
        f"- pre_state_present: {report.get('pre_state_present')}",
        f"- post_state_present: {report.get('post_state_present')}",
        f"- teacher_command_list_present: {report.get('teacher_command_list_present')}",
        f"- terminal_metadata_present: {report.get('terminal_metadata_present')}",
        "",
        "## Diagnostics",
        f"- nonnoop_steps: {report.get('nonoop_steps')}",
        f"- multiple_nonnoop_steps: {report.get('multiple_nonnoop_steps')}",
        f"- mean_teacher_command_count_per_step: {report.get('mean_teacher_command_count_per_step')}",
        f"- action_type_histogram: {report.get('action_type_histogram')}",
        "",
        "## Validation Errors",
    ]
    errs = report.get("validation_errors", []) or []
    if errs:
        lines.extend([f"- {e}" for e in errs])
    else:
        lines.append("- none")

    lines.append("")
    lines.append("## Validation Warnings")
    warns = report.get("validation_warnings", []) or []
    if warns:
        lines.extend([f"- {w}" for w in warns])
    else:
        lines.append("- none")

    return "\n".join(lines) + "\n"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=(
            "Export Stage7B teacher trajectories into replay-ready package layout. "
            "If authoritative runtime state is unavailable in gym_microrts wrapper, export stays honest with replay_ready=false."
        )
    )
    p.add_argument("--checkpoint-path", default=DEFAULT_CHECKPOINT_PATH)
    p.add_argument("--model-metadata-path", default=DEFAULT_MODEL_METADATA_PATH)
    p.add_argument("--map-path", default=EXPECTED_MAP_PATH)
    p.add_argument("--episodes", type=int, default=1)
    p.add_argument("--max-steps-per-episode", type=int, default=6000)
    p.add_argument("--seed", type=int, default=17)
    p.add_argument("--device", choices=["cpu", "cuda"], default="cpu")
    p.add_argument("--num-bot-envs", type=int, default=1)
    p.add_argument("--export-mode", choices=["deterministic", "stochastic"], default="stochastic")
    p.add_argument("--require-mask", type=_parse_bool, default=True)
    p.add_argument("--strict-load", action="store_true", default=True)
    p.add_argument("--no-strict-load", dest="strict_load", action="store_false")
    p.add_argument("--output-root", default=DEFAULT_OUTPUT_ROOT)
    p.add_argument("--run-label", default="legacy032")
    p.add_argument("--write-jsonl", type=_parse_bool, default=True)
    p.add_argument("--env-id", default="MicrortsRandomEnemyShapedReward1-v1")
    p.add_argument("--policy-source", default="legacy032_policy_action")
    return p.parse_args()


def main() -> int:
    args = parse_args()

    checkpoint_path = _resolve(args.checkpoint_path)
    metadata_path = _resolve(args.model_metadata_path)
    output_root = _resolve(args.output_root)

    if not checkpoint_path.exists():
        raise SystemExit(f"checkpoint path does not exist: {checkpoint_path}")
    if not metadata_path.exists():
        raise SystemExit(f"model metadata path does not exist: {metadata_path}")

    if list(BRANCH_SIZES) != EXPECTED_BRANCH_SIZES:
        raise SystemExit("branch size contract mismatch in importer")

    run_dir = output_root / f"stage7b_replay_ready_{str(args.run_label).strip()}_{_now_compact()}"
    run_dir.mkdir(parents=True, exist_ok=False)

    metadata = load_metadata(metadata_path)
    contract = assert_legacy032_contract(metadata)

    if str(args.map_path).strip() != EXPECTED_MAP_PATH:
        raise SystemExit(f"map path mismatch: expected={EXPECTED_MAP_PATH}, actual={args.map_path}")

    if int(args.num_bot_envs) <= 0:
        raise SystemExit("--num-bot-envs must be > 0")

    device = torch.device("cuda" if args.device == "cuda" and torch.cuda.is_available() else "cpu")
    torch.manual_seed(int(args.seed))
    np.random.seed(int(args.seed))

    policy, build_report = build_policy_from_metadata(metadata=metadata, device=device)
    load_report = load_policy_checkpoint_strict(
        policy=policy,
        checkpoint_path=checkpoint_path,
        device=device,
        strict=bool(args.strict_load),
    )
    policy.eval()

    runtime_state_available = False
    runtime_state_sample_preview: Dict[str, Any] | None = None
    contains_initial_state = False
    contains_pre_state = False
    contains_post_state = False

    episode_paths: List[Path] = []
    all_jsonl_rows: Dict[int, List[Dict[str, Any]]] = {}

    env = None
    try:
        env = _create_env(
            max_steps=int(args.max_steps_per_episode),
            map_path=str(args.map_path),
            num_bot_envs=int(args.num_bot_envs),
        )

        mapsize = int(contract["mapsize"])
        mask_dim = int(contract["mask_dim"])

        for ep in range(int(args.episodes)):
            obs = _safe_reset(env, seed=int(args.seed) + ep)

            episode_id: List[int] = []
            step_id: List[int] = []
            reward_t: List[float] = []
            done_t: List[bool] = []
            terminated_t: List[bool] = []
            truncated_t: List[bool] = []
            terminal_type_t: List[str] = []

            observation_t: List[np.ndarray] = []
            per_cell_action_t: List[np.ndarray] = []
            action_mask_available_t: List[bool] = []
            action_mask_t: List[np.ndarray] = []

            teacher_command_count_t: List[int] = []
            teacher_commands_t_json: List[str] = []
            command_actor_count_t: List[int] = []
            teacher_action_type_histogram_t_json: List[str] = []
            source_valid_action_count_t: List[int] = []
            unsupported_action_count_t: List[int] = []

            info_t_json: List[str] = []
            initial_state_json: List[str] = []
            runtime_state_t_json: List[str] = []
            runtime_state_tp1_json: List[str] = []
            rows_for_jsonl: List[Dict[str, Any]] = []

            for st in range(int(args.max_steps_per_episode)):
                nenv = int(obs.shape[0])
                mask_np, mask_source = read_action_mask(
                    env,
                    nenv,
                    mapsize,
                    mask_dim,
                    require_mask=bool(args.require_mask),
                )
                mask_available = str(mask_source) != "fallback_ones_mask"

                obs_t = torch.as_tensor(obs, dtype=torch.float32, device=device)
                mask_t = torch.as_tensor(mask_np, dtype=torch.float32, device=device)
                logits = infer_logits(policy, obs_t)
                action_t = _choose_action(
                    export_mode=str(args.export_mode),
                    logits=logits,
                    action_mask=mask_t,
                    nvec=contract["action_space_nvec"],
                )
                env_action = format_env_action(action_t)

                step_result, step_debug = step_env_training_compatible(
                    env=env,
                    action_tensor=env_action,
                    action_mask=mask_np,
                    mapsize=mapsize,
                )

                if len(step_result) == 4:
                    next_obs, rewards, dones, infos = step_result
                    truncs = np.zeros_like(dones)
                else:
                    next_obs, rewards, dones, truncs, infos = step_result

                reward_value = float(np.asarray(rewards).reshape(-1)[0])
                terminated_flag = bool(np.asarray(dones).reshape(-1)[0])
                truncated_flag = bool(np.asarray(truncs).reshape(-1)[0])
                done_flag = bool(terminated_flag or truncated_flag)
                terminal_type = "terminated" if terminated_flag else ("truncated" if truncated_flag else "none")

                actions_step = np.asarray(env_action[0], dtype=np.int32).copy()
                source_valid_mask = np.asarray(mask_np[0, :, 0] > 0, dtype=np.bool_)
                actions_step[~source_valid_mask, :] = 0
                commands, cmd_diag = _build_teacher_commands(actions_step)

                action_hist = cmd_diag.get("teacher_action_type_histogram", {})
                unsupported = 0
                for raw_type in action_hist.keys():
                    try:
                        rt = int(raw_type)
                    except ValueError:
                        unsupported += int(action_hist[raw_type])
                        continue
                    if rt < 0 or rt >= EXPECTED_BRANCH_SIZES[0]:
                        unsupported += int(action_hist[raw_type])

                info_payload = infos[0] if isinstance(infos, (list, tuple)) and len(infos) > 0 else infos
                if not isinstance(info_payload, dict):
                    info_payload = {}

                initial_state = info_payload.get("initial_state_json")
                state_t = info_payload.get("runtime_state_t_json")
                state_tp1 = info_payload.get("runtime_state_tp1_json")

                has_initial = isinstance(initial_state, str) and len(initial_state) > 0
                has_pre = isinstance(state_t, str) and len(state_t) > 0
                has_post = isinstance(state_tp1, str) and len(state_tp1) > 0

                contains_initial_state = bool(contains_initial_state or has_initial)
                contains_pre_state = bool(contains_pre_state or has_pre)
                contains_post_state = bool(contains_post_state or has_post)
                runtime_state_available = bool(runtime_state_available or has_pre or has_post)

                if runtime_state_sample_preview is None and has_post:
                    try:
                        parsed = json.loads(state_tp1)
                        runtime_state_sample_preview = {
                            "map_width": parsed.get("map_width"),
                            "map_height": parsed.get("map_height"),
                            "step": parsed.get("step"),
                            "players_count": len(parsed.get("players", [])),
                            "units_count": len(parsed.get("units", [])),
                            "resource_nodes_count": len(parsed.get("resource_nodes", [])),
                            "terminal": parsed.get("terminal", {}),
                        }
                    except Exception:
                        runtime_state_sample_preview = {"parse_error": True}

                info_row = {
                    "episode_id": int(ep),
                    "step_id": int(st),
                    "info": str(info_payload),
                    "runtime_state_available": bool(has_pre or has_post),
                }

                episode_id.append(int(ep))
                step_id.append(int(st))
                reward_t.append(reward_value)
                done_t.append(done_flag)
                terminated_t.append(terminated_flag)
                truncated_t.append(truncated_flag)
                terminal_type_t.append(str(terminal_type))

                observation_t.append(np.asarray(obs, dtype=np.float32)[0])
                per_cell_action_t.append(actions_step)
                action_mask_available_t.append(bool(mask_available))
                action_mask_t.append(np.asarray(mask_np[0], dtype=np.bool_))

                teacher_command_count_t.append(int(len(commands)))
                teacher_commands_t_json.append(json.dumps(commands, ensure_ascii=True))
                command_actor_count_t.append(int(cmd_diag["nonoop_actor_count"]))
                teacher_action_type_histogram_t_json.append(json.dumps(action_hist, ensure_ascii=True))
                source_valid_action_count_t.append(int(step_debug.get("source_valid_total", 0)))
                unsupported_action_count_t.append(int(unsupported))

                initial_state_json.append(initial_state if has_initial else "")
                runtime_state_t_json.append(state_t if has_pre else "")
                runtime_state_tp1_json.append(state_tp1 if has_post else "")

                info_t_json.append(json.dumps(info_row, ensure_ascii=True))
                rows_for_jsonl.append(
                    {
                        "episode_id": int(ep),
                        "step_id": int(st),
                        "reward_t": reward_value,
                        "done_t": done_flag,
                        "terminated_t": terminated_flag,
                        "truncated_t": truncated_flag,
                        "teacher_command_count_t": int(len(commands)),
                        "teacher_commands": commands,
                        "nonoop_actor_count_t": int(cmd_diag["nonoop_actor_count"]),
                        "teacher_action_type_histogram_t": action_hist,
                        "source_valid_action_count_t": int(step_debug.get("source_valid_total", 0)),
                        "unsupported_action_count_t": int(unsupported),
                        "initial_state_json": initial_state if has_initial else "",
                        "runtime_state_t_json": state_t if has_pre else "",
                        "runtime_state_tp1_json": state_tp1 if has_post else "",
                    }
                )

                if done_flag:
                    break

                obs = np.asarray(next_obs, dtype=np.float32)

            ep_npz_path = run_dir / f"episode_{ep:05d}.replay_ready.npz"
            np.savez_compressed(
                ep_npz_path,
                episode_id=np.asarray(episode_id, dtype=np.int32),
                step_id=np.asarray(step_id, dtype=np.int32),
                done_t=np.asarray(done_t, dtype=np.bool_),
                terminated_t=np.asarray(terminated_t, dtype=np.bool_),
                truncated_t=np.asarray(truncated_t, dtype=np.bool_),
                reward_t=np.asarray(reward_t, dtype=np.float32),
                terminal_type_t=np.asarray(terminal_type_t, dtype=object),
                observation_t=np.asarray(observation_t, dtype=np.float32),
                per_cell_action_t=np.asarray(per_cell_action_t, dtype=np.int16),
                action_mask_available_t=np.asarray(action_mask_available_t, dtype=np.bool_),
                action_mask_t=np.asarray(action_mask_t, dtype=np.bool_),
                teacher_command_count_t=np.asarray(teacher_command_count_t, dtype=np.int16),
                teacher_commands_t_json=np.asarray(teacher_commands_t_json, dtype=object),
                nonnoop_actor_count_t=np.asarray(command_actor_count_t, dtype=np.int16),
                nonoop_actor_count_t=np.asarray(command_actor_count_t, dtype=np.int16),
                teacher_action_type_histogram_t_json=np.asarray(teacher_action_type_histogram_t_json, dtype=object),
                source_valid_action_count_t=np.asarray(source_valid_action_count_t, dtype=np.int16),
                unsupported_action_count_t=np.asarray(unsupported_action_count_t, dtype=np.int16),
                initial_state_json=np.asarray(initial_state_json, dtype=object),
                runtime_state_t_json=np.asarray(runtime_state_t_json, dtype=object),
                runtime_state_tp1_json=np.asarray(runtime_state_tp1_json, dtype=object),
                info_t_json=np.asarray(info_t_json, dtype=object),
            )
            episode_paths.append(ep_npz_path)
            all_jsonl_rows[ep] = rows_for_jsonl

            if bool(args.write_jsonl):
                ep_jsonl_path = run_dir / f"episode_{ep:05d}.replay_ready.jsonl"
                _json_lines_dump(ep_jsonl_path, rows_for_jsonl)

    finally:
        if env is not None:
            try:
                env.close()
            except Exception:
                pass

    contains_teacher_commands = True
    contains_terminal_metadata = True
    runtime_state_meta = _runtime_state_status(
        available=bool(runtime_state_available and contains_initial_state and contains_pre_state and contains_post_state),
        sample_state=runtime_state_sample_preview,
    )

    replay_ready = bool(
        contains_initial_state
        and contains_pre_state
        and contains_post_state
        and contains_teacher_commands
        and contains_terminal_metadata
    )

    manifest = {
        "schema_version": "stage7b.teacher_replay_ready.v1",
        "source_teacher_lineage": "legacy032",
        "checkpoint_path": str(checkpoint_path),
        "policy_source": str(args.policy_source),
        "env_id": str(args.env_id),
        "gym_microrts_version": "0.3.2",
        "map_path": str(args.map_path),
        "seed": int(args.seed),
        "episodes": int(args.episodes),
        "max_steps_per_episode": int(args.max_steps_per_episode),
        "branch_sizes": list(EXPECTED_BRANCH_SIZES),
        "attack_target_size": int(EXPECTED_ATTACK_TARGET_SIZE),
        "attack_target_center_index": int(EXPECTED_ATTACK_TARGET_CENTER),
        "observation_shape": list(EXPECTED_OBS_SHAPE),
        "action_shape": list(EXPECTED_ACTION_SHAPE),
        "contains_initial_state": bool(contains_initial_state),
        "contains_pre_state": bool(contains_pre_state),
        "contains_post_state": bool(contains_post_state),
        "contains_teacher_command_list": bool(contains_teacher_commands),
        "contains_terminal_metadata": bool(contains_terminal_metadata),
        "replay_ready": bool(replay_ready),
        "runtime_state_availability": runtime_state_meta,
        "strict_load": bool(args.strict_load),
        "strict_load_report": load_report,
        "architecture_build_report": build_report,
        "expected_architecture": EXPECTED_ARCHITECTURE,
        "raw_action_nvec": list(EXPECTED_RAW_ACTION_NVEC),
        "created_utc": _now_iso(),
        "notes": [
            "No ML-Agents training/PPO/imitation/demo is run by this script.",
            "Export includes teacher commands and contract diagnostics.",
            "Authoritative runtime state is not faked when unavailable.",
        ],
    }

    manifest_path = run_dir / "replay_manifest.json"
    _json_dump(manifest_path, manifest)

    validation = _validate_export(manifest=manifest, episode_paths=episode_paths)

    report_payload = {
        "generated_at_utc": _now_iso(),
        "run_dir": str(run_dir),
        "episodes_exported": validation["episodes_exported"],
        "steps_exported": validation["steps_exported"],
        "observation_shape": validation["observation_shape"],
        "action_shape": validation["action_shape"],
        "branch_sizes": validation["branch_sizes"],
        "attack_target_size": validation["attack_target_size"],
        "initial_state_present": validation["initial_state_present"],
        "pre_state_present": validation["pre_state_present"],
        "post_state_present": validation["post_state_present"],
        "teacher_command_list_present": validation["teacher_command_list_present"],
        "terminal_metadata_present": validation["terminal_metadata_present"],
        "replay_ready": validation["replay_ready"],
        "nonoop_steps": validation["nonoop_steps"],
        "multiple_nonnoop_steps": validation["multiple_nonnoop_steps"],
        "mean_teacher_command_count_per_step": validation["mean_teacher_command_count_per_step"],
        "action_type_histogram": validation["action_type_histogram"],
        "validation_errors": validation["validation_errors"],
        "validation_warnings": validation["validation_warnings"],
    }

    report_json_path = run_dir / "stage7b_replay_ready_export_report.json"
    _json_dump(report_json_path, report_payload)

    report_md_path = run_dir / "stage7b_replay_ready_export_report.md"
    report_md_path.write_text(_markdown_report(report_payload, run_dir), encoding="utf-8")

    summary_payload = {
        "generated_at_utc": _now_iso(),
        "run_dir": str(run_dir),
        "replay_manifest": str(manifest_path),
        "episode_files": [p.name for p in episode_paths],
        "report_json": str(report_json_path),
        "report_md": str(report_md_path),
        "replay_ready": bool(report_payload["replay_ready"]),
        "validation_errors_count": int(len(report_payload["validation_errors"])),
        "validation_warnings_count": int(len(report_payload["validation_warnings"])),
    }

    replay_summary_json = run_dir / "replay_export_summary.json"
    replay_summary_md = run_dir / "replay_export_summary.md"
    _json_dump(replay_summary_json, summary_payload)

    summary_md_lines = [
        "# Replay Export Summary",
        "",
        f"- generated_at_utc: {summary_payload['generated_at_utc']}",
        f"- run_dir: {summary_payload['run_dir']}",
        f"- replay_ready: {summary_payload['replay_ready']}",
        f"- episode_count: {len(episode_paths)}",
        f"- validation_errors_count: {summary_payload['validation_errors_count']}",
        f"- validation_warnings_count: {summary_payload['validation_warnings_count']}",
    ]
    replay_summary_md.write_text("\n".join(summary_md_lines) + "\n", encoding="utf-8")

    print(str(run_dir))
    print(str(manifest_path))
    print(str(report_json_path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
