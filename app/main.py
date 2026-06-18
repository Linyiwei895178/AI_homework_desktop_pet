"""
AI_Desktop_Pet - 程序入口
启动桌面UI，加载桌宠，处理事件循环
"""
import sys
import os
import time

# 将项目根目录加入 sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtCore import QEvent, QObject, Qt, QTimer
from PySide6.QtWidgets import QApplication

from app.services.demo_mode import MockUserStateProvider
from app.ui.desktop_pet import DesktopPet
from app.ui.vision_debug_panel import VisionDebugPanel
from app.controller.event_handler import EventHandler
from app.controller.pet_controller import PetController
from models.state.pet_state import PetState
from models.state.behavior_rules import decide_action
from models.state.echo_team_d_interface import EchoTeamDInterface
from models.nlp.deepseek_api import generate_pet_reply, DeepSeekClient
from models.nlp.proactive_event_builder import build_gesture_event
from models.tts.tts_manager import speak
from models.tts.echo_team_c_interface import EchoTeamCInterface
from models.vision.qwen_vl_api import get_user_state, QwenVLClient
from models.vision.user_state_detector import (
    UserStateDetector,
    STATE_NORMAL, STATE_FOCUSED, STATE_DISTRACTED, STATE_TIRED,
    STATE_AWAY, STATE_RETURN, STATE_STUDY_LONG, STATE_LOW_LIGHT,
    STATE_CAMERA_ERROR, STATE_UNKNOWN,
)
from models.vision.gesture_detector import GESTURE_NONE, GestureDetector
from models.vision.shared_camera import SharedCameraCapture
from models.vision.vision_runtime_api import VisionRuntimeAPI
from utils.logger import setup_logger


def main():
    """
    主函数：初始化所有模块，通过接口层串联，启动事件循环

    模块分工：
    - 队员A (UI):  DesktopPet, EventHandler, PetController
    - 队员B (Vision): UserStateDetector, QwenVLClient
    - 队员C (TTS/NLP): EchoTeamCInterface, DeepSeekClient, speak
    - 队员D (State):  EchoTeamDInterface, PetState, BehaviorRules
    """
    # 初始化日志
    logger = setup_logger("AI_Desktop_Pet")
    logger.info("=" * 50)
    logger.info("AI_Desktop_Pet 启动中...")
    logger.info("=" * 50)

    # ====== 1. 初始化桌宠 UI (队员A) ======
    app = QApplication.instance() or QApplication(sys.argv)

    pet_image_path = os.path.join(
        "assets", "images", "cat_image_smile_001.png"
    )
    pet = DesktopPet(image_path=pet_image_path, position=(100, 100))
    logger.info(f"桌宠图片加载: {pet_image_path}")

    # ====== 2. 初始化桌宠状态 (队员D) ======
    pet_state = PetState()
    try:
        pet_state.load_state()
        logger.info("[队员D] 已从 logs/pet_state.json 恢复状态")
    except Exception:
        pass
    team_d = EchoTeamDInterface(pet_state)
    logger.info(f"[队员D] 状态初始化: mood={pet_state.mood}, energy={pet_state.energy}, intimacy={pet_state.intimacy}")

    # ====== 3. 初始化 TTS/NLP 接口 (队员C) ======
    team_c = EchoTeamCInterface()
    pet.attach_team_interfaces(team_c=team_c, team_d=team_d, external=True)

    # 队员C ← 对话结束：更新队员D状态并刷新状态栏/仪表盘
    team_c.api_register_logic_callback(pet._handle_team_c_chat_event)

    # 队员D ← 注册队员C的状态监听（状态变化时通知队员C）
    team_d.api_register_status_listener(lambda event: logger.info(f"[队员C←队员D] 状态事件: {event}"))

    logger.info("[队员C←→队员D] 双向接口绑定完成")

    # ====== 4. 初始化控制器和事件处理器 (队员A) ======
    pet_controller = PetController(pet, pet_state)
    event_handler = EventHandler(pet, pet_controller)

    # ====== 5. 绑定鼠标事件回调 (队员A) ======
    pet.on_drag_callback = event_handler.handle_drag
    pet.on_click_callback = event_handler.handle_click
    pet.on_right_click_callback = pet.close
    logger.info("[队员A] 鼠标事件回调绑定完成")

    # ====== 6. 队员B视觉模块配置 ======
    def env_bool(name: str, default: bool = False) -> bool:
        raw = os.getenv(name)
        if raw is None:
            return bool(default)
        return raw.strip().lower() in {"1", "true", "yes", "y", "on"}

    MOCK_ENABLED = os.getenv("DESKTOP_PET_MOCK_USER_STATE", "false").strip().lower() in {
        "1", "true", "yes", "y", "on"
    }  # 摄像头不可用或演示阶段可开启模拟状态
    USER_STATE_ENABLED = env_bool("DESKTOP_PET_USER_STATE_ENABLED", True)
    CAMERA_START_ENABLED = env_bool("DESKTOP_PET_CAMERA_ENABLED", False)
    GESTURE_FEATURE_ENABLED = env_bool("DESKTOP_PET_GESTURE_FEATURE_ENABLED", True)
    GESTURE_START_ENABLED = env_bool("DESKTOP_PET_GESTURE_ENABLED", False)
    DEEPFACE_ENABLED = env_bool("DESKTOP_PET_DEEPFACE_ENABLED", False)
    VLM_ENABLED = env_bool("DESKTOP_PET_QWEN_VL_ENABLED", env_bool("DESKTOP_PET_VLM_ENABLED", False))
    FACE_MIMIC_ENABLED = env_bool("DESKTOP_PET_FACE_MIMIC_ENABLED", False)
    CAMERA_INDEX = int(os.getenv("DESKTOP_PET_CAMERA_INDEX", "0") or 0)
    CAMERA_WIDTH = max(160, int(os.getenv("DESKTOP_PET_CAMERA_WIDTH", "320") or 320))
    CAMERA_HEIGHT = max(120, int(os.getenv("DESKTOP_PET_CAMERA_HEIGHT", "240") or 240))
    CAMERA_READ_INTERVAL_SECONDS = max(
        0.03,
        float(os.getenv("DESKTOP_PET_CAMERA_READ_INTERVAL", "0.07") or 0.07),
    )
    USER_DETECT_INTERVAL_SECONDS = max(
        0.2,
        float(os.getenv("DESKTOP_PET_USER_DETECT_INTERVAL", "0.4") or 0.4),
    )
    EMOTION_INTERVAL_SECONDS = max(
        0.5,
        float(os.getenv("DESKTOP_PET_EMOTION_INTERVAL", "0.7") or 0.7),
    )
    logger.info(
        "[队员B] 轻量模式配置: "
        f"camera_start={CAMERA_START_ENABLED}, gesture_start={GESTURE_START_ENABLED}, "
        f"deepface={DEEPFACE_ENABLED}, qwen_vl={VLM_ENABLED}, face_mimic={FACE_MIMIC_ENABLED}, "
        f"camera={CAMERA_WIDTH}x{CAMERA_HEIGHT}@{CAMERA_READ_INTERVAL_SECONDS:.2f}s, "
        f"user_detect_interval={USER_DETECT_INTERVAL_SECONDS:.1f}s, "
        f"emotion_interval={EMOTION_INTERVAL_SECONDS:.1f}s"
    )

    # ====== 7. 初始化共享摄像头 (队员B) ======
    shared_camera = None
    initial_camera_requested = CAMERA_START_ENABLED or (GESTURE_FEATURE_ENABLED and GESTURE_START_ENABLED)
    if initial_camera_requested:
        try:
            shared_camera = SharedCameraCapture(
                camera_index=CAMERA_INDEX,
                width=CAMERA_WIDTH,
                height=CAMERA_HEIGHT,
                read_interval=CAMERA_READ_INTERVAL_SECONDS,
            )
            if shared_camera.start():
                pet._shared_camera = shared_camera
                logger.info(
                    f"[队员B] 共享摄像头已启动(index={CAMERA_INDEX}, "
                    f"{CAMERA_WIDTH}x{CAMERA_HEIGHT}, interval={CAMERA_READ_INTERVAL_SECONDS:.2f}s)"
                )
            else:
                logger.warning(f"[队员B] 共享摄像头启动失败: {shared_camera.last_error()}")
                shared_camera = None
        except Exception as exc:
            shared_camera = None
            logger.exception(f"[队员B] 共享摄像头启动异常，视觉模块将降级: {exc}")
    else:
        logger.info("[队员B] 默认轻量启动：摄像头默认关闭，等待 q 键或 UI 开关手动开启。")

    # ====== 8. 初始化用户状态检测器 (队员B B-4) ======
    user_detector = None
    mock_user_state_provider = MockUserStateProvider()
    if USER_STATE_ENABLED and not MOCK_ENABLED and shared_camera is not None:
        try:
            user_detector = UserStateDetector(
                detect_interval=USER_DETECT_INTERVAL_SECONDS,
                emotion_interval=EMOTION_INTERVAL_SECONDS,
                enable_vlm=VLM_ENABLED,
                enable_deepface=DEEPFACE_ENABLED,
                enable_face_mimic=FACE_MIMIC_ENABLED,
                frame_provider=shared_camera,
            )
            user_detector.start()
            pet._user_state_detector = user_detector
            logger.info("[队员B] 用户状态检测器已启动，使用共享摄像头")
        except Exception as exc:
            user_detector = None
            logger.exception(f"[队员B] 用户状态检测器启动失败，将使用mock状态: {exc}")
    elif USER_STATE_ENABLED:
        logger.info("[队员B] 用户状态检测器使用mock状态")
    else:
        logger.info("[队员B] 用户状态检测器已关闭")

    # ====== 9. 初始化手势检测器 (队员B B-5) ======
    GESTURE_COOLDOWN_SECONDS = 3.0
    GESTURE_POLL_INTERVAL_MS = max(200, int(os.getenv("DESKTOP_PET_GESTURE_POLL_MS", "200") or 200))
    GESTURE_DETECT_INTERVAL_SECONDS = max(
        0.25,
        float(os.getenv("DESKTOP_PET_GESTURE_DETECT_INTERVAL", "0.25") or 0.25),
    )
    GESTURE_ZOOM_APPLY_INTERVAL_SECONDS = max(
        0.30,
        float(os.getenv("DESKTOP_PET_GESTURE_ZOOM_APPLY_INTERVAL", "0.30") or 0.30),
    )
    GESTURE_ZOOM_MIN_DELTA = max(
        0.10,
        float(os.getenv("DESKTOP_PET_GESTURE_ZOOM_MIN_DELTA", "0.10") or 0.10),
    )
    gesture_detector = None
    gesture_timer = None
    gesture_last_response_at = {}
    gesture_zoom_last_scale = None
    gesture_zoom_last_apply_at = 0.0
    last_runtime_action = {
        "action_code": "",
        "last_trigger_time": None,
    }

    if GESTURE_FEATURE_ENABLED and GESTURE_START_ENABLED and shared_camera is not None:
        try:
            gesture_detector = GestureDetector(
                enable_real=shared_camera is not None,
                frame_provider=shared_camera,
                detect_interval=GESTURE_DETECT_INTERVAL_SECONDS,
            )
            gesture_detector.start()
            pet._gesture_detector = gesture_detector
            logger.info(f"[队员B] 手势检测器已启动(real={gesture_detector.is_real_active()})")
        except Exception as exc:
            gesture_detector = None
            logger.exception(f"[队员B] 手势检测器启动失败，桌宠继续运行: {exc}")
    else:
        logger.info("[队员B] 默认轻量启动：手势识别默认关闭，等待 UI 开关手动开启。")

    def apply_gesture_zoom(gesture_state: dict) -> bool:
        """Apply pinch zoom from MediaPipe Hands without triggering speech."""
        nonlocal gesture_zoom_last_scale, gesture_zoom_last_apply_at

        zoom = gesture_state.get("zoom") if isinstance(gesture_state, dict) else None
        if not isinstance(zoom, dict):
            return False

        now = time.monotonic()
        if not zoom.get("active"):
            return False

        try:
            scale = float(zoom.get("scale_ratio", zoom.get("smooth_scale")))
        except (TypeError, ValueError):
            return False

        if now - gesture_zoom_last_apply_at < GESTURE_ZOOM_APPLY_INTERVAL_SECONDS:
            return True
        if gesture_zoom_last_scale is not None and abs(scale - gesture_zoom_last_scale) < GESTURE_ZOOM_MIN_DELTA:
            return True

        setter = getattr(pet, "set_pet_scale", None)
        if not callable(setter):
            logger.warning("[队员B] 未找到桌宠缩放接口 set_pet_scale，跳过本次手势缩放。")
            return False

        applied_scale = setter(scale)
        if applied_scale is None:
            current_scale = getattr(pet, "current_pet_scale", lambda: scale)
            applied_scale = current_scale() if callable(current_scale) else scale
        try:
            zoom["applied_scale"] = round(float(applied_scale), 3)
            gesture_state["zoom"] = zoom
        except Exception:
            pass
        gesture_zoom_last_scale = float(applied_scale)
        gesture_zoom_last_apply_at = now
        logger.info(
            "[队员B] 手势缩放应用: "
            f"pinch={zoom.get('pinch_distance')}, scale={float(applied_scale):.2f}"
        )
        return True

    def check_gesture_state():
        """轮询手势状态；同一个手势 3 秒内只响应一次。"""
        if gesture_detector is None:
            return

        try:
            gesture_state = gesture_detector.get_state()
            if apply_gesture_zoom(gesture_state):
                return

            gesture_code = str(gesture_state.get("gesture_code") or GESTURE_NONE).strip()
            if gesture_code == GESTURE_NONE or not gesture_state.get("need_response", False):
                return

            now = time.monotonic()
            last_at = gesture_last_response_at.get(gesture_code, 0.0)
            if now - last_at < GESTURE_COOLDOWN_SECONDS:
                return
            gesture_last_response_at[gesture_code] = now

            logger.info(
                f"[队员B→队员C] 手势事件: {gesture_code} "
                f"(置信度: {gesture_state.get('confidence')})"
            )
            event_data = build_gesture_event(
                gesture_type=gesture_code,
                confidence=gesture_state.get("confidence", 0.0),
                duration=gesture_state.get("duration", 0.0),
            )
            event_data.update({
                "gesture_code": gesture_code,
                "gesture_name": gesture_state.get("gesture_name", ""),
                "description": gesture_state.get("description", ""),
                "suggestion": gesture_state.get("suggestion", ""),
                "source": gesture_state.get("source", []),
                "mood": "happy",
                "voice_action": "speak",
            })
            if hasattr(team_c, "api_on_status_event"):
                team_c.api_on_status_event(event_data)
            else:
                speak("我看到你的手势啦！", state="happy", action="speak")
        except Exception as exc:
            logger.exception(f"[队员B] 手势检测轮询失败，已忽略本次结果: {exc}")

    if gesture_detector is not None:
        gesture_timer = QTimer()
        gesture_timer.setInterval(GESTURE_POLL_INTERVAL_MS)
        gesture_timer.timeout.connect(check_gesture_state)
        gesture_timer.start()
        pet._gesture_timer = gesture_timer
        logger.info(
            "[主循环] 手势检测轮询已启动"
            f"（每{GESTURE_POLL_INTERVAL_MS}ms一次，同手势3秒冷却，支持pinch缩放）"
        )

    camera_detection_enabled = bool(shared_camera is not None and shared_camera.is_running())
    gesture_detection_enabled = bool(gesture_detector is not None)
    camera_toggle_in_progress = False
    gesture_toggle_in_progress = False
    last_camera_toggle_at = 0.0
    last_gesture_toggle_at = 0.0
    CAMERA_TOGGLE_DEBOUNCE_SECONDS = 1.5

    def build_camera_off_state() -> dict:
        return {
            "state_code": STATE_UNKNOWN,
            "state_name": "摄像头已关闭",
            "description": "用户状态检测已暂停",
            "tags": ["camera_off"],
            "confidence": 1.0,
            "duration": 0.0,
            "need_response": False,
            "suggestion": "",
            "source": ["camera_off"],
        }

    def ensure_shared_camera() -> bool:
        """Start the shared camera once and reuse it across B modules."""
        nonlocal shared_camera, camera_detection_enabled

        if shared_camera is not None and shared_camera.is_running():
            camera_detection_enabled = True
            return True

        try:
            shared_camera = SharedCameraCapture(
                camera_index=CAMERA_INDEX,
                width=CAMERA_WIDTH,
                height=CAMERA_HEIGHT,
                read_interval=CAMERA_READ_INTERVAL_SECONDS,
            )
            if shared_camera.start():
                pet._shared_camera = shared_camera
                camera_detection_enabled = True
                logger.info(
                    f"[队员B] 共享摄像头已启动(index={CAMERA_INDEX}, "
                    f"{CAMERA_WIDTH}x{CAMERA_HEIGHT}, interval={CAMERA_READ_INTERVAL_SECONDS:.2f}s)"
                )
                return True

            logger.warning(f"[队员B] 共享摄像头启动失败: {shared_camera.last_error()}")
        except Exception as exc:
            logger.exception(f"[队员B] 共享摄像头启动异常，已降级: {exc}")

        shared_camera = None
        pet._shared_camera = None
        camera_detection_enabled = False
        return False

    def start_user_detector() -> bool:
        """开启共享摄像头和用户状态检测；不会自动开启手势。"""
        nonlocal shared_camera, user_detector, camera_detection_enabled

        if camera_detection_enabled and (not USER_STATE_ENABLED or MOCK_ENABLED or user_detector is not None):
            logger.info("[队员B] 摄像头检测已处于开启状态，忽略重复开启。")
            return True

        if not ensure_shared_camera():
            logger.warning("[队员B] 摄像头打开失败，主程序继续运行并降级为mock/unknown状态")
            return False

        if USER_STATE_ENABLED and not MOCK_ENABLED:
            try:
                if user_detector is not None:
                    user_detector.stop()
                user_detector = UserStateDetector(
                    detect_interval=USER_DETECT_INTERVAL_SECONDS,
                    emotion_interval=EMOTION_INTERVAL_SECONDS,
                    enable_vlm=VLM_ENABLED,
                    enable_deepface=DEEPFACE_ENABLED,
                    enable_face_mimic=FACE_MIMIC_ENABLED,
                    frame_provider=shared_camera,
                )
                user_detector.start()
                pet._user_state_detector = user_detector
                logger.info("[队员B] 用户状态检测器已启动，使用共享摄像头")
            except Exception as exc:
                user_detector = None
                pet._user_state_detector = None
                try:
                    if shared_camera is not None:
                        shared_camera.stop()
                except Exception:
                    pass
                shared_camera = None
                pet._shared_camera = None
                camera_detection_enabled = False
                logger.exception(f"[队员B] 用户状态检测器启动失败，将使用mock/unknown状态: {exc}")
                return False
        elif USER_STATE_ENABLED:
            user_detector = None
            pet._user_state_detector = None
            logger.info("[队员B] 用户状态检测器使用mock/unknown状态")

        camera_detection_enabled = True
        logger.info("[队员B] 摄像头检测已开启")
        return True

    def stop_gesture_detector() -> None:
        """关闭手势识别，不关闭用户状态检测摄像头。"""
        nonlocal gesture_detector, gesture_timer, gesture_detection_enabled

        if gesture_detector is None and gesture_timer is None and not gesture_detection_enabled:
            logger.info("[队员B] 手势识别已处于关闭状态，忽略重复关闭。")
            return

        gesture_detection_enabled = False
        try:
            if gesture_timer is not None:
                gesture_timer.stop()
                gesture_timer.deleteLater()
                gesture_timer = None
                pet._gesture_timer = None
        except Exception as exc:
            logger.warning(f"[队员B] 手势轮询定时器关闭异常，已忽略: {exc}")

        try:
            if gesture_detector is not None:
                gesture_detector.stop()
                gesture_detector = None
                pet._gesture_detector = None
        except Exception as exc:
            logger.warning(f"[队员B] 手势检测器关闭异常，已忽略: {exc}")

        logger.info("[队员B] 手势识别已关闭")

    def start_gesture_detector() -> bool:
        """开启手势识别；摄像头关闭时自动先开启摄像头。"""
        nonlocal gesture_detector, gesture_timer, gesture_detection_enabled

        if not GESTURE_FEATURE_ENABLED:
            logger.info("[队员B] 当前配置未启用手势识别功能。")
            gesture_detection_enabled = False
            return False

        if gesture_detector is not None and gesture_detection_enabled:
            logger.info("[队员B] 手势识别已处于开启状态，忽略重复开启。")
            return True

        if not camera_detection_enabled and not start_user_detector():
            logger.warning("[队员B] 摄像头未开启，手势识别无法启动。")
            gesture_detection_enabled = False
            return False

        try:
            if gesture_timer is not None:
                gesture_timer.stop()
                gesture_timer.deleteLater()
                gesture_timer = None
            if gesture_detector is not None:
                gesture_detector.stop()

            gesture_detector = GestureDetector(
                enable_real=shared_camera is not None,
                frame_provider=shared_camera,
                detect_interval=GESTURE_DETECT_INTERVAL_SECONDS,
            )
            gesture_detector.start()
            pet._gesture_detector = gesture_detector

            gesture_timer = QTimer()
            gesture_timer.setInterval(GESTURE_POLL_INTERVAL_MS)
            gesture_timer.timeout.connect(check_gesture_state)
            gesture_timer.start()
            pet._gesture_timer = gesture_timer
            gesture_detection_enabled = True
            logger.info(
                f"[队员B] 手势识别已开启(real={gesture_detector.is_real_active()}, "
                f"poll={GESTURE_POLL_INTERVAL_MS}ms, detect={GESTURE_DETECT_INTERVAL_SECONDS:.2f}s)"
            )
            return True
        except Exception as exc:
            gesture_detection_enabled = False
            gesture_detector = None
            pet._gesture_detector = None
            logger.exception(f"[队员B] 手势识别启动失败，桌宠继续运行: {exc}")
            return False

    def stop_user_detector() -> None:
        """关闭用户状态检测、手势检测和共享摄像头。"""
        nonlocal shared_camera, user_detector, camera_detection_enabled

        if (
            not camera_detection_enabled
            and shared_camera is None
            and user_detector is None
            and gesture_detector is None
            and gesture_timer is None
        ):
            logger.info("[队员B] 摄像头检测已处于关闭状态，忽略重复关闭。")
            return

        stop_gesture_detector()
        camera_detection_enabled = False

        try:
            if user_detector is not None:
                user_detector.stop()
                user_detector = None
                pet._user_state_detector = None
        except Exception as exc:
            logger.warning(f"[队员B] 用户状态检测器关闭异常，已忽略: {exc}")

        try:
            if shared_camera is not None:
                shared_camera.stop()
                shared_camera = None
                pet._shared_camera = None
        except Exception as exc:
            logger.warning(f"[队员B] 共享摄像头关闭异常，已忽略: {exc}")

        logger.info("[队员B] 摄像头检测已关闭")

    def toggle_user_detector() -> None:
        """q键触发：开关摄像头和 B 模块用户状态检测。"""
        nonlocal camera_toggle_in_progress, last_camera_toggle_at

        now = time.monotonic()
        if camera_toggle_in_progress:
            logger.info("[队员B] 摄像头检测正在切换中，忽略重复q键。")
            return
        if now - last_camera_toggle_at < CAMERA_TOGGLE_DEBOUNCE_SECONDS:
            logger.info("[队员B] q键摄像头切换防抖中，忽略本次按键。")
            return

        camera_toggle_in_progress = True
        last_camera_toggle_at = now
        try:
            if camera_detection_enabled:
                stop_user_detector()
            else:
                start_user_detector()
            sync_vision_runtime_controls()
        finally:
            camera_toggle_in_progress = False

    def toggle_gesture_detector() -> None:
        """UI触发：开关 B 模块手势识别。"""
        nonlocal gesture_toggle_in_progress, last_gesture_toggle_at

        now = time.monotonic()
        if gesture_toggle_in_progress:
            logger.info("[队员B] 手势识别正在切换中，忽略重复操作。")
            return
        if now - last_gesture_toggle_at < CAMERA_TOGGLE_DEBOUNCE_SECONDS:
            logger.info("[队员B] 手势识别切换防抖中，忽略本次操作。")
            return

        gesture_toggle_in_progress = True
        last_gesture_toggle_at = now
        try:
            if gesture_detection_enabled:
                stop_gesture_detector()
            else:
                start_gesture_detector()
            sync_vision_runtime_controls()
        finally:
            gesture_toggle_in_progress = False

    def get_vision_runtime_status() -> dict:
        """给 A 组 UI 使用的 B 模块运行状态快照。"""
        return {
            "camera_enabled": bool(camera_detection_enabled),
            "gesture_enabled": bool(gesture_detection_enabled),
            "debug_preview_visible": is_vision_debug_panel_visible(),
            "deepface_enabled": bool(DEEPFACE_ENABLED),
            "vlm_enabled": bool(VLM_ENABLED),
            "face_mimic_enabled": bool(FACE_MIMIC_ENABLED),
            "camera_available": bool(shared_camera is not None and shared_camera.is_running()),
        }

    def get_runtime_user_state() -> dict | None:
        """Read latest user state without starting detectors."""
        if user_detector is not None:
            try:
                return user_detector.get_state()
            except Exception:
                return None
        try:
            latest = pet_state.get_last_user_state()
            return latest if isinstance(latest, dict) else None
        except Exception:
            return None

    def get_runtime_gesture_state() -> dict | None:
        """Read latest gesture state without starting gesture detection."""
        if gesture_detector is None:
            return None
        try:
            return gesture_detector.get_state()
        except Exception:
            return None

    def get_runtime_action_state() -> dict:
        return dict(last_runtime_action)

    vision_runtime_api = VisionRuntimeAPI(
        shared_camera_getter=lambda: shared_camera,
        camera_enabled_getter=lambda: bool(camera_detection_enabled),
        user_detector_running_getter=lambda: bool(
            user_detector is not None and getattr(user_detector, "_is_running", True)
        ),
        gesture_detector_running_getter=lambda: bool(
            gesture_detector is not None
            and (
                gesture_detector.is_running()
                if hasattr(gesture_detector, "is_running")
                else gesture_detection_enabled
            )
        ),
        user_state_getter=get_runtime_user_state,
        gesture_state_getter=get_runtime_gesture_state,
        pet_state_getter=lambda: pet_state,
        action_state_getter=get_runtime_action_state,
    )

    class CameraToggleKeyFilter(QObject):
        """Qt 全局按键过滤器：q 切换摄像头；输入框聚焦时放行，不影响聊天输入。"""

        def eventFilter(self, obj, event):  # noqa: N802 - Qt API name
            if event.type() != QEvent.Type.KeyPress:
                return False
            if event.key() != Qt.Key.Key_Q:
                return False
            if event.modifiers() & (
                Qt.KeyboardModifier.ControlModifier
                | Qt.KeyboardModifier.AltModifier
                | Qt.KeyboardModifier.MetaModifier
            ):
                return False

            focus_widget = QApplication.focusWidget()
            if focus_widget is not None and (
                focus_widget.inherits("QLineEdit")
                or focus_widget.inherits("QTextEdit")
                or focus_widget.inherits("QPlainTextEdit")
            ):
                return False

            if event.isAutoRepeat():
                event.accept()
                return True

            toggle_user_detector()
            event.accept()
            return True

    camera_toggle_key_filter = CameraToggleKeyFilter(app)
    app.installEventFilter(camera_toggle_key_filter)
    pet._camera_toggle_key_filter = camera_toggle_key_filter
    logger.info("[队员B] q键摄像头/用户状态检测开关已绑定")

    vision_debug_panel = None

    def is_vision_debug_panel_visible() -> bool:
        return vision_debug_panel is not None and vision_debug_panel.isVisible()

    def sync_vision_debug_controls() -> None:
        console = getattr(pet, "_console", None)
        if console is None:
            return
        sync = getattr(console, "sync_vision_debug_state", None)
        if not callable(sync):
            return
        try:
            sync(is_vision_debug_panel_visible())
        except RuntimeError:
            return
        except Exception as exc:
            logger.warning(f"[队员B] 视觉调试控制台状态同步失败，已忽略: {exc}")

    def sync_vision_runtime_controls() -> None:
        console = getattr(pet, "_console", None)
        if console is None:
            return
        for method_name in (
            "sync_camera_detection_state",
            "sync_gesture_detection_state",
            "sync_vision_debug_state",
        ):
            sync = getattr(console, method_name, None)
            if not callable(sync):
                continue
            try:
                sync()
            except RuntimeError:
                return
            except Exception as exc:
                logger.warning(f"[队员B] 视觉控制台状态同步失败({method_name})，已忽略: {exc}")

    def ensure_vision_debug_panel() -> VisionDebugPanel:
        nonlocal vision_debug_panel
        if vision_debug_panel is None:
            vision_debug_panel = VisionDebugPanel(
                detector_getter=lambda: user_detector,
                gesture_getter=(
                    lambda: gesture_detector.get_debug_snapshot()
                    if gesture_detector is not None and hasattr(gesture_detector, "get_debug_snapshot")
                    else (gesture_detector.get_state() if gesture_detector is not None else None)
                ),
                camera_frame_getter=(
                    lambda: shared_camera.get_frame()
                    if shared_camera is not None and hasattr(shared_camera, "get_frame")
                    else None
                ),
                camera_enabled_getter=lambda: camera_detection_enabled,
                refresh_ms=400,
            )
            vision_debug_panel.hide()
            pet._vision_debug_panel = vision_debug_panel
            vision_debug_panel.visibility_changed.connect(lambda _visible: sync_vision_debug_controls())
            logger.info("[队员B] 视觉调试预览窗口已创建")
        return vision_debug_panel

    def set_vision_debug_panel_visible(enabled: bool) -> None:
        panel = ensure_vision_debug_panel()
        if enabled:
            panel.start()
            panel.showMaximized()
            panel.raise_()
            panel.activateWindow()
            panel.update_from_detector()
            logger.info("[队员B] 视觉调试预览窗口已显示")
        else:
            panel.hide()
            logger.info("[队员B] 视觉调试预览窗口已隐藏")
        sync_vision_debug_controls()

    pet._vision_debug_set_visible = set_vision_debug_panel_visible
    pet._vision_debug_is_visible = is_vision_debug_panel_visible
    pet._vision_debug_panel = None
    pet._camera_detection_enabled = lambda: bool(camera_detection_enabled)
    pet._gesture_detection_enabled = lambda: bool(gesture_detection_enabled)
    pet._toggle_camera_detection = toggle_user_detector
    pet._toggle_gesture_detection = toggle_gesture_detector
    pet._start_user_detector = start_user_detector
    pet._stop_user_detector = stop_user_detector
    pet._start_gesture_detector = start_gesture_detector
    pet._stop_gesture_detector = stop_gesture_detector
    pet._get_vision_runtime_status = get_vision_runtime_status
    pet.start_user_detector = start_user_detector
    pet.stop_user_detector = stop_user_detector
    pet.start_gesture_detector = start_gesture_detector
    pet.stop_gesture_detector = stop_gesture_detector
    pet.toggle_user_detector = toggle_user_detector
    pet.toggle_gesture_detector = toggle_gesture_detector
    pet.get_vision_runtime_status = get_vision_runtime_status
    pet._vision_runtime_api = vision_runtime_api
    pet.get_latest_camera_frame_rgb = vision_runtime_api.get_latest_camera_frame_rgb
    pet.get_latest_runtime_snapshot = vision_runtime_api.get_latest_runtime_snapshot

    # ====== 10. 启动定时状态检测 + 自动回应 ======
    SPEECH_HINT_COOLDOWN_SECONDS = 300.0
    USER_STATE_RESPONSE_COOLDOWN_SECONDS = 120.0
    USER_STATE_SILENT_CODES = {STATE_AWAY}
    USER_STATE_SUPPRESS_D_HINT_CODES = {
        STATE_DISTRACTED,
        STATE_TIRED,
        STATE_AWAY,
        STATE_STUDY_LONG,
        STATE_LOW_LIGHT,
        STATE_CAMERA_ERROR,
    }
    USER_STATE_DEFAULT_SUGGESTIONS = {
        STATE_DISTRACTED: "给桌宠：轻轻提醒用户把注意力拉回当前任务，不要表现成桌宠自己难过。",
        STATE_TIRED: "给桌宠：关心用户可能疲劳，建议休息眼睛、喝水或活动一下。",
        STATE_STUDY_LONG: "给桌宠：提醒用户已经学习较久，可以短暂休息后再继续。",
        STATE_LOW_LIGHT: "给桌宠：提醒用户把环境光调亮一点，保护眼睛。",
        STATE_CAMERA_ERROR: "给桌宠：用简短语气提示当前视觉检测可能不稳定。",
    }
    last_speech_hint_text = ""
    last_speech_hint_at = 0.0
    last_user_state_response_at = {}
    shutting_down = False

    def build_user_state_event(user_state: dict) -> dict:
        """把 B 模块 user_state 转成 C 模块可处理的主动状态事件。"""
        state_code = str(user_state.get("state_code", STATE_UNKNOWN) or STATE_UNKNOWN)
        suggestion = str(user_state.get("suggestion", "") or "").strip()
        if not suggestion:
            suggestion = USER_STATE_DEFAULT_SUGGESTIONS.get(
                state_code,
                "给桌宠：根据用户当前状态，用一句简短自然的话做轻量提醒。",
            )
        return {
            "event_type": "user_state_alert",
            "state_code": state_code,
            "description": user_state.get("description", ""),
            "tags": user_state.get("tags", []),
            "confidence": user_state.get("confidence", 0.0),
            "duration": user_state.get("duration", 0.0),
            "need_response": bool(user_state.get("need_response", False)),
            "suggestion": suggestion,
            "source": user_state.get("source", []),
            "action": team_d.api_decide_action(),
            "pet_id": pet_state.pet_id,
            "mood": "neutral",
            "pet_mood": pet_state.mood,
            "energy": pet_state.energy,
            "intimacy": pet_state.intimacy,
        }

    def check_user_state():
        """定时检测用户状态，更新桌宠行为和对话"""
        nonlocal last_speech_hint_text, last_speech_hint_at

        if shutting_down:
            return

        if not USER_STATE_ENABLED:
            if not shutting_down:
                QTimer.singleShot(3000, check_user_state)
            return

        if not camera_detection_enabled:
            user_state = build_camera_off_state()
        elif MOCK_ENABLED or user_detector is None:
            user_state = mock_user_state_provider.get_state()
        else:
            try:
                user_state = user_detector.get_state()
            except Exception as exc:
                logger.exception(f"[队员B] 读取用户状态失败，已降级为mock状态: {exc}")
                user_state = mock_user_state_provider.get_state()

        # 6a. 更新桌宠状态（队员B → 队员D）
        team_d.api_apply_user_state(user_state)
        logger.info(f"[队员B→队员D] 用户状态: {user_state['state_code']} "
                    f"(置信度: {user_state['confidence']})")
        if hasattr(pet, "refresh_pet_stats_ui"):
            pet.refresh_pet_stats_ui(force=True)

        state_code = str(user_state.get("state_code", STATE_UNKNOWN) or STATE_UNKNOWN)
        suppress_pet_mood_hint = state_code in USER_STATE_SUPPRESS_D_HINT_CODES
        user_state_spoke = False

        # 6b. 如果用户需要主动回应，优先使用 B 模块 suggestion 生成 user_state 事件
        if user_state.get("need_response", False):
            now = time.monotonic()
            last_at = last_user_state_response_at.get(state_code, 0.0)
            if state_code in USER_STATE_SILENT_CODES:
                logger.info(f"[队员B→队员C] 用户状态 {state_code} 需要静默等待，跳过主动语音。")
            elif now - last_at < USER_STATE_RESPONSE_COOLDOWN_SECONDS:
                logger.info(
                    f"[队员B→队员C] 用户状态 {state_code} 主动提醒冷却中，跳过。"
                )
            else:
                event_data = build_user_state_event(user_state)
                logger.info(f"[队员B→队员C] 用户状态事件: {event_data}")
                if hasattr(team_c, "api_on_status_event"):
                    reply = team_c.api_on_status_event(event_data)
                else:
                    suggestion = event_data.get("suggestion", "根据用户当前状态，做出合适的回应。")
                    reply = generate_pet_reply(text_prompt=suggestion, user_state=user_state)
                    speak(reply, state=state_code, action="speak")

                logger.info(f"[队员C] 用户状态主动回应: {reply}")
                last_user_state_response_at[state_code] = now
                user_state_spoke = bool(reply)

                # 对话结束后通知队员D更新状态
                if reply:
                    team_d.api_on_chat_finished(len(reply))

        # 6c. 根据桌宠状态决定动作（队员D），触发桌宠表情/动画切换（队员A）
        action = team_d.api_decide_action()
        logger.info(f"[队员D→队员A] 决策动作: {action}")
        last_runtime_action["action_code"] = str(action or "")
        last_runtime_action["last_trigger_time"] = time.time()
        pet_controller.trigger_action(pet, action)

        # 6d. 检查是否需要主动语音提示（队员D → 队员C）
        # 用户状态提醒已经由 B 的 suggestion 控制；避免 distracted/tired/away 被 mood=sad 固定话术覆盖。
        if suppress_pet_mood_hint or user_state_spoke:
            logger.info(
                f"[队员D→队员C] 当前为用户状态提醒链路({state_code})，跳过宠物自身 mood 固定话术。"
            )
        elif team_d.api_should_speak():
            hint = team_d.api_get_speech_hint()
            if hint:
                now = time.monotonic()
                same_hint_in_cooldown = (
                    hint == last_speech_hint_text
                    and now - last_speech_hint_at < SPEECH_HINT_COOLDOWN_SECONDS
                )
                chain_in_cooldown = now - last_speech_hint_at < SPEECH_HINT_COOLDOWN_SECONDS
                if same_hint_in_cooldown or chain_in_cooldown:
                    logger.info(f"[队员D→队员C] 主动语音提示冷却中，跳过: {hint}")
                else:
                    logger.info(f"[队员D→队员C] 主动语音提示: {hint}")
                    last_speech_hint_text = hint
                    last_speech_hint_at = now
                    # 播放提示语音（队员C TTS）
                    speak(hint, state="hint", action="speak")
                    # 注意：主动提示不计入对话字数，不更新状态

        # 6e. 定时循环（每 3 秒检测一次）
        if not shutting_down:
            QTimer.singleShot(3000, check_user_state)

    # 启动定时检测（延迟 1 秒后首次执行）
    QTimer.singleShot(1000, check_user_state)
    logger.info(f"[主循环] 定时状态检测已启动（每3秒一次，mock={MOCK_ENABLED}）")

    # ====== 11. 启动事件循环（Qt主事件循环） ======
    logger.info("启动桌面宠物事件循环...")
    try:
        pet.run()
    except KeyboardInterrupt:
        logger.info("用户中断，桌宠退出。")
    except Exception as e:
        logger.exception(f"运行时异常: {e}")
    finally:
        shutting_down = True
        logger.info("[AI_Desktop_Pet] 正在清理子窗口和后台线程...")
        try:
            app.removeEventFilter(camera_toggle_key_filter)
        except Exception:
            pass
        try:
            if hasattr(team_c, "api_stop_long_text"):
                team_c.api_stop_long_text()
        except Exception as exc:
            logger.warning(f"[队员C] 停止长文本朗读失败，已忽略: {exc}")
        try:
            if hasattr(pet, "stop_text_reading"):
                pet.stop_text_reading()
        except Exception as exc:
            logger.warning(f"[队员C] 停止桌宠朗读失败，已忽略: {exc}")
        if gesture_timer is not None:
            try:
                gesture_timer.stop()
            except Exception:
                pass
            try:
                gesture_timer.deleteLater()
            except Exception:
                pass
        if gesture_detector is not None:
            try:
                gesture_detector.stop()
            except Exception as exc:
                logger.warning(f"[队员B] 手势检测器清理异常，已忽略: {exc}")
        logger.info("[AI_Desktop_Pet] GestureDetector 已停止")
        if user_detector is not None:
            try:
                user_detector.stop()
            except Exception as exc:
                logger.warning(f"[队员B] 用户状态检测器清理异常，已忽略: {exc}")
        logger.info("[AI_Desktop_Pet] UserStateDetector 已停止")
        if shared_camera is not None:
            try:
                shared_camera.stop()
            except Exception as exc:
                logger.warning(f"[队员B] 共享摄像头清理异常，已忽略: {exc}")
        logger.info("[AI_Desktop_Pet] 共享摄像头已释放")
        try:
            if vision_debug_panel is not None:
                vision_debug_panel.shutdown()
            logger.info("[AI_Desktop_Pet] 视觉调试窗口已关闭")
        except Exception as exc:
            logger.warning(f"[AI_Desktop_Pet] 视觉调试窗口清理异常，已忽略: {exc}")
        try:
            if hasattr(pet, "cleanup"):
                pet.cleanup(quit_app=False)
            else:
                try:
                    setattr(pet, "_cleaning_up", True)
                except Exception:
                    pass
                pet.close()
            logger.info("[AI_Desktop_Pet] DesktopPet 主窗口已关闭")
            logger.info("[AI_Desktop_Pet] Live2D 窗口已释放")
        except Exception as exc:
            logger.warning(f"[AI_Desktop_Pet] 桌宠 UI 清理异常，已忽略: {exc}")
        try:
            for widget in list(app.topLevelWidgets()):
                try:
                    widget.hide()
                except Exception:
                    pass
                try:
                    widget.close()
                except Exception:
                    pass
                try:
                    widget.deleteLater()
                except Exception:
                    pass
            QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
            app.processEvents()
            app.closeAllWindows()
            QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
            app.processEvents()
        except Exception:
            pass
        try:
            app.quit()
        except Exception:
            pass
        logger.info("[AI_Desktop_Pet] 清理完成，程序退出。")


if __name__ == "__main__":
    main()
