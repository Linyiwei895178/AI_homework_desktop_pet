"""
Computer activity detector for companion-style desktop pet comments.

The detector only inspects the foreground window title, process name, and
fullscreen status. It does not capture the screen or read app contents.
"""

from __future__ import annotations

import os
import random
import re
import time
from dataclasses import dataclass
from typing import Any, Dict, Iterable, Optional

try:
    import win32api  # type: ignore
    import win32con  # type: ignore
    import win32gui  # type: ignore
    import win32process  # type: ignore
except Exception:  # pragma: no cover - exercised only on Windows with pywin32
    win32api = None  # type: ignore
    win32con = None  # type: ignore
    win32gui = None  # type: ignore
    win32process = None  # type: ignore


ACTIVITY_GAMING = "gaming"
ACTIVITY_WATCHING = "watching"
ACTIVITY_BROWSING = "browsing"
ACTIVITY_CHATTING = "chatting"
ACTIVITY_CODING = "coding"
ACTIVITY_WORKING = "working"
ACTIVITY_IDLE = "idle"
ACTIVITY_UNKNOWN = "unknown"

COMMENTABLE_ACTIVITIES = {ACTIVITY_GAMING, ACTIVITY_WATCHING}

ACTIVITY_NAME_MAP = {
    ACTIVITY_GAMING: "游戏中",
    ACTIVITY_WATCHING: "看剧/视频中",
    ACTIVITY_BROWSING: "浏览网页",
    ACTIVITY_CHATTING: "聊天中",
    ACTIVITY_CODING: "编程中",
    ACTIVITY_WORKING: "办公中",
    ACTIVITY_IDLE: "桌面空闲",
    ACTIVITY_UNKNOWN: "未知电脑状态",
}

BROWSER_PROCESSES = {
    "chrome.exe",
    "msedge.exe",
    "firefox.exe",
    "brave.exe",
    "opera.exe",
    "browser.exe",
    "qqbrowser.exe",
    "360chrome.exe",
}

VIDEO_PLAYER_PROCESSES = {
    "potplayer.exe",
    "potplayer64.exe",
    "vlc.exe",
    "mpv.exe",
    "wmplayer.exe",
    "moviesandtv.exe",
    "bilibili.exe",
    "qqlive.exe",
    "qiyi.exe",
    "youku.exe",
}

CHAT_PROCESSES = {
    "wechat.exe",
    "weixin.exe",
    "qq.exe",
    "tim.exe",
    "discord.exe",
    "telegram.exe",
    "dingtalk.exe",
    "feishu.exe",
    "lark.exe",
}

CODING_PROCESSES = {
    "pycharm64.exe",
    "pycharm.exe",
    "code.exe",
    "cursor.exe",
    "idea64.exe",
    "webstorm64.exe",
    "devenv.exe",
    "sublime_text.exe",
    "notepad++.exe",
}

OFFICE_PROCESSES = {
    "winword.exe",
    "excel.exe",
    "powerpnt.exe",
    "wps.exe",
    "et.exe",
    "wpp.exe",
    "onenote.exe",
    "notion.exe",
    "obsidian.exe",
}

KNOWN_GAME_PROCESSES = {
    "eldenring.exe",
    "starfield.exe",
    "stardew valley.exe",
    "stardewvalley.exe",
    "minecraft.exe",
    "javaw.exe",
    "league of legends.exe",
    "leagueclientux.exe",
    "valorant-win64-shipping.exe",
    "cs2.exe",
    "dota2.exe",
    "overwatch.exe",
    "r5apex.exe",
    "genshinimpact.exe",
    "yuan shen.exe",
    "hkrpg.exe",
    "zenlesszonezero.exe",
    "palworld-win64-shipping.exe",
}

GAME_TITLE_KEYWORDS = (
    "steam",
    "epic games",
    "xbox",
    "minecraft",
    "stardew valley",
    "星露谷",
    "league of legends",
    "英雄联盟",
    "valorant",
    "无畏契约",
    "counter-strike",
    "cs2",
    "dota 2",
    "apex legends",
    "overwatch",
    "守望先锋",
    "原神",
    "崩坏",
    "绝区零",
    "elden ring",
    "艾尔登法环",
    "palworld",
    "幻兽帕鲁",
)

WATCHING_TITLE_KEYWORDS = (
    "youtube",
    "netflix",
    "bilibili",
    "哔哩哔哩",
    "b站",
    "腾讯视频",
    "爱奇艺",
    "优酷",
    "芒果tv",
    "acfun",
    "西瓜视频",
    "抖音",
    "tiktok",
    "prime video",
    "disney+",
    "hulu",
    "potplayer",
    "vlc",
    "番剧",
    "电视剧",
    "电影",
    "动漫",
    "动画",
    "追剧",
)

EPISODE_PATTERNS = (
    re.compile(r"第\s*\d+\s*[集话話]", re.IGNORECASE),
    re.compile(r"\bS\d{1,2}E\d{1,2}\b", re.IGNORECASE),
    re.compile(r"\bepisode\s+\d+\b", re.IGNORECASE),
)


@dataclass(frozen=True)
class ForegroundWindow:
    hwnd: int
    process_name: str
    process_path: str
    window_title: str
    is_fullscreen: bool


def create_empty_activity_state(activity_code: str = ACTIVITY_UNKNOWN) -> Dict[str, Any]:
    if activity_code not in ACTIVITY_NAME_MAP:
        activity_code = ACTIVITY_UNKNOWN
    return {
        "activity_code": activity_code,
        "activity_name": ACTIVITY_NAME_MAP[activity_code],
        "description": "",
        "tags": [],
        "confidence": 0.0,
        "duration": 0.0,
        "need_response": False,
        "suggestion": "",
        "source": [],
        "app_name": "",
        "process_name": "",
        "window_title": "",
        "is_fullscreen": False,
    }


class ComputerActivityDetector:
    """Foreground-window based computer activity detector."""

    def __init__(self, min_comment_duration: float = 45.0):
        self.min_comment_duration = max(0.0, float(min_comment_duration))
        self._activity_since = time.time()
        self._last_signature = ""
        self._last_state: Dict[str, Any] = create_empty_activity_state()

    def get_state(self) -> Dict[str, Any]:
        now = time.time()
        window = self._read_foreground_window()
        if window is None:
            state = create_empty_activity_state(ACTIVITY_UNKNOWN)
            state.update(
                {
                    "description": "暂时无法读取前台窗口信息。",
                    "source": ["foreground_window_unavailable"],
                }
            )
            self._last_state = state
            return dict(state)

        state = classify_window_activity(
            process_name=window.process_name,
            window_title=window.window_title,
            is_fullscreen=window.is_fullscreen,
        )
        signature = self._signature_for(state)
        if signature != self._last_signature:
            self._last_signature = signature
            self._activity_since = now

        duration = max(0.0, now - self._activity_since)
        state["duration"] = round(duration, 2)
        state["need_response"] = (
            state["activity_code"] in COMMENTABLE_ACTIVITIES
            and duration >= self.min_comment_duration
            and state["confidence"] >= 0.58
        )
        state["suggestion"] = build_activity_suggestion(state)
        self._last_state = dict(state)
        return state

    def _read_foreground_window(self) -> Optional[ForegroundWindow]:
        if not (win32gui and win32process):
            return None
        try:
            hwnd = int(win32gui.GetForegroundWindow())
            if not hwnd:
                return None
            title = str(win32gui.GetWindowText(hwnd) or "").strip()
            _thread_id, pid = win32process.GetWindowThreadProcessId(hwnd)
            process_path = _process_path_from_pid(pid)
            process_name = os.path.basename(process_path).strip()
            is_fullscreen = _is_window_fullscreen(hwnd)
            return ForegroundWindow(
                hwnd=hwnd,
                process_name=process_name,
                process_path=process_path,
                window_title=title,
                is_fullscreen=is_fullscreen,
            )
        except Exception:
            return None

    @staticmethod
    def _signature_for(state: Dict[str, Any]) -> str:
        title_key = _compact_title(str(state.get("window_title", "")))
        process_name = str(state.get("process_name", "")).lower()
        return f"{state.get('activity_code')}|{process_name}|{title_key}"


def classify_window_activity(
    process_name: str = "",
    window_title: str = "",
    is_fullscreen: bool = False,
) -> Dict[str, Any]:
    """Classify a foreground window into a coarse computer activity state."""
    process = _normalize_process_name(process_name)
    title = (window_title or "").strip()
    haystack = f"{process} {title}".lower()
    tags: list[str] = []
    source = ["foreground_window"]

    if not process and not title:
        return create_empty_activity_state(ACTIVITY_IDLE)

    if process in VIDEO_PLAYER_PROCESSES or _contains_any(haystack, WATCHING_TITLE_KEYWORDS) or _matches_any(title, EPISODE_PATTERNS):
        code = ACTIVITY_WATCHING
        confidence = 0.86 if process in VIDEO_PLAYER_PROCESSES else 0.78
        tags.extend(["视频", "陪看"])
    elif process in KNOWN_GAME_PROCESSES or _contains_any(haystack, GAME_TITLE_KEYWORDS):
        code = ACTIVITY_GAMING
        confidence = 0.88 if process in KNOWN_GAME_PROCESSES else 0.78
        tags.extend(["游戏", "陪玩"])
    elif is_fullscreen and process not in BROWSER_PROCESSES | VIDEO_PLAYER_PROCESSES | CODING_PROCESSES | OFFICE_PROCESSES:
        code = ACTIVITY_GAMING
        confidence = 0.62
        tags.extend(["全屏", "可能是游戏"])
    elif process in CHAT_PROCESSES:
        code = ACTIVITY_CHATTING
        confidence = 0.82
        tags.append("聊天")
    elif process in CODING_PROCESSES:
        code = ACTIVITY_CODING
        confidence = 0.84
        tags.append("编程")
    elif process in OFFICE_PROCESSES:
        code = ACTIVITY_WORKING
        confidence = 0.82
        tags.append("办公")
    elif process in BROWSER_PROCESSES:
        code = ACTIVITY_BROWSING
        confidence = 0.68
        tags.append("网页")
    else:
        code = ACTIVITY_UNKNOWN
        confidence = 0.42
        tags.append("前台窗口")

    if is_fullscreen and "全屏" not in tags:
        tags.append("全屏")

    state = create_empty_activity_state(code)
    state.update(
        {
            "description": _describe_activity(code, process, title, is_fullscreen),
            "tags": tags[:6],
            "confidence": round(confidence, 2),
            "source": source,
            "app_name": _friendly_app_name(process, title),
            "process_name": process,
            "window_title": title,
            "is_fullscreen": bool(is_fullscreen),
        }
    )
    return state


def build_companion_event(state: Dict[str, Any]) -> Dict[str, Any]:
    """Convert an activity state to a Team C proactive event."""
    if not isinstance(state, dict):
        return {}
    activity_code = str(state.get("activity_code", "") or "")
    if activity_code not in COMMENTABLE_ACTIVITIES:
        return {}
    return {
        "event_type": "computer_activity_comment",
        "activity_code": activity_code,
        "activity_name": state.get("activity_name", ACTIVITY_NAME_MAP.get(activity_code, "")),
        "app_name": state.get("app_name", ""),
        "process_name": state.get("process_name", ""),
        "window_title": state.get("window_title", ""),
        "duration": state.get("duration", 0.0),
        "confidence": state.get("confidence", 0.0),
        "tags": state.get("tags", []),
        "suggestion": state.get("suggestion", build_activity_suggestion(state)),
        "need_response": True,
        "state_code": "normal",
    }


def build_activity_suggestion(state: Dict[str, Any]) -> str:
    activity_code = str(state.get("activity_code", "") or "")
    title = _short_title(str(state.get("window_title", "") or ""))
    target = f"《{title}》" if title else "当前内容"
    if activity_code == ACTIVITY_GAMING:
        return (
            f"用户正在玩游戏，前台内容是{target}。"
            "请像坐在旁边陪朋友打游戏一样点评一句，轻松、短、别指挥太多，"
            "可以夸操作、吐槽局势或提醒稳一点。"
        )
    if activity_code == ACTIVITY_WATCHING:
        return (
            f"用户正在看剧或视频，前台内容是{target}。"
            "请像一起看剧的朋友一样点评一句，轻松、短、不要剧透，"
            "可以说这个氛围、反转或角色有意思。"
        )
    return "根据用户当前电脑状态，主动说一句自然、简短的话。"


def build_local_companion_comment(state: Dict[str, Any]) -> str:
    """Local fallback when the LLM path is unavailable."""
    activity_code = str(state.get("activity_code", "") or "")
    title = _short_title(str(state.get("window_title", "") or ""))
    target = f"《{title}》" if title else "这个"

    if activity_code == ACTIVITY_GAMING:
        options = [
            f"{target}这局感觉有点上头，稳住稳住，精彩的地方要来了。",
            f"这个节奏不错呀，先别急，像朋友在旁边给你递一口气。",
            f"我坐旁边看着呢，刚刚这波很有戏，继续打得漂亮一点。",
        ]
    elif activity_code == ACTIVITY_WATCHING:
        options = [
            f"{target}这个氛围挺会抓人的，我也有点想知道后面怎么转。",
            f"这段感觉要出事了呀，我先安静陪你看，精彩了再小声说。",
            f"这剧情有点会钓人，先别划走，我们看看它怎么圆回来。",
        ]
    else:
        options = ["我在旁边陪着你，当前节奏还挺舒服的。"]
    return random.choice(options)


def _process_path_from_pid(pid: int) -> str:
    if not (win32api and win32con and win32process):
        return ""
    access = getattr(win32con, "PROCESS_QUERY_INFORMATION", 0x0400) | getattr(win32con, "PROCESS_VM_READ", 0x0010)
    handle = None
    try:
        handle = win32api.OpenProcess(access, False, int(pid))
        return str(win32process.GetModuleFileNameEx(handle, 0) or "")
    except Exception:
        return ""
    finally:
        if handle:
            try:
                win32api.CloseHandle(handle)
            except Exception:
                pass


def _is_window_fullscreen(hwnd: int) -> bool:
    if not (win32gui and win32api and win32con):
        return False
    try:
        left, top, right, bottom = win32gui.GetWindowRect(hwnd)
        monitor = win32api.MonitorFromWindow(hwnd, win32con.MONITOR_DEFAULTTONEAREST)
        info = win32api.GetMonitorInfo(monitor)
        mon_left, mon_top, mon_right, mon_bottom = info.get("Monitor", (0, 0, 0, 0))
        return (
            left <= mon_left + 2
            and top <= mon_top + 2
            and right >= mon_right - 2
            and bottom >= mon_bottom - 2
        )
    except Exception:
        return False


def _normalize_process_name(process_name: str) -> str:
    return os.path.basename(process_name or "").strip().lower()


def _contains_any(text: str, keywords: Iterable[str]) -> bool:
    return any(keyword.lower() in text for keyword in keywords if keyword)


def _matches_any(text: str, patterns: Iterable[re.Pattern[str]]) -> bool:
    return any(pattern.search(text or "") for pattern in patterns)


def _friendly_app_name(process: str, title: str) -> str:
    if process:
        stem = os.path.splitext(process)[0]
        return stem.replace("_", " ").strip()
    return _short_title(title)


def _describe_activity(code: str, process: str, title: str, is_fullscreen: bool) -> str:
    app = _friendly_app_name(process, title) or "前台应用"
    name = ACTIVITY_NAME_MAP.get(code, ACTIVITY_NAME_MAP[ACTIVITY_UNKNOWN])
    title_part = f"，窗口标题是“{_short_title(title)}”" if title else ""
    screen_part = "，处于全屏状态" if is_fullscreen else ""
    return f"检测到电脑前台状态：{name}；应用为 {app}{title_part}{screen_part}。"


def _short_title(title: str, max_len: int = 36) -> str:
    cleaned = re.sub(r"\s+", " ", title or "").strip()
    cleaned = re.sub(r"\s+-\s+(Google Chrome|Microsoft Edge|Mozilla Firefox)$", "", cleaned, flags=re.IGNORECASE)
    if len(cleaned) <= max_len:
        return cleaned
    return cleaned[: max_len - 1].rstrip() + "…"


def _compact_title(title: str) -> str:
    short = _short_title(title, max_len=24).lower()
    return re.sub(r"[^0-9a-zA-Z\u4e00-\u9fff]+", "", short)
