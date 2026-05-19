"""
桌宠动作触发逻辑，与状态模块交互
"""
from models.nlp.deepseek_api import generate_pet_reply
from models.tts.tts_manager import speak
from utils.logger import get_logger

# TO_DO: 定义动作触发函数
#   trigger_action(pet, action)
#   #根据pet_state调用对应动画/声音/对话

logger = get_logger("PetController")


class PetController:
    """
    桌宠控制器：触发桌宠动作，协调各模块
    """

    def __init__(self, pet, pet_state):
        """
        初始化控制器
        :param pet: DesktopPet对象
        :param pet_state: PetState对象
        """
        self.pet = pet
        self.pet_state = pet_state

    # TO_DO: 定义动作触发函数
    def trigger_action(self, pet, action: str):
        """
        根据动作名称触发桌宠行为
        :param pet: DesktopPet对象
        :param action: 动作名称（如 "idle", "happy", "sad", "hungry"）
        """
        # TO_DO: 根据pet_state调用对应动画/声音/对话
        logger.info(f"触发动作: {action}")

        # 根据动作类型执行不同行为
        if action == "happy":
            self._action_happy(pet)
        elif action == "sad":
            self._action_sad(pet)
        elif action == "hungry":
            self._action_hungry(pet)
        elif action == "idle":
            self._action_idle(pet)
        else:
            self._action_idle(pet)

    def _action_happy(self, pet):
        """
        开心动作：切换表情，生成对话，语音播报
        """
        # TO_DO: 开心动作逻辑
        print("[PetController] 桌宠很开心！😊")
        pet.current_state = "happy"
        reply = generate_pet_reply("I'm so happy!")
        print(f"[PetController] 对话回复: {reply}")
        speak(reply)

    def _action_sad(self, pet):
        """
        难过动作：切换表情，生成安慰对话
        """
        # TO_DO: 难过动作逻辑
        print("[PetController] 桌宠有点难过...😢")
        pet.current_state = "sad"
        reply = generate_pet_reply("I'm feeling sad...")
        print(f"[PetController] 对话回复: {reply}")
        speak(reply)

    def _action_hungry(self, pet):
        """
        饥饿动作：切换表情
        """
        # TO_DO: 饥饿动作逻辑
        print("[PetController] 桌宠饿了...🍽️")
        pet.current_state = "hungry"
        reply = generate_pet_reply("I'm hungry!")
        print(f"[PetController] 对话回复: {reply}")

    def _action_idle(self, pet):
        """
        空闲动作：保持默认状态
        """
        # TO_DO: 空闲动作逻辑
        print("[PetController] 桌宠空闲中...")
        pet.current_state = "smile"
        pet.set_image(pet.image_path)
