# Pose Study

This folder captures the pose analysis pass over the two anatomy PDF references.

Generated reference assets:

- `pose_candidates_index.json`: full scanned-page feature index and selected references.
- `pose_candidates_sheet_1.jpg` through `pose_candidates_sheet_4.jpg`: 96 selected pose candidates.
- `selected_pages/`: rendered selected pose pages.
- `pose_taxonomy.json`: learned pose families and anatomy notes.
- `live2d_pose_rig_spec.json`: Live2D layer, pivot, parameter, and pose-preset plan.

## Live2D Feasibility

The male and female anatomy line-art bases can be converted into Live2D source art, but not by treating the full body as a single image. The next production step is to cut the model into overlapping transparent parts:

- head and neck
- chest, abdomen, pelvis, obliques
- left/right upper arm, forearm, hand, deltoid and elbow covers
- left/right thigh, shin, foot, hip and knee covers
- separate muscle-detail and construction-line layers

Small and medium poses are practical in one Live2D rig: breathing, idle sway, head turn, shoulder/hip counter-tilt, moderate arm raise, leg step, and muscle-line emphasis.

Very large poses from the PDFs, such as kneeling, crouching, jumping, deep side views, and heavy foreshortening, should be alternate pose artwork or separate motion-specific layer sets. A single front-facing model should not be expected to deform cleanly into every extreme pose.
