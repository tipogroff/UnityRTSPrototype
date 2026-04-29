# Stage 4 Audit - Legacy032 24x24 Alignment

Date: 2026-04-29
Scope: `python/week5_teacher_reference/patched_paper_scripts/ppo_gridnet_diverse_encode_decode_local_save.py`

## Summary

Reference script is not a pure map-path parameterization problem.
It includes multiple hardcoded 16x16 assumptions in both environment and policy tensor reshaping.

Conclusion:
- Safe Stage 4 path is a separate patched script in legacy032 workspace.
- Reference source must remain unchanged.
- For 24x24 target contract, architecture must be contract-verified and fail-fast when actor output spatial shape does not match env map.

## Hardcoded 16x16 Findings

1. Environment map path hardcoded to 16x16:
- `map_path="maps/16x16/basesWorkers16x16.xml"`

2. Implicit 16x16 map size hardcoded:
- `mapsize = 16 * 16`
- reshape/view paths use literal `256`:
  - `logprob.T.view(-1, 256, num_predicted_parameters)`
  - `entropy.T.view(-1, 256, num_predicted_parameters)`
  - `action.T.view(-1, 256, num_predicted_parameters)`
  - `invalid_action_masks.view(-1, 256, ...)`

3. Decoder output channels hardcoded for 16x16-local contract:
- `Decoder(78)` where 78 = `6+4+4+4+4+7+49`

## MicroRTSGridModeVecEnv and Contract Computation

Reference flow derives runtime shapes from env:
- observation space from `envs.observation_space.shape`
- action branches from `envs.action_space.nvec[1:]`
- masks from `envs.vec_client.getMasks(0)` then split by `envs.action_space.nvec[1:]`

However, hardcoded constants (256 and 78) bypass dynamic map contract and reintroduce 16x16 lock.

## Architecture Dependence on Map Size

Encoder/decoder topology is resolution-sensitive:
- 4x MaxPool2d(stride=2) in encoder
- 4x ConvTranspose2d(stride=2) in decoder

For 16x16 input:
- downsample: 16 -> 8 -> 4 -> 2 -> 1
- upsample: 1 -> 2 -> 4 -> 8 -> 16
- actor spatial output matches env map.

For 24x24 input:
- downsample: 24 -> 12 -> 6 -> 3 -> 2
- upsample: 2 -> 4 -> 8 -> 16 -> 32
- actor spatial output becomes 32x32, not 24x24.

This creates shape incompatibility for action reshaping and invalidates silent map-path-only migration.

## Decoder and Action Contract for 24x24

Target 24x24 gridmode contract requires:
- observation `[24,24,27]`
- action nvec `[576,6,4,4,4,4,7,576]`
- per-cell branch sum for logits split = `6+4+4+4+4+7+576 = 605`

Reference decoder channel count 78 is incompatible with target branch sum 605.
Even if channel count is adjusted dynamically, spatial mismatch (32x32 vs 24x24) can still break tensor views.

## Mask Path Analysis

Mask path is structurally map/action dependent and remains valid conceptually:
- source: `envs.vec_client.getMasks(0)`
- branch split: `torch.split(mask[:,1:], envs.action_space.nvec[1:], dim=1)`
- masked categorical: `torch.where(mask_bool, logits, -1e8)`

If action branch sizes change with map, mask split must follow env nvec dynamically.
This is already dynamic in reference code.

## Can CLI `--map-path` Alone Solve Stage 4?

No.
`--map-path` parameterization alone is insufficient because:
- hardcoded mapsize and view dimensions (256) remain;
- decoder output channels fixed to 78;
- encoder/decoder spatial topology does not preserve 24x24 map resolution.

## Backward Compatibility Requirement

Backward compatibility with 16x16 reference path can be preserved by:
- keeping reference script unchanged;
- creating dedicated patched script under legacy032 workspace;
- keeping reference_internal evaluation mode for historical Stage 3 artifacts.

## Stage 4 Audit Decision

Decision: create separate patched 24x24 script in legacy032 workspace and enforce contract verification with fail-fast report.

Minimal architectural fix proposal (if 24x24 actor shape mismatch occurs):
- Use resolution-aware actor head so output spatial dimensions exactly match env map HxW.
- Example approaches:
  - adaptive pooling in encoder + upsampling/interpolation to env HxW before final logits projection;
  - or remove one pooling/deconv stage and redesign to preserve 24x24.

Do not apply silent implicit reshaping or cropping.
Any mismatch must produce an explicit BLOCKED policy-architecture report.
