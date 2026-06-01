"""
AI_Desktop_Pet - 程序入口
启动桌面UI，加载桌宠，处理事件循环

模块结构（8大模块）：
- utils:    config, logger, event_log, time_utils, safe_json, file_manager
- app/ui:   DesktopPet, widgets, pet_motion, cloud_panel, feedback_bubble, ui_settings_store
- app/controller: EventHandler, PetController
- app/services: EventBus, AppContext, SyncScheduler, DemoMode
- models/state: PetState, BehaviorRules, EchoTeamDInterface, UserProfile, PetLeveling, StateSerialization
- models/nlp:  DeepSeekClient, PromptBuilder, EmotionAnalyzer, ProactiveEventBuilder
- models/tts:  TTSEngine, TTSManager, SoundEffectManager, EchoTeamCInterface
- models/vision: UserStateDetector, ComputerActivityDetector, QwenVLClient, ScreenUsageTracker, GestureDetector, CompanionEventBuilder
- models/cloud: CloudConfig, CloudModels, SupabaseCloudService, SharedPetRoomManager
"""
import sys
import os
from pathlib import Path

# 将项目根目录加入 sys.path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

# ── Team A: UI ──
from app.ui.desktop_pet import DesktopPet
from app.controller.event_handler import EventHandler
from app.controller.pet_controller import PetController
# ── Team D: State ──
from models.state.pet_state import PetState
from models.state.behavior_rules import decide_action
from models.state.echo_team_d_interface import EchoTeamDInterface
# ── Team C: NLP / TTS ──
from models.nlp.deepseek_api import generate_pet_reply, DeepSeekClient
from models.tts.tts_manager import speak
from models.tts.echo_team_c_interface import EchoTeamCInterface
# ── Team B: Vision ──
from models.vision.qwen_vl_api import get_user_state, QwenVLClient
from models.vision.user_state_detector import (
    UserStateDetector,
    STATE_NORMAL, STATE_FOCUSED, STATE_DISTRACTED, STATE_TIRED,
    STATE_AWAY, STATE_RETURN, STATE_STUDY_LONG, STATE_LOW_LIGHT,
    STATE_CAMERA_ERROR, STATE_UNKNOWN,
)
# ── Utils ──
from utils.logger import setup_logger
from utils.event_log import get_event_log
from utils.time_utils import CooldownTracker
from utils.safe_json import safe_read_json, safe_write_json
from utils.file_manager import FileManager, file_manager
from app.services.event_bus import get_event_bus
from app.services.app_context import AppContext
from app.services.demo_mode import MockUserStateProvider


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
    team_d = EchoTeamDInterface(pet_state)
    logger.info(f"[队员D] 状态初始化: mood={pet_state.mood}, energy={pet_state.energy}, intimacy={pet_state.intimacy}")

    # ====== 3. 初始化 TTS/NLP 接口 (队员C) ======
    team_c = EchoTeamCInterface()

    # 队员C ← 注册队员D的状态回调（对话结束后通知队员D）
    team_c.api_register_logic_callback(team_d.api_on_chat_finished)

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

    # ====== 6. 初始化用户状态检测器 (队员B) ======
    MOCK_ENABLED = os.getenv("DESKTOP_PET_MOCK_USER_STATE", "false").strip().lower() in {
        "1", "true", "yes", "y", "on"
    }  # 可通过环境变量强制开启模拟状态
    mock_user_state_provider = MockUserStateProvider(cycle_seconds=10.0)
    required_user_state_fields = {
        "state_code", "state_name", "description", "tags", "confidence",
        "duration", "need_response", "suggestion", "source",
    }
    allowed_user_state_codes = {
        STATE_NORMAL, STATE_FOCUSED, STATE_DISTRACTED, STATE_TIRED,
        STATE_AWAY, STATE_RETURN, STATE_STUDY_LONG, STATE_LOW_LIGHT,
        STATE_CAMERA_ERROR, STATE_UNKNOWN,
    }
    vision_fallback_logged = False

    user_detector = None
    VISION_ENABLED = (
        not MOCK_ENABLED
        and os.getenv("DESKTOP_PET_ENABLE_USER_STATE_DETECTOR", "true").strip().lower() in {
            "1", "true", "yes", "y", "on"
        }
    )
    if VISION_ENABLED:
        try:
            user_detector = UserStateDetector(enable_vlm=False)
            user_detector.start()
            logger.info("[队员B] 用户状态检测器已启动")
        except Exception:
            user_detector = None
            logger.exception("[队员B] 用户状态检测器初始化失败，切换到 mock 用户状态，继续启动桌宠。")
    else:
        logger.info(f"[队员B] 使用 mock 用户状态（mock={MOCK_ENABLED}, vision_enabled={VISION_ENABLED}）")

    # ====== 7. 启动定时状态检测 + 自动回应 ======
    def check_user_state():
        """定时检测用户状态，更新桌宠行为和对话"""
        nonlocal vision_fallback_logged

        if MOCK_ENABLED or user_detector is None:
            user_state = mock_user_state_provider.get_state()
        else:
            # 正式模式：从 UserStateDetector 获取真实状态
            try:
                user_state = user_detector.get_state()
            except Exception:
                if not vision_fallback_logged:
                    logger.exception("[队员B] 获取用户状态失败，切换到 mock 用户状态。")
                    vision_fallback_logged = True
                user_state = mock_user_state_provider.get_state()

            if not required_user_state_fields.issubset(set(user_state.keys())):
                if not vision_fallback_logged:
                    logger.warning("[队员B] 用户状态字段不完整，切换到 mock 用户状态。")
                    vision_fallback_logged = True
                user_state = mock_user_state_provider.get_state()

            if user_state.get("state_code") not in allowed_user_state_codes:
                if not vision_fallback_logged:
                    logger.warning("[队员B] 用户状态码不合法，切换到 mock 用户状态。")
                    vision_fallback_logged = True
                user_state = mock_user_state_provider.get_state()

            if user_state.get("state_code") == STATE_CAMERA_ERROR:
                if not vision_fallback_logged:
                    logger.warning("[队员B] 摄像头不可用或权限不足，切换到 mock 用户状态。")
                    vision_fallback_logged = True
                user_state = mock_user_state_provider.get_state()

        # 6a. 更新桌宠状态（队员B → 队员D）
        team_d.api_apply_user_state(user_state)
        logger.info(f"[队员B→队员D] 用户状态: {user_state['state_code']} "
                    f"(置信度: {user_state['confidence']})")

        # 6b. 如果用户需要主动回应，通过队员C生成对话
        if user_state.get("need_response", False):
            suggestion = user_state.get("suggestion", "根据用户当前状态，做出合适的回应。")
            reply = generate_pet_reply(
                text_prompt=suggestion,
                user_state=user_state,
            )
            logger.info(f"[队员C] 桌宠主动回应: {reply}")

            # 播放语音（队员C TTS）
            speak(reply, state=user_state.get("state_code", "neutral"), action="speak")

            # 对话结束后通知队员D更新状态
            team_d.api_on_chat_finished(len(reply))

        # 6c. 根据桌宠状态决定动作（队员D），触发桌宠表情/动画切换（队员A）
        action = team_d.api_decide_action()
        logger.info(f"[队员D→队员A] 决策动作: {action}")
        pet_controller.trigger_action(pet, action)

        # 6d. 检查是否需要主动语音提示（队员D → 队员C）
        if team_d.api_should_speak():
            hint = team_d.api_get_speech_hint()
            if hint:
                logger.info(f"[队员D→队员C] 主动语音提示: {hint}")
                # 播放提示语音（队员C TTS）
                speak(hint, state="hint", action="speak")
                # 注意：主动提示不计入对话字数，不更新状态

    # 启动定时检测（每 3 秒一次）。挂到 pet 上避免 QTimer 被垃圾回收。
    state_timer = QTimer(app)
    state_timer.setInterval(3000)
    state_timer.timeout.connect(check_user_state)
    pet._user_state_timer = state_timer
    state_timer.start()
    logger.info(f"[主循环] 定时状态检测已启动（每3秒一次，mock={MOCK_ENABLED}）")

    # ====== 8. 启动事件循环（Qt主事件循环） ======
    logger.info("启动桌面宠物事件循环...")
    try:
        pet.run()
    except KeyboardInterrupt:
        logger.info("用户中断，桌宠退出。")
    except Exception as e:
        logger.exception(f"运行时异常: {e}")
    finally:
        # 停止用户状态检测器（如果已启动）
        if user_detector:
            user_detector.stop()
        if getattr(pet, "_running", False):
            pet.close()
        logger.info("AI_Desktop_Pet 已退出。")


if __name__ == "__main__":
    main()
