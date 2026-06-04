"""
CloudPanel: PySide6 QWidget for cloud co-creation UI.

Provides room_id input, join/sync buttons, pet status display, and recent events.

# TODO: Fully integrate with SharedPetRoomManager and EchoTeamDInterface.
# TODO: Add real button callbacks once cloud service is ready.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class CloudPanel(QWidget):
    """
    Cloud co-creation settings panel.

    This panel will allow users to:
    - Join/create a shared pet room.
    - Sync pet state manually.
    - View the remote pet's level / exp / coins / affection.
    - Browse recent pet interaction events from other room members.

    # TODO: Wire up signals with SharedPetRoomManager.
    """

    # Signals for integration
    join_room_requested = Signal(str)  # room_id
    sync_requested = Signal()
    leave_room_requested = Signal()

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._room_id = ""
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        # ── Room section ──
        room_layout = QHBoxLayout()
        room_layout.addWidget(QLabel("房间 ID:"))
        self._room_input = QLineEdit()
        self._room_input.setPlaceholderText("输入房间号或留空创建")
        room_layout.addWidget(self._room_input)
        self._join_btn = QPushButton("加入 / 创建")
        room_layout.addWidget(self._join_btn)
        layout.addLayout(room_layout)

        # ── Sync section ──
        sync_layout = QHBoxLayout()
        self._sync_btn = QPushButton("同步状态")
        sync_layout.addWidget(self._sync_btn)
        sync_layout.addStretch()
        self._room_label = QLabel("未加入房间")
        sync_layout.addWidget(self._room_label)
        layout.addLayout(sync_layout)

        # ── Pet status ──
        status_frame = QFrame()
        status_frame.setFrameShape(QFrame.StyledPanel)
        status_layout = QVBoxLayout(status_frame)
        status_layout.setContentsMargins(4, 4, 4, 4)

        self._level_label = QLabel("等级: --")
        self._exp_label = QLabel("经验: --")
        self._coins_label = QLabel("金币: --")
        self._mood_label = QLabel("心情: --")
        self._energy_label = QLabel("能量: --")
        self._intimacy_label = QLabel("亲密度: --")
        self._hunger_label = QLabel("饱食度: --")
        self._bond_label = QLabel("羁绊: --")

        for lbl in (
            self._level_label,
            self._exp_label,
            self._coins_label,
            self._mood_label,
            self._energy_label,
            self._intimacy_label,
            self._hunger_label,
            self._bond_label,
        ):
            status_layout.addWidget(lbl)

        layout.addWidget(status_frame)

        # ── Recent events ──
        events_label = QLabel("最近事件:")
        layout.addWidget(events_label)
        self._event_list = QListWidget()
        self._event_list.setMaximumHeight(150)
        layout.addWidget(self._event_list)

        # ── Signals (TODO) ──
        # self._join_btn.clicked.connect(self._on_join_clicked)
        # self._sync_btn.clicked.connect(lambda: self.sync_requested.emit())
        self._join_btn.clicked.connect(self._on_join_clicked)

    def _on_join_clicked(self) -> None:
        room_id = self._room_input.text().strip()
        if room_id:
            self._room_id = room_id
            self._room_label.setText(f"房间: {room_id}")
            self.join_room_requested.emit(room_id)
        else:
            self._room_label.setText("请输入房间号")

    # ── Public update methods (called from outside) ──

    def update_pet_status(self, state_dict: Dict[str, Any]) -> None:
        """
        Update the displayed pet status.

        :param state_dict: dict with keys like level, exp, coins, mood, energy, intimacy, etc.
        """
        self._level_label.setText(f"等级: {state_dict.get('level', '--')}")
        self._exp_label.setText(f"经验: {state_dict.get('exp', '--')}")
        self._coins_label.setText(f"金币: {state_dict.get('coins', '--')}")
        self._mood_label.setText(f"心情: {state_dict.get('mood', '--')}")
        self._energy_label.setText(f"能量: {state_dict.get('energy', '--')}")
        self._intimacy_label.setText(f"亲密度: {state_dict.get('intimacy', '--')}")
        self._hunger_label.setText(f"饱食度: {state_dict.get('hunger', '--')}")
        self._bond_label.setText(f"羁绊: {state_dict.get('bond_score', '--')}")

    def add_event(self, event_text: str) -> None:
        """Add a single event line to the list."""
        item = QListWidgetItem(event_text)
        self._event_list.insertItem(0, item)
        while self._event_list.count() > 50:
            self._event_list.takeItem(self._event_list.count() - 1)

    def set_events(self, events: List[str]) -> None:
        """Replace the event list."""
        self._event_list.clear()
        for ev in events[-50:]:
            self._event_list.addItem(ev)

    def set_room_id(self, room_id: str) -> None:
        self._room_id = room_id
        self._room_input.setText(room_id)
        self._room_label.setText(f"房间: {room_id}" if room_id else "未加入房间")

    def get_room_id(self) -> str:
        return self._room_id
