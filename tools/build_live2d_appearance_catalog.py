from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from models.live2d_appearance import (  # noqa: E402
    AppearanceCatalogBuilder,
    DEFAULT_SAMPLES_PER_CATEGORY,
    category_counts,
    default_catalog_dir,
    resolve_default_lineart_zip,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build the Live2D appearance catalog from a line-art zip archive.",
    )
    parser.add_argument(
        "--zip",
        dest="zip_path",
        default="",
        help="Path to the line-art zip. If omitted, the tool searches OneDrive and LIVE2D_LINEART_ZIP.",
    )
    parser.add_argument(
        "--output",
        default=str(default_catalog_dir(ROOT)),
        help="Output directory for catalog.json and thumbnails.",
    )
    parser.add_argument(
        "--count",
        type=int,
        default=DEFAULT_SAMPLES_PER_CATEGORY,
        help="Samples to generate per appearance category.",
    )
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--thumbnail-size", type=int, default=224)
    parser.add_argument(
        "--no-thumbnails",
        action="store_true",
        help="Only write catalog metadata; skip thumbnail extraction.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    zip_path = Path(args.zip_path) if args.zip_path else resolve_default_lineart_zip()
    if zip_path is None or not zip_path.is_file():
        print(
            "No source zip found. Set LIVE2D_LINEART_ZIP or pass --zip.",
            file=sys.stderr,
        )
        return 2

    builder = AppearanceCatalogBuilder(
        zip_path,
        args.output,
        samples_per_category=args.count,
        seed=args.seed,
        thumbnail_size=args.thumbnail_size,
        build_thumbnails=not args.no_thumbnails,
    )
    catalog = builder.build()
    print(f"source: {zip_path}")
    print(f"catalog: {Path(args.output) / 'catalog.json'}")
    print(f"total_images: {catalog['source_summary']['total_images']}")
    for category_id, count in category_counts(catalog).items():
        print(f"{category_id}: {count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
