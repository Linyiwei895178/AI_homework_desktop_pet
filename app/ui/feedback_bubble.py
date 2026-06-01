"""
Small helpers for streaming short feedback text into UI bubbles.
"""

from __future__ import annotations

import time
from typing import Callable


def show_feedback_message(
    text: str,
    ui_callback: Callable[[str], None] | None,
    *,
    stream: bool = True,
    delay: float = 0.015,
) -> str:
    """Send text to a bubble callback and return the same text for TTS."""
    message = str(text or "").strip()
    if not message or ui_callback is None:
        return message
    if not stream:
        ui_callback(message)
        return message
    for char in message:
        ui_callback(char)
        if delay > 0:
            time.sleep(delay)
    return message
