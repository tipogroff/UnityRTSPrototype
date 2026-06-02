using RTS.Core;

namespace RTS.Presentation
{
    public enum HumanPlayMode
    {
        AIvsAI = 0,
        Player1vsAI = 1,
        AIvsPlayer2 = 2,
        Player1vsScriptedOrHeuristic = 3,
        PausedDemo = 4,
        AIvsBot = 5,
    }

    public readonly struct HumanPlayModeState
    {
        public HumanPlayModeState(HumanPlayMode mode, bool hasHumanSide, Owner humanSide, string diagnostics)
        {
            Mode = mode;
            HasHumanSide = hasHumanSide;
            HumanSide = humanSide;
            Diagnostics = diagnostics ?? string.Empty;
        }

        public HumanPlayMode Mode { get; }
        public bool HasHumanSide { get; }
        public Owner HumanSide { get; }
        public string Diagnostics { get; }
    }
}
