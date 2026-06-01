"""
FeedbackBubble: light-weight non-blocking feedback for level-ups,
feeding, sync success, etc.

When the UI is simple, falls back to printing to console.
"""

from __future__ import annotations

from typing import Any, Optional

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QLabel, QWidget


def show_feedback_message(
    parent: Optional[QWidget],
    text: str,
    duration_ms: int = 3000,
    position: Optional[str] = None,
) -> None:
    """
    Display a floating feedback message near the parent widget.

    Falls back to print() if no parent or if the parent is not visible.

    :param parent:        parent QWidget (e.g. DesktopPet window)
    :param text:          message text to display
    :param duration_ms:   how long to show before auto-hide (ms)
    :param position:      "top", "bottom", or None (centered)
    """
    if parent is None or not parent.isVisible():
        print(f"[FeedbackBubble] {text}")
        return

    label = QLabel(text, parent)
    label.setWindowFlags(
        Qt.ToolTip | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
    )
    label.setAttribute(Qt.WA_ShowWithoutActivating)
    label.setStyleSheet(
        """
        QLabel {
            background-color: rgba(0, 0, 0, 180);
            color: white;
            padding: 8px 16px;
            border-radius: 12px;
            font-size: 14px;
        }
        """
    )
    label.adjustSize()

    # Position relative to parent
    pw = parent.width()
    ph = parent.height()
    lw = label.width()
    lh = label.height()
    if position == "top":
        x = (pw - lw) // 2
        y = 10
    elif position == "bottom":
        x = (pw - lw) // 2
        y = ph - lh - 10
    else:
        x = (pw - lw) // 2
        y = (ph - lh) // 2

    label.move(x, y)
    label.show()

    # Auto-dismiss after duration_ms
    def _dismiss() -> None:
        try:
            label.close()
            label.deleteLater()
        except RuntimeError:
            pass

    QTimer.singleShot(duration_ms, _dismiss)
