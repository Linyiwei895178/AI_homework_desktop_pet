from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw


CANVAS = (1024, 1536)
ROOT = Path("assets/live2d_modeling/anatomy_lineart_bases")
MANIFEST_FILE = ROOT / "manifest.json"
PARAM_FILE = ROOT / "anatomy_parameters.json"
OUT_DIR = Path("assets/live2d_modeling/custom_bases")


def load_manifest() -> dict[str, Any]:
    return json.loads(MANIFEST_FILE.read_text(encoding="utf-8"))


def load_parameter_schema() -> dict[str, Any]:
    return json.loads(PARAM_FILE.read_text(encoding="utf-8"))


def load_parameter_defaults() -> tuple[dict[str, float], dict[str, tuple[float, float]]]:
    schema = load_parameter_schema()
    defaults: dict[str, float] = {}
    bounds: dict[str, tuple[float, float]] = {}
    for group in schema.get("groups", []):
        for item in group.get("parameters", []):
            key = str(item.get("key") or "")
            if not key:
                continue
            defaults[key] = float(item.get("default", 0))
            bounds[key] = (float(item.get("min", 0)), float(item.get("max", 100)))
    return defaults, bounds


def load_user_params(path: Path | None) -> dict[str, float]:
    if path is None:
        return {}
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    raw = data.get("params", data) if isinstance(data, dict) else {}
    return {str(key): float(value) for key, value in raw.items()}


def build_params(user_param_path: Path | None = None) -> dict[str, float]:
    defaults, bounds = load_parameter_defaults()
    params = dict(defaults)
    params.update(load_user_params(user_param_path))
    return clamp_params(params, bounds)


def clamp_params(
    params: dict[str, float],
    bounds: dict[str, tuple[float, float]] | None = None,
) -> dict[str, float]:
    if bounds is None:
        _defaults, bounds = load_parameter_defaults()
    out = dict(params)
    for key, (lo, hi) in bounds.items():
        value = float(out.get(key, lo))
        out[key] = max(lo, min(hi, value))
    return out


def pct(params: dict[str, float], key: str) -> float:
    return float(params.get(key, 100.0)) / 100.0


def smoothstep(edge0: float, edge1: float, x: float) -> float:
    if edge0 == edge1:
        return 1.0 if x >= edge1 else 0.0
    t = max(0.0, min(1.0, (x - edge0) / (edge1 - edge0)))
    return t * t * (3.0 - 2.0 * t)


def region_window(y: float, top: float, bottom: float, feather: float = 70.0) -> float:
    return smoothstep(top, top + feather, y) * (1.0 - smoothstep(bottom - feather, bottom, y))


def gaussian_influence(x: float, center: float, radius: float) -> float:
    if radius <= 0:
        return 0.0
    return math.exp(-((x - center) / radius) ** 2)


def base_file(base_id: str, asset_key: str) -> Path:
    manifest = load_manifest()
    bases = manifest.get("bases", {})
    if base_id not in bases:
        raise ValueError(f"unknown anatomy base: {base_id}")
    filename = bases[base_id].get(asset_key)
    if not filename:
        raise ValueError(f"base {base_id!r} has no {asset_key!r} asset")
    return ROOT / filename


def load_base_image(base_id: str) -> Image.Image:
    transparent = base_file(base_id, "transparent")
    if transparent.is_file():
        return Image.open(transparent).convert("RGBA")
    return Image.open(base_file(base_id, "preview")).convert("RGBA")


def width_profile(y: float, params: dict[str, float]) -> float:
    scale = 1.0
    scale += (pct(params, "head_size") - 1.0) * 0.50 * region_window(y, 20, 255, 55)
    scale += (pct(params, "shoulder_width") - 1.0) * 0.96 * region_window(y, 205, 405, 75)
    scale += (pct(params, "chest_width") - 1.0) * 0.82 * region_window(y, 300, 575, 82)
    scale += (pct(params, "chest_muscle") - 1.0) * 0.34 * region_window(y, 300, 555, 76)
    scale += (pct(params, "waist_width") - 1.0) * 0.78 * region_window(y, 500, 725, 76)
    scale += (pct(params, "hip_width") - 1.0) * 0.86 * region_window(y, 640, 890, 86)
    scale += (pct(params, "thigh_muscle") - 1.0) * 0.22 * region_window(y, 785, 1065, 92)
    scale += (pct(params, "calf_muscle") - 1.0) * 0.16 * region_window(y, 1060, 1335, 92)
    return max(0.72, min(1.34, scale))


def vertical_source_y(y: float, params: dict[str, float]) -> float:
    baseline = 1450.0
    y = baseline + (y - baseline) / pct(params, "overall_height")
    head_scale = 1.0 + (pct(params, "head_size") - 1.0) * 0.54
    head_center = 142.0
    head_weight = region_window(y, 20, 265, 58)
    y = y + (head_center + (y - head_center) / head_scale - y) * head_weight
    y -= (float(params.get("torso_length", 100.0)) - 100.0) * 2.10 * smoothstep(270, 900, y)
    y -= (float(params.get("leg_length", 100.0)) - 100.0) * 2.45 * smoothstep(735, 1435, y)
    return y


def inverse_local_limb_x(x: float, y: float, params: dict[str, float]) -> float:
    upper_arm_scale = 1.0 + (pct(params, "arm_muscle") - 1.0) * 0.58
    forearm_scale = 1.0 + (pct(params, "forearm_muscle") - 1.0) * 0.54
    thigh_scale = 1.0 + (pct(params, "thigh_muscle") - 1.0) * 0.54
    calf_scale = 1.0 + (pct(params, "calf_muscle") - 1.0) * 0.52

    arm_upper_y = region_window(y, 245, 610, 84)
    arm_fore_y = region_window(y, 560, 930, 96)
    thigh_y = region_window(y, 745, 1085, 94)
    calf_y = region_window(y, 1030, 1335, 96)

    for center in (336.0, 688.0):
        upper_influence = arm_upper_y * gaussian_influence(x, center, 92.0)
        fore_influence = arm_fore_y * gaussian_influence(x, center, 78.0)
        if upper_influence > 0.002:
            scale = 1.0 + (upper_arm_scale - 1.0) * upper_influence
            x = center + (x - center) / scale
        if fore_influence > 0.002:
            scale = 1.0 + (forearm_scale - 1.0) * fore_influence
            x = center + (x - center) / scale

    for center in (430.0, 594.0):
        thigh_influence = thigh_y * gaussian_influence(x, center, 96.0)
        calf_influence = calf_y * gaussian_influence(x, center, 78.0)
        if thigh_influence > 0.002:
            scale = 1.0 + (thigh_scale - 1.0) * thigh_influence
            x = center + (x - center) / scale
        if calf_influence > 0.002:
            scale = 1.0 + (calf_scale - 1.0) * calf_influence
            x = center + (x - center) / scale
    return x


def source_point(x: float, y: float, params: dict[str, float]) -> tuple[float, float]:
    sy = vertical_source_y(y, params)
    sx = 512.0 + (x - 512.0) / width_profile(sy, params)
    sx = inverse_local_limb_x(sx, sy, params)
    return max(0.0, min(CANVAS[0] - 1.0, sx)), max(0.0, min(CANVAS[1] - 1.0, sy))


def warp_image(img: Image.Image, params: dict[str, float]) -> Image.Image:
    grid_x = list(range(0, CANVAS[0], 64)) + [CANVAS[0]]
    grid_y = list(range(0, CANVAS[1], 64)) + [CANVAS[1]]
    mesh: list[tuple[tuple[int, int, int, int], tuple[float, ...]]] = []
    for y0, y1 in zip(grid_y, grid_y[1:]):
        for x0, x1 in zip(grid_x, grid_x[1:]):
            p0 = source_point(x0, y0, params)
            p1 = source_point(x0, y1, params)
            p2 = source_point(x1, y1, params)
            p3 = source_point(x1, y0, params)
            mesh.append(((x0, y0, x1, y1), (*p0, *p1, *p2, *p3)))
    return img.transform(CANVAS, Image.Transform.MESH, mesh, Image.Resampling.BICUBIC)


def qcurve(
    p0: tuple[float, float],
    p1: tuple[float, float],
    p2: tuple[float, float],
    steps: int = 24,
) -> list[tuple[float, float]]:
    out: list[tuple[float, float]] = []
    for i in range(steps + 1):
        t = i / steps
        x = (1.0 - t) ** 2 * p0[0] + 2.0 * (1.0 - t) * t * p1[0] + t * t * p2[0]
        y = (1.0 - t) ** 2 * p0[1] + 2.0 * (1.0 - t) * t * p1[1] + t * t * p2[1]
        out.append((x, y))
    return out


def draw_smooth_line(
    draw: ImageDraw.ImageDraw,
    points: list[tuple[float, float]],
    fill: tuple[int, int, int, int],
    width: int,
) -> None:
    draw.line([(round(x), round(y)) for x, y in points], fill=fill, width=width, joint="curve")


def muscle_overlay(base_id: str, params: dict[str, float]) -> Image.Image:
    definition = max(
        0.0,
        float(params.get("muscle_definition", 100.0)) - 100.0,
        float(params.get("abdomen_definition", 100.0)) - 100.0,
    )
    if definition <= 0:
        return Image.new("RGBA", CANVAS, (0, 0, 0, 0))
    alpha = max(0, min(96, round(definition * 1.25)))
    ab_alpha = max(0, min(118, round((float(params.get("abdomen_definition", 100.0)) - 100.0) * 1.55)))
    img = Image.new("RGBA", (CANVAS[0] * 2, CANVAS[1] * 2), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img, "RGBA")

    def s(point: tuple[float, float]) -> tuple[float, float]:
        return point[0] * 2.0, point[1] * 2.0

    def line(points: list[tuple[float, float]], a: int, w: int = 2) -> None:
        if a <= 0:
            return
        draw_smooth_line(draw, [s(p) for p in points], (48, 48, 48, a), w * 2)

    male = base_id == "male"
    pec_y = 342 if male else 318
    abs_top = 430 if male else 438
    abs_width = 116 if male else 84

    line(qcurve((512, pec_y + 8), (430, pec_y - 20), (352, pec_y + 64)), alpha, 2)
    line(qcurve((512, pec_y + 8), (594, pec_y - 20), (672, pec_y + 64)), alpha, 2)
    line(qcurve((352, pec_y + 64), (426, pec_y + 104), (512, pec_y + 88)), round(alpha * 0.72), 2)
    line(qcurve((672, pec_y + 64), (598, pec_y + 104), (512, pec_y + 88)), round(alpha * 0.72), 2)

    for y in (abs_top, abs_top + 66, abs_top + 132):
        line(qcurve((512 - abs_width, y), (512, y + 18), (512 + abs_width, y)), ab_alpha, 2)
    line([(512, abs_top - 36), (512, abs_top + 198)], round(ab_alpha * 0.9), 2)
    line(qcurve((396, 492), (430, 590), (410, 690)), round(alpha * 0.62), 2)
    line(qcurve((628, 492), (594, 590), (614, 690)), round(alpha * 0.62), 2)

    for side, sx in ((-1, 337), (1, 687)):
        line(qcurve((sx, 284), (sx + side * 58, 332), (sx + side * 50, 434)), alpha, 2)
        line(qcurve((sx, 514), (sx + side * 28, 625), (sx + side * 18, 760)), round(alpha * 0.65), 2)
        line(qcurve((sx, 806), (sx + side * 16, 936), (sx + side * 4, 1090)), round(alpha * 0.54), 2)

    for side, cx in ((-1, 430), (1, 594)):
        line(qcurve((cx - side * 28, 778), (cx - side * 58, 910), (cx - side * 34, 1062)), alpha, 2)
        line(qcurve((cx + side * 30, 1038), (cx + side * 54, 1166), (cx + side * 28, 1308)), round(alpha * 0.62), 2)

    return img.resize(CANVAS, Image.Resampling.LANCZOS)


def adjust_line_alpha(img: Image.Image, params: dict[str, float]) -> Image.Image:
    line_weight = pct(params, "line_weight")
    definition = pct(params, "muscle_definition")
    construction = pct(params, "construction_lines")
    alpha = img.getchannel("A")

    def map_alpha(value: int) -> int:
        if value <= 0:
            return 0
        if value < 95:
            factor = construction * (0.62 + 0.38 * definition) * line_weight
        elif value < 190:
            factor = (0.55 * construction + 0.45 * definition) * line_weight
        else:
            factor = line_weight
        return max(0, min(255, round(value * factor)))

    out = img.copy()
    out.putalpha(alpha.point(map_alpha))
    return out


def composite_preview(transparent: Image.Image) -> Image.Image:
    bg = Image.new("RGBA", CANVAS, (248, 250, 252, 255))
    bg.alpha_composite(transparent)
    return bg.convert("RGB")


def render_anatomy_base(base_id: str, params: dict[str, float]) -> Image.Image:
    base = load_base_image(base_id)
    warped = warp_image(base, params)
    overlay = warp_image(muscle_overlay(base_id, params), params)
    warped.alpha_composite(overlay)
    return adjust_line_alpha(warped, params)


def render_preview_image(
    base_id: str,
    params: dict[str, float],
    size: tuple[int, int] | None = None,
) -> Image.Image:
    defaults, bounds = load_parameter_defaults()
    merged = dict(defaults)
    merged.update(params)
    transparent = render_anatomy_base(base_id, clamp_params(merged, bounds))
    preview = composite_preview(transparent)
    if size:
        preview = preview.resize(size, Image.Resampling.LANCZOS)
    return preview


def render(base_id: str, params: dict[str, float], out_dir: Path, name: str) -> dict[str, str]:
    defaults, bounds = load_parameter_defaults()
    merged = dict(defaults)
    merged.update(params)
    merged = clamp_params(merged, bounds)
    out_dir.mkdir(parents=True, exist_ok=True)
    transparent = render_anatomy_base(base_id, merged)
    preview = composite_preview(transparent)
    transparent_path = out_dir / f"{name}_lineart_transparent.png"
    preview_path = out_dir / f"{name}_lineart_reference.png"
    params_path = out_dir / f"{name}_anatomy_params.json"
    transparent.save(transparent_path)
    preview.save(preview_path)
    params_path.write_text(json.dumps({"base": base_id, "params": merged}, ensure_ascii=False, indent=2), encoding="utf-8")
    return {
        "lineart_reference": str(preview_path),
        "lineart_transparent": str(transparent_path),
        "params": str(params_path),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Render an adjustable anatomy line-art Live2D base.")
    parser.add_argument("--base", default="male", choices=tuple(load_manifest().get("bases", {}).keys()))
    parser.add_argument("--params", type=Path, default=None)
    parser.add_argument("--out-dir", type=Path, default=OUT_DIR)
    parser.add_argument("--name", default="")
    args = parser.parse_args()
    name = args.name or f"{args.base}_anatomy"
    result = render(args.base, build_params(args.params), args.out_dir, name)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
