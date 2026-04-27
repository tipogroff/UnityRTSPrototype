# Reference vs Project Training Delta

## Purpose
This report compares the successful isolated reference reproduction branch with the current
project-compatible training branch.

The goal is to identify what the reference run proves, what it does not prove, and which
technical deltas are the most plausible explanations for the current behavior gap.

---

## 1. What Reference Proves

The reference branch proves the following:
- the old gym-microrts 0.3.2 stack can be made to run on the current Windows machine
- the original paper-style training recipe can execute end-to-end in an isolated environment
- the policy can reach visible in-game behavior by 100k steps in that isolated setup
- TensorBoard artifacts are produced reliably
- local model saving can be added without wandb by using a patched local copy

Observed successful reference outcomes:
- env verification: PASS
- smoke 10k: PASS
- staged long 100k: PASS
- visible behavior: movement, harvesting, barracks, unit production, attack

---

## 2. What Reference Does NOT Prove

The reference branch does **not** prove:
- Unity parity
- BC readiness
- direct checkpoint compatibility with the current project pipeline
- equivalence of action semantics between old gym-microrts and project-compatible env
- equivalence of observation semantics between old paper env and current project env
- that the existing project-compatible MaskablePPO pipeline is correct except for training budget

A successful reference run is a control experiment, not a drop-in solution.

---

## 3. Key Deltas Likely Responsible for Behavior Difference

### Reference branch
Reference branch characteristics:
- gym_microrts 0.3.2
- paper script env id: `MicrortsDefeatCoacAIShaped-v3`
- reference verify env id: `MicrortsMining-v1`
- verify observation surface: `[10,10,27]`
- verify action space: `MultiDiscrete([100,6,4,4,4,4,7,100])`
- paper training metadata observed at run time:
  - observation surface `[16,16,27]`
  - action space `MultiDiscrete([256,6,4,4,4,4,7,49])`
- Gridnet encoder-decoder architecture
- original paper invalid action masking semantics
- diverse scripted bots with `num_bot_envs=6`
- visible behavior emerged by 100k

### Project-compatible branch
Project-compatible branch characteristics:
- MicroRTS-Py / v0.6.1-compatible env
- observation surface `[24,24,27]`
- action space `[576,7]` at wrapper stage, or Gym raw `[4032]` depending on stage
- MaskablePPO custom wrapper
- behavior gate
- movement_warmup scaffold
- unstable actor-level movement at 10k / 20k

### Most important deltas
The most plausible behavior-affecting deltas are:
- architecture difference: Gridnet encoder-decoder vs current project-compatible policy stack
- invalid action masking semantics differ from the original paper implementation
- action space semantics differ materially
- map size / grid cardinality differ
- training opponents differ
- training budget differs
- checkpoint/eval artifacts were missing in the project branch during early debugging

---

## 4. Which Elements to Port Next

Recommended next ports from reference into the project-compatible branch:
- Gridnet encoder-decoder architecture
- original paper invalid action masking and action semantics mapping
- diverse bot setup
- larger training budget once movement is confirmed locally
- local checkpoint and eval artifact generation as first-class outputs

These are the highest-value hypotheses because they directly affect policy expressiveness,
action validity, and debugging visibility.

---

## 5. Risks

Important risks when interpreting or porting from reference:
- direct checkpoint is not Unity-compatible
- action semantics differ
- grid size differs
- reward/task setup differs
- old env uses different action space
- success in the old stack may rely on assumptions that are absent in the project-compatible stack

Because of these deltas, reference success should be treated as guidance for architecture and
training design, not as evidence that the exact same weights can be reused.

---

## 6. Recommended Next Branch B

Recommended next branch B:
- **project-compatible Gridnet teacher training**

Suggested scope for branch B:
- keep project-compatible env and pipeline boundaries
- introduce Gridnet-style encoder-decoder policy
- re-check invalid action masking against the paper logic
- preserve project-side artifact generation and behavior gate
- add local checkpoints and evaluation artifacts from the start
- do not attempt direct checkpoint reuse from the old reference branch

This gives the cleanest next experiment:
- preserve project compatibility
- import the most likely missing ingredients from the successful reference control
- isolate whether architecture + action semantics + training setup explain the behavior gap

---

## Bottom Line

The reference branch demonstrates that the old paper-style recipe can still produce meaningful
behavior in an isolated control setup.

The project-compatible branch still differs in several behavior-critical ways.
The next rational step is **not** to force direct checkpoint reuse, but to build a
project-compatible Gridnet teacher branch that ports the likely missing ingredients while
preserving the project's env and artifact contracts.
