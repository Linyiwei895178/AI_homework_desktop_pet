"""
桌宠状态（心情/能量/亲密度）

对接 UserStateDetector 状态字典，通过 update_from_user_state() 方法
将用户状态识别结果映射为桌宠自身的 mood/energy/intimacy 变化。
"""

import json
import os
import time
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
    """

    def __init__(self, mood: str = "neutral", energy: int = 100, intimacy: int = 50, pet_id: str = "cat"):
        """
        初始化桌宠状态

        :param mood: 初始心情，可选 "neutral", "happy", "sad", "angry", "hungry"
        :param energy: 初始能量值 (0-100)
        :param intimacy: 初始亲密度 (0-100)
        """
        self.mood = mood
        self.energy = max(0, min(100, energy))
        self.intimacy = max(0, min(100, intimacy))
        self.pet_id = (pet_id or "cat").strip() or "cat"

        # 状态变化记录
        self._last_event = None
        self._last_user_state: Optional[dict] = None
        self._history = []

    def update_state(self, event: str):
        """
        根据事件更新桌宠状态

        :param event: 事件名称（如 "click", "feed", "play", "idle"）
        """
        self._last_event = event

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

        # 记录状态变化历史（结构化快照）
        self._history.append({
            "event": event,
            "mood": self.mood,
            "energy": self.energy,
            "intimacy": self.intimacy,
            "timestamp": time.time(),
        })

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

        # 记录状态变化历史（结构化快照）
        self._history.append({
            "event": f"user_state:{state_code}",
            "mood": self.mood,
            "energy": self.energy,
            "intimacy": self.intimacy,
            "timestamp": time.time(),
        })

    def get_last_user_state(self) -> Optional[dict]:
        """
        获取最近一次接收到的用户状态字典

        :return: 用户状态字典，如果从未接收过则返回 None
        """
        return self._last_user_state

    def set_pet_id(self, pet_id: str):
        """同步当前桌宠 ID，供状态决策和 TTS 音色选择使用。"""
        value = (pet_id or "").strip()
        if value:
            self.pet_id = value

    def save_state(self, filepath: Optional[str] = None):
        """
        将当前状态持久化到 JSON 文件（状态持久化）

        :param filepath: 保存路径，默认保存到项目根目录下的 logs/pet_state.json
        """
        if filepath is None:
            logs_dir = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                "logs",
            )
            os.makedirs(logs_dir, exist_ok=True)
            filepath = os.path.join(logs_dir, "pet_state.json")

        state_data = {
            "pet_id": self.pet_id,
            "mood": self.mood,
            "energy": self.energy,
            "intimacy": self.intimacy,
        }
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(state_data, f, ensure_ascii=False, indent=2)
        print(f"[PetState] 状态已保存到: {filepath}")

    def load_state(self, filepath: Optional[str] = None):
        """
        从 JSON 文件恢复状态（状态持久化）

        :param filepath: 读取路径，默认从 logs/pet_state.json 读取
        :return: self（支持链式调用）
        """
        if filepath is None:
            logs_dir = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                "logs",
            )
            filepath = os.path.join(logs_dir, "pet_state.json")

        if not os.path.exists(filepath):
            print(f"[PetState] 状态文件不存在: {filepath}，保持当前状态")
            return self

        with open(filepath, "r", encoding="utf-8") as f:
            state_data = json.load(f)

        self.mood = state_data.get("mood", self.mood)
        self.energy = max(0, min(100, state_data.get("energy", self.energy)))
        self.intimacy = max(0, min(100, state_data.get("intimacy", self.intimacy)))
        self.pet_id = str(state_data.get("pet_id", self.pet_id) or self.pet_id)
        print(f"[PetState] 状态已从 {filepath} 恢复: {self}")
        return self

    def get_history(self, n: Optional[int] = None) -> list:
        """
        获取状态变化历史记录

        :param n: 返回最近 n 条记录，None 返回全部
        :return: 历史记录列表，每条为包含 event/mood/energy/intimacy/timestamp 的字典
        """
        if n is None:
            return list(self._history)
        return self._history[-n:]

    def reset_history(self):
        """
        清空状态变化历史记录（配合 api_reset_ai_memory 使用）
        """
        self._history.clear()
        self._last_event = None
        self._last_user_state = None
        print("[PetState] 历史记录已清空。")

    def reset_state(self, mood: str = "neutral", energy: int = 100, intimacy: int = 50):
        """
        重置桌宠状态为指定值（默认为初始值）

        :param mood: 目标心情
        :param energy: 目标能量 (0-100)
        :param intimacy: 目标亲密度 (0-100)
        """
        self.mood = mood
        self.energy = max(0, min(100, energy))
        self.intimacy = max(0, min(100, intimacy))
        print(f"[PetState] 状态已重置: {self}")

    def get_state_info(self) -> dict:
        """
        获取当前状态的字典表示

        :return: 包含 mood, energy, intimacy 的字典
        """
        return {
            "pet_id": self.pet_id,
            "mood": self.mood,
            "energy": self.energy,
            "intimacy": self.intimacy
        }

    def __str__(self) -> str:
        """字符串表示"""
        return f"PetState(mood={self.mood}, energy={self.energy}, intimacy={self.intimacy})"
