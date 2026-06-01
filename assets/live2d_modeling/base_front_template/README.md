# Live2D Front Base Template

This folder contains two front-view white mannequin bases.

## High-fidelity AI cut base

Use this first when visual quality matters:

- `ai_chroma_front_reference_transparent.png`: high-fidelity transparent white mannequin.
- `ai_cut_layers/full_base.png`: normalized 1024x1536 full transparent base.
- `ai_cut_layers/layered_preview.png`: default recomposed preview from the cut layers.
- `ai_cut_layers/global_fit_comparison.png`: target/reference comparison for the high-fidelity base after global alignment.
- `ai_cut_layers/manifest.json`: layer order and cut-layer metadata.
- `ai_cut_layers/*.png`: Live2D-friendly cut layers for head, ears, torso, arms, hands, legs, neck, and face relief.

These are raster cut layers. They are suitable as source art for Live2D/Cubism rigging, but they are not a finished `.moc3` model.

## Procedural editable base

Use this when code-side repeatability matters:

- `base_front_preview.png`: procedural smooth front-view mannequin.
- `base_front_with_guides.png`: same base with body/face guides.
- `face_front_construction.png`: front face construction guide.
- `layers/*.png`: editable procedural layers.
- `base_front_manifest.json`: draw order, anchors, and suggested Live2D parameters.

## Reference fitting

The fitting outputs are in `fit_to_reference/`.

- `comparison.png`: target, optimized candidate, and difference map.
- `fit_report.json`: loss, iteration count, best parameters, and history.
- `target_normalized.png`: the cropped user reference used as target.
- `optimized_candidate_transparent.png`: fitted procedural candidate.

Regenerate assets with:

```powershell
& 'C:\Users\醨\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' tools\extract_ai_live2d_layers.py
& 'C:\Users\醨\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' tools\fit_live2d_base_to_reference.py --target 'C:\Users\醨\xwechat_files\wxid_odh8547copbs32_bb21\temp\RWTemp\2026-06\40f32654c2889e4312cd53deb0bda6c1.png' --crop 395,540,395,1240 --iterations 520 --seed 13
```
