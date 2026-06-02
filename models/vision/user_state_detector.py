"""
UserStateDetector - 用户状态感知模块（优化版）

固定对外接口（不要改）：
    detector = UserStateDetector()
    detector.start()
    state = detector.get_state()

固定返回字段（不要改）：
    state_code, state_name, description, tags, confidence, duration,
    need_response, suggestion, source

本优化版重点：
1. 优先使用 MediaPipe FaceDetection / FaceMesh，OpenCV Haar 只做备用。
2. “低头/短暂未识别人脸”不会立刻判断离开；只要最近检测到过脸/头，就继续认为人在。
3. 增加状态平滑，减少 normal / unknown / away / return 抖动。
4. Qwen-VL 每 5 秒调用一次（可通过 vlm_interval 调整）。
5. 对外字段和 state_code 完全兼容已发给队友的接口。
"""

from __future__ import annotations

import copy
import math
import threading
import time
from collections import deque
from typing import Any, Callable, Deque, Dict, List, Optional, Tuple

# ========== 状态大类常量：已经发给队友，不要随意修改 ========== 

STATE_NORMAL = "normal"
STATE_FOCUSED = "focused"
STATE_DISTRACTED = "distracted"
STATE_TIRED = "tired"
STATE_AWAY = "away"
STATE_RETURN = "return"
STATE_STUDY_LONG = "study_long"
STATE_LOW_LIGHT = "low_light"
STATE_CAMERA_ERROR = "camera_error"
STATE_UNKNOWN = "unknown"

ALL_STATE_CODES = [
    STATE_NORMAL,
    STATE_FOCUSED,
    STATE_DISTRACTED,
    STATE_TIRED,
    STATE_AWAY,
    STATE_RETURN,
    STATE_STUDY_LONG,
    STATE_LOW_LIGHT,
    STATE_CAMERA_ERROR,
    STATE_UNKNOWN,
]

STATE_NAME_MAP = {
    STATE_NORMAL: "正常状态",
    STATE_FOCUSED: "专注学习",
    STATE_DISTRACTED: "疑似分心",
    STATE_TIRED: "疑似疲劳",
    STATE_AWAY: "离开座位",
    STATE_RETURN: "回到座位",
    STATE_STUDY_LONG: "学习过久",
    STATE_LOW_LIGHT: "环境偏暗",
    STATE_CAMERA_ERROR: "摄像头异常",
    STATE_UNKNOWN: "未知状态",
}


def create_empty_state(state_code: str = STATE_UNKNOWN) -> dict:
    if state_code not in ALL_STATE_CODES:
        state_code = STATE_UNKNOWN
    return {
        "state_code": state_code,
        "state_name": STATE_NAME_MAP.get(state_code, "未知状态"),
        "description": "",
        "tags": [],
        "confidence": 0.0,
        "duration": 0.0,
        "need_response": False,
        "suggestion": "",
        "source": [],
    }


def is_valid_state(state: dict) -> bool:
    required = [
        "state_code", "state_name", "description", "tags",
        "confidence", "duration", "need_response", "suggestion", "source",
    ]
    return isinstance(state, dict) and all(k in state for k in required)


class UserStateDetector:
    """
    用户状态检测器。

    说明：
    - 不会每帧调用 Qwen-VL，而是每 vlm_interval 秒调用一次。
    - 低头/遮挡导致短暂检测不到脸时，不会直接判断 away。
    - 如果检测不到 MediaPipe，会自动降级到 OpenCV Haar。
    """

    def __init__(
        self,
        camera_index: int = 0,
        detect_interval: float = 0.5,
        vlm_interval: float = 5.0,          # 按你的要求：每 5 秒调用一次 API
        enable_vlm: bool = False,
        study_long_seconds: float = 40 * 60,
        away_threshold: float = 12.0,       # 优化：离开阈值拉长，低头不会马上 away
        face_memory_seconds: float = 10.0,  # 最近识别到脸/头的记忆时间
        low_light_threshold: float = 55.0,
        looking_down_seconds: float = 5.0,
        eye_closed_seconds: float = 2.0,
        tired_eye_seconds: float = 4.0,
        focused_seconds: float = 25.0,
        response_cooldown: float = 30.0,
        show_preview: bool = False,
        frame_provider: Any = None,
    ):
        self.camera_index = camera_index
        self._detect_interval = max(0.1, float(detect_interval))
        self._vlm_interval = max(5.0, float(vlm_interval))
        self._vlm_enabled = bool(enable_vlm)
        self._study_long_seconds = float(study_long_seconds)
        self._away_threshold = float(away_threshold)
        self._face_memory_seconds = float(face_memory_seconds)
        self._low_light_threshold = float(low_light_threshold)
        self._looking_down_seconds = float(looking_down_seconds)
        self._eye_closed_seconds = float(eye_closed_seconds)
        self._tired_eye_seconds = float(tired_eye_seconds)
        self._focused_seconds = float(focused_seconds)
        self._response_cooldown = float(response_cooldown)
        self._show_preview = bool(show_preview)
        self._frame_provider = frame_provider

        self._is_running = False
        self._detect_thread: Optional[threading.Thread] = None
        self._lock = threading.RLock()
        self._callback: Optional[Callable[[dict], None]] = None

        self._current_state: dict = create_empty_state(STATE_UNKNOWN)
        self._latest_frame: Any = None
        self._cap: Any = None
        self._owns_camera = frame_provider is None

        self._cv2: Any = None
        self._mp: Any = None
        self._mp_face_detection: Any = None
        self._mp_face_mesh: Any = None
        self._face_detection: Any = None
        self._face_mesh: Any = None
        self._haar_frontal: Any = None
        self._haar_profile: Any = None
        self._vl_client: Any = None

        # DeepFace 表情识别增强模块。不可用时自动降级，不影响基础检测。
        self._emotion_recognizer: Any = None
        self._emotion_enabled: bool = True

        now = time.time()
        self._last_face_seen_at: Optional[float] = None
        self._face_present_since: Optional[float] = None
        self._no_face_since: Optional[float] = None
        self._study_started_at: Optional[float] = None
        self._last_present_tick: Optional[float] = None
        self._total_present_seconds: float = 0.0
        self._was_away = False
        self._return_until: float = 0.0

        self._looking_down_since: Optional[float] = None
        self._eyes_closed_since: Optional[float] = None
        self._low_light_since: Optional[float] = None
        self._last_face_center: Optional[Tuple[float, float]] = None
        self._face_center_history: Deque[Tuple[float, float, float]] = deque(maxlen=20)

        self._last_state_code: str = STATE_UNKNOWN
        self._state_since: float = now
        self._last_response_at: Dict[str, float] = {}
        self._last_vlm_at: float = 0.0
        self._last_vlm_state: Optional[dict] = None

    # ==================== 对外接口 ====================

    def start(self):
        if self._is_running:
            return
        self._is_running = True
        self._detect_thread = threading.Thread(target=self._detect_loop, daemon=True)
        self._detect_thread.start()
        print("[UserStateDetector] 检测器启动。")

    def stop(self):
        self._is_running = False
        if self._detect_thread and self._detect_thread.is_alive():
            self._detect_thread.join(timeout=2.0)
        self._release_resources()
        print("[UserStateDetector] 检测器停止。")

    def get_state(self) -> dict:
        with self._lock:
            return copy.deepcopy(self._current_state)

    def get_frame(self):
        with self._lock:
            if self._latest_frame is None:
                return None
            try:
                return self._latest_frame.copy()
            except Exception:
                return self._latest_frame

    def set_vlm_enabled(self, enabled: bool):
        self._vlm_enabled = bool(enabled)
        print(f"[UserStateDetector] Qwen-VL 启用状态: {self._vlm_enabled}")

    def set_callback(self, callback_func: Callable[[dict], None]):
        self._callback = callback_func

    def set_mock_state(self, state_code: str = STATE_DISTRACTED):
        mock_states = {
            STATE_NORMAL: self._build_state(
                STATE_NORMAL, "用户姿态正常，正在注视屏幕。", ["正常", "注视屏幕"],
                0.95, False, "", ["mock"]
            ),
            STATE_FOCUSED: self._build_state(
                STATE_FOCUSED, "用户正在专注学习，头部稳定，视线集中。", ["专注", "学习", "稳定"],
                0.91, False, "保持安静，不打扰用户。", ["mock"]
            ),
            STATE_DISTRACTED: self._build_state(
                STATE_DISTRACTED, "用户低头时间较长，画面中疑似出现手机，注意力可能分散。",
                ["低头", "疑似看手机", "注意力分散"], 0.82, True,
                "建议桌宠用轻松语气提醒用户回到学习任务。", ["mock"]
            ),
            STATE_TIRED: self._build_state(
                STATE_TIRED, "用户闭眼或姿态松弛时间较长，疑似疲劳。", ["闭眼", "疲劳", "姿态松弛"],
                0.80, True, "建议桌宠关心用户，提醒休息或喝水。", ["mock"]
            ),
            STATE_AWAY: self._build_state(
                STATE_AWAY, "摄像头画面中未检测到用户，已离开座位。", ["无人", "离开"],
                0.98, False, "桌宠可进入待机状态。", ["mock"]
            ),
            STATE_RETURN: self._build_state(
                STATE_RETURN, "用户刚刚回到座位，姿态正在恢复。", ["回到座位", "欢迎"],
                0.88, True, "建议桌宠热情打招呼，表示欢迎回来。", ["mock"]
            ),
            STATE_STUDY_LONG: self._build_state(
                STATE_STUDY_LONG, "用户已连续学习较长时间，建议适当休息。", ["长时间学习", "需要休息"],
                0.78, True, "建议桌宠提醒用户休息，做眼保健操或起身活动。", ["mock"]
            ),
            STATE_LOW_LIGHT: self._build_state(
                STATE_LOW_LIGHT, "环境光线偏暗，可能影响用眼健康。", ["光线偏暗", "环境提醒"],
                0.86, True, "建议提醒用户开灯或调整光线。", ["mock"]
            ),
            STATE_CAMERA_ERROR: self._build_state(
                STATE_CAMERA_ERROR, "摄像头无法正常打开或读取。", ["摄像头异常"],
                1.0, False, "请检查摄像头权限或是否被其他软件占用。", ["mock"]
            ),
            STATE_UNKNOWN: create_empty_state(STATE_UNKNOWN),
        }
        state = mock_states.get(state_code, create_empty_state(STATE_UNKNOWN))
        print(f"[UserStateDetector] 设置模拟状态: {state.get('state_code')}")
        self._update_state(state)

    # ==================== 主检测循环 ====================

    def _detect_loop(self):
        if not self._init_dependencies_and_camera():
            self._update_state(self._build_state(
                STATE_CAMERA_ERROR,
                "摄像头无法打开，请检查摄像头权限、设备连接或是否被其他软件占用。",
                ["摄像头异常"],
                1.0,
                False,
                "请检查摄像头权限或关闭占用摄像头的软件。",
                ["opencv", "camera"],
            ))
            return

        while self._is_running:
            loop_start = time.time()
            try:
                ret, frame = self._read_frame()
                if not ret or frame is None:
                    self._update_state(self._build_state(
                        STATE_CAMERA_ERROR,
                        "摄像头读取失败，暂时无法获取用户画面。",
                        ["摄像头读取失败"],
                        1.0,
                        False,
                        "请检查摄像头是否正常工作。",
                        ["opencv", "camera"],
                    ))
                    time.sleep(self._detect_interval)
                    continue

                with self._lock:
                    self._latest_frame = frame.copy()

                state = self._analyze_frame(frame)
                state = self._maybe_apply_vlm(frame, state)
                self._update_state(state)

                if self._show_preview:
                    self._draw_preview(frame, state)

            except Exception as exc:
                self._update_state(self._build_state(
                    STATE_CAMERA_ERROR,
                    f"检测循环出现异常：{exc}",
                    ["检测异常"],
                    1.0,
                    False,
                    "可重启检测器或检查依赖安装情况。",
                    ["exception"],
                ))

            elapsed = time.time() - loop_start
            time.sleep(max(0.01, self._detect_interval - elapsed))

    def _init_dependencies_and_camera(self) -> bool:
        try:
            import cv2  # type: ignore
            self._cv2 = cv2
        except Exception as exc:
            print(f"[UserStateDetector] OpenCV 导入失败：{exc}")
            return False

        # MediaPipe 优先，Haar 备用
        try:
            import mediapipe as mp  # type: ignore
            self._mp = mp
            self._mp_face_detection = mp.solutions.face_detection
            self._mp_face_mesh = mp.solutions.face_mesh
            self._face_detection = self._mp_face_detection.FaceDetection(
                model_selection=0,
                min_detection_confidence=0.45,
            )
            self._face_mesh = self._mp_face_mesh.FaceMesh(
                static_image_mode=False,
                max_num_faces=1,
                refine_landmarks=True,
                min_detection_confidence=0.45,
                min_tracking_confidence=0.45,
            )
            print("[UserStateDetector] MediaPipe 已启用。")
        except Exception as exc:
            print(f"[UserStateDetector] MediaPipe 不可用，将使用 OpenCV Haar 降级：{exc}")
            self._mp = None
            self._face_detection = None
            self._face_mesh = None

        try:
            frontal_path = self._cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
            profile_path = self._cv2.data.haarcascades + "haarcascade_profileface.xml"
            self._haar_frontal = self._cv2.CascadeClassifier(frontal_path)
            self._haar_profile = self._cv2.CascadeClassifier(profile_path)
        except Exception:
            self._haar_frontal = None
            self._haar_profile = None

        if self._vlm_enabled:
            self._init_vlm_client()

        # 表情识别是增强项：可用则加载，不可用不影响基础检测。
        self._init_emotion_recognizer()

        if self._frame_provider is not None:
            return True

        self._cap = self._cv2.VideoCapture(self.camera_index)
        if not self._cap or not self._cap.isOpened():
            return False

        # 尽量降低延迟
        try:
            self._cap.set(self._cv2.CAP_PROP_FRAME_WIDTH, 640)
            self._cap.set(self._cv2.CAP_PROP_FRAME_HEIGHT, 480)
            self._cap.set(self._cv2.CAP_PROP_BUFFERSIZE, 1)
        except Exception:
            pass
        return True

    def _read_frame(self) -> Tuple[bool, Any]:
        if self._frame_provider is not None:
            getter = getattr(self._frame_provider, "get_frame", None)
            if not callable(getter):
                return False, None
            frame = getter()
            return frame is not None, frame

        if self._cap is None:
            return False, None
        return self._cap.read()

    def _release_resources(self):
        try:
            if self._owns_camera and self._cap is not None:
                self._cap.release()
        except Exception:
            pass
        try:
            if self._face_detection is not None:
                self._face_detection.close()
        except Exception:
            pass
        try:
            if self._face_mesh is not None:
                self._face_mesh.close()
        except Exception:
            pass
        try:
            if self._show_preview and self._cv2 is not None:
                self._cv2.destroyAllWindows()
        except Exception:
            pass

    # ==================== 帧分析 ====================

    def _analyze_frame(self, frame: Any) -> dict:
        now = time.time()
        h, w = frame.shape[:2]
        brightness = self._calc_brightness(frame)
        low_light = brightness < self._low_light_threshold

        # 1. 优先 MediaPipe：只要 FaceDetection 或 FaceMesh 任一成功，就认为识别到“头/脸”
        face_info = self._detect_face_or_head(frame)
        face_present = face_info["present"]
        source = face_info["source"][:] if face_info["source"] else ["rule"]

        # 2. 人脸/头部记忆：低头导致短暂识别不到时，不立刻判 away
        if face_present:
            self._last_face_seen_at = now
            self._no_face_since = None
            if self._face_present_since is None:
                self._face_present_since = now
            if self._study_started_at is None:
                self._study_started_at = now
            if self._last_present_tick is not None:
                self._total_present_seconds += max(0.0, now - self._last_present_tick)
            self._last_present_tick = now
        else:
            if self._no_face_since is None:
                self._no_face_since = now
            self._last_present_tick = None

        recently_seen = (
            self._last_face_seen_at is not None
            and (now - self._last_face_seen_at) <= self._face_memory_seconds
        )
        no_face_duration = 0.0 if self._no_face_since is None else now - self._no_face_since

        # 3. 关键特征判断
        looking_down = False
        eyes_closed = False
        if face_info.get("landmarks"):
            looking_down = self._estimate_looking_down(face_info["landmarks"], w, h)
            eyes_closed = self._estimate_eyes_closed(face_info["landmarks"], w, h)
        else:
            # 没有 landmarks 时，用框的位置粗略辅助。脸框特别靠下时，可能低头或坐姿较低。
            bbox = face_info.get("bbox")
            if bbox:
                _, y, _, bh = bbox
                looking_down = (y + bh / 2) / max(1, h) > 0.62

        if looking_down:
            if self._looking_down_since is None:
                self._looking_down_since = now
        else:
            self._looking_down_since = None

        if eyes_closed:
            if self._eyes_closed_since is None:
                self._eyes_closed_since = now
        else:
            self._eyes_closed_since = None

        if low_light:
            if self._low_light_since is None:
                self._low_light_since = now
        else:
            self._low_light_since = None

        looking_down_duration = 0.0 if self._looking_down_since is None else now - self._looking_down_since
        eyes_closed_duration = 0.0 if self._eyes_closed_since is None else now - self._eyes_closed_since
        low_light_duration = 0.0 if self._low_light_since is None else now - self._low_light_since
        present_duration = 0.0 if self._face_present_since is None else now - self._face_present_since
        study_duration = 0.0 if self._study_started_at is None else now - self._study_started_at

        # 4. 离开/回来/正常状态逻辑
        # 关键优化：最近看到过脸/头，则不判 away，避免低头误判人不在。
        if not face_present and not recently_seen:
            if no_face_duration >= self._away_threshold:
                self._was_away = True
                return self._build_state(
                    STATE_AWAY,
                    "连续一段时间未检测到用户人脸或头部，判断用户已离开座位。",
                    ["无人", "离开"],
                    0.92,
                    False,
                    "桌宠可进入等待状态，不必频繁打扰。",
                    self._merge_source(source, "rule"),
                )
            return self._build_state(
                STATE_UNKNOWN,
                "暂时未检测到人脸或头部，正在继续确认用户是否离开。",
                ["暂未检测到人脸", "继续确认"],
                0.45,
                False,
                "继续观察，暂不主动回应。",
                self._merge_source(source, "rule"),
            )

        # 如果短暂没检测到，但最近刚检测到过，保持“人在”状态，不输出 away/unknown
        if not face_present and recently_seen:
            return self._build_state(
                STATE_NORMAL,
                "用户刚才仍在画面中，当前可能因低头或短暂遮挡导致人脸不明显，继续视为在座位。",
                ["在座位", "短暂遮挡", "可能低头"],
                0.66,
                False,
                "保持普通陪伴即可。",
                self._merge_source(source, "rule"),
            )

        if face_present and self._was_away:
            self._was_away = False
            self._return_until = now + 3.0
            return self._build_state(
                STATE_RETURN,
                "用户离开后重新出现在摄像头画面中。",
                ["回来", "重新检测到人脸"],
                0.88,
                True,
                "可以欢迎用户回来，并鼓励继续学习。",
                self._merge_source(source, "rule"),
            )

        if now < self._return_until:
            return self._build_state(
                STATE_RETURN,
                "用户刚刚回到座位。",
                ["回来", "重新检测到人脸"],
                0.86,
                False,
                "可以欢迎用户回来，并鼓励继续学习。",
                self._merge_source(source, "rule"),
            )

        # 5. 优先级判断：疲劳 > 分心低头 > 学习过久 > 暗光 > 专注 > 正常
        if eyes_closed_duration >= self._tired_eye_seconds:
            return self._build_state(
                STATE_TIRED,
                "用户闭眼时间较长，疑似疲劳或困倦。",
                ["闭眼", "疲劳", "需要休息"],
                0.86,
                True,
                "建议桌宠提醒用户休息、喝水或活动一下。",
                self._merge_source(source, "rule"),
            )

        if looking_down_duration >= self._looking_down_seconds:
            return self._build_state(
                STATE_DISTRACTED,
                "用户低头时间较长，但仍检测到头部/人脸，疑似低头看手机或注意力分散。",
                ["低头", "疑似分心", "人在座位"],
                0.80,
                True,
                "建议桌宠用轻松语气提醒用户抬头并回到学习任务。",
                self._merge_source(source, "rule"),
            )

        if study_duration >= self._study_long_seconds:
            return self._build_state(
                STATE_STUDY_LONG,
                "用户已连续学习较长时间，建议适当休息。",
                ["长时间学习", "久坐", "需要休息"],
                0.82,
                True,
                "建议桌宠提醒用户起身活动或休息眼睛。",
                self._merge_source(source, "rule"),
            )

        if low_light_duration >= 3.0:
            return self._build_state(
                STATE_LOW_LIGHT,
                "当前环境光线偏暗，可能影响用眼健康。",
                ["环境偏暗", "用眼提醒"],
                0.84,
                True,
                "建议提醒用户开灯或调整光线。",
                self._merge_source(source, "rule"),
            )

        if present_duration >= self._focused_seconds and not looking_down and not eyes_closed:
            return self._build_state(
                STATE_FOCUSED,
                "用户在座位上，状态稳定，疑似正在专注学习。",
                ["在座位", "学习中", "状态稳定"],
                0.84,
                False,
                "保持安静陪伴，暂时不主动打扰。",
                self._merge_source(source, "rule"),
            )

        return self._build_state(
            STATE_NORMAL,
            "用户在座位上，姿态基本正常。",
            ["在座位", "正常"],
            0.78,
            False,
            "保持普通陪伴即可。",
            self._merge_source(source, "rule"),
        )

    def _detect_face_or_head(self, frame: Any) -> dict:
        """
        检测脸/头部。
        只要 MediaPipe FaceDetection 或 FaceMesh 任意检测成功，就认为用户在。
        """
        h, w = frame.shape[:2]
        result = {"present": False, "bbox": None, "landmarks": None, "source": []}

        rgb = None
        try:
            rgb = self._cv2.cvtColor(frame, self._cv2.COLOR_BGR2RGB)
        except Exception:
            rgb = frame

        # 1. MediaPipe FaceDetection
        if self._face_detection is not None:
            try:
                fd = self._face_detection.process(rgb)
                if fd and fd.detections:
                    det = fd.detections[0]
                    box = det.location_data.relative_bounding_box
                    x = max(0, int(box.xmin * w))
                    y = max(0, int(box.ymin * h))
                    bw = min(w - x, int(box.width * w))
                    bh = min(h - y, int(box.height * h))
                    result.update({
                        "present": True,
                        "bbox": (x, y, bw, bh),
                        "source": self._merge_source(result["source"], "mediapipe_face"),
                    })
            except Exception:
                pass

        # 2. MediaPipe FaceMesh：低头时 FaceDetection 有时失败，但 FaceMesh 可能仍有关键点
        if self._face_mesh is not None:
            try:
                fm = self._face_mesh.process(rgb)
                if fm and fm.multi_face_landmarks:
                    landmarks = fm.multi_face_landmarks[0].landmark
                    xs = [lm.x for lm in landmarks]
                    ys = [lm.y for lm in landmarks]
                    x = max(0, int(min(xs) * w))
                    y = max(0, int(min(ys) * h))
                    bw = min(w - x, int((max(xs) - min(xs)) * w))
                    bh = min(h - y, int((max(ys) - min(ys)) * h))
                    result.update({
                        "present": True,
                        "bbox": (x, y, bw, bh),
                        "landmarks": landmarks,
                        "source": self._merge_source(result["source"], "mediapipe_mesh"),
                    })
            except Exception:
                pass

        # 3. Haar 降级：正脸 + 侧脸
        if not result["present"]:
            try:
                gray = self._cv2.cvtColor(frame, self._cv2.COLOR_BGR2GRAY)
                faces = []
                if self._haar_frontal is not None and not self._haar_frontal.empty():
                    faces = list(self._haar_frontal.detectMultiScale(gray, 1.1, 5, minSize=(60, 60)))
                if not faces and self._haar_profile is not None and not self._haar_profile.empty():
                    faces = list(self._haar_profile.detectMultiScale(gray, 1.1, 5, minSize=(60, 60)))
                # 侧脸镜像再试一次
                if not faces and self._haar_profile is not None and not self._haar_profile.empty():
                    flipped = self._cv2.flip(gray, 1)
                    pf = list(self._haar_profile.detectMultiScale(flipped, 1.1, 5, minSize=(60, 60)))
                    if pf:
                        fx, fy, fw, fh = pf[0]
                        faces = [(w - fx - fw, fy, fw, fh)]
                if faces:
                    x, y, bw, bh = max(faces, key=lambda b: b[2] * b[3])
                    result.update({
                        "present": True,
                        "bbox": (int(x), int(y), int(bw), int(bh)),
                        "source": self._merge_source(result["source"], "opencv_haar"),
                    })
            except Exception:
                pass

        # 更新中心点历史，用于后续拓展稳定性判断
        bbox = result.get("bbox")
        if result["present"] and bbox:
            x, y, bw, bh = bbox
            cx = (x + bw / 2) / max(1, w)
            cy = (y + bh / 2) / max(1, h)
            self._last_face_center = (cx, cy)
            self._face_center_history.append((time.time(), cx, cy))

        return result

    # ==================== 特征计算 ====================

    def _calc_brightness(self, frame: Any) -> float:
        try:
            gray = self._cv2.cvtColor(frame, self._cv2.COLOR_BGR2GRAY)
            return float(gray.mean())
        except Exception:
            return 128.0

    def _estimate_looking_down(self, landmarks: Any, w: int, h: int) -> bool:
        """
        简化低头判断：
        - 鼻尖相对眼睛中心明显偏下；
        - 或者脸部关键点整体偏画面下方。
        该规则不追求医学级准确，只为桌宠提醒提供参考。
        """
        try:
            # FaceMesh 常用点：1 鼻尖，33/263 眼角，10 额头上方，152 下巴
            nose = landmarks[1]
            left_eye = landmarks[33]
            right_eye = landmarks[263]
            forehead = landmarks[10]
            chin = landmarks[152]

            eye_y = (left_eye.y + right_eye.y) / 2
            face_height = max(0.001, chin.y - forehead.y)
            nose_below_eye_ratio = (nose.y - eye_y) / face_height

            # 低头时鼻尖相对眼睛更靠下，脸中心也容易偏下
            face_center_y = (forehead.y + chin.y) / 2
            return nose_below_eye_ratio > 0.28 or face_center_y > 0.58
        except Exception:
            return False

    def _estimate_eyes_closed(self, landmarks: Any, w: int, h: int) -> bool:
        try:
            left_ear = self._eye_aspect_ratio(landmarks, [33, 160, 158, 133, 153, 144], w, h)
            right_ear = self._eye_aspect_ratio(landmarks, [362, 385, 387, 263, 373, 380], w, h)
            ear = (left_ear + right_ear) / 2
            return ear < 0.18
        except Exception:
            return False

    @staticmethod
    def _eye_aspect_ratio(landmarks: Any, idx: List[int], w: int, h: int) -> float:
        pts = [(landmarks[i].x * w, landmarks[i].y * h) for i in idx]
        p1, p2, p3, p4, p5, p6 = pts
        vertical1 = math.dist(p2, p6)
        vertical2 = math.dist(p3, p5)
        horizontal = math.dist(p1, p4)
        if horizontal <= 1e-6:
            return 0.3
        return (vertical1 + vertical2) / (2.0 * horizontal)

    # ==================== Qwen-VL 融合 ====================

    def _init_vlm_client(self):
        if self._vl_client is not None:
            return
        try:
            from models.vision.qwen_vl_api import QwenVLClient
            self._vl_client = QwenVLClient()
        except Exception as exc:
            print(f"[UserStateDetector] Qwen-VL 客户端初始化失败：{exc}")
            self._vl_client = None


    def _init_emotion_recognizer(self):
        """
        初始化 DeepFace 表情识别模块。
        这里只创建 EmotionRecognizer；如果 deepface/tf-keras/权重不可用，会自动降级，不影响基础状态检测。
        """
        if not self._emotion_enabled:
            return
        if self._emotion_recognizer is not None:
            return
        try:
            from models.vision.emotion_recognizer import EmotionRecognizer
            self._emotion_recognizer = EmotionRecognizer(
                enabled=True,
                min_confidence=0.70,
                min_margin=0.18,
                analyze_interval=2.0,
                smoothing_window=3,
            )
            print("[UserStateDetector] DeepFace 表情识别模块已加载（保守模式）。")
        except Exception as exc:
            print(f"[UserStateDetector] DeepFace 表情识别不可用：{exc}")
            self._emotion_recognizer = None

    def _maybe_apply_vlm(self, frame: Any, base_state: dict) -> dict:
        """
        Qwen-VL + DeepFace 表情识别融合。

        只改内部链路，不改 get_state() 对外接口：
        - DeepFace 先给出表情初判；
        - 表情结果会作为补充信息传入 Qwen-VL prompt；
        - Qwen-VL 输出最终状态；
        - 再把表情标签、描述、建议融合进最终 state。
        """
        if not self._vlm_enabled:
            return base_state

        self._init_vlm_client()
        if self._vl_client is None:
            return base_state

        now = time.time()
        if now - self._last_vlm_at < self._vlm_interval:
            # 如果上一轮 VLM 状态仍然较新，而且是有价值状态，可短时间保持
            if self._last_vlm_state and now - self._last_vlm_at < self._vlm_interval * 1.6:
                return self._fuse_states(base_state, self._last_vlm_state)
            return base_state

        self._last_vlm_at = now

        emotion_result = None
        try:
            if self._emotion_enabled:
                self._init_emotion_recognizer()
            if self._emotion_recognizer is not None:
                emotion_result = self._emotion_recognizer.analyze_frame(frame)
        except Exception as exc:
            print(f"[UserStateDetector] DeepFace 表情分析失败：{exc}")
            emotion_result = None

        try:
            # qwen_vl_api.py 如果已经加入 build_prompt_with_emotion，就使用表情增强提示词；否则自动退回默认提示词。
            prompt = None
            try:
                from models.vision.qwen_vl_api import build_prompt_with_emotion
                prompt = build_prompt_with_emotion(emotion_result)
            except Exception:
                prompt = None

            if prompt:
                vlm_state = self._vl_client.analyze_frame(frame, prompt=prompt)
            else:
                vlm_state = self._vl_client.analyze_frame(frame)

            if is_valid_state(vlm_state) and vlm_state.get("state_code") != STATE_UNKNOWN:
                # normal 默认不主动打扰
                if vlm_state.get("state_code") == STATE_NORMAL:
                    vlm_state["need_response"] = False

                # 表情识别结果不新增字段，只增强 tags / description / suggestion / source。
                if emotion_result and self._emotion_recognizer is not None:
                    try:
                        vlm_state = self._emotion_recognizer.enhance_state(vlm_state, emotion_result)
                    except Exception as exc:
                        print(f"[UserStateDetector] 表情状态融合失败：{exc}")

                self._last_vlm_state = vlm_state
                return self._fuse_states(base_state, vlm_state)

        except Exception as exc:
            print(f"[UserStateDetector] Qwen-VL 分析失败：{exc}")

        # 如果 Qwen-VL 失败，但 DeepFace 有结果，则至少把表情结果融合进本地规则状态。
        if emotion_result and self._emotion_recognizer is not None:
            try:
                return self._emotion_recognizer.enhance_state(base_state, emotion_result)
            except Exception as exc:
                print(f"[UserStateDetector] 本地表情状态融合失败：{exc}")

        return base_state

    def _fuse_states(self, base_state: dict, vlm_state: dict) -> dict:
        """
        状态融合原则：
        - camera_error / away 等硬状态优先保留本地规则。
        - Qwen-VL 如果判断 tired/distracted/focused/low_light，可覆盖 normal。
        - 不让 Qwen-VL 的 away 覆盖“最近检测到脸”的本地结果，避免误判。
        """
        base_code = base_state.get("state_code", STATE_UNKNOWN)
        vlm_code = vlm_state.get("state_code", STATE_UNKNOWN)

        if base_code == STATE_CAMERA_ERROR:
            return base_state

        if base_code == STATE_AWAY:
            # 本地确认长时间无人，优先 away
            return base_state

        # 如果本地确认人在，VLM 的 away 不覆盖
        if vlm_code == STATE_AWAY and base_code in {STATE_NORMAL, STATE_FOCUSED, STATE_DISTRACTED, STATE_TIRED, STATE_RETURN, STATE_STUDY_LONG, STATE_LOW_LIGHT}:
            return base_state

        priority = {
            STATE_TIRED: 90,
            STATE_DISTRACTED: 80,
            STATE_STUDY_LONG: 70,
            STATE_LOW_LIGHT: 60,
            STATE_RETURN: 55,
            STATE_FOCUSED: 50,
            STATE_NORMAL: 40,
            STATE_UNKNOWN: 10,
        }
        chosen = vlm_state if priority.get(vlm_code, 0) > priority.get(base_code, 0) else base_state

        # 合并描述、标签和来源
        merged = copy.deepcopy(chosen)
        tags = []
        for tag in base_state.get("tags", []) + vlm_state.get("tags", []):
            if tag not in tags:
                tags.append(tag)
        sources = self._merge_source(base_state.get("source", []), vlm_state.get("source", []))
        sources = self._merge_source(sources, "fusion")

        if chosen is vlm_state:
            # 如果 VLM 选中，也保留本地“人在座位”信息
            if "在座位" in base_state.get("tags", []) and "在座位" not in tags:
                tags.append("在座位")
        merged["tags"] = tags[:8]
        merged["source"] = sources
        if merged.get("state_code") == STATE_NORMAL:
            merged["need_response"] = False
        return self._normalize_state(merged)

    # ==================== 状态构造与更新 ====================

    def _build_state(
        self,
        state_code: str,
        description: str,
        tags: List[str],
        confidence: float,
        need_response: bool,
        suggestion: str,
        source: List[str],
    ) -> dict:
        if state_code not in ALL_STATE_CODES:
            state_code = STATE_UNKNOWN
        state = {
            "state_code": state_code,
            "state_name": STATE_NAME_MAP.get(state_code, "未知状态"),
            "description": description,
            "tags": list(tags or []),
            "confidence": round(max(0.0, min(1.0, float(confidence))), 2),
            "duration": 0.0,
            "need_response": bool(need_response),
            "suggestion": suggestion or "",
            "source": self._merge_source([], source or []),
        }
        return self._normalize_state(state)

    def _normalize_state(self, state: dict) -> dict:
        code = state.get("state_code", STATE_UNKNOWN)
        if code not in ALL_STATE_CODES:
            code = STATE_UNKNOWN
        normalized = create_empty_state(code)
        normalized.update({
            "state_code": code,
            "state_name": STATE_NAME_MAP.get(code, state.get("state_name", "未知状态")),
            "description": str(state.get("description", "") or ""),
            "tags": list(state.get("tags", []) or []),
            "confidence": round(max(0.0, min(1.0, float(state.get("confidence", 0.0) or 0.0))), 2),
            "duration": round(float(state.get("duration", 0.0) or 0.0), 2),
            "need_response": bool(state.get("need_response", False)),
            "suggestion": str(state.get("suggestion", "") or ""),
            "source": self._merge_source([], state.get("source", []) or []),
        })
        if normalized["state_code"] == STATE_NORMAL:
            normalized["need_response"] = False
        return normalized

    def _update_state(self, new_state: dict):
        if not is_valid_state(new_state):
            new_state = create_empty_state(STATE_UNKNOWN)

        now = time.time()
        new_code = new_state.get("state_code", STATE_UNKNOWN)

        with self._lock:
            if new_code != self._last_state_code:
                self._last_state_code = new_code
                self._state_since = now
            new_state["duration"] = round(now - self._state_since, 2)

            # 主动回应冷却，避免桌宠刷屏
            if new_state.get("need_response"):
                last = self._last_response_at.get(new_code, 0.0)
                if now - last >= self._response_cooldown:
                    self._last_response_at[new_code] = now
                else:
                    new_state["need_response"] = False

            old_code = self._current_state.get("state_code")
            self._current_state = copy.deepcopy(new_state)

        if self._callback and new_code != old_code:
            try:
                self._callback(copy.deepcopy(new_state))
            except Exception as exc:
                print(f"[UserStateDetector] 状态回调函数执行失败：{exc}")

    @staticmethod
    def _merge_source(existing: Any, new_item: Any) -> List[str]:
        result: List[str] = []
        items: List[Any] = []
        if isinstance(existing, list):
            items.extend(existing)
        elif existing:
            items.append(existing)
        if isinstance(new_item, list):
            items.extend(new_item)
        elif new_item:
            items.append(new_item)
        for item in items:
            text = str(item)
            if text and text not in result:
                result.append(text)
        return result

    def _draw_preview(self, frame: Any, state: dict):
        try:
            text = f"{state.get('state_code')} | {state.get('state_name')} | {state.get('source')}"
            self._cv2.putText(frame, text, (20, 40), self._cv2.FONT_HERSHEY_SIMPLEX, 0.75, (0, 255, 0), 2)
            self._cv2.imshow("UserStateDetector Preview", frame)
            key = self._cv2.waitKey(1) & 0xFF
            if key == ord('q'):
                self._is_running = False
        except Exception:
            pass


# 简单手动测试：python models/vision/user_state_detector.py
if __name__ == "__main__":
    detector = UserStateDetector(show_preview=True, enable_vlm=False)
    detector.start()
    try:
        while True:
            print(detector.get_state())
            time.sleep(3)
    except KeyboardInterrupt:
        detector.stop()
