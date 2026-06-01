from __future__ import annotations

import argparse
import json
import math
import random
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageOps


CANVAS = (1024, 1536)
LOSS_SIZE = (256, 384)
ROOT = Path("assets/live2d_modeling/base_front_template")
LAYER_DIR = ROOT / "layers"
OUT_DIR = ROOT / "fit_to_reference"


DEFAULT_TARGET = ROOT / "ai_high_fidelity_front_reference.png"
LAYER_ORDER = [
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


BOUNDS: dict[str, tuple[float, float]] = {
    "global_sx": (0.46, 1.22),
    "global_sy": (0.58, 1.22),
    "global_y": (-260.0, 260.0),
    "head_sx": (0.56, 1.18),
    "head_sy": (0.62, 1.18),
    "head_y": (-120.0, 120.0),
    "body_sx": (0.78, 1.22),
    "body_sy": (0.82, 1.26),
    "body_y": (-130.0, 130.0),
    "arm_sx": (0.70, 1.24),
    "arm_sy": (0.72, 1.28),
    "arm_spread": (-110.0, 110.0),
    "arm_y": (-120.0, 120.0),
    "leg_sx": (0.70, 1.24),
    "leg_sy": (0.72, 1.32),
    "leg_spread": (-95.0, 95.0),
    "leg_y": (-130.0, 130.0),
}


DEFAULT_PARAMS: dict[str, float] = {
    "global_sx": 1.0,
    "global_sy": 1.0,
    "global_y": 0.0,
    "head_sx": 1.0,
    "head_sy": 1.0,
    "head_y": 0.0,
    "body_sx": 1.0,
    "body_sy": 1.0,
    "body_y": 0.0,
    "arm_sx": 1.0,
    "arm_sy": 1.0,
    "arm_spread": 0.0,
    "arm_y": 0.0,
    "leg_sx": 1.0,
    "leg_sy": 1.0,
    "leg_spread": 0.0,
    "leg_y": 0.0,
}


LayerInfo = dict[str, Any]


def fit_image_to_canvas(img: Image.Image, size: tuple[int, int] = CANVAS) -> Image.Image:
    img = img.convert("RGB")
    canvas = Image.new("RGB", size, tuple(np.median(np.asarray(img.resize((16, 16))), axis=(0, 1)).astype(int)))
    source = img.copy()
    source.thumbnail(size, Image.Resampling.LANCZOS)
    x = (size[0] - source.width) // 2
    y = (size[1] - source.height) // 2
    canvas.paste(source, (x, y))
    return canvas


def estimate_target_mask(img: Image.Image) -> Image.Image:
    arr = np.asarray(img.convert("RGB")).astype(np.float32)
    border = np.concatenate(
        [
            arr[:32, :, :].reshape(-1, 3),
            arr[-32:, :, :].reshape(-1, 3),
            arr[:, :32, :].reshape(-1, 3),
            arr[:, -32:, :].reshape(-1, 3),
        ],
        axis=0,
    )
    bg = np.median(border, axis=0)
    diff = np.mean(np.abs(arr - bg), axis=2)
    mask = diff > max(5.5, float(np.percentile(diff, 70)) * 0.34)
    mask_img = Image.fromarray((mask.astype(np.uint8) * 255), "L")
    mask_img = mask_img.filter(ImageFilter.GaussianBlur(1.2))
    mask_img = mask_img.point(lambda p: 255 if p > 18 else 0)
    bbox = mask_img.getbbox()
    if bbox:
        clean = Image.new("L", CANVAS, 0)
        crop = mask_img.crop(bbox).filter(ImageFilter.MaxFilter(9)).filter(ImageFilter.GaussianBlur(1.2))
        clean.paste(crop, bbox)
        mask_img = clean.point(lambda p: 255 if p > 16 else 0)
    return mask_img


def load_layers() -> dict[str, LayerInfo]:
    layers: dict[str, LayerInfo] = {}
    for name in LAYER_ORDER:
        img = Image.open(LAYER_DIR / f"{name}.png").convert("RGBA")
        bbox = img.getbbox()
        if bbox is None:
            raise ValueError(f"empty layer: {name}")
        crop = img.crop(bbox)
        layers[name] = {
            "image": crop,
            "bbox": bbox,
            "center": ((bbox[0] + bbox[2]) / 2, (bbox[1] + bbox[3]) / 2),
        }
    return layers


def clamp_params(params: dict[str, float]) -> dict[str, float]:
    out: dict[str, float] = {}
    for key, value in params.items():
        lo, hi = BOUNDS[key]
        out[key] = max(lo, min(hi, float(value)))
    return out


def layer_transform(name: str, params: dict[str, float]) -> tuple[float, float, float, float]:
    if name in {"head", "left_ear", "right_ear", "face_relief"}:
        return params["head_sx"], params["head_sy"], 0.0, params["head_y"]
    if name in {"torso", "neck"}:
        return params["body_sx"], params["body_sy"], 0.0, params["body_y"]
    if name in {"left_arm", "right_arm"}:
        side = -1.0 if name == "left_arm" else 1.0
        return params["arm_sx"], params["arm_sy"], side * params["arm_spread"], params["arm_y"] + params["body_y"] * 0.25
    if name in {"left_leg", "right_leg"}:
        side = -1.0 if name == "left_leg" else 1.0
        return params["leg_sx"], params["leg_sy"], side * params["leg_spread"], params["leg_y"] + params["body_y"] * 0.35
    return 1.0, 1.0, 0.0, 0.0


def paste_scaled(base: Image.Image, info: LayerInfo, sx: float, sy: float, dx: float, dy: float) -> None:
    crop: Image.Image = info["image"]
    bbox = info["bbox"]
    center_x, center_y = info["center"]
    new_w = max(2, round(crop.width * sx))
    new_h = max(2, round(crop.height * sy))
    scaled = crop.resize((new_w, new_h), Image.Resampling.LANCZOS)
    old_anchor_x = center_x - bbox[0]
    old_anchor_y = center_y - bbox[1]
    paste_x = round(center_x + dx - old_anchor_x * sx)
    paste_y = round(center_y + dy - old_anchor_y * sy)
    base.alpha_composite(scaled, (paste_x, paste_y))


def apply_global(img: Image.Image, params: dict[str, float]) -> Image.Image:
    sx = params["global_sx"]
    sy = params["global_sy"]
    scaled = img.resize((max(2, round(CANVAS[0] * sx)), max(2, round(CANVAS[1] * sy))), Image.Resampling.LANCZOS)
    out = Image.new("RGBA", CANVAS, (0, 0, 0, 0))
    out.alpha_composite(scaled, ((CANVAS[0] - scaled.width) // 2, round((CANVAS[1] - scaled.height) // 2 + params["global_y"])))
    return out


def render_candidate(layers: dict[str, LayerInfo], params: dict[str, float]) -> Image.Image:
    img = Image.new("RGBA", CANVAS, (0, 0, 0, 0))
    for name in LAYER_ORDER:
        sx, sy, dx, dy = layer_transform(name, params)
        paste_scaled(img, layers[name], sx, sy, dx, dy)
    return apply_global(img, params)


def bbox_center(bbox: tuple[int, int, int, int]) -> tuple[float, float]:
    return (bbox[0] + bbox[2]) / 2, (bbox[1] + bbox[3]) / 2


def initial_params_from_target(layers: dict[str, LayerInfo], target_mask: Image.Image) -> dict[str, float]:
    params = dict(DEFAULT_PARAMS)
    candidate_bbox = render_candidate(layers, params).getbbox()
    target_bbox = target_mask.getbbox()
    if not candidate_bbox or not target_bbox:
        return clamp_params(params)

    cand_w = max(1, candidate_bbox[2] - candidate_bbox[0])
    cand_h = max(1, candidate_bbox[3] - candidate_bbox[1])
    target_w = max(1, target_bbox[2] - target_bbox[0])
    target_h = max(1, target_bbox[3] - target_bbox[1])
    params["global_sx"] = target_w / cand_w
    params["global_sy"] = target_h / cand_h

    canvas_cx, canvas_cy = CANVAS[0] / 2, CANVAS[1] / 2
    cand_cx, cand_cy = bbox_center(candidate_bbox)
    target_cx, target_cy = bbox_center(target_bbox)
    # apply_global scales around the canvas center, so infer the y offset after scaling.
    scaled_cy = canvas_cy + (cand_cy - canvas_cy) * params["global_sy"]
    params["global_y"] = target_cy - scaled_cy

    # The reference body has a smaller skull-to-body ratio than the editable chibi
    # base, so start the search with a slightly reduced head.
    params["head_sx"] = 0.84
    params["head_sy"] = 0.88
    params["head_y"] = 26.0
    return clamp_params(params)


def composite_on_gray(rgba: Image.Image) -> Image.Image:
    bg = Image.new("RGBA", CANVAS, (220, 222, 223, 255))
    bg.alpha_composite(rgba)
    return bg.convert("RGB")


def edge_map(gray: np.ndarray) -> np.ndarray:
    gx = np.abs(np.diff(gray, axis=1, prepend=gray[:, :1]))
    gy = np.abs(np.diff(gray, axis=0, prepend=gray[:1, :]))
    edge = gx + gy
    m = edge.max()
    return edge / m if m > 0 else edge


def prepare_loss_arrays(target: Image.Image, target_mask_img: Image.Image | None = None) -> dict[str, np.ndarray]:
    target_small = target.resize(LOSS_SIZE, Image.Resampling.LANCZOS)
    mask = (target_mask_img or estimate_target_mask(target)).resize(LOSS_SIZE, Image.Resampling.LANCZOS)
    target_gray = np.asarray(ImageOps.grayscale(target_small)).astype(np.float32) / 255.0
    target_mask = (np.asarray(mask).astype(np.float32) / 255.0) > 0.20
    return {
        "rgb": np.asarray(target_small).astype(np.float32) / 255.0,
        "gray": target_gray,
        "mask": target_mask,
        "edge": edge_map(target_gray),
    }


def loss_for(candidate: Image.Image, target_arrays: dict[str, np.ndarray]) -> float:
    rgba_small = candidate.resize(LOSS_SIZE, Image.Resampling.LANCZOS)
    cand_alpha = np.asarray(rgba_small.getchannel("A")).astype(np.float32) / 255.0
    cand_mask = cand_alpha > 0.18
    cand_rgb = np.asarray(composite_on_gray(candidate).resize(LOSS_SIZE, Image.Resampling.LANCZOS)).astype(np.float32) / 255.0
    cand_gray = np.asarray(ImageOps.grayscale(Image.fromarray((cand_rgb * 255).astype(np.uint8)))).astype(np.float32) / 255.0
    target_mask = target_arrays["mask"]
    union = np.logical_or(cand_mask, target_mask)
    inter = np.logical_and(cand_mask, target_mask)
    iou = inter.sum() / max(1, union.sum())
    mask_loss = 1.0 - iou
    gray_loss = float(np.mean((cand_gray[union] - target_arrays["gray"][union]) ** 2)) if union.any() else 1.0
    edge_loss = float(np.mean((edge_map(cand_gray) - target_arrays["edge"]) ** 2))
    return mask_loss * 1.25 + gray_loss * 0.55 + edge_loss * 0.30


def random_step(params: dict[str, float], scale: float) -> dict[str, float]:
    proposal = dict(params)
    keys = list(BOUNDS.keys())
    random.shuffle(keys)
    for key in keys[: random.randint(2, 5)]:
        lo, hi = BOUNDS[key]
        span = hi - lo
        proposal[key] += random.gauss(0.0, span * scale)
    return clamp_params(proposal)


def make_comparison(target: Image.Image, candidate: Image.Image, path: Path) -> None:
    target_rgb = target.convert("RGB")
    cand_rgb = composite_on_gray(candidate)
    diff = ImageChops.difference(target_rgb, cand_rgb).convert("L")
    diff_rgb = ImageOps.colorize(diff, black="#eef2f3", white="#e11d48")
    panel = Image.new("RGB", (CANVAS[0] * 3, CANVAS[1]), (238, 241, 242))
    panel.paste(target_rgb, (0, 0))
    panel.paste(cand_rgb, (CANVAS[0], 0))
    panel.paste(diff_rgb, (CANVAS[0] * 2, 0))
    draw = ImageDraw.Draw(panel)
    draw.rectangle((0, 0, CANVAS[0] * 3, 44), fill=(20, 24, 31))
    for i, label in enumerate(["target", "optimized candidate", "difference"]):
        draw.text((i * CANVAS[0] + 24, 14), label, fill=(255, 255, 255))
    panel.save(path)


def parse_crop(value: str | None) -> tuple[int, int, int, int] | None:
    if not value:
        return None
    parts = [int(float(part.strip())) for part in value.split(",")]
    if len(parts) != 4:
        raise ValueError("--crop must be x,y,w,h")
    x, y, w, h = parts
    if w <= 0 or h <= 0:
        raise ValueError("--crop width and height must be positive")
    return x, y, x + w, y + h


def optimize(
    target_path: Path,
    iterations: int,
    seed: int,
    crop: tuple[int, int, int, int] | None = None,
) -> dict[str, Any]:
    random.seed(seed)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    raw_target = Image.open(target_path)
    if crop is not None:
        raw_target = raw_target.crop(crop)
    target = fit_image_to_canvas(raw_target)
    target.save(OUT_DIR / "target_normalized.png")
    layers = load_layers()
    target_mask = estimate_target_mask(target)
    target_mask.save(OUT_DIR / "target_mask.png")
    arrays = prepare_loss_arrays(target, target_mask)
    current = initial_params_from_target(layers, target_mask)
    current_img = render_candidate(layers, current)
    current_loss = loss_for(current_img, arrays)
    best = dict(current)
    best_img = current_img
    best_loss = current_loss
    history: list[dict[str, float]] = [{"iteration": 0, "loss": best_loss}]
    temperature = 0.10
    for i in range(1, iterations + 1):
        scale = 0.115 * (1 - i / max(1, iterations)) + 0.012
        proposal = random_step(current, scale)
        prop_img = render_candidate(layers, proposal)
        prop_loss = loss_for(prop_img, arrays)
        accept = prop_loss < current_loss
        if not accept:
            # Small simulated-annealing chance helps escape bad layer-scale local minima.
            accept = math.exp((current_loss - prop_loss) / max(0.0001, temperature)) > random.random()
        temperature *= 0.985
        if accept:
            current, current_loss, current_img = proposal, prop_loss, prop_img
            if prop_loss < best_loss:
                best, best_loss, best_img = dict(proposal), prop_loss, prop_img
        if i % 10 == 0 or i == iterations:
            history.append({"iteration": i, "loss": best_loss})
    best_img.save(OUT_DIR / "optimized_candidate_transparent.png")
    composite_on_gray(best_img).save(OUT_DIR / "optimized_candidate_preview.png")
    make_comparison(target, best_img, OUT_DIR / "comparison.png")
    result = {
        "target": str(target_path),
        "crop": crop,
        "iterations": iterations,
        "seed": seed,
        "initial_loss": history[0]["loss"],
        "best_loss": best_loss,
        "improvement": history[0]["loss"] - best_loss,
        "params": best,
        "outputs": {
            "target_normalized": "target_normalized.png",
            "candidate_transparent": "optimized_candidate_transparent.png",
            "candidate_preview": "optimized_candidate_preview.png",
            "comparison": "comparison.png",
        },
        "history": history,
    }
    (OUT_DIR / "fit_report.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Fit the layered Live2D base template to a front-view 3D reference.")
    parser.add_argument("--target", type=Path, default=DEFAULT_TARGET)
    parser.add_argument("--crop", type=str, default="", help="optional x,y,w,h crop before fitting")
    parser.add_argument("--iterations", type=int, default=160)
    parser.add_argument("--seed", type=int, default=7)
    args = parser.parse_args()
    result = optimize(args.target, args.iterations, args.seed, parse_crop(args.crop))
    print(json.dumps({k: result[k] for k in ("initial_loss", "best_loss", "improvement")}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
