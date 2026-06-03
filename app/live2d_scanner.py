"""
Live2D model scanner - scans assets/models/ for .model3.json files
"""

import json
import os
from typing import Any

IGNORE_IDS = {"mao"}  # IDs to exclude from results

# Display name overrides for specific IDs
DISPLAY_NAMES = {
    "doro": "Doro",
    "elf_count": "精灵伯爵",
    "monkey": "吗喽",
}


def resolve_live2d_thumb(model_path: str) -> str:
    """Resolve thumbnail PNG from model directory."""
    if not model_path or not os.path.isfile(model_path):
        return ""
    runtime = os.path.dirname(os.path.abspath(model_path))
    avatar = os.path.join(runtime, "avatar.png")
    if os.path.isfile(avatar):
        return avatar
    preview = os.path.join(runtime, "_preview_first_motion.png")
    if os.path.isfile(preview):
        return preview
    for tex_dir_name in ("mao_pro.4096", "textures", "texture"):
        tex_dir = os.path.join(runtime, tex_dir_name)
        if os.path.isdir(tex_dir):
            for fname in sorted(os.listdir(tex_dir)):
                if fname.lower().endswith(".png"):
                    return os.path.join(tex_dir, fname)
    for dirpath, _dn, files in os.walk(runtime):
        for fname in sorted(files):
            if fname.lower().endswith(".png"):
                return os.path.join(dirpath, fname)
    return ""


def list_live2d_motion_stems(model_path: str) -> list[str]:
    if not model_path or not os.path.isfile(model_path):
        return []
    runtime = os.path.dirname(os.path.abspath(model_path))
    stems: list[str] = []
    seen: set[str] = set()
    for dirpath, _dn, files in os.walk(runtime):
        for fname in sorted(files):
            if not fname.lower().endswith(".motion3.json"):
                continue
            stem = fname[: -len(".motion3.json")]
            # 过滤掉 _OFF_ 开头的动作（关闭动作，不可叠加，对用户无意义）
            if stem.startswith("_OFF_"):
                continue
            if stem not in seen:
                seen.add(stem)
                stems.append(stem)
    return stems


def scan_live2d_models(models_dir: str) -> list[dict[str, Any]]:
    """Scan models_dir for all Live2D model subdirectories."""
    results: list[dict[str, Any]] = []
    if not os.path.isdir(models_dir):
        return results
    for sub_name in sorted(os.listdir(models_dir)):
        sub_dir = os.path.join(models_dir, sub_name)
        if not os.path.isdir(sub_dir):
            continue
        if sub_name in IGNORE_IDS:
            continue
        found_model3 = None
        for dirpath, _dn, files in os.walk(sub_dir):
            for fname in files:
                if fname.lower().endswith(".model3.json"):
                    found_model3 = os.path.join(dirpath, fname)
                    break
            if found_model3:
                break
        if not found_model3:
            continue
        try:
            with open(found_model3, encoding="utf-8-sig") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError):
            continue
        refs = data.get("FileReferences", {})
        moc = refs.get("Moc") or ""
        runtime_dir = os.path.dirname(found_model3)
        moc_path = os.path.join(runtime_dir, moc) if moc else ""
        if not moc_path or not os.path.isfile(moc_path):
            continue
        stems = list_live2d_motion_stems(found_model3)
        thumb = resolve_live2d_thumb(found_model3) or ""
        display_name = DISPLAY_NAMES.get(sub_name, sub_name)
        results.append({
            "id": sub_name,
            "name": display_name,
            "thumb": thumb,
            "personality": "",
            "motions": [{"id": s, "label": s, "gif": "", "frames": []} for s in stems],
            "model_path": found_model3,
            "is_flat": False,
            "is_self_modeled_live2d": False,
        })
    return results
