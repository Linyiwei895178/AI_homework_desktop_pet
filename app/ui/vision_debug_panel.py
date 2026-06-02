from __future__ import annotations

import time
from typing import Any, Callable, Optional

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class VisionDebugPanel(QWidget):
    """Standalone Qt panel for visual debugging of Team B camera perception."""

    visibility_changed = Signal(bool)

    def __init__(
        self,
        detector_getter: Optional[Callable[[], Any]] = None,
        gesture_getter: Optional[Callable[[], dict | None]] = None,
        camera_enabled_getter: Optional[Callable[[], bool]] = None,
        refresh_ms: int = 150,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._detector_getter = detector_getter
        self._gesture_getter = gesture_getter
        self._camera_enabled_getter = camera_enabled_getter
        self._refresh_ms = max(50, int(refresh_ms))

        self.setWindowTitle("Vision Debug Preview")
        self.resize(820, 680)

        self.image_label = QLabel("Waiting for camera frame...")
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setMinimumSize(640, 480)
        self.image_label.setStyleSheet(
            "QLabel { background: #050505; color: #d1d5db; border: 1px solid #374151; }"
        )

        self.info_label = QLabel("")
        self.info_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        self.info_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.info_label.setStyleSheet(
            "QLabel { color: #e5e7eb; background: #111827; padding: 8px; font-family: Consolas, monospace; }"
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)
        layout.addWidget(self.image_label, 1)
        layout.addWidget(self.info_label, 0)

        self._timer = QTimer(self)
        self._timer.setInterval(self._refresh_ms)
        self._timer.timeout.connect(self.update_from_detector)
        self._logged_waiting_frame = False
        self._logged_first_frame = False
        self._closing_for_cleanup = False

    def start(self) -> None:
        if not self._timer.isActive():
            self._timer.start()

    def stop(self) -> None:
        if self._timer.isActive():
            self._timer.stop()

    def shutdown(self) -> None:
        self._closing_for_cleanup = True
        self.stop()
        self.hide()
        self.close()
        self.deleteLater()

    def toggle_visible(self) -> None:
        if self.isVisible():
            self.hide()
            return
        self.show()
        self.raise_()
        self.activateWindow()
        self.update_from_detector()

    def update_from_detector(self) -> None:
        if not self.isVisible():
            return

        camera_enabled = True
        if self._camera_enabled_getter is not None:
            try:
                camera_enabled = bool(self._camera_enabled_getter())
            except Exception:
                camera_enabled = False

        if not camera_enabled:
            self._show_placeholder("Camera Off")
            self.info_label.setText("camera: off\nstate: unknown\nsource: camera_off")
            return

        detector = None
        if self._detector_getter is not None:
            try:
                detector = self._detector_getter()
            except Exception:
                detector = None

        if detector is None:
            self._log_waiting_frame_once()
            self._show_placeholder("Waiting for camera frame...")
            self.info_label.setText("detector: unavailable")
            return

        snapshot = self._read_snapshot(detector)
        frame = snapshot.get("frame")
        info = snapshot.get("info") or {}
        state = snapshot.get("state") or {}
        gesture_state = self._read_gesture_state()

        if frame is None:
            self._log_waiting_frame_once()
            self._show_placeholder("Waiting for camera frame...")
            self.info_label.setText(self._format_info(info, state, gesture_state))
            return

        self.set_frame(frame)
        self.info_label.setText(self._format_info(info, state, gesture_state))

    def set_frame(self, frame: Any) -> None:
        pixmap = self._frame_to_pixmap(frame)
        if pixmap is None:
            self._log_waiting_frame_once()
            self._show_placeholder("Waiting for camera frame...")
            return
        scaled = pixmap.scaled(
            self.image_label.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.image_label.setPixmap(scaled)
        self._log_first_frame_once()

    def closeEvent(self, event) -> None:  # noqa: N802 - Qt API name
        if self._closing_for_cleanup:
            super().closeEvent(event)
            return
        event.ignore()
        self.hide()

    def showEvent(self, event) -> None:  # noqa: N802 - Qt API name
        super().showEvent(event)
        self.visibility_changed.emit(True)

    def hideEvent(self, event) -> None:  # noqa: N802 - Qt API name
        super().hideEvent(event)
        self.visibility_changed.emit(False)

    def _read_snapshot(self, detector: Any) -> dict:
        getter = getattr(detector, "get_debug_snapshot", None)
        if callable(getter):
            try:
                snapshot = getter()
                if isinstance(snapshot, dict):
                    return snapshot
            except Exception:
                pass

        frame = None
        frame_getter = getattr(detector, "get_debug_frame", None)
        if callable(frame_getter):
            try:
                frame = frame_getter()
            except Exception:
                frame = None

        state = {}
        state_getter = getattr(detector, "get_state", None)
        if callable(state_getter):
            try:
                state = state_getter()
            except Exception:
                state = {}
        return {"frame": frame, "info": {}, "state": state}

    def _read_gesture_state(self) -> dict | None:
        if self._gesture_getter is None:
            return None
        try:
            state = self._gesture_getter()
            return state if isinstance(state, dict) else None
        except Exception:
            return None

    def _frame_to_pixmap(self, frame: Any) -> QPixmap | None:
        try:
            if frame.ndim != 3 or frame.shape[2] < 3:
                return None
            h, w, channels = frame.shape[:3]
            rgb = frame[:, :, :3][:, :, ::-1].copy()
            image = QImage(
                rgb.data,
                int(w),
                int(h),
                int(3 * w),
                QImage.Format.Format_RGB888,
            ).copy()
            return QPixmap.fromImage(image)
        except Exception:
            return None

    def _show_placeholder(self, text: str) -> None:
        self.image_label.setPixmap(QPixmap())
        self.image_label.setText(text)

    def _log_waiting_frame_once(self) -> None:
        if self._logged_waiting_frame:
            return
        self._logged_waiting_frame = True
        print("[队员B] 视觉调试预览等待摄像头画面")

    def _log_first_frame_once(self) -> None:
        if self._logged_first_frame:
            return
        self._logged_first_frame = True
        print("[队员B] 视觉调试预览已接收到摄像头画面")

    def _format_info(self, info: dict, state: dict, gesture_state: dict | None) -> str:
        state_code = info.get("state_code") or state.get("state_code") or "unknown"
        confidence = info.get("confidence", state.get("confidence", 0.0))
        source = info.get("source") or state.get("source") or []
        if isinstance(source, list):
            source_text = ", ".join(str(item) for item in source)
        else:
            source_text = str(source)

        lines = [
            f"state_code: {state_code}",
            f"confidence: {confidence}",
            f"source: {source_text}",
            f"face_present: {info.get('face_present', False)}",
            f"bbox: {info.get('bbox')}",
            f"landmarks: {info.get('landmarks_count', 0)}",
            f"looking_down: {info.get('looking_down', False)}",
            f"eyes_closed: {info.get('eyes_closed', False)}",
            f"low_light: {info.get('low_light', False)}",
            f"brightness: {info.get('brightness', 0.0)}",
        ]

        if gesture_state:
            lines.extend([
                f"gesture_code: {gesture_state.get('gesture_code', 'none')}",
                f"gesture_confidence: {gesture_state.get('confidence', 0.0)}",
                f"gesture_source: {gesture_state.get('source', [])}",
            ])

        updated_at = info.get("updated_at")
        if updated_at:
            age = max(0.0, time.time() - float(updated_at))
            lines.append(f"debug_age_seconds: {age:.2f}")

        return "\n".join(lines)
