#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Literal

OwnerMode = Literal["absolute_player_channels", "perspective_friendly_enemy"]


def resolve_owner_mode_from_snapshot(snapshot_path: Path) -> OwnerMode:
    payload = json.loads(snapshot_path.read_text(encoding="utf-8-sig"))
    raw = str(payload.get("owner_encoding_mode", "")).strip().lower()
    if raw == "friendly_enemy":
        return "perspective_friendly_enemy"
    return "absolute_player_channels"


def owner_labels_for_mode(mode: OwnerMode) -> List[str]:
    if mode == "perspective_friendly_enemy":
        return ["neutral", "friendly", "enemy"]
    return ["neutral", "player1", "player2"]


def interpret_owner(owner_slice: List[float], mode: OwnerMode) -> str:
    labels = owner_labels_for_mode(mode)
    argmax_idx = max(range(3), key=lambda i: owner_slice[i])
    return labels[argmax_idx]


def normalize_owner_modes(mode_arg: str, inferred_mode: OwnerMode) -> List[OwnerMode]:
    mode_arg = (mode_arg or "both").strip().lower()
    if mode_arg == "absolute_player_channels":
        return ["absolute_player_channels"]
    if mode_arg == "perspective_friendly_enemy":
        return ["perspective_friendly_enemy"]
    if mode_arg == "auto":
        return [inferred_mode]
    # both
    return ["absolute_player_channels", "perspective_friendly_enemy"]
