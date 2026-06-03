"""
Live2D 桌宠动画播放器（PySide6 + live2d-py）
"""
from __future__ import annotations

import json
import inspect
import os
import random
import re
import sys
import threading
import time
from typing import Any, Callable, Optional

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, PROJECT_ROOT)

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
    DEFAULT_TTS_UI_SETTINGS,
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
    normalize_tts_settings,
    scan_flat_pets,
)
from models.vision.computer_activity_detector import (
    ComputerActivityDetector,
    build_activity_suggestion,
    build_companion_event,
    build_local_companion_comment,
)
from app.ui.ui_settings_store import load_ui_settings
from app.ui.feedback_bubble import show_feedback_message
from models.state.user_profile import UserProfile
from utils.config import config
from app.model_switcher import reload_live2d_model

try:
    import win32api
    import win32con
    import win32gui
except ImportError:
    win32api = None  # type: ignore
    win32gui = None  # type: ignore
    win32con = None  # type: ignore

MODEL_PATH = os.path.join(
    PROJECT_ROOT,
    "assets",
    "models",
    "mao_pro_zh",
    "mao_pro_zh",
    "runtime",
    "mao_pro.model3.json",
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
    PROJECT_ROOT,
    "data",
)
SETTINGS_PATH = os.path.join(_SETTINGS_DIR, "pet_ui_settings.json")

ACTION_MAPPING_PATH = os.path.join(PROJECT_ROOT, "assets", "action_mapping.json")
PET_MEMORY_PATH = os.path.join(PROJECT_ROOT, "assets", "pet_memory.json")
SYNONYMS_PATH = os.path.join(PROJECT_ROOT, "assets", "synonyms.json")
BASE_WINDOW_W = 450
BASE_WINDOW_H = 600
MIN_ACTION_PLAY_MS = 1500
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


def _config_bool(key: str, default: bool = False) -> bool:
  value = config.get(key, str(default).lower())
  return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


def _config_float(key: str, default: float) -> float:
  try:
    return float(config.get(key, default))
  except (TypeError, ValueError):
    return float(default)


def _config_int(key: str, default: int) -> int:
  try:
    return int(float(config.get(key, default)))
  except (TypeError, ValueError):
    return int(default)


def _setting_bool(value: Any, default: bool = False) -> bool:
  if value is None:
    return default
  if isinstance(value, str):
    text = value.strip().lower()
    if text in {"1", "true", "yes", "y", "on", "开启", "允许", "记住"}:
      return True
    if text in {"0", "false", "no", "n", "off", "关闭", "禁止"}:
      return False
    return default
  return bool(value)


def _setting_float(value: Any, default: float) -> float:
  try:
    return float(value)
  except (TypeError, ValueError):
    return float(default)


# ---------------------------------------------------------------------------
# 队员 C / D 接口（Mock + 真实实现自动切换）
# ---------------------------------------------------------------------------


class MockTeamC:
  """队员 C Mock：模拟逐字输出与系统语音。"""

  def __init__(self) -> None:
    self._logic_callback: Callable[[dict[str, Any]], None] | None = None
    self.pet_id = ""
    self.voice_pack_id = ""
    self.tts_settings: dict[str, Any] = {}

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

  def api_play_system_voice(
    self,
    text: str,
    state: str = "neutral",
    action: str = "speak",
    current_state: dict[str, Any] | None = None,
  ) -> None:
    print(f"[MockTeamC] api_play_system_voice: {text} (state={state}, action={action})")

  def api_read_long_text(
    self,
    text: str,
    current_state: dict[str, Any] | None = None,
    title: str = "",
    progress_callback: Callable[[dict[str, Any]], None] | None = None,
  ) -> None:
    value = str(text or "").strip()
    if progress_callback:
      progress_callback({"event_type": "long_text_started", "title": title, "total": 1 if value else 0})
    print(f"[MockTeamC] api_read_long_text: {title or '未命名'} ({len(value)} chars)")
    if progress_callback:
      progress_callback({"event_type": "long_text_finished", "title": title, "total": 1 if value else 0})

  def api_stop_long_text(self) -> None:
    print("[MockTeamC] api_stop_long_text")

  def api_register_logic_callback(self, callback: Callable[[dict[str, Any]], None]) -> None:
    self._logic_callback = callback
    print("[MockTeamC] 队员D逻辑回调已绑定（Mock）")

  def api_set_pet_id(self, pet_id: str) -> None:
    self.pet_id = (pet_id or "").strip()
    if not self.voice_pack_id:
      self.voice_pack_id = self.pet_id
    print(f"[MockTeamC] pet_id={self.pet_id}, voice_pack_id={self.voice_pack_id}")

  def api_set_voice_pack_id(self, pack_id: str) -> None:
    self.voice_pack_id = (pack_id or "").strip() or self.pet_id
    print(f"[MockTeamC] voice_pack_id={self.voice_pack_id}")

  def api_set_tts_settings(self, settings: dict[str, Any] | None) -> None:
    self.tts_settings = dict(settings or {})
    print(f"[MockTeamC] tts_settings={self.tts_settings}")


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

  def save(self, path: str = ACTION_MAPPING_PATH) -> None:
    try:
      os.makedirs(os.path.dirname(path), exist_ok=True)
      with open(path, "w", encoding="utf-8") as f:
        json.dump(self._data, f, ensure_ascii=False, indent=2)
    except OSError as exc:
      print(f"[ActionMapping] 保存失败: {exc}")

  def set_pet_mapping(self, pet_id: str, mapping: dict[str, list[str]]) -> None:
    self._data[pet_id] = {
      str(k): [str(x) for x in v]
      for k, v in mapping.items()
      if isinstance(v, list)
    }
    self.save()

  def pick_gif(self, pet_id: str, action_code: str, *, allow_idle_fallback: bool = True) -> str:
    pet_map = self._data.get(pet_id, {})
    candidates = list(pet_map.get(action_code, []) or [])
    if not candidates and allow_idle_fallback and action_code != "idle":
      return ""
    if not candidates and allow_idle_fallback:
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
            "label": motion_label_from_filename(fname),
            "gif": path,
            "frames": [],
            "action_code": action_code,
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
  """合并扫描数据与角色独立 action_mapping 配置。"""
  pet = dict(pet)
  pet["is_flat"] = True
  pet_id = pet.get("id", "")
  scanned_motions = pet.get("motions", [])
  if resolver and not mapping._data.get(pet_id):
    scanned_motions = resolver.motions_for_flat(pet_id) or scanned_motions
  pet["motions"] = mapping.motions_for_pet(pet_id, scanned_motions)
  idle_from_map = mapping.pick_gif(pet_id, "idle", allow_idle_fallback=False)
  if idle_from_map:
    pet["idle_gif"] = idle_from_map
  elif resolver:
    idle_asset = resolver._pick_flat_idle_fallback(pet_id)
    if idle_asset and idle_asset.get("type") == "gif":
      pet["idle_gif"] = idle_asset.get("path", "")
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
  comment_finished = Signal()
  chat_reply_finished = Signal(str, str)


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
      on_voice_pack_changed=desktop_pet.switch_voice_pack,
      current_voice_pack_id=desktop_pet.current_voice_pack_id(),
      on_tts_settings_changed=desktop_pet.update_tts_settings,
      current_tts_settings=desktop_pet.current_tts_settings(),
      on_read_text=desktop_pet.read_text_aloud,
      on_stop_read_text=desktop_pet.stop_text_reading,
      on_pet_settings_changed=desktop_pet.update_pet_personalization_settings,
    )
    self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
    self._flat = desktop_pet.list_flat_pets_enriched()
    self._history_viewer: StatusHistoryViewer | None = None
    self._reload_flat_tab()
    self._setup_console_nav()
    self.sync_dashboard_stats()

  def _setup_console_nav(self) -> None:
    self.resize(800, 600)
    self.setMinimumSize(720, 540)

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

  def _vision_debug_visible(self) -> bool:
    getter = getattr(self._desk, "_vision_debug_is_visible", None)
    if not callable(getter):
      return False
    try:
      return bool(getter())
    except Exception:
      return False

  def sync_vision_debug_state(self, visible: bool | None = None) -> None:
    btn = getattr(self, "_vision_debug_btn", None)
    if btn is None:
      return
    if visible is None:
      visible = self._vision_debug_visible()
    btn.blockSignals(True)
    btn.setChecked(bool(visible))
    btn.setText("视觉预览：开启" if visible else "视觉预览：关闭")
    btn.blockSignals(False)

  def _toggle_vision_debug_preview(self, checked: bool) -> None:
    setter = getattr(self._desk, "_vision_debug_set_visible", None)
    if callable(setter):
      try:
        setter(bool(checked))
      except Exception as exc:
        self._log(f"视觉调试预览切换失败: {exc}")
    else:
      self._log("视觉调试预览入口尚未初始化")
    self.sync_vision_debug_state()

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
    vision = QFrame()
    vision.setStyleSheet(_glass_style(14))
    vl = QVBoxLayout(vision)
    vl.setContentsMargins(14, 12, 14, 12)
    vl.setSpacing(8)
    vl.addWidget(QLabel("<h3>视觉调试</h3>"))
    desc = QLabel("显示B模块摄像头画面、FaceLandmarker关键点和用户状态调试信息。")
    desc.setWordWrap(True)
    desc.setStyleSheet("color:#64748b;")
    vl.addWidget(desc)
    self._vision_debug_btn = QPushButton("视觉预览：关闭")
    self._vision_debug_btn.setCheckable(True)
    self._vision_debug_btn.setStyleSheet(BTN_GLASS)
    self._vision_debug_btn.clicked.connect(self._toggle_vision_debug_preview)
    vl.addWidget(self._vision_debug_btn)
    lay.addWidget(vision)
    self.sync_vision_debug_state()
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
    self._action_min_play = False
    self._action_played_ms = 0
    self._gif_cycle_duration_ms = 0
    self._png_play_start = 0.0
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
      self._start_gif(gif, loop=False, on_finish=self.show_idle, min_play_ms=MIN_ACTION_PLAY_MS)
      return True
    frame_list = [f for f in (frames or []) if os.path.isfile(f)]
    if frame_list:
      self._frames = frame_list
      self._frame_index = 0
      self._png_play_start = time.time()
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
      self._start_gif(gif, loop=False, on_finish=self.show_idle, min_play_ms=MIN_ACTION_PLAY_MS)
      return True
    if frames:
      self._frames = [f for f in frames if os.path.isfile(f)]
      if not self._frames:
        self._playing_motion = False
        return False
      self._frame_index = 0
      self._png_play_start = time.time()
      self._on_frame_tick()
      self._frame_timer.start(self.FRAME_MS)
      return True
    self._playing_motion = False
    return False

  def hit_test(self, pos: tuple[int, int]) -> bool:
    if self._pixmap_rect.isEmpty():
      return False
    pt = QPoint(pos[0], pos[1])
    if not self._pixmap_rect.contains(pt):
      return False
    pm = self._display.pixmap()
    if pm is None or pm.isNull():
      return True
    lx = pos[0] - self._pixmap_rect.x()
    ly = pos[1] - self._pixmap_rect.y()
    if lx < 0 or ly < 0 or lx >= pm.width() or ly >= pm.height():
      return True
    return QColor(pm.toImage().pixel(lx, ly)).alpha() > 16

  def tick(self) -> None:
    pass

  def _stop_playback(self) -> None:
    self._frame_timer.stop()
    self._gif_timer.stop()
    self._gif_frames = []
    self._gif_durations_ms = []
    self._gif_frame_index = 0
    self._loop_gif = False
    self._action_min_play = False
    self._action_played_ms = 0
    self._gif_cycle_duration_ms = 0
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
    min_play_ms: int = 0,
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
    self._action_min_play = not loop and min_play_ms > 0
    self._action_played_ms = 0
    self._gif_cycle_duration_ms = sum(self._gif_durations_ms) or 100
    self._gif_frame_index = 0
    self._show_gif_frame(0)
    self._display.show()
    if len(self._gif_frames) == 1 and not loop:
      delay = self._gif_durations_ms[0]
      if self._action_min_play:
        delay = max(delay, min_play_ms)
      QTimer.singleShot(delay, self._on_gif_cycle_complete)
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
        self._on_gif_cycle_complete()
        return
    self._gif_frame_index = next_index
    self._show_gif_frame(self._gif_frame_index)
    self._gif_timer.start(self._gif_durations_ms[self._gif_frame_index])

  def _on_gif_cycle_complete(self) -> None:
    if self._action_min_play:
      self._action_played_ms += self._gif_cycle_duration_ms
      if self._action_played_ms < MIN_ACTION_PLAY_MS:
        self._gif_frame_index = 0
        self._show_gif_frame(0)
        if len(self._gif_frames) == 1:
          remain = MIN_ACTION_PLAY_MS - self._action_played_ms
          QTimer.singleShot(max(self._gif_durations_ms[0], remain), self._on_gif_cycle_complete)
        else:
          self._gif_timer.start(self._gif_durations_ms[0])
        return
    self._finish_gif_playback()

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
      elapsed_ms = int((time.time() - self._png_play_start) * 1000)
      if self._playing_motion and elapsed_ms < MIN_ACTION_PLAY_MS:
        self._frame_index = 0
        return
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
_THEME_BORDER = "rgba(255, 141, 161, 46)"
_THEME_CARD = "rgba(255, 255, 255, 224)"
_THEME_GLASS = "rgba(255, 255, 255, 199)"
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


def _bubble_qss(radius: int = 20) -> str:
  return f"""
    QFrame#glass {{
      background-color: {_THEME_GLASS};
      border: none;
      border-radius: {radius}px;
    }}
  """


def _btn_glass_qss(radius: int = 24) -> str:
  return f"""
    QPushButton {{
      background-color: rgba(255, 255, 255, 235);
      border: 1px solid {_THEME_BORDER};
      border-radius: {radius}px;
      padding: 10px 18px;
      color: {_THEME_TEXT};
      font-family: {_FONT_STACK};
      font-size: 14px;
    }}
    QPushButton:hover {{
      background-color: {_THEME_PINK_LIGHT};
      border-color: rgba(255, 141, 161, 89);
    }}
    QPushButton:pressed {{
      background-color: #FFD0DC;
    }}
    QPushButton:checked {{
      background-color: {_THEME_PINK_LIGHT};
      color: {_THEME_PINK};
      border-color: rgba(255, 141, 161, 115);
      font-weight: 600;
    }}
  """


def _btn_primary_qss(radius: int = 24, padding: str = "10px 22px") -> str:
  return f"""
    QPushButton {{
      background-color: {_THEME_PINK};
      color: white;
      border: none;
      border-radius: {radius}px;
      padding: {padding};
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
  background-color: rgba(255, 255, 255, 235);
  border: 1px solid {_THEME_BORDER};
  border-radius: 20px;
  padding: 10px 16px;
  color: {_THEME_TEXT};
  font-size: 14px;
  selection-background-color: {_THEME_PINK_LIGHT};
}}
QLineEdit:focus, QTextEdit:focus {{
  border: 1px solid rgba(255, 141, 161, 140);
}}
QTabWidget::pane {{
  border: none;
  background: transparent;
}}
QTabBar::tab {{
  background: rgba(255, 255, 255, 153);
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
  background: rgba(255, 141, 161, 89);
  border-radius: 4px;
  min-height: 24px;
}}
QScrollBar::handle:vertical:hover {{
  background: rgba(255, 141, 161, 140);
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
  height: 0;
}}
QScrollBar:horizontal {{
  background: transparent;
  height: 8px;
}}
QScrollBar::handle:horizontal {{
  background: rgba(255, 141, 161, 89);
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
    is_floating_bubble = w is pet.info_bubble or w is pet.chat_bubble
    w.setObjectName("glass")
    w.setAutoFillBackground(not is_floating_bubble)
    w.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, is_floating_bubble)
    w.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, is_floating_bubble)
    style = _bubble_qss(radii.get(w, 20)) if is_floating_bubble else _glass_qss(radii.get(w, 20))
    w.setStyleSheet(style)
    if is_floating_bubble:
      w.setGraphicsEffect(None)
    else:
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
    pet.input_box._btn.setStyleSheet(_btn_primary_qss(18, "0px 18px"))
    pet.input_box._btn.setMinimumHeight(30)
  for bubble in (pet.info_bubble, pet.chat_bubble):
    if bubble and hasattr(bubble, "_lbl"):
      bubble._lbl.setFont(_pet_font(15))
  if pet.input_box and hasattr(pet.input_box, "_field"):
    pet.input_box._field.setFont(_pet_font(15))
    if hasattr(pet.input_box, "_apply_field_style"):
      pet.input_box._apply_field_style()


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

  def __init__(self, pet: "DesktopPet", parent: QWidget | None = None) -> None:
    super().__init__(parent)
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
    self._pet._prepare_mouse_at(pos)
    if event.button() == Qt.MouseButton.RightButton:
      self._pet._open_context_menu(pos)
    elif event.button() == Qt.MouseButton.LeftButton:
      self._pet._on_left_press(pos)

  def mouseReleaseEvent(self, event: QMouseEvent) -> None:
    if event.button() == Qt.MouseButton.LeftButton:
      pos = (int(event.position().x()), int(event.position().y()))
      self._pet._on_left_release(pos)

  def shutdown(self) -> None:
    self._gl_ready = False
    try:
      self.makeCurrent()
      self.doneCurrent()
    except RuntimeError:
      pass
    except Exception:
      pass
    try:
      self.hide()
    except RuntimeError:
      pass
    try:
      self.close()
    except RuntimeError:
      pass
    try:
      self.deleteLater()
    except RuntimeError:
      pass


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
    self._gl = Live2DWidget(pet, self)
    layout.addWidget(self._gl)
    self._gl.lower()

    self._plane_player = PlanePetPlayer(self)
    self._plane_player.hide()

    pet.arc_menu.setParent(self)
    pet.context_menu.setParent(self)
    pet.pin_submenu.setParent(self)
    pet.hover_submenu.setParent(self)
    pet.status_submenu.setParent(self)
    pet.chat_submenu.setParent(self)
    pet._sync_floating_overlay_flags()

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

  def closeEvent(self, event) -> None:
    if not self._pet._cleaning_up:
      event.ignore()
      self._pet._close_pet_window()
      return
    super().closeEvent(event)

  def shutdown(self) -> None:
    self._pet._cleaning_up = True
    gl = getattr(self, "_gl", None)
    if gl is not None:
      shutdown = getattr(gl, "shutdown", None)
      if callable(shutdown):
        shutdown()
    plane_player = getattr(self, "_plane_player", None)
    if plane_player is not None:
      try:
        plane_player.hide()
        plane_player.close()
        plane_player.deleteLater()
      except RuntimeError:
        pass
      except Exception:
        pass
    try:
      self.hide()
    except RuntimeError:
      pass
    try:
      self.close()
    except RuntimeError:
      pass
    try:
      self.deleteLater()
    except RuntimeError:
      pass

  def mouseMoveEvent(self, event: QMouseEvent) -> None:
    if self._pet._is_flat_mode():
      pos = (event.position().x(), event.position().y())
      self._pet._on_mouse_move(pos)
    super().mouseMoveEvent(event)

  def mousePressEvent(self, event: QMouseEvent) -> None:
    pos = (int(event.position().x()), int(event.position().y()))
    self._pet._prepare_mouse_at(pos)
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
    self._cleaning_up = False
    self._closed = False
    self.available_motions: list[str] = []
    self.motion_name_map = MOTION_NAME_MAP

    self.on_click_callback: Optional[Callable[..., Any]] = None

    self._hwnd: Optional[int] = None
    self._win_w = 0
    self._win_h = 0
    self._pin_top = True
    self._hover_fade_enabled = False
    self._status_bar_enabled = False
    self._hovering_window = False
    self._window_alpha = 255
    self._click_through_active = False
    self._rbutton_was_down = False

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
    self._pending_chat_history: list[dict[str, str]] = []

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
    self._last_pet_id: str = ""
    self._voice_pack_id: str = ""
    self._tts_settings: dict[str, Any] = normalize_tts_settings(DEFAULT_TTS_UI_SETTINGS)
    self._active_pet: dict | None = None
    self._console: PetControlConsole | None = None
    self._chat_stream: ChatStreamBridge | None = None
    self._companion_bubble_active = False
    self._companion_bubble_token = 0

    self._computer_activity_config_enabled = _config_bool("COMPUTER_ACTIVITY_ENABLED", True)
    self._computer_companion_enabled = False
    self._desktop_observation_authorized = False
    self._computer_include_window_title = True
    self._computer_no_disturb_fullscreen = True
    self._computer_activity_detector: ComputerActivityDetector | None = None
    if self._computer_activity_config_enabled:
      self._computer_activity_detector = ComputerActivityDetector(
        min_comment_duration=_config_float("COMPUTER_ACTIVITY_MIN_DURATION", 0.0)
      )
    self._computer_comment_timer: Optional[QTimer] = None
    self._computer_comment_busy = False
    self._last_computer_comment_at = 0.0
    self._last_computer_comment_signature = ""
    self._computer_poll_ms = max(500, _config_int("COMPUTER_ACTIVITY_POLL_MS", 1000))
    self._computer_comment_cooldown = max(30.0, _config_float("COMPUTER_ACTIVITY_COMMENT_COOLDOWN", 150.0))
    self._apply_desktop_access_settings_from_disk()
    self._speech_hint_enabled = _config_bool("STATE_SPEECH_HINT_ENABLED", True)
    self._speech_hint_timer: Optional[QTimer] = None
    self._speech_hint_busy = False
    self._speech_hint_poll_ms = max(5000, _config_int("STATE_SPEECH_HINT_POLL_MS", 30000))
    self._speech_hint_cooldown = max(60.0, _config_float("STATE_SPEECH_HINT_COOLDOWN", 180.0))
    self._last_speech_hint_at = 0.0
    self._last_speech_hint_text = ""

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
      event_type = str(event.get("event_type") or event.get("event") or "")
      if event_type == "user_chat":
        reply = str(event.get("ai_reply") or "").strip()
        if reply:
          character_name = self._take_pending_chat_character(str(event.get("user_input") or ""))
          if self._chat_stream is not None:
            self._chat_stream.chat_reply_finished.emit(character_name, reply)
          else:
            self._save_chat_message("ai", reply, character_name=character_name)
        if hasattr(self.team_d, "api_update_from_chat_emotion"):
          try:
            self.team_d.api_update_from_chat_emotion(event)
          except Exception as exc:
            print(f"[DesktopPet] 更新聊天情绪画像失败: {exc}")
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

  def reload_action_mapping(self) -> None:
    self.action_mapping = ActionMappingStore.load()

  def refresh_pet_motions_after_synonym_change(self) -> None:
    self.refresh_pet_motions_after_mapping_change()

  def refresh_pet_motions_after_mapping_change(self) -> None:
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
      player = self._plane_player()
      if not player:
        return
      gif = self.action_mapping.pick_gif(pet_id, action, allow_idle_fallback=False)
      if not gif:
        gif = self.action_mapping.pick_gif(pet_id, "idle", allow_idle_fallback=False)
      if gif:
        player.play_asset(gif=gif)
      else:
        player.show_idle()
    elif self._model is not None:
      pet_id = (self._active_pet or {}).get("id", "mao")
      model_path = (self._active_pet or {}).get("model_path") or self.model_path
      if not self._play_live2d_from_mapping(pet_id, action, model_path):
        idle_stem = self._mapping_motion_stem(pet_id, "idle", model_path)
        if idle_stem:
          self.play_motion(idle_stem)
        else:
          self._start_idle_motion()

  def _mapping_motion_stem(
    self, pet_id: str, action: str, model_path: str | None = None
  ) -> str:
    pet_map = self.action_mapping._data.get(pet_id, {})
    candidates = list(pet_map.get(action, []) or [])
    if not candidates:
      return ""
    stem = random.choice(candidates)
    if self._resolve_motion(stem)[0] is not None:
      return stem
    matched = self.synonym_resolver._match_live2d_motions(pet_id, action, model_path)
    for path in matched:
      s = self.synonym_resolver._motion_stem_from_file(path)
      if s == stem or stem in path:
        return s
    return stem

  def _play_live2d_from_mapping(
    self, pet_id: str, action: str, model_path: str | None = None
  ) -> bool:
    stem = self._mapping_motion_stem(pet_id, action, model_path)
    if stem and self.play_motion(stem):
      return True
    return False

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
    self._last_pet_id = pet.get("id", "")
    self._sync_team_c_voice_context()
    self._save_pet_memory()
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
      # 重新加载 Live2D 模型（根据 pet 中的 model_path）
      model_path = pet.get('model_path') or ''
      if model_path and os.path.isfile(model_path):
        reload_live2d_model(self, model_path)
      self._start_idle_motion()
    self._update_mouse_passthrough(self._local_mouse_pos())
    self._show_switch_notice(name)
    print(f"[DesktopPet] 已切换到: {name}")
    QTimer.singleShot(0, self._after_pet_switch)

  def current_voice_pack_id(self) -> str:
    return self._voice_pack_id

  def current_tts_settings(self) -> dict[str, Any]:
    return dict(self._tts_settings)

  def switch_voice_pack(self, pack: dict) -> None:
    pack_id = str(pack.get("id", "") if isinstance(pack, dict) else "").strip()
    self._voice_pack_id = pack_id
    self._sync_team_c_voice_context()
    self._save_settings()
    name = str(pack.get("name") or pack.get("display_name") or "默认") if isinstance(pack, dict) else "默认"
    print(f"[DesktopPet] 已切换语音包: {name} ({pack_id or 'auto'})")

  def update_tts_settings(self, settings: dict[str, Any]) -> None:
    self._tts_settings = normalize_tts_settings(settings)
    self._sync_team_c_voice_context()
    self._save_settings()
    print(f"[DesktopPet] TTS settings updated: {self._tts_settings}")

  def update_pet_personalization_settings(self, settings: dict[str, dict[str, Any]]) -> None:
    self._apply_desktop_access_settings(settings)
    if not self._running:
      return
    if self._computer_companion_enabled:
      self._start_computer_companion()
    else:
      self._stop_computer_companion()

  def _apply_desktop_access_settings_from_disk(self) -> None:
    settings_path = os.path.join(PROJECT_ROOT, "data", "pet_personalization_settings.json")
    try:
      with open(settings_path, encoding="utf-8") as f:
        loaded = json.load(f)
    except (OSError, json.JSONDecodeError):
      loaded = {}
    self._apply_desktop_access_settings(loaded if isinstance(loaded, dict) else {})

  def _apply_desktop_access_settings(self, personalization: dict[str, Any] | None) -> None:
    settings = personalization if isinstance(personalization, dict) else {}
    desktop_access = settings.get("desktop_access") if isinstance(settings.get("desktop_access"), dict) else {}
    boundaries = settings.get("boundaries") if isinstance(settings.get("boundaries"), dict) else {}

    authorized = _setting_bool(desktop_access.get("foreground_observation_authorized"), False)
    comment_enabled = _setting_bool(desktop_access.get("proactive_comment_enabled"), True)
    self._desktop_observation_authorized = authorized
    self._computer_include_window_title = _setting_bool(desktop_access.get("include_window_title"), True)
    self._computer_no_disturb_fullscreen = _setting_bool(boundaries.get("no_disturb_when_fullscreen"), True)
    default_cooldown = _config_float("COMPUTER_ACTIVITY_COMMENT_COOLDOWN", 150.0)
    configured_cooldown = _setting_float(desktop_access.get("comment_interval_seconds"), default_cooldown)
    self._computer_comment_cooldown = max(30.0, min(3600.0, configured_cooldown))
    self._computer_companion_enabled = bool(
      self._computer_activity_config_enabled
      and self._desktop_observation_authorized
      and comment_enabled
    )
    if self._computer_companion_enabled and self._computer_activity_detector is None:
      self._computer_activity_detector = ComputerActivityDetector(
        min_comment_duration=_config_float("COMPUTER_ACTIVITY_MIN_DURATION", 0.0)
      )
    print(
      "[DesktopPet] 桌面授权: "
      f"authorized={self._desktop_observation_authorized}, "
      f"comments={self._computer_companion_enabled}, "
      f"title_context={self._computer_include_window_title}, "
      f"cooldown={self._computer_comment_cooldown:.0f}s"
    )

  def read_text_aloud(self, text: str, title: str = "") -> None:
    value = str(text or "").strip()
    if not value:
      return
    self._sync_team_c_voice_context()
    context = self._current_voice_state_context()
    context["voice_action"] = "read"
    context["tts_action"] = "read"
    if hasattr(self.team_c, "api_read_long_text"):
      try:
        self.team_c.api_read_long_text(value, current_state=context, title=title or "文本")
        return
      except Exception as exc:
        print(f"[DesktopPet] 长文本朗读失败: {exc}")
    if not hasattr(self.team_c, "api_play_system_voice"):
      return
    state = str(context.get("mood") or context.get("state_code") or "neutral").strip() or "neutral"
    if state == "normal":
      state = "neutral"
    try:
      self.team_c.api_play_system_voice(value, state=state, action="read")
    except Exception as exc:
      print(f"[DesktopPet] 文本朗读失败: {exc}")

  def _play_system_voice(self, text: str, *, state: str | None = None, action: str = "speak") -> None:
    if not hasattr(self.team_c, "api_play_system_voice"):
      return
    self._sync_team_c_voice_context()
    context = self._current_voice_state_context()
    voice_state = (state or str(context.get("mood") or context.get("state_code") or "neutral")).strip()
    if voice_state == "normal":
      voice_state = "neutral"
    voice_action = (action or "speak").strip() or "speak"
    context["voice_action"] = voice_action
    context["tts_action"] = voice_action
    play_voice = self.team_c.api_play_system_voice
    try:
      accepts_context = "current_state" in inspect.signature(play_voice).parameters
    except (TypeError, ValueError):
      accepts_context = False
    if accepts_context:
      play_voice(
        text,
        state=voice_state or "neutral",
        action=voice_action,
        current_state=context,
      )
    else:
      play_voice(text, state=voice_state or "neutral", action=voice_action)

  def stop_text_reading(self) -> None:
    if hasattr(self.team_c, "api_stop_long_text"):
      try:
        self.team_c.api_stop_long_text()
      except Exception as exc:
        print(f"[DesktopPet] 停止长文本朗读失败: {exc}")

  def _sync_team_c_voice_context(self) -> None:
    pet_id = self._last_pet_id or str((self._active_pet or {}).get("id", ""))
    if pet_id and hasattr(self.team_c, "api_set_pet_id"):
      try:
        self.team_c.api_set_pet_id(pet_id)
      except Exception as exc:
        print(f"[DesktopPet] 同步桌宠ID到队员C失败: {exc}")
    if hasattr(self.team_c, "api_set_voice_pack_id"):
      try:
        self.team_c.api_set_voice_pack_id(self._voice_pack_id)
      except Exception as exc:
        print(f"[DesktopPet] 同步语音包到队员C失败: {exc}")

    if hasattr(self.team_c, "api_set_tts_settings"):
      try:
        self.team_c.api_set_tts_settings(self._tts_settings)
      except Exception as exc:
        print(f"[DesktopPet] Sync TTS settings to Team C failed: {exc}")

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
    self._lower_character_layer()
    for widget in (
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
      if self._widget_alive(widget):
        widget.raise_()

  def _sync_floating_overlay_flags(self) -> None:
    flags = Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool
    if self._pin_top:
      flags |= Qt.WindowType.WindowStaysOnTopHint
    passive_flags = flags | Qt.WindowType.WindowDoesNotAcceptFocus
    for widget in (self.info_bubble, self.chat_bubble):
      if widget is None:
        continue
      was_visible = widget.isVisible()
      widget.setParent(None)
      widget.setWindowFlags(passive_flags)
      widget.setAutoFillBackground(False)
      widget.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
      widget.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
      widget.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
      if was_visible:
        QWidget.show(widget)
    if self.input_box is not None:
      was_visible = self.input_box.isVisible()
      self.input_box.setParent(None)
      self.input_box.setWindowFlags(flags)
      if was_visible:
        QWidget.show(self.input_box)

  def _floating_overlay_pos(self, width: int, height: int, preferred_y: int) -> tuple[int, int]:
    if self._window is None:
      return 0, 0
    gap = 12
    screen_margin = 8
    base = self._window.frameGeometry()
    screen = QApplication.screenAt(base.center()) or QApplication.primaryScreen()
    area = screen.availableGeometry() if screen else QRect(0, 0, 1920, 1080)
    left_room = base.left() - area.left()
    right_room = area.right() - base.right()
    if right_room >= width + gap or right_room >= left_room:
      x = min(base.right() + gap, area.right() - width - screen_margin)
    else:
      x = max(area.left() + screen_margin, base.left() - width - gap)
    y = base.top() + preferred_y
    y = max(area.top() + screen_margin, min(y, area.bottom() - height - screen_margin))
    return x, y

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
    self._model.StopAllMotions()
    self._model.StartMotion(
      group,
      index,
      MotionPriority.FORCE,
      onFinishMotionHandler=self._start_idle_motion,
    )
    try:
        self._model.SetExpression(motion_name)
    except Exception:
        pass
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
          self._play_system_voice(SYSTEM_VOICE_ON_CLICK, action="click")
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
        self._play_system_voice(SYSTEM_VOICE_ON_CLICK, action="click")
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

    size = self.window_size or (BASE_WINDOW_W, BASE_WINDOW_H)
    self._win_w, self._win_h = size
    self._aspect_ratio = self._win_w / max(1, self._win_h)
    self._resize_start_size = (self._win_w, self._win_h)

    self._window = PetWindow(self)
    self._window.setGeometry(self.position[0], self.position[1], self._win_w, self._win_h)
    self._window.show()

    self._set_pin_top(self._pin_top)
    self._apply_window_opacity(255)
    self._apply_ui_scale()
    if self._status_bar_enabled and self.info_bubble:
      self.info_bubble.show(0, 0)
      self._layout_bubbles()
    if self._chat_open:
      self._set_chat_open(True)
    self._running = True

    self._timer = QTimer()
    self._timer.timeout.connect(self._tick)
    self._timer.start(16)

    self._start_computer_companion()
    self._start_state_speech_hints()
    QTimer.singleShot(0, self._restore_last_pet)

    self._app.exec()
    if self._running:
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
    self._chat_stream.comment_finished.connect(self._handle_companion_comment_finished)
    self._chat_stream.chat_reply_finished.connect(self._save_ai_reply_from_event)
    _apply_desktop_overlays(self)

  def _append_chat_chunk(self, ch: str) -> None:
    if self.chat_bubble is None or not (self._chat_open or self._companion_bubble_active):
      return
    next_text = self.chat_bubble.text + ch
    if not self.chat_bubble.visible or not self.chat_bubble.isVisible():
      self._layout_bubbles(chat_text=next_text)
      return
    old_height = self.chat_bubble.height()
    self.chat_bubble.set_text(next_text)
    self.chat_bubble.adjustSize()
    if abs(self.chat_bubble.height() - old_height) > 8:
      self._reflow_visible_bubbles()
    else:
      self.chat_bubble.update()

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
    """Place chat/status/input overlays beside the pet window."""
    if self._window is None:
      return
    _cx, head_y, _body_bottom = self._character_layout()
    margin = 8
    gap = 10

    status_on = bool(self._status_bar_enabled and self.info_bubble)
    chat_on = bool((self._chat_open or self._companion_bubble_active) and self.chat_bubble)
    input_on = bool(self._chat_open and self.input_box)

    items: list[tuple[QWidget, int, int]] = []
    if status_on and self.info_bubble:
      self.info_bubble.show(0, 0)
      items.append((self.info_bubble, self.info_bubble.width(), self.info_bubble.height()))
    if input_on and self.input_box:
      self.input_box.show(0, 0)
      items.append((self.input_box, self.input_box.width(), self.input_box.height()))
    if chat_on and self.chat_bubble:
      text = chat_text if chat_text is not None else self.chat_bubble.text
      self.chat_bubble.show(0, 0, text)
      items.append((self.chat_bubble, self.chat_bubble.width(), self.chat_bubble.height()))

    if not items:
      return

    stack_w = max(width for _widget, width, _height in items)
    stack_h = sum(height for _widget, _width, height in items) + gap * (len(items) - 1)
    preferred_y = max(margin, min(head_y - stack_h // 3, self._win_h - stack_h - margin))
    x, y = self._floating_overlay_pos(stack_w, stack_h, preferred_y)

    cursor_y = y
    for widget, width, height in items:
      widget.move(x + (stack_w - width) // 2, cursor_y)
      widget.raise_()
      cursor_y += height + gap

    self._raise_ui_overlays()

  def _reflow_visible_bubbles(self) -> None:
    """Reposition already-visible overlays without hiding/showing them."""
    visible: list[QWidget] = []
    for widget in (self.info_bubble, self.input_box, self.chat_bubble):
      if widget is not None and widget.isVisible():
        visible.append(widget)
    if not visible:
      return

    margin = 8
    gap = 10
    stack_w = max(widget.width() for widget in visible)
    stack_h = sum(widget.height() for widget in visible) + gap * (len(visible) - 1)
    x = min(widget.x() for widget in visible)
    y = max(margin, min(visible[0].y(), self._win_h - stack_h - margin))

    cursor_y = y
    for widget in visible:
      widget.move(x + (stack_w - widget.width()) // 2, cursor_y)
      widget.raise_()
      cursor_y += widget.height() + gap
    self._raise_ui_overlays()

  def _remember_pending_chat_reply(self, character_name: str, user_text: str) -> None:
    self._pending_chat_history.append(
      {"name": str(character_name or "").strip(), "user": str(user_text or "").strip()}
    )
    if len(self._pending_chat_history) > 50:
      self._pending_chat_history = self._pending_chat_history[-50:]

  def _take_pending_chat_character(self, user_text: str) -> str:
    value = str(user_text or "").strip()
    for idx, item in enumerate(self._pending_chat_history):
      if not value or item.get("user") == value:
        found = self._pending_chat_history.pop(idx)
        return found.get("name") or self._active_character_name()
    if self._pending_chat_history:
      found = self._pending_chat_history.pop(0)
      return found.get("name") or self._active_character_name()
    return self._active_character_name()

  def _save_ai_reply_from_event(self, character_name: str, reply: str) -> None:
    self._save_chat_message("ai", reply, character_name=character_name)

  def _save_chat_message(self, role: str, text: str, character_name: str | None = None) -> None:
    name = character_name or self._active_character_name()
    text = str(text or "").strip()
    if not text:
      return
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

  def _apply_window_size(self, w: int, h: int, save_memory: bool = True) -> None:
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
    self._apply_ui_scale()
    if self._status_bar_enabled or self._chat_open:
      self._layout_bubbles()
    if save_memory:
      self._save_pet_memory()

  def _ui_scale_factor(self) -> float:
    return max(0.35, min(1.25, self._win_w / BASE_WINDOW_W))

  def _apply_ui_scale(self) -> None:
    scale = self._ui_scale_factor()
    for widget in (
      self.context_menu,
      self.pin_submenu,
      self.hover_submenu,
      self.status_submenu,
      self.chat_submenu,
      self.info_bubble,
      self.chat_bubble,
      self.input_box,
      self.arc_menu,
    ):
      if widget is not None and hasattr(widget, "apply_ui_scale"):
        widget.apply_ui_scale(scale)

  def _scale_window(self, factor: float) -> None:
    if factor <= 0:
      return
    new_w = int(self._win_w * factor)
    new_h = int(new_w / self._aspect_ratio)
    self._apply_window_size(new_w, new_h)

  def set_pet_scale(self, scale: float, min_scale: float = 0.6, max_scale: float = 1.8) -> float:
    value = max(float(min_scale), min(float(max_scale), float(scale)))
    new_w = int(round(BASE_WINDOW_W * value))
    new_h = int(round(BASE_WINDOW_H * value))
    if abs(new_w - self._win_w) < 2 and abs(new_h - self._win_h) < 2:
      return self.current_pet_scale()
    self._aspect_ratio = BASE_WINDOW_W / BASE_WINDOW_H
    self._apply_window_size(new_w, new_h, save_memory=False)
    if self._window is not None:
      self._window.update()
    if self._is_flat_mode():
      player = self._plane_player()
      if player is not None:
        player.update()
    print(f"[DesktopPet] 缩放已应用: scale={value:.2f}, size={new_w}x{new_h}")
    return self.current_pet_scale()

  def current_pet_scale(self) -> float:
    if self._win_w <= 0:
      return 1.0
    return self._win_w / BASE_WINDOW_W

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
    if enabled == self._click_through_active:
      return
    try:
      style = win32gui.GetWindowLong(self._hwnd, win32con.GWL_EXSTYLE)
      if enabled:
        style |= win32con.WS_EX_LAYERED | win32con.WS_EX_TRANSPARENT
      else:
        style &= ~win32con.WS_EX_TRANSPARENT
      win32gui.SetWindowLong(self._hwnd, win32con.GWL_EXSTYLE, style)
      self._click_through_active = enabled
    except Exception:
      pass

  def _stop_runtime_timers(self) -> None:
    self._running = False
    for attr in ("_timer", "_computer_comment_timer", "_speech_hint_timer"):
      timer = getattr(self, attr, None)
      if timer is not None:
        try:
          timer.stop()
        except RuntimeError:
          pass
        try:
          timer.deleteLater()
        except RuntimeError:
          pass
        setattr(self, attr, None)
    try:
      self._edge_hold_timer.stop()
    except RuntimeError:
      pass
    try:
      self._edge_hold_timer.deleteLater()
    except RuntimeError:
      pass

  def _close_qt_widget(self, widget: QWidget | None) -> None:
    if not self._widget_alive(widget):
      return
    shutdown = getattr(widget, "shutdown", None)
    if callable(shutdown):
      try:
        shutdown()
        return
      except RuntimeError:
        return
      except Exception as exc:
        print(f"[DesktopPet] 子窗口 shutdown 失败，改用 close: {exc}")
    try:
      widget.hide()
    except RuntimeError:
      pass
    try:
      widget.close()
    except RuntimeError:
      pass
    try:
      widget.deleteLater()
    except RuntimeError:
      pass

  def _close_child_windows(self) -> None:
    for widget in (
      getattr(self, "_vision_debug_panel", None),
      self._console,
      self.info_bubble,
      self.chat_bubble,
      self.input_box,
      self.context_menu,
      self.pin_submenu,
      self.hover_submenu,
      self.status_submenu,
      self.chat_submenu,
      self.arc_menu,
      self._window,
    ):
      self._close_qt_widget(widget)
    self._clear_overlay_refs()
    self._console = None
    self._window = None
    self._hwnd = None
    if hasattr(self, "_vision_debug_panel"):
      self._vision_debug_panel = None
    self._chat_stream = None

  def _release_live2d_resources(self) -> None:
    gl_widget = None
    if self._window is not None:
      gl_widget = getattr(self._window, "_gl", None)
    made_current = False
    if gl_widget is not None and self._widget_alive(gl_widget):
      try:
        gl_widget.makeCurrent()
        made_current = True
      except RuntimeError:
        made_current = False
      except Exception:
        made_current = False
    self._model = None
    try:
      live2d.glRelease()
    except Exception:
      pass
    try:
      live2d.dispose()
    except Exception:
      pass
    if gl_widget is not None and made_current:
      try:
        gl_widget.doneCurrent()
      except RuntimeError:
        pass
      except Exception:
        pass

  def close(self) -> None:
    if self._closed:
      return
    self._closed = True
    self._cleaning_up = True
    self._stop_runtime_timers()
    self.stop_text_reading()
    self._release_live2d_resources()
    self._close_child_windows()

  def cleanup(self, quit_app: bool = False) -> None:
    self.close()
    if quit_app and self._app:
      self._app.quit()

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
    self._poll_right_button_menu()

  def _start_computer_companion(self) -> None:
    if not self._computer_companion_enabled or self._computer_activity_detector is None:
      return
    if self._computer_comment_timer is not None:
      self._computer_comment_timer.stop()
    self._computer_comment_timer = QTimer()
    self._computer_comment_timer.timeout.connect(self._poll_computer_companion)
    self._computer_comment_timer.start(self._computer_poll_ms)
    QTimer.singleShot(self._computer_poll_ms, self._poll_computer_companion)
    print("[DesktopPet] 电脑状态陪伴点评已开启。")

  def _stop_computer_companion(self) -> None:
    if self._computer_comment_timer is not None:
      self._computer_comment_timer.stop()
      self._computer_comment_timer = None
    self._computer_comment_busy = False
    print("[DesktopPet] 电脑状态陪伴点评已关闭。")

  def _start_state_speech_hints(self) -> None:
    if not self._speech_hint_enabled:
      return
    if self._speech_hint_timer is not None:
      self._speech_hint_timer.stop()
    self._speech_hint_timer = QTimer()
    self._speech_hint_timer.timeout.connect(self._poll_state_speech_hint)
    self._speech_hint_timer.start(self._speech_hint_poll_ms)
    QTimer.singleShot(self._speech_hint_poll_ms, self._poll_state_speech_hint)
    print("[DesktopPet] 桌宠主动语音提示已开启。")

  def _poll_state_speech_hint(self) -> None:
    if (
      not self._running
      or self._speech_hint_busy
      or self._computer_comment_busy
      or self._chat_open
      or self._any_menu_open()
      or self._resizing_corner
    ):
      return
    if not hasattr(self.team_d, "api_should_speak") or not hasattr(self.team_d, "api_get_speech_hint"):
      return
    try:
      if not self.team_d.api_should_speak():
        return
      hint = str(self.team_d.api_get_speech_hint() or "").strip()
    except Exception as exc:
      print(f"[DesktopPet] 主动语音提示检查失败: {exc}")
      return
    if not hint:
      return

    now = time.time()
    if now - self._last_speech_hint_at < self._speech_hint_cooldown:
      return
    if hint == self._last_speech_hint_text and now - self._last_speech_hint_at < self._speech_hint_cooldown * 2:
      return

    self._last_speech_hint_at = now
    self._last_speech_hint_text = hint
    self._emit_state_speech_hint(hint)

  def _emit_state_speech_hint(self, hint: str) -> None:
    self._speech_hint_busy = True
    self._begin_companion_bubble()

    def _run() -> None:
      try:
        self._stream_text_to_ui(hint)
        if hasattr(self.team_c, "api_play_speech_hint"):
          self.team_c.api_play_speech_hint(hint)
        elif hasattr(self.team_c, "api_play_system_voice"):
          self.team_c.api_play_system_voice(hint, state="hint", action="speak")
      except Exception as exc:
        print(f"[DesktopPet] 主动语音提示失败: {exc}")
      finally:
        self._speech_hint_busy = False
        if self._chat_stream is not None:
          self._chat_stream.comment_finished.emit()

    threading.Thread(target=_run, daemon=True).start()

  def _poll_computer_companion(self) -> None:
    if (
      not self._running
      or not self._computer_companion_enabled
      or not self._desktop_observation_authorized
      or self._computer_activity_detector is None
      or self._computer_comment_busy
      or self._chat_open
      or self._any_menu_open()
      or self._resizing_corner
    ):
      return

    try:
      state = self._computer_activity_detector.get_state()
    except Exception as exc:
      print(f"[DesktopPet] 电脑状态检测失败: {exc}")
      return

    if self._computer_no_disturb_fullscreen and bool(state.get("is_fullscreen")):
      return
    if not state.get("need_response"):
      return
    comment_state = self._privacy_filtered_activity_state(state)
    event = build_companion_event(comment_state)
    if not event:
      return

    now = time.time()
    signature = self._computer_comment_signature(event)
    if now - self._last_computer_comment_at < self._computer_comment_cooldown:
      return
    if signature == self._last_computer_comment_signature and now - self._last_computer_comment_at < self._computer_comment_cooldown * 2:
      return

    self._last_computer_comment_at = now
    self._last_computer_comment_signature = signature
    self._emit_computer_companion_comment(event, comment_state)

  def _privacy_filtered_activity_state(self, state: dict[str, Any]) -> dict[str, Any]:
    filtered = dict(state)
    if not self._computer_include_window_title:
      filtered["window_title"] = ""
      filtered["description"] = re.sub(
        r"，窗口标题是.*?(?:，|。|$)",
        "，",
        str(filtered.get("description") or ""),
      ).rstrip("，")
      filtered["suggestion"] = build_activity_suggestion(filtered)
    return filtered

  def _emit_computer_companion_comment(self, event: dict[str, Any], state: dict[str, Any]) -> None:
    self._computer_comment_busy = True
    self._begin_companion_bubble()

    def _run() -> None:
      reply = ""
      try:
        if hasattr(self.team_c, "api_on_status_event"):
          reply = self.team_c.api_on_status_event(event, ui_callback=self._stream_ui_callback)
        if not reply:
          reply = build_local_companion_comment(state)
          self._stream_text_to_ui(reply)
          if hasattr(self.team_c, "api_play_system_voice"):
            self.team_c.api_play_system_voice(reply, state="happy", action="speak")
      except Exception as exc:
        print(f"[DesktopPet] 电脑状态点评失败，使用本地短句: {exc}")
        reply = build_local_companion_comment(state)
        self._stream_text_to_ui(reply)
        try:
          if hasattr(self.team_c, "api_play_system_voice"):
            self.team_c.api_play_system_voice(reply, state="happy", action="speak")
        except Exception as voice_exc:
          print(f"[DesktopPet] 电脑状态点评语音失败: {voice_exc}")
      finally:
        if self._chat_stream is not None:
          self._chat_stream.comment_finished.emit()

    threading.Thread(target=_run, daemon=True).start()

  def _begin_companion_bubble(self) -> None:
    self._companion_bubble_active = True
    self._companion_bubble_token += 1
    if self.chat_bubble is not None:
      self.chat_bubble.set_text("")
      self._layout_bubbles(chat_text="")

  def _handle_companion_comment_finished(self) -> None:
    self._computer_comment_busy = False
    token = self._companion_bubble_token

    def _hide_if_current() -> None:
      if token == self._companion_bubble_token:
        self._hide_companion_bubble()

    QTimer.singleShot(9000, _hide_if_current)

  def _finish_companion_comment(self) -> None:
    self._handle_companion_comment_finished()

  def _hide_companion_bubble(self) -> None:
    if self._chat_open:
      self._companion_bubble_active = False
      return
    self._companion_bubble_active = False
    if self.chat_bubble is not None:
      self.chat_bubble.hide()
    if self._status_bar_enabled and self.info_bubble is not None:
      self._layout_bubbles()
    self._update_mouse_passthrough(self._local_mouse_pos())

  def _stream_text_to_ui(self, text: str) -> None:
    show_feedback_message(text, self._stream_ui_callback, stream=True, delay=0.015)

  @staticmethod
  def _computer_comment_signature(event: dict[str, Any]) -> str:
    title = str(event.get("window_title", "") or "")[:48].lower()
    process = str(event.get("process_name", "") or "").lower()
    return f"{event.get('activity_code')}|{process}|{title}"

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
      self._click_through_active = False
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

  def _cursor_in_window(self, mouse_pos: tuple[int, int]) -> bool:
    x, y = mouse_pos
    return 0 <= x < self._win_w and 0 <= y < self._win_h

  def _prepare_mouse_at(self, pos: tuple[int, int]) -> None:
    """点击前先按位置取消穿透，避免 WS_EX_TRANSPARENT 吞掉 Qt 鼠标事件。"""
    if not self._hover_fade_enabled:
      return
    if self._is_mouse_on_body(pos) or self._point_on_ui(pos):
      self._set_window_click_through(False)
      self._set_gl_mouse_passthrough(not self._is_mouse_on_body(pos))
    self._update_mouse_passthrough(pos)

  def _poll_right_button_menu(self) -> None:
    """穿透开启时 Qt 收不到右键；在 tick 里用 Win32 检测角色身上的右键。"""
    if not self._hover_fade_enabled or not win32api or not win32con:
      self._rbutton_was_down = False
      return
    try:
      down = bool(win32api.GetAsyncKeyState(win32con.VK_RBUTTON) & 0x8000)
    except Exception:
      return
    if down and not self._rbutton_was_down:
      pos = self._local_mouse_pos()
      if (
        self._cursor_in_window(pos)
        and self._is_mouse_on_body(pos)
        and self._click_through_active
      ):
        self._set_window_click_through(False)
        self._set_gl_mouse_passthrough(False)
        self._open_context_menu(pos)
    self._rbutton_was_down = down

  def _update_mouse_passthrough(self, mouse_pos: tuple[int, int]) -> None:
    """悬停淡出开启时：仅窗口内透明背景穿透；关闭时：完全不穿透。"""
    if self._any_menu_open() or self._resize_visible:
      self._set_window_click_through(False)
      self._set_gl_mouse_passthrough(True)
      return
    if self._chat_open:
      self._set_window_click_through(False)
      if self._is_flat_mode():
        self._set_gl_mouse_passthrough(True)
      else:
        self._set_gl_mouse_passthrough(False)
      return
    if self._dragging or self._resizing_corner:
      self._set_window_click_through(False)
      self._set_gl_mouse_passthrough(False)
      return
    if not self._hover_fade_enabled:
      self._set_window_click_through(False)
      self._set_gl_mouse_passthrough(False)
      return
    if not self._cursor_in_window(mouse_pos):
      self._set_window_click_through(False)
      self._set_gl_mouse_passthrough(True)
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
      return False
    if self._model is None:
      return False
    x, y = mouse_pos
    for area_id in HIT_AREAS:
      if self._model.HitTest(area_id, x, y):
        return True
    try:
      parts = self._model.HitPart(float(x), float(y), True)
      if parts:
        return True
    except Exception:
      pass
    return False

  def _load_settings(self) -> None:
    defaults = {
      "pin_top": True,
      "hover_fade": False,
      "status_bar": False,
      "chat_open": False,
      "voice_pack_id": "",
      "tts_settings": DEFAULT_TTS_UI_SETTINGS,
    }
    data: dict[str, Any] = dict(defaults)
    try:
      with open(SETTINGS_PATH, encoding="utf-8") as f:
        data.update(json.load(f))
    except (OSError, json.JSONDecodeError, TypeError):
      pass
    mem = self._load_pet_memory()
    if mem:
      data.update({k: mem[k] for k in defaults if k in mem})
      if mem.get("last_pet_id"):
        self._last_pet_id = str(mem["last_pet_id"])
      pos = mem.get("position")
      if isinstance(pos, (list, tuple)) and len(pos) == 2:
        self.position = [int(pos[0]), int(pos[1])]
      size = mem.get("window_size")
      if isinstance(size, (list, tuple)) and len(size) == 2:
        self.window_size = (int(size[0]), int(size[1]))
    self._pin_top = bool(data.get("pin_top", defaults["pin_top"]))
    self._hover_fade_enabled = bool(data.get("hover_fade", defaults["hover_fade"]))
    self._status_bar_enabled = bool(data.get("status_bar", defaults["status_bar"]))
    self._chat_open = bool(data.get("chat_open", defaults["chat_open"]))
    self._voice_pack_id = str(data.get("voice_pack_id", defaults["voice_pack_id"]) or "").strip()
    self._tts_settings = normalize_tts_settings(data.get("tts_settings", defaults["tts_settings"]))
    self._sync_team_c_voice_context()

  def _save_settings(self) -> None:
    data = {
      "pin_top": self._pin_top,
      "hover_fade": self._hover_fade_enabled,
      "status_bar": self._status_bar_enabled,
      "chat_open": self._chat_open,
      "voice_pack_id": self._voice_pack_id,
      "tts_settings": self._tts_settings,
    }
    try:
      os.makedirs(_SETTINGS_DIR, exist_ok=True)
      with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    except OSError as exc:
      print(f"[DesktopPet] 保存设置失败: {exc}")
    self._save_pet_memory()

  def _load_pet_memory(self) -> dict[str, Any]:
    if not os.path.isfile(PET_MEMORY_PATH):
      return {}
    try:
      with open(PET_MEMORY_PATH, encoding="utf-8") as f:
        data = json.load(f)
      return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError, TypeError):
      return {}

  def _save_pet_memory(self) -> None:
    data: dict[str, Any] = {
      "last_pet_id": self._last_pet_id or (self._active_pet or {}).get("id", ""),
      "pin_top": self._pin_top,
      "hover_fade": self._hover_fade_enabled,
      "status_bar": self._status_bar_enabled,
      "chat_open": self._chat_open,
      "voice_pack_id": self._voice_pack_id,
      "tts_settings": self._tts_settings,
    }
    if self._window is not None:
      data["position"] = [self._window.x(), self._window.y()]
      data["window_size"] = [self._win_w, self._win_h]
    else:
      data["position"] = list(self.position)
      data["window_size"] = [self._win_w, self._win_h]
    try:
      os.makedirs(os.path.dirname(PET_MEMORY_PATH), exist_ok=True)
      with open(PET_MEMORY_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    except OSError as exc:
      print(f"[DesktopPet] 保存记忆失败: {exc}")

  def _restore_last_pet(self) -> None:
    pet_id = self._last_pet_id
    if not pet_id:
      return
    record = self.build_pet_record(pet_id)
    if record:
      self.switch_to_pet(record)
      return
    for pet in self.list_flat_pets_enriched():
      if pet.get("id") == pet_id:
        self.switch_to_pet(pet)
        return

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
    self._sync_floating_overlay_flags()
    if self._status_bar_enabled or self._chat_open:
      self._layout_bubbles()
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
    if enabled and self.info_bubble:
      self.info_bubble.show(0, 0)
      self._layout_bubbles()
    elif self.info_bubble:
      self.info_bubble.hide()
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
    if self._status_bar_enabled or self._chat_open:
      self._layout_bubbles()
    self._save_pet_memory()

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
    self._update_hover_alpha(ipos)

  def _input_box_contains(self, pos: tuple[int, int]) -> bool:
    if not self._chat_open or not self._widget_alive(self.input_box):
      return False
    return self.input_box.isVisible() and self.input_box.geometry().contains(QPoint(*pos))

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
    if self._input_box_contains(pos):
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
      if self._input_box_contains(pos) and self.input_box:
        self.input_box._field.setFocus()
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
    if self._input_box_contains(pos) and self.input_box:
      local = self.input_box.mapFromParent(QPoint(*pos))
      if (
        hasattr(self.input_box, "_voice_btn")
        and self.input_box._voice_btn.geometry().contains(local)
      ):
        self.input_box.start_voice_input()
        return True
      if self.input_box._btn.geometry().contains(local):
        self._submit_chat()
        return True
      self.input_box._field.setFocus()
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

  def _widget_alive(self, widget: QWidget | None) -> bool:
    if widget is None:
      return False
    try:
      from shiboken6 import isValid
      return bool(isValid(widget))
    except ImportError:
      return True

  def _dismiss_menus(self) -> None:
    for widget in (
      self.context_menu,
      self.pin_submenu,
      self.hover_submenu,
      self.status_submenu,
      self.chat_submenu,
      self.arc_menu,
    ):
      if self._widget_alive(widget):
        widget.hide()
    self._restore_window_focus()

  def _clear_overlay_refs(self) -> None:
    self.context_menu = None
    self.pin_submenu = None
    self.hover_submenu = None
    self.status_submenu = None
    self.chat_submenu = None
    self.arc_menu = None
    self.info_bubble = None
    self.chat_bubble = None
    self.input_box = None

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
      self._close_pet_window()
    elif item == "关闭":
      pass

  def _close_pet_window(self) -> None:
    """关闭完整桌宠程序并释放所有 UI 子窗口。"""
    self._save_pet_memory()
    self.cleanup(quit_app=True)

  def _open_settings_panel(self) -> None:
    self.arc_menu.hide()
    console = PetControlConsole(
      desktop_pet=self,
      project_root=PROJECT_ROOT,
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
    user_text = str(msg).strip()
    character_name = self._active_character_name()
    if not self._chat_open:
      self._set_chat_open(True)
    self._save_chat_message("user", user_text, character_name=character_name)
    self._remember_pending_chat_reply(character_name, user_text)
    self._layout_bubbles(chat_text="")
    self.input_box.set_text("")
    self.team_c.api_user_speak(
      user_text,
      self._current_voice_state_context(),
      self._stream_ui_callback,
    )

  def _current_voice_state_context(self) -> dict[str, Any]:
    state: dict[str, Any] = {"state_code": "normal"}
    try:
      if hasattr(self.team_d, "api_get_pet_status"):
        raw = self.team_d.api_get_pet_status()
        if isinstance(raw, dict):
          state.update(raw)
    except Exception as exc:
      print(f"[DesktopPet] Read voice state context failed: {exc}")
    emotion_style = str(self._tts_settings.get("emotion_style") or "auto").strip()
    if emotion_style:
      state["tts_style"] = emotion_style
    tts_settings = dict(self._tts_settings)
    state["tts_settings"] = tts_settings
    if str(tts_settings.get("response_language") or "").strip():
      state["response_language"] = str(tts_settings.get("response_language") or "").strip()
    if str(tts_settings.get("edge_voice") or "").strip():
      state["edge_voice"] = str(tts_settings.get("edge_voice") or "").strip()
    try:
      ui_settings = load_ui_settings(PROJECT_ROOT)
      personalization = ui_settings.get("personalization_settings")
      if isinstance(personalization, dict):
        state["personalization_settings"] = personalization
    except Exception as exc:
      print(f"[DesktopPet] Load personalization settings failed: {exc}")
    try:
      state["user_profile"] = UserProfile.load().to_prompt_context()
    except Exception as exc:
      print(f"[DesktopPet] Load user profile failed: {exc}")
    return state

  def _start_idle_motion(self, *_args: Any) -> None:
    if self._model is None:
      return
    self._model.StartMotion("Idle", 0, MotionPriority.FORCE)

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
