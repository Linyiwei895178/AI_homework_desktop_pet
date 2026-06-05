"""
桌宠状态（心情/能量/亲密度/等级/经验/金币/饱食度/羁绊）
=====================================================

对接 UserStateDetector 状态字典，通过 update_from_user_state() 方法
将用户状态识别结果映射为桌宠自身的 mood/energy/intimacy 变化。

扩展字段（队员D后续可配置数值）：
- level: 等级（默认1）
- exp: 经验值
- coins: 金币
- hunger: 饱食度（0-100）
- bond_score: 羁绊值

═══════════════════════════════════════════════════════
【队员A — UI】直接读写
═══════════════════════════════════════════════════════

>>> from models.state.pet_state import PetState

>>> s = PetState()
>>> s.mood       # "neutral" | "happy" | "sad" | "angry" | "hungry"
>>> s.energy     # 0-100
>>> s.intimacy   # 0-100
>>> s.level, s.exp, s.coins, s.hunger, s.bond_score

>>> s.update_state("feed")  # 投喂
>>> s.update_state("play")  # 陪玩
>>> s.update_state("chat")  # 聊天
>>> s.update_state("work")  # 工作陪伴
>>> s.update_state("study") # 学习陪伴

>>> s.to_dict()             # 全体字段 dict
>>> s.get_state_info()      # 同 to_dict()

═══════════════════════════════════════════════════════
【队员B — Vision】用户状态映射
═══════════════════════════════════════════════════════

>>> s.update_from_user_state({
...     "state_code": "distracted",
...     "confidence": 0.85,
...     "duration": 10.0,
...     "need_response": True,
... })

═══════════════════════════════════════════════════════
【队员C — NLP/TTS】对话后更新 + 等级经验
═══════════════════════════════════════════════════════

>>> s.add_exp(50)                          # 加经验(可能触发升级)
>>> s.apply_interaction("chat")            # 返回变化 delta
>>> s.get_level_progress()                 # {level, exp, next_level_exp, progress, remaining}
>>> s.check_level_up()                     # 手动触发升级检查

>>> s.save_state()                         # 持久化到 logs/pet_state.json
>>> s.load_state()                         # 从文件恢复(兼容旧格式)
>>> s.from_dict({"mood":"happy", ...})     # 从旧 JSON 复原
"""

import json
import os
import time
from typing import Any, Dict, List, Optional

from models.state.pet_leveling import (
    calculate_interaction_delta,
    exp_to_next_level,
    get_level_progress as _get_level_progress,
)


# 用户 state_code → 桌宠 mood 映射规则
USER_STATE_TO_PET_MOOD = {
    "normal": "happy",
    "focused": "neutral",
    "distracted": "neutral",
    "tired": "neutral",
    "away": "neutral",
    "return": "happy",
    "study_long": "neutral",
    "low_light": "neutral",
    "camera_error": "neutral",
    "unknown": "neutral",
}


class PetState:
    """
    桌宠状态类
    管理桌宠的心情(mood)、能量(energy)、亲密度(intimacy)
    扩展字段：等级(level)、经验(exp)、金币(coins)、饱食度(hunger)、羁绊(bond_score)

    支持两种更新方式：
    1. update_state(event)       - 根据事件名称更新（旧接口）
    2. update_from_user_state(state_dict) - 根据用户状态字典更新（新接口）
    """

    def __init__(self, mood: str = "neutral", energy: int = 100, intimacy: int = 50, pet_id: str = "cat",
                 level: int = 1, exp: int = 0, coins: int = 0, hunger: int = 50, bond_score: int = 0):
        """
        初始化桌宠状态

        :param mood: 初始心情，可选 "neutral", "happy", "sad", "angry", "hungry"
        :param energy: 初始能量值 (0-100)
        :param intimacy: 初始亲密度 (0-100)
        :param pet_id: 桌宠ID
        :param level: 初始等级
        :param exp: 初始经验值
        :param coins: 初始金币
        :param hunger: 初始饱食度 (0-100)
        :param bond_score: 初始羁绊值
        """
        self.mood = mood
        self.energy = max(0, min(100, energy))
        self.intimacy = max(0, min(100, intimacy))
        self.pet_id = (pet_id or "cat").strip() or "cat"

        # 扩展字段
        self.level = max(1, int(level))
        self.exp = max(0, int(exp))
        self.coins = max(0, int(coins))
        self.hunger = max(0, min(100, int(hunger)))
        self.bond_score = max(0, int(bond_score))

        # 状态变化记录
        self._last_event = None
        self._last_user_state: Optional[dict] = None
        self._last_user_state_effect_code: Optional[str] = None
        self._last_user_state_effect_at: float = 0.0
        self._history = []

    def update_state(self, event: str):
        """
        根据事件更新桌宠状态（心情/能量/亲密度 + 等级系统）

        :param event: 事件名称（如 "click", "feed", "play", "idle", "chat", "work", "study"）
        """
        self._last_event = event

        # ── 基础心情/能量/亲密度变化 ──
        if event == "click":
            self.intimacy = min(100, self.intimacy + 2)
            self.energy = max(0, self.energy - 1)
            self.mood = "happy"

        elif event == "feed":
            self.energy = min(100, self.energy + 20)
            self.intimacy = min(100, self.intimacy + 5)
            self.mood = "happy"

        elif event == "play":
            self.energy = max(0, self.energy - 10)
            self.intimacy = min(100, self.intimacy + 3)
            self.mood = "happy"

        elif event == "chat":
            # 聊天：消耗少量能量，增加亲密度
            self.energy = max(0, self.energy - 2)
            self.intimacy = min(100, self.intimacy + 2)
            if self.mood in ("sad", "angry"):
                self.mood = "neutral"

        elif event == "work":
            # 工作陪伴：消耗能量，增加经验
            self.energy = max(0, self.energy - 15)
            if self.mood == "sad":
                self.mood = "neutral"

        elif event == "study":
            # 学习陪伴：同 work 逻辑
            self.energy = max(0, self.energy - 10)
            if self.mood == "sad":
                self.mood = "neutral"

        elif event == "idle":
            # 空闲：能量缓慢恢复
            self.energy = min(100, self.energy + 1)
            if self.energy < 30:
                self.mood = "hungry"
            elif self.energy > 80:
                self.mood = "neutral"

        elif event == "sad":
            self.mood = "sad"
            self.energy = max(0, self.energy - 5)

        else:
            # 未知事件，保持当前状态
            pass

        # ── 等级系统：应用经验/金币/饱食度/羁绊变化 ──
        delta = calculate_interaction_delta(event)
        if delta:
            self.exp += delta.get("exp", 0)
            self.coins = max(0, self.coins + delta.get("coins", 0))
            self.hunger = max(0, min(100, self.hunger + delta.get("hunger", 0)))
            self.bond_score = max(0, self.bond_score + delta.get("bond_score", 0))

            # 检查升级
            self.check_level_up()

        # 记录状态变化历史（结构化快照）
        self._history.append({
            "event": event,
            "mood": self.mood,
            "energy": self.energy,
            "intimacy": self.intimacy,
            "level": self.level,
            "exp": self.exp,
            "coins": self.coins,
            "hunger": self.hunger,
            "bond_score": self.bond_score,
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
        now = time.time()

        # 将用户状态码映射为桌宠心情
        new_mood = USER_STATE_TO_PET_MOOD.get(state_code, "neutral")
        self.mood = new_mood

        same_state_effect_recent = (
            state_code == self._last_user_state_effect_code
            and now - self._last_user_state_effect_at < 120.0
        )

        # 根据置信度和持续时间调整能量。同一用户状态短时间连续上报时不重复扣。
        if need_response and confidence > 0.7 and not same_state_effect_recent:
            # 用户需要响应时，桌宠消耗一些能量来回应
            energy_cost = min(5, int(duration / 10) + 1) if duration > 0 else 2
            self.energy = max(0, self.energy - energy_cost)
            self._last_user_state_effect_code = state_code
            self._last_user_state_effect_at = now

        # 用户分心/疲劳/离开是需要陪伴或等待的状态，不视为宠物自身受伤。
        if state_code == "return":
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
            "level": self.level,
            "exp": self.exp,
            "coins": self.coins,
            "hunger": self.hunger,
            "bond_score": self.bond_score,
            "timestamp": time.time(),
        })

    def check_level_up(self) -> bool:
        """检查并执行升级（公开方法，供外部调用）。

        由 update_state / add_exp 内部也会自动调用。
        返回值表示本次调用是否触发了升级。
        """
        needed = exp_to_next_level(self.level)
        if self.exp < needed:
            return False
        self.exp -= needed
        self.level += 1
        # 升级奖励
        bonus = calculate_interaction_delta("level_up")
        self.coins += bonus.get("coins", 0)
        self.energy = min(100, self.energy + bonus.get("energy", 0))
        self.intimacy = min(100, self.intimacy + bonus.get("intimacy", 0))
        self.bond_score += bonus.get("bond_score", 0)
        print(f"[PetState] 升级! 当前等级={self.level}, 剩余exp={self.exp}")
        return True

    def add_exp(self, amount: int) -> List[str]:
        """
        增加经验值，如果达到升级所需经验则自动升级。
        负数输入会安全地归零处理。

        :param amount: 增加的经验值（正整数或零；负数会被视为0）
        :return: 触发的事件列表，可能包含 "level_up"
        """
        # 安全处理负数输入（容错）
        if amount < 0:
            amount = 0
        if amount == 0:
            return []
        self.exp += int(amount)
        events: List[str] = []

        # 可能连续升级多次
        while self.exp >= exp_to_next_level(self.level):
            if self.check_level_up():
                events.append("level_up")

        return events

    def apply_interaction(self, action_type: str, actor: str = "local") -> dict:
        """
        应用一次互动（点击/投喂/玩耍/聊天/工作陪伴/学习陪伴），更新状态并返回变化。

        :param action_type: 互动类型（click/feed/play/chat/work/study/pet 等）
        :param actor: 互动执行者
        :return: 状态变化字典
        """
        old = self.to_dict()
        self.update_state(action_type)
        deltas: Dict[str, Any] = {}
        new = self.to_dict()
        for key, new_val in new.items():
            old_val = old.get(key, new_val)
            if isinstance(new_val, (int, float)) and isinstance(old_val, (int, float)):
                diff = new_val - old_val
                if diff != 0:
                    deltas[key + "_delta"] = diff
        deltas["actor"] = actor
        deltas["action_type"] = action_type
        return deltas

    def to_dict(self) -> dict:
        """将当前状态转换为字典（包含所有字段）。"""
        return {
            "pet_id": self.pet_id, "mood": self.mood, "energy": self.energy,
            "intimacy": self.intimacy, "level": self.level, "exp": self.exp,
            "coins": self.coins, "hunger": self.hunger, "bond_score": self.bond_score,
        }

    def from_dict(self, data: dict) -> "PetState":
        """从字典恢复状态（兼容旧格式，缺失字段使用默认值）。"""
        if not isinstance(data, dict):
            return self
        self.mood = str(data.get("mood", self.mood))
        self.energy = max(0, min(100, int(data.get("energy", self.energy))))
        self.intimacy = max(0, min(100, int(data.get("intimacy", self.intimacy))))
        self.pet_id = str(data.get("pet_id", self.pet_id) or self.pet_id)
        self.level = max(1, int(data.get("level", self.level)))
        self.exp = max(0, int(data.get("exp", self.exp)))
        self.coins = max(0, int(data.get("coins", self.coins)))
        self.hunger = max(0, min(100, int(data.get("hunger", self.hunger))))
        self.bond_score = max(0, int(data.get("bond_score", self.bond_score)))
        return self

    def get_level_progress(self) -> dict:
        """获取等级进度信息（委托 pet_leveling.get_level_progress）。"""
        return _get_level_progress(self.level, self.exp)

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

        state_data = self.to_dict()
        state_data["updated_at"] = time.time()

        # 原子写入（通过临时文件 + rename）
        try:
            tmp_path = str(filepath) + ".tmp"
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(state_data, f, ensure_ascii=False, indent=2)
            os.replace(tmp_path, str(filepath))
            print(f"[PetState] 状态已保存到: {filepath}")
        except OSError as e:
            print(f"[PetState] 保存状态失败: {e}")

    def load_state(self, filepath: Optional[str] = None):
        """
        从 JSON 文件恢复状态（状态持久化，兼容旧格式）

        旧格式可能只有 mood/energy/intimacy/pet_id，
        新格式包含 level/exp/coins/hunger/bond_score。
        缺失字段自动填充默认值。

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

        try:
            with open(filepath, "r", encoding="utf-8") as f:
                state_data = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            print(f"[PetState] 状态文件读取失败: {e}，保持当前状态")
            return self

        self.from_dict(state_data)
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
        return self.to_dict()

    def __str__(self) -> str:
        """字符串表示"""
        return f"PetState(mood={self.mood}, energy={self.energy}, intimacy={self.intimacy}, level={self.level}, exp={self.exp}, coins={self.coins}, hunger={self.hunger}, bond_score={self.bond_score})"
