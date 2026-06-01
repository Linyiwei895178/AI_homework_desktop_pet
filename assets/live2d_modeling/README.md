# Live2D Modeling Assets

The active modeling flow uses anatomy line-art bases:

- `anatomy_lineart_bases/male_standing_anatomy_lineart.png`
- `anatomy_lineart_bases/male_standing_anatomy_lineart_transparent.png`
- `anatomy_lineart_bases/female_standing_anatomy_lineart.png`
- `anatomy_lineart_bases/female_standing_anatomy_lineart_transparent.png`
- `anatomy_lineart_bases/anatomy_parameters.json`
- `anatomy_lineart_bases/manifest.json`
- `tools/render_anatomy_lineart_model.py`

The app's Live2D modeling entry lets the user choose male or female first, then adjust anatomy sliders for proportion, torso shape, muscle volume, and line detail. It exports a modeling project under `custom_bases/`.

`base_front_template/` is kept as a legacy reference folder. It is no longer the main modeling entry.

`pose_study/` contains the PDF pose analysis, selected reference sheets, pose taxonomy, and the Live2D rig specification for converting these anatomy bases into layered, pose-aware models.
