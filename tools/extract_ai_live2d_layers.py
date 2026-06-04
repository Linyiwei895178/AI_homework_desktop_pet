from __future__ import annotations

import json
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter


CANVAS = (1024, 1536)
ROOT = Path("assets/live2d_modeling/base_front_template")
SOURCE = ROOT / "ai_chroma_front_reference_transparent.png"
OUT = ROOT / "ai_cut_layers"


def paste_fitted_subject(src: Image.Image) -> Image.Image:
    src = src.convert("RGBA")
    bbox = src.getbbox()
    if bbox is None:
        raise ValueError("source image has no opaque pixels")
    subject = src.crop(bbox)
    target_h = 1380
    scale = target_h / subject.height
    subject = subject.resize((round(subject.width * scale), target_h), Image.Resampling.LANCZOS)
    canvas = Image.new("RGBA", CANVAS, (0, 0, 0, 0))
    x = (CANVAS[0] - subject.width) // 2
    y = 92
    canvas.alpha_composite(subject, (x, y))
    return canvas


def aa_polygon(points: list[tuple[float, float]], blur: float = 0.8) -> Image.Image:
    scale = 4
    mask = Image.new("L", (CANVAS[0] * scale, CANVAS[1] * scale), 0)
    pts = [(round(x * scale), round(y * scale)) for x, y in points]
    ImageDraw.Draw(mask).polygon(pts, fill=255)
    if blur:
        mask = mask.filter(ImageFilter.GaussianBlur(blur * scale))
    return mask.resize(CANVAS, Image.Resampling.LANCZOS)


def aa_ellipse(box: tuple[float, float, float, float], blur: float = 0.8) -> Image.Image:
    scale = 4
    mask = Image.new("L", (CANVAS[0] * scale, CANVAS[1] * scale), 0)
    x0, y0, x1, y1 = box
    ImageDraw.Draw(mask).ellipse(
        (round(x0 * scale), round(y0 * scale), round(x1 * scale), round(y1 * scale)),
        fill=255,
    )
    if blur:
        mask = mask.filter(ImageFilter.GaussianBlur(blur * scale))
    return mask.resize(CANVAS, Image.Resampling.LANCZOS)


def layer_from_mask(full: Image.Image, mask: Image.Image) -> Image.Image:
    layer = full.copy()
    alpha = Image.composite(full.getchannel("A"), Image.new("L", CANVAS, 0), mask)
    layer.putalpha(alpha)
    return layer


def union_mask(*masks: Image.Image) -> Image.Image:
    if not masks:
        return Image.new("L", CANVAS, 0)
    out = masks[0]
    for mask in masks[1:]:
        out = ImageChops.lighter(out, mask)
    return out


def save_layer(full: Image.Image, name: str, mask: Image.Image) -> dict[str, object]:
    layer = layer_from_mask(full, mask)
    path = OUT / f"{name}.png"
    layer.save(path)
    return {"name": name, "file": path.name, "bbox": layer.getbbox()}


def build_masks() -> dict[str, Image.Image]:
    masks: dict[str, Image.Image] = {}
    masks["left_leg"] = union_mask(
        aa_polygon([(370, 850), (526, 850), (526, 1492), (358, 1492), (334, 980)]),
        aa_ellipse((348, 1390, 540, 1524), blur=1.0),
    )
    masks["right_leg"] = union_mask(
        aa_polygon([(498, 850), (654, 850), (690, 980), (666, 1492), (498, 1492)]),
        aa_ellipse((484, 1390, 676, 1524), blur=1.0),
    )
    masks["torso"] = aa_polygon(
        [(330, 520), (694, 520), (744, 746), (672, 982), (352, 982), (280, 746)]
    )
    masks["neck"] = aa_polygon([(424, 472), (600, 472), (610, 618), (414, 618)])
    masks["left_arm"] = aa_polygon([(314, 530), (400, 552), (348, 1065), (255, 1065), (238, 930)])
    masks["right_arm"] = aa_polygon([(624, 552), (710, 530), (786, 930), (769, 1065), (676, 1065)])
    masks["left_hand"] = aa_ellipse((222, 934, 348, 1084))
    masks["right_hand"] = aa_ellipse((676, 934, 802, 1084))
    masks["head"] = aa_polygon(
        [
            (262, 86),
            (762, 86),
            (820, 292),
            (742, 504),
            (604, 588),
            (420, 588),
            (282, 504),
            (204, 292),
        ],
        blur=1.2,
    )
    masks["left_ear"] = aa_ellipse((184, 306, 310, 460), blur=1.0)
    masks["right_ear"] = aa_ellipse((714, 306, 840, 460), blur=1.0)
    masks["face_relief"] = aa_polygon(
        [(360, 290), (664, 290), (680, 494), (512, 554), (344, 494)],
        blur=2.2,
    )
    return masks


def make_preview(layers: list[dict[str, object]]) -> Image.Image:
    bg = Image.new("RGBA", CANVAS, (218, 221, 222, 255))
    for layer in layers:
        img = Image.open(OUT / str(layer["file"])).convert("RGBA")
        bg.alpha_composite(img)
    return bg.convert("RGB")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    full = paste_fitted_subject(Image.open(SOURCE))
    full.save(OUT / "full_base.png")
    masks = build_masks()
    layer_order = [
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
        "face_relief",
    ]
    layers = [save_layer(full, name, masks[name]) for name in layer_order]
    preview = make_preview(layers)
    preview.save(OUT / "layered_preview.png")
    manifest = {
        "canvas": CANVAS,
        "source": str(SOURCE),
        "full_base": "full_base.png",
        "layered_preview": "layered_preview.png",
        "layer_order": layer_order,
        "layers": layers,
        "notes": [
            "High-fidelity raster base generated with an image model, then chroma-keyed and cut into Live2D-friendly front-view layers.",
            "The layer cuts are a rigging base, not a finished Cubism .moc3 model.",
        ],
    }
    (OUT / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"out": str(OUT), "layers": len(layers)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
