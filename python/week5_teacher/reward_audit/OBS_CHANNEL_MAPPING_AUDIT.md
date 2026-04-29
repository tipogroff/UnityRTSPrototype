# OBS_CHANNEL_MAPPING_AUDIT

## Environment
- env_id: MicrortsSelfPlayShapedReward-v1
- map_path: maps/24x24/basesWorkers24x24.xml
- opponent_pool: passiveAI
- steps: 200

## Owner Channel Counts
- owner_neutral: 0
- owner_player1: 0
- owner_player2: 400

## Unit Channel Counts
- unit_resource: 114400
- unit_base: 0
- unit_barracks: 0
- unit_worker: 0
- unit_light: 800
- unit_heavy: 114400
- unit_ranged: 400

## Action Channel Counts
- action_noop: 400
- action_move: 113600
- action_harvest: 800
- action_return: 400
- action_produce: 0
- action_attack: 400

## Mask Alignment
- actor_valid_cells: 11
- actor_valid_cells_with_any_unit: 11
- actor_valid_with_unit_share: 1.000000

## Example actor_valid cells
- (env=0, y=1, x=1): owner=[0.0, 0.0, 0.0], unit=[1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0], valid_action_type=[1, 1, 1, 0, 1, 0]
- (env=0, y=2, x=2): owner=[0.0, 0.0, 1.0], unit=[1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0], valid_action_type=[1, 0, 0, 0, 1, 0]
- (env=0, y=1, x=1): owner=[0.0, 0.0, 0.0], unit=[1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0], valid_action_type=[1, 1, 1, 0, 1, 0]
- (env=0, y=2, x=2): owner=[0.0, 0.0, 1.0], unit=[1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0], valid_action_type=[1, 0, 0, 0, 1, 0]
- (env=0, y=0, x=1): owner=[0.0, 0.0, 0.0], unit=[1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0], valid_action_type=[1, 1, 1, 0, 1, 0]
- (env=0, y=2, x=2): owner=[0.0, 0.0, 1.0], unit=[1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0], valid_action_type=[1, 0, 0, 0, 1, 0]
- (env=0, y=2, x=2): owner=[0.0, 0.0, 1.0], unit=[1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0], valid_action_type=[1, 0, 0, 0, 1, 0]
- (env=0, y=0, x=1): owner=[0.0, 0.0, 0.0], unit=[1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0], valid_action_type=[1, 1, 1, 0, 1, 0]
- (env=0, y=2, x=2): owner=[0.0, 0.0, 1.0], unit=[1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0], valid_action_type=[1, 0, 0, 0, 1, 0]
- (env=0, y=0, x=1): owner=[0.0, 0.0, 0.0], unit=[1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0], valid_action_type=[1, 1, 1, 0, 1, 0]
- (env=0, y=0, x=1): owner=[0.0, 0.0, 0.0], unit=[1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0], valid_action_type=[1, 1, 1, 0, 1, 0]

## Warnings
- env.action_masks returned 78 channels; source_unit_mask missing, actor/source reconstructed from action_type validity
