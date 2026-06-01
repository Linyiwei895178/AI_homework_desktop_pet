from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

from PIL import Image, ImageDraw, ImageFilter


CANVAS = (1024, 1536)
SS = 4
HCANVAS = (CANVAS[0] * SS, CANVAS[1] * SS)
CX = 512
OUT_DIR = Path("assets/live2d_modeling/base_front_template")
LAYER_DIR = OUT_DIR / "layers"


RGBA = tuple[int, int, int, int]
Point = tuple[float, float]


def sp(point: Point) -> tuple[int, int]:
    return round(point[0] * SS), round(point[1] * SS)


def sb(box: tuple[float, float, float, float]) -> tuple[int, int, int, int]:
    x0, y0, x1, y1 = box
    return (
        round(min(x0, x1) * SS),
        round(min(y0, y1) * SS),
        round(max(x0, x1) * SS),
        round(max(y0, y1) * SS),
    )


def cubic(p0: Point, p1: Point, p2: Point, p3: Point, steps: int = 32) -> list[Point]:
    points: list[Point] = []
    for i in range(steps + 1):
        t = i / steps
        x = (
            (1 - t) ** 3 * p0[0]
            + 3 * (1 - t) ** 2 * t * p1[0]
            + 3 * (1 - t) * t * t * p2[0]
            + t**3 * p3[0]
        )
        y = (
            (1 - t) ** 3 * p0[1]
            + 3 * (1 - t) ** 2 * t * p1[1]
            + 3 * (1 - t) * t * t * p2[1]
            + t**3 * p3[1]
        )
        points.append((x, y))
    return points


def qcurve(p0: Point, p1: Point, p2: Point, steps: int = 24) -> list[Point]:
    points: list[Point] = []
    for i in range(steps + 1):
        t = i / steps
        x = (1 - t) * (1 - t) * p0[0] + 2 * (1 - t) * t * p1[0] + t * t * p2[0]
        y = (1 - t) * (1 - t) * p0[1] + 2 * (1 - t) * t * p1[1] + t * t * p2[1]
        points.append((x, y))
    return points


def joined(segments: Iterable[list[Point]]) -> list[Point]:
    out: list[Point] = []
    for segment in segments:
        for point in segment:
            if not out or out[-1] != point:
                out.append(point)
    return out


def high_layer() -> Image.Image:
    return Image.new("RGBA", HCANVAS, (0, 0, 0, 0))


def low(img: Image.Image) -> Image.Image:
    return img.resize(CANVAS, Image.Resampling.LANCZOS)


def polygon_mask(points: list[Point]) -> Image.Image:
    mask = Image.new("L", HCANVAS, 0)
    ImageDraw.Draw(mask).polygon([sp(point) for point in points], fill=255)
    return mask.filter(ImageFilter.GaussianBlur(0.35 * SS))


def mask_from_ellipse(box: tuple[float, float, float, float], blur: float = 0) -> Image.Image:
    mask = Image.new("L", HCANVAS, 0)
    ImageDraw.Draw(mask).ellipse(sb(box), fill=255)
    if blur:
        mask = mask.filter(ImageFilter.GaussianBlur(blur * SS))
    return mask


def add_solid(img: Image.Image, mask: Image.Image, color: RGBA) -> None:
    fill = Image.new("RGBA", HCANVAS, color)
    fill.putalpha(mask)
    img.alpha_composite(fill)


def add_blur_ellipse(
    img: Image.Image,
    clip_mask: Image.Image,
    box: tuple[float, float, float, float],
    color: RGBA,
    blur: float = 28,
) -> None:
    overlay = high_layer()
    od = ImageDraw.Draw(overlay, "RGBA")
    od.ellipse(sb(box), fill=color)
    overlay = overlay.filter(ImageFilter.GaussianBlur(blur * SS))
    alpha = Image.composite(overlay.getchannel("A"), Image.new("L", HCANVAS, 0), clip_mask)
    overlay.putalpha(alpha)
    img.alpha_composite(overlay)


def add_blur_polygon(
    img: Image.Image,
    clip_mask: Image.Image,
    points: list[Point],
    color: RGBA,
    blur: float = 18,
) -> None:
    overlay = high_layer()
    ImageDraw.Draw(overlay, "RGBA").polygon([sp(point) for point in points], fill=color)
    overlay = overlay.filter(ImageFilter.GaussianBlur(blur * SS))
    alpha = Image.composite(overlay.getchannel("A"), Image.new("L", HCANVAS, 0), clip_mask)
    overlay.putalpha(alpha)
    img.alpha_composite(overlay)


def stroke_points(
    img: Image.Image,
    points: list[Point],
    color: RGBA = (174, 176, 171, 70),
    width: float = 2.2,
    closed: bool = False,
) -> None:
    draw = ImageDraw.Draw(img, "RGBA")
    scaled = [sp(point) for point in points]
    if closed and scaled:
        scaled.append(scaled[0])
    draw.line(scaled, fill=color, width=max(1, round(width * SS)), joint="curve")


def shape_layer(
    points: list[Point],
    base: RGBA = (244, 244, 238, 255),
    outline: RGBA = (193, 196, 190, 78),
    outline_width: float = 2.4,
) -> tuple[Image.Image, Image.Image]:
    img = high_layer()
    mask = polygon_mask(points)
    add_solid(img, mask, base)
    stroke_points(img, points, outline, outline_width, closed=True)
    return img, mask


def draw_head() -> Image.Image:
    points = joined(
        [
            cubic((512, 78), (390, 80), (292, 164), (286, 315), 34),
            cubic((286, 315), (276, 445), (365, 558), (512, 586), 34),
            cubic((512, 586), (659, 558), (748, 445), (738, 315), 34),
            cubic((738, 315), (732, 164), (634, 80), (512, 78), 34),
        ]
    )
    img, mask = shape_layer(points, base=(245, 245, 239, 255), outline=(187, 190, 184, 70), outline_width=2.8)
    add_blur_ellipse(img, mask, (322, 72, 704, 332), (255, 255, 255, 105), blur=32)
    add_blur_ellipse(img, mask, (210, 218, 492, 622), (168, 168, 160, 42), blur=36)
    add_blur_ellipse(img, mask, (518, 184, 820, 598), (255, 255, 255, 74), blur=36)
    add_blur_ellipse(img, mask, (344, 420, 680, 650), (190, 190, 182, 26), blur=34)
    add_blur_ellipse(img, mask, (354, 210, 670, 512), (212, 212, 205, 26), blur=52)
    return low(img)


def draw_ear(side: int) -> Image.Image:
    img = high_layer()
    cx = CX + side * 235
    outer = mask_from_ellipse((cx - 43, 314, cx + 43, 440), blur=0.25)
    add_solid(img, outer, (242, 242, 236, 255))
    add_blur_ellipse(img, outer, (cx - 36, 332, cx + 24, 430), (170, 170, 164, 34), blur=12)
    add_blur_ellipse(img, outer, (cx - 18, 306, cx + 42, 390), (255, 255, 255, 66), blur=14)
    d = ImageDraw.Draw(img, "RGBA")
    d.ellipse(sb((cx - 43, 314, cx + 43, 440)), outline=(190, 193, 186, 74), width=round(2.2 * SS))
    d.arc(sb((cx - 27, 343, cx + 26, 420)), 94 if side < 0 else 266, 284 if side < 0 else 76, fill=(179, 181, 174, 92), width=round(3.0 * SS))
    d.arc(sb((cx - 10, 363, cx + 21, 404)), 110 if side < 0 else 250, 278 if side < 0 else 70, fill=(206, 207, 200, 88), width=round(2.4 * SS))
    return low(img)


def draw_neck() -> Image.Image:
    points = joined(
        [
            cubic((456, 536), (472, 562), (552, 562), (568, 536), 12),
            cubic((568, 536), (568, 588), (566, 643), (553, 680), 14),
            cubic((553, 680), (536, 704), (488, 704), (471, 680), 12),
            cubic((471, 680), (458, 643), (456, 588), (456, 536), 14),
        ]
    )
    img, mask = shape_layer(points, base=(241, 241, 235, 255), outline=(188, 191, 184, 55), outline_width=2.0)
    add_blur_ellipse(img, mask, (416, 534, 506, 714), (160, 160, 154, 44), blur=24)
    add_blur_ellipse(img, mask, (514, 518, 606, 696), (255, 255, 255, 60), blur=22)
    return low(img)


def draw_torso() -> Image.Image:
    points = joined(
        [
            cubic((350, 642), (405, 595), (476, 610), (512, 668), 18),
            cubic((512, 668), (548, 610), (619, 595), (674, 642), 18),
            cubic((674, 642), (664, 774), (644, 936), (612, 1050), 24),
            cubic((612, 1050), (576, 1090), (448, 1090), (412, 1050), 18),
            cubic((412, 1050), (380, 936), (360, 774), (350, 642), 24),
        ]
    )
    img, mask = shape_layer(points, base=(244, 244, 238, 255), outline=(187, 190, 184, 66), outline_width=2.4)
    add_blur_ellipse(img, mask, (334, 608, 502, 1108), (170, 170, 164, 34), blur=32)
    add_blur_ellipse(img, mask, (496, 596, 702, 1038), (255, 255, 255, 76), blur=42)
    add_blur_ellipse(img, mask, (426, 896, 604, 1104), (178, 178, 170, 33), blur=38)
    add_blur_polygon(img, mask, [(406, 710), (472, 656), (512, 680), (552, 656), (618, 710), (612, 744), (512, 706), (412, 744)], (232, 232, 225, 35), blur=18)
    return low(img)


def draw_arm(side: int) -> Image.Image:
    sx = CX + side * 176
    points = joined(
        [
            cubic((sx - side * 24, 654), (sx + side * 30, 654), (sx + side * 70, 760), (sx + side * 83, 884), 24),
            cubic((sx + side * 83, 884), (sx + side * 93, 988), (sx + side * 78, 1066), (sx + side * 48, 1100), 20),
            cubic((sx + side * 48, 1100), (sx + side * 18, 1122), (sx - side * 22, 1097), (sx - side * 12, 1034), 18),
            cubic((sx - side * 12, 1034), (sx + side * 10, 904), (sx + side * 14, 730), (sx - side * 24, 654), 26),
        ]
    )
    img, mask = shape_layer(points, base=(241, 241, 235, 255), outline=(187, 190, 184, 62), outline_width=2.2)
    add_blur_ellipse(img, mask, (min(sx - 24, sx + side * 112), 646, max(sx - 24, sx + side * 112), 1110), (168, 168, 160, 30), blur=30)
    add_blur_ellipse(img, mask, (min(sx - side * 26, sx + side * 70), 628, max(sx - side * 26, sx + side * 70), 928), (255, 255, 255, 54), blur=28)
    d = ImageDraw.Draw(img, "RGBA")
    hx = sx + side * 48
    palm = mask_from_ellipse((hx - 40, 1040, hx + 40, 1134), blur=0.25)
    add_solid(img, palm, (241, 241, 235, 255))
    d.ellipse(sb((hx - 40, 1040, hx + 40, 1134)), outline=(187, 190, 184, 62), width=round(2.0 * SS))
    finger_base = 1100
    for n, length in enumerate((48, 58, 62, 54)):
        fx = hx + side * (-24 + n * 13)
        d.rounded_rectangle(
            sb((fx - 7, finger_base, fx + 8, finger_base + length)),
            radius=round(7 * SS),
            fill=(241, 241, 235, 255),
            outline=(190, 192, 186, 58),
            width=round(1.8 * SS),
        )
    return low(img)


def draw_leg(side: int) -> Image.Image:
    inner_x = CX + side * 34
    outer_x = CX + side * 122
    left = min(inner_x, outer_x)
    right = max(inner_x, outer_x)
    points = joined(
        [
            cubic((left + 8, 1010), (left - 4, 1134), (left + 2, 1276), (left + 10, 1388), 24),
            cubic((left + 10, 1388), (left + 30, 1420), (right - 10, 1420), (right + 8, 1388), 16),
            cubic((right + 8, 1388), (right + 20, 1276), (right + 10, 1134), (right, 1010), 24),
            cubic((right, 1010), (right - 26, 988), (left + 34, 988), (left + 8, 1010), 16),
        ]
    )
    img, mask = shape_layer(points, base=(243, 243, 237, 255), outline=(187, 190, 184, 62), outline_width=2.2)
    add_blur_ellipse(img, mask, (left - 24, 1020, left + 78, 1425), (168, 168, 160, 28), blur=30)
    add_blur_ellipse(img, mask, (right - 70, 1018, right + 55, 1376), (255, 255, 255, 52), blur=28)
    d = ImageDraw.Draw(img, "RGBA")
    foot = (left - 28, 1372, right + 8, 1440) if side < 0 else (left - 8, 1372, right + 28, 1440)
    d.rounded_rectangle(sb(foot), radius=round(22 * SS), fill=(242, 242, 236, 255), outline=(187, 190, 184, 64), width=round(2.0 * SS))
    return low(img)


def draw_face_relief() -> Image.Image:
    img = high_layer()
    d = ImageDraw.Draw(img, "RGBA")
    for ex in (430, 594):
        add_blur_ellipse(img, Image.new("L", HCANVAS, 255), (ex - 54, 336, ex + 54, 414), (170, 170, 164, 32), blur=8)
        add_blur_ellipse(img, Image.new("L", HCANVAS, 255), (ex - 36, 346, ex + 36, 402), (255, 255, 255, 82), blur=8)
        d.arc(sb((ex - 54, 328, ex + 54, 408)), 195, 345, fill=(172, 178, 176, 64), width=round(2.6 * SS))
    d.line([sp((512, 404)), sp((498, 450)), sp((526, 450))], fill=(198, 198, 190, 54), width=round(3.2 * SS), joint="curve")
    d.arc(sb((462, 456, 562, 520)), 24, 156, fill=(188, 188, 180, 48), width=round(2.6 * SS))
    return low(img.filter(ImageFilter.GaussianBlur(0.25 * SS)))


def draw_face_guides() -> Image.Image:
    img = high_layer()
    d = ImageDraw.Draw(img, "RGBA")
    guide = (42, 130, 188, 118)
    strong = (30, 112, 176, 178)
    d.line((CX * SS, 70 * SS, CX * SS, 630 * SS), fill=strong, width=round(2.2 * SS))
    d.line(sb((318, 374, 706, 374)), fill=guide, width=round(2.0 * SS))
    d.line(sb((350, 482, 674, 482)), fill=(42, 130, 188, 78), width=round(1.5 * SS))
    d.ellipse(sb((292, 78, 732, 586)), outline=(30, 112, 176, 122), width=round(2.2 * SS))
    d.arc(sb((350, 320, 466, 426)), 196, 344, fill=strong, width=round(2.6 * SS))
    d.arc(sb((558, 320, 674, 426)), 196, 344, fill=strong, width=round(2.6 * SS))
    d.line(sb((386, 382, 376, 554)), fill=(42, 130, 188, 76), width=round(1.4 * SS))
    d.line(sb((638, 382, 648, 554)), fill=(42, 130, 188, 76), width=round(1.4 * SS))
    d.line(sb((352, 614, 672, 614)), fill=(42, 130, 188, 72), width=round(1.4 * SS))
    for x, y in [(512, 70), (318, 374), (512, 482), (512, 614)]:
        d.ellipse(sb((x - 5, y - 5, x + 5, y + 5)), fill=strong)
    return low(img)


def save_layer(img: Image.Image, name: str) -> str:
    path = LAYER_DIR / name
    img.save(path)
    return str(path.relative_to(OUT_DIR)).replace("\\", "/")


def compose(layers: dict[str, Image.Image], guides: bool = False) -> Image.Image:
    base = Image.new("RGBA", CANVAS, (220, 222, 223, 255))
    shadow = high_layer()
    sd = ImageDraw.Draw(shadow, "RGBA")
    sd.ellipse(sb((220, 1378, 804, 1460)), fill=(0, 0, 0, 36))
    base.alpha_composite(low(shadow.filter(ImageFilter.GaussianBlur(9 * SS))))
    order = [
        "left_leg",
        "right_leg",
        "neck",
        "left_arm",
        "right_arm",
        "torso",
        "left_ear",
        "right_ear",
        "head",
        "face_relief",
    ]
    for key in order:
        base.alpha_composite(layers[key])
    if guides:
        base.alpha_composite(layers["face_guides"])
    return base.convert("RGB")


def compose_face(layers: dict[str, Image.Image]) -> Image.Image:
    face = Image.new("RGBA", (840, 840), (246, 248, 247, 255))
    offset = (-92, -12)
    for key in ["left_ear", "right_ear", "head", "face_relief", "face_guides"]:
        face.alpha_composite(layers[key], offset)
    return face.convert("RGB")


def manifest(layer_paths: dict[str, str]) -> dict:
    return {
        "format": "pet_buddy_live2d_base_template_v2",
        "name": "smooth_front_view_white_mannequin_base",
        "canvas": {"width": CANVAS[0], "height": CANVAS[1]},
        "view": "front/main",
        "purpose": "high-resolution smooth white mannequin base for Live2D-style rigging and later face/hair/outfit drawing",
        "preview": "base_front_preview.png",
        "face_construction_preview": "face_front_construction.png",
        "draw_order": [
            "left_leg",
            "right_leg",
            "neck",
            "left_arm",
            "right_arm",
            "torso",
            "left_ear",
            "right_ear",
            "head",
            "face_relief",
            "face_guides",
        ],
        "layers": layer_paths,
        "anchors": {
            "head": {
                "top": [512, 78],
                "center": [512, 334],
                "chin": [512, 586],
                "left_eye_socket": [430, 376],
                "right_eye_socket": [594, 376],
                "mouth": [512, 488],
            },
            "body": {
                "neck": [512, 612],
                "shoulders": [[350, 642], [674, 642]],
                "waist": [[412, 1050], [612, 1050]],
                "hands": [[288, 1092], [736, 1092]],
                "feet": [[392, 1410], [632, 1410]],
            },
        },
        "recommended_live2d_params": {
            "ParamAngleX": {"range": [-10, 10], "layers": ["head", "left_ear", "right_ear", "face_relief"]},
            "ParamAngleY": {"range": [-8, 8], "layers": ["head", "face_relief", "neck"]},
            "ParamBodyAngleX": {"range": [-6, 6], "layers": ["torso", "left_arm", "right_arm"]},
            "ParamBreath": {"range": [0, 1], "layers": ["torso", "neck"]},
            "ParamEyeLOpen": {"range": [0, 1], "source": "replace left socket with final eye layers"},
            "ParamEyeROpen": {"range": [0, 1], "source": "replace right socket with final eye layers"},
        },
    }


def main() -> None:
    LAYER_DIR.mkdir(parents=True, exist_ok=True)
    layers = {
        "left_leg": draw_leg(-1),
        "right_leg": draw_leg(1),
        "neck": draw_neck(),
        "left_arm": draw_arm(-1),
        "right_arm": draw_arm(1),
        "torso": draw_torso(),
        "left_ear": draw_ear(-1),
        "right_ear": draw_ear(1),
        "head": draw_head(),
        "face_relief": draw_face_relief(),
        "face_guides": draw_face_guides(),
    }
    layer_paths = {name: save_layer(img, f"{name}.png") for name, img in layers.items()}
    compose(layers, guides=False).save(OUT_DIR / "base_front_preview.png")
    compose(layers, guides=True).save(OUT_DIR / "base_front_with_guides.png")
    compose_face(layers).save(OUT_DIR / "face_front_construction.png")
    (OUT_DIR / "base_front_manifest.json").write_text(
        json.dumps(manifest(layer_paths), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
