"""
Small helpers for streaming short feedback text into UI bubbles.
"""

from __future__ import annotations

import time
from typing import Callable, Optional

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QLabel, QWidget


def _stream_to_callback(
    message: str,
    ui_callback: Callable[[str], None],
    *,
    stream: bool = True,
    delay: float = 0.015,
) -> str:
    if not stream:
        ui_callback(message)
        return message
    for char in message:
        ui_callback(char)
        if delay > 0:
            time.sleep(delay)
    return message


def _show_parent_toast(parent: QWidget, message: str, *, duration_ms: int = 2200) -> None:
    toast = QLabel(message, parent)
    toast.setStyleSheet(
        "background-color: rgba(30, 41, 59, 220); color: white;"
        "border-radius: 10px; padding: 10px 18px; font-size: 14px;"
    )
    toast.setAlignment(Qt.AlignmentFlag.AlignCenter)
    toast.adjustSize()
    x = max(16, (parent.width() - toast.width()) // 2)
    y = max(16, parent.height() - toast.height() - 36)
    toast.move(x, y)
    toast.raise_()
    toast.show()

    def _hide() -> None:
        try:
            toast.hide()
            toast.deleteLater()
        except RuntimeError:
            pass

    QTimer.singleShot(duration_ms, _hide)


def show_feedback_message(
    parent_or_text: QWidget | str,
    text_or_callback: str | Callable[[str], None] | None = None,
    ui_callback: Callable[[str], None] | None = None,
    *,
    stream: bool = True,
    delay: float = 0.015,
) -> str:
    """
    显示反馈文案。

    - ``show_feedback_message(parent, text)``：在 parent 上显示短暂气泡（云端同步等）。
    - ``show_feedback_message(text, ui_callback)``：流式写入聊天气泡回调（桌宠对话）。
    """
    if isinstance(parent_or_text, str):
        text = str(parent_or_text or "").strip()
        if not text:
            return text
        if callable(text_or_callback):
            return _stream_to_callback(text, text_or_callback, stream=stream, delay=delay)
        if ui_callback is not None:
            return _stream_to_callback(text, ui_callback, stream=stream, delay=delay)
        return text

    parent = parent_or_text
    message = str(text_or_callback or "").strip()
    if not message:
        return message
    _show_parent_toast(parent, message)
    if ui_callback is not None:
        return _stream_to_callback(message, ui_callback, stream=stream, delay=delay)
    return message
