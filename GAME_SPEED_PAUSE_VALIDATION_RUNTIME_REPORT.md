# Game Speed Pause Runtime Validation
Started at realtime=8,29
## Mode=AIvsPlayer
[PauseValidation] Mode=AIvsPlayer Step counter growing: 11 -> 35 PASS
[PauseValidation] Mode=AIvsPlayer RequestPause External pausedStep=35 activeReasons=External episodePaused=True
[PauseValidation] Mode=AIvsPlayer After 2.0s step=35 PASS stopped
[PauseValidation] Mode=AIvsPlayer StepOnce returned=True step 35 -> 36 PASS single step
[PauseValidation] Mode=AIvsPlayer After Step wait 2.0s step=36 PASS still paused
[PauseValidation] Mode=AIvsPlayer After resume step=42 PASS resumed
## Mode=AIvsBot
[PauseValidation] Mode=AIvsBot Step counter growing: 19 -> 25 PASS
[PauseValidation] Mode=AIvsBot RequestPause External pausedStep=25 activeReasons=External episodePaused=True
[PauseValidation] Mode=AIvsBot After 2.0s step=25 PASS stopped
[PauseValidation] Mode=AIvsBot StepOnce returned=True step 25 -> 26 PASS single step
[PauseValidation] Mode=AIvsBot After Step wait 2.0s step=26 PASS still paused
[PauseValidation] Mode=AIvsBot After resume step=32 PASS resumed
## Mode=AIvsAI
[PauseValidation] Mode=AIvsAI Step counter growing: 18 -> 22 PASS
[PauseValidation] Mode=AIvsAI RequestPause External pausedStep=22 activeReasons=External episodePaused=True
[PauseValidation] Mode=AIvsAI After 2.0s step=22 PASS stopped
[PauseValidation] Mode=AIvsAI StepOnce returned=True step 22 -> 23 PASS single step
[PauseValidation] Mode=AIvsAI After Step wait 2.0s step=23 PASS still paused
[PauseValidation] Mode=AIvsAI After resume step=29 PASS resumed
RESULT: PASS
