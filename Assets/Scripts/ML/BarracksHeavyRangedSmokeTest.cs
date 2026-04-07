// BarracksHeavyRangedSmokeTest.cs — Week 4 smoke test for production-split and combat-unit mechanics
//
// Test scenarios:
// 1. Worker builds Barracks (valid) — action accepted, Barracks registered
// 2. Worker build blocked: insufficient resources — action rejected, reason contains resource text
// 3. Worker build blocked: target cell occupied — action rejected, reason contains "occupied"
// 4. Base production split — Base accepts Worker, rejects Light/Heavy/Ranged
// 5. Barracks production split — Barracks accepts Light/Heavy/Ranged, rejects Worker
// 6. Heavy runtime: definition attackDamage=2, attackRange=1; mask enables melee attack
// 7. Ranged runtime: definition attackRange=3; LIMITATION — commanded attack surface still Chebyshev ≤ 1
// 8. Heuristic short loop — at least one player builds Barracks within 50 steps

using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using RTS.Core;
using RTS.Gameplay;

namespace RTS.ML
{
    /// <summary>
    /// Smoke tests for Week 4 mechanics: Worker→Barracks, production split, Heavy, Ranged.
    /// Attach to a scene GameObject alongside MatchBootstrap. Enable _runOnAwake to auto-run.
    /// </summary>
    public class BarracksHeavyRangedSmokeTest : MonoBehaviour
    {
        [SerializeField] private bool _runOnAwake = true;
        [SerializeField] private bool _verboseLogs = true;

        private GridManager      _gridManager;
        private UnitRegistry     _unitRegistry;
        private MatchManager     _matchManager;
        private MatchBootstrap   _matchBootstrap;
        private ResourceManager  _resourceManager;
        private ActionDecoder    _decoder;
        private ActionApplier    _applier;

        // ─────────────────────────────────────────────────────────────────────
        // Unity lifecycle
        // ─────────────────────────────────────────────────────────────────────

        private void Start()
        {
            if (!_runOnAwake)
                return;

            // Запускаем через корутину — ждём один кадр, чтобы MatchBootstrap.Start()
            // и EpisodeController.Start() успели инициализировать матч.
            StartCoroutine(RunTestsNextFrame());
        }

        private IEnumerator RunTestsNextFrame()
        {
            yield return null; // один кадр паузы
            ResolveReferences();
            RunTests();
        }

        [ContextMenu("Run Barracks/Heavy/Ranged Smoke Tests")]
        public void RunTests()
        {
            Debug.Log("[BHRSmokeTest] ===== Starting Week 4 Barracks/Heavy/Ranged Smoke Tests =====");

            RunIsolated(TestWorkerBuildsBarracks,               "Test 1: Worker builds Barracks");
            RunIsolated(TestWorkerBuildBlockedNoResources,      "Test 2: Worker build — insufficient resources");
            RunIsolated(TestWorkerBuildBlockedOccupied,         "Test 3: Worker build — target cell occupied");
            RunIsolated(TestBaseProductionSplit,                "Test 4: Base production split");
            RunIsolated(TestBarracksProductionSplit,            "Test 5: Barracks production split");
            RunIsolated(TestHeavyRuntimeDefinition,             "Test 6: Heavy runtime definition");
            RunIsolated(TestRangedRuntimeLimitation,            "Test 7: Ranged runtime limitation");
            RunIsolated(TestHeuristicBuildsBarracksInLoop,      "Test 8: Heuristic builds Barracks");

            Debug.Log("[BHRSmokeTest] ===== Week 4 Smoke Tests Completed =====");
        }

        // ─────────────────────────────────────────────────────────────────────
        // Test infrastructure
        // ─────────────────────────────────────────────────────────────────────

        private void RunIsolated(System.Action testMethod, string testLabel)
        {
            if (!ResetEpisodeAndResolve(testLabel))
            {
                Debug.LogWarning($"[BHRSmokeTest] {testLabel}: skipped — missing runtime dependencies");
                return;
            }
            testMethod();
        }

        private bool ResetEpisodeAndResolve(string testLabel)
        {
            var episodeController = EpisodeController.Instance;
            if (episodeController != null)
                episodeController.ResetEpisode();
            else
                Debug.LogWarning($"[BHRSmokeTest] {testLabel}: EpisodeController not found — running without episode reset");

            ResolveReferences();

            return _gridManager      != null
                && _unitRegistry     != null
                && _matchManager     != null
                && _resourceManager  != null
                && _matchBootstrap   != null
                && _decoder          != null
                && _applier          != null;
        }

        private void ResolveReferences()
        {
            _gridManager     = GridManager.Instance     ?? FindFirstObjectByType<GridManager>();
            _unitRegistry    = UnitRegistry.Instance    ?? FindFirstObjectByType<UnitRegistry>();
            _matchManager    = MatchManager.Instance;
            _matchBootstrap  = MatchBootstrap.Instance;
            _resourceManager = ResourceManager.Instance ?? FindFirstObjectByType<ResourceManager>();

            if (_gridManager == null || _unitRegistry == null || _matchManager == null || _matchBootstrap == null)
                return;

            _decoder = new ActionDecoder(_gridManager, _unitRegistry);
            _applier = new ActionApplier(_gridManager, _unitRegistry, _matchManager, _resourceManager);
        }

        // ─────────────────────────────────────────────────────────────────────
        // Test 1 — Worker builds Barracks (valid)
        // ─────────────────────────────────────────────────────────────────────

        private void TestWorkerBuildsBarracks()
        {
            if (!TrySpawnUnit(UnitType.Worker, Owner.Player1, new GridPosition(3, 3), out UnitRuntime worker))
            {
                Debug.LogWarning("[BHRSmokeTest] Test 1: cannot spawn Worker at (3,3) — skipping");
                return;
            }

            // Clear a free target cell to the north
            GridPosition targetPos = worker.GridPos.Neighbour(Direction.North);
            if (_gridManager.IsCellOccupied(targetPos))
            {
                Debug.LogWarning($"[BHRSmokeTest] Test 1: target cell {targetPos} occupied — skipping");
                return;
            }

            // Ensure enough resources
            int barracksCost = GetBarracksCost();
            _matchManager.AddResources(Owner.Player1, barracksCost + 100);

            int registeredBefore = CountUnitsByType(UnitType.Barracks, Owner.Player1);

            var action = _decoder.DecodeDebug(
                actorIndexFlat:    worker.GridPos.ToFlatIndex(),
                actionType:        (int)UnitActionType.Produce,
                direction:         (int)Direction.North,
                produceUnitType:   (int)ProducibleUnit.Worker, // placeholder — ignored for Worker actor
                attackTargetLocal: 0);

            _applier.ResetDiagnostics();
            bool applied = _applier.ApplyAction(action, worker.Owner);

            // ActionApplier ставит команду в очередь MatchManager; реальный спавн Barracks
            // происходит в MatchManager.ExecuteProductionPhase() → TryWorkerBuildBarracks.
            // Делаем один StepMatch, чтобы команда была исполнена.
            if (applied)
                _matchManager.StepMatch();

            int registeredAfter = CountUnitsByType(UnitType.Barracks, Owner.Player1);
            bool barracksSpawned = registeredAfter > registeredBefore;

            Log("Test 1", applied,      "action accepted by ActionApplier");
            Log("Test 1", barracksSpawned, "Barracks registered in UnitRegistry after build");

            if (!applied && _applier.RejectionReasonsLastStep.Count > 0)
                Debug.LogWarning($"[BHRSmokeTest] Test 1 rejection: {_applier.RejectionReasonsLastStep[0]}");
        }

        // ─────────────────────────────────────────────────────────────────────
        // Test 2 — Worker build blocked: insufficient resources
        // ─────────────────────────────────────────────────────────────────────

        private void TestWorkerBuildBlockedNoResources()
        {
            if (!TrySpawnUnit(UnitType.Worker, Owner.Player1, new GridPosition(3, 3), out UnitRuntime worker))
            {
                Debug.LogWarning("[BHRSmokeTest] Test 2: cannot spawn Worker — skipping");
                return;
            }

            GridPosition targetPos = worker.GridPos.Neighbour(Direction.North);
            if (_gridManager.IsCellOccupied(targetPos))
            {
                Debug.LogWarning($"[BHRSmokeTest] Test 2: target cell {targetPos} occupied — skipping");
                return;
            }

            // Drain all resources so the build must fail
            _matchManager.AddResources(Owner.Player1, -_matchManager.GetResources(Owner.Player1));

            var action = _decoder.DecodeDebug(
                actorIndexFlat:    worker.GridPos.ToFlatIndex(),
                actionType:        (int)UnitActionType.Produce,
                direction:         (int)Direction.North,
                produceUnitType:   (int)ProducibleUnit.Worker,
                attackTargetLocal: 0);

            _applier.ResetDiagnostics();
            bool applied = _applier.ApplyAction(action, worker.Owner);

            bool hasResourceReason = _applier.RejectionReasonsLastStep.Count > 0
                && (_applier.RejectionReasonsLastStep[0].ToLower().Contains("resource")
                 || _applier.RejectionReasonsLastStep[0].ToLower().Contains("enough")
                 || _applier.RejectionReasonsLastStep[0].ToLower().Contains("cost"));

            Log("Test 2", !applied,          "action correctly rejected");
            Log("Test 2", hasResourceReason,  "rejection reason mentions resources/cost");

            if (_verboseLogs && _applier.RejectionReasonsLastStep.Count > 0)
                Debug.Log($"[BHRSmokeTest] Test 2 rejection: {_applier.RejectionReasonsLastStep[0]}");
        }

        // ─────────────────────────────────────────────────────────────────────
        // Test 3 — Worker build blocked: target cell occupied
        // ─────────────────────────────────────────────────────────────────────

        private void TestWorkerBuildBlockedOccupied()
        {
            if (!TrySpawnUnit(UnitType.Worker, Owner.Player1, new GridPosition(3, 3), out UnitRuntime worker))
            {
                Debug.LogWarning("[BHRSmokeTest] Test 3: cannot spawn Worker — skipping");
                return;
            }

            GridPosition targetPos = worker.GridPos.Neighbour(Direction.North);

            // Place an obstacle on the target cell
            if (!_gridManager.IsCellOccupied(targetPos))
                TrySpawnUnit(UnitType.Worker, Owner.Player2, targetPos, out _);

            if (!_gridManager.IsCellOccupied(targetPos))
            {
                Debug.LogWarning($"[BHRSmokeTest] Test 3: could not occupy {targetPos} — skipping");
                return;
            }

            _matchManager.AddResources(Owner.Player1, GetBarracksCost() + 100);

            var action = _decoder.DecodeDebug(
                actorIndexFlat:    worker.GridPos.ToFlatIndex(),
                actionType:        (int)UnitActionType.Produce,
                direction:         (int)Direction.North,
                produceUnitType:   (int)ProducibleUnit.Worker,
                attackTargetLocal: 0);

            _applier.ResetDiagnostics();
            bool applied = _applier.ApplyAction(action, worker.Owner);

            bool hasOccupiedReason = _applier.RejectionReasonsLastStep.Count > 0
                && _applier.RejectionReasonsLastStep[0].ToLower().Contains("occupied");

            Log("Test 3", !applied,          "action correctly rejected for occupied cell");
            Log("Test 3", hasOccupiedReason,  "rejection reason mentions 'occupied'");

            if (_verboseLogs && _applier.RejectionReasonsLastStep.Count > 0)
                Debug.Log($"[BHRSmokeTest] Test 3 rejection: {_applier.RejectionReasonsLastStep[0]}");
        }

        // ─────────────────────────────────────────────────────────────────────
        // Test 4 — Base production split: accepts Worker, rejects Light/Heavy/Ranged
        // ─────────────────────────────────────────────────────────────────────

        private void TestBaseProductionSplit()
        {
            if (!TrySpawnUnit(UnitType.Base, Owner.Player1, new GridPosition(5, 5), out UnitRuntime baseBuilding))
            {
                Debug.LogWarning("[BHRSmokeTest] Test 4: cannot spawn Base — skipping");
                return;
            }

            // Ensure free cell to the north
            GridPosition spawnPos = baseBuilding.GridPos.Neighbour(Direction.North);
            if (_gridManager.IsCellOccupied(spawnPos))
            {
                Debug.LogWarning($"[BHRSmokeTest] Test 4: spawn cell {spawnPos} occupied — skipping");
                return;
            }

            _matchManager.AddResources(Owner.Player1, 9999);

            int actorIndex = baseBuilding.GridPos.ToFlatIndex();

            // Worker → should be accepted
            var workerAction = _decoder.DecodeDebug(actorIndex, (int)UnitActionType.Produce,
                (int)Direction.North, (int)ProducibleUnit.Worker, 0);
            _applier.ResetDiagnostics();
            bool workerAccepted = _applier.ApplyAction(workerAction, Owner.Player1);
            Log("Test 4", workerAccepted, "Base → produce Worker accepted");

            // Light → should be rejected (rule: Base only produces Worker)
            var lightAction = _decoder.DecodeDebug(actorIndex, (int)UnitActionType.Produce,
                (int)Direction.North, (int)ProducibleUnit.Light, 0);
            _applier.ResetDiagnostics();
            bool lightRejected = !_applier.ApplyAction(lightAction, Owner.Player1);
            Log("Test 4", lightRejected, "Base → produce Light rejected");

            // Heavy → should be rejected
            var heavyAction = _decoder.DecodeDebug(actorIndex, (int)UnitActionType.Produce,
                (int)Direction.North, (int)ProducibleUnit.Heavy, 0);
            _applier.ResetDiagnostics();
            bool heavyRejected = !_applier.ApplyAction(heavyAction, Owner.Player1);
            Log("Test 4", heavyRejected, "Base → produce Heavy rejected");

            // Ranged → should be rejected
            var rangedAction = _decoder.DecodeDebug(actorIndex, (int)UnitActionType.Produce,
                (int)Direction.North, (int)ProducibleUnit.Ranged, 0);
            _applier.ResetDiagnostics();
            bool rangedRejected = !_applier.ApplyAction(rangedAction, Owner.Player1);
            Log("Test 4", rangedRejected, "Base → produce Ranged rejected");

            if (_verboseLogs)
            {
                foreach (var r in _applier.RejectionReasonsLastStep)
                    Debug.Log($"[BHRSmokeTest] Test 4 last rejection: {r}");
            }
        }

        // ─────────────────────────────────────────────────────────────────────
        // Test 5 — Barracks production split: accepts Light/Heavy/Ranged, rejects Worker
        // ─────────────────────────────────────────────────────────────────────

        private void TestBarracksProductionSplit()
        {
            if (!TrySpawnUnit(UnitType.Barracks, Owner.Player1, new GridPosition(7, 7), out UnitRuntime barracks))
            {
                Debug.LogWarning("[BHRSmokeTest] Test 5: cannot spawn Barracks — skipping");
                return;
            }

            GridPosition spawnPos = barracks.GridPos.Neighbour(Direction.North);
            if (_gridManager.IsCellOccupied(spawnPos))
            {
                Debug.LogWarning($"[BHRSmokeTest] Test 5: spawn cell {spawnPos} occupied — skipping");
                return;
            }

            _matchManager.AddResources(Owner.Player1, 9999);

            int actorIndex = barracks.GridPos.ToFlatIndex();

            // Worker → should be rejected (rule: Barracks does not produce Worker)
            var workerAction = _decoder.DecodeDebug(actorIndex, (int)UnitActionType.Produce,
                (int)Direction.North, (int)ProducibleUnit.Worker, 0);
            _applier.ResetDiagnostics();
            bool workerRejected = !_applier.ApplyAction(workerAction, Owner.Player1);
            Log("Test 5", workerRejected, "Barracks → produce Worker rejected");

            // Light → should be accepted
            var lightAction = _decoder.DecodeDebug(actorIndex, (int)UnitActionType.Produce,
                (int)Direction.North, (int)ProducibleUnit.Light, 0);
            _applier.ResetDiagnostics();
            bool lightAccepted = _applier.ApplyAction(lightAction, Owner.Player1);
            Log("Test 5", lightAccepted, "Barracks → produce Light accepted");

            // Heavy → should be accepted (spawn cell may be occupied after Light; accept result is best-effort)
            var heavyAction = _decoder.DecodeDebug(actorIndex, (int)UnitActionType.Produce,
                (int)Direction.North, (int)ProducibleUnit.Heavy, 0);
            _applier.ResetDiagnostics();
            bool heavyResult = _applier.ApplyAction(heavyAction, Owner.Player1);
            bool heavyNotRuleRejected = !(_applier.RejectionReasonsLastStep.Count > 0
                && _applier.RejectionReasonsLastStep[0].ToLower().Contains("production rule"));
            Log("Test 5", heavyNotRuleRejected, "Barracks → produce Heavy not rejected by production rule");
            if (_verboseLogs)
                Debug.Log($"[BHRSmokeTest] Test 5 Heavy produce result: {(heavyResult ? "accepted" : "rejected")}");

            // Ranged → should be accepted (same caveat)
            var rangedAction = _decoder.DecodeDebug(actorIndex, (int)UnitActionType.Produce,
                (int)Direction.North, (int)ProducibleUnit.Ranged, 0);
            _applier.ResetDiagnostics();
            bool rangedResult = _applier.ApplyAction(rangedAction, Owner.Player1);
            bool rangedNotRuleRejected = !(_applier.RejectionReasonsLastStep.Count > 0
                && _applier.RejectionReasonsLastStep[0].ToLower().Contains("production rule"));
            Log("Test 5", rangedNotRuleRejected, "Barracks → produce Ranged not rejected by production rule");
            if (_verboseLogs)
                Debug.Log($"[BHRSmokeTest] Test 5 Ranged produce result: {(rangedResult ? "accepted" : "rejected")}");
        }

        // ─────────────────────────────────────────────────────────────────────
        // Test 6 — Heavy runtime: definition values + melee attack mask
        // ─────────────────────────────────────────────────────────────────────

        private void TestHeavyRuntimeDefinition()
        {
            UnitDefinition def = GetDefinition(UnitType.Heavy);
            if (def == null)
            {
                Debug.LogWarning("[BHRSmokeTest] Test 6: UnitDef_Heavy not found in GameConfig — skipping");
                return;
            }

            Log("Test 6", def.attackDamage    >= 2, $"Heavy attackDamage≥2 (got {def.attackDamage})");
            Log("Test 6", def.attackRange      == 1, $"Heavy attackRange==1 (got {def.attackRange})");
            Log("Test 6", def.maxHitPoints     >= 3, $"Heavy maxHitPoints≥3 (got {def.maxHitPoints})");

            // Spawn Heavy adjacent to an enemy to verify attack mask
            if (!TrySpawnUnit(UnitType.Heavy, Owner.Player1, new GridPosition(4, 4), out UnitRuntime heavy))
            {
                Debug.LogWarning("[BHRSmokeTest] Test 6: cannot spawn Heavy — definition check only");
                return;
            }

            GridPosition enemyPos = heavy.GridPos.Neighbour(Direction.North);
            if (!_gridManager.IsCellOccupied(enemyPos))
                TrySpawnUnit(UnitType.Light, Owner.Player2, enemyPos, out _);

            if (_gridManager.IsCellOccupied(enemyPos) && _gridManager.GetOccupant(enemyPos)?.Owner == Owner.Player2)
            {
                var maskBuilder = new ActionMaskBuilder(_matchManager, _gridManager, _resourceManager,
                    _unitRegistry, _matchBootstrap);
                ActionMaskSet mask = maskBuilder.BuildTransferCompatibleMask(Owner.Player1);
                ActorActionMask heavyMask = mask.GetActorMaskByFlatIndex(heavy.GridPos.ToFlatIndex());

                bool attackEnabled = heavyMask != null && heavyMask.IsActionTypeEnabled(UnitActionType.Attack);
                Log("Test 6", attackEnabled, "Heavy attack action type enabled in mask when enemy is adjacent");
            }
            else
            {
                Debug.LogWarning("[BHRSmokeTest] Test 6: no adjacent enemy — mask check skipped");
            }
        }

        // ─────────────────────────────────────────────────────────────────────
        // Test 7 — Ranged runtime: definition values + LIMITATION note
        // ─────────────────────────────────────────────────────────────────────

        private void TestRangedRuntimeLimitation()
        {
            UnitDefinition def = GetDefinition(UnitType.Ranged);
            if (def == null)
            {
                Debug.LogWarning("[BHRSmokeTest] Test 7: UnitDef_Ranged not found in GameConfig — skipping");
                return;
            }

            Log("Test 7", def.attackRange    >= 2, $"Ranged attackRange≥2 (got {def.attackRange}, MVP target=3)");
            Log("Test 7", def.attackDamage   >= 1, $"Ranged attackDamage≥1 (got {def.attackDamage})");
            Log("Test 7", def.maxHitPoints   >= 1, $"Ranged maxHitPoints≥1 (got {def.maxHitPoints})");

            // LIMITATION: all 9 ActionContract.AttackOffsets are Chebyshev ≤ 1.
            // Ranged attackRange=3 affects CombatResolver auto-combat only.
            // Commanded attacks (ML action surface) are still limited to Chebyshev ≤ 1.
            bool allOffsetsChebyshevOne = true;
            foreach (var (dx, dy) in ActionContract.AttackOffsets)
            {
                int chebyshev = Mathf.Max(Mathf.Abs(dx), Mathf.Abs(dy));
                if (chebyshev > 1)
                {
                    allOffsetsChebyshevOne = false;
                    break;
                }
            }

            Log("Test 7", allOffsetsChebyshevOne,
                "LIMITATION CONFIRMED: all ActionContract.AttackOffsets are Chebyshev≤1 — " +
                "Ranged commanded attack surface identical to melee; advantage is auto-combat only");

            Debug.Log("[BHRSmokeTest] Test 7: Ranged advantage via CombatResolver auto-combat is intentional. " +
                      "Wider commanded attack surface requires ActionContract expansion (future work).");
        }

        // ─────────────────────────────────────────────────────────────────────
        // Test 8 — Heuristic builds Barracks in a short episode loop
        // ─────────────────────────────────────────────────────────────────────

        private void TestHeuristicBuildsBarracksInLoop()
        {
            HeuristicPolicyAdapter adapter = FindFirstObjectByType<HeuristicPolicyAdapter>();
            if (adapter == null)
            {
                GameObject host = new GameObject("HeuristicPolicyAdapter_BHRTest");
                adapter = host.AddComponent<HeuristicPolicyAdapter>();
            }

            adapter.Initialize(_gridManager, _unitRegistry, _resourceManager, _matchManager, _matchBootstrap);
            adapter.SetPlayerControlModes(HeuristicControlMode.Heuristic, HeuristicControlMode.Heuristic);

            // Give both players plenty of resources so Barracks build is affordable
            _matchManager.AddResources(Owner.Player1, 500);
            _matchManager.AddResources(Owner.Player2, 500);

            int barracksP1Before = CountUnitsByType(UnitType.Barracks, Owner.Player1);
            int barracksP2Before = CountUnitsByType(UnitType.Barracks, Owner.Player2);
            int barracksBuilt = 0;

            for (int step = 0; step < 50; step++)
            {
                if (_matchManager.Phase != MatchPhase.Running)
                    break;

                adapter.DecideAndApply(Owner.Player1);
                adapter.DecideAndApply(Owner.Player2);
                _matchManager.StepMatch();

                int p1Now = CountUnitsByType(UnitType.Barracks, Owner.Player1);
                int p2Now = CountUnitsByType(UnitType.Barracks, Owner.Player2);
                barracksBuilt = (p1Now - barracksP1Before) + (p2Now - barracksP2Before);

                if (barracksBuilt > 0)
                {
                    if (_verboseLogs)
                        Debug.Log($"[BHRSmokeTest] Test 8: Barracks built at step {step}");
                    break;
                }
            }

            Log("Test 8", barracksBuilt > 0, "heuristic built at least one Barracks within 50 steps");

            if (barracksBuilt == 0)
                Debug.LogWarning("[BHRSmokeTest] Test 8: no Barracks built in 50 steps — " +
                    "check HeuristicPolicyAdapter.TrySelectWorkerAction / PlayerHasBarracks path");
        }

        // ─────────────────────────────────────────────────────────────────────
        // Helpers
        // ─────────────────────────────────────────────────────────────────────

        private void Log(string testLabel, bool condition, string description)
        {
            string symbol = condition ? "✓" : "✗";
            if (condition)
                Debug.Log($"[BHRSmokeTest] {symbol} {testLabel}: {description}");
            else
                Debug.LogWarning($"[BHRSmokeTest] {symbol} {testLabel}: FAIL — {description}");
        }

        private bool TrySpawnUnit(UnitType type, Owner owner, GridPosition position, out UnitRuntime unit)
        {
            unit = null;
            if (_matchBootstrap?.GetConfig() == null)
                return false;
            if (!_gridManager.IsInside(position) || _gridManager.IsCellOccupied(position))
                return false;

            var factory = new UnitFactory(_matchBootstrap.GetConfig(), _gridManager, _gridManager.transform, _unitRegistry);
            unit = factory.Spawn(type, owner, position);
            return unit != null;
        }

        private int CountUnitsByType(UnitType type, Owner owner)
        {
            IReadOnlyList<UnitRuntime> all = _unitRegistry.GetAllUnits();
            int count = 0;
            for (int i = 0; i < all.Count; i++)
            {
                if (all[i] != null && all[i].IsAlive && all[i].Type == type && all[i].Owner == owner)
                    count++;
            }
            return count;
        }

        private UnitDefinition GetDefinition(UnitType type)
        {
            GameConfig config = _matchBootstrap?.GetConfig();
            return config?.GetDefinition(type);
        }

        private int GetBarracksCost()
        {
            UnitDefinition def = GetDefinition(UnitType.Barracks);
            return def != null && def.productionCost > 0 ? def.productionCost : 50;
        }
    }
}
