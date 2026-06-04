"""
PetMotionController: handles free-roaming, mouse-following, and edge-resting logic.

This module provides animation-like motion that can be plugged into DesktopPet.
Actual position updates happen via callbacks set on the DesktopPet instance.
"""

from __future__ import annotations

import math
import random
import time
from typing import Any, Callable, Dict, Optional, Tuple


class PetMotionController:
    """
    Controls the pet's on-screen motion behaviors:

    - Free-roaming:   pet moves randomly within the screen bounds.
    - Follow-mouse:   pet drifts toward the cursor position.
    - Edge-rest:      when idle or low energy, pet moves to a screen edge and rests.

    Usage:
        motion = PetMotionController()
        motion.set_move_callback(lambda x, y: print(f"Move to ({x}, {y})"))
        motion.set_enabled(True)
        # In your main loop:
        motion.tick()

    # TODO: Integrate with DesktopPet widget's actual window.move(x, y) API.
    """

    def __init__(self):
        self._enabled = False
        self._follow_mouse = False
        self._x: float = 100.0
        self._y: float = 100.0
        self._target_x: Optional[float] = None
        self._target_y: Optional[float] = None
        self._speed: float = 3.0  # pixels per tick
        self._screen_w: float = 1920.0
        self._screen_h: float = 1080.0
        self._last_tick = time.time()
        self._move_callback: Optional[Callable[[float, float], None]] = None
        self._idle_counter = 0
        self._resting = False

    def set_enabled(self, enabled: bool) -> None:
        """Enable or disable all motion behaviors."""
        self._enabled = bool(enabled)

    def set_follow_mouse(self, enabled: bool) -> None:
        """Enable or disable mouse-following behavior."""
        self._follow_mouse = bool(enabled)

    def set_screen_bounds(self, width: float, height: float) -> None:
        """Update screen dimensions for boundary clamping."""
        self._screen_w = max(100.0, float(width))
        self._screen_h = max(100.0, float(height))

    def set_position(self, x: float, y: float) -> None:
        """Directly set the pet's position."""
        self._x = max(0.0, min(self._screen_w, float(x)))
        self._y = max(0.0, min(self._screen_h, float(y)))

    def get_position(self) -> Tuple[float, float]:
        """Get current position."""
        return (self._x, self._y)

    def set_move_callback(self, callback: Optional[Callable[[float, float], None]]) -> None:
        """
        Register a callback to actually move the pet window.

        The callback receives (x, y) in screen coordinates.
        """
        self._move_callback = callback

    def set_speed(self, pixels_per_tick: float) -> None:
        """Set movement speed."""
        self._speed = max(0.5, float(pixels_per_tick))

    def set_mouse_position(self, mx: float, my: float) -> None:
        """
        Update the known mouse position for follow-mouse behavior.

        Call from your app's mouse-move event handler.
        """
        self._mouse_x = float(mx)
        self._mouse_y = float(my)

    def tick(self) -> None:
        """
        Advance motion by one tick (call ~30-60 times per second).

        If not enabled, does nothing.
        """
        if not self._enabled:
            return

        self._idle_counter += 1

        if self._follow_mouse:
            # Move toward the last-known mouse position
            self._move_toward(getattr(self, "_mouse_x", self._x), getattr(self, "_mouse_y", self._y))
        elif self._resting:
            # Stay at edge; occasionally twitch
            if self._idle_counter % 120 == 0:
                self._apply_move(self._x, self._y)  # "twitch" in place
        else:
            # Free-roaming: wander randomly
            if self._target_x is None or self._distance_to_target() < 10.0:
                self._pick_random_target()
            self._move_toward(self._target_x, self._target_y)

        self._last_tick = time.time()

    def enter_rest_mode(self) -> None:
        """Move to a screen edge and stop roaming."""
        self._resting = True
        self._follow_mouse = False
        # Choose a random edge position
        edge_x = random.choice([20.0, self._screen_w - 160.0])
        edge_y = self._screen_h - 180.0
        self._target_x = edge_x
        self._target_y = edge_y

    def exit_rest_mode(self) -> None:
        """Resume normal roaming."""
        self._resting = False
        self._target_x = None

    def is_resting(self) -> bool:
        return self._resting

    # ── Internal helpers ─────────────────────────────────────

    def _move_toward(self, tx: float, ty: float) -> None:
        dx = float(tx) - self._x
        dy = float(ty) - self._y
        dist = math.hypot(dx, dy)
        if dist < 1.0:
            return
        step = min(self._speed, dist)
        self._x += (dx / dist) * step
        self._y += (dy / dist) * step
        self._x = max(0.0, min(self._screen_w, self._x))
        self._y = max(0.0, min(self._screen_h - 50.0, self._y))
        self._apply_move(self._x, self._y)

    def _pick_random_target(self) -> None:
        margin = 80.0
        self._target_x = random.uniform(margin, self._screen_w - margin)
        self._target_y = random.uniform(margin, self._screen_h - margin - 80.0)

    def _distance_to_target(self) -> float:
        if self._target_x is None:
            return 0.0
        return math.hypot(self._x - self._target_x, self._y - self._target_y)

    def _apply_move(self, x: float, y: float) -> None:
        if self._move_callback:
            try:
                self._move_callback(x, y)
            except Exception as exc:
                print(f"[PetMotionController] move callback error: {exc}")
