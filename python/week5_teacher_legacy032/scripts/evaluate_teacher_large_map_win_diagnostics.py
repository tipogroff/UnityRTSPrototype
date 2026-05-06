from legacy032_policy_action import Legacy032Policy  # noqa: F401
from evaluate_teacher_legacy032 import main

# Delegates to evaluate_teacher_legacy032.py, which defaults to --step-mode training_compatible.

if __name__ == "__main__":
    raise SystemExit(main())
