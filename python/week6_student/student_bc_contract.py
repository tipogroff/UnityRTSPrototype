from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterator, Mapping, Optional, Sequence, Tuple

import numpy as np


SUPPORTED_SCHEMA_VERSIONS: frozenset[str] = frozenset({"day6.bc_ready.v1"})
REQUIRED_SPLITS: tuple[str, str] = ("train", "validation")


class BCContractError(RuntimeError):
    """Raised when BC-ready artifacts violate the student-side contract."""


@dataclass(frozen=True)
class ManifestContract:
    schema_version: str
    input_key: str
    input_dtype: str
    input_shape_per_sample: tuple[int, ...]
    target_key: str
    target_dtype: str
    target_shape_per_sample: tuple[int, ...]
    target_branch_sizes: tuple[int, ...]
    target_branch_names: tuple[str, ...]
    optional_mask_declared_present: Optional[bool]
    optional_mask_note: Optional[str]
    required_metadata_keys: tuple[str, ...]
    diagnostic_only_keys: tuple[str, ...]


@dataclass(frozen=True)
class SplitData:
    split_name: str
    path: Path
    input_tensor: np.ndarray
    target_action_branches: np.ndarray
    sample_id: np.ndarray
    episode_id: np.ndarray
    step_id: np.ndarray
    source_episode_file: np.ndarray
    target_action_branch_sizes: np.ndarray
    optional_mask: Optional[np.ndarray]
    has_optional_mask_flag: Optional[bool]
    diagnostic_arrays: Mapping[str, np.ndarray]
    manifest_mask_present: Optional[bool]
    schema_version_from_file: str

    @property
    def samples(self) -> int:
        return int(self.input_tensor.shape[0])

    @property
    def mask_available(self) -> bool:
        return self.optional_mask is not None

    def iter_batches(self, batch_size: int) -> Iterator["BatchSlice"]:
        if batch_size <= 0:
            raise ValueError(f"batch_size must be > 0, got {batch_size}")
        n = self.samples
        for start in range(0, n, batch_size):
            stop = min(start + batch_size, n)
            yield BatchSlice(
                split_name=self.split_name,
                start_index=start,
                stop_index=stop,
                input_tensor=self.input_tensor[start:stop],
                target_action_branches=self.target_action_branches[start:stop],
                optional_mask=(None if self.optional_mask is None else self.optional_mask[start:stop]),
                sample_id=self.sample_id[start:stop],
            )


@dataclass(frozen=True)
class BatchSlice:
    split_name: str
    start_index: int
    stop_index: int
    input_tensor: np.ndarray
    target_action_branches: np.ndarray
    optional_mask: Optional[np.ndarray]
    sample_id: np.ndarray


@dataclass(frozen=True)
class LoadedBCDataset:
    run_dir: Path
    manifest_path: Path
    train: SplitData
    validation: SplitData
    contract: ManifestContract
    manifest_payload: Mapping[str, Any]
    manifest_diagnostic_warnings: Sequence[str]

    @property
    def split_map(self) -> Dict[str, SplitData]:
        return {
            "train": self.train,
            "validation": self.validation,
        }
