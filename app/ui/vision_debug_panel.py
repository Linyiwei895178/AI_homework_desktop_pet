from __future__ import annotations

import time
from typing import Any, Callable, Optional

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import QLabel, QHBoxLayout, QSizePolicy, QScrollArea, QVBoxLayout, QWidget


HAND_CONNECTIONS = [
    (0, 1), (1, 2), (2, 3), (3, 4),
    (0, 5), (5, 6), (6, 7), (7, 8),
    (0, 9), (9, 10), (10, 11), (11, 12),
    (0, 13), (13, 14), (14, 15), (15, 16),
    (0, 17), (17, 18), (18, 19), (19, 20),
    (5, 9), (9, 13), (13, 17),
]

SHOW_ZOOM_DEBUG = True


class VisionDebugPanel(QWidget):
    """Standalone Qt panel for visual debugging of Team B camera perception."""

    visibility_changed = Signal(bool)

    def __init__(
        self,
        detector_getter: Optional[Callable[[], Any]] = None,
        gesture_getter: Optional[Callable[[], dict | None]] = None,
        camera_frame_getter: Optional[Callable[[], Any]] = None,
        camera_enabled_getter: Optional[Callable[[], bool]] = None,
        runtime_snapshot_getter: Optional[Callable[[], dict | None]] = None,
        response_getter: Optional[Callable[[], dict | None]] = None,
        refresh_ms: int = 400,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._detector_getter = detector_getter
        self._gesture_getter = gesture_getter
        self._camera_frame_getter = camera_frame_getter
        self._camera_enabled_getter = camera_enabled_getter
        self._runtime_snapshot_getter = runtime_snapshot_getter
        self._response_getter = response_getter
        self._refresh_ms = max(100, int(refresh_ms))

        self.setWindowTitle("Vision Debug Preview")
        self.resize(1280, 820)

        self.image_label = QLabel("Waiting for camera frame...")
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.image_label.setMinimumSize(640, 480)
        self.image_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.image_label.setStyleSheet(
            "QLabel { background: #050505; color: #d1d5db; border: 1px solid #374151; }"
        )

        self.info_label = QLabel("")
        self.info_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        self.info_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.info_label.setWordWrap(False)
        self.info_label.setStyleSheet(
            "QLabel { color: #e5e7eb; background: #111827; padding: 8px; font-family: Consolas, monospace; }"
        )

        self.result_label = QLabel("识别结果：等待手势")
        self.result_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        self.result_label.setWordWrap(True)
        self.result_label.setMinimumHeight(110)
        self.result_label.setStyleSheet(
            """
            QLabel {
                color: #f8fafc;
                background: #172033;
                border: 1px solid #334155;
                padding: 16px;
                font-size: 24px;
                font-family: Microsoft YaHei, SimHei, sans-serif;
                font-weight: 600;
            }
            """
        )

        self.pet_status_label = QLabel("桌宠状态：普通")
        self.pet_status_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        self.pet_status_label.setWordWrap(True)
        self.pet_status_label.setMinimumHeight(88)
        self.pet_status_label.setStyleSheet(
            """
            QLabel {
                color: #e0f2fe;
                background: #0f2636;
                border-left: 1px solid #334155;
                border-right: 1px solid #334155;
                border-bottom: 1px solid #334155;
                padding: 14px 16px;
                font-size: 20px;
                font-family: Microsoft YaHei, SimHei, sans-serif;
            }
            """
        )

        self.response_label = QLabel("桌宠回应：暂无自动回应")
        self.response_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        self.response_label.setWordWrap(True)
        self.response_label.setMinimumHeight(120)
        self.response_label.setStyleSheet(
            """
            QLabel {
                color: #fff7ed;
                background: #2b1f12;
                border-left: 1px solid #334155;
                border-right: 1px solid #334155;
                border-bottom: 1px solid #334155;
                padding: 14px 16px;
                font-size: 20px;
                font-family: Microsoft YaHei, SimHei, sans-serif;
            }
            """
        )

        self.info_scroll = QScrollArea()
        self.info_scroll.setWidgetResizable(True)
        self.info_scroll.setWidget(self.info_label)
        self.info_scroll.setMinimumWidth(460)
        self.info_scroll.setMaximumWidth(640)
        self.info_scroll.setStyleSheet("QScrollArea { background: #111827; border: 1px solid #1f2937; }")

        side_panel = QWidget()
        side_panel.setMinimumWidth(460)
        side_panel.setMaximumWidth(640)
        side_layout = QVBoxLayout(side_panel)
        side_layout.setContentsMargins(0, 0, 0, 0)
        side_layout.setSpacing(0)
        side_layout.addWidget(self.result_label, 0)
        side_layout.addWidget(self.pet_status_label, 0)
        side_layout.addWidget(self.response_label, 0)
        side_layout.addWidget(self.info_scroll, 1)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.image_label, 1)
        layout.addWidget(side_panel, 0)

        self._timer = QTimer(self)
        self._timer.setInterval(self._refresh_ms)
        self._timer.timeout.connect(self.update_from_detector)
        self._logged_waiting_frame = False
        self._logged_first_frame = False
        self._logged_first_hand = False
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
        self.showMaximized()
        self.raise_()
        self.activateWindow()
        self.update_from_detector()

    def update_from_detector(self) -> None:
        if not self.isVisible():
            return

        runtime_snapshot = self._read_runtime_snapshot()
        response_state = self._read_response_state()
        self.pet_status_label.setText(self._format_pet_status(runtime_snapshot))
        self.response_label.setText(self._format_pet_response(response_state))

        camera_enabled = True
        if self._camera_enabled_getter is not None:
            try:
                camera_enabled = bool(self._camera_enabled_getter())
            except Exception:
                camera_enabled = False

        if not camera_enabled:
            self._show_placeholder("Camera Off")
            self.result_label.setText("识别结果：摄像头已关闭")
            self.info_label.setText("camera: off\nstate: unknown\nsource: camera_off")
            return

        detector = None
        if self._detector_getter is not None:
            try:
                detector = self._detector_getter()
            except Exception:
                detector = None

        snapshot = self._read_snapshot(detector) if detector is not None else {"frame": None, "info": {}, "state": {}}
        frame = snapshot.get("frame")
        info = snapshot.get("info") or {}
        state = snapshot.get("state") or {}
        if isinstance(snapshot.get("face_mimic"), dict) and "face_mimic" not in info:
            info = dict(info)
            info["face_mimic"] = snapshot.get("face_mimic")
        gesture_state = self._read_gesture_state()

        if frame is None:
            frame = self._read_camera_frame()

        if frame is None:
            self._log_waiting_frame_once()
            self._show_placeholder("Waiting for camera frame...")
            self.result_label.setText(self._format_result_summary(info, state, gesture_state))
            self.info_label.setText(self._format_info(info, state, gesture_state))
            return

        display_frame = self._draw_face_overlay(frame, info, state)
        display_frame = self._draw_hand_overlay(display_frame, gesture_state)
        self.set_frame(display_frame)
        self.result_label.setText(self._format_result_summary(info, state, gesture_state))
        self.info_label.setText(self._format_info(info, state, gesture_state))

    def _read_camera_frame(self) -> Any:
        if self._camera_frame_getter is None:
            return None
        try:
            return self._camera_frame_getter()
        except Exception:
            return None

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
        self.start()
        self.visibility_changed.emit(True)

    def hideEvent(self, event) -> None:  # noqa: N802 - Qt API name
        super().hideEvent(event)
        self.stop()
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

    def _read_runtime_snapshot(self) -> dict:
        if self._runtime_snapshot_getter is None:
            return {}
        try:
            snapshot = self._runtime_snapshot_getter()
            return snapshot if isinstance(snapshot, dict) else {}
        except Exception:
            return {}

    def _read_response_state(self) -> dict:
        if self._response_getter is None:
            return {}
        try:
            response = self._response_getter()
            return response if isinstance(response, dict) else {}
        except Exception:
            return {}

    def _draw_face_overlay(self, frame: Any, info: dict, state: dict) -> Any:
        try:
            import cv2  # type: ignore
        except Exception:
            return frame

        try:
            canvas = frame.copy()
            height, width = canvas.shape[:2]

            bbox = info.get("bbox")
            if isinstance(bbox, (list, tuple)) and len(bbox) == 4:
                x, y, bw, bh = [int(v) for v in bbox]
                cv2.rectangle(canvas, (x, y), (x + bw, y + bh), (255, 0, 0), 2)

            landmarks = info.get("landmarks")
            if isinstance(landmarks, list):
                for idx, landmark in enumerate(landmarks):
                    if idx % 3 != 0 or not isinstance(landmark, dict):
                        continue
                    x = float(landmark.get("x", 0.0) or 0.0)
                    y = float(landmark.get("y", 0.0) or 0.0)
                    px = int(max(0.0, min(1.0, x)) * width)
                    py = int(max(0.0, min(1.0, y)) * height)
                    cv2.circle(canvas, (px, py), 1, (0, 255, 0), -1)

            return canvas
        except Exception:
            return frame

    def _draw_hand_overlay(self, frame: Any, gesture_state: dict | None) -> Any:
        hands = []
        if isinstance(gesture_state, dict):
            raw_hands = gesture_state.get("hands")
            if isinstance(raw_hands, list):
                hands = raw_hands
        if not hands:
            return frame

        try:
            import cv2  # type: ignore
        except Exception:
            return frame

        try:
            canvas = frame.copy()
            height, width = canvas.shape[:2]
            gesture_code = str((gesture_state or {}).get("gesture_code") or "none")
            confidence = float((gesture_state or {}).get("confidence", 0.0) or 0.0)
            zoom_state = gesture_state.get("zoom") if SHOW_ZOOM_DEBUG and isinstance(gesture_state, dict) else None
            zoom_state = zoom_state if isinstance(zoom_state, dict) else {}

            for hand in hands:
                if not isinstance(hand, dict):
                    continue
                landmarks = hand.get("landmarks")
                if not isinstance(landmarks, list) or len(landmarks) < 21:
                    continue

                points: list[tuple[int, int] | None] = []
                for landmark in landmarks:
                    if not isinstance(landmark, dict):
                        points.append(None)
                        continue
                    x = float(landmark.get("x", 0.0) or 0.0)
                    y = float(landmark.get("y", 0.0) or 0.0)
                    px = int(round(x * width)) if 0.0 <= x <= 1.5 else int(round(x))
                    py = int(round(y * height)) if 0.0 <= y <= 1.5 else int(round(y))
                    if px < 0 or py < 0 or px >= width or py >= height:
                        points.append(None)
                    else:
                        points.append((px, py))

                if not any(points):
                    continue

                for start, end in HAND_CONNECTIONS:
                    if start >= len(points) or end >= len(points):
                        continue
                    p1 = points[start]
                    p2 = points[end]
                    if p1 is None or p2 is None:
                        continue
                    cv2.line(canvas, p1, p2, (255, 210, 40), 2, cv2.LINE_AA)

                for idx, point in enumerate(points):
                    if point is None:
                        continue
                    radius = 5 if idx == 0 else 4
                    color = (0, 255, 255) if idx == 0 else (40, 255, 180)
                    cv2.circle(canvas, point, radius, color, -1, cv2.LINE_AA)
                    cv2.circle(canvas, point, radius + 1, (15, 32, 39), 1, cv2.LINE_AA)

                wrist = points[0] or next((point for point in points if point is not None), None)
                if wrist is not None:
                    handedness = str(hand.get("handedness") or gesture_state.get("handedness") or "Unknown")
                    label = f"{handedness} {gesture_code} {confidence:.2f}"
                    cv2.putText(
                        canvas,
                        label,
                        (max(4, wrist[0] + 8), max(18, wrist[1] - 10)),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.55,
                        (255, 255, 120),
                        2,
                        cv2.LINE_AA,
                    )
                    pinch_distance = zoom_state.get("pinch_distance")
                    scale_ratio = zoom_state.get("scale_ratio")
                    if SHOW_ZOOM_DEBUG and pinch_distance is not None and scale_ratio is not None:
                        zoom_label = (
                            f"pinch {float(pinch_distance):.3f}  "
                            f"smooth {float(scale_ratio):.2f}"
                        )
                        cv2.putText(
                            canvas,
                            zoom_label,
                            (max(4, wrist[0] + 8), max(38, wrist[1] + 12)),
                            cv2.FONT_HERSHEY_SIMPLEX,
                            0.5,
                            (120, 255, 255),
                            2,
                            cv2.LINE_AA,
                        )
                self._log_first_hand_once()
            return canvas
        except Exception:
            return frame

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

    def _log_first_hand_once(self) -> None:
        if self._logged_first_hand:
            return
        self._logged_first_hand = True
        print("[队员B] 视觉调试预览已接收到手部关键点")

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
        mimic = info.get("face_mimic") if isinstance(info.get("face_mimic"), dict) else {}
        if mimic:
            lines.extend([
                f"mimic_available: {mimic.get('available', False)}",
                f"mimic_expression: {mimic.get('expression', 'unknown')}",
                f"mimic_mouth_open: {mimic.get('mouth_open', 0.0)}",
                f"mimic_smile: {mimic.get('smile', 0.0)}",
                f"mimic_eye_blink_left: {mimic.get('eye_blink_left', 0.0)}",
                f"mimic_eye_blink_right: {mimic.get('eye_blink_right', 0.0)}",
                f"mimic_brow_raise: {mimic.get('brow_raise', 0.0)}",
                f"mimic_mouth_frown: {mimic.get('mouth_frown', 0.0)}",
                f"mimic_head_yaw: {mimic.get('head_yaw', 0.0)}",
                f"mimic_head_pitch: {mimic.get('head_pitch', 0.0)}",
                f"mimic_head_roll: {mimic.get('head_roll', 0.0)}",
                f"mimic_source: {mimic.get('source', [])}",
            ])

        if gesture_state:
            hands = gesture_state.get("hands")
            hand_count = len(hands) if isinstance(hands, list) else 0
            zoom = gesture_state.get("zoom")
            zoom = zoom if isinstance(zoom, dict) else {}
            gesture_lines = [
                f"gesture_code: {gesture_state.get('gesture_code', 'none')}",
                f"gesture_confidence: {gesture_state.get('confidence', 0.0)}",
                f"gesture_handedness: {gesture_state.get('handedness', 'Unknown')}",
                f"hand_landmarks: {hand_count}",
                f"gesture_source: {gesture_state.get('source', [])}",
            ]
            if SHOW_ZOOM_DEBUG:
                gesture_lines.extend([
                    f"pinch_distance: {zoom.get('pinch_distance')}",
                    f"target_scale: {zoom.get('target_scale')}",
                    f"smooth_scale: {zoom.get('smooth_scale')}",
                    f"applied_scale: {zoom.get('applied_scale')}",
                    f"scale_ratio: {zoom.get('scale_ratio')}",
                ])
            else:
                gesture_lines.append("gesture_zoom: disabled")
            lines.extend(gesture_lines)
        else:
            lines.append("gesture_detector: unavailable")

        updated_at = info.get("updated_at")
        if updated_at:
            age = max(0.0, time.time() - float(updated_at))
            lines.append(f"debug_age_seconds: {age:.2f}")

        return "\n".join(lines)

    def _format_result_summary(self, info: dict, state: dict, gesture_state: dict | None) -> str:
        state_code = str(info.get("state_code") or state.get("state_code") or "unknown")
        confidence = self._safe_float(info.get("confidence", state.get("confidence", 0.0)))
        face_present = bool(info.get("face_present", False))

        gesture_text = "等待手势"
        if gesture_state is None:
            gesture_text = "手势识别未开启"
        elif isinstance(gesture_state, dict):
            gesture_code = str(gesture_state.get("gesture_code") or "none")
            gesture_name = str(gesture_state.get("gesture_name") or "").strip()
            zoom = gesture_state.get("zoom") if SHOW_ZOOM_DEBUG and isinstance(gesture_state.get("zoom"), dict) else {}
            if SHOW_ZOOM_DEBUG and zoom.get("active"):
                gesture_text = "识别到捏合缩放手势"
            elif gesture_code not in {"", "none"}:
                display_name = gesture_name or gesture_code
                gesture_text = f"识别到 {display_name} 手势"

        face_text = "已识别人脸" if face_present else "未识别人脸"
        return (
            f"识别结果：{gesture_text}\n"
            f"用户状态：{state_code}  置信度：{confidence:.2f}\n"
            f"人脸状态：{face_text}"
        )

    def _format_pet_status(self, snapshot: dict) -> str:
        pet_emotion = snapshot.get("pet_emotion") if isinstance(snapshot, dict) else {}
        action = snapshot.get("action") if isinstance(snapshot, dict) else {}
        pet_emotion = pet_emotion if isinstance(pet_emotion, dict) else {}
        action = action if isinstance(action, dict) else {}

        mood = str(pet_emotion.get("mood") or "neutral")
        mood_name = str(pet_emotion.get("mood_name") or self._mood_name(mood))
        energy = pet_emotion.get("energy")
        intimacy = pet_emotion.get("intimacy")
        action_code = str(action.get("action_code") or "")
        action_name = str(action.get("action_name") or self._action_name(action_code))

        energy_text = "--" if energy is None else str(energy)
        intimacy_text = "--" if intimacy is None else str(intimacy)
        return (
            f"桌宠状态：{mood_name} ({mood})\n"
            f"当前动作：{action_name} ({action_code or 'none'})\n"
            f"能量：{energy_text}    好感度：{intimacy_text}"
        )

    def _format_pet_response(self, response_state: dict) -> str:
        text = str(response_state.get("text") or "").strip() if isinstance(response_state, dict) else ""
        if not text:
            return "桌宠回应：暂无自动回应"

        event_type = str(response_state.get("event_type") or "").strip()
        if event_type:
            return f"桌宠回应（{event_type}）：\n{text}"
        return f"桌宠回应：\n{text}"

    @staticmethod
    def _mood_name(mood: str) -> str:
        names = {
            "happy": "开心",
            "neutral": "平静",
            "sad": "难过",
            "tired": "疲惫",
            "excited": "兴奋",
            "angry": "生气",
            "hungry": "饥饿",
        }
        return names.get(mood, mood or "普通")

    @staticmethod
    def _action_name(action_code: str) -> str:
        names = {
            "happy": "开心动作",
            "idle": "待机",
            "rest": "休息",
            "speak": "说话",
            "sad": "难过动作",
            "hungry": "饥饿动作",
            "": "无动作",
        }
        return names.get(action_code, action_code or "无动作")

    @staticmethod
    def _safe_float(value: Any) -> float:
        try:
            return float(value)
        except Exception:
            return 0.0
