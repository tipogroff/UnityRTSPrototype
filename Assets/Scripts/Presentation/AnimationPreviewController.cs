using System;
using UnityEngine;

namespace RTS.Presentation
{
    public sealed class AnimationPreviewController : MonoBehaviour
    {
        private static readonly int IsMovingHash = Animator.StringToHash("IsMoving");
        private static readonly int AttackHash = Animator.StringToHash("Attack");
        private static readonly int DeathHash = Animator.StringToHash("Death");
        private static readonly int HarvestHash = Animator.StringToHash("Harvest");

        [SerializeField] private Animator animator;
        [SerializeField] private bool autoCycle = true;
        [SerializeField] private float idleSeconds = 2f;
        [SerializeField] private float walkSeconds = 2f;
        [SerializeField] private float attackSeconds = 1.25f;
        [SerializeField] private float harvestSeconds = 1.25f;
        [SerializeField] private float deathSeconds = 1.5f;

        private float _timer;
        private PreviewPhase _phase;

        private enum PreviewPhase
        {
            Idle,
            Walk,
            Attack,
            Harvest,
            Death
        }

        private void Awake()
        {
            if (animator == null)
            {
                animator = GetComponentInChildren<Animator>(true);
            }
        }

        private void OnEnable()
        {
            ResetToIdle();
        }

        private void Update()
        {
            if (animator == null)
            {
                return;
            }

            HandleKeyboard();
            if (!autoCycle)
            {
                return;
            }

            _timer += Time.deltaTime;
            switch (_phase)
            {
                case PreviewPhase.Idle:
                    if (_timer >= idleSeconds)
                    {
                        SetWalk(true);
                    }
                    break;
                case PreviewPhase.Walk:
                    if (_timer >= walkSeconds)
                    {
                        PlayAttack();
                    }
                    break;
                case PreviewPhase.Attack:
                    if (_timer >= attackSeconds)
                    {
                        PlayHarvest();
                    }
                    break;
                case PreviewPhase.Harvest:
                    if (_timer >= harvestSeconds)
                    {
                        PlayDeath();
                    }
                    break;
                case PreviewPhase.Death:
                    if (_timer >= deathSeconds)
                    {
                        ResetToIdle();
                    }
                    break;
                default:
                    throw new ArgumentOutOfRangeException();
            }
        }

        private void HandleKeyboard()
        {
            if (Input.GetKeyDown(KeyCode.Alpha1))
            {
                ResetToIdle();
            }
            else if (Input.GetKeyDown(KeyCode.Alpha2))
            {
                SetWalk(true);
            }
            else if (Input.GetKeyDown(KeyCode.Alpha3))
            {
                PlayAttack();
            }
            else if (Input.GetKeyDown(KeyCode.Alpha4))
            {
                PlayHarvest();
            }
            else if (Input.GetKeyDown(KeyCode.Alpha5))
            {
                PlayDeath();
            }
        }

        public void ResetToIdle()
        {
            ResetTriggers();
            animator.SetBool(IsMovingHash, false);
            animator.Play("Idle", 0, 0f);
            _phase = PreviewPhase.Idle;
            _timer = 0f;
        }

        public void SetWalk(bool value)
        {
            ResetTriggers();
            animator.SetBool(IsMovingHash, value);
            if (!value)
            {
                animator.Play("Idle", 0, 0f);
                _phase = PreviewPhase.Idle;
            }
            else
            {
                animator.Play("Walk", 0, 0f);
                _phase = PreviewPhase.Walk;
            }

            _timer = 0f;
        }

        public void PlayAttack()
        {
            animator.SetBool(IsMovingHash, false);
            Trigger(AttackHash);
            animator.Play("Attack", 0, 0f);
            _phase = PreviewPhase.Attack;
            _timer = 0f;
        }

        public void PlayHarvest()
        {
            animator.SetBool(IsMovingHash, false);
            Trigger(HarvestHash);
            animator.Play("HarvestFallback", 0, 0f);
            _phase = PreviewPhase.Harvest;
            _timer = 0f;
        }

        public void PlayDeath()
        {
            animator.SetBool(IsMovingHash, false);
            Trigger(DeathHash);
            animator.Play("Death", 0, 0f);
            _phase = PreviewPhase.Death;
            _timer = 0f;
        }

        private void Trigger(int hash)
        {
            ResetTriggers();
            animator.SetTrigger(hash);
        }

        private void ResetTriggers()
        {
            animator.ResetTrigger(AttackHash);
            animator.ResetTrigger(DeathHash);
            animator.ResetTrigger(HarvestHash);
        }
    }
}