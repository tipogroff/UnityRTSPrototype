from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Sequence

import numpy as np

from student_bc_contract import (
    BCContractError,
    LoadedBCDataset,
    ManifestContract,
    REQUIRED_SPLITS,
    SUPPORTED_SCHEMA_VERSIONS,
    SplitData,
)


_CANONICAL_FILES: dict[str, str] = {
    "manifest": "bc_manifest.json",
    "train": "bc_train.npz",
    "validation": "bc_validation.npz",
}

_REQUIRED_ARRAY_KEYS: tuple[str, ...] = (
    "input_tensor",
    "target_action_branches",
    "sample_id",
    "episode_id",
    "step_id",
    "source_episode_file",
    "target_action_branch_sizes",
    "schema_version",
    "split",
)


def _read_json(path: Path) -> Mapping[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise BCContractError(f"Invalid JSON at {path}: {exc}") from exc


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise BCContractError(message)


def _as_tuple_of_ints(value: Any, field_name: str) -> tuple[int, ...]:
    if not isinstance(value, list) or len(value) == 0:
        raise BCContractError(f"Manifest field '{field_name}' must be a non-empty list of ints")
    ints: list[int] = []
    for idx, item in enumerate(value):
        if not isinstance(item, int):
            raise BCContractError(
                f"Manifest field '{field_name}' must contain ints; index {idx} has {type(item).__name__}"
            )
        ints.append(int(item))
    return tuple(ints)


def _load_manifest_contract(manifest: Mapping[str, Any]) -> ManifestContract:
    schema_version = str(manifest.get("schema_version", "")).strip()
    _require(schema_version in SUPPORTED_SCHEMA_VERSIONS, f"Unsupported schema_version: '{schema_version}'")

    sample_structure = (
        manifest.get("schema", {})
        .get("sample_structure", {})
    )
    required_section = sample_structure.get("required", {})

    input_spec = required_section.get("input_tensor")
    target_spec = required_section.get("target_action_branches")
    metadata_spec = required_section.get("metadata")

    _require(isinstance(input_spec, Mapping), "Manifest missing schema.sample_structure.required.input_tensor")
    _require(
        isinstance(target_spec, Mapping),
        "Manifest missing schema.sample_structure.required.target_action_branches",
    )
    _require(isinstance(metadata_spec, Mapping), "Manifest missing schema.sample_structure.required.metadata")

    input_dtype = str(input_spec.get("dtype", "")).strip()
    target_dtype = str(target_spec.get("dtype", "")).strip()
    _require(input_dtype != "", "Manifest input_tensor.dtype is empty")
    _require(target_dtype != "", "Manifest target_action_branches.dtype is empty")

    input_shape_per_sample = _as_tuple_of_ints(input_spec.get("shape"), "input_tensor.shape")
    target_shape_per_sample = _as_tuple_of_ints(target_spec.get("shape"), "target_action_branches.shape")
    target_branch_sizes = _as_tuple_of_ints(
        target_spec.get("branch_sizes"),
        "target_action_branches.branch_sizes",
    )

    target_branch_names = (
        "action_type",
        "move_dir",
        "harvest_dir",
        "return_dir",
        "produce_dir",
        "produce_unit_type",
        "attack_target_local",
    )
    _require(
        len(target_branch_names) == len(target_branch_sizes),
        (
            "Branch name count must match branch size count. "
            f"names={len(target_branch_names)} sizes={len(target_branch_sizes)}"
        ),
    )

    optional_mask = sample_structure.get("optional", {}).get("optional_mask", {})
    optional_mask_declared_present: Optional[bool] = None
    optional_mask_note: Optional[str] = None
    if isinstance(optional_mask, Mapping):
        present = optional_mask.get("present")
        if isinstance(present, bool):
            optional_mask_declared_present = present
        note = optional_mask.get("note")
        if note is not None:
            optional_mask_note = str(note)

    required_metadata_keys = tuple(sorted(str(k) for k in metadata_spec.keys()))
    diagnostic_only_raw = sample_structure.get("diagnostic_only", {})
    diagnostic_only_keys: tuple[str, ...]
    if isinstance(diagnostic_only_raw, Mapping):
        diagnostic_only_keys = tuple(sorted(str(k) for k in diagnostic_only_raw.keys()))
    else:
        diagnostic_only_keys = ()

    return ManifestContract(
        schema_version=schema_version,
        input_key="input_tensor",
        input_dtype=input_dtype,
        input_shape_per_sample=input_shape_per_sample,
        target_key="target_action_branches",
        target_dtype=target_dtype,
        target_shape_per_sample=target_shape_per_sample,
        target_branch_sizes=target_branch_sizes,
        target_branch_names=target_branch_names,
        optional_mask_declared_present=optional_mask_declared_present,
        optional_mask_note=optional_mask_note,
        required_metadata_keys=required_metadata_keys,
        diagnostic_only_keys=diagnostic_only_keys,
    )


def _require_split_path_consistency(run_dir: Path, manifest: Mapping[str, Any]) -> None:
    split_files = manifest.get("split_files", {})
    _require(isinstance(split_files, Mapping), "Manifest field 'split_files' is missing or invalid")

    for split_name in REQUIRED_SPLITS:
        _require(split_name in split_files, f"Manifest missing split_files.{split_name}")
        manifest_path_raw = split_files[split_name]
        _require(
            isinstance(manifest_path_raw, str) and manifest_path_raw.strip() != "",
            f"Manifest split_files.{split_name} must be non-empty string",
        )

        manifest_path = Path(manifest_path_raw)
        canonical_path = run_dir / _CANONICAL_FILES[split_name]

        _require(
            manifest_path.resolve(strict=False) == canonical_path.resolve(strict=False),
            (
                f"Manifest split_files.{split_name} path mismatch: "
                f"expected {canonical_path}, got {manifest_path}"
            ),
        )


def _extract_single_string(array: np.ndarray, key: str, split_name: str) -> str:
    flat = np.asarray(array).reshape(-1)
    _require(flat.size == 1, f"{split_name}: '{key}' must contain exactly one string value")
    return str(flat[0])


def _validate_metadata_lengths(split_name: str, n: int, arrays: Mapping[str, np.ndarray]) -> None:
    for key in ("sample_id", "episode_id", "step_id", "source_episode_file"):
        _require(
            arrays[key].shape[0] == n,
            f"{split_name}: '{key}' length mismatch; expected {n}, got {arrays[key].shape[0]}",
        )


def _validate_optional_mask(
    split_name: str,
    arrays: Mapping[str, np.ndarray],
    target_shape: tuple[int, ...],
) -> tuple[Optional[np.ndarray], Optional[bool]]:
    has_optional_mask_flag: Optional[bool] = None
    if "has_optional_mask" in arrays:
        has_optional_mask_flag = bool(np.asarray(arrays["has_optional_mask"]).reshape(-1)[0])

    has_optional_mask_array = "optional_mask" in arrays
    if has_optional_mask_flag is True and not has_optional_mask_array:
        raise BCContractError(
            f"{split_name}: has_optional_mask=true but optional_mask array is missing"
        )
    if has_optional_mask_flag is False and has_optional_mask_array:
        raise BCContractError(
            f"{split_name}: has_optional_mask=false but optional_mask array is present"
        )

    if not has_optional_mask_array:
        return None, has_optional_mask_flag

    optional_mask = np.asarray(arrays["optional_mask"])
    _require(
        optional_mask.shape == target_shape,
        (
            f"{split_name}: optional_mask shape mismatch; "
            f"expected {target_shape}, got {optional_mask.shape}"
        ),
    )
    _require(
        optional_mask.dtype == np.bool_,
        f"{split_name}: optional_mask dtype must be bool, got {optional_mask.dtype}",
    )
    return optional_mask, has_optional_mask_flag


def _load_split(
    split_name: str,
    path: Path,
    contract: ManifestContract,
    manifest: Mapping[str, Any],
) -> SplitData:
    with np.load(path, allow_pickle=False) as npz_data:
        arrays: Dict[str, np.ndarray] = {k: np.asarray(npz_data[k]) for k in npz_data.files}

    missing = [k for k in _REQUIRED_ARRAY_KEYS if k not in arrays]
    _require(not missing, f"{split_name}: missing required arrays: {missing}")

    input_tensor = arrays["input_tensor"]
    target = arrays["target_action_branches"]

    _require(input_tensor.ndim == 4, f"{split_name}: input_tensor must be 4D, got ndim={input_tensor.ndim}")
    _require(target.ndim == 3, f"{split_name}: target_action_branches must be 3D, got ndim={target.ndim}")

    _require(
        tuple(input_tensor.shape[1:]) == contract.input_shape_per_sample,
        (
            f"{split_name}: input_tensor sample shape mismatch; "
            f"expected {contract.input_shape_per_sample}, got {tuple(input_tensor.shape[1:])}"
        ),
    )
    _require(
        tuple(target.shape[1:]) == contract.target_shape_per_sample,
        (
            f"{split_name}: target_action_branches sample shape mismatch; "
            f"expected {contract.target_shape_per_sample}, got {tuple(target.shape[1:])}"
        ),
    )

    _require(
        str(input_tensor.dtype) == contract.input_dtype,
        f"{split_name}: input_tensor dtype mismatch; expected {contract.input_dtype}, got {input_tensor.dtype}",
    )
    _require(
        str(target.dtype) == contract.target_dtype,
        (
            f"{split_name}: target_action_branches dtype mismatch; "
            f"expected {contract.target_dtype}, got {target.dtype}"
        ),
    )

    n = int(input_tensor.shape[0])
    _require(target.shape[0] == n, f"{split_name}: input/target sample count mismatch")

    _validate_metadata_lengths(split_name=split_name, n=n, arrays=arrays)

    branch_sizes = arrays["target_action_branch_sizes"]
    _require(branch_sizes.ndim == 1, f"{split_name}: target_action_branch_sizes must be 1D")
    _require(
        target.shape[2] == branch_sizes.shape[0],
        (
            f"{split_name}: branch count mismatch between target_action_branches and "
            f"target_action_branch_sizes ({target.shape[2]} vs {branch_sizes.shape[0]})"
        ),
    )
    _require(
        tuple(int(x) for x in branch_sizes.tolist()) == contract.target_branch_sizes,
        (
            f"{split_name}: target_action_branch_sizes mismatch; "
            f"expected {contract.target_branch_sizes}, got {tuple(int(x) for x in branch_sizes.tolist())}"
        ),
    )

    split_in_file = _extract_single_string(arrays["split"], key="split", split_name=split_name)
    _require(
        split_in_file == split_name,
        f"{split_name}: split marker mismatch; file has '{split_in_file}'",
    )

    schema_version_in_file = _extract_single_string(
        arrays["schema_version"],
        key="schema_version",
        split_name=split_name,
    )
    _require(
        schema_version_in_file == contract.schema_version,
        (
            f"{split_name}: schema_version mismatch; "
            f"manifest={contract.schema_version}, file={schema_version_in_file}"
        ),
    )

    optional_mask, has_optional_mask_flag = _validate_optional_mask(
        split_name=split_name,
        arrays=arrays,
        target_shape=tuple(target.shape),
    )

    diagnostic_arrays: dict[str, np.ndarray] = {}
    for key in ("diagnostic_reward_t", "diagnostic_done_t"):
        if key in arrays:
            arr = arrays[key]
            _require(
                arr.shape[0] == n,
                f"{split_name}: {key} length mismatch; expected {n}, got {arr.shape[0]}",
            )
            diagnostic_arrays[key] = arr

    manifest_mask_present: Optional[bool] = None
    split_summary = manifest.get("split_summary", {})
    if isinstance(split_summary, Mapping) and split_name in split_summary:
        marker = split_summary.get(split_name, {}).get("mask_present")
        if isinstance(marker, bool):
            manifest_mask_present = marker

    return SplitData(
        split_name=split_name,
        path=path,
        input_tensor=input_tensor,
        target_action_branches=target,
        sample_id=arrays["sample_id"],
        episode_id=arrays["episode_id"],
        step_id=arrays["step_id"],
        source_episode_file=arrays["source_episode_file"],
        target_action_branch_sizes=branch_sizes,
        optional_mask=optional_mask,
        has_optional_mask_flag=has_optional_mask_flag,
        diagnostic_arrays=diagnostic_arrays,
        manifest_mask_present=manifest_mask_present,
        schema_version_from_file=schema_version_in_file,
    )


def _validate_split_consistency(train: SplitData, validation: SplitData, contract: ManifestContract) -> None:
    _require(
        tuple(train.input_tensor.shape[1:]) == tuple(validation.input_tensor.shape[1:]),
        "train/validation input sample shapes are inconsistent",
    )
    _require(
        tuple(train.target_action_branches.shape[1:]) == tuple(validation.target_action_branches.shape[1:]),
        "train/validation target sample shapes are inconsistent",
    )
    _require(
        str(train.input_tensor.dtype) == str(validation.input_tensor.dtype),
        "train/validation input dtypes are inconsistent",
    )
    _require(
        str(train.target_action_branches.dtype) == str(validation.target_action_branches.dtype),
        "train/validation target dtypes are inconsistent",
    )

    train_branch_sizes = tuple(int(x) for x in train.target_action_branch_sizes.tolist())
    val_branch_sizes = tuple(int(x) for x in validation.target_action_branch_sizes.tolist())
    _require(
        train_branch_sizes == val_branch_sizes,
        "train/validation branch size vectors are inconsistent",
    )
    _require(
        train_branch_sizes == contract.target_branch_sizes,
        "branch size vectors do not match manifest contract",
    )


def _validate_manifest_vs_splits(
    train: SplitData,
    validation: SplitData,
    contract: ManifestContract,
    manifest: Mapping[str, Any],
) -> None:
    split_summary = manifest.get("split_summary", {})
    if not isinstance(split_summary, Mapping):
        return

    for split_name, split_data in (("train", train), ("validation", validation)):
        summary = split_summary.get(split_name)
        if not isinstance(summary, Mapping):
            continue

        samples = summary.get("samples")
        if isinstance(samples, int):
            _require(
                split_data.samples == samples,
                f"{split_name}: sample count mismatch vs manifest split_summary ({split_data.samples} vs {samples})",
            )

        shape = summary.get("input_tensor_shape")
        if isinstance(shape, list):
            _require(
                tuple(int(x) for x in shape) == tuple(split_data.input_tensor.shape),
                f"{split_name}: input_tensor shape mismatch vs manifest split_summary",
            )

        target_shape = summary.get("target_action_branches_shape")
        if isinstance(target_shape, list):
            _require(
                tuple(int(x) for x in target_shape) == tuple(split_data.target_action_branches.shape),
                f"{split_name}: target_action_branches shape mismatch vs manifest split_summary",
            )

        expected_mask_present = summary.get("mask_present")
        if isinstance(expected_mask_present, bool):
            _require(
                split_data.mask_available == expected_mask_present,
                (
                    f"{split_name}: mask availability mismatch vs manifest split_summary "
                    f"({split_data.mask_available} vs {expected_mask_present})"
                ),
            )

    if contract.optional_mask_declared_present is not None:
        expected = contract.optional_mask_declared_present
        actual_any = train.mask_available or validation.mask_available
        _require(
            expected == actual_any,
            (
                "Manifest optional_mask declared presence mismatch: "
                f"declared={expected}, actual_any_split={actual_any}"
            ),
        )


def _collect_manifest_warnings(manifest: Mapping[str, Any]) -> list[str]:
    warnings: list[str] = []
    readiness = manifest.get("supervised_target_readiness", {})
    if isinstance(readiness, Mapping):
        items = readiness.get("warnings")
        if isinstance(items, Sequence) and not isinstance(items, (str, bytes)):
            warnings.extend(str(item) for item in items)
    return warnings


def load_bc_ready_dataset(run_dir: Path) -> LoadedBCDataset:
    """Load canonical Week 5 BC-ready train/validation artifacts for Week 6 student-side usage.

    This loader intentionally reads only BC-ready artifacts and fails on contract mismatch.
    It does not read raw rollouts or adapted batch artifacts and performs no schema remapping.
    """
    run_dir = run_dir.resolve()
    _require(run_dir.exists() and run_dir.is_dir(), f"BC-ready run directory does not exist: {run_dir}")

    manifest_path = run_dir / _CANONICAL_FILES["manifest"]
    train_path = run_dir / _CANONICAL_FILES["train"]
    val_path = run_dir / _CANONICAL_FILES["validation"]

    for path in (manifest_path, train_path, val_path):
        _require(path.exists(), f"Missing required file: {path}")

    manifest = _read_json(manifest_path)
    contract = _load_manifest_contract(manifest)
    _require_split_path_consistency(run_dir=run_dir, manifest=manifest)

    train = _load_split(split_name="train", path=train_path, contract=contract, manifest=manifest)
    validation = _load_split(split_name="validation", path=val_path, contract=contract, manifest=manifest)

    _validate_split_consistency(train=train, validation=validation, contract=contract)
    _validate_manifest_vs_splits(train=train, validation=validation, contract=contract, manifest=manifest)
    warnings = _collect_manifest_warnings(manifest)

    return LoadedBCDataset(
        run_dir=run_dir,
        manifest_path=manifest_path,
        train=train,
        validation=validation,
        contract=contract,
        manifest_payload=manifest,
        manifest_diagnostic_warnings=warnings,
    )
