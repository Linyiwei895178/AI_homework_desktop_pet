"""
AI_Desktop_Pet - 程序入口
启动桌面UI，加载桌宠，处理事件循环
"""
import sys
import os

# 将项目根目录加入 sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.ui.desktop_pet import DesktopPet
from app.controller.event_handler import EventHandler
from app.controller.pet_controller import PetController
from models.state.pet_state import PetState
from models.state.behavior_rules import decide_action
from models.nlp.deepseek_api import generate_pet_reply, DeepSeekClient
from models.tts.tts_manager import speak
from models.vision.qwen_vl_api import get_user_state, QwenVLClient
from models.vision.user_state_detector import (
    UserStateDetector,
    STATE_NORMAL, STATE_FOCUSED, STATE_DISTRACTED, STATE_TIRED,
    STATE_AWAY, STATE_RETURN, STATE_STUDY_LONG, STATE_LOW_LIGHT,
    STATE_CAMERA_ERROR, STATE_UNKNOWN,
)
from utils.logger import setup_logger

# TO_DO: 初始化桌面UI，加载桌宠图片
# TO_DO: 绑定鼠标拖动事件和点击事件
# TO_DO: 启动事件循环
# TO_DO: 启动用户状态检测循环（UserStateDetector）
# TO_DO: 根据用户状态自动调整桌宠行为和对话


def main():
    """
    主函数：初始化桌宠、状态、控制器，启动事件循环
    """
    # 初始化日志
    logger = setup_logger("AI_Desktop_Pet")
    logger.info("AI_Desktop_Pet 启动中...")

    # ====== 1. 初始化桌宠 UI ======
    pet_image_path = os.path.join(
        "assets", "images", "cat_image_smile_001.png"
    )
    pet = DesktopPet(image_path=pet_image_path, position=(100, 100))
    logger.info(f"桌宠图片加载: {pet_image_path}")

    # ====== 2. 初始化桌宠状态 ======
    pet_state = PetState()
    logger.info(f"桌宠状态初始化: mood={pet_state.mood}, energy={pet_state.energy}, intimacy={pet_state.intimacy}")

    # ====== 3. 初始化控制器和事件处理器 ======
    pet_controller = PetController(pet, pet_state)
    event_handler = EventHandler(pet, pet_controller)

    # ====== 4. 绑定鼠标事件回调 ======
    pet.on_drag_callback = event_handler.handle_drag
    pet.on_click_callback = event_handler.handle_click
    pet.on_right_click_callback = pet.close

    # ====== 5. TO_DO: 初始化用户状态检测器（UserStateDetector） ======
    # 取消以下注释即可启用用户状态检测：
    #
    # user_detector = UserStateDetector()
    # user_detector.set_mock_state(STATE_NORMAL)  # demo阶段可设置模拟状态
    # user_detector.start()
    # logger.info("用户状态检测器已启动")

    # ====== 6. TO_DO: 启动定时状态检测 + 自动回应 ======
    # 使用 Tkinter 的 after() 实现定时检测循环：
    #
    # def check_user_state():
    #     """定时检测用户状态，更新桌宠行为和对话"""
    #     # 6a. 获取用户状态（来自 UserStateDetector）
    #     user_state = user_detector.get_state()
    #     logger.info(f"用户状态检测: {user_state['state_code']} (置信度: {user_state['confidence']})")
    #
    #     # 6b. 更新桌宠状态（将用户状态映射为桌宠 mood/energy/intimacy）
    #     pet_state.update_from_user_state(user_state)
    #
    #     # 6c. 如果用户需要主动回应，生成上下文感知的对话
    #     if user_state.get("need_response", False):
    #         suggestion = user_state.get("suggestion", "")
    #         reply = generate_pet_reply(
    #             text_prompt=suggestion or "根据用户当前状态，做出合适的回应。",
    #             user_state=user_state,
    #         )
    #         logger.info(f"桌宠主动回应: {reply}")
    #         # TO_DO: 在桌宠气泡中显示回复 / TTS 播放
    #         # pet.show_speech_bubble(reply)
    #         # speak(reply, state=user_state.get('state_code', 'neutral'), action='speak')
    #
    #     # 6d. 根据桌宠状态决定动作，触发桌宠表情/动画切换
    #     action = decide_action(pet_state)
    #     pet_controller.trigger_action(pet, action)
    #
    #     # 6e. 定时循环（每 3 秒检测一次）
    #     pet.root.after(3000, check_user_state)
    #
    # # 启动定时检测（延迟 1 秒后首次执行）
    # pet.root.after(1000, check_user_state)

    # ====== 7. 启动事件循环（Tkinter主事件循环） ======
    logger.info("启动桌面宠物事件循环...")
    try:
        pet.root.mainloop()
    except KeyboardInterrupt:
        logger.info("用户中断，桌宠退出。")
    except Exception as e:
        logger.error(f"运行时异常: {e}")
    finally:
        # TO_DO: 停止用户状态检测器
        # if 'user_detector' in dir() and user_detector:
        #     user_detector.stop()
        pet.close()
        logger.info("AI_Desktop_Pet 已退出。")


if __name__ == "__main__":
    main()
