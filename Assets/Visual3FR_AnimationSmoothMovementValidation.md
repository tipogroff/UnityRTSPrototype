# Visual-3F-R Animation + Smooth Movement Validation

- Generated UTC: 2026-05-12T21:14:17.8495525Z

## Mode A (Smooth Disabled)
- Idle playback healthy: True
- Units with owner marker issues: 0
- Units with bridge/interpolator moving mismatch: 0

## Mode B (Smooth Enabled)
- Idle playback healthy: False
- Units with owner marker issues: 0
- Units interpolating: 0
- Units with excessive snaps: 2

## Trace
- Lines: 7806
- Started count: 3616
- Completed count: 3534
- Snapped count: 520
- Repeated snap same frame count: 464

## Final Recommendation
- Smooth movement default: Disabled
- Mode A idle healthy: True
- Mode B idle healthy: False
- Mode B no excessive snaps: False
- Smooth enabled validated: False
- Note: Smooth movement should remain disabled by default until snap/jerk regressions are eliminated.
