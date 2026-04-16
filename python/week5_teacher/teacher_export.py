from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple


class RolloutError(RuntimeError):
    pass


@dataclass
class EpisodeExportRecord:
    episode_id: int
    step_id: List[int]
    observation_t: List[Any]
    action_t: List[Any]
    action_t_json: List[str]
    action_t_hash: List[str]
    reward_t: List[float]
    done_t: List[bool]
    terminated_t: List[bool]
    truncated_t: List[bool]
    terminal_type_t: List[str]
    info_t_json: List[str]
    action_mask_t_json: List[str]
    action_mask_available_t: List[bool]
    observation_shape: Optional[List[int]]
    env_info_keys_union: List[str]


@dataclass
class BatchValidationResult:
    ok: bool
    errors: List[str]


def compute_mean(values: Sequence[float]) -> float:
    if not values:
        return 0.0
    return float(sum(values) / len(values))


def compute_std(values: Sequence[float]) -> float:
    if len(values) < 2:
        return 0.0
    mean = compute_mean(values)
    variance = sum((value - mean) ** 2 for value in values) / len(values)
    return float(variance**0.5)


def sanitize_label(value: str) -> str:
    allowed = []
    for ch in value.strip():
        if ch.isalnum() or ch in ("-", "_"):
            allowed.append(ch)
    return "".join(allowed) or "raw_teacher"


def canonical_json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":"))


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def normalize_json_payload(payload: Any, numpy_module: Optional[Any]) -> Any:
    if payload is None:
        return None
    if isinstance(payload, (bool, int, str)):
        return payload
    if isinstance(payload, float):
        if math.isnan(payload) or math.isinf(payload):
            raise RolloutError("Encountered NaN/Inf in JSON payload normalization.")
        return payload
    if isinstance(payload, dict):
        return {str(key): normalize_json_payload(value, numpy_module) for key, value in payload.items()}
    if isinstance(payload, (list, tuple)):
        return [normalize_json_payload(value, numpy_module) for value in payload]

    if numpy_module is not None:
        if isinstance(payload, numpy_module.generic):
            return normalize_json_payload(payload.item(), numpy_module)
        if hasattr(payload, "shape"):
            array = numpy_module.asarray(payload)
            return normalize_json_payload(array.tolist(), numpy_module)

    return str(payload)


def to_numpy_array(value: Any, numpy_module: Optional[Any], field_name: str) -> Any:
    if numpy_module is None:
        raise RolloutError(
            f"NumPy is required for Day 3 export, but it is unavailable while processing '{field_name}'."
        )
    return numpy_module.asarray(value)


def ensure_finite_array(array: Any, numpy_module: Any, field_name: str, episode_id: int, step_id: int) -> None:
    if not bool(numpy_module.isfinite(array).all()):
        raise RolloutError(
            f"Non-finite values detected in {field_name} at episode_id={episode_id}, step_id={step_id}."
        )


def should_write_jsonl(write_jsonl: str, batch_mode: str) -> bool:
    if write_jsonl == "always":
        return True
    if write_jsonl == "never":
        return False
    return batch_mode == "debug"


def extract_action_surface_bucket(action_payload: Any) -> str:
    if isinstance(action_payload, (bool, int, float, str)) or action_payload is None:
        return f"scalar:{action_payload}"
    if isinstance(action_payload, list):
        if not action_payload:
            return "list:empty"
        first = action_payload[0]
        if isinstance(first, (bool, int)):
            return f"list_len={len(action_payload)}_first={int(first)}"
        return f"list_len={len(action_payload)}"
    if isinstance(action_payload, dict):
        if "action_type" in action_payload and isinstance(action_payload["action_type"], (bool, int, str)):
            return f"dict_action_type={action_payload['action_type']}"
        keys = sorted(action_payload.keys())
        return f"dict_keys={'+'.join(keys[:3])}"
    return f"type={type(action_payload).__name__}"


def try_read_action_mask(
    env: Any,
    step_info: Dict[str, Any],
    numpy_module: Optional[Any],
) -> Tuple[Optional[str], bool, Optional[str], Optional[str]]:
    candidate: Any = None
    source: Optional[str] = None
    error: Optional[str] = None

    if hasattr(env, "get_action_mask"):
        try:
            candidate = env.get_action_mask()
            if candidate is not None:
                source = "env.get_action_mask"
        except Exception as exc:
            error = f"env.get_action_mask failed: {exc}"

    if candidate is None and hasattr(env, "action_masks"):
        try:
            action_masks_attr = getattr(env, "action_masks")
            candidate = action_masks_attr() if callable(action_masks_attr) else action_masks_attr
            if candidate is not None:
                source = "env.action_masks"
        except Exception as exc:
            error = f"env.action_masks failed: {exc}"

    if candidate is None:
        for key in ("action_mask", "action_masks", "mask", "valid_action_mask"):
            if key in step_info:
                candidate = step_info[key]
                source = f"info.{key}"
                break

    if candidate is None:
        return "", False, source, error

    normalized = normalize_json_payload(candidate, numpy_module)
    return canonical_json(normalized), True, source, error


def new_episode_record(episode_id: int) -> EpisodeExportRecord:
    return EpisodeExportRecord(
        episode_id=episode_id,
        step_id=[],
        observation_t=[],
        action_t=[],
        action_t_json=[],
        action_t_hash=[],
        reward_t=[],
        done_t=[],
        terminated_t=[],
        truncated_t=[],
        terminal_type_t=[],
        info_t_json=[],
        action_mask_t_json=[],
        action_mask_available_t=[],
        observation_shape=None,
        env_info_keys_union=[],
    )


def validate_episode_record(record: EpisodeExportRecord, numpy_module: Any) -> BatchValidationResult:
    errors: List[str] = []
    step_count = len(record.step_id)
    fields_to_check = {
        "observation_t": len(record.observation_t),
        "action_t": len(record.action_t),
        "action_t_json": len(record.action_t_json),
        "action_t_hash": len(record.action_t_hash),
        "reward_t": len(record.reward_t),
        "done_t": len(record.done_t),
        "terminated_t": len(record.terminated_t),
        "truncated_t": len(record.truncated_t),
        "terminal_type_t": len(record.terminal_type_t),
        "info_t_json": len(record.info_t_json),
        "action_mask_t_json": len(record.action_mask_t_json),
        "action_mask_available_t": len(record.action_mask_available_t),
    }
    for field_name, field_len in fields_to_check.items():
        if field_len != step_count:
            errors.append(
                f"episode_id={record.episode_id}: length mismatch for {field_name} ({field_len} != {step_count})"
            )

    expected_steps = list(range(step_count))
    if record.step_id != expected_steps:
        errors.append(
            f"episode_id={record.episode_id}: step_id sequence is not contiguous 0..N-1"
        )

    if step_count == 0:
        errors.append(f"episode_id={record.episode_id}: episode has zero recorded steps")
        return BatchValidationResult(ok=False, errors=errors)

    for index, reward_value in enumerate(record.reward_t):
        if math.isnan(reward_value) or math.isinf(reward_value):
            errors.append(f"episode_id={record.episode_id}: reward_t[{index}] is NaN/Inf")

    if not record.done_t[-1]:
        errors.append(f"episode_id={record.episode_id}: final done_t is False")

    for index in range(step_count - 1):
        if record.done_t[index]:
            errors.append(
                f"episode_id={record.episode_id}: done_t[{index}] is True before final step"
            )

    for index in range(step_count):
        terminated = record.terminated_t[index]
        truncated = record.truncated_t[index]
        done = record.done_t[index]
        if done != (terminated or truncated):
            errors.append(
                f"episode_id={record.episode_id}: done/terminated/truncated mismatch at step {index}"
            )

        action_hash = sha256_text(record.action_t_json[index])
        if action_hash != record.action_t_hash[index]:
            errors.append(
                f"episode_id={record.episode_id}: action hash mismatch at step {index}"
            )

    if record.observation_shape is None:
        errors.append(f"episode_id={record.episode_id}: observation_shape is missing")

    for index, observation in enumerate(record.observation_t):
        observation_array = numpy_module.asarray(observation)
        if list(observation_array.shape) != (record.observation_shape or []):
            errors.append(
                f"episode_id={record.episode_id}: observation shape drift at step {index}: "
                f"{list(observation_array.shape)} != {record.observation_shape}"
            )
        if not bool(numpy_module.isfinite(observation_array).all()):
            errors.append(
                f"episode_id={record.episode_id}: non-finite observation at step {index}"
            )

    return BatchValidationResult(ok=len(errors) == 0, errors=errors)


def write_episode_npz(path: Path, record: EpisodeExportRecord, numpy_module: Any, batch_metadata: Dict[str, Any]) -> None:
    observation_array = numpy_module.stack([numpy_module.asarray(obs) for obs in record.observation_t], axis=0)
    action_json_array = numpy_module.asarray(record.action_t_json, dtype=object)
    action_hash_array = numpy_module.asarray(record.action_t_hash, dtype=object)
    info_json_array = numpy_module.asarray(record.info_t_json, dtype=object)
    mask_json_array = numpy_module.asarray(record.action_mask_t_json, dtype=object)
    action_payload_array = numpy_module.asarray(record.action_t, dtype=object)
    terminal_type_array = numpy_module.asarray(record.terminal_type_t, dtype=object)

    numpy_module.savez_compressed(
        path,
        episode_id=numpy_module.asarray([record.episode_id], dtype=numpy_module.int64),
        step_id=numpy_module.asarray(record.step_id, dtype=numpy_module.int64),
        observation_t=observation_array,
        action_t=action_payload_array,
        action_t_json=action_json_array,
        action_t_hash=action_hash_array,
        reward_t=numpy_module.asarray(record.reward_t, dtype=numpy_module.float32),
        done_t=numpy_module.asarray(record.done_t, dtype=numpy_module.bool_),
        terminated_t=numpy_module.asarray(record.terminated_t, dtype=numpy_module.bool_),
        truncated_t=numpy_module.asarray(record.truncated_t, dtype=numpy_module.bool_),
        terminal_type_t=terminal_type_array,
        info_t_json=info_json_array,
        action_mask_t_json=mask_json_array,
        action_mask_available_t=numpy_module.asarray(record.action_mask_available_t, dtype=numpy_module.bool_),
        observation_shape=numpy_module.asarray(record.observation_shape or [], dtype=numpy_module.int64),
        env_info_keys_union=numpy_module.asarray(record.env_info_keys_union, dtype=object),
        batch_metadata_json=numpy_module.asarray([canonical_json(batch_metadata)], dtype=object),
    )


def write_episode_jsonl(path: Path, record: EpisodeExportRecord) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for index in range(len(record.step_id)):
            payload = {
                "episode_id": record.episode_id,
                "step_id": record.step_id[index],
                "observation_shape": record.observation_shape,
                "action_t": json.loads(record.action_t_json[index]),
                "reward_t": record.reward_t[index],
                "done_t": record.done_t[index],
                "terminated_t": record.terminated_t[index],
                "truncated_t": record.truncated_t[index],
                "terminal_type_t": record.terminal_type_t[index],
                "action_mask_available": record.action_mask_available_t[index],
                "action_mask_t": (
                    json.loads(record.action_mask_t_json[index])
                    if record.action_mask_available_t[index]
                    else None
                ),
                "info": json.loads(record.info_t_json[index]),
            }
            handle.write(json.dumps(payload, ensure_ascii=False))
            handle.write("\n")


def validate_saved_episode_npz(path: Path, numpy_module: Any) -> BatchValidationResult:
    errors: List[str] = []

    with numpy_module.load(path, allow_pickle=True) as data:
        step_id = data["step_id"]
        done_t = data["done_t"]
        reward_t = data["reward_t"]
        observation_t = data["observation_t"]
        action_t_json = data["action_t_json"]
        action_t_hash = data["action_t_hash"]
        terminal_type_t = data["terminal_type_t"]

        step_count = int(step_id.shape[0])
        required = [
            ("done_t", done_t),
            ("reward_t", reward_t),
            ("observation_t", observation_t),
            ("action_t_json", action_t_json),
            ("action_t_hash", action_t_hash),
            ("terminal_type_t", terminal_type_t),
        ]
        for field_name, array in required:
            if int(array.shape[0]) != step_count:
                errors.append(f"{path.name}: length mismatch after serialization for {field_name}")

        if step_count > 0:
            expected_step_id = numpy_module.arange(step_count)
            if not bool((step_id == expected_step_id).all()):
                errors.append(f"{path.name}: non-contiguous step_id after serialization")

            if not bool(done_t[-1]):
                errors.append(f"{path.name}: last done_t is False after serialization")

            if step_count > 1 and bool(done_t[:-1].any()):
                errors.append(f"{path.name}: done_t contains True before final step after serialization")

            if not bool(numpy_module.isfinite(reward_t).all()):
                errors.append(f"{path.name}: reward_t contains NaN/Inf after serialization")

            if not bool(numpy_module.isfinite(observation_t).all()):
                errors.append(f"{path.name}: observation_t contains NaN/Inf after serialization")

            for index in range(step_count):
                action_json = str(action_t_json[index])
                expected_hash = str(action_t_hash[index])
                actual_hash = sha256_text(action_json)
                if actual_hash != expected_hash:
                    errors.append(
                        f"{path.name}: action hash mismatch after serialization at step {index}"
                    )

    return BatchValidationResult(ok=len(errors) == 0, errors=errors)
