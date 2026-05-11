Status: VISUAL_ENVIRONMENT_BASELINE_GO

Base visual:
- TowerHouse_SecondAge
- fallback MeshRenderer disabled

Barracks visual:
- Barracks_FirstAge_Level1
- fallback MeshRenderer disabled

Resource visual:
- Resource_Gold_1
- green cube fallback disabled
- root BoxCollider preserved/restored

Environment:
- Env_Rock_A
- Env_Rock_B
- Env_Tree_A
- Env_Tree_B

Important invariant:
- all visual changes are presentation-layer only
- gameplay root transforms/scripts/colliders/AI contracts unchanged