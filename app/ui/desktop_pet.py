"""
Live2D 桌宠动画播放器（PySide6 + live2d-py）
"""
from __future__ import annotations

import json
import os
import random
import re
import sys
import threading
import time
from typing import Any, Callable, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

import live2d.v3 as live2d
from live2d.v3 import MotionPriority
from OpenGL.GL import (
    GL_BLEND,
    GL_ONE_MINUS_SRC_ALPHA,
    GL_SRC_ALPHA,
    glBlendFunc,
    glClearColor,
    glEnable,
)
from PySide6.QtCore import QEvent, QObject, QPoint, QRect, QRectF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QCursor, QFont, QImage, QKeyEvent, QMouseEvent, QPainter, QPen, QPixmap, QWheelEvent
from PySide6.QtOpenGLWidgets import QOpenGLWidget
from PySide6.QtWidgets import (
  QApplication,
  QComboBox,
  QFrame,
  QHBoxLayout,
  QLabel,
  QLineEdit,
  QListWidget,
  QProgressBar,
  QPushButton,
  QTextEdit,
  QVBoxLayout,
  QWidget,
)

from app.ui.widgets import (
    ArcMotionMenu,
    BTN_GLASS,
    BTN_PRIMARY,
    ChatBubble,
    ChatHistoryStore,
    ControlConsole,
    InfoBubble,
    InputBox,
    MAO_PRO_ZH_DISPLAY,
    RightClickMenu,
    SubMenu,
    _app_font,
    _glass_style,
    _load_pixmap,
    apply_zhegou_idle_thumb,
    is_mao_pro_zh_model,
    load_custom_pet_ids,
    motion_label_from_filename,
    scan_flat_pets,
)

try:
    import win32con
    import win32gui
except ImportError:
    win32gui = None  # type: ignore
    win32con = None  # type: ignore

MODEL_PATH = (
    r"C:\Users\lenovo\AI_homework_desktop_pet\assets\models\mao_pro_zh"
    r"\mao_pro_zh\runtime\mao_pro.model3.json"
)

EMOTION_TO_EXPRESSION: dict[str, str] = {
    "exp_01": "exp_01",
    "exp_02": "exp_02",
    "exp_03": "exp_03",
    "exp_04": "exp_04",
    "exp_05": "exp_05",
    "exp_06": "exp_06",
    "exp_07": "exp_07",
    "exp_08": "exp_08",
    "smile": "exp_01",
    "happy": "exp_02",
    "sad": "exp_03",
    "angry": "exp_04",
    "surprised": "exp_05",
    "neutral": "exp_06",
    "shy": "exp_07",
    "sleepy": "exp_08",
}

MOTION_NAME_MAP: dict[str, str] = {
    "Idle": "待机",
    "": "展示动作",
    "default": "常规动作",
    "mtn_01": "动作一",
    "mtn_02": "动作二",
    "mtn_03": "动作三",
    "mtn_04": "动作四",
    "special_01": "特殊一",
    "special_02": "特殊二",
    "special_03": "特殊三",
}

HIT_AREAS = ("HitAreaHead", "HitAreaBody")
CHAT_GREETING = "你好呀！我是小黑，有什么可以帮我的吗？"
DRAG_THRESHOLD = 5
HOVER_FADE_ALPHA = int(255 * 0.7)
HEAD_CENTER_Y_OFFSET = 60
ANGLE_X_MIN, ANGLE_X_MAX = -30.0, 30.0
ANGLE_Y_MIN, ANGLE_Y_MAX = -20.0, 20.0
WIN32_TRANSPARENT_COLORKEY = 0x0000FF00

_SETTINGS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "data",
)
SETTINGS_PATH = os.path.join(_SETTINGS_DIR, "pet_ui_settings.json")

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ACTION_MAPPING_PATH = os.path.join(PROJECT_ROOT, "assets", "action_mapping.json")
SYNONYMS_PATH = os.path.join(PROJECT_ROOT, "assets", "synonyms.json")
ANIMATIONS_DIR = os.path.join(PROJECT_ROOT, "assets", "animations")
IMAGES_DIR = os.path.join(PROJECT_ROOT, "assets", "images")
MODELS_DIR = os.path.join(PROJECT_ROOT, "assets", "models")

DEFAULT_SYNONYMS: dict[str, list[str]] = {
  "happy": ["开心", "高兴", "幸福", "快乐", "愉快", "喜悦", "哈哈", "微笑", "笑"],
  "sad": ["伤心", "难过", "悲伤", "哭泣", "委屈", "沮丧", "郁闷"],
  "hungry": ["吃饭", "吃", "饿", "想吃", "讨食", "食物", "饭"],
  "angry": ["生气", "愤怒", "发火", "不爽", "暴躁", "炸毛"],
  "idle": ["idle", "待机", "站立", "发呆", "闲", "stand"],
}

SYNONYM_ACTION_LABELS: dict[str, str] = {
  "happy": "开心",
  "sad": "伤心",
  "hungry": "吃饭",
  "angry": "生气",
  "idle": "待机",
}

IDLE_FALLBACK_EXTRA = ["idle", "待机"]

DEFAULT_ACTION_MAPPING: dict[str, dict[str, list[str]]] = {
  "这狗": {
    "happy": ["这狗_anim_开心.gif", "这狗_anim_撒娇.gif"],
    "sad": ["这狗_anim_伤心.gif"],
    "hungry": ["这狗_anim_吃饭.gif"],
    "angry": ["这狗_anim_生气.gif"],
    "idle": ["这狗_anim_idle.gif"],
  },
}

MOOD_STAT_VALUES: dict[str, int] = {
  "happy": 90,
  "sad": 35,
  "angry": 25,
  "hungry": 40,
  "idle": 70,
  "normal": 75,
}

SYSTEM_VOICE_ON_CLICK = "喵～你好呀，我是你的桌面小伙伴！"


# ---------------------------------------------------------------------------
# 队员 C / D 接口（Mock + 真实实现自动切换）
# ---------------------------------------------------------------------------


class MockTeamC:
  """队员 C Mock：模拟逐字输出与系统语音。"""

  def __init__(self) -> None:
    self._logic_callback: Callable[[dict[str, Any]], None] | None = None

  def api_user_speak(
    self,
    text: str,
    current_state: dict[str, Any],
    ui_callback: Callable[[str], None],
  ) -> None:
    reply = f"喵～收到：{text.strip()}"

    def _run() -> None:
      try:
        for ch in reply:
          if ui_callback:
            ui_callback(ch)
          time.sleep(0.06)
        if self._logic_callback:
          self._logic_callback(
            {
              "event_type": "user_chat",
              "user_input": text.strip(),
              "ai_reply": reply,
              "word_count": len(reply),
            }
          )
      except Exception as exc:
        print(f"[MockTeamC] api_user_speak 异常: {exc}")
        if ui_callback:
          ui_callback(f"出错了: {exc}")

    threading.Thread(target=_run, daemon=True).start()

  def api_play_system_voice(self, text: str, state: str = "neutral", action: str = "speak") -> None:
    print(f"[MockTeamC] api_play_system_voice: {text} (state={state}, action={action})")

  def api_register_logic_callback(self, callback: Callable[[dict[str, Any]], None]) -> None:
    self._logic_callback = callback
    print("[MockTeamC] 队员D逻辑回调已绑定（Mock）")


class MockTeamD:
  """队员 D Mock：固定状态与 idle 决策。"""

  def __init__(self) -> None:
    self._history: list[dict[str, Any]] = [
      {
        "event": "mock_init",
        "mood": "happy",
        "energy": 85,
        "intimacy": 72,
        "timestamp": time.time(),
      }
    ]

  def api_get_pet_status(self) -> dict[str, Any]:
    return {"mood": "happy", "energy": 85, "intimacy": 72}

  def api_decide_action(self) -> str:
    return "idle"

  def api_get_status_history(self, n: int = 10) -> list:
    return list(self._history[-n:])

  def api_on_chat_finished(self, word_count: int) -> None:
    self._history.append(
      {
        "event": "chat_finished",
        "word_count": word_count,
        "mood": "happy",
        "energy": max(0, 85 - word_count // 30),
        "intimacy": min(100, 72 + word_count // 20),
        "timestamp": time.time(),
      }
    )


def _create_team_c() -> Any:
  try:
    from models.tts.echo_team_c_interface import EchoTeamCInterface
    return EchoTeamCInterface()
  except Exception as exc:
    print(f"[DesktopPet] 使用 MockTeamC（队员C未就绪: {exc}）")
    return MockTeamC()


def _create_team_d() -> Any:
  try:
    from models.state.echo_team_d_interface import EchoTeamDInterface
    from models.state.pet_state import PetState

    return EchoTeamDInterface(PetState())
  except Exception as exc:
    print(f"[DesktopPet] 使用 MockTeamD（队员D未就绪: {exc}）")
    return MockTeamD()


class ActionMappingStore:
  """读取 assets/action_mapping.json，按角色与动作名解析 GIF。"""

  def __init__(self, data: dict[str, dict[str, list[str]]]) -> None:
    self._data = data

  @classmethod
  def load(cls, path: str = ACTION_MAPPING_PATH) -> "ActionMappingStore":
    cls._ensure_file(path)
    data = json.loads(json.dumps(DEFAULT_ACTION_MAPPING))
    if os.path.isfile(path):
      try:
        with open(path, encoding="utf-8") as f:
          loaded = json.load(f)
        if isinstance(loaded, dict):
          for pet_id, actions in loaded.items():
            if isinstance(actions, dict):
              data[pet_id] = {
                str(k): [str(x) for x in v] if isinstance(v, list) else []
                for k, v in actions.items()
              }
      except (OSError, json.JSONDecodeError) as exc:
        print(f"[ActionMapping] 读取失败，使用内置默认: {exc}")
    return cls(data)

  @staticmethod
  def _ensure_file(path: str) -> None:
    if os.path.isfile(path):
      return
    try:
      os.makedirs(os.path.dirname(path), exist_ok=True)
      with open(path, "w", encoding="utf-8") as f:
        json.dump(DEFAULT_ACTION_MAPPING, f, ensure_ascii=False, indent=2)
      print(f"[ActionMapping] 已生成默认配置: {path}")
    except OSError as exc:
      print(f"[ActionMapping] 无法写入默认配置: {exc}")

  def _resolve_anim_path(self, filename: str) -> str:
    return _resolve_asset_path(os.path.join("assets", "animations", filename.strip()))

  def pick_gif(self, pet_id: str, action_code: str) -> str:
    pet_map = self._data.get(pet_id, {})
    candidates = list(pet_map.get(action_code, []) or [])
    if not candidates:
      candidates = list(pet_map.get("idle", []) or [])
    if not candidates:
      return ""
    chosen = random.choice(candidates)
    path = self._resolve_anim_path(chosen)
    if path and os.path.isfile(path):
      return path
    return ""

  def motions_for_pet(self, pet_id: str, scanned_motions: list[dict] | None = None) -> list[dict]:
    """从配置生成动作按钮列表；配置为空时回退扫描结果。"""
    motions: list[dict] = []
    pet_map = self._data.get(pet_id, {})
    for action_code, files in sorted(pet_map.items()):
      for fname in files:
        path = self._resolve_anim_path(fname)
        if not path or not os.path.isfile(path):
          continue
        motions.append(
          {
            "id": f"{action_code}:{os.path.basename(fname)}",
            "label": action_code,
            "gif": path,
            "frames": [],
          }
        )
    if motions:
      return motions
    return list(scanned_motions or [])


def scan_flat_pet_list(project_root: str = PROJECT_ROOT) -> list[dict]:
  """扫描平面角色：以 animations GIF 与 images 头像合并。"""
  return scan_flat_pets(project_root)


class SynonymStore:
  """同义词配置：读写 assets/synonyms.json。"""

  def __init__(self, data: dict[str, list[str]]) -> None:
    self._data: dict[str, list[str]] = {
      k: list(dict.fromkeys(str(w) for w in v if str(w).strip()))
      for k, v in data.items()
      if isinstance(v, list)
    }

  @classmethod
  def load(cls, path: str = SYNONYMS_PATH) -> "SynonymStore":
    cls._ensure_file(path)
    data = json.loads(json.dumps(DEFAULT_SYNONYMS))
    if os.path.isfile(path):
      try:
        with open(path, encoding="utf-8") as f:
          loaded = json.load(f)
        if isinstance(loaded, dict):
          for action, words in loaded.items():
            if isinstance(words, list):
              data[str(action)] = [str(w) for w in words]
      except (OSError, json.JSONDecodeError) as exc:
        print(f"[Synonyms] 读取失败，使用内置默认: {exc}")
    return cls(data)

  @staticmethod
  def _ensure_file(path: str) -> None:
    if os.path.isfile(path):
      return
    try:
      os.makedirs(os.path.dirname(path), exist_ok=True)
      with open(path, "w", encoding="utf-8") as f:
        json.dump(DEFAULT_SYNONYMS, f, ensure_ascii=False, indent=2)
      print(f"[Synonyms] 已生成默认配置: {path}")
    except OSError as exc:
      print(f"[Synonyms] 无法写入默认配置: {exc}")

  def save(self, path: str = SYNONYMS_PATH) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
      json.dump(self._data, f, ensure_ascii=False, indent=2)

  def all_actions(self) -> list[str]:
    order = ["happy", "sad", "hungry", "angry", "idle"]
    keys = set(self._data.keys()) | set(order)
    return [a for a in order if a in keys] + sorted(k for k in keys if k not in order)

  def words_for(self, action: str) -> list[str]:
    return list(self._data.get(action, []))

  def add_word(self, action: str, word: str) -> bool:
    w = word.strip()
    if not w:
      return False
    bucket = self._data.setdefault(action, [])
    if w not in bucket:
      bucket.append(w)
    return True

  def remove_word(self, action: str, word: str) -> bool:
    bucket = self._data.get(action, [])
    if word in bucket:
      bucket.remove(word)
      return True
    return False


class SynonymActionResolver:
  """根据队员 D 的动作名 + 同义词，匹配并播放平面 / Live2D 素材。"""

  def __init__(self, project_root: str, store: SynonymStore) -> None:
    self._root = project_root
    self.store = store

  def _synonyms(self, action: str, *, extra: list[str] | None = None) -> list[str]:
    words = list(self.store.words_for(action))
    if extra:
      words.extend(extra)
    return list(dict.fromkeys(w for w in words if w))

  @staticmethod
  def _name_matches(filename: str, synonyms: list[str]) -> bool:
    low = filename.lower()
    return any(s.lower() in low for s in synonyms)

  def _flat_scan_dirs(self, pet_id: str) -> list[str]:
    dirs: list[str] = []
    sub = os.path.join(ANIMATIONS_DIR, pet_id)
    if os.path.isdir(sub):
      dirs.append(sub)
    if os.path.isdir(ANIMATIONS_DIR):
      dirs.append(ANIMATIONS_DIR)
    return dirs

  def _iter_flat_files(self, pet_id: str) -> list[str]:
    found: list[str] = []
    seen: set[str] = set()
    prefix = f"{pet_id}_"
    for folder in self._flat_scan_dirs(pet_id):
      in_subfolder = folder.endswith(os.path.join("animations", pet_id))
      for fname in sorted(os.listdir(folder)):
        path = os.path.join(folder, fname)
        if not os.path.isfile(path):
          continue
        ext = os.path.splitext(fname)[1].lower()
        if ext not in (".gif", ".png"):
          continue
        if not in_subfolder and not (fname.startswith(prefix) or pet_id in fname):
          continue
        norm = os.path.normpath(path)
        if norm not in seen:
          seen.add(norm)
          found.append(norm)
    return found

  @staticmethod
  def _group_png_sequences(paths: list[str]) -> list[list[str]]:
    groups: dict[str, list[tuple[int, str]]] = {}
    for path in paths:
      base = os.path.basename(path)
      m = re.match(r"^(.+)_(\d+)\.png$", base, re.IGNORECASE)
      if m:
        key, seq = m.group(1), int(m.group(2))
        groups.setdefault(key, []).append((seq, path))
      else:
        groups.setdefault(base, []).append((0, path))
    out: list[list[str]] = []
    for _key, items in groups.items():
      out.append([p for _s, p in sorted(items, key=lambda x: x[0])])
    return out

  def _match_flat_assets(self, pet_id: str, action: str) -> tuple[list[str], list[list[str]]]:
    syns = self._synonyms(action)
    gifs: list[str] = []
    pngs: list[str] = []
    for path in self._iter_flat_files(pet_id):
      name = os.path.basename(path)
      if not self._name_matches(name, syns):
        continue
      if name.lower().endswith(".gif"):
        gifs.append(path)
      elif name.lower().endswith(".png"):
        pngs.append(path)
    return gifs, self._group_png_sequences(pngs)

  def _pick_flat_playable(
    self, pet_id: str, action: str, *, fallback_idle: bool = False
  ) -> dict[str, Any] | None:
    gifs, seq_groups = self._match_flat_assets(pet_id, action)
    if gifs:
      return {"type": "gif", "path": random.choice(gifs), "frames": []}
    if seq_groups:
      frames = random.choice(seq_groups)
      if frames:
        return {"type": "frames", "path": "", "frames": frames}
    if fallback_idle:
      return self._pick_flat_idle_fallback(pet_id)
    return None

  def _pick_flat_idle_fallback(self, pet_id: str) -> dict[str, Any] | None:
    idle_syns = self._synonyms("idle", extra=IDLE_FALLBACK_EXTRA)
    gifs: list[str] = []
    pngs: list[str] = []
    for path in self._iter_flat_files(pet_id):
      name = os.path.basename(path)
      if not self._name_matches(name, idle_syns):
        continue
      if name.lower().endswith(".gif"):
        gifs.append(path)
      elif name.lower().endswith(".png"):
        pngs.append(path)
    seq_groups = self._group_png_sequences(pngs)
    if gifs:
      return {"type": "gif", "path": gifs[0], "frames": []}
    if seq_groups:
      return {"type": "frames", "path": "", "frames": seq_groups[0]}
    all_gifs = [p for p in self._iter_flat_files(pet_id) if p.lower().endswith(".gif")]
    if all_gifs:
      return {"type": "gif", "path": sorted(all_gifs)[0], "frames": []}
    return None

  def _live2d_model_roots(self, pet_id: str, model_path: str | None = None) -> list[str]:
    roots: list[str] = []
    if model_path and os.path.isfile(model_path):
      roots.append(os.path.dirname(os.path.abspath(model_path)))
    candidate = os.path.join(MODELS_DIR, pet_id)
    if os.path.isdir(candidate):
      roots.append(candidate)
    if os.path.isdir(MODELS_DIR):
      for name in sorted(os.listdir(MODELS_DIR)):
        full = os.path.join(MODELS_DIR, name)
        if os.path.isdir(full) and pet_id.lower() in name.lower():
          roots.append(full)
    unique: list[str] = []
    seen: set[str] = set()
    for r in roots:
      norm = os.path.normpath(r)
      if norm not in seen:
        seen.add(norm)
        unique.append(norm)
    return unique

  def _iter_live2d_motions(self, pet_id: str, model_path: str | None = None) -> list[str]:
    files: list[str] = []
    seen: set[str] = set()
    for root in self._live2d_model_roots(pet_id, model_path):
      for dirpath, _dirnames, filenames in os.walk(root):
        for fname in sorted(filenames):
          if not fname.lower().endswith(".motion3.json"):
            continue
          full = os.path.normpath(os.path.join(dirpath, fname))
          if full not in seen:
            seen.add(full)
            files.append(full)
    return files

  @staticmethod
  def _motion_stem_from_file(path: str) -> str:
    base = os.path.basename(path)
    if base.lower().endswith(".motion3.json"):
      return base[: -len(".motion3.json")]
    return os.path.splitext(base)[0]

  def _match_live2d_motions(
    self, pet_id: str, action: str, model_path: str | None = None
  ) -> list[str]:
    syns = self._synonyms(action)
    matched = [
      p
      for p in self._iter_live2d_motions(pet_id, model_path)
      if self._name_matches(os.path.basename(p), syns)
    ]
    return matched

  def motions_for_flat(self, pet_id: str) -> list[dict]:
    menu: list[dict] = []
    gifs = [p for p in self._iter_flat_files(pet_id) if p.lower().endswith(".gif")]
    for gif in gifs:
      label = motion_label_from_filename(os.path.basename(gif))
      menu.append(
        {
          "id": f"file:{os.path.basename(gif)}",
          "label": label,
          "gif": gif,
          "frames": [],
          "action_code": "idle",
        }
      )
    pngs = [p for p in self._iter_flat_files(pet_id) if p.lower().endswith(".png")]
    for i, frames in enumerate(self._group_png_sequences(pngs)):
      if not frames:
        continue
      base = os.path.basename(frames[0])
      label = motion_label_from_filename(re.sub(r"_\d+$", "", os.path.splitext(base)[0]))
      menu.append(
        {
          "id": f"seq{i}:{label}",
          "label": label,
          "gif": "",
          "frames": frames,
          "action_code": "idle",
        }
      )
    return menu

  def motions_for_live2d(self, pet_id: str, model_path: str | None = None) -> list[dict]:
    menu: list[dict] = []
    for mpath in self._iter_live2d_motions(pet_id, model_path):
      stem = self._motion_stem_from_file(mpath)
      menu.append(
        {
          "id": stem,
          "label": stem,
          "gif": "",
          "frames": [],
          "motion_path": mpath,
          "action_code": "idle",
        }
      )
    return menu

  def play_flat_asset(self, player: "PlanePetPlayer", asset: dict[str, Any] | None) -> bool:
    if not player or not asset:
      return False
    return player.play_asset(gif=asset.get("path") or "", frames=asset.get("frames") or [])

  def play_flat_decided(self, pet_id: str, action: str, player: "PlanePetPlayer | None") -> bool:
    if not player:
      return False
    asset = self._pick_flat_playable(pet_id, action)
    if asset:
      self.play_flat_asset(player, asset)
      print(f"[SynonymAction] 平面 {pet_id} 动作 {action} -> {asset.get('path') or 'PNG序列'}")
      return True
    asset = self._pick_flat_idle_fallback(pet_id)
    if asset:
      self.play_flat_asset(player, asset)
      print(f"[SynonymAction] 平面 {pet_id} 未匹配 {action}，兜底 idle/首个动图")
      return True
    print(f"[SynonymAction] 警告: 平面角色 {pet_id} 无任何可播放动图")
    return False

  def play_live2d_decided(
    self,
    pet_id: str,
    action: str,
    play_fn: Callable[[str], bool],
    model_path: str | None = None,
  ) -> bool:
    matched = self._match_live2d_motions(pet_id, action, model_path)
    if matched:
      stem = self._motion_stem_from_file(random.choice(matched))
      if play_fn(stem):
        print(f"[SynonymAction] Live2D {pet_id} 动作 {action} -> {stem}")
        return True
    all_motions = self._iter_live2d_motions(pet_id, model_path)
    if all_motions:
      stem = self._motion_stem_from_file(sorted(all_motions)[0])
      if play_fn(stem):
        print(f"[SynonymAction] Live2D {pet_id} 未匹配 {action}，兜底 -> {stem}")
        return True
    print(f"[SynonymAction] 警告: Live2D 角色 {pet_id} 无 .motion3.json 动作文件")
    return False

  def play_flat_motion_item(self, player: "PlanePetPlayer | None", motion: dict) -> bool:
    if not player:
      return False
    gif = motion.get("gif") or ""
    frames = motion.get("frames") or []
    if gif or frames:
      return player.play_asset(gif=gif, frames=frames)
    action = motion.get("action_code") or motion.get("id", "idle").split(":")[0]
    asset = self._pick_flat_playable(motion.get("pet_id", ""), action) if motion.get("pet_id") else None
    return bool(asset and self.play_flat_asset(player, asset))


def enrich_flat_pet(
  pet: dict,
  mapping: ActionMappingStore,
  resolver: SynonymActionResolver | None = None,
) -> dict:
  """合并扫描数据、同义词动作与 action_mapping 配置。"""
  pet = dict(pet)
  pet["is_flat"] = True
  pet_id = pet.get("id", "")
  if resolver:
    pet["motions"] = resolver.motions_for_flat(pet_id)
    idle_asset = resolver._pick_flat_idle_fallback(pet_id)
    if idle_asset and idle_asset.get("type") == "gif":
      pet["idle_gif"] = idle_asset.get("path", "")
  else:
    scanned_motions = pet.get("motions", [])
    pet["motions"] = mapping.motions_for_pet(pet_id, scanned_motions)
    idle_from_map = mapping.pick_gif(pet_id, "idle")
    if idle_from_map:
      pet["idle_gif"] = idle_from_map
  thumb = _resolve_asset_path(pet.get("thumb") or "")
  if not thumb:
    thumb = _resolve_asset_path(os.path.join("assets", "images", f"{pet_id}_image.png"))
  if thumb:
    pet["thumb"] = thumb
    pet["idle_image"] = thumb
  pet = _normalize_flat_pet(pet)
  return apply_zhegou_idle_thumb(PROJECT_ROOT, pet)


class ChatStreamBridge(QObject):
  """将队员 C 后台线程的流式文字块安全投递到主线程 UI。"""

  chunk_received = Signal(str)


class StatusHistoryViewer(QWidget):
  """显示 api_get_status_history 原始记录。"""

  def __init__(self, records: list, parent: QWidget | None = None) -> None:
    super().__init__(parent)
    self.setWindowTitle("状态历史记录")
    self.resize(560, 420)
    lay = QVBoxLayout(self)
    lay.addWidget(QLabel("<h3>状态历史（api_get_status_history 原始输出）</h3>"))
    box = QTextEdit()
    box.setReadOnly(True)
    box.setPlainText(self._format_records(records))
    lay.addWidget(box, 1)
    row = QHBoxLayout()
    row.addStretch()
    close_btn = QPushButton("关闭")
    close_btn.clicked.connect(self.close)
    row.addWidget(close_btn)
    lay.addLayout(row)

  @staticmethod
  def _format_records(records: list) -> str:
    if not records:
      return "(空列表)"
    lines: list[str] = []
    for i, item in enumerate(records):
      lines.append(f"--- 记录 {i} ---")
      lines.append(repr(item))
    return "\n".join(lines)


class PetControlConsole(ControlConsole):
  """集成队员 C/D、动作映射与平面素材库的控制台。"""

  def __init__(
    self,
    desktop_pet: "DesktopPet",
    project_root: str,
    model_path: str,
    available_motions: list[str],
    motion_name_map: dict[str, str],
  ) -> None:
    self._desk = desktop_pet
    super().__init__(
      project_root=project_root,
      model_path=model_path,
      available_motions=available_motions,
      motion_name_map=motion_name_map,
      on_play_motion=desktop_pet.play_motion,
      on_pet_changed=desktop_pet.switch_to_pet,
    )
    self._flat = desktop_pet.list_flat_pets_enriched()
    self._history_viewer: StatusHistoryViewer | None = None
    self._reload_flat_tab()
    self._setup_console_nav()
    self.sync_dashboard_stats()

  def _setup_console_nav(self) -> None:
    self.resize(800, 600)
    self.setMinimumSize(720, 540)
    if hasattr(self, "_stack"):
      old = self._stack.widget(4)
      if old is not None:
        self._stack.removeWidget(old)
        old.deleteLater()
      self._stack.insertWidget(4, self._page_synonym_settings())

  def _install_synonym_settings_page(self) -> None:
    pass

  def _page_synonym_settings(self) -> QWidget:
    w = QWidget()
    lay = QVBoxLayout(w)
    lay.setContentsMargins(24, 16, 24, 24)
    lay.addWidget(QLabel("<h2>同义词管理</h2>"))
    lay.addWidget(QLabel("<p>为动作添加关键词后，智能匹配文件名并立即生效（无需重启）。</p>"))
    row = QHBoxLayout()
    self._syn_action_combo = QComboBox()
    for code in self._desk.synonym_store.all_actions():
      self._syn_action_combo.addItem(SYNONYM_ACTION_LABELS.get(code, code), code)
    row.addWidget(QLabel("动作"))
    row.addWidget(self._syn_action_combo, 1)
    lay.addLayout(row)
    add_row = QHBoxLayout()
    self._syn_word_input = QLineEdit()
    self._syn_word_input.setPlaceholderText("输入新同义词…")
    add_btn = QPushButton("添加")
    add_btn.setStyleSheet(BTN_PRIMARY)
    add_btn.clicked.connect(self._on_synonym_add)
    add_row.addWidget(self._syn_word_input, 1)
    add_row.addWidget(add_btn)
    lay.addLayout(add_row)
    lay.addWidget(QLabel("当前同义词列表"))
    self._syn_list = QListWidget()
    lay.addWidget(self._syn_list, 1)
    del_row = QHBoxLayout()
    del_btn = QPushButton("删除选中")
    del_btn.setStyleSheet(BTN_GLASS)
    del_btn.clicked.connect(self._on_synonym_delete)
    del_row.addStretch()
    del_row.addWidget(del_btn)
    lay.addLayout(del_row)
    self._syn_action_combo.currentIndexChanged.connect(self._refresh_synonym_list)
    self._refresh_synonym_list()
    return w

  def _current_syn_action(self) -> str:
    return self._syn_action_combo.currentData() or "idle"

  def _refresh_synonym_list(self) -> None:
    if not hasattr(self, "_syn_list"):
      return
    self._syn_list.clear()
    for word in self._desk.synonym_store.words_for(self._current_syn_action()):
      self._syn_list.addItem(word)

  def _on_synonym_add(self) -> None:
    action = self._current_syn_action()
    word = self._syn_word_input.text().strip()
    if not word:
      return
    self._desk.synonym_store.add_word(action, word)
    self._desk.synonym_store.save()
    self._syn_word_input.clear()
    self._refresh_synonym_list()
    self._desk.refresh_pet_motions_after_synonym_change()
    self._show_toast(f"已添加同义词: {word}")

  def _on_synonym_delete(self) -> None:
    action = self._current_syn_action()
    item = self._syn_list.currentItem()
    if item is None:
      return
    self._desk.synonym_store.remove_word(action, item.text())
    self._desk.synonym_store.save()
    self._refresh_synonym_list()
    self._desk.refresh_pet_motions_after_synonym_change()
    self._show_toast("已删除同义词")

  def _reload_flat_tab(self) -> None:
    self._flat = self._desk.list_flat_pets_enriched()
    self._custom_ids = load_custom_pet_ids(self._project_root)
    self._reload_character_tabs()

  def _open_pet_main(self, pet: dict) -> None:
    if pet.get("is_flat") or pet.get("is_custom"):
      built = self._desk.build_pet_record(pet.get("id", ""))
      if built:
        pet = built
      self._apply_pet_switch(pet)
      return
    if pet["id"] in {p["id"] for p in self._flat}:
      built = self._desk.build_pet_record(pet.get("id", ""))
      if built:
        pet = built
      self._apply_pet_switch(pet)
      return
    super()._open_pet_main(pet)

  def sync_dashboard_stats(self) -> None:
    self.stats = self._desk.stats_for_dashboard()
    if hasattr(self, "_dash_pet_pic"):
      self._refresh_dashboard()

  def _current_pet(self) -> dict | None:
    return self._get_pet(self._current_pet_id)

  def _refresh_dashboard(self) -> None:
    pet = self._current_pet()
    if not pet or not hasattr(self, "_dash_pet_pic"):
      return
    thumb = pet.get("thumb") or self._pet_idle_path(pet)
    self._dash_pet_pic.setPixmap(_load_pixmap(thumb, QSize(100, 100)))
    self._dash_pet_name.setText(f"<b>{pet['name']}</b>")
    self._dash_pet_personality.setText(pet.get("personality", ""))

  def _page_dashboard(self) -> QWidget:
    import datetime

    w = QWidget()
    lay = QVBoxLayout(w)
    lay.setContentsMargins(24, 16, 24, 24)
    now = datetime.datetime.now()
    wd = "一二三四五六日"[now.weekday()]
    lay.addWidget(QLabel(f"<h2>欢迎回来，用户</h2><p>{now.year}年{now.month}月{now.day}日 星期{wd}</p>"))
    cards = QHBoxLayout()
    for icon, title, key, col in (
      ("🐾", "宠物心情", "mood", "#3b82f6"),
      ("🔥", "能量值", "energy", "#fb923c"),
      ("❤️", "好感度", "affection", "#ec4899"),
    ):
      cards.addWidget(self._stat_card(icon, title, self.stats[key], col))
    lay.addLayout(cards)
    tool_row = QHBoxLayout()
    hist_btn = QPushButton("查看历史")
    hist_btn.setStyleSheet(BTN_GLASS)
    hist_btn.clicked.connect(self._show_status_history)
    tool_row.addWidget(hist_btn)
    tool_row.addStretch()
    lay.addLayout(tool_row)
    lay.addWidget(QLabel("<h3>当前宠物简介</h3>"))
    intro = QFrame()
    intro.setStyleSheet(_glass_style(14))
    il = QHBoxLayout(intro)
    self._dash_pet_pic = QLabel()
    self._dash_pet_pic.setAlignment(Qt.AlignmentFlag.AlignCenter)
    il.addWidget(self._dash_pet_pic)
    tx = QVBoxLayout()
    self._dash_pet_name = QLabel()
    self._dash_pet_personality = QLabel()
    self._dash_pet_personality.setWordWrap(True)
    tx.addWidget(self._dash_pet_name)
    tx.addWidget(self._dash_pet_personality)
    il.addLayout(tx, 1)
    lay.addWidget(intro)
    lay.addStretch()
    return w

  def _show_status_history(self) -> None:
    records = self._desk.team_d.api_get_status_history(10)
    self._history_viewer = StatusHistoryViewer(records, self)
    self._history_viewer.show()

  def _apply_pet_switch(self, pet: dict) -> None:
    self._flat = scan_flat_pet_list(self._project_root)
    if pet.get("is_flat") or pet["id"] in {p["id"] for p in self._flat}:
      pet = self._desk.build_pet_record(pet["id"]) or pet
    pet = self._get_pet(pet["id"]) or pet
    self._current_pet_id = pet["id"]
    self._sel_pet = pet["id"]
    self._pet_main_id = pet["id"]
    self._stop_animation()
    self.sync_dashboard_stats()
    self._show_toast(f"已切换到 {pet['name']}")
    self._nav("dashboard")
    self._log(f"切换角色: {pet['name']} ({pet['id']})")
    if self.on_pet_changed:
      self.on_pet_changed(pet)

  def _refresh_pet_main(self) -> None:
    pet = self._get_pet(self._pet_main_id)
    if not pet or not hasattr(self, "_pet_main_pic"):
      return
    if pet.get("is_flat"):
      pet = self._desk.build_pet_record(pet["id"]) or pet
    idle_path = self._pet_idle_path(pet)
    self._pet_main_name.setText(f"<h2>{pet['name']}</h2>")
    self._pet_main_desc.setText(pet.get("personality", ""))
    self._pet_main_pic.setPixmap(_load_pixmap(idle_path, QSize(120, 120)))
    while self._pet_main_motions_lay.count():
      item = self._pet_main_motions_lay.takeAt(0)
      if item.widget():
        item.widget().deleteLater()
    motions = self._desk.motions_for_dashboard(pet)
    if not motions:
      b = QPushButton("暂无动作")
      b.setEnabled(False)
      b.setStyleSheet(BTN_GLASS)
      self._pet_main_motions_lay.addWidget(b)
    else:
      for m in motions:
        b = QPushButton(m.get("label", m.get("id", "动作")))
        b.setStyleSheet(BTN_GLASS)
        b.clicked.connect(
          lambda _=False, motion=m, p=pet: self._desk.play_flat_motion(
            motion, self._pet_main_pic, self._pet_idle_path(p), QSize(120, 120)
          )
        )
        self._pet_main_motions_lay.addWidget(b)


def _resolve_asset_path(path: str) -> str:
  """将相对/绝对资产路径解析为可读取的本地文件路径。"""
  if not path:
    return ""
  raw = path.strip()
  if os.path.isfile(raw):
    return os.path.normpath(raw)
  normalized = raw.replace("/", os.sep).replace("\\", os.sep)
  for base in (PROJECT_ROOT, os.getcwd()):
    candidate = os.path.normpath(os.path.join(base, normalized))
    if os.path.isfile(candidate):
      return candidate
  return ""


def _normalize_flat_pet(pet: dict) -> dict:
  """规范化平面角色字典中的资产路径。"""
  out = dict(pet)
  out["is_flat"] = True
  for key in ("thumb", "idle_image", "idle_gif"):
    if out.get(key):
      out[key] = _resolve_asset_path(out[key])
  motions: list[dict] = []
  for motion in pet.get("motions", []):
    item = dict(motion)
    if item.get("gif"):
      item["gif"] = _resolve_asset_path(item["gif"])
    item["frames"] = [
      resolved
      for frame in item.get("frames", [])
      if (resolved := _resolve_asset_path(frame))
    ]
    motions.append(item)
  out["motions"] = motions
  if not out.get("idle_gif"):
    for motion in motions:
      gif = motion.get("gif") or ""
      if gif and motion.get("id", "").lower() != "idle":
        out["idle_gif"] = gif
        break
  if not out.get("idle_image") and out.get("thumb"):
    out["idle_image"] = out["thumb"]
  return out


def _flat_motion_playable(motion: dict) -> bool:
  gif = motion.get("gif") or ""
  frames = motion.get("frames") or []
  return bool(gif and os.path.isfile(gif)) or bool(frames)


try:
  from PIL import Image as PILImage
  _PIL_AVAILABLE = True
except ImportError:
  PILImage = None  # type: ignore[misc, assignment]
  _PIL_AVAILABLE = False


def _pil_image_to_pixmap(img: "PILImage.Image") -> QPixmap:
  rgba = img.convert("RGBA")
  w, h = rgba.size
  data = rgba.tobytes("raw", "RGBA")
  qimg = QImage(data, w, h, w * 4, QImage.Format.Format_RGBA8888)
  return QPixmap.fromImage(qimg.copy())


class PlanePetPlayer(QWidget):
  """平面角色 GIF / PNG 序列播放器（鼠标穿透，由 PetWindow 统一处理事件）。"""

  FRAME_MS = 100

  def __init__(self, parent: QWidget | None = None) -> None:
    super().__init__(parent)
    self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
    self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
    self._display = QLabel(self)
    self._display.setAlignment(Qt.AlignmentFlag.AlignCenter)
    self._display.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
    self._motions: dict[str, dict] = {}
    self._idle_gif = ""
    self._idle_frame = ""
    self._pixmap_rect = QRect()
    self._gif_on_finish: Callable[[], None] | None = None
    self._gif_timer = QTimer(self)
    self._gif_timer.timeout.connect(self._on_gif_timer)
    self._gif_frames: list[QPixmap] = []
    self._gif_durations_ms: list[int] = []
    self._gif_frame_index = 0
    self._pil_gif = None
    self._loop_gif = False
    self._frame_timer = QTimer(self)
    self._frame_timer.timeout.connect(self._on_frame_tick)
    self._frames: list[str] = []
    self._frame_index = 0
    self._playing_motion = False
    self.hide()

  def set_pet(self, pet: dict, width: int, height: int) -> None:
    pet = _normalize_flat_pet(pet)
    self.setGeometry(0, 0, width, height)
    self._display.setGeometry(0, 0, width, height)
    self._motions = {
      m["id"]: m
      for m in pet.get("motions", [])
      if _flat_motion_playable(m)
    }
    self._idle_gif = _resolve_asset_path(pet.get("idle_gif") or "")
    if not self._idle_gif or not os.path.isfile(self._idle_gif):
      self._idle_gif = ""
    self._idle_frame = ""
    static = _resolve_asset_path(pet.get("thumb") or pet.get("idle_image") or "")
    if static and os.path.isfile(static):
      self._idle_frame = static
    elif pet.get("motions"):
      for motion in pet["motions"]:
        frames = motion.get("frames") or []
        if frames and os.path.isfile(frames[0]):
          self._idle_frame = frames[0]
          break
    self.show()
    self.show_idle()

  def show_idle(self) -> None:
    self._playing_motion = False
    self._stop_playback()
    if self._idle_gif and os.path.isfile(self._idle_gif):
      self._start_gif(self._idle_gif, loop=True)
    elif self._idle_frame and os.path.isfile(self._idle_frame):
      self._show_still(self._idle_frame)
    else:
      self._display.clear()
      self._pixmap_rect = QRect()
      print("[PlanePetPlayer] 无可用的待机资源")

  def play_asset(self, *, gif: str = "", frames: list[str] | None = None) -> bool:
    """直接播放 GIF 或 PNG 序列（同义词智能匹配结果）。"""
    self._playing_motion = True
    self._stop_playback()
    if gif and os.path.isfile(gif):
      self._start_gif(gif, loop=False, on_finish=self.show_idle)
      return True
    frame_list = [f for f in (frames or []) if os.path.isfile(f)]
    if frame_list:
      self._frames = frame_list
      self._frame_index = 0
      self._on_frame_tick()
      self._frame_timer.start(self.FRAME_MS)
      return True
    self._playing_motion = False
    return False

  def play_motion(self, action_name: str) -> bool:
    key = action_name.strip()
    motion = self._motions.get(key)
    if motion is None:
      for mid, item in self._motions.items():
        if mid.lower() == key.lower():
          motion = item
          break
    if not motion:
      return False
    gif = _resolve_asset_path(motion.get("gif") or "")
    frames = motion.get("frames") or []
    self._playing_motion = True
    self._stop_playback()
    if gif and os.path.isfile(gif):
      self._start_gif(gif, loop=False, on_finish=self.show_idle)
      return True
    if frames:
      self._frames = [f for f in frames if os.path.isfile(f)]
      if not self._frames:
        self._playing_motion = False
        return False
      self._frame_index = 0
      self._on_frame_tick()
      self._frame_timer.start(self.FRAME_MS)
      return True
    self._playing_motion = False
    return False

  def hit_test(self, pos: tuple[int, int]) -> bool:
    if self._pixmap_rect.isEmpty():
      return False
    return self._pixmap_rect.contains(QPoint(pos[0], pos[1]))

  def tick(self) -> None:
    pass

  def _stop_playback(self) -> None:
    self._frame_timer.stop()
    self._gif_timer.stop()
    self._gif_frames = []
    self._gif_durations_ms = []
    self._gif_frame_index = 0
    self._loop_gif = False
    if self._pil_gif is not None:
      try:
        self._pil_gif.close()
      except Exception:
        pass
      self._pil_gif = None
    self._gif_on_finish = None
    self._frames = []
    self._frame_index = 0

  def _start_gif(
    self,
    path: str,
    *,
    loop: bool,
    on_finish: Callable[[], None] | None = None,
  ) -> None:
    path = _resolve_asset_path(path)
    if not path or not os.path.isfile(path):
      print(f"[PlanePetPlayer] GIF 不存在: {path}")
      if on_finish:
        on_finish()
      return
    if not _PIL_AVAILABLE or PILImage is None:
      print("[PlanePetPlayer] 未安装 Pillow，无法播放 GIF。请运行: pip install Pillow")
      if on_finish:
        on_finish()
      return
    self._gif_timer.stop()
    self._gif_frames = []
    self._gif_durations_ms = []
    if self._pil_gif is not None:
      try:
        self._pil_gif.close()
      except Exception:
        pass
      self._pil_gif = None
    try:
      img = PILImage.open(path)
      self._pil_gif = img
      frame_count = getattr(img, "n_frames", 1) or 1
      for i in range(frame_count):
        img.seek(i)
        self._gif_frames.append(_pil_image_to_pixmap(img))
        duration = int(img.info.get("duration", 100) or 100)
        self._gif_durations_ms.append(max(duration, 20))
    except Exception as exc:
      print(f"[PlanePetPlayer] GIF 加载失败 ({path}): {exc}")
      if self._pil_gif is not None:
        try:
          self._pil_gif.close()
        except Exception:
          pass
        self._pil_gif = None
      if on_finish:
        on_finish()
      return
    if not self._gif_frames:
      print(f"[PlanePetPlayer] GIF 无有效帧: {path}")
      if on_finish:
        on_finish()
      return
    self._loop_gif = loop
    self._gif_on_finish = on_finish
    self._gif_frame_index = 0
    self._show_gif_frame(0)
    self._display.show()
    if len(self._gif_frames) == 1 and not loop:
      QTimer.singleShot(self._gif_durations_ms[0], self._finish_gif_playback)
    else:
      self._gif_timer.start(self._gif_durations_ms[0])

  def _show_gif_frame(self, index: int) -> None:
    if index < 0 or index >= len(self._gif_frames):
      return
    pm = self._gif_frames[index]
    size = self._display.size()
    if size.width() < 1 or size.height() < 1:
      size = self.size()
    if size.width() > 0 and size.height() > 0:
      pm = pm.scaled(
        size,
        Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
      )
    self._display.setPixmap(pm)
    self._update_rect_from_pixmap(pm)

  def _on_gif_timer(self) -> None:
    next_index = self._gif_frame_index + 1
    if next_index >= len(self._gif_frames):
      if self._loop_gif:
        next_index = 0
      else:
        self._gif_timer.stop()
        self._finish_gif_playback()
        return
    self._gif_frame_index = next_index
    self._show_gif_frame(self._gif_frame_index)
    self._gif_timer.start(self._gif_durations_ms[self._gif_frame_index])

  def _finish_gif_playback(self) -> None:
    done = self._gif_on_finish
    self._gif_on_finish = None
    if done:
      done()

  def _on_frame_tick(self) -> None:
    if not self._frames:
      self._frame_timer.stop()
      self.show_idle()
      return
    self._show_still(self._frames[self._frame_index])
    self._frame_index = self._frame_index + 1
    if self._frame_index >= len(self._frames):
      self._frame_timer.stop()
      self._playing_motion = False
      self.show_idle()

  def _show_still(self, path: str) -> None:
    pm = QPixmap(path)
    if pm.isNull():
      self._display.clear()
      self._pixmap_rect = QRect()
      return
    scaled = pm.scaled(
      self._display.size(),
      Qt.AspectRatioMode.KeepAspectRatio,
      Qt.TransformationMode.SmoothTransformation,
    )
    self._display.setPixmap(scaled)
    self._update_rect_from_pixmap(scaled)

  def _update_rect_from_display(self) -> None:
    pm = self._display.pixmap()
    if pm is not None and not pm.isNull():
      self._update_rect_from_pixmap(pm)
      return
    self._update_rect_from_pixmap(QPixmap())

  def _update_rect_from_pixmap(self, pm: QPixmap) -> None:
    if pm.isNull():
      self._pixmap_rect = QRect()
      return
    x = (self.width() - pm.width()) // 2
    y = (self.height() - pm.height()) // 2
    self._pixmap_rect = QRect(x, y, pm.width(), pm.height())

  def resizeEvent(self, event) -> None:
    super().resizeEvent(event)
    self._display.setGeometry(0, 0, self.width(), self.height())
    if self._gif_frames and 0 <= self._gif_frame_index < len(self._gif_frames):
      self._show_gif_frame(self._gif_frame_index)
    elif self._display.pixmap() is not None:
      pm = self._display.pixmap()
      if pm is not None and not pm.isNull():
        scaled = pm.scaled(
          self._display.size(),
          Qt.AspectRatioMode.KeepAspectRatio,
          Qt.TransformationMode.SmoothTransformation,
        )
        self._display.setPixmap(scaled)
        self._update_rect_from_pixmap(scaled)


# ---------------------------------------------------------------------------
# Pet Buddy 主题（参考图：粉色毛玻璃、大圆角、柔和阴影）
# ---------------------------------------------------------------------------

_THEME_PINK = "#FF8DA1"
_THEME_PINK_HOVER = "#FF7A92"
_THEME_PINK_LIGHT = "#FFE4EC"
_THEME_PINK_BG_START = "#FCE4EC"
_THEME_PINK_BG_END = "#FFF5F8"
_THEME_TEXT = "#333333"
_THEME_TEXT_MUTED = "#757575"
_THEME_BORDER = "rgba(255, 141, 161, 0.18)"
_THEME_CARD = "rgba(255, 255, 255, 0.88)"
_THEME_GLASS = "rgba(255, 255, 255, 0.78)"
_FONT_STACK = '"Microsoft YaHei UI", "Segoe UI", "PingFang SC", sans-serif'

_PRIMARY_BTN_TEXTS = frozenset({
  "喂食", "发送", "上传平面图片", "+",
})


def _pet_font(size: int, bold: bool = False) -> QFont:
  from PySide6.QtGui import QFontDatabase
  if sys.platform == "win32":
    for name in ("Microsoft YaHei UI", "Microsoft YaHei", "Segoe UI", "PingFang SC"):
      if QFontDatabase.hasFamily(name):
        f = QFont(name, size)
        f.setBold(bold)
        return f
  f = QFont("Segoe UI", size)
  f.setBold(bold)
  return f


def _soft_shadow(
  widget: QWidget,
  blur: float = 18.0,
  offset_y: float = 4.0,
  alpha: int = 55,
) -> None:
  from PySide6.QtWidgets import QGraphicsDropShadowEffect
  effect = QGraphicsDropShadowEffect(widget)
  effect.setBlurRadius(blur)
  effect.setOffset(0, offset_y)
  effect.setColor(QColor(255, 141, 161, alpha))
  widget.setGraphicsEffect(effect)


def _glass_qss(radius: int = 20) -> str:
  return f"""
    QFrame#glass {{
      background-color: {_THEME_GLASS};
      border: 1px solid {_THEME_BORDER};
      border-radius: {radius}px;
    }}
  """


def _btn_glass_qss(radius: int = 24) -> str:
  return f"""
    QPushButton {{
      background-color: rgba(255, 255, 255, 0.92);
      border: 1px solid {_THEME_BORDER};
      border-radius: {radius}px;
      padding: 10px 18px;
      color: {_THEME_TEXT};
      font-family: {_FONT_STACK};
      font-size: 14px;
    }}
    QPushButton:hover {{
      background-color: {_THEME_PINK_LIGHT};
      border-color: rgba(255, 141, 161, 0.35);
    }}
    QPushButton:pressed {{
      background-color: #FFD0DC;
    }}
    QPushButton:checked {{
      background-color: {_THEME_PINK_LIGHT};
      color: {_THEME_PINK};
      border-color: rgba(255, 141, 161, 0.45);
      font-weight: 600;
    }}
  """


def _btn_primary_qss(radius: int = 24) -> str:
  return f"""
    QPushButton {{
      background-color: {_THEME_PINK};
      color: white;
      border: none;
      border-radius: {radius}px;
      padding: 10px 22px;
      font-family: {_FONT_STACK};
      font-size: 14px;
      font-weight: 600;
    }}
    QPushButton:hover {{ background-color: {_THEME_PINK_HOVER}; }}
    QPushButton:pressed {{ background-color: #F06B85; }}
  """


APP_GLOBAL_QSS = f"""
* {{
  font-family: {_FONT_STACK};
  color: {_THEME_TEXT};
}}
QLabel {{
  color: {_THEME_TEXT};
  font-size: 14px;
}}
QLineEdit, QTextEdit {{
  background-color: rgba(255, 255, 255, 0.92);
  border: 1px solid {_THEME_BORDER};
  border-radius: 20px;
  padding: 10px 16px;
  color: {_THEME_TEXT};
  font-size: 14px;
  selection-background-color: {_THEME_PINK_LIGHT};
}}
QLineEdit:focus, QTextEdit:focus {{
  border: 1px solid rgba(255, 141, 161, 0.55);
}}
QTabWidget::pane {{
  border: none;
  background: transparent;
}}
QTabBar::tab {{
  background: rgba(255, 255, 255, 0.6);
  border: 1px solid {_THEME_BORDER};
  border-radius: 16px;
  padding: 8px 18px;
  margin-right: 6px;
  color: {_THEME_TEXT_MUTED};
}}
QTabBar::tab:selected {{
  background: {_THEME_PINK_LIGHT};
  color: {_THEME_PINK};
  font-weight: 600;
}}
QProgressBar {{
  background: #F3E8EB;
  border: none;
  border-radius: 6px;
  height: 8px;
}}
QProgressBar::chunk {{
  background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
    stop:0 {_THEME_PINK}, stop:1 #FFB3C1);
  border-radius: 6px;
}}
QScrollBar:vertical {{
  background: transparent;
  width: 8px;
  margin: 4px 2px;
}}
QScrollBar::handle:vertical {{
  background: rgba(255, 141, 161, 0.35);
  border-radius: 4px;
  min-height: 24px;
}}
QScrollBar::handle:vertical:hover {{
  background: rgba(255, 141, 161, 0.55);
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
  height: 0;
}}
QScrollBar:horizontal {{
  background: transparent;
  height: 8px;
}}
QScrollBar::handle:horizontal {{
  background: rgba(255, 141, 161, 0.35);
  border-radius: 4px;
}}
QScrollArea {{
  border: none;
  background: transparent;
}}
"""


def _patch_menu_paint(menu: RightClickMenu | SubMenu, *, dim_active: bool = False) -> None:
  """覆盖自绘菜单：毛玻璃白底圆角 + Pet Buddy 粉色调 hover。"""
  font = _pet_font(15 if isinstance(menu, SubMenu) else 16)
  radius = 12 if isinstance(menu, SubMenu) else 16

  def paintEvent(_event) -> None:
    if not menu.visible:
      return
    from PySide6.QtGui import QPainter, QPainterPath, QPen
    p = QPainter(menu)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setFont(font)
    bg = QPainterPath()
    bg.addRoundedRect(QRectF(0, 0, menu.width(), menu.height()), radius, radius)
    p.fillPath(bg, QColor(255, 255, 255, 248))
    p.setPen(QPen(QColor(226, 232, 240, 220), 1))
    p.drawPath(bg)
    pad = menu.PADDING
    ih = menu.ITEM_HEIGHT
    for i, label in enumerate(menu.ITEMS):
      item_r = QRect(0, pad + i * ih, menu.WIDTH, ih)
      is_dim = dim_active and i == menu.active_index
      is_hover = i == menu.hover_index and not is_dim
      if is_hover:
        path = QPainterPath()
        path.addRoundedRect(QRectF(item_r.adjusted(4, 2, -4, -2)), 10, 10)
        p.fillPath(path, QColor(255, 228, 236, 230))
      color = QColor(180, 180, 190) if is_dim else QColor(51, 51, 51)
      if is_hover:
        color = QColor(255, 122, 146)
      p.setPen(color)
      indent = 12 if isinstance(menu, SubMenu) else 16
      p.drawText(item_r.adjusted(indent, 0, 0, 0), Qt.AlignmentFlag.AlignVCenter, label)
    p.end()

  menu.paintEvent = paintEvent  # type: ignore[method-assign]


def _patch_arc_menu_paint(menu: ArcMotionMenu) -> None:
  from PySide6.QtGui import QPainter, QPainterPath
  font = _pet_font(12)

  def paintEvent(_event) -> None:
    if not menu.visible:
      return
    p = QPainter(menu)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setFont(font)
    for i, item in enumerate(menu.items):
      pop = menu._pop_scale(i)
      if pop <= 0.01:
        continue
      hovered = i == menu.hover_index
      r = menu.button_rect(i, hovered)
      path = QPainterPath()
      path.addEllipse(QRectF(r))
      if hovered:
        p.fillPath(path, QColor(255, 141, 161, 215))
      else:
        p.fillPath(path, QColor(255, 255, 255, 225))
      p.setPen(QColor(255, 255, 255) if hovered else QColor(51, 51, 51))
      label = str(item.get("label", ""))
      if len(label) > 5:
        label = label[:4] + "…"
      p.drawText(r, Qt.AlignmentFlag.AlignCenter, label)
    p.end()

  menu.paintEvent = paintEvent  # type: ignore[method-assign]


def _apply_desktop_overlays(pet: "DesktopPet") -> None:
  """桌宠窗口上的菜单、气泡、输入框。"""
  glass_widgets = (
    pet.context_menu, pet.pin_submenu, pet.hover_submenu,
    pet.status_submenu, pet.chat_submenu, pet.info_bubble, pet.chat_bubble, pet.input_box,
  )
  radii = {pet.context_menu: 20, pet.pin_submenu: 16, pet.hover_submenu: 16,
           pet.status_submenu: 16, pet.chat_submenu: 16, pet.info_bubble: 20, pet.chat_bubble: 20,
           pet.input_box: 24}
  for w in glass_widgets:
    if w is None:
      continue
    w.setObjectName("glass")
    w.setAutoFillBackground(True)
    w.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
    w.setStyleSheet(_glass_qss(radii.get(w, 20)).replace("248", "252"))
    _soft_shadow(w, blur=16, offset_y=3, alpha=45)
  if pet.context_menu:
    _patch_menu_paint(pet.context_menu)
  for sm in (pet.pin_submenu, pet.hover_submenu, pet.status_submenu, pet.chat_submenu):
    if sm:
      _patch_menu_paint(sm, dim_active=True)
  if pet.arc_menu:
    pet.arc_menu.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
    _patch_arc_menu_paint(pet.arc_menu)
    _soft_shadow(pet.arc_menu, blur=20, offset_y=4, alpha=40)
  if pet.input_box and hasattr(pet.input_box, "_btn"):
    pet.input_box._btn.setStyleSheet(_btn_primary_qss(20))
  for bubble in (pet.info_bubble, pet.chat_bubble):
    if bubble and hasattr(bubble, "_lbl"):
      bubble._lbl.setFont(_pet_font(15))
  if pet.input_box and hasattr(pet.input_box, "_field"):
    pet.input_box._field.setFont(_pet_font(15))
    pet.input_box._field.setStyleSheet("background: transparent; border: none;")


def _apply_control_console_theme(console: ControlConsole) -> None:
  """控制台：渐变背景、侧边栏毛玻璃、卡片阴影、按钮样式。"""
  console.setStyleSheet(f"""
    QMainWindow {{
      background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 {_THEME_PINK_BG_START}, stop:1 {_THEME_PINK_BG_END});
    }}
  """)
  central = console.centralWidget()
  if central:
    central.setStyleSheet(f"""
      background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 {_THEME_PINK_BG_START}, stop:1 {_THEME_PINK_BG_END});
    """)

  sidebar: QFrame | None = None
  if central and central.layout() and central.layout().count() > 0:
    item = central.layout().itemAt(0)
    if item and item.widget() and isinstance(item.widget(), QFrame):
      sidebar = item.widget()

  if sidebar:
    sidebar.setObjectName("sidebar")
    sidebar.setStyleSheet(f"""
      QFrame#sidebar {{
        background-color: {_THEME_GLASS};
        border: none;
        border-right: 1px solid {_THEME_BORDER};
        border-top-right-radius: 24px;
        border-bottom-right-radius: 24px;
      }}
    """)
    _soft_shadow(sidebar, blur=22, offset_y=0, alpha=35)

  for frame in console.findChildren(QFrame):
    if frame is sidebar:
      continue
    if frame.objectName() != "sidebar":
      frame.setObjectName("glass")
    frame.setStyleSheet(_glass_qss(20))
    _soft_shadow(frame, blur=14, offset_y=3, alpha=40)

  for btn in console.findChildren(QPushButton):
    if btn.objectName() == "switchPetBtn":
      btn.setStyleSheet("""
        QPushButton#switchPetBtn {
          background-color: #7c3aed; color: white; border: none;
          border-radius: 12px; padding: 10px 22px; font-weight: bold;
        }
        QPushButton#switchPetBtn:hover { background-color: #6d28d9; }
        QPushButton#switchPetBtn:pressed { background-color: #5b21b6; }
      """)
      _soft_shadow(btn, blur=12, offset_y=2, alpha=35)
      continue
    text = btn.text().strip().replace("\n", " ")
    is_primary = (
      any(k in text for k in _PRIMARY_BTN_TEXTS)
      or text.startswith("喂食")
      or (len(text) <= 4 and text in ("发送", "上传平面图片"))
    )
    is_chrome = text in ("—", "□", "×", "← 返回")
    if is_chrome:
      btn.setStyleSheet(f"""
        QPushButton {{
          background: rgba(255,255,255,0.5);
          border: none; border-radius: 14px;
          color: {_THEME_TEXT_MUTED}; font-size: 13px;
        }}
        QPushButton:hover {{ background: {_THEME_PINK_LIGHT}; color: {_THEME_PINK}; }}
      """)
      btn.setFixedSize(32, 32)
    elif is_primary:
      btn.setStyleSheet(_btn_primary_qss())
      _soft_shadow(btn, blur=12, offset_y=2, alpha=35)
    else:
      btn.setStyleSheet(_btn_glass_qss())
      if btn.isCheckable():
        pass
      elif btn.iconSize().width() > 50:
        btn.setStyleSheet(_btn_glass_qss(20))

  for lbl in console.findChildren(QLabel):
    if "<h2>" in lbl.text() or "欢迎" in lbl.text():
      lbl.setFont(_pet_font(22, True))
    elif "<h3>" in lbl.text():
      lbl.setFont(_pet_font(17, True))
    else:
      lbl.setFont(_pet_font(14))

  if sidebar:
    for child in sidebar.findChildren(QLabel):
      if "Pet Console" in child.text() or "Console" in child.text():
        child.setText("💗  Pet Buddy")
        child.setFont(_pet_font(20, True))
        child.setStyleSheet(f"color: {_THEME_PINK}; padding: 4px 0;")

  for bar in console.findChildren(QProgressBar):
    bar.setStyleSheet(f"""
      QProgressBar {{
        background: #F3E8EB; border: none; border-radius: 6px; height: 8px;
      }}
      QProgressBar::chunk {{
        background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
          stop:0 {_THEME_PINK}, stop:1 #FFB3C1);
        border-radius: 6px;
      }}
    """)


class _ResizeOverlay(QWidget):
  """边缘长按后显示的等比缩放框。"""

  HANDLE = 12

  def __init__(self, pet: "DesktopPet", parent: QWidget | None = None) -> None:
    super().__init__(parent)
    self._pet = pet
    self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
    self.hide()

  def show_overlay(self) -> None:
    self.setGeometry(0, 0, self._pet._win_w, self._pet._win_h)
    self.show()
    self.raise_()

  def hide_overlay(self) -> None:
    self.hide()

  def _corner_at(self, pos: QPoint) -> str | None:
    w, h = self.width(), self.height()
    hs = self.HANDLE
    corners = {
      "tl": QRect(0, 0, hs, hs),
      "tr": QRect(w - hs, 0, hs, hs),
      "bl": QRect(0, h - hs, hs, hs),
      "br": QRect(w - hs, h - hs, hs, hs),
    }
    for name, rect in corners.items():
      if rect.contains(pos):
        return name
    return None

  def paintEvent(self, _event) -> None:
    p = QPainter(self)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(QPen(QColor(255, 141, 161, 200), 2, Qt.PenStyle.DashLine))
    p.setBrush(QColor(255, 255, 255, 20))
    p.drawRoundedRect(self.rect().adjusted(2, 2, -2, -2), 8, 8)
    hs = self.HANDLE
    for rect in (
      QRect(0, 0, hs, hs),
      QRect(self.width() - hs, 0, hs, hs),
      QRect(0, self.height() - hs, hs, hs),
      QRect(self.width() - hs, self.height() - hs, hs, hs),
    ):
      p.fillRect(rect, QColor(255, 141, 161, 180))
    p.end()

  def mousePressEvent(self, event: QMouseEvent) -> None:
    if event.button() == Qt.MouseButton.LeftButton:
      corner = self._corner_at(event.position().toPoint())
      if corner:
        self._pet._begin_corner_resize(corner, event.globalPosition().toPoint())
        event.accept()
        return
    super().mousePressEvent(event)


class _ArcMenuHideFilter(QObject):
  """环形菜单自行关闭时恢复主窗口焦点（仅 desktop_pet 内使用）。"""

  def __init__(self, pet: "DesktopPet") -> None:
    super().__init__()
    self._pet = pet

  def eventFilter(self, watched: QObject, event: QEvent) -> bool:
    if (
      event.type() == QEvent.Type.Hide
      and self._pet.arc_menu is not None
      and watched is self._pet.arc_menu
    ):
      QTimer.singleShot(0, self._pet._on_arc_menu_hidden)
    return False


class Live2DWidget(QOpenGLWidget):
  """OpenGL 渲染 Live2D 模型。"""

  def __init__(self, pet: "DesktopPet") -> None:
    super().__init__()
    self._pet = pet
    self._gl_ready = False
    self.setMouseTracking(True)
    self.setAttribute(Qt.WidgetAttribute.WA_AlwaysStackOnTop, False)

  def initializeGL(self) -> None:
    live2d.init()
    live2d.glInit()
    glEnable(GL_BLEND)
    glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
    self._pet._init_model_gl()
    self._gl_ready = True
    if is_mao_pro_zh_model(self._pet.model_path):
      QTimer.singleShot(200, self._pet._capture_mao_pro_motion_preview)

  def resizeGL(self, w: int, h: int) -> None:
    if self._pet._model is not None:
      self._pet._model.Resize(w, h)

  def paintGL(self) -> None:
    if self._pet._model is None:
      return
    glClearColor(0.0, 1.0, 0.0, 1.0)
    live2d.clearBuffer(0.0, 1.0, 0.0, 1.0)
    self._pet._model.Draw()

  def mouseMoveEvent(self, event: QMouseEvent) -> None:
    pos = (event.position().x(), event.position().y())
    self._pet._on_mouse_move(pos)

  def mousePressEvent(self, event: QMouseEvent) -> None:
    pos = (int(event.position().x()), int(event.position().y()))
    if event.button() == Qt.MouseButton.RightButton:
      self._pet._open_context_menu(pos)
    elif event.button() == Qt.MouseButton.LeftButton:
      self._pet._on_left_press(pos)

  def mouseReleaseEvent(self, event: QMouseEvent) -> None:
    if event.button() == Qt.MouseButton.LeftButton:
      pos = (int(event.position().x()), int(event.position().y()))
      self._pet._on_left_release(pos)


class PetWindow(QWidget):
  """无边框透明桌宠主窗口。"""

  def __init__(self, pet: "DesktopPet") -> None:
    super().__init__()
    self._pet = pet
    self.setWindowFlags(
      Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint
    )
    self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
    self.setWindowTitle("Live2D Desktop Pet")
    self.setMouseTracking(True)

    layout = QVBoxLayout(self)
    layout.setContentsMargins(0, 0, 0, 0)
    self._gl = Live2DWidget(pet)
    layout.addWidget(self._gl)
    self._gl.lower()

    self._plane_player = PlanePetPlayer(self)
    self._plane_player.hide()

    pet.info_bubble.setParent(self)
    pet.chat_bubble.setParent(self)
    pet.input_box.setParent(self)
    pet.arc_menu.setParent(self)
    pet.context_menu.setParent(self)
    pet.pin_submenu.setParent(self)
    pet.hover_submenu.setParent(self)
    pet.status_submenu.setParent(self)
    pet.chat_submenu.setParent(self)

    self._resize_overlay = _ResizeOverlay(pet, self)
    self._resize_overlay.hide()

    pet.input_box.submitted.connect(pet._submit_chat)
    self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

  def showEvent(self, event) -> None:
    super().showEvent(event)
    self._pet._init_win32_window(int(self.winId()))
    self._pet._set_pin_top(self._pet._pin_top)

  def paintEvent(self, event) -> None:
    super().paintEvent(event)

  def mouseMoveEvent(self, event: QMouseEvent) -> None:
    if self._pet._is_flat_mode():
      pos = (event.position().x(), event.position().y())
      self._pet._on_mouse_move(pos)
    super().mouseMoveEvent(event)

  def mousePressEvent(self, event: QMouseEvent) -> None:
    pos = (int(event.position().x()), int(event.position().y()))
    if self._pet._is_flat_mode():
      if event.button() == Qt.MouseButton.RightButton:
        self._pet._open_context_menu(pos)
      elif event.button() == Qt.MouseButton.LeftButton:
        if self._pet._any_menu_open():
          self._pet._on_window_left_press(pos)
        else:
          self._pet._on_left_press(pos)
    else:
      if event.button() == Qt.MouseButton.RightButton:
        self._pet._open_context_menu(pos)
      elif event.button() == Qt.MouseButton.LeftButton:
        self._pet._on_window_left_press(pos)
    super().mousePressEvent(event)

  def mouseReleaseEvent(self, event: QMouseEvent) -> None:
    if self._pet._is_flat_mode() and event.button() == Qt.MouseButton.LeftButton:
      pos = (int(event.position().x()), int(event.position().y()))
      self._pet._on_left_release(pos)
    super().mouseReleaseEvent(event)

  def keyPressEvent(self, event: QKeyEvent) -> None:
    if event.key() == Qt.Key.Key_Escape:
      self._pet._dismiss_menus()
      self._pet._hide_resize_overlay()
      event.accept()
      return
    super().keyPressEvent(event)

  def wheelEvent(self, event: QWheelEvent) -> None:
    if event.modifiers() & Qt.KeyboardModifier.ControlModifier or abs(event.angleDelta().y()) > 0:
      delta = event.angleDelta().y()
      factor = 1.0 + (delta / 1200.0)
      self._pet._scale_window(factor)
      event.accept()
      return
    super().wheelEvent(event)


class DesktopPet:
  """Live2D 桌宠：模型动画、透明背景、视线跟随、菜单与对话。"""

  def __init__(
    self,
    model_path: str = MODEL_PATH,
    position: tuple[int, int] = (100, 100),
    window_size: tuple[int, int] | None = None,
    image_path: str | None = None,
  ):
    self.model_path = os.path.normpath(model_path)
    self.position = list(position)
    self.current_state = "idle"
    self.window_size = window_size
    _ = image_path

    self._model: Optional[live2d.LAppModel] = None
    self._motion_index: dict[str, tuple[str, int]] = {}
    self._running = False
    self.available_motions: list[str] = []
    self.motion_name_map = MOTION_NAME_MAP

    self.on_click_callback: Optional[Callable[..., Any]] = None

    self._hwnd: Optional[int] = None
    self._win_w = 0
    self._win_h = 0
    self._pin_top = True
    self._hover_fade_enabled = True
    self._status_bar_enabled = False
    self._hovering_window = False
    self._window_alpha = 255

    self._dragging = False
    self._drag_start_screen: tuple[int, int] = (0, 0)
    self._drag_start_win: tuple[int, int] = (0, 0)
    self._click_start: tuple[int, int] = (0, 0)
    self._click_moved = False

    self._aspect_ratio = 450 / 600
    self._resize_visible = False
    self._resizing_corner: str | None = None
    self._resize_start_global: QPoint | None = None
    self._resize_start_size: tuple[int, int] = (450, 600)
    self._edge_hold_timer = QTimer()
    self._edge_hold_timer.setSingleShot(True)
    self._edge_hold_timer.timeout.connect(self._show_resize_overlay)
    self._chat_history = ChatHistoryStore(PROJECT_ROOT)

    self._app: Optional[QApplication] = None
    self._window: Optional[PetWindow] = None
    self._timer: Optional[QTimer] = None

    self.context_menu: Optional[RightClickMenu] = None
    self.pin_submenu: Optional[SubMenu] = None
    self.hover_submenu: Optional[SubMenu] = None
    self.status_submenu: Optional[SubMenu] = None
    self.chat_submenu: Optional[SubMenu] = None
    self.arc_menu: Optional[ArcMotionMenu] = None
    self.info_bubble: Optional[InfoBubble] = None
    self.chat_bubble: Optional[ChatBubble] = None
    self.input_box: Optional[InputBox] = None
    self._chat_open = False
    self._active_pet: dict | None = None
    self._console: PetControlConsole | None = None
    self._chat_stream: ChatStreamBridge | None = None

    self._bind_team_interfaces()
    self._load_settings()

  def load_synonyms(self) -> None:
    self.synonym_store = SynonymStore.load()
    self.synonym_resolver = SynonymActionResolver(PROJECT_ROOT, self.synonym_store)

  def _bind_team_interfaces(self) -> None:
    self.action_mapping = ActionMappingStore.load()
    self.load_synonyms()
    self.team_c = _create_team_c()
    self.team_d = _create_team_d()

    def on_chat_event(event: dict[str, Any]) -> None:
      wc = int(event.get("word_count", 0) or 0)
      if hasattr(self.team_d, "api_on_chat_finished"):
        self.team_d.api_on_chat_finished(wc)
      QTimer.singleShot(0, self._after_chat_status_update)

    if hasattr(self.team_c, "api_register_logic_callback"):
      self.team_c.api_register_logic_callback(on_chat_event)

  def _after_chat_status_update(self) -> None:
    self.play_action_from_decision()
    if self._console:
      self._console.sync_dashboard_stats()

  @staticmethod
  def _scan_portrait_pet_ids() -> list[str]:
    if not os.path.isdir(IMAGES_DIR):
      return []
    ids: list[str] = []
    for fname in os.listdir(IMAGES_DIR):
      m = re.match(r"^(.+)_image\.png$", fname, re.IGNORECASE)
      if m:
        ids.append(m.group(1))
    return sorted(ids)

  def list_flat_pets_enriched(self) -> list[dict]:
    pets = scan_flat_pet_list()
    known = {p["id"] for p in pets}
    for pet_id in self._scan_portrait_pet_ids():
      if pet_id in known:
        continue
      thumb = _resolve_asset_path(os.path.join("assets", "images", f"{pet_id}_image.png"))
      pets.append(
        {
          "id": pet_id,
          "name": pet_id,
          "thumb": thumb,
          "idle_image": thumb,
          "idle_gif": "",
          "personality": f"平面素材角色 · {pet_id}",
          "motions": [],
          "is_flat": True,
        }
      )
    return [enrich_flat_pet(p, self.action_mapping, self.synonym_resolver) for p in pets]

  def refresh_pet_motions_after_synonym_change(self) -> None:
    if self._active_pet and self._active_pet.get("is_flat"):
      rebuilt = self.build_pet_record(self._active_pet.get("id", ""))
      if rebuilt:
        self._active_pet = rebuilt
        if self._window:
          self._window._plane_player.set_pet(rebuilt, self._win_w, self._win_h)
    if self._console:
      self._console._reload_flat_tab()
      self._console.sync_dashboard_stats()

  def build_pet_record(self, pet_id: str) -> dict | None:
    for pet in self.list_flat_pets_enriched():
      if pet["id"] == pet_id:
        return pet
    return None

  def stats_for_dashboard(self) -> dict[str, int]:
    raw = self.team_d.api_get_pet_status()
    mood = raw.get("mood", "happy")
    if isinstance(mood, (int, float)):
      mood_val = int(mood)
    else:
      mood_val = MOOD_STAT_VALUES.get(str(mood).lower(), 75)
    energy = int(raw.get("energy", 72))
    intimacy = int(raw.get("intimacy", raw.get("affection", 72)))
    return {"mood": mood_val, "energy": energy, "affection": intimacy}

  def motions_for_dashboard(self, pet: dict) -> list[dict]:
    if pet.get("is_flat"):
      return self.synonym_resolver.motions_for_flat(pet.get("id", ""))
    return self.synonym_resolver.motions_for_live2d(
      pet.get("id", "mao"),
      pet.get("model_path") or self.model_path,
    )

  def play_flat_motion(
    self,
    motion: dict,
    pic_label: QLabel,
    idle_path: str,
    size: QSize,
  ) -> None:
    if self._console:
      self._console._play_motion(motion, pic_label, idle_path, size)
    if self._is_flat_mode():
      player = self._plane_player()
      if player:
        motion = dict(motion)
        motion["pet_id"] = (self._active_pet or {}).get("id", "")
        self.synonym_resolver.play_flat_motion_item(player, motion)

  def play_action_from_decision(self) -> None:
    action = self.team_d.api_decide_action()
    if self._is_flat_mode() and self._active_pet:
      pet_id = self._active_pet.get("id", "")
      self.synonym_resolver.play_flat_decided(pet_id, action, self._plane_player())
    elif self._model is not None:
      pet_id = (self._active_pet or {}).get("id", "mao")
      model_path = (self._active_pet or {}).get("model_path") or self.model_path
      self.synonym_resolver.play_live2d_decided(
        pet_id, action, self.play_motion, model_path=model_path
      )

  def send_to_ai(self, msg: str) -> str:
    return f"收到：{msg}"

  def play_model_motion(self, motion_name: str) -> bool:
    return self.play_motion(motion_name)

  def switch_to_pet(self, pet: dict) -> None:
    """切换桌宠显示：平面角色使用 PlanePetPlayer，Live2D 恢复 GL 模型。"""
    if self._window is None:
      return

    pet_id = pet.get("id", "")
    built = self.build_pet_record(pet_id)
    if built:
      pet = built
    elif pet.get("is_flat"):
      pet = enrich_flat_pet(_normalize_flat_pet(pet), self.action_mapping, self.synonym_resolver)
    self._active_pet = pet
    name = pet.get("name") or pet.get("id", "")
    if pet.get("is_flat"):
      self._window._gl.hide()
      self._window._plane_player.set_pet(pet, self._win_w, self._win_h)
      self._window._plane_player.show()
      self._window._plane_player.lower()
      self._raise_ui_overlays()
      print(
        f"[DesktopPet] 平面角色加载: idle_gif={pet.get('idle_gif', '')}, "
        f"idle_image={pet.get('idle_image', '')}, motions={len(pet.get('motions', []))}"
      )
    else:
      self._window._plane_player.hide()
      self._window._gl.show()
      self._start_idle_motion()
    self._update_mouse_passthrough(self._local_mouse_pos())
    self._show_switch_notice(name)
    print(f"[DesktopPet] 已切换到: {name}")
    QTimer.singleShot(0, self._after_pet_switch)

  def _after_pet_switch(self) -> None:
    self.play_action_from_decision()
    if self._console:
      self._console.sync_dashboard_stats()

  def _is_flat_mode(self) -> bool:
    return bool(self._active_pet and self._active_pet.get("is_flat"))

  def _plane_player(self) -> PlanePetPlayer | None:
    if self._window is None:
      return None
    return self._window._plane_player

  def _raise_ui_overlays(self) -> None:
    if self._window is None:
      return
    for widget in (
      self._window._plane_player,
      self._window._gl,
      self.info_bubble,
      self.chat_bubble,
      self.input_box,
      self.arc_menu,
      self.context_menu,
      self.pin_submenu,
      self.hover_submenu,
      self.status_submenu,
      self.chat_submenu,
    ):
      if widget is not None:
        widget.raise_()

  def _current_arc_motion_items(self) -> list[dict[str, str]]:
    if self._is_flat_mode() and self._active_pet:
      items: list[dict[str, str]] = []
      for motion in self._active_pet.get("motions", []):
        if not _flat_motion_playable(motion):
          continue
        mid = motion.get("id", "")
        items.append({"label": motion.get("label", mid), "value": mid})
      return items
    return [
      {"label": self.motion_name_map.get(m, m), "value": m}
      for m in self.available_motions
    ]

  def _lower_character_layer(self) -> None:
    if self._window is None:
      return
    if self._is_flat_mode():
      self._window._plane_player.lower()
    else:
      self._window._gl.lower()

  def _show_switch_notice(self, name: str) -> None:
    if self.chat_bubble is None or self._window is None:
      return
    msg = f"已切换到 {name}"
    prev_open = self._chat_open
    self._chat_open = True
    self._layout_bubbles(chat_text=msg)

    def _restore() -> None:
      if not prev_open:
        self._chat_open = False
        self.chat_bubble.hide()
      else:
        self._layout_bubbles()

    QTimer.singleShot(2500, _restore)

  def play_motion(self, motion_name: str) -> bool:
    key = motion_name.strip()
    if self._is_flat_mode():
      player = self._plane_player()
      if player is None:
        return False
      if key.lower() in ("idle", "待机"):
        player.show_idle()
        print(f"[DesktopPet] 平面角色回到待机")
        return True
      if player.play_motion(key):
        print(f"[DesktopPet] 播放平面动作: {key}")
        return True
      print(f"[DesktopPet] 未找到平面动作: {key}")
      return False
    if self._model is None:
      return False
    group, index = self._resolve_motion(motion_name)
    if group is None:
      print(f"[DesktopPet] 未找到动作: {motion_name}")
      return False
    self._model.StartMotion(
      group,
      index,
      MotionPriority.NORMAL,
      onFinishMotionHandler=self._start_idle_motion,
    )
    print(f"[DesktopPet] 播放动作: {motion_name}")
    return True

  def set_expression(self, emotion: str) -> bool:
    if self._is_flat_mode():
      print(f"[DesktopPet] 平面角色暂不支持表情切换: {emotion}")
      self.current_state = emotion
      return True
    if self._model is None:
      return False
    expression_id = EMOTION_TO_EXPRESSION.get(emotion.strip().lower(), emotion)
    try:
      self._model.SetExpression(expression_id)
      self.current_state = emotion
      return True
    except Exception as exc:
      print(f"[DesktopPet] 设置表情失败 ({expression_id}): {exc}")
      return False

  def on_click(self, x: int, y: int) -> dict[str, Any]:
    result: dict[str, Any] = {
      "x": x,
      "y": y,
      "hit_areas": [],
      "hit_parts": [],
      "clicked": False,
    }
    if self._is_flat_mode():
      player = self._plane_player()
      if player and player.hit_test((x, y)):
        result["hit_areas"] = ["HitAreaBody"]
        result["clicked"] = True
        try:
          self.team_c.api_play_system_voice(SYSTEM_VOICE_ON_CLICK)
        except Exception as exc:
          print(f"[DesktopPet] api_play_system_voice 失败: {exc}")
      if self.on_click_callback:
        self.on_click_callback(result)
      return result
    if self._model is None:
      return result
    for area_id in HIT_AREAS:
      if self._model.HitTest(area_id, x, y):
        result["hit_areas"].append(area_id)
        result["clicked"] = True
    parts = self._model.HitPart(float(x), float(y), True)
    if parts:
      result["hit_parts"] = parts
      result["clicked"] = True
    if result["clicked"]:
      try:
        self.team_c.api_play_system_voice(SYSTEM_VOICE_ON_CLICK)
      except Exception as exc:
        print(f"[DesktopPet] api_play_system_voice 失败: {exc}")
    if self.on_click_callback:
      self.on_click_callback(result)
    return result

  def run(self) -> None:
    if not os.path.isfile(self.model_path):
      raise FileNotFoundError(f"模型文件不存在: {self.model_path}")

    self._app = QApplication.instance() or QApplication(sys.argv)
    self._app.setStyleSheet(APP_GLOBAL_QSS)
    self._init_ui_widgets()

    size = self.window_size or (450, 600)
    self._win_w, self._win_h = size
    self._aspect_ratio = self._win_w / max(1, self._win_h)
    self._resize_start_size = (self._win_w, self._win_h)

    self._window = PetWindow(self)
    self._window.setGeometry(self.position[0], self.position[1], self._win_w, self._win_h)
    self._window.show()

    self._set_pin_top(self._pin_top)
    self._apply_window_opacity(255)
    if self._status_bar_enabled and self.info_bubble:
      self._layout_bubbles()
    self._running = True

    self._timer = QTimer()
    self._timer.timeout.connect(self._tick)
    self._timer.start(16)

    self._app.exec()
    self.close()

  def _init_ui_widgets(self) -> None:
    """在 QApplication 创建后初始化 Qt 控件。"""
    self.context_menu = RightClickMenu()
    self.pin_submenu = SubMenu(("开始置顶", "关闭置顶"))
    self.hover_submenu = SubMenu(("开启", "关闭"))
    self.status_submenu = SubMenu(("开启状态栏", "关闭状态栏"))
    self.chat_submenu = SubMenu(("开启AI对话", "关闭AI对话"))
    self.arc_menu = ArcMotionMenu()
    self.info_bubble = InfoBubble()
    self.chat_bubble = ChatBubble()
    self.input_box = InputBox()
    self.pin_submenu.set_active(self._pin_top)
    self.hover_submenu.set_active(self._hover_fade_enabled)
    self.status_submenu.set_active(self._status_bar_enabled)
    self.chat_submenu.set_active(self._chat_open)
    self.context_menu.item_selected.connect(self._on_menu_selected)
    self.pin_submenu.item_selected.connect(self._on_pin_submenu_item_and_dismiss)
    self.hover_submenu.item_selected.connect(self._on_hover_submenu_item_and_dismiss)
    self.status_submenu.item_selected.connect(self._on_status_submenu_item_and_dismiss)
    self.chat_submenu.item_selected.connect(self._on_chat_submenu_item_and_dismiss)
    self.arc_menu.picked.connect(self._on_arc_motion_picked)
    self._arc_hide_filter = _ArcMenuHideFilter(self)
    self.arc_menu.installEventFilter(self._arc_hide_filter)
    self._chat_stream = ChatStreamBridge()
    self._chat_stream.chunk_received.connect(self._append_chat_chunk)
    _apply_desktop_overlays(self)

  def _append_chat_chunk(self, ch: str) -> None:
    if self.chat_bubble is None or not self._chat_open:
      return
    self._layout_bubbles(chat_text=self.chat_bubble.text + ch)

  def _stream_ui_callback(self, ch: str) -> None:
    if self._chat_stream is not None:
      self._chat_stream.chunk_received.emit(ch)

  def _chat_greeting(self) -> str:
    name = self._active_character_name()
    return f"你好呀！我是{name}，有什么可以帮我的吗？"

  def _active_character_name(self) -> str:
    if self._active_pet:
      if is_mao_pro_zh_model(str(self._active_pet.get("model_path") or self.model_path)):
        return MAO_PRO_ZH_DISPLAY
      return str(self._active_pet.get("name") or self._active_pet.get("id") or "默认")
    if is_mao_pro_zh_model(self.model_path):
      return MAO_PRO_ZH_DISPLAY
    return "默认"

  def _head_center(self) -> tuple[int, int]:
    return (self._win_w // 2, max(40, self._win_h // 2 - HEAD_CENTER_Y_OFFSET))

  def _character_layout(self) -> tuple[int, int, int]:
    """返回 (center_x, head_top_y, body_bottom_y)。"""
    cx = self._win_w // 2
    head_y = max(40, self._win_h // 2 - HEAD_CENTER_Y_OFFSET)
    body_bottom = min(self._win_h - 8, int(self._win_h * 0.82))
    if self._is_flat_mode():
      player = self._plane_player()
      if player and not player._pixmap_rect.isEmpty():
        rect = player._pixmap_rect
        cx = rect.center().x()
        head_y = max(8, rect.top())
        body_bottom = min(self._win_h - 8, rect.bottom())
    return cx, head_y, body_bottom

  def _layout_bubbles(self, chat_text: str | None = None) -> None:
    """AI 对话气泡在头顶正上方；输入框在角色正下方；状态栏在头顶左上方。"""
    if self._window is None:
      return
    cx, head_y, body_bottom = self._character_layout()
    margin = 8
    gap = 10

    status_on = bool(self._status_bar_enabled and self.info_bubble)
    chat_on = bool(self._chat_open and self.chat_bubble)

    if self._chat_open and self.input_box:
      ix = max(margin, min(cx - self.input_box.WIDTH // 2, self._win_w - self.input_box.WIDTH - margin))
      iy = min(self._win_h - self.input_box.HEIGHT - margin, body_bottom + gap)
      self.input_box.show(ix, iy)

    status_rect: QRect | None = None
    if status_on:
      self.info_bubble.show(0, 0)
      sw, sh = self.info_bubble.width(), self.info_bubble.height()
      sx = max(margin, cx - sw - 28)
      sy = max(margin, head_y - sh - gap)
      self.info_bubble.move(sx, sy)
      status_rect = QRect(sx, sy, sw, sh)

    chat_rect: QRect | None = None
    if chat_on:
      text = chat_text if chat_text is not None else self.chat_bubble.text
      self.chat_bubble.show(0, 0, text)
      cw, ch = self.chat_bubble.width(), self.chat_bubble.height()
      chat_x = max(margin, min(cx - cw // 2, self._win_w - cw - margin))
      chat_y = max(margin, head_y - ch - gap)
      self.chat_bubble.move(chat_x, chat_y)
      chat_rect = QRect(chat_x, chat_y, cw, ch)

      if status_rect and status_rect.intersects(chat_rect):
        chat_y = max(margin, status_rect.top() - ch - gap)
        self.chat_bubble.move(chat_x, chat_y)
        chat_rect = QRect(chat_x, chat_y, cw, ch)
      if status_rect and status_rect.intersects(chat_rect):
        sx = max(margin, chat_rect.left() - status_rect.width() - gap)
        self.info_bubble.move(sx, status_rect.y())
        status_rect = QRect(sx, status_rect.y(), status_rect.width(), status_rect.height())

    char_box = QRect(cx - 80, head_y, 160, max(40, body_bottom - head_y + 8))
    for rect, widget in (
      (chat_rect, self.chat_bubble if chat_on else None),
      (status_rect, self.info_bubble if status_on else None),
    ):
      if rect is None or widget is None:
        continue
      if char_box.intersects(rect):
        new_y = max(margin, head_y - rect.height() - gap)
        widget.move(rect.x(), new_y)

  def _save_chat_message(self, role: str, text: str) -> None:
    name = self._active_character_name()
    msgs = self._chat_history.load(name)
    msgs.append((role, text))
    self._chat_history.save(name, msgs)
    if self._console:
      self._console.append_chat_message(name, role, text)

  def _edge_zone(self, pos: tuple[int, int]) -> bool:
    margin = 10
    x, y = pos
    on_edge = (
      x <= margin or y <= margin or x >= self._win_w - margin or y >= self._win_h - margin
    )
    return on_edge and not self._is_mouse_on_body(pos)

  def _show_resize_overlay(self) -> None:
    if self._window and hasattr(self._window, "_resize_overlay"):
      self._resize_visible = True
      self._window._resize_overlay.show_overlay()

  def _hide_resize_overlay(self) -> None:
    self._resize_visible = False
    if self._window and hasattr(self._window, "_resize_overlay"):
      self._window._resize_overlay.hide_overlay()

  def _begin_corner_resize(self, corner: str, global_pos: QPoint) -> None:
    self._resizing_corner = corner
    self._resize_start_global = global_pos
    self._resize_start_size = (self._win_w, self._win_h)

  def _apply_window_size(self, w: int, h: int) -> None:
    w = max(220, w)
    h = max(280, h)
    self._win_w, self._win_h = w, h
    if self._window:
      self._window.setGeometry(self._window.x(), self._window.y(), w, h)
      if self._is_flat_mode():
        player = self._plane_player()
        if player:
          player.set_pet(self._active_pet or {}, w, h)
      elif self._model:
        self._model.Resize(w, h)
    if self._resize_visible and self._window and hasattr(self._window, "_resize_overlay"):
      self._window._resize_overlay.setGeometry(0, 0, w, h)
    if self._status_bar_enabled or self._chat_open:
      self._layout_bubbles()

  def _scale_window(self, factor: float) -> None:
    if factor <= 0:
      return
    new_w = int(self._win_w * factor)
    new_h = int(new_w / self._aspect_ratio)
    self._apply_window_size(new_w, new_h)

  def _on_pin_submenu_item_and_dismiss(self, choice: str) -> None:
    self._on_pin_submenu_item(choice)
    self._dismiss_menus()

  def _on_hover_submenu_item_and_dismiss(self, choice: str) -> None:
    self._on_hover_submenu_item(choice)
    self._dismiss_menus()

  def _on_status_submenu_item_and_dismiss(self, choice: str) -> None:
    self._on_status_submenu_item(choice)
    self._dismiss_menus()

  def _on_chat_submenu_item_and_dismiss(self, choice: str) -> None:
    self._on_chat_submenu_item(choice)
    self._dismiss_menus()

  def _set_window_click_through(self, enabled: bool) -> None:
    if not win32gui or not self._hwnd:
      return
    try:
      style = win32gui.GetWindowLong(self._hwnd, win32con.GWL_EXSTYLE)
      if enabled:
        style |= win32con.WS_EX_LAYERED | win32con.WS_EX_TRANSPARENT
      else:
        style &= ~win32con.WS_EX_TRANSPARENT
      win32gui.SetWindowLong(self._hwnd, win32con.GWL_EXSTYLE, style)
    except Exception:
      pass

  def close(self) -> None:
    self._running = False
    if self._timer:
      self._timer.stop()
    self._model = None
    try:
      live2d.glRelease()
    except Exception:
      pass
    try:
      live2d.dispose()
    except Exception:
      pass

  def _tick(self) -> None:
    if not self._running:
      return
    mx, my = self._local_mouse_pos()
    if self._is_flat_mode():
      player = self._plane_player()
      if player:
        player.tick()
      if not self._dragging:
        self._update_hover_alpha((mx, my))
    else:
      if self._model is None:
        return
      self._update_gaze(mx, my)
      if not self._dragging:
        self._update_hover_alpha((mx, my))
      self._model.Update()
      if self._window and self._window._gl:
        self._window._gl.update()
    if self.arc_menu:
      self.arc_menu.tick(1.0 / 60.0)

  def _update_gaze(self, mx: int, my: int) -> None:
    """窗口全域视线：x -> angleX [-30,30]，y -> angleY [-20,20]，每帧 Drag。"""
    if self._model is None or self._win_w <= 0 or self._win_h <= 0:
      return
    cx = max(0, min(self._win_w, mx))
    cy = max(0, min(self._win_h, my))
    ratio_x = cx / self._win_w
    ratio_y = cy / self._win_h
    _angle_x = ANGLE_X_MIN + ratio_x * (ANGLE_X_MAX - ANGLE_X_MIN)
    _angle_y = ANGLE_Y_MIN + ratio_y * (ANGLE_Y_MAX - ANGLE_Y_MIN)
    drag_x = int(((_angle_x - ANGLE_X_MIN) / (ANGLE_X_MAX - ANGLE_X_MIN)) * self._win_w)
    drag_y = int(((_angle_y - ANGLE_Y_MIN) / (ANGLE_Y_MAX - ANGLE_Y_MIN)) * self._win_h)
    self._model.Drag(drag_x, drag_y)

  def _local_mouse_pos(self) -> tuple[int, int]:
    if self._window is None:
      return 0, 0
    pt = self._window.mapFromGlobal(QCursor.pos())
    return int(pt.x()), int(pt.y())

  def _to_global(self, pos: tuple[int, int]) -> tuple[int, int]:
    if self._window is None:
      return pos
    gp = self._window.mapToGlobal(QPoint(*pos))
    return gp.x(), gp.y()

  def _init_model_gl(self) -> None:
    self._model = live2d.LAppModel()
    self._model.LoadModelJson(self.model_path, maskBufferCount=2)
    self._model.Resize(self._win_w, self._win_h)
    self._build_motion_index()
    self._load_available_motions()
    self._start_idle_motion()

  def _capture_mao_pro_motion_preview(self) -> None:
    """mao_pro_zh：从首个 motion3 首帧生成预览图。"""
    if not is_mao_pro_zh_model(self.model_path) or self._model is None:
      return
    runtime = os.path.dirname(os.path.abspath(self.model_path))
    cache = os.path.join(runtime, "_preview_first_motion.png")
    if os.path.isfile(cache):
      return
    motions_dir = os.path.join(runtime, "motions")
    if not os.path.isdir(motions_dir):
      return
    first_stem = ""
    for fname in sorted(os.listdir(motions_dir)):
      if fname.lower().endswith(".motion3.json"):
        first_stem = fname[: -len(".motion3.json")]
        break
    if not first_stem:
      return
    group, index = self._resolve_motion(first_stem)
    if group is None:
      return

    def _grab() -> None:
      if self._model is None or self._window is None:
        return
      self._model.Update()
      self._window._gl.update()
      QApplication.processEvents()
      pix = self._window._gl.grabFramebuffer()
      if pix.isNull():
        return
      try:
        pix.save(cache)
        print(f"[DesktopPet] mao_pro 预览图已保存: {cache}")
      except OSError as exc:
        print(f"[DesktopPet] 保存 mao_pro 预览图失败: {exc}")
      self._start_idle_motion()

    try:
      self._model.StartMotion(group, index, MotionPriority.IDLE)
      self._model.Update()
    except Exception as exc:
      print(f"[DesktopPet] mao_pro 预览动作启动失败: {exc}")
      return
    QTimer.singleShot(180, _grab)

  def _init_win32_window(self, hwnd: int) -> None:
    if win32gui is None:
      return
    try:
      self._hwnd = hwnd
      ex_style = win32gui.GetWindowLong(self._hwnd, win32con.GWL_EXSTYLE)
      ex_style |= win32con.WS_EX_LAYERED
      ex_style &= ~win32con.WS_EX_TRANSPARENT
      win32gui.SetWindowLong(
        self._hwnd,
        win32con.GWL_EXSTYLE,
        ex_style,
      )
      win32gui.SetLayeredWindowAttributes(
        self._hwnd,
        WIN32_TRANSPARENT_COLORKEY,
        255,
        win32con.LWA_COLORKEY | win32con.LWA_ALPHA,
      )
    except Exception as exc:
      print(f"[DesktopPet] Win32 窗口初始化失败: {exc}")

  def _apply_window_opacity(self, alpha: int) -> None:
    self._window_alpha = max(0, min(255, alpha))
    if not win32gui or not self._hwnd:
      return
    try:
      win32gui.SetLayeredWindowAttributes(
        self._hwnd,
        WIN32_TRANSPARENT_COLORKEY,
        self._window_alpha,
        win32con.LWA_COLORKEY | win32con.LWA_ALPHA,
      )
    except Exception:
      pass

  def _is_cursor_over_window(self) -> bool:
    if self._window is None:
      return False
    gp = QCursor.pos()
    return self._window.frameGeometry().contains(gp)

  def _update_hover_alpha(self, mouse_pos: tuple[int, int]) -> None:
    if not self._hover_fade_enabled:
      if self._hovering_window:
        self._hovering_window = False
        self._apply_window_opacity(255)
      self._update_mouse_passthrough(mouse_pos)
      return
    over = self._is_cursor_over_window()
    if over != self._hovering_window:
      self._hovering_window = over
      self._apply_window_opacity(HOVER_FADE_ALPHA if over else 255)
    self._update_mouse_passthrough(mouse_pos)

  def _update_mouse_passthrough(self, mouse_pos: tuple[int, int]) -> None:
    """悬停淡出开启时：透明区域穿透；关闭时：完全不穿透。"""
    if self._any_menu_open() or self._chat_open or self._resize_visible:
      self._set_window_click_through(False)
      self._set_gl_mouse_passthrough(True)
      return
    if self._dragging or self._resizing_corner:
      self._set_window_click_through(False)
      self._set_gl_mouse_passthrough(False)
      return
    if not self._hover_fade_enabled:
      self._set_window_click_through(False)
      self._set_gl_mouse_passthrough(False)
      return
    on_body = self._is_mouse_on_body(mouse_pos)
    on_ui = self._point_on_ui(mouse_pos)
    self._set_gl_mouse_passthrough(not on_body)
    self._set_window_click_through(not on_body and not on_ui)

  def _set_gl_mouse_passthrough(self, enabled: bool) -> None:
    if self._window and self._window._gl:
      self._window._gl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, enabled)

  def _set_window_alpha(self, alpha: int) -> None:
    self._apply_window_opacity(alpha)

  def _is_mouse_on_body(self, mouse_pos: tuple[int, int]) -> bool:
    if self._is_flat_mode():
      player = self._plane_player()
      if player:
        return player.hit_test(mouse_pos)
      return True
    if self._model is None:
      return False
    x, y = mouse_pos
    return bool(self._model.HitTest("HitAreaBody", x, y))

  def _load_settings(self) -> None:
    defaults = {"pin_top": True, "hover_fade": True, "status_bar": False}
    try:
      with open(SETTINGS_PATH, encoding="utf-8") as f:
        data = json.load(f)
      self._pin_top = bool(data.get("pin_top", defaults["pin_top"]))
      self._hover_fade_enabled = bool(data.get("hover_fade", defaults["hover_fade"]))
      self._status_bar_enabled = bool(data.get("status_bar", defaults["status_bar"]))
    except (OSError, json.JSONDecodeError, TypeError):
      self._pin_top = defaults["pin_top"]
      self._hover_fade_enabled = defaults["hover_fade"]
      self._status_bar_enabled = defaults["status_bar"]

  def _save_settings(self) -> None:
    data = {
      "pin_top": self._pin_top,
      "hover_fade": self._hover_fade_enabled,
      "status_bar": self._status_bar_enabled,
    }
    try:
      os.makedirs(_SETTINGS_DIR, exist_ok=True)
      with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    except OSError as exc:
      print(f"[DesktopPet] 保存设置失败: {exc}")

  def _set_pin_top(self, enabled: bool) -> None:
    self._pin_top = enabled
    if win32gui and self._hwnd:
      flag = win32con.HWND_TOPMOST if enabled else win32con.HWND_NOTOPMOST
      try:
        win32gui.SetWindowPos(
          self._hwnd,
          flag,
          0,
          0,
          0,
          0,
          win32con.SWP_NOMOVE | win32con.SWP_NOSIZE | win32con.SWP_SHOWWINDOW,
        )
      except Exception:
        pass
    elif self._window:
      if enabled:
        self._window.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
      else:
        self._window.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, False)
      self._window.show()
    if self.pin_submenu:
      self.pin_submenu.set_active(enabled)
    self._save_settings()

  def _set_hover_fade(self, enabled: bool) -> None:
    self._hover_fade_enabled = enabled
    if self.hover_submenu:
      self.hover_submenu.set_active(enabled)
    if not enabled:
      self._hovering_window = False
      self._apply_window_opacity(255)
      self._set_window_click_through(False)
      self._set_gl_mouse_passthrough(False)
    else:
      self._update_hover_alpha(self._local_mouse_pos())
    self._save_settings()

  def _set_status_bar(self, enabled: bool) -> None:
    self._status_bar_enabled = enabled
    if self.status_submenu:
      self.status_submenu.set_active(enabled)
    if not enabled and self.info_bubble:
      self.info_bubble.hide()
    self._layout_bubbles()
    self._save_settings()

  def _set_chat_open(self, enabled: bool) -> None:
    self._chat_open = enabled
    if self.chat_submenu:
      self.chat_submenu.set_active(enabled)
    if enabled:
      if self.input_box:
        self.input_box.set_text("")
      self._layout_bubbles(chat_text=self._chat_greeting())
    else:
      if self.chat_bubble:
        self.chat_bubble.hide()
      if self.input_box:
        self.input_box.hide()
      self._layout_bubbles()
    self._update_mouse_passthrough(self._local_mouse_pos())
    self._save_settings()

  def _screen_pos(self) -> tuple[int, int]:
    if win32gui is not None:
      return win32gui.GetCursorPos()
    pos = QCursor.pos()
    return pos.x(), pos.y()

  def _move_window(self, screen_x: int, screen_y: int) -> None:
    if self._window is None:
      return
    dx = screen_x - self._drag_start_screen[0]
    dy = screen_y - self._drag_start_screen[1]
    self._window.move(self._drag_start_win[0] + dx, self._drag_start_win[1] + dy)

  def _on_mouse_move(self, pos: tuple[float, float]) -> None:
    ipos = (int(pos[0]), int(pos[1]))
    if self._resizing_corner and self._resize_start_global is not None:
      gp = QCursor.pos()
      dx = gp.x() - self._resize_start_global.x()
      dy = gp.y() - self._resize_start_global.y()
      delta = max(dx, dy) if self._resizing_corner in ("br", "tr") else max(-dx, -dy)
      sign = 1 if self._resizing_corner in ("br", "tr", "bl") else -1
      base_w = self._resize_start_size[0]
      new_w = max(220, base_w + sign * delta)
      new_h = int(new_w / self._aspect_ratio)
      self._apply_window_size(new_w, new_h)
      return
    if self.context_menu and self.context_menu.visible:
      self.context_menu.update_hover(ipos)
    if self.pin_submenu and self.pin_submenu.visible:
      self.pin_submenu.update_hover(ipos)
    if self.hover_submenu and self.hover_submenu.visible:
      self.hover_submenu.update_hover(ipos)
    if self.status_submenu and self.status_submenu.visible:
      self.status_submenu.update_hover(ipos)
    if self.chat_submenu and self.chat_submenu.visible:
      self.chat_submenu.update_hover(ipos)
    if self.arc_menu and self.arc_menu.visible:
      self.arc_menu.update(self._to_global(ipos))
    if self._dragging:
      dx = ipos[0] - self._click_start[0]
      dy = ipos[1] - self._click_start[1]
      if abs(dx) > DRAG_THRESHOLD or abs(dy) > DRAG_THRESHOLD:
        self._click_moved = True
      if self._click_moved:
        sx, sy = self._screen_pos()
        self._move_window(sx, sy)
        return

  def _point_on_ui(self, pos: tuple[int, int]) -> bool:
    if self.context_menu and self.context_menu.visible and self.context_menu.rect.contains(QPoint(*pos)):
      return True
    if self.pin_submenu and self.pin_submenu.visible and self.pin_submenu.rect.contains(QPoint(*pos)):
      return True
    if self.hover_submenu and self.hover_submenu.visible and self.hover_submenu.rect.contains(QPoint(*pos)):
      return True
    if self.status_submenu and self.status_submenu.visible and self.status_submenu.rect.contains(QPoint(*pos)):
      return True
    if self.chat_submenu and self.chat_submenu.visible and self.chat_submenu.rect.contains(QPoint(*pos)):
      return True
    if self.info_bubble.visible and self.info_bubble.rect.contains(QPoint(*pos)):
      return True
    if self._chat_open:
      if self.chat_bubble.visible and self.chat_bubble.rect.contains(QPoint(*pos)):
        return True
      if self.input_box.visible and self.input_box.rect.contains(QPoint(*pos)):
        return True
    if self.arc_menu and self.arc_menu.visible:
      gpos = self._to_global(pos)
      lp = self.arc_menu.mapFromGlobal(QPoint(*gpos))
      if self.arc_menu.hit_region().contains(lp):
        return True
    return False

  def _on_left_press(self, pos: tuple[int, int]) -> None:
    if self._any_menu_open():
      self._on_window_left_press(pos)
      if self._point_on_ui(pos):
        return
    if self._point_on_ui(pos):
      return
    if self._edge_zone(pos):
      self._edge_hold_timer.start(450)
    self._click_start = pos
    self._click_moved = False
    self._dragging = True
    self._drag_start_screen = self._screen_pos()
    if self._window:
      self._drag_start_win = (self._window.x(), self._window.y())
    else:
      self._drag_start_win = tuple(self.position)

  def _on_left_release(self, pos: tuple[int, int]) -> None:
    self._edge_hold_timer.stop()
    if self._resizing_corner:
      self._resizing_corner = None
      self._resize_start_global = None
      self._hide_resize_overlay()
      self._dragging = False
      return
    was_drag = self._dragging and self._click_moved
    self._dragging = False
    if self._any_menu_open():
      return
    if self._ui_consumes_click(pos):
      return
    if not was_drag and not self._click_moved:
      self.on_click(pos[0], pos[1])

  def _ui_consumes_click(self, pos: tuple[int, int]) -> bool:
    if self.info_bubble.visible and not self.info_bubble.rect.contains(QPoint(*pos)):
      self.info_bubble.hide()
      return True

    if self.pin_submenu and self.pin_submenu.visible:
      choice = self.pin_submenu.handle_click(pos)
      if choice == "开始置顶":
        self._set_pin_top(True)
      elif choice == "关闭置顶":
        self._set_pin_top(False)
      if choice:
        self._dismiss_menus()
        return True
      if self.pin_submenu.rect.contains(QPoint(*pos)):
        return True
      self.pin_submenu.hide()

    if self.hover_submenu and self.hover_submenu.visible:
      choice = self.hover_submenu.handle_click(pos)
      if choice == "开启":
        self._set_hover_fade(True)
      elif choice == "关闭":
        self._set_hover_fade(False)
      if choice:
        self._dismiss_menus()
        return True
      if self.hover_submenu.rect.contains(QPoint(*pos)):
        return True
      self.hover_submenu.hide()

    if self.status_submenu and self.status_submenu.visible:
      choice = self.status_submenu.handle_click(pos)
      if choice == "开启状态栏":
        self._set_status_bar(True)
      elif choice == "关闭状态栏":
        self._set_status_bar(False)
      if choice:
        self._dismiss_menus()
        return True
      if self.status_submenu.rect.contains(QPoint(*pos)):
        return True
      self.status_submenu.hide()

    if self.chat_submenu and self.chat_submenu.visible:
      choice = self.chat_submenu.handle_click(pos)
      if choice == "开启AI对话":
        self._set_chat_open(True)
      elif choice == "关闭AI对话":
        self._set_chat_open(False)
      if choice:
        self._dismiss_menus()
        return True
      if self.chat_submenu.rect.contains(QPoint(*pos)):
        return True
      self.chat_submenu.hide()

    if self.arc_menu and self.arc_menu.visible:
      picked = self.arc_menu.handle_click(self._to_global(pos))
      if picked:
        self._on_arc_motion_picked(picked)
        return True
      self._close_arc_menu()
      return False

    if self.context_menu and self.context_menu.visible:
      selected = self.context_menu.handle_click(pos)
      if selected:
        self._on_menu_selected(selected, pos)
        return True
      self.context_menu.hide()
      return False

    return False

  def _any_menu_open(self) -> bool:
    return bool(
      (self.context_menu and self.context_menu.visible)
      or (self.pin_submenu and self.pin_submenu.visible)
      or (self.hover_submenu and self.hover_submenu.visible)
      or (self.status_submenu and self.status_submenu.visible)
      or (self.chat_submenu and self.chat_submenu.visible)
      or (self.arc_menu and self.arc_menu.visible)
    )

  def _restore_window_focus(self) -> None:
    if self._window is None:
      return
    self._window.activateWindow()
    self._window.raise_()
    self._window.setFocus()
    if not self._is_flat_mode() and self._window._gl:
      self._window._gl.setFocus()
    self._update_mouse_passthrough(self._local_mouse_pos())

  def _dismiss_menus(self) -> None:
    if self.context_menu:
      self.context_menu.hide()
    if self.pin_submenu:
      self.pin_submenu.hide()
    if self.hover_submenu:
      self.hover_submenu.hide()
    if self.status_submenu:
      self.status_submenu.hide()
    if self.chat_submenu:
      self.chat_submenu.hide()
    if self.arc_menu:
      self.arc_menu.hide()
    self._restore_window_focus()

  def _close_arc_menu(self) -> None:
    if self.arc_menu:
      self.arc_menu.hide()
    self._restore_window_focus()

  def _show_submenu_adjacent(self, submenu: SubMenu, item_rect) -> None:
    gap = 4
    x_right = item_rect.right() + gap
    x_left = item_rect.left() - submenu.WIDTH - gap
    y = item_rect.y()
    x = x_right
    if item_rect.right() + submenu.WIDTH + gap > self._win_w:
      x = x_left
    if self._window:
      global_right = self._window.mapToGlobal(QPoint(item_rect.right(), y)).x()
      screen = QApplication.primaryScreen()
      if screen and global_right + submenu.WIDTH + gap > screen.availableGeometry().right():
        x = x_left
    if x < 0:
      x = max(0, min(x_left, self._win_w - submenu.WIDTH))
    submenu.show(x, y)
    submenu.raise_()
    self._set_gl_mouse_passthrough(True)

  def _on_window_left_press(self, pos: tuple[int, int]) -> None:
    if not self._any_menu_open():
      return
    if not self._point_on_ui(pos):
      self._dismiss_menus()

  def _on_pin_submenu_item(self, choice: str) -> None:
    if choice == "开始置顶":
      self._set_pin_top(True)
    elif choice == "关闭置顶":
      self._set_pin_top(False)

  def _on_hover_submenu_item(self, choice: str) -> None:
    if choice == "开启":
      self._set_hover_fade(True)
    elif choice == "关闭":
      self._set_hover_fade(False)

  def _on_status_submenu_item(self, choice: str) -> None:
    if choice == "开启状态栏":
      self._set_status_bar(True)
    elif choice == "关闭状态栏":
      self._set_status_bar(False)

  def _on_chat_submenu_item(self, choice: str) -> None:
    if choice == "开启AI对话":
      self._set_chat_open(True)
    elif choice == "关闭AI对话":
      self._set_chat_open(False)

  def _on_arc_motion_picked(self, item: dict) -> None:
    motion = str(item.get("value", ""))
    label = str(item.get("label", motion))
    print(f"[DesktopPet] 播放动作: {label} ({motion})")
    self.play_motion(motion)
    self._close_arc_menu()

  def _open_context_menu(self, pos: tuple[int, int]) -> None:
    if not self.context_menu:
      return
    self._set_window_click_through(False)
    if self.context_menu.visible and not self.context_menu.rect.contains(QPoint(*pos)):
      self._dismiss_menus()
    self.pin_submenu.hide()
    self.hover_submenu.hide()
    self.status_submenu.hide()
    self.chat_submenu.hide()
    self._close_arc_menu()
    menu_h = self.context_menu.PADDING * 2 + len(RightClickMenu.ITEMS) * self.context_menu.ITEM_HEIGHT
    mx = max(0, min(pos[0], self._win_w - self.context_menu.WIDTH - 4))
    my = max(0, min(pos[1], self._win_h - menu_h - 4))
    self.context_menu.show(mx, my)
    self.context_menu.raise_()
    if self._window:
      self._lower_character_layer()
      self._window.setFocus()
    self._set_gl_mouse_passthrough(True)
    self._update_mouse_passthrough(pos)

  def _on_arc_menu_hidden(self) -> None:
    if not self._any_menu_open():
      self._restore_window_focus()

  def _on_menu_selected(self, item: str, pos: tuple[int, int] = (0, 0)) -> None:
    if item in ("置顶设置", "悬停淡出", "状态栏", "AI对话"):
      self.pin_submenu.hide()
      self.hover_submenu.hide()
      self.status_submenu.hide()
      self.chat_submenu.hide()
    else:
      self.pin_submenu.hide()
      self.hover_submenu.hide()
      self.status_submenu.hide()
      self.chat_submenu.hide()

    if item == "置顶设置":
      pin_idx = RightClickMenu.ITEMS.index("置顶设置")
      item_r = self.context_menu.item_rect(pin_idx)
      self.pin_submenu.set_active(self._pin_top)
      self._show_submenu_adjacent(self.pin_submenu, item_r)
      return
    if item == "悬停淡出":
      fade_idx = RightClickMenu.ITEMS.index("悬停淡出")
      item_r = self.context_menu.item_rect(fade_idx)
      self.hover_submenu.set_active(self._hover_fade_enabled)
      self._show_submenu_adjacent(self.hover_submenu, item_r)
      return
    if item == "状态栏":
      status_idx = RightClickMenu.ITEMS.index("状态栏")
      item_r = self.context_menu.item_rect(status_idx)
      self.status_submenu.set_active(self._status_bar_enabled)
      self._show_submenu_adjacent(self.status_submenu, item_r)
      return
    if item == "AI对话":
      chat_idx = RightClickMenu.ITEMS.index("AI对话")
      item_r = self.context_menu.item_rect(chat_idx)
      self.chat_submenu.set_active(self._chat_open)
      self._show_submenu_adjacent(self.chat_submenu, item_r)
      return

    self._dismiss_menus()

    if item == "设置面板":
      self._open_settings_panel()
    elif item == "动作展示":
      center = self._head_center()
      items = self._current_arc_motion_items()
      if not items:
        print("[DesktopPet] 当前角色没有可用动作")
        return
      self.arc_menu.show(center[0], center[1], items)
      self.arc_menu.raise_()
      if self._window:
        self._lower_character_layer()
        self._window.setFocus()
      self._set_gl_mouse_passthrough(True)
    elif item == "待机":
      if self._is_flat_mode():
        player = self._plane_player()
        if player:
          player.show_idle()
      else:
        self.play_model_motion("Idle")
    elif item == "退出":
      self._running = False
      if self._app:
        self._app.quit()
    elif item == "关闭":
      pass

  def _open_settings_panel(self) -> None:
    self.arc_menu.hide()
    self.info_bubble.hide()
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    console = PetControlConsole(
      desktop_pet=self,
      project_root=project_root,
      model_path=self.model_path,
      available_motions=self.available_motions,
      motion_name_map=self.motion_name_map,
    )
    self._console = console
    _apply_control_console_theme(console)
    console.run()
    self._console = None

  def _open_chat(self) -> None:
    self._set_chat_open(True)

  def _toggle_chat(self) -> None:
    self._set_chat_open(not self._chat_open)

  def _submit_chat(self, text: str | None = None) -> None:
    msg = text if text is not None else self.input_box.get_text()
    if not msg or not str(msg).strip():
      return
    if not self._chat_open:
      self._set_chat_open(True)
    self._save_chat_message("user", str(msg).strip())
    self._layout_bubbles(chat_text="")
    self.input_box.set_text("")
    self.team_c.api_user_speak(
      str(msg).strip(),
      {"state_code": "normal"},
      self._stream_ui_callback,
    )
    QTimer.singleShot(2500, self._save_ai_reply_from_bubble)

  def _save_ai_reply_from_bubble(self) -> None:
    if self.chat_bubble and self.chat_bubble.text.strip():
      self._save_chat_message("ai", self.chat_bubble.text.strip())

  def _start_idle_motion(self, *_args: Any) -> None:
    if self._model is None:
      return
    self._model.StartMotion("Idle", 0, MotionPriority.IDLE, onFinishMotionHandler=self._start_idle_motion)

  def _build_motion_index(self) -> None:
    self._motion_index.clear()
    try:
      with open(self.model_path, encoding="utf-8") as f:
        data = json.load(f)
      motion_groups = data.get("FileReferences", {}).get("Motions", {})
    except (OSError, json.JSONDecodeError) as exc:
      print(f"[DesktopPet] 读取动作配置失败: {exc}")
      self._motion_index["idle"] = ("Idle", 0)
      return
    for group, entries in motion_groups.items():
      group_key = group.lower() if group else "default"
      if group:
        self._motion_index[group.lower()] = (group, 0)
      else:
        self._motion_index["default"] = ("", 0)
      for idx, entry in enumerate(entries):
        file_path = entry.get("File", "")
        stem = self._motion_stem_from_path(file_path).lower()
        self._motion_index[stem] = (group, idx)
        self._motion_index[f"{group_key}:{idx}"] = (group, idx)

  @staticmethod
  def _motion_stem_from_path(file_path: str) -> str:
    base = os.path.basename(file_path)
    if base.endswith(".motion3.json"):
      return base[: -len(".motion3.json")]
    return os.path.splitext(base)[0]

  def _motions_dir(self) -> str:
    return os.path.join(os.path.dirname(self.model_path), "motions")

  def _scan_motions_from_folder(self) -> list[str]:
    motions_dir = self._motions_dir()
    if not os.path.isdir(motions_dir):
      return []
    return sorted(
      f[: -len(".motion3.json")]
      for f in os.listdir(motions_dir)
      if f.endswith(".motion3.json")
    )

  def _scan_motions_from_model_json(self) -> list[str]:
    names: list[str] = []
    try:
      with open(self.model_path, encoding="utf-8") as f:
        data = json.load(f)
      motion_groups = data.get("FileReferences", {}).get("Motions", {})
    except (OSError, json.JSONDecodeError):
      return names
    for _group, entries in motion_groups.items():
      for entry in entries:
        stem = self._motion_stem_from_path(entry.get("File", ""))
        if stem and stem not in names:
          names.append(stem)
    return names

  def _load_available_motions(self) -> None:
    motions = self._scan_motions_from_folder()
    if not motions:
      motions = self._scan_motions_from_model_json()
    self.available_motions = motions

  def _resolve_motion(self, motion_name: str) -> tuple[Optional[str], int]:
    key = motion_name.strip().lower()
    if key in self._motion_index:
      return self._motion_index[key]
    direct = motion_name.strip()
    if direct.lower() in self._motion_index:
      return self._motion_index[direct.lower()]
    if ":" in key:
      group_part, _, idx_part = key.partition(":")
      if group_part in self._motion_index:
        base_group, _ = self._motion_index[group_part]
        try:
          return base_group, int(idx_part)
        except ValueError:
          pass
    return None, 0


def main() -> None:
  pet = DesktopPet()
  pet.run()


if __name__ == "__main__":
  main()
