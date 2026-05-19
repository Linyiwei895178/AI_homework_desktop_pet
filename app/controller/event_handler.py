"""
响应用户事件（点击/拖拽）并调用动作逻辑
"""
from models.state.behavior_rules import decide_action
from utils.logger import get_logger

# TO_DO: 监听桌宠鼠标事件，调用 pet_controller

logger = get_logger("EventHandler")


class EventHandler:
    """
    事件处理器：监听桌宠鼠标事件，调用 pet_controller 执行动作
    """

    # TO_DO: 监听桌宠鼠标事件，调用 pet_controller

    def __init__(self, pet, pet_controller):
        """
        初始化事件处理器
        :param pet: DesktopPet对象
        :param pet_controller: PetController对象
        """
        self.pet = pet
        self.pet_controller = pet_controller
        self._event_queue = []

    def handle_drag(self, event):
        """
        处理拖拽事件：更新桌宠位置
        :param event: 鼠标事件对象
        """
        # TO_DO: 响应拖拽事件，更新桌宠坐标
        logger.info(f"拖拽事件 - 新位置: ({self.pet.position[0]}, {self.pet.position[1]})")

    def handle_click(self, event):
        """
        处理点击事件：根据行为规则触发桌宠动作
        :param event: 鼠标事件对象
        """
        # TO_DO: 响应点击事件，调用 pet_controller 触发动作
        logger.info("点击事件触发")

        # 根据当前状态决策动作
        pet_state = self.pet_controller.pet_state
        action = decide_action(pet_state)
        logger.info(f"行为决策结果: {action}")

        # 触发动作
        self.pet_controller.trigger_action(self.pet, action)

        # 更新桌宠状态
        pet_state.update_state(action)
        logger.info(f"状态更新: mood={pet_state.mood}, energy={pet_state.energy}, intimacy={pet_state.intimacy}")

    def get_next_event(self):
        """
        获取下一个待处理事件（模拟事件队列）
        :return: 事件对象，若无事件返回None
        """
        if self._event_queue:
            return self._event_queue.pop(0)
        return None

    def dispatch(self, event):
        """
        分发事件到对应的处理函数
        :param event: 事件对象
        """
        # TO_DO: 根据事件类型调用对应的处理方法
        if hasattr(event, 'type'):
            if event.type == "drag":
                self.handle_drag(event)
            elif event.type == "click":
                self.handle_click(event)
