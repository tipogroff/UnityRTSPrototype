from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Mapping, Tuple

import numpy as np


GRID_H = 24
GRID_W = 24
CELL_COUNT = GRID_H * GRID_W
CHANNELS = 27

RAW_HP = slice(0, 5)
RAW_RESOURCES = slice(5, 10)
RAW_OWNER = slice(10, 13)
RAW_UNIT_TYPE = slice(13, 21)
RAW_ACTION = slice(21, 27)

UNITY_OWNER = slice(2, 5)
UNITY_UNIT_TYPE = slice(5, 12)
UNITY_ACTION = slice(12, 18)
UNITY_DIRECTION = slice(18, 22)
UNITY_PRODUCE = slice(22, 26)

UNITY_CH_HIT_POINTS = 0
UNITY_CH_RESOURCES = 1
UNITY_CH_OWNER_NEUTRAL = 2
UNITY_CH_OWNER_FRIENDLY = 3
UNITY_CH_OWNER_ENEMY = 4
UNITY_CH_UNIT_RESOURCE = 5
UNITY_CH_UNIT_BASE = 6
UNITY_CH_UNIT_BARRACKS = 7
UNITY_CH_UNIT_WORKER = 8
UNITY_CH_UNIT_LIGHT = 9
UNITY_CH_UNIT_HEAVY = 10
UNITY_CH_UNIT_RANGED = 11
UNITY_CH_ACTION_NOOP = 12
UNITY_CH_DIR_SOUTH = 20
UNITY_CH_ATTACK_TARGET = 26


RAW_CHANNELS: Tuple[str, ...] = (
    "hp_bin_0",
    "hp_bin_1",
    "hp_bin_2",
    "hp_bin_3",
    "hp_bin_4_or_more",
    "resource_bin_0",
    "resource_bin_1",
    "resource_bin_2",
    "resource_bin_3",
    "resource_bin_4_or_more",
    "owner_neutral",
    "owner_player0",
    "owner_player1",
    "unit_empty_none",
    "unit_resource",
    "unit_base",
    "unit_barracks",
    "unit_worker",
    "unit_light",
    "unit_heavy",
    "unit_ranged",
    "current_action_noop",
    "current_action_move",
    "current_action_harvest",
    "current_action_return",
    "current_action_produce",
    "current_action_attack",
)

UNITY_CHANNELS: Tuple[str, ...] = (
    "hit_points",
    "resources",
    "owner_neutral",
    "owner_friendly",
    "owner_enemy",
    "unit_resource",
    "unit_base",
    "unit_barracks",
    "unit_worker",
    "unit_light",
    "unit_heavy",
    "unit_ranged",
    "action_noop",
    "action_move",
    "action_harvest",
    "action_return",
    "action_produce",
    "action_attack",
    "dir_north",
    "dir_east",
    "dir_south",
    "dir_west",
    "produce_worker",
    "produce_light",
    "produce_heavy",
    "produce_ranged",
    "attack_target_index",
)


# Raw unit-type local indices inside channels 13..20.
RAW_UT_EMPTY = 0
RAW_UT_RESOURCE = 1
RAW_UT_BASE = 2
RAW_UT_BARRACKS = 3
RAW_UT_WORKER = 4
RAW_UT_LIGHT = 5
RAW_UT_HEAVY = 6
RAW_UT_RANGED = 7


# Unity unit-type local indices inside channels 5..11.
UNITY_UT_RESOURCE = 0
UNITY_UT_BASE = 1
UNITY_UT_BARRACKS = 2
UNITY_UT_WORKER = 3
UNITY_UT_LIGHT = 4
UNITY_UT_HEAVY = 5
UNITY_UT_RANGED = 6


RAW_TO_UNITY_UNIT_LOCAL: Mapping[int, int] = {
    RAW_UT_RESOURCE: UNITY_UT_RESOURCE,
    RAW_UT_BASE: UNITY_UT_BASE,
    RAW_UT_BARRACKS: UNITY_UT_BARRACKS,
    RAW_UT_WORKER: UNITY_UT_WORKER,
    RAW_UT_LIGHT: UNITY_UT_LIGHT,
    RAW_UT_HEAVY: UNITY_UT_HEAVY,
    RAW_UT_RANGED: UNITY_UT_RANGED,
}


# microRTS observations clip HP/resource groups at 4. Normalize full-health
# common unit types to 1.0; damaged values remain coarse approximations.
RAW_FULL_HP_BIN_BY_UNIT_LOCAL: Mapping[int, int] = {
    RAW_UT_RESOURCE: 1,
    RAW_UT_BASE: 4,
    RAW_UT_BARRACKS: 4,
    RAW_UT_WORKER: 1,
    RAW_UT_LIGHT: 4,
    RAW_UT_HEAVY: 4,
    RAW_UT_RANGED: 1,
}


# Unity visual-inspection scene uses horizontal corner resources, while
# gym-microRTS basesWorkers24x24.xml stores the second resource vertically.
UNITY_CORNER_RESOURCE_REMAP: Tuple[Tuple[int, int], ...] = (
    (1 * GRID_W + 0, 0 * GRID_W + 1),      # A2 -> B1
    (22 * GRID_W + 23, 23 * GRID_W + 22),  # X23 -> W24
)

ATTACK_OFFSETS: Tuple[Tuple[int, int], ...] = tuple(
    (dx, dy) for dy in range(-3, 4) for dx in range(-3, 4)
)
ATTACK_CAPABLE_UNITY_LOCAL = {
    UNITY_UT_WORKER,
    UNITY_UT_LIGHT,
    UNITY_UT_HEAVY,
    UNITY_UT_RANGED,
}


@dataclass(frozen=True)
class Legacy032ToUnityV2AdapterConfig:
    """Controls source-to-target semantic adaptation.

    player0 is the acting teacher side in the Legacy032 rollout, so for Unity
    Player1 visual inference raw owner_player0 becomes owner_friendly and
    raw owner_player1 becomes owner_enemy.
    """

    player_perspective: str = "player0"
    default_direction: str = "south"
    apply_unity_corner_resource_layout: bool = True
    derive_representative_attack_target: bool = True


def semantic_mapping_table() -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []

    def add(raw: int | str, raw_meaning: str, target: int | None, target_meaning: str, note: str = "") -> None:
        rows.append(
            {
                "raw_channel_index": raw,
                "raw_meaning": raw_meaning,
                "target_unity_channel_index": target,
                "target_meaning": target_meaning,
                "approximation_or_risk": note,
            }
        )

    add("0..4", "hit point discrete one-hot bin, clipped at 4", 0, "hit_points scalar", "coarse normalized by unit type full HP bin")
    add("5..9", "resource/carry discrete one-hot bin, clipped at 4", 1, "resources scalar", "coarse normalized as bin/4")
    add(10, "absolute owner neutral", 2, "owner_neutral")
    add(11, "absolute owner player0", 3, "owner_friendly / owner_player1 relative to acting player", "exact for Player1-perspective export from player0 teacher")
    add(12, "absolute owner player1", 4, "owner_enemy / owner_player2 relative to acting player", "exact for Player1-perspective export from player0 teacher")
    add(13, "empty/no-unit sentinel", None, "no Unity unit_type channel", "used to suppress unit/action/direction on empty cells")
    add(14, "unit Resource", 5, "unit_resource")
    add(15, "unit Base", 6, "unit_base")
    add(16, "unit Barracks", 7, "unit_barracks")
    add(17, "unit Worker", 8, "unit_worker")
    add(18, "unit Light", 9, "unit_light")
    add(19, "unit Heavy", 10, "unit_heavy")
    add(20, "unit Ranged", 11, "unit_ranged")
    for i, name in enumerate(("NoOp", "Move", "Harvest", "Return", "Produce", "Attack")):
        add(21 + i, f"current action {name}", 12 + i, f"action_{name.lower()}", "copied only for typed cells; empty cells are zero-action")
    add("unavailable", "Legacy032 raw observation has no facing/direction planes", 20, "dir_south", "default south for typed cells, matching Unity early corner fallback")
    add("unavailable", "Legacy032 raw observation has no active produce-unit plane", None, "produce_worker..produce_ranged", "set all zero")
    add("board-derived", "Legacy032 raw observation has no attack target plane", 26, "attack_target_index", "optional representative local 7x7 enemy target derived from board")
    add("layout", "Legacy032 vertical corner resource pair", None, "Unity horizontal corner resource pair", "known map-level static resource remap A2->B1 and X23->W24 when target cell is empty")
    return rows


def _as_flat_obs(raw_observation: np.ndarray) -> Tuple[np.ndarray, Tuple[int, ...]]:
    raw = np.asarray(raw_observation, dtype=np.float32)
    original_shape = tuple(int(v) for v in raw.shape)
    if raw.ndim == 4 and tuple(raw.shape[1:]) == (GRID_H, GRID_W, CHANNELS):
        return raw.reshape(raw.shape[0], CELL_COUNT, CHANNELS), original_shape
    if raw.ndim == 3 and tuple(raw.shape[1:]) == (CELL_COUNT, CHANNELS):
        return raw, original_shape
    if raw.ndim == 3 and tuple(raw.shape) == (GRID_H, GRID_W, CHANNELS):
        return raw.reshape(1, CELL_COUNT, CHANNELS), original_shape
    if raw.ndim == 2 and tuple(raw.shape) == (CELL_COUNT, CHANNELS):
        return raw.reshape(1, CELL_COUNT, CHANNELS), original_shape
    raise ValueError(f"unexpected Legacy032 raw observation shape: {original_shape}")


def _restore_shape(flat: np.ndarray, original_shape: Tuple[int, ...]) -> np.ndarray:
    if len(original_shape) == 4:
        return flat.reshape(original_shape[0], GRID_H, GRID_W, CHANNELS)
    if len(original_shape) == 3 and original_shape == (GRID_H, GRID_W, CHANNELS):
        return flat.reshape(GRID_H, GRID_W, CHANNELS)
    if len(original_shape) == 3:
        return flat
    if len(original_shape) == 2:
        return flat.reshape(CELL_COUNT, CHANNELS)
    return flat


def _one_hot_argmax(block: np.ndarray) -> np.ndarray:
    return np.argmax(block, axis=-1).astype(np.int16, copy=False)


def _group_sum(block: np.ndarray) -> np.ndarray:
    return np.sum(block > 0.5, axis=-1)


def _set_one_hot(out: np.ndarray, base: int, count: int, indices: np.ndarray, mask: np.ndarray) -> None:
    for local in range(count):
        out[..., base + local] = ((indices == local) & mask).astype(np.float32)


def _clear_to_neutral_empty(out: np.ndarray, flat_index: int, sample_mask: np.ndarray) -> None:
    if not bool(np.any(sample_mask)):
        return
    out[sample_mask, flat_index, :] = 0.0
    out[sample_mask, flat_index, UNITY_CH_OWNER_NEUTRAL] = 1.0


def _copy_cell(out: np.ndarray, src_flat: int, dst_flat: int, sample_mask: np.ndarray) -> None:
    if bool(np.any(sample_mask)):
        out[sample_mask, dst_flat, :] = out[sample_mask, src_flat, :]


class Legacy032ToUnityV2SemanticObservationAdapter:
    def __init__(self, config: Legacy032ToUnityV2AdapterConfig | None = None) -> None:
        self.config = config or Legacy032ToUnityV2AdapterConfig()
        if self.config.player_perspective != "player0":
            raise ValueError("only player0 -> Unity Player1/friendly perspective is currently supported")
        if self.config.default_direction != "south":
            raise ValueError("only default_direction='south' is currently supported")

    def adapt(self, raw_observation: np.ndarray, *, restore_input_rank: bool = False) -> np.ndarray:
        flat, original_shape = _as_flat_obs(raw_observation)
        out = self.adapt_flat(flat)
        return _restore_shape(out, original_shape) if restore_input_rank else out

    def adapt_flat(self, raw_flat: np.ndarray) -> np.ndarray:
        raw = np.asarray(raw_flat, dtype=np.float32)
        if raw.ndim != 3 or tuple(raw.shape[1:]) != (CELL_COUNT, CHANNELS):
            raise ValueError(f"expected raw_flat [N,576,27], got {list(raw.shape)}")

        n = int(raw.shape[0])
        out = np.zeros((n, CELL_COUNT, CHANNELS), dtype=np.float32)

        hp_bin = _one_hot_argmax(raw[..., RAW_HP])
        res_bin = _one_hot_argmax(raw[..., RAW_RESOURCES])
        owner_idx = _one_hot_argmax(raw[..., RAW_OWNER])
        raw_unit_idx = _one_hot_argmax(raw[..., RAW_UNIT_TYPE])
        raw_action_idx = _one_hot_argmax(raw[..., RAW_ACTION])

        typed = raw_unit_idx != RAW_UT_EMPTY

        # Scalars.
        full_hp = np.full_like(hp_bin, 4, dtype=np.int16)
        for raw_unit, full_bin in RAW_FULL_HP_BIN_BY_UNIT_LOCAL.items():
            full_hp[raw_unit_idx == int(raw_unit)] = int(full_bin)
        out[..., UNITY_CH_HIT_POINTS] = np.where(
            typed,
            np.clip(hp_bin.astype(np.float32) / np.maximum(full_hp.astype(np.float32), 1.0), 0.0, 1.0),
            0.0,
        )
        out[..., UNITY_CH_RESOURCES] = np.where(
            typed,
            np.clip(res_bin.astype(np.float32) / 4.0, 0.0, 1.0),
            0.0,
        )

        # Owner is present for every cell in both raw and Unity contract.
        out[..., UNITY_CH_OWNER_NEUTRAL] = (owner_idx == 0).astype(np.float32)
        out[..., UNITY_CH_OWNER_FRIENDLY] = (owner_idx == 1).astype(np.float32)
        out[..., UNITY_CH_OWNER_ENEMY] = (owner_idx == 2).astype(np.float32)

        unity_unit_idx = np.full_like(raw_unit_idx, -1, dtype=np.int16)
        for raw_local, unity_local in RAW_TO_UNITY_UNIT_LOCAL.items():
            unity_unit_idx[raw_unit_idx == int(raw_local)] = int(unity_local)
        _set_one_hot(out, UNITY_CH_UNIT_RESOURCE, 7, unity_unit_idx, typed)

        # Runtime current-action is a state feature. Copy the raw unit-action group
        # for occupied cells; leave empty cells all-zero like Unity runtime empties.
        _set_one_hot(out, UNITY_CH_ACTION_NOOP, 6, raw_action_idx, typed)

        # Legacy032 has no facing/direction plane. Unity early corner states use
        # south as the fallback facing for typed entities.
        out[..., UNITY_CH_DIR_SOUTH] = typed.astype(np.float32)

        if self.config.derive_representative_attack_target:
            self._fill_representative_attack_target(out, unity_unit_idx)

        if self.config.apply_unity_corner_resource_layout:
            self._apply_known_corner_resource_layout(out, raw_unit_idx)

        np.clip(out, 0.0, 1.0, out=out)
        self.assert_semantic_sane(out)
        return out

    def _apply_known_corner_resource_layout(self, out: np.ndarray, raw_unit_idx: np.ndarray) -> None:
        for src_flat, dst_flat in UNITY_CORNER_RESOURCE_REMAP:
            src_is_resource = raw_unit_idx[:, src_flat] == RAW_UT_RESOURCE
            dst_is_empty = raw_unit_idx[:, dst_flat] == RAW_UT_EMPTY
            move_mask = src_is_resource & dst_is_empty
            _copy_cell(out, src_flat, dst_flat, move_mask)
            _clear_to_neutral_empty(out, src_flat, move_mask)

    def _fill_representative_attack_target(self, out: np.ndarray, unity_unit_idx: np.ndarray) -> None:
        owner = out[..., UNITY_OWNER]
        friendly = owner[..., 1] > 0.5
        enemy = owner[..., 2] > 0.5
        attack_capable = np.isin(unity_unit_idx, list(ATTACK_CAPABLE_UNITY_LOCAL)) & friendly

        for flat in range(CELL_COUNT):
            actor_samples = np.where(attack_capable[:, flat])[0]
            if actor_samples.size == 0:
                continue
            y, x = divmod(flat, GRID_W)
            for local_index, (dx, dy) in enumerate(ATTACK_OFFSETS):
                tx = x + dx
                ty = y + dy
                if tx < 0 or tx >= GRID_W or ty < 0 or ty >= GRID_H:
                    continue
                if dx == 0 and dy == 0:
                    continue
                target_flat = ty * GRID_W + tx
                hits = actor_samples[enemy[actor_samples, target_flat]]
                if hits.size == 0:
                    continue
                unset = out[hits, flat, UNITY_CH_ATTACK_TARGET] == 0.0
                if bool(np.any(unset)):
                    out[hits[unset], flat, UNITY_CH_ATTACK_TARGET] = (local_index + 1.0) / 49.0

    @staticmethod
    def assert_semantic_sane(obs: np.ndarray) -> None:
        arr = np.asarray(obs, dtype=np.float32)
        if arr.ndim != 3 or tuple(arr.shape[1:]) != (CELL_COUNT, CHANNELS):
            raise AssertionError(f"expected adapted obs [N,576,27], got {list(arr.shape)}")
        if bool(np.isnan(arr).any()) or bool(np.isinf(arr).any()):
            raise AssertionError("adapted observation contains NaN/Inf")
        if float(arr.min()) < -1e-6 or float(arr.max()) > 1.000001:
            raise AssertionError(f"adapted observation outside [0,1]: min={arr.min()} max={arr.max()}")

        groups: Iterable[Tuple[str, slice]] = (
            ("owner", UNITY_OWNER),
            ("unit_type", UNITY_UNIT_TYPE),
            ("current_action", UNITY_ACTION),
            ("direction", UNITY_DIRECTION),
            ("produce", UNITY_PRODUCE),
        )
        for name, sl in groups:
            sums = _group_sum(arr[..., sl])
            if int(np.count_nonzero(sums > 1)) != 0:
                raise AssertionError(f"{name} group has multi-hot cells")

        unit = arr[..., UNITY_UNIT_TYPE] > 0.5
        if int(np.count_nonzero(unit[..., UNITY_UT_RESOURCE] & unit[..., UNITY_UT_RANGED])) != 0:
            raise AssertionError("impossible unit combination: resource + ranged")

        first = arr[0]
        def _is(flat: int, ch: int) -> bool:
            return bool(first[flat, ch] > 0.5)

        if not (_is(25, UNITY_CH_OWNER_FRIENDLY) and _is(25, UNITY_CH_UNIT_WORKER)):
            raise AssertionError("early corner B2 must decode as friendly Worker")
        if not (_is(50, UNITY_CH_OWNER_FRIENDLY) and _is(50, UNITY_CH_UNIT_BASE)):
            raise AssertionError("early corner C3 must decode as friendly Base")
        if not (_is(0, UNITY_CH_OWNER_NEUTRAL) and _is(0, UNITY_CH_UNIT_RESOURCE)):
            raise AssertionError("early corner A1 must decode as neutral Resource")
        if not (_is(1, UNITY_CH_OWNER_NEUTRAL) and _is(1, UNITY_CH_UNIT_RESOURCE)):
            raise AssertionError("early corner B1 must decode as neutral Resource")


def adapt_legacy032_observation_to_unity_v2(
    raw_observation: np.ndarray,
    *,
    config: Legacy032ToUnityV2AdapterConfig | None = None,
    restore_input_rank: bool = False,
) -> np.ndarray:
    return Legacy032ToUnityV2SemanticObservationAdapter(config).adapt(
        raw_observation,
        restore_input_rank=restore_input_rank,
    )

