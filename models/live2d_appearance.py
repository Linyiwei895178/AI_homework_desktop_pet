from __future__ import annotations

import datetime as _dt
import hashlib
import json
import os
import random
import re
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from PIL import Image, ImageFile, ImageOps


ImageFile.LOAD_TRUNCATED_IMAGES = True

CATALOG_FORMAT = "pet_buddy_live2d_appearance_catalog_v1"
SELECTION_FORMAT = "pet_buddy_live2d_appearance_selection_v1"
DEFAULT_SAMPLES_PER_CATEGORY = 50
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".pjpeg", ".webp", ".octet-stream"}


CATEGORY_DEFS: list[dict[str, str]] = [
    {
        "id": "face_features",
        "label": "五官表情",
        "description": "眼型、眉形、鼻口和表情气质的组合参考。",
    },
    {
        "id": "face_shape",
        "label": "脸型轮廓",
        "description": "头脸比例、下颌、脸颊和轮廓线风格参考。",
    },
    {
        "id": "hair",
        "label": "头发",
        "description": "长度、刘海、发束、体积和动态线条参考。",
    },
    {
        "id": "clothing",
        "label": "衣着",
        "description": "上装、下装、外套、层次和角色定位参考。",
    },
    {
        "id": "accessories",
        "label": "配饰道具",
        "description": "头饰、眼镜、首饰、手持物和装饰性道具参考。",
    },
    {
        "id": "scene",
        "label": "场景",
        "description": "建筑、自然、室内外空间和插画背景参考。",
    },
]


FACE_EYES = ["杏眼", "圆眼", "上挑眼", "下垂眼", "细长眼", "大眼", "半眯眼", "猫眼", "凤眼", "无辜眼"]
FACE_BROWS = ["柔和弯眉", "短平眉", "浓眉", "细眉", "剑眉", "困惑眉", "挑眉", "下压眉", "淡眉", "断眉"]
FACE_MOUTHS = ["小口微笑", "平静小口", "张口笑", "嘟嘴", "冷淡薄唇", "猫嘴", "惊讶口", "抿嘴", "害羞笑", "锐利笑"]
FACE_NOSES = ["极简鼻线", "小鼻尖", "短鼻梁", "立体鼻梁", "柔和鼻影", "点状鼻", "侧光鼻线", "清秀鼻", "高鼻梁", "圆润鼻头"]
FACE_MOODS = ["清冷", "元气", "温柔", "倔强", "神秘", "乖巧", "成熟", "少年感", "傲娇", "沉静"]

FACE_SHAPES = ["圆脸", "鹅蛋脸", "瓜子脸", "短下巴脸", "尖下巴脸", "方圆脸", "长脸", "娃娃脸", "窄脸", "宽颧脸"]
FACE_CHEEKS = ["饱满脸颊", "轻薄脸颊", "柔软面颊", "利落颧骨", "微鼓脸颊", "内收脸颊", "平滑侧脸", "清瘦脸颊"]
FACE_CHINS = ["圆下巴", "尖下巴", "短下巴", "小巧下巴", "平下巴", "柔和下颌", "利落下颌", "微翘下巴"]
FACE_LINES = ["轻线稿", "清晰结构线", "柔线条", "硬朗线条", "高留白", "密集排线", "漫画轮廓", "素描轮廓"]

HAIR_LENGTHS = ["超短发", "短发", "齐耳短发", "波波头", "中长发", "及肩发", "长发", "超长发", "双马尾", "单马尾", "盘发", "侧扎发"]
HAIR_BANGS = ["无刘海", "齐刘海", "斜刘海", "空气刘海", "碎刘海", "中分", "偏分", "遮眼刘海", "挑染前发", "龙须刘海"]
HAIR_TEXTURES = ["直发", "微卷", "大卷", "蓬松", "凌乱发束", "湿发线条", "厚重发片", "轻盈发丝", "尖刺发束", "柔顺发流"]
HAIR_DETAILS = ["发尾外翘", "发尾内扣", "高光发片", "层次剪裁", "侧边碎发", "后脑蓬度", "发旋明显", "飘动发束"]

CLOTHING_BASES = ["校服", "卫衣", "衬衫", "西装", "连衣裙", "夹克", "斗篷", "针织衫", "运动装", "战斗服", "礼服", "和风服"]
CLOTHING_LAYERS = ["单层简洁", "内外叠穿", "高领层次", "短外套", "长外套", "披肩", "腰封", "围裙", "半透明罩衫", "装甲局部"]
CLOTHING_BOTTOMS = ["短裙", "长裙", "短裤", "直筒裤", "阔腿裤", "束脚裤", "不对称裙摆", "高腰下装", "靴裤", "连体剪裁"]
CLOTHING_VIBES = ["日常", "学院", "奇幻", "赛博", "复古", "街头", "优雅", "侦探", "冒险", "舞台"]

ACCESSORY_TYPES = ["发卡", "蝴蝶结", "帽子", "眼镜", "耳饰", "项链", "领结", "围巾", "手套", "腰包", "翅膀饰", "面具"]
ACCESSORY_PLACEMENTS = ["头顶", "侧发", "耳侧", "脸部", "颈部", "胸前", "腰间", "手部", "背部", "肩部"]
ACCESSORY_MATERIALS = ["金属", "丝带", "皮革", "玻璃", "宝石", "布料", "机械", "木质", "羽毛", "透明材质"]
ACCESSORY_PROPS = ["书本", "麦克风", "法杖", "长剑", "杯子", "相机", "耳机", "小包", "花束", "交通道具"]

SCENE_PLACES = ["卧室", "街角", "校园", "神社", "城堡", "现代建筑", "车站", "森林", "海边", "山谷", "工作室", "舞台"]
SCENE_COMPOSITIONS = ["正面背景", "俯视空间", "仰视建筑", "宽景构图", "近景物件", "门窗框景", "走廊透视", "自然剪影"]
SCENE_MOODS = ["清晨", "午后", "黄昏", "雨天", "夜景", "安静", "热闹", "废墟感", "梦幻", "写实素描"]
SCENE_ELEMENTS = ["树木", "云层", "招牌", "家具", "桥梁", "车辆", "岩石", "水面", "塔楼", "室内陈设"]


@dataclass(frozen=True)
class ZipEntryInfo:
    name: str
    archive_name: str
    size: int
    extension: str
    content_type: str
    source_group: str


def default_catalog_dir(project_root: str | Path) -> Path:
    return Path(project_root) / "assets" / "live2d_modeling" / "appearance_catalog"


def default_catalog_path(project_root: str | Path) -> Path:
    return default_catalog_dir(project_root) / "catalog.json"


def load_appearance_catalog(project_root: str | Path) -> dict[str, Any] | None:
    path = default_catalog_path(project_root)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if data.get("format") != CATALOG_FORMAT:
        return None
    return limit_appearance_catalog(data)


def limit_appearance_catalog(
    catalog: dict[str, Any],
    sample_limit: int = DEFAULT_SAMPLES_PER_CATEGORY,
) -> dict[str, Any]:
    limit = max(1, int(sample_limit))
    limited = dict(catalog)
    categories: list[Any] = []
    for category in catalog.get("categories", []):
        if not isinstance(category, dict):
            categories.append(category)
            continue
        samples = category.get("samples", [])
        if isinstance(samples, list) and len(samples) > limit:
            category = dict(category)
            category["samples"] = samples[:limit]
            category["count"] = len(category["samples"])
        categories.append(category)
    limited["categories"] = categories
    return limited


def resolve_default_lineart_zip() -> Path | None:
    env_path = os.environ.get("LIVE2D_LINEART_ZIP", "").strip()
    if env_path:
        path = Path(env_path)
        if path.is_file():
            return path

    roots = [Path("C:/Users"), Path.home().parent if Path.home().parent.exists() else None]
    seen: set[Path] = set()
    for root in roots:
        if root is None or not root.exists():
            continue
        for user_dir in root.glob("*"):
            onedrive = user_dir / "OneDrive"
            if not onedrive.exists():
                continue
            patterns = [
                "*/线稿合集*.zip",
                "*/*线稿*.zip",
                "*/*4.8G*.zip",
            ]
            for pattern in patterns:
                for candidate in onedrive.glob(pattern):
                    if candidate in seen:
                        continue
                    seen.add(candidate)
                    name = candidate.name
                    if candidate.is_file() and ("线稿" in name or "4.8G" in name):
                        return candidate
    return None


def export_appearance_selection(
    project_root: str | Path,
    selections: dict[str, dict[str, Any]],
    *,
    filename: str = "selected_appearance.json",
) -> Path:
    out_dir = default_catalog_dir(project_root)
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "format": SELECTION_FORMAT,
        "created_at": _dt.datetime.now().isoformat(timespec="seconds"),
        "catalog": "catalog.json",
        "selections": {
            category_id: {
                "id": sample.get("id"),
                "title": sample.get("title"),
                "category": category_id,
                "tags": sample.get("tags", []),
                "prompt_fragment": sample.get("prompt_fragment", ""),
                "thumbnail": sample.get("thumbnail", ""),
                "source": sample.get("source", {}),
            }
            for category_id, sample in selections.items()
        },
    }
    path = out_dir / filename
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


class AppearanceCatalogBuilder:
    def __init__(
        self,
        zip_path: str | Path,
        output_dir: str | Path,
        *,
        samples_per_category: int = DEFAULT_SAMPLES_PER_CATEGORY,
        seed: int = 42,
        thumbnail_size: int = 224,
        build_thumbnails: bool = True,
    ) -> None:
        self.zip_path = Path(zip_path)
        self.output_dir = Path(output_dir)
        self.samples_per_category = max(1, int(samples_per_category))
        self.seed = int(seed)
        self.thumbnail_size = max(96, int(thumbnail_size))
        self.build_thumbnails = build_thumbnails

    def build(self) -> dict[str, Any]:
        entries = self._read_entries()
        if not entries:
            raise ValueError(f"no supported image entries found in {self.zip_path}")

        categories: list[dict[str, Any]] = []
        self.output_dir.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(self.zip_path) as archive:
            for category_def in CATEGORY_DEFS:
                category_id = category_def["id"]
                pool = self._pool_for_category(entries, category_id)
                selected = self._select_entries(pool, self.samples_per_category, category_id)
                samples: list[dict[str, Any]] = []
                for index, entry in enumerate(selected):
                    sample_id = f"{category_id}_{index + 1:03d}"
                    style = self._style_for_category(category_id, index)
                    rel_thumb = ""
                    image_stats: dict[str, Any] = {}
                    if self.build_thumbnails:
                        rel_thumb, image_stats = self._write_thumbnail(archive, entry, category_id, sample_id)
                    samples.append(
                        {
                            "id": sample_id,
                            "category": category_id,
                            "title": style["title"],
                            "tags": style["tags"],
                            "prompt_fragment": style["prompt_fragment"],
                            "thumbnail": rel_thumb,
                            "image_stats": image_stats,
                            "source": {
                                "zip_path": entry.name,
                                "content_type": entry.content_type,
                                "source_group": entry.source_group,
                                "size": entry.size,
                            },
                        }
                    )
                categories.append({**category_def, "count": len(samples), "samples": samples})

        catalog = {
            "format": CATALOG_FORMAT,
            "generated_at": _dt.datetime.now().isoformat(timespec="seconds"),
            "source_zip": str(self.zip_path),
            "source_summary": self._source_summary(entries),
            "notes": [
                "Samples are style references distilled from the supplied line-art archive.",
                "Character categories prefer 人物、生物 entries; scene categories prefer 场景 entries; accessory samples may include object-only sources.",
                "The catalog avoids copying full source art into prompts and stores only local thumbnails plus source paths.",
            ],
            "categories": categories,
        }
        (self.output_dir / "catalog.json").write_text(
            json.dumps(catalog, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return catalog

    def _read_entries(self) -> list[ZipEntryInfo]:
        entries: list[ZipEntryInfo] = []
        with zipfile.ZipFile(self.zip_path) as archive:
            for info in archive.infolist():
                if info.is_dir() or info.file_size <= 0:
                    continue
                display_name = decode_zip_filename(info.filename)
                ext = Path(display_name).suffix.lower()
                if ext not in IMAGE_EXTENSIONS:
                    continue
                content_type, source_group = classify_zip_path(display_name)
                entries.append(
                    ZipEntryInfo(
                        name=display_name,
                        archive_name=info.filename,
                        size=int(info.file_size),
                        extension=ext,
                        content_type=content_type,
                        source_group=source_group,
                    )
                )
        return entries

    def _pool_for_category(self, entries: list[ZipEntryInfo], category_id: str) -> list[ZipEntryInfo]:
        character = [e for e in entries if e.content_type.startswith("character")]
        scene = [
            e
            for e in entries
            if e.content_type.startswith("scene") or e.content_type.startswith("object")
        ]
        object_like = [
            e
            for e in entries
            if e.content_type.startswith("object") or e.content_type in {"scene_architecture", "scene_object"}
        ]
        if category_id in {"face_features", "face_shape", "hair", "clothing"}:
            return character or entries
        if category_id == "accessories":
            return (object_like + character) or entries
        if category_id == "scene":
            return scene or entries
        return entries

    def _select_entries(
        self,
        pool: list[ZipEntryInfo],
        count: int,
        category_id: str,
    ) -> list[ZipEntryInfo]:
        if not pool:
            return []
        ordered = sorted(pool, key=lambda item: item.name)
        rng = random.Random(self.seed + _stable_int(category_id))
        rng.shuffle(ordered)
        if len(ordered) >= count:
            return ordered[:count]
        result: list[ZipEntryInfo] = []
        while len(result) < count:
            result.extend(ordered)
        return result[:count]

    def _write_thumbnail(
        self,
        archive: zipfile.ZipFile,
        entry: ZipEntryInfo,
        category_id: str,
        sample_id: str,
    ) -> tuple[str, dict[str, Any]]:
        rel_path = Path("thumbnails") / category_id / f"{sample_id}.jpg"
        out_path = self.output_dir / rel_path
        out_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with archive.open(entry.archive_name) as stream:
                image = Image.open(stream)
                image = ImageOps.exif_transpose(image)
                if getattr(image, "is_animated", False):
                    image.seek(0)
                image = image.convert("RGBA")
                stats = _image_stats(image)
                thumb = _fit_on_white(image, self.thumbnail_size)
                thumb.save(out_path, format="JPEG", quality=86, optimize=True)
            return rel_path.as_posix(), stats
        except Exception as exc:  # keep catalog generation robust over imperfect scrape archives
            return "", {"error": str(exc)}

    def _source_summary(self, entries: list[ZipEntryInfo]) -> dict[str, Any]:
        by_type: dict[str, int] = {}
        by_group: dict[str, int] = {}
        for entry in entries:
            by_type[entry.content_type] = by_type.get(entry.content_type, 0) + 1
            by_group[entry.source_group] = by_group.get(entry.source_group, 0) + 1
        return {
            "total_images": len(entries),
            "by_content_type": dict(sorted(by_type.items(), key=lambda item: item[0])),
            "top_source_groups": dict(
                sorted(by_group.items(), key=lambda item: item[1], reverse=True)[:20]
            ),
        }

    def _style_for_category(self, category_id: str, index: int) -> dict[str, Any]:
        if category_id == "face_features":
            return _compose(
                index,
                [FACE_EYES, FACE_BROWS, FACE_NOSES, FACE_MOUTHS, FACE_MOODS],
                "{4}{0} + {1} + {2} + {3}",
                "五官参考：{4}气质，{0}，{1}，{2}，{3}。",
            )
        if category_id == "face_shape":
            return _compose(
                index,
                [FACE_SHAPES, FACE_CHEEKS, FACE_CHINS, FACE_LINES],
                "{0} / {1} / {2}",
                "脸型参考：{0}，{1}，{2}，轮廓采用{3}。",
            )
        if category_id == "hair":
            return _compose(
                index,
                [HAIR_LENGTHS, HAIR_BANGS, HAIR_TEXTURES, HAIR_DETAILS],
                "{0} + {1} + {2}",
                "发型参考：{0}，{1}，{2}，重点表现{3}。",
            )
        if category_id == "clothing":
            return _compose(
                index,
                [CLOTHING_VIBES, CLOTHING_BASES, CLOTHING_LAYERS, CLOTHING_BOTTOMS],
                "{0}{1} / {2}",
                "服装参考：{0}风格的{1}，{2}，下装或裙摆为{3}。",
            )
        if category_id == "accessories":
            return _compose(
                index,
                [ACCESSORY_TYPES, ACCESSORY_PLACEMENTS, ACCESSORY_MATERIALS, ACCESSORY_PROPS],
                "{1}{0} / {2}",
                "配饰参考：{1}位置的{0}，材质倾向{2}，可搭配{3}。",
            )
        if category_id == "scene":
            return _compose(
                index,
                [SCENE_PLACES, SCENE_COMPOSITIONS, SCENE_MOODS, SCENE_ELEMENTS],
                "{2}{0} / {1}",
                "场景参考：{2}氛围的{0}，{1}，包含{3}元素。",
            )
        return {"title": f"外观样例 {index + 1}", "tags": [], "prompt_fragment": ""}


def classify_zip_path(filename: str) -> tuple[str, str]:
    normalized = filename.replace("\\", "/")
    parts = [part for part in normalized.split("/") if part]
    source_group = "/".join(parts[:3]) if len(parts) >= 3 else "/".join(parts[:2])
    if "【场景】" in normalized:
        if "【自然】" in normalized:
            return "scene_nature", source_group
        if "现代交通" in normalized:
            return "object_vehicle", source_group
        if "建筑" in normalized:
            return "scene_architecture", source_group
        if "【建筑、物件】" in normalized:
            return "scene_object", source_group
        if "【插画】" in normalized:
            return "scene_illustration", source_group
        return "scene", source_group
    if "【人物、生物】" in normalized:
        if "【动漫】" in normalized:
            return "character_anime", source_group
        if "【日韩】" in normalized:
            return "character_east_asian", source_group
        if "【欧美】" in normalized:
            return "character_western", source_group
        return "character", source_group
    return "unknown", source_group


def decode_zip_filename(filename: str) -> str:
    """Repair common GBK-in-CP437 zip names produced by older Windows tools."""
    try:
        repaired = filename.encode("cp437").decode("gbk")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return filename
    if "线稿" in repaired or "【" in repaired:
        return repaired
    return filename


def category_counts(catalog: dict[str, Any]) -> dict[str, int]:
    return {
        str(category.get("id")): len(category.get("samples", []))
        for category in catalog.get("categories", [])
        if isinstance(category, dict)
    }


def flatten_samples(catalog: dict[str, Any]) -> Iterable[dict[str, Any]]:
    for category in catalog.get("categories", []):
        if not isinstance(category, dict):
            continue
        for sample in category.get("samples", []):
            if isinstance(sample, dict):
                yield sample


def _compose(
    index: int,
    vocab_groups: list[list[str]],
    title_template: str,
    prompt_template: str,
) -> dict[str, Any]:
    picks: list[str] = []
    stride = 1
    for group in vocab_groups:
        picks.append(group[(index // stride) % len(group)])
        stride *= max(1, len(group))
    title = title_template.format(*picks)
    prompt = prompt_template.format(*picks)
    return {"title": title, "tags": picks, "prompt_fragment": prompt}


def _fit_on_white(image: Image.Image, size: int) -> Image.Image:
    bg = Image.new("RGBA", image.size, (255, 255, 255, 255))
    bg.alpha_composite(image)
    rgb = bg.convert("RGB")
    rgb.thumbnail((size, size), Image.Resampling.LANCZOS)
    canvas = Image.new("RGB", (size, size), "white")
    x = (size - rgb.width) // 2
    y = (size - rgb.height) // 2
    canvas.paste(rgb, (x, y))
    return canvas


def _image_stats(image: Image.Image) -> dict[str, Any]:
    width, height = image.size
    bg = Image.new("RGBA", image.size, (255, 255, 255, 255))
    bg.alpha_composite(image)
    gray = ImageOps.grayscale(bg.convert("RGB")).resize((96, 96), Image.Resampling.BILINEAR)
    pixels = list(gray.getdata())
    ink = sum(1 for value in pixels if value < 242)
    dark = sum(1 for value in pixels if value < 96)
    return {
        "width": width,
        "height": height,
        "aspect_ratio": round(width / max(1, height), 3),
        "ink_density": round(ink / len(pixels), 4),
        "dark_density": round(dark / len(pixels), 4),
    }


def _stable_int(value: str) -> int:
    digest = hashlib.sha1(value.encode("utf-8")).hexdigest()
    return int(digest[:8], 16)


def safe_filename(value: str) -> str:
    value = re.sub(r"[\\/:*?\"<>|]+", "_", value.strip())
    value = re.sub(r"\s+", "_", value).strip("._")
    return value or "appearance"
