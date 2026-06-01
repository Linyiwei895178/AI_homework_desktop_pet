"""
AI_Desktop_Pet - 程序入口
启动桌面UI，加载桌宠，处理事件循环
"""
import sys
import os
import time

# 将项目根目录加入 sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from app.ui.desktop_pet import DesktopPet
from app.controller.event_handler import EventHandler
from app.controller.pet_controller import PetController
from models.state.pet_state import PetState
from models.state.behavior_rules import decide_action
from models.state.echo_team_d_interface import EchoTeamDInterface
from models.nlp.deepseek_api import generate_pet_reply, DeepSeekClient
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
    team_d = EchoTeamDInterface(pet_state)
    logger.info(f"[队员D] 状态初始化: mood={pet_state.mood}, energy={pet_state.energy}, intimacy={pet_state.intimacy}")

    # ====== 3. 初始化 TTS/NLP 接口 (队员C) ======
    team_c = EchoTeamCInterface()

    # 队员C ← 注册队员D的状态回调（对话结束后通知队员D）
    def _on_team_c_chat_event(event):
        if isinstance(event, dict):
            if hasattr(team_d, "api_update_from_chat_emotion"):
                team_d.api_update_from_chat_emotion(event)
            team_d.api_on_chat_finished(int(event.get("word_count", 0) or 0))
        else:
            team_d.api_on_chat_finished(int(event or 0))

    team_c.api_register_logic_callback(_on_team_c_chat_event)

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
    # 取消注释以下代码即可启用摄像头检测：
    # user_detector = UserStateDetector(enable_vlm=False)
    # user_detector.set_mock_state(STATE_NORMAL)
    # team_d.api_bind_vision_detector(user_detector)  # 队员B → 队员D 自动同步
    # user_detector.start()
    # logger.info("[队员B] 用户状态检测器已启动，已绑定队员D")

    # ====== 7. 初始化手势检测器 (队员B，仅通过主入口接入，不改A/C/D核心逻辑) ======
    GESTURE_ENABLED = os.getenv("DESKTOP_PET_GESTURE_ENABLED", "true").strip().lower() in {
        "1", "true", "yes", "y", "on"
    }
    GESTURE_COOLDOWN_SECONDS = 3.0
    GESTURE_RESPONSES = {
        "wave": "我看到你啦！",
        "ok": "收到，OK！",
        "heart": "嘿嘿，我也喜欢你！",
        "raised_hand": "我在呢，有什么事吗？",
    }
    gesture_detector = None
    gesture_timer = None
    gesture_last_response_at = {}

    if GESTURE_ENABLED:
        try:
            gesture_detector = GestureDetector(enable_real=True)
            gesture_detector.start()
            pet._gesture_detector = gesture_detector
            logger.info(f"[队员B] 手势检测器已启动(real={gesture_detector.is_real_active()})")
        except Exception as exc:
            gesture_detector = None
            logger.exception(f"[队员B] 手势检测器启动失败，桌宠继续运行: {exc}")
    else:
        logger.info("[队员B] 手势检测器已通过 DESKTOP_PET_GESTURE_ENABLED 关闭")

    def check_gesture_state():
        """轮询手势状态；同一个手势 3 秒内只响应一次。"""
        if gesture_detector is None:
            return

        try:
            gesture_state = gesture_detector.get_state()
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
            response = GESTURE_RESPONSES.get(gesture_code, "我看到你的手势啦！")
            if hasattr(team_c, "api_play_system_voice"):
                team_c.api_play_system_voice(response, state="happy", action="speak")
            else:
                speak(response, state="happy", action="speak")
        except Exception as exc:
            logger.exception(f"[队员B] 手势检测轮询失败，已忽略本次结果: {exc}")

    if gesture_detector is not None:
        gesture_timer = QTimer()
        gesture_timer.setInterval(300)
        gesture_timer.timeout.connect(check_gesture_state)
        gesture_timer.start()
        pet._gesture_timer = gesture_timer
        logger.info("[主循环] 手势检测轮询已启动（每300ms一次，同手势3秒冷却）")

    # ====== 8. 启动定时状态检测 + 自动回应 ======
    MOCK_ENABLED = os.getenv("DESKTOP_PET_MOCK_USER_STATE", "false").strip().lower() in {
        "1", "true", "yes", "y", "on"
    }  # demo阶段可通过环境变量开启模拟状态

    def check_user_state():
        """定时检测用户状态，更新桌宠行为和对话"""
        if MOCK_ENABLED:
            # demo阶段：使用模拟状态轮换展示功能
            mock_states_cycle = [
                STATE_NORMAL,
                STATE_FOCUSED,
                STATE_DISTRACTED,
                STATE_TIRED,
                STATE_RETURN,
            ]
            import time
            idx = int(time.time() / 10) % len(mock_states_cycle)
            mock_code = mock_states_cycle[idx]

            # 构建模拟状态字典
            user_state = {
                "state_code": mock_code,
                "state_name": {
                    STATE_NORMAL: "正常状态",
                    STATE_FOCUSED: "专注学习",
                    STATE_DISTRACTED: "疑似分心",
                    STATE_TIRED: "疑似疲劳",
                    STATE_RETURN: "回到座位",
                }.get(mock_code, "未知"),
                "description": f"模拟状态: {mock_code}",
                "tags": [mock_code, "mock"],
                "confidence": 0.85,
                "duration": 10.0,
                "need_response": mock_code in (STATE_DISTRACTED, STATE_TIRED),
                "suggestion": "根据用户状态做出合适的回应。",
                "source": ["mock"],
            }
        else:
            # 正式模式：从 UserStateDetector 获取真实状态
            # user_state = user_detector.get_state()
            QTimer.singleShot(3000, check_user_state)
            return  # 真实视觉检测未开启时保持安静

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

        # 6e. 定时循环（每 3 秒检测一次）
        QTimer.singleShot(3000, check_user_state)

    # 启动定时检测（延迟 1 秒后首次执行）
    QTimer.singleShot(1000, check_user_state)
    logger.info(f"[主循环] 定时状态检测已启动（每3秒一次，mock={MOCK_ENABLED}）")

    # ====== 9. 启动事件循环（Qt主事件循环） ======
    logger.info("启动桌面宠物事件循环...")
    try:
        pet.run()
    except KeyboardInterrupt:
        logger.info("用户中断，桌宠退出。")
    except Exception as e:
        logger.exception(f"运行时异常: {e}")
    finally:
        # 停止用户状态检测器（如果已启动）
        # if "user_detector" in dir() and user_detector:
        #     user_detector.stop()
        if gesture_timer is not None:
            gesture_timer.stop()
        if gesture_detector is not None:
            gesture_detector.stop()
        if getattr(pet, "_running", False):
            pet.close()
        logger.info("AI_Desktop_Pet 已退出。")


if __name__ == "__main__":
    main()
