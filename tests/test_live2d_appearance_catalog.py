from __future__ import annotations

import io
import zipfile
from pathlib import Path

from PIL import Image

from models.live2d_appearance import (
    AppearanceCatalogBuilder,
    CATALOG_FORMAT,
    DEFAULT_SAMPLES_PER_CATEGORY,
    category_counts,
    classify_zip_path,
    decode_zip_filename,
    load_appearance_catalog,
)


def _image_bytes(color: tuple[int, int, int]) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (96, 128), color).save(buffer, format="JPEG")
    return buffer.getvalue()


def _write_demo_zip(path: Path) -> None:
    image_specs = [
        ("线稿/【人物、生物】/【动漫】/char_001.jpg", (240, 240, 240)),
        ("线稿/【人物、生物】/【日韩】/char_002.jpg", (220, 220, 220)),
        ("线稿/【人物、生物】/【欧美】/char_003.jpg", (200, 200, 200)),
        ("线稿/【场景】/【建筑、物件】/建筑/scene_001.jpg", (180, 180, 180)),
        ("线稿/【场景】/【建筑、物件】/现代交通/object_001.jpg", (160, 160, 160)),
        ("线稿/【场景】/【自然】/nature_001.jpg", (140, 140, 140)),
    ]
    with zipfile.ZipFile(path, "w") as archive:
        for filename, color in image_specs:
            archive.writestr(filename, _image_bytes(color))


def test_classify_zip_path_uses_archive_categories():
    assert classify_zip_path("线稿/【人物、生物】/【动漫】/1.jpg")[0] == "character_anime"
    assert classify_zip_path("线稿/【场景】/【自然】/1.jpg")[0] == "scene_nature"
    assert classify_zip_path("线稿/【场景】/【建筑、物件】/现代交通/1.jpg")[0] == "object_vehicle"


def test_decode_zip_filename_repairs_gbk_cp437_names():
    raw = "线稿/【人物、生物】/【动漫】/1.jpg".encode("gbk").decode("cp437")

    assert decode_zip_filename(raw) == "线稿/【人物、生物】/【动漫】/1.jpg"


def test_builder_generates_requested_samples_per_category(tmp_path: Path):
    zip_path = tmp_path / "lineart.zip"
    _write_demo_zip(zip_path)
    out_dir = tmp_path / "catalog"

    catalog = AppearanceCatalogBuilder(
        zip_path,
        out_dir,
        samples_per_category=5,
        build_thumbnails=False,
    ).build()

    assert catalog["format"] == CATALOG_FORMAT
    assert (out_dir / "catalog.json").is_file()
    assert set(category_counts(catalog).values()) == {5}
    assert catalog["source_summary"]["total_images"] == 6

    scene_category = next(c for c in catalog["categories"] if c["id"] == "scene")
    assert all(
        sample["source"]["content_type"].startswith(("scene", "object"))
        for sample in scene_category["samples"]
    )

    hair_category = next(c for c in catalog["categories"] if c["id"] == "hair")
    assert all(
        sample["source"]["content_type"].startswith("character")
        for sample in hair_category["samples"]
    )


def test_loaded_catalog_caps_default_samples_per_category(tmp_path: Path):
    zip_path = tmp_path / "lineart.zip"
    _write_demo_zip(zip_path)
    out_dir = tmp_path / "assets" / "live2d_modeling" / "appearance_catalog"

    AppearanceCatalogBuilder(
        zip_path,
        out_dir,
        samples_per_category=DEFAULT_SAMPLES_PER_CATEGORY + 2,
        build_thumbnails=False,
    ).build()

    catalog = load_appearance_catalog(tmp_path)

    assert catalog is not None
    assert set(category_counts(catalog).values()) == {DEFAULT_SAMPLES_PER_CATEGORY}
