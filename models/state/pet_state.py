"""
桌宠状态（心情/能量/亲密度）
"""


class PetState:
    """
    桌宠状态类
    管理桌宠的心情(mood)、能量(energy)、亲密度(intimacy)

    TO_DO:
    - 初始化心情/能量/亲密度
    - 根据事件更新状态
    - 状态持久化
    """

    # TO_DO: 初始化心情/能量/亲密度

    def __init__(self, mood: str = "neutral", energy: int = 100, intimacy: int = 50):
        """
        初始化桌宠状态

        :param mood: 初始心情，可选 "neutral", "happy", "sad", "angry", "hungry"
        :param energy: 初始能量值 (0-100)
        :param intimacy: 初始亲密度 (0-100)
        """
        # TO_DO: 初始化心情/能量/亲密度
        self.mood = mood
        self.energy = max(0, min(100, energy))
        self.intimacy = max(0, min(100, intimacy))

        # 状态变化记录
        self._last_event = None
        self._history = []

    # TO_DO: 根据事件更新状态
    def update_state(self, event: str):
        """
        根据事件更新桌宠状态

        :param event: 事件名称（如 "click", "feed", "play", "idle"）

        TO_DO:
        - 根据不同类型事件调整心情/能量/亲密度
        - 确保各属性在合理范围内 (0-100)
        - 记录状态变化历史
        """
        # TO_DO: 根据事件更新状态
        self._last_event = event
        self._history.append(event)

        if event == "click":
            # 被点击：亲密度上升，能量略降
            self.intimacy = min(100, self.intimacy + 2)
            self.energy = max(0, self.energy - 1)
            self.mood = "happy"

        elif event == "feed":
            # 被喂食：能量上升，亲密度上升
            self.energy = min(100, self.energy + 20)
            self.intimacy = min(100, self.intimacy + 5)
            self.mood = "happy"

        elif event == "play":
            # 玩耍：能量下降，亲密度上升
            self.energy = max(0, self.energy - 10)
            self.intimacy = min(100, self.intimacy + 3)
            self.mood = "happy"

        elif event == "idle":
            # 空闲：能量缓慢恢复
            self.energy = min(100, self.energy + 1)
            if self.energy < 30:
                self.mood = "hungry"
            elif self.energy > 80:
                self.mood = "neutral"

        elif event == "sad":
            # 难过事件：心情变差
            self.mood = "sad"
            self.energy = max(0, self.energy - 5)

        else:
            # 未知事件，保持当前状态
            pass

    def get_state_info(self) -> dict:
        """
        获取当前状态的字典表示

        :return: 包含 mood, energy, intimacy 的字典
        """
        return {
            "mood": self.mood,
            "energy": self.energy,
            "intimacy": self.intimacy
        }

    def __str__(self) -> str:
        """字符串表示"""
        return f"PetState(mood={self.mood}, energy={self.energy}, intimacy={self.intimacy})"
