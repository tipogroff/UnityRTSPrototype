using System;
using System.Collections.Generic;
using RTS.Core;
using RTS.Gameplay;
using UnityEngine;

namespace RTS.MLAgents.Stage7B.TeacherReplay
{
    public sealed class Stage7BTeacherReplayStateSynchronizer
    {
        private readonly MatchManager _match;
        private readonly GridManager _grid;
        private readonly UnitRegistry _registry;
        private readonly MatchBootstrap _bootstrap;
        private readonly ResourceManager _resources;
        private readonly GameConfig _config;

        public Stage7BTeacherReplayStateSynchronizer(
            MatchManager match,
            GridManager grid,
            UnitRegistry registry,
            MatchBootstrap bootstrap,
            ResourceManager resources)
        {
            _match = match;
            _grid = grid;
            _registry = registry;
            _bootstrap = bootstrap;
            _resources = resources;
            _config = bootstrap != null ? bootstrap.GetConfig() : null;
        }

        public bool TrySynchronizeRuntimeState(
            string runtimeStateJson,
            out Stage7BTeacherReplayDropReason dropReason,
            out string diagnostics)
        {
            if (_match == null || _grid == null || _registry == null || _bootstrap == null || _resources == null || _config == null)
            {
                dropReason = Stage7BTeacherReplayDropReason.UnityStateApiMissing;
                diagnostics = "required Unity runtime services are missing (MatchManager/GridManager/UnitRegistry/MatchBootstrap/ResourceManager/GameConfig)";
                return false;
            }

            if (string.IsNullOrWhiteSpace(runtimeStateJson))
            {
                dropReason = Stage7BTeacherReplayDropReason.MissingRuntimeStateT;
                diagnostics = "runtime_state_t_json is empty";
                return false;
            }

            Stage7BTeacherReplayRuntimeState state;
            try
            {
                state = JsonUtility.FromJson<Stage7BTeacherReplayRuntimeState>(runtimeStateJson);
            }
            catch (Exception ex)
            {
                dropReason = Stage7BTeacherReplayDropReason.MissingRuntimeStateT;
                diagnostics = "runtime_state_t_json parse failed: " + ex.Message;
                return false;
            }

            if (state == null)
            {
                dropReason = Stage7BTeacherReplayDropReason.MissingRuntimeStateT;
                diagnostics = "runtime_state_t_json parse returned null";
                return false;
            }

            if (state.map_width != GameConstants.MapWidth || state.map_height != GameConstants.MapHeight)
            {
                dropReason = Stage7BTeacherReplayDropReason.StateSyncFailed;
                diagnostics = "map size mismatch. expected 24x24, got " + state.map_width + "x" + state.map_height;
                return false;
            }

            if (state.players == null || state.units == null || state.resource_nodes == null)
            {
                dropReason = Stage7BTeacherReplayDropReason.StateSyncFailed;
                diagnostics = "runtime_state_t_json missing one of required arrays (players/units/resource_nodes)";
                return false;
            }

            ClearCurrentRuntimeState();

            _match.BeginMatch(0, _config.maxEpisodeSteps);

            if (!ApplyResources(state.resource_nodes, out dropReason, out diagnostics))
            {
                return false;
            }

            if (!ApplyUnits(state.units, out dropReason, out diagnostics))
            {
                return false;
            }

            ApplyPlayerResources(state.players);

            if (state.building_queues != null && state.building_queues.Length > 0)
            {
                diagnostics = "state synchronized with limitation: building_queues reconstruction is not implemented";
            }
            else
            {
                diagnostics = "state synchronized";
            }

            dropReason = Stage7BTeacherReplayDropReason.None;
            return true;
        }

        public bool TryComparePostState(
            string runtimeStateTp1Json,
            out bool terminalMatch,
            out string diagnostics)
        {
            terminalMatch = false;
            diagnostics = string.Empty;

            if (string.IsNullOrWhiteSpace(runtimeStateTp1Json))
            {
                diagnostics = "runtime_state_tp1_json is empty";
                return false;
            }

            Stage7BTeacherReplayRuntimeState expected;
            try
            {
                expected = JsonUtility.FromJson<Stage7BTeacherReplayRuntimeState>(runtimeStateTp1Json);
            }
            catch (Exception ex)
            {
                diagnostics = "runtime_state_tp1_json parse failed: " + ex.Message;
                return false;
            }

            if (expected == null)
            {
                diagnostics = "runtime_state_tp1_json parse returned null";
                return false;
            }

            int expectedUnitCount = 0;
            for (int i = 0; i < expected.units.Length; i++)
            {
                if (!IsResourceType(expected.units[i].type))
                {
                    expectedUnitCount++;
                }
            }

            int actualUnitCount = _registry.GetAllUnits().Count;
            int expectedResourceCount = expected.resource_nodes.Length;
            int actualResourceCount = CountResourceNodes();

            bool playersMatch = true;
            if (expected.players != null)
            {
                for (int i = 0; i < expected.players.Length; i++)
                {
                    Owner owner = MapPlayerId(expected.players[i].player_id);
                    int actual = _match.GetResources(owner);
                    if (actual != expected.players[i].resources)
                    {
                        playersMatch = false;
                        break;
                    }
                }
            }

            bool doneExpected = expected.terminal != null && expected.terminal.done;
            bool doneActual = _match.Phase == MatchPhase.Ended;
            terminalMatch = doneExpected == doneActual;

            bool pass = actualUnitCount == expectedUnitCount
                        && actualResourceCount == expectedResourceCount
                        && playersMatch;

            diagnostics = "post_compare unit_count=" + actualUnitCount + "/" + expectedUnitCount
                          + ", resource_nodes=" + actualResourceCount + "/" + expectedResourceCount
                          + ", players_match=" + playersMatch
                          + ", terminal_match=" + terminalMatch;
            return pass;
        }

        private bool ApplyUnits(
            Stage7BTeacherReplayUnitState[] units,
            out Stage7BTeacherReplayDropReason dropReason,
            out string diagnostics)
        {
            dropReason = Stage7BTeacherReplayDropReason.None;
            diagnostics = string.Empty;

            var occupied = new HashSet<int>();
            var factory = new UnitFactory(_config, _grid, _grid.transform, _registry);

            for (int i = 0; i < units.Length; i++)
            {
                Stage7BTeacherReplayUnitState u = units[i];
                if (u == null || IsResourceType(u.type))
                {
                    continue;
                }

                if (!TryParseUnitType(u.type, out UnitType unitType))
                {
                    dropReason = Stage7BTeacherReplayDropReason.StateSyncFailed;
                    diagnostics = "unsupported unit type: " + u.type;
                    return false;
                }

                GridPosition pos = new GridPosition(u.x, u.y);
                if (!_grid.IsInside(pos))
                {
                    dropReason = Stage7BTeacherReplayDropReason.StateSyncFailed;
                    diagnostics = "unit out of bounds at " + pos;
                    return false;
                }

                int flat = pos.ToFlatIndex();
                if (!occupied.Add(flat))
                {
                    dropReason = Stage7BTeacherReplayDropReason.DuplicateSpawnDetected;
                    diagnostics = "duplicate unit position detected at flat=" + flat;
                    return false;
                }

                Owner owner = MapOwner(u.owner);
                UnitRuntime spawned = factory.Spawn(unitType, owner, pos);
                if (spawned == null)
                {
                    dropReason = Stage7BTeacherReplayDropReason.StateSyncFailed;
                    diagnostics = "failed to spawn unit " + unitType + " at " + pos;
                    return false;
                }

                if (u.carried_resources > 0)
                {
                    spawned.AddCarriedResources(u.carried_resources);
                }

                if (u.hp > 0 && u.hp < spawned.MaxHP)
                {
                    spawned.TakeDamage(spawned.MaxHP - u.hp);
                }
            }

            return true;
        }

        private bool ApplyResources(
            Stage7BTeacherReplayResourceNodeState[] resourceNodes,
            out Stage7BTeacherReplayDropReason dropReason,
            out string diagnostics)
        {
            dropReason = Stage7BTeacherReplayDropReason.None;
            diagnostics = string.Empty;

            var occupied = new HashSet<int>();
            for (int i = 0; i < resourceNodes.Length; i++)
            {
                Stage7BTeacherReplayResourceNodeState node = resourceNodes[i];
                if (node == null)
                {
                    continue;
                }

                GridPosition pos = new GridPosition(node.x, node.y);
                if (!_grid.IsInside(pos))
                {
                    dropReason = Stage7BTeacherReplayDropReason.StateSyncFailed;
                    diagnostics = "resource node out of bounds at " + pos;
                    return false;
                }

                int flat = pos.ToFlatIndex();
                if (!occupied.Add(flat))
                {
                    dropReason = Stage7BTeacherReplayDropReason.DuplicateSpawnDetected;
                    diagnostics = "duplicate resource node position detected at flat=" + flat;
                    return false;
                }

                int max = Mathf.Max(node.remaining, 1);
                var resource = new ResourceNode(pos, max);
                if (node.remaining < max)
                {
                    resource.Harvest(max - Mathf.Max(0, node.remaining));
                }

                _resources.RegisterResourceNode(resource);
            }

            return true;
        }

        private void ApplyPlayerResources(Stage7BTeacherReplayPlayerState[] players)
        {
            if (players == null)
            {
                return;
            }

            for (int i = 0; i < players.Length; i++)
            {
                Stage7BTeacherReplayPlayerState p = players[i];
                Owner owner = MapPlayerId(p.player_id);
                int current = _match.GetResources(owner);
                int delta = p.resources - current;
                if (delta != 0)
                {
                    _match.AddResources(owner, delta);
                }
            }
        }

        private void ClearCurrentRuntimeState()
        {
            List<UnitRuntime> units = _registry.GetAllUnits();
            for (int i = 0; i < units.Count; i++)
            {
                UnitRuntime unit = units[i];
                if (unit == null)
                {
                    continue;
                }

                _grid.RemoveUnit(unit.GridPos);
                _registry.Unregister(unit);
                if (Application.isPlaying)
                {
                    UnityEngine.Object.Destroy(unit.gameObject);
                }
                else
                {
                    UnityEngine.Object.DestroyImmediate(unit.gameObject);
                }
            }

            _registry.Clear();
            _grid.InitGrid(GameConstants.MapWidth, GameConstants.MapHeight);
            _resources.Clear();
            _match.ResetMatch();
        }

        private int CountResourceNodes()
        {
            int count = 0;
            foreach (ResourceNode _ in _resources.GetAllResourceNodes())
            {
                count++;
            }

            return count;
        }

        private static bool IsResourceType(string unitType)
        {
            return string.Equals(unitType, "Resource", StringComparison.OrdinalIgnoreCase);
        }

        private static bool TryParseUnitType(string type, out UnitType unitType)
        {
            unitType = UnitType.Worker;
            if (string.IsNullOrWhiteSpace(type))
            {
                return false;
            }

            switch (type.Trim())
            {
                case "Base": unitType = UnitType.Base; return true;
                case "Barracks": unitType = UnitType.Barracks; return true;
                case "Worker": unitType = UnitType.Worker; return true;
                case "Light": unitType = UnitType.Light; return true;
                case "Heavy": unitType = UnitType.Heavy; return true;
                case "Ranged": unitType = UnitType.Ranged; return true;
                default: return false;
            }
        }

        private static Owner MapOwner(int owner)
        {
            return owner switch
            {
                0 => Owner.Player1,
                1 => Owner.Player2,
                _ => Owner.Neutral,
            };
        }

        private static Owner MapPlayerId(int playerId)
        {
            return playerId == 1 ? Owner.Player2 : Owner.Player1;
        }
    }
}
