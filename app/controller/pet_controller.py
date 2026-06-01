"""
桌宠动作触发逻辑，与状态模块交互
"""
import threading
import time

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
        self._speech_busy = False
        self._last_speech_at = 0.0
        self._speech_cooldown = 12.0
        self._last_visual_action = ""
        self._last_visual_at = 0.0
        self._visual_repeat_cooldown = 8.0

    # TO_DO: 定义动作触发函数
    def trigger_action(self, pet, action: str):
        """
        根据动作名称触发桌宠行为
        :param pet: DesktopPet对象
        :param action: 动作名称（如 "idle", "happy", "sad", "hungry"）
        """
        # TO_DO: 根据pet_state调用对应动画/声音/对话
        action = (action or "idle").strip().lower() or "idle"
        now = time.time()
        if (
            action == self._last_visual_action
            and now - self._last_visual_at < self._visual_repeat_cooldown
        ):
            return
        self._last_visual_action = action
        self._last_visual_at = now

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

    def _apply_pet_visual(self, pet, action: str):
        pet.current_state = action
        if hasattr(pet, "set_expression"):
            pet.set_expression(action)
        if hasattr(pet, "play_motion"):
            pet.play_motion("Idle" if action == "idle" else action)
        elif hasattr(pet, "set_image") and hasattr(pet, "image_path"):
            pet.set_image(pet.image_path)

    def _reply_and_speak_async(self, prompt: str, state: str) -> None:
        now = time.time()
        if self._speech_busy or now - self._last_speech_at < self._speech_cooldown:
            return
        self._speech_busy = True
        self._last_speech_at = now

        def _run() -> None:
            try:
                reply = generate_pet_reply(prompt)
                print(f"[PetController] 对话回复: {reply}")
                speak(reply, state=state, action="speak")
            except Exception as exc:
                logger.exception(f"Speech action failed: {exc}")
            finally:
                self._speech_busy = False

        threading.Thread(target=_run, daemon=True).start()

    def _action_happy(self, pet):
        """
        开心动作：切换表情，生成对话，语音播报
        """
        # TO_DO: 开心动作逻辑
        print("[PetController] 桌宠很开心！😊")
        self._apply_pet_visual(pet, "happy")
        self._reply_and_speak_async("I'm so happy!", "happy")

    def _action_sad(self, pet):
        """
        难过动作：切换表情，生成安慰对话
        """
        # TO_DO: 难过动作逻辑
        print("[PetController] 桌宠有点难过...😢")
        self._apply_pet_visual(pet, "sad")
        self._reply_and_speak_async("I'm feeling sad...", "sad")

    def _action_hungry(self, pet):
        """
        饥饿动作：切换表情
        """
        # TO_DO: 饥饿动作逻辑
        print("[PetController] 桌宠饿了...🍽️")
        self._apply_pet_visual(pet, "hungry")
        self._reply_and_speak_async("I'm hungry!", "hungry")

    def _action_idle(self, pet):
        """
        空闲动作：保持默认状态
        """
        # TO_DO: 空闲动作逻辑
        print("[PetController] 桌宠空闲中...")
        self._apply_pet_visual(pet, "idle")
