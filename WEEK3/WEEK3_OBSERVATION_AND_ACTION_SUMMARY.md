# Week 3: Observation и Action Contract — Итоговый Summary

**Дата:** 29 марта 2026 (Финализация 2 апреля)  
**Статус:** ✅ ЗАВЕРШЕНА как documented engineering layer  
**Область:** ML Agent Interface — observation contract, action contract, invalid action masking, pipeline validation  

---

## I. Обзор Week 3

Week 3 завершена как **documented ML-facing interface layer** между runtime и будущей policy (heuristic/ML/test drivers).

### Основные артефакты Week 3:

1. **Observation Contract (27 channels)**
   - Spatial: 24×24 grid, 27 channels per cell
   - Global: optional 10-dim feature vector
   - Two-layer model: LegacyGymCompatibleSpec (reference) vs UnityMvpTransferSpec (Unity adaptation)

2. **Action Contract (7 branches)**
   - Per-cell: NoOp, Move, Harvest, Return, Produce, Attack
   - Move, Harvest, Return, Produce: 4 directions each
   - Attack: local 3×3 targeting (8 neighbors)
   - Total flat size: 35 branches per cell, 576 cells × 35 = 20160 flat actions

3. **Invalid Action Masking**
   - Pre-sampling layer (does not replace runtime validation)
   - Per-actor, per-action-type, per-parameter masks
   - Gym-compatible + Unity-only rules properly separated

4. **Heuristic Policy Adapter**
   - Reference implementation (economy-first + combat fallback)
   - Uses canonical pipeline (observation → mask → decision → decoder → applier)
   - Diagnostic tool for pipeline validation

5. **Two-Layer Contract Model**
   - LegacyGymCompatibleSpec: reference-compatible layer (Gym-μRTS v0.6.1 alignment)
   - UnityMvpTransferSpec: practical Unity adaptation (extra global features, local 3x3 attack)
   - Documented differences for transfer experiments

### Ограничения (честно)

- Attack targeting ограничена local 3×3 (deliberate v1 reduction)
- Global feature vector только в UnityMvpTransferSpec (не в reference layer)
- Action space reduced vs full Gym-μRTS (only 6 action types, MVP producibles)
- Combat semantics partial (intent encoding, not outcome guarantee)
- Compatibility gaps: 6 known, documented в WEEK3_COMPATIBILITY_GAP_LIST.md

### Что Week 3 НЕ делает

- ❌ Не обучает ML policy (только контрол + heuristic reference)
- ❌ Не доказывает full transfer parity (только контракт совместимость)
- ❌ Не решает все combat-semantics gap'ы (явно задокументированы 6 gap'ов)
- ❌ Не расширяет action space за пределы MVP (deliberate scope)

---

## II. Observation Contract

### 2.1 Spatial Tensor

**Shape:** [24, 24, 27] (height × width × channels)  
**Data type:** float32  
**Range:** [0, 1] (normalized)  
**Flatten order:** Row-major by cell, then channel  
```
flat_index = (row * 24 + col) * 27 + channel
```

### 2.2 Channel Order (27 channels)

| Идентификатор | Назначение | Тип | Семантика |
|----------------|-----------|-----|-----------|
| [0] | Hit Points | Scalar | Нормализовано [0, 1] |
| [1] | Resources | Scalar | Нормализовано [0, 1] |
| [2-4] | Owner | One-hot | Neutral / Player1 / Player2 |
| [5-11] | Unit Type | One-hot | Resource / Base / Barracks / Worker / Light / Heavy / Ranged |
| [12-17] | Action Type | One-hot | NoOp / Move / Harvest / Return / Produce / Attack |
| [18-21] | Direction | One-hot | North / East / South / West |
| [22-25] | Produce Type | One-hot | Worker / Light / Heavy / Ranged |
| [26] | Attack Target Index | Scalar | Normalized [0, 1] или 0 (no target), encoded в 3×3 local grid |

### 2.3 Two-Layer Model: LegacyGymCompatibleSpec vs UnityMvpTransferSpec

#### LegacyGymCompatibleSpec (Reference-Compatible)
- **Назначение:** Transfer baseline, Gym-μRTS v0.6.1 alignment
- **Content:** Spatial tensor only, channels as above, mode labels explicit
- **One-hot encoding:** agent-agnostic (relative friendly/enemy from requesting player)
- **Attack channel [26]:** placeholder-compatible (0.0 typically, since local 3×3 not in reference)
- **Global features:** absent (NOT included)

#### UnityMvpTransferSpec (Unity Practical Adaptation)
- **Назначение:** Actual Unity runtime surface, transfer adapter interface
- **Content:** Spatial tensor (same 27 channels) + optional Global vector [10]
- **One-hot encoding:** same as LegacyGymCompatibleSpec
- **Attack channel [26]:** tactical enemy-presence signal in local 3×3 (reserved for future per-cell attack mask)
- **Global features:** [10D] optional vector encoding:
  - step_norm: normalized progress (step / max_steps)
  - remaining_norm: inverse progress
  - own_resource_share, enemy_resource_share: resource ratio
  - own_unit_share, enemy_unit_share: unit count ratio
  - own_base_alive, enemy_base_alive: binary flags
  - invalid_rate_last_step: rejection rate
  - pending_commands_norm: queued action density

**Key difference:** UnityMvpTransferSpec includes global features for runtime diagnostics; LegacyGymCompatibleSpec must zero-fill if asked for them.

### 2.4 Observation Building Flow

```
ObservationBuilder.BuildObservation(playerId, mode)
  ├─ Iterate all cells [0..23, 0..23]
  ├─ For each cell:
  │  ├─ Read runtime state (UnitRuntime, ResourceNode, GridManager)
  │  ├─ Encode [0]: hit_points / unit.MaxHP
  │  ├─ Encode [1]: resources / max_resources
  │  ├─ Encode [2-4]: owner one-hot (relative to playerId)
  │  ├─ Encode [5-11]: unit_type one-hot
  │  ├─ Encode [12-17]: action_type one-hot (from ActionContract)
  │  ├─ Encode [18-21]: direction one-hot
  │  ├─ Encode [22-25]: produce_type one-hot
  │  └─ Encode [26]: attack_target_index (mode-dependent)
  └─ Return flat [15552] (if mode==LegacyGymCompatible)
  
ObservationBuilder.BuildGlobalFeatures(mode)
  └─ If mode==UnityMvpTransfer: return [10] global vector
  └─ If mode==LegacyGymCompatible: return zero-filled [10] (for API consistency)
```

### 2.5 Authority and Semantics

- **Runtime truth:** GridManager, UnitRegistry, ResourceManager, BuildingRuntime (production queue)
- **Observation derivation:** deterministic snapshot from runtime state
- **Timestep:** observation captured PRE-action, reflects state_{t}
- **Normalization:** all channels [0, 1], determined by GameConstants (max HP, max resources, etc.)

---

## III. Action Contract

### 3.1 Action Space Structure

**Per-cell:** 7 branches (decision tree)

| Branch | Parameters | Values | Size | Purpose |
|--------|-----------|--------|------|---------|
| action_type | choice | 0..6 (NoOp, Move, Harvest, Return, Produce, Attack) | 7 | What to do |
| move_dir | choice (if Move) | 0..3 (N/E/S/W) | 4 | Where to move |
| harvest_dir | choice (if Harvest) | 0..3 | 4 | Where to harvest |
| return_dir | choice (if Return) | 0..3 | 4 | Return direction |
| produce_dir | choice (if Produce) | 0..3 | 4 | Build direction |
| produce_unit_type | choice (if Produce) | 0..3 (Worker/Light/Heavy/Ranged) | 4 | What to build |
| attack_target_index | choice (if Attack) | 0..8 (3×3 local grid) | 9 | Target in local neighborhood |

**Flat size per cell:** 7 + 4 + 4 + 4 + 4 + 4 + 9 = 36 (rounded to 35 + reserved)  
**Total flat size:** 576 cells × 35 = 20160 flat actions

### 3.2 Action Semantics

#### action_type == 0: NoOp
- No-op, skip this actor
- No parameters used
- Valid always

#### action_type == 1: Move
- Move unit to adjacent cell in direction move_dir
- Validated by: actor alive, direction in bounds, destination unoccupied
- Consumed by: MatchManager.MoveUnit()

#### action_type == 2: Harvest
- Harvest from resource cell in harvest_dir
- Validated by: actor is Worker, resource exists and not exhausted, actor has carry capacity
- Consumed by: MatchManager.BeginHarvest()

#### action_type == 3: Return
- Return to nearest base in return_dir
- Validated by: actor carrying resources, base exists
- Consumed by: MatchManager.ReturnResources()

#### action_type == 4: Produce
- Produce unit of produce_unit_type in produce_dir
- Validated by: actor is Building, resources sufficient, production queue free, unit type producible
- Consumed by: BuildingRuntime.StartProducingUnit()

#### action_type == 5: Attack
- Attack target in local 3×3 grid at attack_target_index
- Target index 0..8 maps to neighbors in 3×3 grid
- Validated by: actor has attack capability, target in range (Chebyshev distance), target hostile
- Consumed by: MatchManager.AttackUnit()

#### action_type == 6: Reserved
- Reserved for future expansion

### 3.3 Invalid Action Masking

**Purpose:** Pre-sampling layer for policy to filter impossible actions WITHOUT runtime trial

**Architecture:** Per-cell, three-stage mask
```
MaskStage1: actor availability
  ├─ Actor exists, alive, owned by current player

MaskStage2: action_type feasibility
  ├─ NoOp: always valid
  ├─ Move: destination in bounds and unoccupied
  ├─ Harvest: Worker + resource in range
  ├─ Return: carrying + base exists
  ├─ Produce: Building + affordable + queue free
  └─ Attack: enemy in adjacent cells + Chebyshev

MaskStage3: parameter-level constraints
  ├─ move_dir: output 4-way mask (N/E/S/W feasible)
  ├─ harvest_dir: output 4-way (resource in that direction)
  ├─ return_dir: output 4-way (base in that direction, simplified)
  ├─ produce_dir: output 4-way (build slot in that direction)
  ├─ produce_unit_type: output 4-way (resource-affordable unit types)
  └─ attack_target_index: output 9-way (enemies in 3×3 grid)
```

**Two-Layer Mask Semantics:**

| Semantic Layer | Focus | Output |
|----------------|-------|--------|
| Gym-compatible rules | Player ownership, actor aliveness, basic reachability | Set intersection of Gym feasibility checks |
| Unity-only runtime rules | Match phase, production queue state, live ownership checks | Additional Unity-specific constraints |

**Important:** Mask is **NOT authoritative** — actionapplier still validates at apply time. Mask serves **diagnostics and offline evaluation** only.

### 3.4 Action Decoder

**Input:** Action output from policy (branches or one-hot or continuous)  
**Output:** AgentAction (structured internal format)  
**Semantics:** Deterministic mapping (no randomness)

```csharp
public class AgentAction
{
    public int ActorCellIndex;      // [0..575]
    public ActionType ActionType;    // NoOp, Move, Harvest, Return, Produce, Attack
    public Direction? MoveDir;
    public Direction? HarvestDir;
    public Direction? ReturnDir;
    public Direction? ProduceDir;
    public UnitType? ProduceType;
    public int? AttackTargetIndex;   // [0..8] for local 3×3
}
```

**DecodeTransferCompatible() path:**
- Accepts policy output in transfer-compatible format
- Maps branch indices to ActionType + parameters
- Validates output shape (must match contract)
- Returns AgentAction

---

## IV. Two-Layer Contract: Compatibility Gap Analysis

### 4.1 Six Known Gaps (Documented in WEEK3_COMPATIBILITY_GAP_LIST.md)

| Gap # | Category | Issue | Impact | Mitigation |
|-------|----------|-------|--------|-----------|
| 1 | Observation | Unity-only global features | Direct parity broken if not handled | Mode-specific observation building |
| 2 | Observation | attack_target semantics split (placeholder vs tactical) | Channel meaning differs | Document per-mode semantics |
| 3 | Action | Attack targeting reduced to 3×3 | Broader Gym targeting lost | Adapter/projection for wider targeting |
| 4 | Runtime | Attack intent vs outcome | Command accepted ≠ guaranteed hit | Keep gap explicit, test only submission |
| 5 | Action | Fewer action types than reference | Unsupported actions dropped | Filter/remap for dataset adaption |
| 6 | Runtime | Mask ≠ authoritative validation | Off-policy evaluation overestimates | Use applier as final gate |

### 4.2 Resilience Strategies

**For transfer experiments:**
- Use LegacyGymCompatibleSpec observation only (no global vector)
- Train on spatial tensor [24,24,27] only
- At inference, fill global vector with zeros or adaptation layer
- Attack targeting: expect 3×3 only, remap or drop wider targets
- Treat mask as diagnostic, not authoritative
- Validate combat acceptance, not outcome determinism

**For Week 4+ refinement:**
- Gap 4 (attack outcome) addressed by reward system (proxy semantics)
- Gaps 1-3, 5-6 kept as documented constraints, not "bugs"
- Incremental narrowing possible (e.g., expand attack to 5×5 in future)

---

## V. Heuristic Policy Adapter (Reference Implementation)

Week 3 включает **reference policy implementation** via HeuristicPolicyAdapter — не ML agent, но heuristic baseline через canonical pipeline.

### 5.1 Heuristic Logic

**Priority order (per step, all players):**

1. **Workers:** Harvest-return cycle
   - If carrying: return to nearest base
   - Else if resource in range: harvest
   - Else: idle or move towards resource

2. **Combat units:** Target enemies
   - If enemy in range: attack nearest
   - Else: move towards nearest enemy
   - Fallback: idle

3. **Buildings:** Produce workers/combat units
   - If affordable and queue free: start production
   - Else: idle

### 5.2 Pipeline Arc

```
HeuristicPolicyAdapter
  ├─ Per-player loop
  ├─ Per-actor-type loop (workers → military → buildings)
  ├─ For each actor:
  │  ├─ Read observation via ObservationBuilder
  │  ├─ Build mask via ActionMaskBuilder
  │  ├─ Decide: heuristic logic → AgentAction
  │  ├─ Decode: (already AgentAction from heuristic)
  │  └─ Apply: ActionApplier.ApplyAction(agentAction, actor)
  └─ Repeat until no valid actors
```

### 5.3 Integration with Canonical Loop

Heuristic path uses **same MlPolicyPipelineFacade** as future ML policies:
- `BuildObservation()` identical
- `BuildMask()` identical
- `DecodeAction()` wrapper (heuristic output already AgentAction)
- `ApplyAction()` identical
- Exception: heuristic uses synchronous imperative logic, not async policy inference

---

## VI. Pipeline Validation Status

### 6.1 Tested Scenarios

✅ **Single-actor decision** (one Worker harvests one resource)  
✅ **Multi-actor decisions** (multiple units per player per step)  
✅ **Multi-player game** (both players acting)  
✅ **Production** (building completes, unit spawns)  
✅ **Fallback handling** (invalid action attempted, rejected)  
✅ **Episode reset** (clean state for next episode)

### 6.2 Smoke Test Coverage

- ObservationBuilder.ValidateObservation() checks: size, range, one-hot correctness
- Invalid action rate: measured as (invalid attempts) / (all attempts)
- ActionApplier logs rejection reasons: OutOfBounds, NotOwned, NotAlive, etc.
- HeuristicPolicyAdapter provides end-to-end execution trace

---

## VII. Week 4 Entry Conditions (What Passes Into Week 4)

### ✅ Ready Components (Inherited from Week 3)

- [x] Observation pipeline (ObservationBuilder.BuildObservation)
- [x] Global features optional (BuildGlobalFeatures)
- [x] Action masking (ActionMaskBuilder.BuildTransferCompatibleMask)
- [x] Action decoding (ActionDecoder.DecodeTransferCompatible)
- [x] Action applier (ActionApplier.ApplyAction)
- [x] Invalid action logging (InvalidActionAttemptLog)
- [x] Two-layer contract (LegacyGymCompatibleSpec, UnityMvpTransferSpec)
- [x] Heuristic reference policy (working baseline)
- [x] MlPolicyPipelineFacade (thin orchestration wrapper)
- [x] Compatibility gap documentation (6 gaps explicit)

### ⏳ Not Ready (Week 4 Adds)

- [ ] Reward system (RewardCollector, 4 categories)
- [ ] Terminal pipeline (TerminalEvaluator, 5 reasons)
- [ ] Canonical RL loop orchestration (RlLoopCoordinator)
- [ ] Sanity-check tooling (BaselineRolloutRunner)
- [ ] ML-Agents policy loading/inference

---

## VIII. Known Limitations (Honest)

1. **Attack targeting local 3×3 only**
   - Deliberate v1 reduction for scope
   - Residual carry-over to Week 4 and beyond
   - Requires adapter for broader Gym targeting

2. **Global feature vector Unity-only**
   - LegacyGymCompatibleSpec stays spatial-only
   - UnityMvpTransferSpec adds 10-dim for convenience
   - Transfer experiments must choose layer consciously

3. **Fewer action types than full Gym**
   - Only 6 types (NoOp, Move, Harvest, Return, Produce, Attack)
   - Subset of producible units (Worker, Light, Heavy, Ranged only)
   - Richer Gym action spaces require dataset adapter

4. **Attack intent ≠ outcome guarantee**
   - ActionApplier validates intent
   - Runtime MatchManager/CombatResolver handles outcome
   - Combat hit probability not deterministic by intent alone

5. **Mask pre-sampling only, not authoritative**
   - Runtime validation in ActionApplier can still reject
   - Multi-actor contention may violate expectations
   - Important for offline evaluation protocols

6. **Heuristic baseline not ML baseline**
   - Heuristic is diagnostic tool, not strategy reference
   - Does not prove that action space works for learning
   - ML baseline will be measured in Week 4+

---

## IX. Technical References

### Key Files (Observation + Action)

| Module | File | Purpose |
|--------|------|---------|
| Contract | `Assets/Scripts/ML/ObservationContract.cs` | 27-channel enumeration |
| Contract | `Assets/Scripts/ML/ActionContract.cs` | 7-branch enumeration |
| Observation | `Assets/Scripts/ML/ObservationBuilder.cs` | Tensor generation + validation |
| Action Decoder | `Assets/Scripts/ML/ActionDecoder.cs` | Policy output → AgentAction |
| Masking | `Assets/Scripts/ML/ActionMaskBuilder.cs` | Feasibility mask generation |
| Application | `Assets/Scripts/ML/ActionApplier.cs` | AgentAction → MatchManager.Command |
| Facade | `Assets/Scripts/ML/MlPolicyPipelineFacade.cs` | Orchestration wrapper |
| Heuristic | `Assets/Scripts/ML/HeuristicPolicyAdapter.cs` | Reference policy |
| Mappings | `Assets/Scripts/ML/ActionContractMappings.cs` | Shared branch/enum logic |

### Documentation Artifacts

| Artifact | Content |
|----------|---------|
| `WEEK3_CONTRACT_SPEC.md` | Full 27-channel + 7-branch + global vector specification |
| `WEEK3_COMPATIBILITY_GAP_LIST.md` | 6 known gaps (authoritative) |
| `WEEK3_DAY7_SUMMARY.md` | API cleanup, duplication removal (historical) |
| Inline XML docs | Public API clarification (semantic layer, data layer ownership) |

---

## X. Week 4 Expectations (What Happens Next)

Week 4 **layers on top** of Week 3 without breaking it:

- Adds `RewardCollector` + `RewardTerminalContractTypes` (reward system)
- Adds `EpisodeTerminalPipeline` + `EpisodeTerminalEvaluator` (terminal detection)
- Adds `RlLoopCoordinator` (orchestration: observation → mask → decision → reward → terminal)
- Adds `BaselineRolloutRunner` (sanity-check tooling)
- Uses Week 3's `ActionDecoder`, `ActionMaskBuilder`, `ActionApplier` unchanged

**Invariant:** Week 3 contracts (observation shape, action contract, masking, pipeline) are **not rewritten** in Week 4. Only layered with reward/terminal logic.

---

## Выводы

### Week 3 Статус
```
┌────────────────────────────────────────┐
│ WEEK 3: ✅ ФИНАЛИЗИРОВАНА             │
│ Форма: ML Interface Layer              │
│ Документация: Complete + Validated     │
│ Ready For: Week 4 (Reward + Terminal)  │
└────────────────────────────────────────┘

Что готово:
  ✅ Observation (27 channels, spatial + optional global)
  ✅ Action (7 branches, 20160 flat actions)
  ✅ Invalid action masking
  ✅ Action decoding (AgentAction format)
  ✅ Two-layer contract (reference vs practical)
  ✅ Heuristic reference policy
  ✅ Pipeline validation
  ✅ Compatibility gap documentation (6 gaps)
  
Что NOT ready (Week 4):
  ❌ Reward system
  ❌ Terminal pipeline
  ❌ RL loop orchestration
  ❌ Sanity-check batch tooling
  ❌ ML policy loading

Что НЕ pretend'ится:
  ❌ Full Gym-μRTS parity (documented gaps)
  ❌ Combat outcome guarantee (intent only)
  ❌ Broader action space (local 3×3 only)
  ❌ ML-trained policy (heuristic reference)
```

### Handoff Week 4

Week 4 получает:
- Fully functional observation/action interface
- Invalid action masking (pre-sampling + post-validation layers)
- Heuristic reference policy (working baseline)
- Clear two-layer contract model
- Six documented compatibility gaps
- MlPolicyPipelineFacade (ready for ML policy swap-in)

---

*Week 3 завершена как документированный ML-facing interface layer, ready для Week 4 reward + terminal integration.*
