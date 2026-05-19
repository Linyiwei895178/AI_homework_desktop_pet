"""
桌宠状态（心情/能量/亲密度）

对接 UserStateDetector 状态字典，通过 update_from_user_state() 方法
将用户状态识别结果映射为桌宠自身的 mood/energy/intimacy 变化。
"""

from typing import Optional


# 用户 state_code → 桌宠 mood 映射规则
USER_STATE_TO_PET_MOOD = {
    "normal": "happy",
    "focused": "neutral",
    "distracted": "sad",
    "tired": "sad",
    "away": "sad",
    "return": "happy",
    "study_long": "hungry",
    "low_light": "sad",
    "camera_error": "angry",
    "unknown": "neutral",
}


class PetState:
    """
    桌宠状态类
    管理桌宠的心情(mood)、能量(energy)、亲密度(intimacy)

    支持两种更新方式：
    1. update_state(event)       - 根据事件名称更新（旧接口）
    2. update_from_user_state(state_dict) - 根据用户状态字典更新（新接口）

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
        self._last_user_state: Optional[dict] = None
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

    # TO_DO: update_from_user_state() - 根据用户状态字典更新桌宠状态
    def update_from_user_state(self, user_state: dict):
        """
        根据用户状态字典更新桌宠状态

        这是对接 UserStateDetector / Qwen-VL 的统一接口。
        将用户状态（state_code）映射为桌宠的心情变化，
        并根据 need_response / duration / confidence 调整能量和亲密度。

        :param user_state: 统一格式的用户状态字典
            {
                "state_code": "distracted",   # 用户状态大类
                "state_name": "疑似分心",
                "description": "...",
                "tags": [...],
                "confidence": 0.82,           # 置信度
                "duration": 12.5,             # 状态持续秒数
                "need_response": True,        # 是否需要桌宠回应
                "suggestion": "...",
                "source": ["mediapipe", "qwen_vl"],
            }

        TO_DO:
        - 将 user_state["state_code"] 映射为桌宠 mood
        - 高置信度分心/疲劳 → 适当降低亲密度或能量
        - need_response = True → 标记待响应
        - 根据状态持续时间计算影响力度
        - 记录最近一次用户状态，供其他模块查询
        """
        self._last_user_state = user_state
        state_code = user_state.get("state_code", "unknown")
        confidence = user_state.get("confidence", 0.0)
        duration = user_state.get("duration", 0.0)
        need_response = user_state.get("need_response", False)

        # 将用户状态码映射为桌宠心情
        new_mood = USER_STATE_TO_PET_MOOD.get(state_code, "neutral")
        self.mood = new_mood

        # 根据置信度和持续时间调整能量
        if need_response and confidence > 0.7:
            # 用户需要响应时，桌宠消耗一些能量来回应
            energy_cost = min(5, int(duration / 10) + 1) if duration > 0 else 2
            self.energy = max(0, self.energy - energy_cost)

        # 特定状态下调亲密度（用户状态不好时）
        if state_code in ("distracted", "tired", "away"):
            intimacy_drop = int(confidence * 3) if confidence > 0.5 else 0
            self.intimacy = max(0, self.intimacy - intimacy_drop)
        elif state_code == "return":
            # 用户回来时亲密度上升
            self.intimacy = min(100, self.intimacy + 3)
        elif state_code == "focused":
            # 用户专注时亲密度微升（陪伴）
            self.intimacy = min(100, self.intimacy + 1)

        print(f"[PetState] 根据用户状态更新: {state_code} → mood={self.mood}, "
              f"energy={self.energy}, intimacy={self.intimacy}")

    # TO_DO: get_last_user_state() - 获取最近一次用户状态
    def get_last_user_state(self) -> Optional[dict]:
        """
        获取最近一次接收到的用户状态字典

        :return: 用户状态字典，如果从未接收过则返回 None
        """
        return self._last_user_state

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
