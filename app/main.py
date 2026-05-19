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
from models.nlp.deepseek_api import generate_pet_reply
from models.tts.tts_manager import speak
from utils.logger import setup_logger

# TO_DO: 初始化桌面UI，加载桌宠图片
# TO_DO: 绑定鼠标拖动事件和点击事件
# TO_DO: 启动事件循环


def main():
    """
    主函数：初始化桌宠、状态、控制器，启动事件循环
    """
    # 初始化日志
    logger = setup_logger("AI_Desktop_Pet")
    logger.info("AI_Desktop_Pet 启动中...")

    # TO_DO: 初始化桌面UI，加载桌宠图片
    pet_image_path = os.path.join(
        "assets", "images", "cat_image_smile_001.png"
    )
    pet = DesktopPet(image_path=pet_image_path, position=(100, 100))
    logger.info(f"桌宠图片加载: {pet_image_path}")

    # 初始化桌宠状态
    pet_state = PetState()
    logger.info(f"桌宠状态初始化: mood={pet_state.mood}, energy={pet_state.energy}, intimacy={pet_state.intimacy}")

    # 初始化控制器
    pet_controller = PetController(pet, pet_state)
    event_handler = EventHandler(pet, pet_controller)

    # TO_DO: 绑定鼠标拖动事件和点击事件
    # 将 event_handler 注册到 pet 的事件回调
    pet.on_drag_callback = event_handler.handle_drag
    pet.on_click_callback = event_handler.handle_click

    # TO_DO: 启动事件循环
    logger.info("启动桌面宠物事件循环...")
    try:
        while True:
            pet.draw()
            # 模拟事件获取（后续接入真实GUI事件循环）
            event = event_handler.get_next_event()
            if event:
                event_handler.dispatch(event)
    except KeyboardInterrupt:
        logger.info("用户中断，桌宠退出。")
    except Exception as e:
        logger.error(f"运行时异常: {e}")
    finally:
        logger.info("AI_Desktop_Pet 已退出。")


if __name__ == "__main__":
    main()
