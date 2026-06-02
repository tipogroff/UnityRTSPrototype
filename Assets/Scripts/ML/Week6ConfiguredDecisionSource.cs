using System;
using RTS.Core;
using RTS.Presentation;

namespace RTS.ML
{
    public sealed class Week6ConfiguredDecisionSource : IDecisionSource
    {
        private readonly HeuristicPolicyAdapter _heuristicAdapter;
        private readonly Week6StudentPolicyAdapter _studentAdapter;
        private readonly Week6PlayerControlMode _player1Mode;
        private readonly Week6PlayerControlMode _player2Mode;

        public Week6ConfiguredDecisionSource(
            HeuristicPolicyAdapter heuristicAdapter,
            Week6StudentPolicyAdapter studentAdapter,
            Week6PlayerControlMode player1Mode,
            Week6PlayerControlMode player2Mode)
        {
            _heuristicAdapter = heuristicAdapter;
            _studentAdapter = studentAdapter;
            _player1Mode = player1Mode;
            _player2Mode = player2Mode;

            ValidateSideConfiguration(Owner.Player1, _player1Mode, _heuristicAdapter, _studentAdapter);
            ValidateSideConfiguration(Owner.Player2, _player2Mode, _heuristicAdapter, _studentAdapter);
        }

        public string SourceMode => $"week6-mixed:p1={_player1Mode},p2={_player2Mode}";

        public PolicyExecutionReport Execute(RlLoopStepInput stepInput)
        {
            int accepted = 0;
            int rejected = 0;

            if (_heuristicAdapter != null)
            {
                _heuristicAdapter.SetPlayerControlModes(
                    _player1Mode == Week6PlayerControlMode.HeuristicBaseline ? HeuristicControlMode.Heuristic : HeuristicControlMode.Idle,
                    _player2Mode == Week6PlayerControlMode.HeuristicBaseline ? HeuristicControlMode.Heuristic : HeuristicControlMode.Idle);

                using (HumanPlayCommandSourceDiagnostics.PushSource($"Week6ConfiguredDecisionSource.Heuristic[p1={_player1Mode},p2={_player2Mode}]"))
                {
                    var heuristicTotals = _heuristicAdapter.ExecuteDecisionStepWithCounts(stepInput);
                    accepted += heuristicTotals.acceptedTotal;
                    rejected += heuristicTotals.rejectedTotal;
                }
            }

            if (_studentAdapter != null)
            {
                if (_player1Mode == Week6PlayerControlMode.StudentInference)
                {
                    StudentPolicyExecutionReport p1Report = _studentAdapter.ExecuteDecision(Owner.Player1, stepInput);
                    accepted += p1Report.AcceptedCount;
                    rejected += p1Report.RejectedCount;
                }

                if (_player2Mode == Week6PlayerControlMode.StudentInference)
                {
                    StudentPolicyExecutionReport p2Report = _studentAdapter.ExecuteDecision(Owner.Player2, stepInput);
                    accepted += p2Report.AcceptedCount;
                    rejected += p2Report.RejectedCount;
                }
            }

            return new PolicyExecutionReport(null, accepted, rejected, null, null, countsAvailable: true);
        }

        private static void ValidateSideConfiguration(
            Owner side,
            Week6PlayerControlMode mode,
            HeuristicPolicyAdapter heuristicAdapter,
            Week6StudentPolicyAdapter studentAdapter)
        {
            switch (mode)
            {
                case Week6PlayerControlMode.Idle:
                    return;

                case Week6PlayerControlMode.HeuristicBaseline:
                    if (heuristicAdapter == null)
                    {
                        throw new InvalidOperationException($"[Week6ConfiguredDecisionSource] Side {side} is set to HeuristicBaseline, but HeuristicPolicyAdapter is missing.");
                    }
                    return;

                case Week6PlayerControlMode.StudentInference:
                    if (studentAdapter == null)
                    {
                        throw new InvalidOperationException($"[Week6ConfiguredDecisionSource] Side {side} is set to StudentInference, but Week6StudentPolicyAdapter is missing.");
                    }
                    return;

                default:
                    throw new InvalidOperationException($"[Week6ConfiguredDecisionSource] Unsupported control mode {mode} for side {side}.");
            }
        }
    }
}