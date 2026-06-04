from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
from PIL import Image


def _bleed_transparent_rgb(image: Image.Image, passes: int = 12) -> Image.Image:
    arr = np.array(image.convert("RGBA"), copy=True)
    rgb = arr[:, :, :3]
    alpha = arr[:, :, 3]
    filled = alpha > 0

    for _ in range(max(0, passes)):
        empty = ~filled
        if not empty.any():
            break
        next_rgb = rgb.copy()
        next_filled = filled.copy()
        for dy, dx in ((-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (-1, 1), (1, -1), (1, 1)):
            src_y = slice(max(0, -dy), rgb.shape[0] - max(0, dy))
            dst_y = slice(max(0, dy), rgb.shape[0] - max(0, -dy))
            src_x = slice(max(0, -dx), rgb.shape[1] - max(0, dx))
            dst_x = slice(max(0, dx), rgb.shape[1] - max(0, -dx))
            candidates = filled[src_y, src_x] & empty[dst_y, dst_x]
            if candidates.any():
                dst = next_rgb[dst_y, dst_x]
                dst[candidates] = rgb[src_y, src_x][candidates]
                filled_dst = next_filled[dst_y, dst_x]
                filled_dst[candidates] = True
        rgb = next_rgb
        filled = next_filled

    arr[:, :, :3] = rgb
    return Image.fromarray(arr, "RGBA")


def downscale_texture(src: Path, dst: Path, size: int, bleed_passes: int) -> None:
    with Image.open(src) as raw:
        premultiplied = raw.convert("RGBa")
        resized = premultiplied.resize((size, size), Image.Resampling.LANCZOS).convert("RGBA")
    cleaned = _bleed_transparent_rgb(resized, passes=bleed_passes)
    dst.parent.mkdir(parents=True, exist_ok=True)
    cleaned.save(dst, optimize=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("source_dir", type=Path)
    parser.add_argument("dest_dir", type=Path)
    parser.add_argument("--size", type=int, default=4096)
    parser.add_argument("--bleed-passes", type=int, default=12)
    parser.add_argument("textures", nargs="+")
    args = parser.parse_args()

    for texture in args.textures:
        src = args.source_dir / texture
        dst = args.dest_dir / texture
        downscale_texture(src, dst, args.size, args.bleed_passes)
        print(f"{src} -> {dst}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
