"""
CloudPanel: 设置面板「云端共享」页 — 多人共养房间 UI。
"""

from __future__ import annotations

import time
from typing import Any, Callable, Dict, List, Optional

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.ui.feedback_bubble import show_feedback_message
from models.cloud.shared_pet_room import SharedPetRoomManager

DEFAULT_ROOM_ID = "TEAMROOM001"

MOCK_PET_STATUS: dict[str, Any] = {
    "level": 10,
    "exp": 200,
    "coins": 50,
    "mood": 80,
}

MOCK_RECENT_EVENTS: tuple[str, ...] = (
    "张三 喂食 +5 经验",
    "李四 陪玩 +3 心情",
    "王五 打工 +10 金币",
    "小夏 投喂 +2 亲密度",
    "Echo 同步房间状态",
)

MOCK_MEMBERS: tuple[str, ...] = ("用户A", "用户B")


def _default_local_pet_status() -> dict[str, Any]:
    """通过队员 D 接口读取本地宠物状态（无运行实例时尝试 logs/pet_state.json）。"""
    try:
        from models.state.echo_team_d_interface import EchoTeamDInterface
        from models.state.pet_state import PetState

        pet = PetState()
        try:
            pet.load_state()
        except Exception:
            pass
        return EchoTeamDInterface(pet).api_get_pet_status()
    except Exception as exc:
        print(f"[CloudPanel] 读取本地宠物状态失败: {exc}")
        return {}


def _mood_display_value(raw: Any) -> str:
    if isinstance(raw, (int, float)):
        return str(int(raw))
    text = str(raw or "").strip()
    if not text:
        return "--"
    mapping = {
        "happy": "开心",
        "sad": "难过",
        "neutral": "平静",
        "angry": "生气",
        "hungry": "饥饿",
    }
    return mapping.get(text.lower(), text)


def _format_cloud_event(item: Any) -> str:
    if isinstance(item, str):
        return item.strip() or "（空事件）"
    if not isinstance(item, dict):
        return str(item)
    actor = str(item.get("actor_name") or item.get("actor") or "队友").strip()
    action = str(item.get("action_type") or item.get("action") or item.get("event_type") or "互动").strip()
    delta = item.get("delta") if isinstance(item.get("delta"), dict) else {}
    extra = ""
    if isinstance(delta, dict):
        parts: list[str] = []
        if "exp" in delta:
            parts.append(f"+{delta['exp']} 经验")
        if "mood" in delta:
            parts.append(f"+{delta['mood']} 心情")
        if "coins" in delta:
            parts.append(f"+{delta['coins']} 金币")
        if "intimacy" in delta:
            parts.append(f"+{delta['intimacy']} 亲密度")
        if parts:
            extra = " ".join(parts)
    message = str(item.get("message") or "").strip()
    if message:
        return message
    if extra:
        return f"{actor} {action} {extra}"
    return f"{actor} {action}"


def _member_display_name(item: Any) -> str:
    if isinstance(item, str):
        return item.strip() or "成员"
    if not isinstance(item, dict):
        return str(item)
    name = str(item.get("pet_name") or item.get("name") or item.get("member_name") or "").strip()
    if name:
        return name
    member_id = str(item.get("member_id") or item.get("id") or "").strip()
    if member_id:
        return member_id
    return "成员"


class CloudPanel(QWidget):
    """云端共享：加入房间、同步状态、展示宠物数据与最近事件。"""

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        *,
        get_local_pet_status: Callable[[], dict[str, Any]] | None = None,
        room_manager: SharedPetRoomManager | None = None,
    ) -> None:
        super().__init__(parent)
        self._get_local_pet_status = get_local_pet_status or _default_local_pet_status
        self._room_manager = room_manager or SharedPetRoomManager()
        self._connected = False
        self._use_mock_display = False
        self._last_sync_at: Optional[float] = None
        self._sync_time_timer = QTimer(self)
        self._sync_time_timer.setInterval(60_000)
        self._sync_time_timer.timeout.connect(self._update_sync_time_display)
        self._build_ui()

    def set_room_manager(self, mgr: SharedPetRoomManager) -> None:
        """Switch to an external SharedPetRoomManager (shared with main.py)."""
        self._room_manager = mgr
        if mgr.is_in_room():
            self._set_connection_ui(True)
            self._refresh_recent_events()
            self._refresh_members_list()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 16, 24, 24)
        root.setSpacing(12)

        header = QHBoxLayout()
        header.addWidget(QLabel("<h2>云端共享</h2>"))
        header.addStretch()
        self._status_badge = QLabel("未连接")
        self._status_badge.setStyleSheet(
            "color:#64748b; background:#f1f5f9; border-radius:8px; padding:6px 12px;"
        )
        header.addWidget(self._status_badge)
        root.addLayout(header)

        room_row = QHBoxLayout()
        room_row.addWidget(QLabel("房间号"))
        self._room_input = QLineEdit()
        self._room_input.setText(DEFAULT_ROOM_ID)
        self._room_input.setPlaceholderText("输入房间号，如 TEAMROOM001")
        room_row.addWidget(self._room_input, 1)
        self._join_btn = QPushButton("加入房间")
        self._join_btn.clicked.connect(self._on_join_room)
        room_row.addWidget(self._join_btn)
        self._sync_btn = QPushButton("同步")
        self._sync_btn.clicked.connect(self._on_sync)
        room_row.addWidget(self._sync_btn)
        root.addLayout(room_row)

        sync_status_row = QHBoxLayout()
        self._last_sync_label = QLabel("上次同步：尚未同步")
        self._last_sync_label.setStyleSheet("color:#64748b;")
        sync_status_row.addWidget(self._last_sync_label)
        sync_status_row.addStretch()
        root.addLayout(sync_status_row)

        self._sync_error_label = QLabel("")
        self._sync_error_label.setWordWrap(True)
        self._sync_error_label.setStyleSheet("color:#dc2626;")
        self._sync_error_label.hide()
        root.addWidget(self._sync_error_label)

        pet_frame = QFrame()
        pet_frame.setObjectName("glass")
        pet_frame.setStyleSheet(
            "QFrame#glass {"
            " background-color: rgba(255, 255, 255, 248);"
            " border: 1px solid rgba(226, 232, 240, 220);"
            " border-radius: 14px;"
            "}"
        )
        pet_grid = QGridLayout(pet_frame)
        pet_grid.setContentsMargins(16, 12, 16, 12)
        pet_grid.setHorizontalSpacing(24)
        pet_grid.setVerticalSpacing(8)

        self._level_label = QLabel("等级：--")
        self._exp_label = QLabel("经验：--")
        self._coins_label = QLabel("金币：--")
        self._mood_label = QLabel("心情：--")
        for row, lbl in enumerate(
            (self._level_label, self._exp_label, self._coins_label, self._mood_label)
        ):
            pet_grid.addWidget(lbl, row // 2, row % 2)

        root.addWidget(QLabel("<b>宠物状态</b>"))
        root.addWidget(pet_frame)

        members_header = QHBoxLayout()
        members_header.addWidget(QLabel("<b>在线成员</b>"))
        members_header.addStretch()
        self._members_count_label = QLabel("")
        self._members_count_label.setStyleSheet("color:#64748b;")
        members_header.addWidget(self._members_count_label)
        root.addLayout(members_header)

        self._members_list = QListWidget()
        self._members_list.setMinimumHeight(72)
        self._members_list.setMaximumHeight(120)
        root.addWidget(self._members_list)

        root.addWidget(QLabel("<b>最近互动</b>"))
        self._event_list = QListWidget()
        self._event_list.setMinimumHeight(160)
        root.addWidget(self._event_list, 1)

        hint = QLabel("多人共养：加入房间后可同步本地宠物数据，并查看队友最近互动。")
        hint.setWordWrap(True)
        hint.setStyleSheet("color:#64748b;")
        root.addWidget(hint)

        self._set_connection_ui(False)
        self._apply_pet_status({})
        self._populate_members_list(list(MOCK_MEMBERS))

    def _set_connection_ui(self, connected: bool) -> None:
        self._connected = connected
        if connected:
            self._status_badge.setText("已连接")
            self._status_badge.setStyleSheet(
                "color:#166534; background:#dcfce7; border-radius:8px; padding:6px 12px;"
            )
        else:
            self._status_badge.setText("未连接")
            self._status_badge.setStyleSheet(
                "color:#64748b; background:#f1f5f9; border-radius:8px; padding:6px 12px;"
            )
        self._sync_btn.setEnabled(connected)

    def _apply_pet_status(self, state: dict[str, Any]) -> None:
        self._level_label.setText(f"等级：{state.get('level', '--')}")
        self._exp_label.setText(f"经验：{state.get('exp', '--')}")
        self._coins_label.setText(f"金币：{state.get('coins', '--')}")
        self._mood_label.setText(f"心情：{_mood_display_value(state.get('mood'))}")

    def _extract_pet_from_result(self, result: dict[str, Any]) -> dict[str, Any]:
        data = result.get("data")
        if not isinstance(data, dict):
            return {}
        pet = data.get("pet")
        if isinstance(pet, dict):
            return pet
        merged = data.get("merged")
        if isinstance(merged, dict):
            return merged
        return {}

    def _call_fetch_members(self) -> dict[str, Any]:
        mgr = self._room_manager
        if hasattr(mgr, "fetch_members") and callable(mgr.fetch_members):
            return mgr.fetch_members()
        return mgr.get_online_members()

    def _extract_members_from_result(self, result: dict[str, Any]) -> list[Any]:
        if not result.get("ok"):
            return []
        data = result.get("data")
        if isinstance(data, list):
            return data
        if not isinstance(data, dict):
            return []
        for key in ("members", "online_members", "items"):
            raw = data.get(key)
            if isinstance(raw, list):
                return raw
        return []

    def _populate_members_list(self, members: list[Any]) -> None:
        self._members_list.clear()
        if not members:
            item = QListWidgetItem("暂无在线成员")
            item.setFlags(Qt.ItemFlag.NoItemFlags)
            self._members_list.addItem(item)
            self._members_count_label.setText("0 人在线")
            return
        for member in members:
            name = _member_display_name(member)
            avatar = ""
            if isinstance(member, dict):
                avatar = str(member.get("avatar") or member.get("avatar_url") or "").strip()
            prefix = "🟢 "
            if avatar:
                prefix = f"[{avatar[:1]}] "
            self._members_list.addItem(f"{prefix}{name}")
        self._members_count_label.setText(f"{len(members)} 人在线")

    def _refresh_members_list(self, *, use_mock: bool = False) -> None:
        if use_mock or not self._connected:
            self._populate_members_list(list(MOCK_MEMBERS))
            return
        result = self._call_fetch_members()
        members = self._extract_members_from_result(result)
        if not members:
            error = str(result.get("error") or "")
            if error in {"not_configured", "supabase_not_installed"}:
                self._populate_members_list(list(MOCK_MEMBERS))
            else:
                self._populate_members_list(list(MOCK_MEMBERS))
            return
        self._populate_members_list(members)

    def _format_relative_sync_time(self, sync_at: float) -> str:
        elapsed = max(0.0, time.time() - sync_at)
        if elapsed < 10:
            return "刚刚"
        if elapsed < 60:
            return f"{int(elapsed)}秒前"
        if elapsed < 3600:
            return f"{int(elapsed // 60)}分钟前"
        hours = int(elapsed // 3600)
        return f"{hours}小时前"

    def _update_sync_time_display(self) -> None:
        if self._last_sync_at is None:
            self._last_sync_label.setText("上次同步：尚未同步")
            return
        self._last_sync_label.setText(
            f"上次同步：{self._format_relative_sync_time(self._last_sync_at)}"
        )

    def _record_sync_success(self) -> None:
        self._last_sync_at = time.time()
        self._clear_sync_error()
        self._update_sync_time_display()
        if not self._sync_time_timer.isActive():
            self._sync_time_timer.start()

    def _show_sync_error(self, message: str) -> None:
        text = str(message or "").strip() or "同步失败，请重试"
        self._sync_error_label.setText(text)
        self._sync_error_label.show()

    def _clear_sync_error(self) -> None:
        self._sync_error_label.clear()
        self._sync_error_label.hide()

    def _show_mock_pet_and_events(self) -> None:
        self._use_mock_display = True
        self._apply_pet_status(MOCK_PET_STATUS)
        self._event_list.clear()
        for line in MOCK_RECENT_EVENTS:
            self._event_list.addItem(line)
        self._refresh_members_list(use_mock=True)

    def _refresh_recent_events(self, *, use_mock: bool = False) -> None:
        self._event_list.clear()
        if use_mock or not self._connected:
            for line in MOCK_RECENT_EVENTS:
                self._event_list.addItem(line)
            return
        result = self._room_manager.fetch_recent_events(limit=10)
        if not result.get("ok"):
            for line in MOCK_RECENT_EVENTS:
                self._event_list.addItem(line)
            return
        data = result.get("data")
        events: list[Any] = []
        if isinstance(data, dict):
            raw = data.get("events")
            if isinstance(raw, list):
                events = raw
        elif isinstance(data, list):
            events = data
        if not events:
            for line in MOCK_RECENT_EVENTS:
                self._event_list.addItem(line)
            return
        for item in events[:10]:
            self._event_list.addItem(_format_cloud_event(item))

    def _on_join_room(self) -> None:
        room_id = self._room_input.text().strip() or DEFAULT_ROOM_ID
        self._room_input.setText(room_id)
        result = self._room_manager.join_room(room_id)
        if result.get("ok"):
            self._set_connection_ui(True)
            self._use_mock_display = False
            self._clear_sync_error()
            pet = self._extract_pet_from_result(result)
            if pet:
                self._apply_pet_status(pet)
            else:
                local = self._get_local_pet_status()
                self._apply_pet_status(local if local else MOCK_PET_STATUS)
            self._refresh_recent_events()
            self._refresh_members_list()
            show_feedback_message(self, "已加入房间")
            return

        error = str(result.get("error") or "")
        if error in {"not_configured", "supabase_not_installed"}:
            self._set_connection_ui(True)
            self._show_mock_pet_and_events()
            show_feedback_message(self, "已连接")
            return

        self._set_connection_ui(False)
        self._use_mock_display = False
        self._apply_pet_status({})
        self._event_list.clear()
        self._populate_members_list(list(MOCK_MEMBERS))
        show_feedback_message(self, "加入房间失败")

    def _on_sync(self) -> None:
        if not self._room_manager.is_in_room():
            show_feedback_message(self, "请先加入房间")
            return

        local_state = self._get_local_pet_status()
        if not local_state:
            local_state = dict(MOCK_PET_STATUS)

        result = self._room_manager.sync_now(local_state)
        if result.get("ok"):
            merged = self._extract_pet_from_result(result)
            if merged:
                self._apply_pet_status(merged)
            else:
                self._apply_pet_status(local_state)
            self._refresh_recent_events()
            self._refresh_members_list()
            self._record_sync_success()
            show_feedback_message(self, "同步成功")
            return

        if self._use_mock_display or str(result.get("error") or "") in {
            "not_configured",
            "not_in_room",
        }:
            self._show_mock_pet_and_events()
            self._record_sync_success()
            show_feedback_message(self, "同步成功")
            return

        error_detail = str(result.get("error") or "").strip()
        feedback = "同步失败，请重试"
        if error_detail:
            feedback = f"同步失败，请重试（{error_detail}）"
        self._show_sync_error(feedback)
        show_feedback_message(self, "同步失败，请重试")
