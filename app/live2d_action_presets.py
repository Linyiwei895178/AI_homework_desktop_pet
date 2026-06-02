from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


ACTION_PRESET_FORMAT = "pet_buddy_live2d_action_preset_catalog_v1"
ACTION_SHOWCASE_FORMAT = "pet_buddy_live2d_action_showcase_v1"
ACTION_SHOWCASE_SIZE = 7

DEFAULT_ACTION_SHOWCASE_LABELS = (
    "标准正立呼吸",
    "轻挥手",
    "比心",
    "双手伸懒腰",
    "左重心 S 站姿",
    "左脚前迈",
    "回到待机",
)

LIVE2D_ACTION_PARAMETER_RANGES: dict[str, tuple[float, float]] = {
    "ParamAngleX": (-30.0, 30.0),
    "ParamAngleY": (-20.0, 20.0),
    "ParamAngleZ": (-18.0, 18.0),
    "ParamBodyAngleX": (-18.0, 18.0),
    "ParamBodyAngleY": (-14.0, 14.0),
    "ParamBodyAngleZ": (-16.0, 16.0),
    "ParamHipShiftX": (-1.0, 1.0),
    "ParamHipTiltZ": (-1.0, 1.0),
    "ParamShoulderTiltZ": (-1.0, 1.0),
    "ParamSpineCurve": (-1.0, 1.0),
    "ParamArmLRaise": (0.0, 1.0),
    "ParamArmRRaise": (0.0, 1.0),
    "ParamElbowLBend": (0.0, 1.0),
    "ParamElbowRBend": (0.0, 1.0),
    "ParamLegLStep": (-1.0, 1.0),
    "ParamLegRStep": (-1.0, 1.0),
    "ParamKneeLBend": (0.0, 1.0),
    "ParamKneeRBend": (0.0, 1.0),
    "ParamMuscleDefinition": (0.0, 1.0),
    "ParamConstructionLines": (0.0, 1.0),
}


def action_preset_catalog_path(project_root: str | Path) -> Path:
    return (
        Path(project_root)
        / "assets"
        / "live2d_modeling"
        / "pose_study"
        / "live2d_action_presets.json"
    )


def normalize_action_showcase_owner_id(owner_id: str | None = None) -> str:
    raw = str(owner_id or "").strip()
    raw = re.sub(r"[\\/:*?\"<>|]+", "_", raw)
    raw = re.sub(r"\s+", "_", raw).strip("._")
    return raw[:80] or ""


def action_showcase_path(project_root: str | Path, owner_id: str | None = None) -> Path:
    safe_owner = normalize_action_showcase_owner_id(owner_id)
    if safe_owner:
        return Path(project_root) / "data" / "live2d_action_showcases" / f"{safe_owner}.json"
    return Path(project_root) / "data" / "live2d_action_showcase.json"


def load_live2d_action_preset_catalog(project_root: str | Path) -> dict[str, Any]:
    path = action_preset_catalog_path(project_root)
    try:
        catalog = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {
            "format": ACTION_PRESET_FORMAT,
            "categories": [],
            "actions": [],
        }
    return catalog if isinstance(catalog, dict) else {"actions": []}


def load_live2d_action_presets(project_root: str | Path) -> list[dict[str, Any]]:
    catalog = load_live2d_action_preset_catalog(project_root)
    actions = catalog.get("actions", [])
    if not isinstance(actions, list):
        return []
    return [item for item in actions if isinstance(item, dict)]


def _action_by_id(actions: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        str(action.get("id")): action
        for action in actions
        if str(action.get("id") or "")
    }


def default_live2d_action_showcase_ids(actions: list[dict[str, Any]]) -> list[str]:
    by_label = {
        str(action.get("label") or ""): str(action.get("id") or "")
        for action in actions
        if str(action.get("id") or "")
    }
    chosen: list[str] = []
    for label in DEFAULT_ACTION_SHOWCASE_LABELS:
        action_id = by_label.get(label)
        if action_id and action_id not in chosen:
            chosen.append(action_id)
    for action in actions:
        action_id = str(action.get("id") or "")
        if action_id and action_id not in chosen:
            chosen.append(action_id)
        if len(chosen) >= ACTION_SHOWCASE_SIZE:
            break
    return chosen[:ACTION_SHOWCASE_SIZE]


def normalize_live2d_action_showcase_ids(
    actions: list[dict[str, Any]],
    action_ids: Any,
    *,
    size: int = ACTION_SHOWCASE_SIZE,
) -> list[str]:
    valid = _action_by_id(actions)
    normalized: list[str] = []
    seen: set[str] = set()
    if isinstance(action_ids, list):
        for item in action_ids[:size]:
            action_id = str(item or "")
            if not action_id:
                normalized.append("")
            elif action_id in valid and action_id not in seen:
                normalized.append(action_id)
                seen.add(action_id)
            else:
                normalized.append("")
    return normalized


def load_live2d_action_showcase_ids(
    project_root: str | Path,
    owner_id: str | None = None,
) -> list[str]:
    actions = load_live2d_action_presets(project_root)
    path = action_showcase_path(project_root, owner_id)
    raw_ids: Any = []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        data = {}
    if isinstance(data, dict):
        raw_ids = data.get("action_ids") or data.get("actions") or []
        if isinstance(raw_ids, list) and raw_ids and isinstance(raw_ids[0], dict):
            raw_ids = [item.get("id") for item in raw_ids]
    elif isinstance(data, list):
        raw_ids = data
    return normalize_live2d_action_showcase_ids(actions, raw_ids)


def save_live2d_action_showcase_ids(
    project_root: str | Path,
    action_ids: list[str],
    owner_id: str | None = None,
) -> list[str]:
    actions = load_live2d_action_presets(project_root)
    normalized = normalize_live2d_action_showcase_ids(actions, action_ids)
    path = action_showcase_path(project_root, owner_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "format": ACTION_SHOWCASE_FORMAT,
        "size": ACTION_SHOWCASE_SIZE,
        "owner_id": normalize_action_showcase_owner_id(owner_id),
        "action_ids": normalized,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return normalized


def action_category_options(catalog: dict[str, Any]) -> list[tuple[str, str]]:
    categories = catalog.get("categories", [])
    options: list[tuple[str, str]] = []
    if isinstance(categories, list):
        for item in categories:
            if not isinstance(item, dict):
                continue
            key = str(item.get("id") or "")
            label = str(item.get("label") or key)
            if key:
                options.append((key, label))
    return options


def normalize_action_parameters(parameters: Any) -> dict[str, float]:
    if not isinstance(parameters, dict):
        return {}
    normalized: dict[str, float] = {}
    for key, value in parameters.items():
        name = str(key)
        if name not in LIVE2D_ACTION_PARAMETER_RANGES:
            continue
        lo, hi = LIVE2D_ACTION_PARAMETER_RANGES[name]
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            continue
        normalized[name] = round(max(lo, min(hi, numeric)), 3)
    return normalized


def compact_action_for_manifest(action: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "id",
        "label",
        "category",
        "category_label",
        "difficulty",
        "duration",
        "loop",
        "requires_alternate_art",
        "description",
        "rig_notes",
        "tags",
        "parameters",
    )
    compact = {key: action.get(key) for key in keys if key in action}
    compact["parameters"] = normalize_action_parameters(compact.get("parameters"))
    return compact


def compact_actions_for_showcase(
    actions: list[dict[str, Any]],
    action_ids: list[str],
) -> list[dict[str, Any]]:
    valid = _action_by_id(actions)
    return [
        compact_action_for_manifest(valid[action_id])
        for action_id in normalize_live2d_action_showcase_ids(actions, action_ids)
        if action_id in valid
    ]


def filter_live2d_action_presets(
    actions: list[dict[str, Any]],
    *,
    category: str = "",
    query: str = "",
    include_alternate_art: bool = True,
) -> list[dict[str, Any]]:
    category = category.strip()
    query = query.strip().lower()
    out: list[dict[str, Any]] = []
    for action in actions:
        if category and str(action.get("category") or "") != category:
            continue
        if not include_alternate_art and bool(action.get("requires_alternate_art")):
            continue
        if query:
            haystack = " ".join(
                str(action.get(key) or "")
                for key in ("id", "label", "category_label", "description", "rig_notes")
            ).lower()
            tags = action.get("tags", [])
            if isinstance(tags, list):
                haystack += " " + " ".join(str(tag).lower() for tag in tags)
            if query not in haystack:
                continue
        out.append(action)
    return out
