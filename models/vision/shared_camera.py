"""Shared camera capture for vision modules that need the same webcam."""

from __future__ import annotations

import copy
import threading
import time
from typing import Any, Optional


class SharedCameraCapture:
    """Open one OpenCV camera and expose the latest frame to multiple detectors."""

    def __init__(
        self,
        camera_index: int = 0,
        width: int = 640,
        height: int = 480,
        read_interval: float = 0.03,
    ):
        self.camera_index = int(camera_index)
        self.width = int(width)
        self.height = int(height)
        self.read_interval = max(0.01, float(read_interval))

        self._lock = threading.RLock()
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._cv2: Any = None
        self._cap: Any = None
        self._latest_frame: Any = None
        self._last_error: str = ""
        self._last_frame_at: float = 0.0

    def start(self) -> bool:
        """Start the camera reader thread. Return False when camera is unavailable."""
        if self._running:
            return True

        try:
            import cv2  # type: ignore
        except Exception as exc:
            self._last_error = f"OpenCV 导入失败: {exc}"
            return False

        try:
            cap = cv2.VideoCapture(self.camera_index)
            if not cap or not cap.isOpened():
                if cap:
                    cap.release()
                self._last_error = "摄像头无法打开，可能被占用或没有权限。"
                return False

            try:
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
                cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            except Exception:
                pass

            self._cv2 = cv2
            self._cap = cap
            self._running = True
            self._thread = threading.Thread(target=self._read_loop, daemon=True)
            self._thread.start()
            return True
        except Exception as exc:
            self._last_error = f"摄像头启动失败: {exc}"
            self.stop()
            return False

    def stop(self) -> None:
        """Stop the reader and release the camera."""
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
        try:
            if self._cap is not None:
                self._cap.release()
        except Exception:
            pass
        self._cap = None
        self._thread = None

    def is_running(self) -> bool:
        return self._running

    def get_frame(self) -> Any:
        """Return a copy of the latest frame, or None if no frame is available."""
        with self._lock:
            if self._latest_frame is None:
                return None
            try:
                return self._latest_frame.copy()
            except Exception:
                return copy.deepcopy(self._latest_frame)

    def last_error(self) -> str:
        return self._last_error

    def last_frame_at(self) -> float:
        with self._lock:
            return self._last_frame_at

    def _read_loop(self) -> None:
        while self._running and self._cap is not None:
            try:
                ok, frame = self._cap.read()
                if ok and frame is not None:
                    with self._lock:
                        self._latest_frame = frame.copy()
                        self._last_frame_at = time.time()
                        self._last_error = ""
                else:
                    self._last_error = "摄像头暂时没有读到画面。"
            except Exception as exc:
                self._last_error = f"摄像头读取失败: {exc}"

            time.sleep(self.read_interval)


__all__ = ["SharedCameraCapture"]
