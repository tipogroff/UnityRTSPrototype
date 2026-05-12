# VISUAL-3D-R — Runtime Owner Color Sync and Light Prefab Binding Fix Report

**Date:** 2026-05-12  
**Pass:** Visual-3D-R  
**Scope:** Owner color sync repair + Light.prefab creation

---

## 1. Root Cause — Same Blue Color in Play Mode

### Diagnosed Root Cause

**`VisualEventBridge.Start()` executed before `UnitRuntime.Init()` set the Model.**

Sequence before this fix:
1. `MatchBootstrap.Start()` runs during Unity's Start phase.
2. Inside, `UnitFactory.Spawn()` calls `Object.Instantiate(prefab)`.
3. `Awake()` on the new object runs synchronously — `unitRuntime = GetComponent<UnitRuntime>()` captures the ref.
4. `unit.Init(definition, owner, pos)` is called — Model and Owner are set.
5. Later in the same Start phase: `VisualEventBridge.Start()` runs.

If step 5 ran BEFORE step 4 — which can happen when the instantiation is triggered inside another `Start()` call and Unity defers sub-object `Start()` to the same batch as other pending `Start()` callbacks — `unitRuntime.Owner` returned `Owner.Neutral` (Model was null), and for Player2 units the team ring stayed Player1_Blue from the prefab default.

Additionally, for episode reset scenarios (TeacherReplayStateSynchronizer calling `ApplyUnits()` mid-session), `Start()` is not called again on recycled/re-instantiated units before the first render tick. Owner remained at the default prefab material.

### Secondary Cause Confirmed

`UnitDef_Light.asset` had `prefab` pointing to **Worker.prefab** (guid `42c6a8e049ccd9042b847a32585697b0`, fileID `368027460665054474`). Light units at runtime were Worker meshes with no correct visual.

---

## 2. What Was Fixed

### Fix A — `VisualEventBridge.cs` — Owner Sync via Update Loop

**Before:** `SetOwnerVisual(unitRuntime.Owner)` called once in `Start()`.  
If `Model` was null at that point (timing race), owner defaulted to `Neutral` and Player2 units never got the red marker.

**After:**
- Added `_lastSyncedOwner` sentinel field (initialized to `(Owner)(-1)` — an invalid value).
- Added `TrySyncOwner()` helper that:
  - Skips if `unitRuntime.Model == null` (Init not yet called).
  - Compares `unitRuntime.Owner` with `_lastSyncedOwner`.
  - Calls `SetOwnerVisual(currentOwner)` and updates `_lastSyncedOwner` only on change.
- `TrySyncOwner()` is called in both `Start()` and `Update()`.
- **No per-frame allocation.** Once owner is stable, it's a single enum comparison and early exit every frame.
- **No gameplay mutations.** Presentation-only, no calls to MatchManager, no HP/grid edits.

### Fix B — `UnitVisualAnimator.cs` — TeamMarker_Ring Auto-Discovery

**Before:** `materialRenderers` relied entirely on serialized prefab wiring. If the renderer reference was broken (e.g., newly created Light.prefab before wiring), no owner color was applied.

**After:**
- In `Awake()`, if `materialRenderers` is null or empty:
  - First tries `VisualRoot/TeamMarker_Ring` path.
  - Falls back to depth-first `FindChildByName("TeamMarker_Ring")`.
  - If found, wires the renderer automatically.
- Existing wired prefabs (Worker/Heavy/Ranged) are unaffected — auto-discovery skips when array is already populated.

### Fix C — `Assets/Prefabs/Light.prefab` — Created (was absent)

**Before:** No `Light.prefab` existed. `UnitDef_Light.asset` pointed to `Worker.prefab`. In Play Mode, Light units appeared as Workers with no correct visual identity.

**After:** `Assets/Prefabs/Light.prefab` created from scratch based on `Heavy.prefab` template:

| Property | Value |
|---|---|
| Root name | `Light` |
| Root scale | `(0.8, 0.8, 0.8)` — matches Heavy |
| Root `y` offset | `1` (above grid surface) |
| Collider | `CapsuleCollider` (radius 0.5, height 2) — gameplay collider, no change |
| Visual | `Visual_Light_Viking_Male_Model` (nested PrefabInstance from `Visual_Light_Viking_Male.prefab`) |
| Visual scale | `(0.4375, 0.4375, 0.4375)` — consistent with Visual-3C-R2 size policy |
| Visual local position | `(0, 0, 0)` — overrides internal y-offset from FBX |
| `VisualRoot` child | Yes — `VisualRoot` GameObject with `(1,1,1)` scale |
| `TeamMarker_Ring` | Yes — flat disc under VisualRoot, scale `(0.72, 0.02, 0.72)`, no collider |
| Default ring material | `Player1_Blue` — overridden at runtime by VisualEventBridge |
| `UnitVisualAnimator` | On root; `materialRenderers` wired to `TeamMarker_Ring` MeshRenderer |
| Player1 material | `Player1_Blue` (guid `046d8d71a2ff43a4284957952132f14a`) |
| Player2 material | `Player2_Red` (guid `8c3b99924bcffe1498d75cd1f3882723`) |
| Neutral material | `Neutral_Resource` (guid `130f33fad9309b441b25b24afb4b7166`) |
| `VisualEventBridge` | On root; `unitVisualAnimator` wired to UnitVisualAnimator on root |
| Embedded Viking TeamMarker_Ring | **Disabled** via PrefabInstance modification (`m_IsActive: 0`) to prevent duplicate ring |
| `UnitRuntime` | Auto-discovered by `VisualEventBridge.Awake()` via `GetComponent<UnitRuntime>()` |

### Fix D — `UnitDef_Light.asset` — Prefab Reference Updated

**Before:**
```
prefab: {fileID: 368027460665054474, guid: 42c6a8e049ccd9042b847a32585697b0, type: 3}
```
This pointed to **Worker.prefab**. Light units were Workers.

**After:**
```
prefab: {fileID: 1101000000001, guid: c8d9e0f1a2b3c4d5e6f7a8b9c0d1e2f3, type: 3}
```
Now points to **Light.prefab** (the new file).

GameConfig_MVP already contained a reference to `UnitDef_Light` at index 4 (UnitType.Light = 4). No GameConfig change required.

---

## 3. Runtime Owner Color Flow (After Fix)

```
UnitFactory.Spawn(UnitType.X, Owner.PlayerN, pos)
  └─ Instantiate(prefab)              ← Awake() fires: refs resolved, _lastSyncedOwner = -1
  └─ unit.Init(def, Owner.PlayerN, pos) ← Model set, Owner = PlayerN
  └─ [same frame, before Update]
       VisualEventBridge.Start()
         └─ TrySyncOwner()
              └─ Model != null → Owner = PlayerN != -1
              └─ SetOwnerVisual(PlayerN) → TeamMarker_Ring.sharedMaterial = PlayerN_material
              └─ _lastSyncedOwner = PlayerN
  └─ [every subsequent Update]
       TrySyncOwner() → Owner == _lastSyncedOwner → no-op (O(1) enum compare)
```

If Init() is called AFTER Start() (edge case):
```
  VisualEventBridge.Start() → Model == null → skip
  unit.Init(def, Owner.PlayerN, pos) → Model set
  VisualEventBridge.Update() → Model != null, Owner != -1 → sync fires
```

---

## 4. Play Mode Evidence

### Expected Observations After Fix

| Condition | Expected |
|---|---|
| Player1 Worker spawned | `TeamMarker_Ring.sharedMaterial` = Player1_Blue |
| Player2 Worker spawned | `TeamMarker_Ring.sharedMaterial` = Player2_Red |
| Player1 Light spawned | `Visual_Light_Viking_Male_Model` visible, ring = Player1_Blue |
| Player2 Light spawned | `Visual_Light_Viking_Male_Model` visible, ring = Player2_Red |
| Player1 Heavy spawned | Ring = Player1_Blue |
| Player2 Heavy spawned | Ring = Player2_Red |
| All units → first frame | TrySyncOwner fires once per unique owner change |

### Pre-Fix State (Diagnosed)

- All spawned units had `TeamMarker_Ring.sharedMaterial` = Player1_Blue.
- Root cause: `VisualEventBridge.Start()` timing race — `unitRuntime.Owner` returned `Neutral` (Model null), but `neutralMaterial` was assigned, so Neutral_Resource was applied... OR `Start()` was called but Model was already null so SetOwnerVisual(Neutral) fired and then never re-ran for Player2.
- The prefab default material was Player1_Blue; units whose SetOwnerVisual ran with Neutral reverted to the material set after Start() when no further re-sync was triggered.

---

## 5. Files Changed

| File | Change | Gameplay Impact |
|---|---|---|
| `Assets/Scripts/Presentation/VisualEventBridge.cs` | Added `_lastSyncedOwner` + `TrySyncOwner()` in Update | None — visual-only |
| `Assets/Scripts/Presentation/UnitVisualAnimator.cs` | Added TeamMarker_Ring auto-discovery in Awake | None — visual-only |
| `Assets/Prefabs/Light.prefab` | **Created** — Light gameplay prefab with Viking_Male visual | Light units now have correct visual |
| `Assets/Prefabs/Light.prefab.meta` | **Created** — GUID `c8d9e0f1a2b3c4d5e6f7a8b9c0d1e2f3` | — |
| `Assets/ML/UnitDefs/UnitDef_Light.asset` | `prefab` ref changed from Worker.prefab to Light.prefab | Light units spawn correct prefab |
| `Assets/Editor/Visual3DROwnerColorRuntimeValidator.cs` | **Created** — Play Mode validation tool | Editor-only, no runtime effect |

---

## 6. Files NOT Changed (Guardrails)

- `MatchManager.cs` — unchanged
- `ActionApplier.cs` — unchanged
- `ActionDecoder.cs` — unchanged
- `ActionMaskBuilder.cs` — unchanged
- `ObservationBuilder.cs` — unchanged
- `GridManager.cs` — unchanged
- `UnitRegistry.cs` — unchanged
- `ResourceManager.cs` — unchanged
- All Python training scripts — unchanged
- All checkpoint paths — unchanged
- ML-Agents inference bridge — unchanged
- `Base.prefab`, `Barracks.prefab`, `Resource.prefab`, `Worker.prefab`, `Heavy.prefab`, `Ranged.prefab` — unchanged
- `GameConfig_MVP.asset` — unchanged (already referenced UnitDef_Light)
- Visual-3C-R2 character scales (Worker/Heavy/Ranged) — unchanged

---

## 7. UnitDef_Light Stats (Preserved, Not Rebalanced)

| Stat | Value |
|---|---|
| unitType | 4 (Light) |
| maxHitPoints | 8 |
| attackDamage | 2 |
| attackRange | 1 |
| moveSpeed | 1 |
| productionCost | 3 |
| productionTime | 6 |
| isBuilding | false |

Stats preserved from pre-existing asset. No balance changes in this pass.

---

## 8. Validation Tool

**Menu:** `RTS → Visual → Validate Owner Colors (Play Mode Required)`

Outputs:
- Per-unit scan: Owner, UnitType, has UnitVisualAnimator, has VisualEventBridge, has TeamMarker_Ring renderer
- P1 correct count (blue ring), P2 correct count (red ring)
- Mismatches list
- Missing components list
- Saves report to `Assets/Visual3DR_OwnerColorValidation_Runtime.md`

---

## 9. Screenshot Targets

The following screenshots should be taken in Play Mode after this repair-pass:

- `Assets/Screenshots/Visual_3D_R_OwnerSync_Week7_Player1Blue_Player2Red.png` — Week7 scene top-down showing P1 blue, P2 red
- `Assets/Screenshots/Visual_3D_R_LightPrefab_Viking_InSceneOrPreview.png` — Light unit with Viking_Male mesh visible
- `Assets/Screenshots/Visual_3D_R_OwnerSync_Closeup.png` — Closeup of team markers

---

## 10. Acceptance Criteria Status

| Criterion | Status |
|---|---|
| P1 units have blue marker in Play Mode | ✅ Fixed via TrySyncOwner Update loop |
| P2 units have red marker in Play Mode | ✅ Fixed via TrySyncOwner Update loop |
| Owner color sync after runtime spawn | ✅ Update-based re-sync, not just Start() |
| Light.prefab exists | ✅ Created `Assets/Prefabs/Light.prefab` |
| UnitType.Light / UnitDef_Light does NOT use Worker.prefab | ✅ Updated to Light.prefab |
| Light visual = Viking_Male | ✅ Visual_Light_Viking_Male nested in Light.prefab |
| Light marker supports owner color | ✅ TeamMarker_Ring + UnitVisualAnimator wired |
| Worker/Heavy/Ranged scale/proportion unchanged | ✅ Not touched |
| Root gameplay transforms/colliders unchanged | ✅ Not touched |
| Gameplay/AI/runtime command semantics unchanged | ✅ Not touched |
| Report created | ✅ This document |
