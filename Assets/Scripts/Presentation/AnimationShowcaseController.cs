using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using UnityEngine;
using UnityEngine.InputSystem;

namespace RTS.Presentation
{
    public sealed class AnimationShowcaseController : MonoBehaviour
    {
        private enum ShowcaseState
        {
            Idle,
            Walk,
            Attack,
            Harvest,
            Death
        }

        [SerializeField] private AnimationPreviewController[] characters;
        [SerializeField] private bool autoCycle;
        [SerializeField] private float idleSeconds = 1.75f;
        [SerializeField] private float walkSeconds = 1.75f;
        [SerializeField] private float attackSeconds = 1.5f;
        [SerializeField] private float harvestSeconds = 1.5f;
        [SerializeField] private float deathSeconds = 1.75f;
        [SerializeField] private bool showOverlay = true;
        [SerializeField] private int demoStateIndex;

        private readonly List<CharacterSnapshot> _snapshots = new List<CharacterSnapshot>(4);
        private readonly ShowcaseState[] _states =
        {
            ShowcaseState.Idle,
            ShowcaseState.Walk,
            ShowcaseState.Attack,
            ShowcaseState.Harvest,
            ShowcaseState.Death
        };

        private ShowcaseState _currentState = ShowcaseState.Idle;
        private int _appliedStateIndex = -1;
        private float _stateTimer;

        private struct CharacterSnapshot
        {
            public AnimationPreviewController Controller;
            public Vector3 LocalPosition;
            public Quaternion LocalRotation;
            public Vector3 LocalScale;
        }

        private void Awake()
        {
            ResolveCharacters();
            CacheSnapshots();
            ApplySafetyDefaults();
            ApplyState(ShowcaseState.Idle, true);
        }

        private void Update()
        {
            SyncRequestedState();
            HandleHotkeys();

            if (!autoCycle)
            {
                return;
            }

            _stateTimer += Time.deltaTime;
            if (_stateTimer < GetCurrentStateDuration())
            {
                return;
            }

            NextState();
        }

        private void ResolveCharacters()
        {
            if (characters != null && characters.Length > 0)
            {
                return;
            }

            characters = FindObjectsByType<AnimationPreviewController>(FindObjectsSortMode.None)
                .OrderBy(controller => controller.name, StringComparer.Ordinal)
                .ToArray();
        }

        private void CacheSnapshots()
        {
            _snapshots.Clear();

            foreach (var controller in characters ?? Array.Empty<AnimationPreviewController>())
            {
                if (controller == null)
                {
                    continue;
                }

                var transformRef = controller.transform;
                _snapshots.Add(new CharacterSnapshot
                {
                    Controller = controller,
                    LocalPosition = transformRef.localPosition,
                    LocalRotation = transformRef.localRotation,
                    LocalScale = transformRef.localScale
                });
            }
        }

        private void ApplySafetyDefaults()
        {
            foreach (var snapshot in _snapshots)
            {
                snapshot.Controller.SetKeyboardInput(false);
                snapshot.Controller.SetAutoCycle(false);
            }
        }

        private void HandleHotkeys()
        {
            if (WasPressed(Key.Digit1))
            {
                PlayIdle();
            }
            else if (WasPressed(Key.Digit2))
            {
                PlayWalk();
            }
            else if (WasPressed(Key.Digit3))
            {
                PlayAttack();
            }
            else if (WasPressed(Key.Digit4))
            {
                PlayHarvest();
            }
            else if (WasPressed(Key.Digit5))
            {
                PlayDeath();
            }
            else if (WasPressed(Key.R))
            {
                ResetCharacters();
            }
            else if (WasPressed(Key.A))
            {
                ToggleAutoCycle();
            }
            else if (WasPressed(Key.Space))
            {
                NextState();
            }
        }

        private static bool WasPressed(Key key)
        {
            var keyboard = Keyboard.current;
            return keyboard != null && keyboard[key].wasPressedThisFrame;
        }

        public void PlayIdle()
        {
            demoStateIndex = 0;
            ApplyState(ShowcaseState.Idle, true);
        }

        public void PlayWalk()
        {
            demoStateIndex = 1;
            ApplyState(ShowcaseState.Walk, true);
        }

        public void PlayAttack()
        {
            demoStateIndex = 2;
            ApplyState(ShowcaseState.Attack, true);
        }

        public void PlayHarvest()
        {
            demoStateIndex = 3;
            ApplyState(ShowcaseState.Harvest, true);
        }

        public void PlayDeath()
        {
            demoStateIndex = 4;
            ApplyState(ShowcaseState.Death, true);
        }

        public void ResetCharacters()
        {
            foreach (var snapshot in _snapshots)
            {
                if (snapshot.Controller == null)
                {
                    continue;
                }

                var transformRef = snapshot.Controller.transform;
                transformRef.localPosition = snapshot.LocalPosition;
                transformRef.localRotation = snapshot.LocalRotation;
                transformRef.localScale = snapshot.LocalScale;
                snapshot.Controller.SetKeyboardInput(false);
                snapshot.Controller.SetAutoCycle(false);
                snapshot.Controller.RebindAnimator();
                snapshot.Controller.ResetToIdle();
            }

            autoCycle = false;
            _currentState = ShowcaseState.Idle;
            _appliedStateIndex = 0;
            demoStateIndex = 0;
            _stateTimer = 0f;
            LogStateSnapshot("Reset");
        }

        public void ToggleAutoCycle()
        {
            autoCycle = !autoCycle;
            _stateTimer = 0f;
            LogStateSnapshot(autoCycle ? "AutoCycleOn" : "AutoCycleOff");
        }

        public void NextState()
        {
            var nextIndex = Array.IndexOf(_states, _currentState) + 1;
            if (nextIndex >= _states.Length)
            {
                nextIndex = 0;
            }

            ApplyState(_states[nextIndex], true);
        }

        private void ApplyState(ShowcaseState state, bool resetTimer)
        {
            _currentState = state;
            _appliedStateIndex = Array.IndexOf(_states, state);
            if (resetTimer)
            {
                _stateTimer = 0f;
            }

            foreach (var snapshot in _snapshots)
            {
                if (snapshot.Controller == null)
                {
                    continue;
                }

                snapshot.Controller.SetKeyboardInput(false);
                snapshot.Controller.SetAutoCycle(false);

                switch (state)
                {
                    case ShowcaseState.Idle:
                        snapshot.Controller.ResetToIdle();
                        break;
                    case ShowcaseState.Walk:
                        snapshot.Controller.SetWalk(true);
                        break;
                    case ShowcaseState.Attack:
                        snapshot.Controller.PlayAttack();
                        break;
                    case ShowcaseState.Harvest:
                        snapshot.Controller.PlayHarvest();
                        break;
                    case ShowcaseState.Death:
                        snapshot.Controller.PlayDeath();
                        break;
                    default:
                        throw new ArgumentOutOfRangeException(nameof(state), state, null);
                }
            }

            if (resetTimer)
            {
                _stateTimer = 0f;
            }

            LogStateSnapshot(state.ToString());
        }

        private void SyncRequestedState()
        {
            if (demoStateIndex == _appliedStateIndex)
            {
                return;
            }

            if (demoStateIndex < 0 || demoStateIndex >= _states.Length)
            {
                demoStateIndex = 0;
            }

            ApplyState(_states[demoStateIndex], true);
        }

        private float GetCurrentStateDuration()
        {
            switch (_currentState)
            {
                case ShowcaseState.Idle:
                    return idleSeconds;
                case ShowcaseState.Walk:
                    return walkSeconds;
                case ShowcaseState.Attack:
                    return attackSeconds;
                case ShowcaseState.Harvest:
                    return harvestSeconds;
                case ShowcaseState.Death:
                    return deathSeconds;
                default:
                    return idleSeconds;
            }
        }

        private void LogStateSnapshot(string label)
        {
            var builder = new StringBuilder();
            builder.Append("[AnimationShowcase] ");
            builder.Append(label);
            builder.Append(" | autoCycle=");
            builder.Append(autoCycle ? "on" : "off");

            foreach (var snapshot in _snapshots)
            {
                if (snapshot.Controller == null || snapshot.Controller.AnimatorComponent == null)
                {
                    continue;
                }

                var animator = snapshot.Controller.AnimatorComponent;
                var stateInfo = animator.GetCurrentAnimatorStateInfo(0);
                builder.Append(" | ");
                builder.Append(snapshot.Controller.name);
                builder.Append(':');
                builder.Append(snapshot.Controller.CurrentPhaseName);
                builder.Append(" nt=");
                builder.Append(stateInfo.normalizedTime.ToString("0.00"));
            }

            Debug.Log(builder.ToString(), this);
        }

        private void OnGUI()
        {
            if (!showOverlay)
            {
                return;
            }

            GUI.Box(new Rect(12f, 12f, 560f, 180f), "Animation Showcase");
            GUI.Label(new Rect(24f, 40f, 540f, 20f), $"State: {_currentState}  AutoCycle: {(autoCycle ? "On" : "Off")}  Selector: {demoStateIndex}");
            GUI.Label(new Rect(24f, 62f, 540f, 20f), "1 Idle  2 Walk  3 Attack  4 Harvest  5 Death  R Reset  A AutoCycle  Space Next");
            GUI.Label(new Rect(24f, 84f, 540f, 20f), $"Characters: {_snapshots.Count}");

            for (var i = 0; i < _snapshots.Count; i++)
            {
                var snapshot = _snapshots[i];
                if (snapshot.Controller == null || snapshot.Controller.AnimatorComponent == null)
                {
                    continue;
                }

                var animator = snapshot.Controller.AnimatorComponent;
                var stateInfo = animator.GetCurrentAnimatorStateInfo(0);
                GUI.Label(new Rect(24f, 108f + i * 18f, 540f, 18f), $"{snapshot.Controller.name}: {snapshot.Controller.CurrentPhaseName} / nt={stateInfo.normalizedTime:0.00}");
            }
        }
    }
}
