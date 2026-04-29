# REWARD_SANITY_REPORT

- Decision: PARTIAL_PASS_REWARD_SANITY
- Modes present: noop, random_valid, scripted_probe

## Mode Summary
- noop: status=ok, reward_total=0.000000, reward_nonzero_steps=0, done=4, terminal=0, timeout=0, invalid_action_attempts=18000
- random_valid: status=ok, reward_total=12.000000, reward_nonzero_steps=12, done=4, terminal=0, timeout=0, invalid_action_attempts=15606
- scripted_probe: status=ok, reward_total=0.000000, reward_nonzero_steps=0, done=4, terminal=0, timeout=0, invalid_action_attempts=18000

## Decision Vocabulary
- PASS_REWARD_SANITY
- PARTIAL_PASS_REWARD_SANITY
- FAIL_REWARD_ALL_ZERO
- FAIL_REWARD_ENV_ERROR
- INCONCLUSIVE_NEEDS_MANUAL_CHECK
