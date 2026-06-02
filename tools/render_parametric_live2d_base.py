from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from PIL import Image, ImageChops, ImageDraw, ImageFilter


CANVAS = (1024, 1536)
ROOT = Path("assets/live2d_modeling/base_front_template")
PARAM_FILE = ROOT / "rig_parameters.json"
PRESET_FILE = ROOT / "parameter_presets.json"
LAYER_DIR = ROOT / "ai_cut_layers"
OUT_DIR = ROOT / "parametric"

LAYER_ORDER = [
    "left_leg",
    "right_leg",
    "neck",
    "left_arm",
    "right_arm",
    "torso",
    "left_hand",
    "right_hand",
    "left_ear",
    "right_ear",
    "head",
]

SKIN_BASE = (244, 243, 237)
SKIN_LIGHT = (255, 255, 250)
SKIN_SHADOW = (220, 217, 206)
_LAYER_CACHE: dict[str, dict[str, Image.Image]] = {}


def load_parameter_schema() -> tuple[dict[str, float], dict[str, tuple[float, float]]]:
    schema = json.loads(PARAM_FILE.read_text(encoding="utf-8"))
    defaults: dict[str, float] = {}
    bounds: dict[str, tuple[float, float]] = {}
    for group in schema["groups"]:
        for item in group["parameters"]:
            key = item["key"]
            defaults[key] = float(item["default"])
            bounds[key] = (float(item["min"]), float(item["max"]))
    return defaults, bounds


def load_presets() -> dict[str, dict[str, Any]]:
    return json.loads(PRESET_FILE.read_text(encoding="utf-8")).get("presets", {})


def load_user_params(path: Path | None) -> dict[str, float]:
    if path is None:
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    raw = data.get("params", data) if isinstance(data, dict) else {}
    return {str(key): float(value) for key, value in raw.items()}


def build_params(preset: str, user_param_path: Path | None) -> dict[str, float]:
    defaults, bounds = load_parameter_schema()
    params = dict(defaults)
    presets = load_presets()
    if preset not in presets:
        raise ValueError(f"unknown preset: {preset}")
    params.update({key: float(value) for key, value in presets[preset].get("params", {}).items()})
    params.update(load_user_params(user_param_path))
    for key, value in list(params.items()):
        if key not in bounds:
            continue
        lo, hi = bounds[key]
        params[key] = max(lo, min(hi, value))
    return params


def pct(params: dict[str, float], key: str) -> float:
    return params[key] / 100.0


def load_layers() -> dict[str, Image.Image]:
    key = str(LAYER_DIR.resolve())
    if key not in _LAYER_CACHE:
        _LAYER_CACHE[key] = {
            name: Image.open(LAYER_DIR / f"{name}.png").convert("RGBA")
            for name in LAYER_ORDER
        }
    return _LAYER_CACHE[key]


def bbox_center(bbox: tuple[int, int, int, int]) -> tuple[float, float]:
    return (bbox[0] + bbox[2]) / 2, (bbox[1] + bbox[3]) / 2


def paste_scaled(
    base: Image.Image,
    layer: Image.Image,
    sx: float,
    sy: float,
    dx: float,
    dy: float,
    anchor: tuple[float, float] | None = None,
) -> tuple[int, int, int, int] | None:
    bbox = layer.getbbox()
    if bbox is None:
        return None
    crop = layer.crop(bbox)
    if anchor is None:
        anchor = bbox_center(bbox)
    new_w = max(2, round(crop.width * sx))
    new_h = max(2, round(crop.height * sy))
    scaled = crop.resize((new_w, new_h), Image.Resampling.LANCZOS)
    paste_x = round(anchor[0] + dx - (anchor[0] - bbox[0]) * sx)
    paste_y = round(anchor[1] + dy - (anchor[1] - bbox[1]) * sy)
    base.alpha_composite(scaled, (paste_x, paste_y))
    return paste_x, paste_y, paste_x + scaled.width, paste_y + scaled.height


def neutralize_head(layer: Image.Image) -> Image.Image:
    face_mask = Image.new("L", CANVAS, 0)
    draw = ImageDraw.Draw(face_mask)
    draw.ellipse((330, 238, 694, 540), fill=255)
    face_mask = face_mask.filter(ImageFilter.GaussianBlur(14))
    blurred = layer.filter(ImageFilter.GaussianBlur(18))
    return Image.composite(blurred, layer, face_mask)


def soften_torso_bottom(layer: Image.Image, params: dict[str, float]) -> Image.Image:
    spread = abs(params.get("leg_spread", 0.0)) * 0.55 + max(0.0, params.get("torso_width", 100.0) - 108.0) * 0.8
    strength = max(0.25, min(1.0, spread / 74.0))
    fade_start = round(966 - 76 * strength)
    fade_end = round(990 - 52 * strength)
    alpha = layer.getchannel("A")
    fade = Image.new("L", CANVAS, 255)
    draw = ImageDraw.Draw(fade)
    for y in range(fade_start, fade_end + 1):
        t = (y - fade_start) / max(1, fade_end - fade_start)
        falloff = (1.0 - t) ** (1.0 + 2.2 * strength)
        value = round(255 * ((1.0 - strength) + strength * falloff))
        draw.line((0, y, CANVAS[0], y), fill=max(0, min(255, value)))
    for y in range(fade_end + 1, CANVAS[1]):
        draw.line((0, y, CANVAS[0], y), fill=round(255 * max(0.0, 1.0 - strength)))
    out = layer.copy()
    out.putalpha(ImageChops.multiply(alpha, fade))
    return out


def part_transform(name: str, params: dict[str, float]) -> tuple[float, float, float, float]:
    head_sx = pct(params, "head_size") * pct(params, "head_width")
    head_sy = pct(params, "head_size") * pct(params, "head_height")
    head_dx = params["head_x"]
    head_dy = params["head_y"]
    shoulder_spread = (params["shoulder_width"] - 100.0) * 1.35
    torso_sx = pct(params, "torso_width") * pct(params, "shoulder_width")
    torso_sy = pct(params, "torso_height")
    torso_dx = 0.0
    torso_dy = params["torso_y"]
    torso_anchor_y = (518 + 984) / 2
    torso_top_delta = (518 - torso_anchor_y) * (torso_sy - 1.0) + torso_dy
    torso_bottom_delta = (984 - torso_anchor_y) * (torso_sy - 1.0) + torso_dy
    torso_side_push = (params["torso_width"] - 100.0) * 1.15
    if name == "head":
        return head_sx, head_sy, head_dx, head_dy
    if name in {"left_ear", "right_ear"}:
        side = -1.0 if name == "left_ear" else 1.0
        scale = pct(params, "ear_size")
        ear_push = (params["head_width"] - 100.0) * 1.45
        head_size_push = (head_sx - 1.0) * 220.0
        return (
            head_sx * scale,
            head_sy * scale,
            head_dx + side * (params["ear_offset_x"] + ear_push + head_size_push),
            head_dy + params["ear_y"],
        )
    if name == "neck":
        neck_dx = head_dx * 0.35 + torso_dx * 0.2
        neck_dy = params["neck_y"] + head_dy * 0.45 + torso_top_delta * 0.18
        return pct(params, "neck_width"), pct(params, "neck_length"), neck_dx, neck_dy
    if name == "torso":
        return torso_sx, torso_sy, torso_dx, torso_dy
    if name in {"left_arm", "right_arm"}:
        side = -1.0 if name == "left_arm" else 1.0
        return (
            pct(params, "arm_thickness"),
            pct(params, "arm_length"),
            side * (params["arm_spread"] * 0.58 + shoulder_spread + torso_side_push),
            params["arm_y"] + torso_top_delta * 0.64,
        )
    if name in {"left_hand", "right_hand"}:
        side = -1.0 if name == "left_hand" else 1.0
        hand_scale = pct(params, "hand_size")
        return (
            hand_scale,
            hand_scale,
            side * (params["arm_spread"] * 0.58 + shoulder_spread + torso_side_push),
            params["hand_y"] + params["arm_y"] + torso_top_delta * 0.64 + (params["arm_length"] - 100.0) * 3.0,
        )
    if name in {"left_leg", "right_leg"}:
        side = -1.0 if name == "left_leg" else 1.0
        leg_sx = pct(params, "leg_thickness") * 0.72 + pct(params, "foot_width") * 0.28
        leg_sy = pct(params, "leg_length") * 0.88 + pct(params, "foot_height") * 0.12
        hip_push = (params["torso_width"] - 100.0) * 0.34
        return leg_sx, leg_sy, side * (params["leg_spread"] * 0.30 + hip_push), params["leg_y"] + torso_bottom_delta * 0.58
    return 1.0, 1.0, 0.0, 0.0


def apply_global(img: Image.Image, params: dict[str, float]) -> Image.Image:
    scale = pct(params, "global_scale")
    if abs(scale - 1.0) < 0.001 and not params["global_x"] and not params["global_y"]:
        return img
    scaled = img.resize((max(2, round(CANVAS[0] * scale)), max(2, round(CANVAS[1] * scale))), Image.Resampling.LANCZOS)
    out = Image.new("RGBA", CANVAS, (0, 0, 0, 0))
    out.alpha_composite(
        scaled,
        (
            round((CANVAS[0] - scaled.width) / 2 + params["global_x"]),
            round((CANVAS[1] - scaled.height) / 2 + params["global_y"]),
        ),
    )
    return out


def soft_ellipse(
    overlay: Image.Image,
    box: tuple[float, float, float, float],
    color: tuple[int, int, int],
    alpha: int,
    blur: float,
) -> None:
    mask = Image.new("L", CANVAS, 0)
    ImageDraw.Draw(mask).ellipse(tuple(round(v) for v in box), fill=max(0, min(255, alpha)))
    if blur:
        mask = mask.filter(ImageFilter.GaussianBlur(blur))
    fill = Image.new("RGBA", CANVAS, (*color, 255))
    fill.putalpha(mask)
    overlay.alpha_composite(fill)


def soft_line(
    overlay: Image.Image,
    points: list[tuple[float, float]],
    color: tuple[int, int, int],
    alpha: int,
    width: int,
    blur: float,
) -> None:
    mask = Image.new("L", CANVAS, 0)
    ImageDraw.Draw(mask).line([(round(x), round(y)) for x, y in points], fill=max(0, min(255, alpha)), width=width, joint="curve")
    if blur:
        mask = mask.filter(ImageFilter.GaussianBlur(blur))
    fill = Image.new("RGBA", CANVAS, (*color, 255))
    fill.putalpha(mask)
    overlay.alpha_composite(fill)


def soft_polygon(
    overlay: Image.Image,
    points: list[tuple[float, float]],
    color: tuple[int, int, int],
    alpha: int,
    blur: float,
) -> None:
    mask = Image.new("L", CANVAS, 0)
    ImageDraw.Draw(mask).polygon([(round(x), round(y)) for x, y in points], fill=max(0, min(255, alpha)))
    if blur:
        mask = mask.filter(ImageFilter.GaussianBlur(blur))
    fill = Image.new("RGBA", CANVAS, (*color, 255))
    fill.putalpha(mask)
    overlay.alpha_composite(fill)


def qcurve(p0: tuple[float, float], p1: tuple[float, float], p2: tuple[float, float], steps: int = 24) -> list[tuple[float, float]]:
    points: list[tuple[float, float]] = []
    for i in range(steps + 1):
        t = i / steps
        x = (1 - t) ** 2 * p0[0] + 2 * (1 - t) * t * p1[0] + t**2 * p2[0]
        y = (1 - t) ** 2 * p0[1] + 2 * (1 - t) * t * p1[1] + t**2 * p2[1]
        points.append((x, y))
    return points


def map_part_point(name: str, x: float, y: float, params: dict[str, float]) -> tuple[float, float]:
    bbox_lookup = {
        "head": (280, 92, 743, 591),
        "left_ear": (280, 337, 313, 424),
        "right_ear": (712, 338, 743, 424),
        "neck": (412, 470, 612, 620),
        "torso": (307, 518, 716, 984),
        "left_arm": (265, 585, 399, 1012),
        "right_arm": (626, 585, 758, 1012),
        "left_hand": (265, 932, 337, 1012),
        "right_hand": (686, 932, 758, 1012),
        "left_leg": (332, 848, 543, 1472),
        "right_leg": (482, 848, 692, 1472),
    }
    sx, sy, dx, dy = part_transform(name, params)
    anchor = bbox_center(bbox_lookup[name])
    return anchor[0] + dx + (x - anchor[0]) * sx, anchor[1] + dy + (y - anchor[1]) * sy


def map_head_point(x: float, y: float, params: dict[str, float]) -> tuple[float, float]:
    head_bbox = (280, 92, 743, 591)
    cx, cy = bbox_center(head_bbox)
    sx = pct(params, "head_size") * pct(params, "head_width")
    sy = pct(params, "head_size") * pct(params, "head_height")
    return cx + (x - cx) * sx + params["head_x"], cy + (y - cy) * sy + params["head_y"]


def draw_face_features(params: dict[str, float]) -> Image.Image:
    overlay = Image.new("RGBA", CANVAS, (0, 0, 0, 0))
    head_sx = pct(params, "head_size") * pct(params, "head_width")
    head_sy = pct(params, "head_size") * pct(params, "head_height")
    eye_depth = pct(params, "eye_depth")
    center_x = 512 + params["eye_x"]
    eye_y = 365 + params["eye_y"]
    eye_w = 64 * pct(params, "eye_width") * head_sx
    eye_h = 58 * pct(params, "eye_height") * head_sy
    for side in (-1, 1):
        ex, ey = map_head_point(center_x + side * params["eye_spacing"] / 2, eye_y, params)
        soft_ellipse(overlay, (ex - eye_w * 0.62, ey - eye_h * 0.62, ex + eye_w * 0.62, ey + eye_h * 0.62), (112, 110, 101), round(72 * eye_depth), 6)
        soft_ellipse(overlay, (ex - eye_w * 0.47, ey - eye_h * 0.42, ex + eye_w * 0.47, ey + eye_h * 0.45), (255, 255, 250), round(84 * eye_depth), 5)
        soft_ellipse(overlay, (ex - eye_w * 0.64, ey - eye_h * 0.68, ex + eye_w * 0.58, ey - eye_h * 0.12), (84, 82, 76), round(28 * eye_depth), 4)

    nose_depth = pct(params, "nose_depth")
    nx, ny = map_head_point(512 + params["nose_x"], 430 + params["nose_y"], params)
    nose = 1.0 * pct(params, "nose_size")
    soft_ellipse(overlay, (nx - 19 * nose * head_sx, ny - 24 * nose * head_sy, nx + 13 * nose * head_sx, ny + 24 * nose * head_sy), (116, 113, 104), round(38 * nose_depth), 8)
    soft_ellipse(overlay, (nx - 8 * nose * head_sx, ny - 30 * nose * head_sy, nx + 18 * nose * head_sx, ny + 8 * nose * head_sy), (255, 255, 250), round(58 * nose_depth), 7)

    mouth_depth = pct(params, "mouth_depth")
    mx, my = map_head_point(512 + params["mouth_x"], 492 + params["mouth_y"], params)
    mouth_w = 66 * pct(params, "mouth_width") * head_sx
    curve = 20 * params["mouth_curve"] / 100.0 * head_sy
    points = qcurve((mx - mouth_w / 2, my), (mx, my + curve), (mx + mouth_w / 2, my))
    soft_line(overlay, points, (95, 92, 84), round(64 * mouth_depth), 3, 1.2)
    soft_line(overlay, [(x, y + 2.5 * head_sy) for x, y in points], (255, 255, 250), round(38 * mouth_depth), 2, 1.6)
    return overlay


def draw_joint_fill(params: dict[str, float]) -> Image.Image:
    overlay = Image.new("RGBA", CANVAS, (0, 0, 0, 0))
    head_y = params["head_y"]
    torso_y = params["torso_y"]
    leg_y = params["leg_y"]

    neck_top_l = map_part_point("neck", 432, 488, params)
    neck_top_r = map_part_point("neck", 592, 488, params)
    neck_bottom_l = map_part_point("neck", 408, 610, params)
    neck_bottom_r = map_part_point("neck", 616, 610, params)
    chin_l = map_part_point("head", 424, 526, params)
    chin_r = map_part_point("head", 600, 526, params)
    soft_polygon(
        overlay,
        [chin_l, chin_r, neck_top_r, neck_bottom_r, neck_bottom_l, neck_top_l],
        SKIN_BASE,
        178,
        10,
    )
    soft_line(overlay, [map_part_point("head", 512, 518, params), map_part_point("neck", 512, 610, params)], SKIN_LIGHT, 42, 68, 18)

    for side_name, side in (("left", -1.0), ("right", 1.0)):
        ear = "left_ear" if side < 0 else "right_ear"
        head_x = 352 if side < 0 else 672
        ear_x = 306 if side < 0 else 718
        bridge = [
            map_part_point("head", head_x, 358, params),
            map_part_point(ear, ear_x, 360, params),
            map_part_point(ear, ear_x, 410, params),
            map_part_point("head", head_x, 420, params),
        ]
        soft_polygon(overlay, bridge, SKIN_BASE, 132, 8)
        soft_line(
            overlay,
            [map_part_point("head", head_x, 388, params), map_part_point(ear, ear_x, 388, params)],
            SKIN_LIGHT,
            34,
            34,
            9,
        )

    shoulder_w = pct(params, "shoulder_width")
    shoulder_half = 178 * shoulder_w
    shoulder_y = 610 + torso_y * 0.35
    shoulder_mask = Image.new("L", CANVAS, 0)
    ImageDraw.Draw(shoulder_mask).polygon(
        [
            (512 - shoulder_half, shoulder_y),
            (512 + shoulder_half, shoulder_y),
            (612, shoulder_y + 86),
            (412, shoulder_y + 86),
        ],
        fill=124,
    )
    shoulder_mask = shoulder_mask.filter(ImageFilter.GaussianBlur(14))
    shoulder_fill = Image.new("RGBA", CANVAS, (*SKIN_BASE, 255))
    shoulder_fill.putalpha(shoulder_mask)
    overlay.alpha_composite(shoulder_fill)

    for side_name, side in (("left", -1.0), ("right", 1.0)):
        arm = "left_arm" if side < 0 else "right_arm"
        hand = "left_hand" if side < 0 else "right_hand"
        torso_x = 340 if side < 0 else 684
        arm_x = 376 if side < 0 else 648
        shoulder_bridge = [
            map_part_point("torso", 326 if side < 0 else 698, 600, params),
            map_part_point(arm, 386 if side < 0 else 638, 600, params),
            map_part_point(arm, 398 if side < 0 else 626, 782, params),
            map_part_point("torso", 386 if side < 0 else 638, 792, params),
        ]
        soft_polygon(overlay, shoulder_bridge, SKIN_BASE, 154, 13)
        soft_line(
            overlay,
            [
                map_part_point("torso", 352 if side < 0 else 672, 635, params),
                map_part_point(arm, 392 if side < 0 else 632, 635, params),
            ],
            SKIN_LIGHT,
            34,
            58,
            13,
        )
        soft_line(
            overlay,
            [
                map_part_point("torso", torso_x, 628, params),
                map_part_point(arm, arm_x, 628, params),
                map_part_point(arm, arm_x, 760, params),
            ],
            SKIN_BASE,
            120,
            58,
            15,
        )
        soft_line(
            overlay,
            [map_part_point(arm, arm_x, 940, params), map_part_point(hand, arm_x, 964, params)],
            SKIN_BASE,
            112,
            34,
            10,
        )

    hip_y = 890 + torso_y * 0.2 + leg_y * 0.3
    soft_ellipse(overlay, (356, hip_y - 58, 668, hip_y + 92), SKIN_BASE, 132, 16)
    soft_ellipse(overlay, (438, hip_y + 5, 586, hip_y + 118), SKIN_SHADOW, 30, 13)
    crotch_top = map_part_point("torso", 512, 858, params)
    soft_ellipse(
        overlay,
        (crotch_top[0] - 108, crotch_top[1] - 30, crotch_top[0] + 108, crotch_top[1] + 94),
        SKIN_BASE,
        108,
        17,
    )
    for leg, x in (("left_leg", 460), ("right_leg", 564)):
        soft_line(
            overlay,
            [map_part_point("torso", x, 900, params), map_part_point(leg, x, 880, params)],
            SKIN_BASE,
            88,
            64,
            16,
        )

    soft_ellipse(
        overlay,
        (392, 486 + head_y * 0.35, 632, 640 + torso_y * 0.25),
        SKIN_BASE,
        138,
        13,
    )
    return overlay


def seam_closure_mask(params: dict[str, float]) -> Image.Image:
    mask = Image.new("L", CANVAS, 0)
    draw = ImageDraw.Draw(mask)

    for ear in ("left_ear", "right_ear"):
        ex, ey = map_part_point(ear, 512, 382, params)
        draw.ellipse((ex - 82, ey - 92, ex + 82, ey + 92), fill=210)

    nx, ny = map_part_point("neck", 512, 548, params)
    draw.ellipse((nx - 210, ny - 155, nx + 210, ny + 175), fill=235)

    shoulder_points = [
        map_part_point("torso", 320, 560, params),
        map_part_point("torso", 704, 560, params),
        map_part_point("right_arm", 666, 690, params),
        map_part_point("torso", 612, 790, params),
        map_part_point("torso", 412, 790, params),
        map_part_point("left_arm", 358, 690, params),
    ]
    draw.polygon([(round(x), round(y)) for x, y in shoulder_points], fill=225)

    for arm, hand in (("left_arm", "left_hand"), ("right_arm", "right_hand")):
        ax, ay = map_part_point(arm, 512, 952, params)
        hx, hy = map_part_point(hand, 512, 966, params)
        cx = (ax + hx) / 2
        cy = (ay + hy) / 2
        draw.ellipse((cx - 78, cy - 76, cx + 78, cy + 76), fill=190)

    return mask.filter(ImageFilter.GaussianBlur(14))


def close_alpha_gaps(img: Image.Image, params: dict[str, float], radius: int = 13) -> Image.Image:
    alpha = img.getchannel("A")
    size = radius * 2 + 1
    closed = alpha.filter(ImageFilter.MaxFilter(size)).filter(ImageFilter.MinFilter(size))
    gap = ImageChops.subtract(closed, alpha)
    gap = gap.point(lambda v: 0 if v < 8 else min(210, int(v * 1.45))).filter(ImageFilter.GaussianBlur(2.0))
    gap = ImageChops.multiply(gap, seam_closure_mask(params))
    fill = Image.new("RGBA", CANVAS, (*SKIN_BASE, 255))
    fill.putalpha(gap)
    out = img.copy()
    out.alpha_composite(fill)
    return out


def compose(params: dict[str, float], *, close_gaps: bool = True) -> tuple[Image.Image, Image.Image]:
    layers = load_layers()
    composed = Image.new("RGBA", CANVAS, (0, 0, 0, 0))
    for layer_name in LAYER_ORDER:
        layer = layers[layer_name]
        if layer_name == "head":
            layer = neutralize_head(layer)
        elif layer_name == "torso":
            layer = soften_torso_bottom(layer, params)
        sx, sy, dx, dy = part_transform(layer_name, params)
        paste_scaled(composed, layer, sx, sy, dx, dy)
    composed.alpha_composite(draw_joint_fill(params))
    if close_gaps:
        composed = close_alpha_gaps(composed, params)
    features = draw_face_features(params)
    composed.alpha_composite(features)
    transparent = apply_global(composed, params)
    return transparent, features


def render_preview_image(
    params: dict[str, float],
    size: tuple[int, int] | None = None,
    *,
    close_gaps: bool = False,
) -> Image.Image:
    transparent, _features = compose(params, close_gaps=close_gaps)
    preview = Image.new("RGBA", CANVAS, (218, 221, 222, 255))
    preview.alpha_composite(transparent)
    if size:
        preview = preview.resize(size, Image.Resampling.LANCZOS)
    return preview.convert("RGB")


def render(params: dict[str, float], out_dir: Path, name: str) -> dict[str, str]:
    out_dir.mkdir(parents=True, exist_ok=True)
    transparent, features = compose(params, close_gaps=True)
    preview = Image.new("RGBA", CANVAS, (218, 221, 222, 255))
    preview.alpha_composite(transparent)
    transparent_path = out_dir / f"{name}_transparent.png"
    preview_path = out_dir / f"{name}_preview.png"
    params_path = out_dir / f"{name}_params.json"
    features.save(out_dir / f"{name}_face_features.png")
    transparent.save(transparent_path)
    preview.convert("RGB").save(preview_path)
    params_path.write_text(json.dumps({"params": params}, ensure_ascii=False, indent=2), encoding="utf-8")
    return {
        "transparent": str(transparent_path),
        "preview": str(preview_path),
        "params": str(params_path),
        "face_features": str(out_dir / f"{name}_face_features.png"),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Render an adjustable Live2D front white-base mannequin.")
    parser.add_argument("--preset", default="default", help="preset key from parameter_presets.json")
    parser.add_argument("--params", type=Path, default=None, help="optional JSON file with parameter overrides")
    parser.add_argument("--out-dir", type=Path, default=OUT_DIR)
    parser.add_argument("--name", default="")
    args = parser.parse_args()
    name = args.name or args.preset
    params = build_params(args.preset, args.params)
    result = render(params, args.out_dir, name)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
