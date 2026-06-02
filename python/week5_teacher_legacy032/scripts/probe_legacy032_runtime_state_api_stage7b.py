from __future__ import annotations

import argparse
import inspect
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np

from legacy032_policy_action import BRANCH_SIZES, read_action_mask, step_env_training_compatible
from export_replay_ready_teacher_rollout_stage7b import _build_ai2s

DEFAULT_MAP_PATH = "maps/24x24/basesWorkers24x24.xml"
DEFAULT_MAX_STEPS = 64
DEFAULT_NUM_BOT_ENVS = 1
DEFAULT_SEED = 17
DEFAULT_JSON_REPORT = "python/week5_teacher_legacy032/reports/stage7b_legacy032_runtime_state_api_probe.json"
DEFAULT_MD_REPORT = "python/week5_teacher_legacy032/reports/stage7b_legacy032_runtime_state_api_probe.md"

KEYWORDS = ["state", "unit", "game", "json", "xml", "physical", "player", "resource", "trace"]
METHOD_CANDIDATES = [
    "getState",
    "getGameState",
    "getPhysicalGameState",
    "getUnit",
    "getUnits",
    "toJSON",
    "toXML",
    "getTrace",
    "getPlayers",
    "getResources",
    "getRuntimeStateJSON",
    "getRuntimeStateBatchJSON",
    "getInitialStateJSON",
]


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _resolve(path_str: str) -> Path:
    p = Path(path_str)
    if p.is_absolute():
        return p
    return (_repo_root() / p).resolve()


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _safe_reset(env: Any, seed: int) -> np.ndarray:
    try:
        obs = env.reset(seed=seed)
    except TypeError:
        obs = env.reset()
    if isinstance(obs, tuple):
        obs = obs[0]
    return np.asarray(obs, dtype=np.float32)


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


def _jsonable(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, np.ndarray):
        flat = value.reshape(-1)
        return {
            "kind": "ndarray",
            "dtype": str(value.dtype),
            "shape": [int(v) for v in value.shape],
            "preview": flat[: min(16, flat.shape[0])].tolist(),
        }
    return str(value)


def _safe_get_attr(obj: Any, attr: str) -> Tuple[bool, Any, str | None]:
    try:
        return True, getattr(obj, attr), None
    except Exception as exc:
        return False, None, f"{type(exc).__name__}: {exc}"


def _method_try_call(obj: Any, method_name: str) -> Dict[str, Any]:
    result: Dict[str, Any] = {
        "method": method_name,
        "callable": False,
        "attempted": False,
        "ok": False,
        "error": None,
        "return_type": None,
        "return_preview": None,
    }

    exists, method_obj, err = _safe_get_attr(obj, method_name)
    if not exists:
        result["error"] = err
        return result

    if not callable(method_obj):
        return result

    result["callable"] = True

    try:
        sig = inspect.signature(method_obj)
        required_params = [
            p
            for p in sig.parameters.values()
            if p.default is inspect._empty and p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD)
        ]
        if len(required_params) > 0:
            result["error"] = f"signature requires args: {str(sig)}"
            return result
    except Exception:
        # JPype methods may not expose signatures; we still try zero-arg call.
        pass

    result["attempted"] = True
    try:
        out = method_obj()
        result["ok"] = True
        result["return_type"] = str(type(out))
        result["return_preview"] = _jsonable(out)
    except Exception as exc:
        result["error"] = f"{type(exc).__name__}: {exc}"

    return result


def _collect_object_probe(label: str, obj: Any) -> Dict[str, Any]:
    names = sorted(set(dir(obj)))
    callable_names: List[str] = []
    keyword_names: List[str] = []

    for name in names:
        lowered = name.lower()
        if any(k in lowered for k in KEYWORDS):
            keyword_names.append(name)

        try:
            attr = getattr(obj, name)
            if callable(attr):
                callable_names.append(name)
        except Exception:
            continue

    candidate_presence: Dict[str, bool] = {}
    for cand in METHOD_CANDIDATES:
        candidate_presence[cand] = cand in names

    invoke_checks = []
    to_try = sorted(set([c for c in METHOD_CANDIDATES if c in names]))
    for method_name in to_try:
        invoke_checks.append(_method_try_call(obj, method_name))

    return {
        "label": label,
        "type": str(type(obj)),
        "repr": str(obj)[:500],
        "dir": names,
        "callable_methods": callable_names,
        "keyword_methods": keyword_names,
        "candidate_presence": candidate_presence,
        "candidate_invocation": invoke_checks,
    }


def _attach_targets(env: Any) -> Dict[str, Any]:
    targets: Dict[str, Any] = {"env": env}

    if hasattr(env, "vec_client"):
        targets["env.vec_client"] = env.vec_client
    if hasattr(env, "client"):
        targets["env.client"] = env.client

    vec_client = getattr(env, "vec_client", None)
    if vec_client is not None:
        if hasattr(vec_client, "client"):
            targets["env.vec_client.client"] = vec_client.client
        if hasattr(vec_client, "clients"):
            clients = vec_client.clients
            targets["env.vec_client.clients"] = clients
            try:
                if len(clients) > 0:
                    targets["env.vec_client.clients[0]"] = clients[0]
            except Exception:
                pass
        if hasattr(vec_client, "selfPlayClients"):
            sp_clients = vec_client.selfPlayClients
            targets["env.vec_client.selfPlayClients"] = sp_clients
            try:
                if len(sp_clients) > 0:
                    targets["env.vec_client.selfPlayClients[0]"] = sp_clients[0]
            except Exception:
                pass

    if hasattr(env, "render_client"):
        targets["env.render_client"] = env.render_client

    return targets


def _probe_snapshot(env: Any, stage_label: str) -> Dict[str, Any]:
    targets = _attach_targets(env)
    object_probes: Dict[str, Any] = {}

    for target_name, target_obj in targets.items():
        object_probes[target_name] = _collect_object_probe(target_name, target_obj)

    found_any_candidate = False
    found_exact: Dict[str, List[str]] = {name: [] for name in METHOD_CANDIDATES}

    for target_name, payload in object_probes.items():
        presence = payload.get("candidate_presence", {})
        for cand in METHOD_CANDIDATES:
            if bool(presence.get(cand, False)):
                found_any_candidate = True
                found_exact[cand].append(target_name)

    return {
        "stage": stage_label,
        "targets": object_probes,
        "found_any_exact_candidate": bool(found_any_candidate),
        "exact_candidate_locations": found_exact,
    }


def _run_single_step(env: Any, obs: np.ndarray) -> Dict[str, Any]:
    mapsize = 24 * 24
    mask_dim = 1 + sum(BRANCH_SIZES)
    nenv = int(obs.shape[0])

    mask_np, mask_source = read_action_mask(
        env=env,
        num_envs=nenv,
        mapsize=mapsize,
        mask_dim=mask_dim,
        require_mask=True,
    )

    noop_action = np.zeros((nenv, mapsize, len(BRANCH_SIZES)), dtype=np.int32)
    step_result, debug = step_env_training_compatible(
        env=env,
        action_tensor=noop_action,
        action_mask=mask_np,
        mapsize=mapsize,
    )

    if len(step_result) == 4:
        next_obs, rewards, dones, infos = step_result
        truncs = np.zeros_like(dones)
    else:
        next_obs, rewards, dones, truncs, infos = step_result

    rewards_np = np.asarray(rewards)
    dones_np = np.asarray(dones)
    truncs_np = np.asarray(truncs)

    info_payload = infos[0] if isinstance(infos, (list, tuple)) and len(infos) > 0 else infos

    return {
        "mask_source": str(mask_source),
        "step_debug": _jsonable(debug),
        "reward_sample": float(rewards_np.reshape(-1)[0]),
        "done_sample": bool(dones_np.reshape(-1)[0]),
        "truncated_sample": bool(truncs_np.reshape(-1)[0]),
        "next_obs_shape": [int(v) for v in np.asarray(next_obs).shape],
        "info_sample": _jsonable(info_payload),
    }


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")


def _build_markdown_report(payload: Dict[str, Any]) -> str:
    found = bool(payload.get("runtime_state_api_found", False))
    lines = [
        "# Stage7B Legacy032 Runtime-State API Probe",
        "",
        f"- generated_at_utc: {payload.get('generated_at_utc')}",
        f"- map_path: {payload.get('map_path')}",
        f"- num_bot_envs: {payload.get('num_bot_envs')}",
        f"- max_steps: {payload.get('max_steps')}",
        f"- runtime_state_api_found: {found}",
        "",
        "## Step Smoke",
        f"- reset_obs_shape: {payload.get('reset_obs_shape')}",
        f"- step_status: {payload.get('step_status')}",
    ]

    step_info = payload.get("step_info", {})
    if isinstance(step_info, dict) and step_info:
        lines.extend(
            [
                f"- reward_sample: {step_info.get('reward_sample')}",
                f"- done_sample: {step_info.get('done_sample')}",
                f"- truncated_sample: {step_info.get('truncated_sample')}",
                f"- next_obs_shape: {step_info.get('next_obs_shape')}",
                f"- mask_source: {step_info.get('mask_source')}",
            ]
        )

    lines.append("")
    lines.append("## Candidate Methods")

    pre = payload.get("probe_before_step", {})
    post = payload.get("probe_after_step", {})

    pre_locs = pre.get("exact_candidate_locations", {}) if isinstance(pre, dict) else {}
    post_locs = post.get("exact_candidate_locations", {}) if isinstance(post, dict) else {}

    for name in METHOD_CANDIDATES:
        pre_targets = pre_locs.get(name, []) if isinstance(pre_locs, dict) else []
        post_targets = post_locs.get(name, []) if isinstance(post_locs, dict) else []
        lines.append(f"- {name}: before={pre_targets} after={post_targets}")

    lines.append("")
    lines.append("## Conclusion")
    if found:
        lines.append("- Runtime-state API candidate methods were discovered; inspect JSON report invocation results.")
    else:
        lines.append("- No explicit runtime-state API candidate methods were discovered on probed objects.")
        lines.append("- Authoritative replay state snapshots are currently unavailable from Python without JNI/Java bridge extension.")

    return "\n".join(lines) + "\n"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=(
            "Probe legacy032 gym_microrts runtime-state API availability for Stage7B replay-ready export. "
            "No training, PPO, imitation, demo recording, or Unity ML-Agents runs are performed."
        )
    )
    p.add_argument("--map-path", default=DEFAULT_MAP_PATH)
    p.add_argument("--max-steps", type=int, default=DEFAULT_MAX_STEPS)
    p.add_argument("--num-bot-envs", type=int, default=DEFAULT_NUM_BOT_ENVS)
    p.add_argument("--seed", type=int, default=DEFAULT_SEED)
    p.add_argument("--output-json", default=DEFAULT_JSON_REPORT)
    p.add_argument("--output-md", default=DEFAULT_MD_REPORT)
    return p.parse_args()


def main() -> int:
    args = parse_args()

    out_json = _resolve(args.output_json)
    out_md = _resolve(args.output_md)

    env = None
    probe_before: Dict[str, Any] = {}
    probe_after: Dict[str, Any] = {}
    step_info: Dict[str, Any] = {}
    step_status = "not_started"
    reset_shape: List[int] = []

    try:
        env = _create_env(
            max_steps=int(args.max_steps),
            map_path=str(args.map_path),
            num_bot_envs=int(args.num_bot_envs),
        )
        obs = _safe_reset(env, seed=int(args.seed))
        reset_shape = [int(v) for v in obs.shape]

        probe_before = _probe_snapshot(env, "after_reset_before_step")

        try:
            step_info = _run_single_step(env, obs)
            step_status = "ok"
        except Exception as exc:
            step_status = f"failed: {type(exc).__name__}: {exc}"
            step_info = {"error": step_status}

        probe_after = _probe_snapshot(env, "after_one_step")

    finally:
        if env is not None:
            try:
                env.close()
            except Exception:
                pass

    found_before = bool(probe_before.get("found_any_exact_candidate", False))
    found_after = bool(probe_after.get("found_any_exact_candidate", False))

    payload: Dict[str, Any] = {
        "generated_at_utc": _now_iso(),
        "map_path": str(args.map_path),
        "num_bot_envs": int(args.num_bot_envs),
        "max_steps": int(args.max_steps),
        "seed": int(args.seed),
        "reset_obs_shape": reset_shape,
        "step_status": step_status,
        "step_info": step_info,
        "probe_before_step": probe_before,
        "probe_after_step": probe_after,
        "runtime_state_api_found": bool(found_before or found_after),
        "notes": [
            "This probe is read-only with respect to training artifacts.",
            "No ML-Agents training/PPO/imitation/.demo workflow is executed.",
            "If runtime_state_api_found=false, authoritative state snapshot support needs wrapper/JNI patching.",
        ],
    }

    _write_json(out_json, payload)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text(_build_markdown_report(payload), encoding="utf-8")

    print(str(out_json))
    print(str(out_md))
    print(f"runtime_state_api_found={payload['runtime_state_api_found']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
