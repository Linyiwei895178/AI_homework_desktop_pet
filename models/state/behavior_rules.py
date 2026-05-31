"""
状态对应动作决策规则 + 行为协调器

核心类 BehaviorRules：
- 接收 PetState 实例，作为桌宠状态的唯一决策入口
- get_action() → 对接 app/ui/desktop_pet.py / widgets.py
- apply_user_state(user_state) → 对接 models/vision/user_state_detector.py
- on_chat_finished(word_count) → 对接 models/tts/tts_manager.py
- get_speech_hint() → 主动语音提示文本
"""

from typing import Any, Callable, Dict, Optional

from models.state.pet_state import PetState


# ===== 主动语音提示模板 =====
# key: (条件字段, 条件, 比较方式)  →  value: 提示文本
SPEECH_HINTS = [
    # (条件函数, 提示文本)
    (lambda s: s.energy <= 10, "我要饿晕了…快救救我…🆘"),
    (lambda s: s.energy <= 20, "我好饿，快给我些吃的吧！🍔"),
    (lambda s: s.energy <= 30, "肚子有点饿了…有没有好吃的？🍪"),
    (lambda s: s.intimacy >= 90, "最喜欢你啦！💖"),
    (lambda s: s.intimacy >= 80, "和你在一起好开心呀！😊"),
    (lambda s: s.intimacy <= 15, "你都不理我了…😿"),
    (lambda s: s.intimacy <= 5, "呜呜…你是不是不喜欢我了…💔"),
    (lambda s: s.mood == "sad", "今天有点难过…陪陪我好不好？🥺"),
    (lambda s: s.mood == "angry", "哼！我生气了！🔥"),
    (lambda s: s.mood == "hungry", "好饿好饿…求投喂！"),
]


class BehaviorRules:
    """
    行为决策引擎

    接收 PetState 实例，统一决策桌宠的动作、语音提示、对话后状态更新。

    用法:
        rules = BehaviorRules(pet_state)
        action = rules.get_action()           # → 接口: desktop_pet.py / widgets.py
        rules.apply_user_state(user_state)    # ← 接口: user_state_detector.py
        rules.on_chat_finished(word_count)    # → 接口: tts_manager.py
        hint = rules.get_speech_hint()        # → 主动语音提示
    """

    def __init__(self, pet_state: PetState):
        """
        :param pet_state: PetState 实例，管理 mood/energy/intimacy
        """
        self.pet_state = pet_state

        # 动作 → mood 映射表
        self._mood_action_map = {
            "happy": "happy",
            "sad": "sad",
            "angry": "angry",
            "hungry": "hungry",
            "neutral": "idle",
        }

        # ── 队友接口回调 ──
        # 接口3: NLP/TTS 队友注册的回调（AI对话结束时触发）
        self._logic_status_callback: Optional[Callable[[Dict[str, Any]], None]] = None
        # 接口补充: Vision 队友注册的回调（用户状态变化时触发）
        self._vision_callback: Optional[Callable[[Dict[str, Any]], None]] = None
        # 最近一次 chat 数据缓存（供回调使用）
        self._last_chat_data: Dict[str, Any] = {}

    # ═══════════════════════════════════════════════════════════
    # 核心方法: get_action()
    # 对接 app/ui/desktop_pet.py、app/ui/widgets.py
    # ═══════════════════════════════════════════════════════════

    def get_action(self) -> str:
        """
        根据当前 pet_state 决策应执行的动作名称

        决策优先级:
          1. energy < 30 → "hungry"（饥饿优先）
          2. mood 映射 → mood → 动作
          3. intimacy > 80 且 idle → "happy"（高亲密度额外互动）

        :return: 动作名称字符串
                 可能值: "idle", "happy", "sad", "hungry", "angry", "feed", "play", "click"

        对接说明:
          - desktop_pet.py: pet_controller.trigger_action(pet, action)
          - widgets.py:       StatusPanel.update_display(pet_state)
        """
        # 饥饿优先
        if self.pet_state.energy < 30:
            return "hungry"

        # 心情映射
        action = self._mood_action_map.get(self.pet_state.mood, "idle")

        # 高亲密度时即使中性也表现开心
        if self.pet_state.intimacy > 80 and action == "idle":
            action = "happy"

        return action

    # ═══════════════════════════════════════════════════════════
    # apply_user_state()
    # 对接 models/vision/user_state_detector.py
    # ═══════════════════════════════════════════════════════════

    def apply_user_state(self, user_state: dict):
        """
        接收 UserStateDetector 输出的统一格式 user_state 字典，
        调用 pet_state.update_from_user_state() 更新桌宠状态。

        :param user_state: 统一格式的用户状态字典
            {
                "state_code": "distracted",
                "state_name": "疑似分心",
                "description": "...",
                "tags": [...],
                "confidence": 0.82,
                "duration": 12.5,
                "need_response": True,
                "suggestion": "...",
                "source": ["mediapipe", "qwen_vl"],
            }

        对接说明:
          - user_state_detector.py: UserStateDetector.get_state() → 本方法
          - 内部调用 pet_state.update_from_user_state() 完成映射
        """
        if not user_state or not isinstance(user_state, dict):
            return

        self.pet_state.update_from_user_state(user_state)

        # 如果用户需要回应 且 队友C注册了回调，通知队友C
        if user_state.get("need_response", False):
            self._notify_callback("user_state_updated", {
                "state_code": user_state.get("state_code", "unknown"),
                "need_response": True,
                "suggestion": user_state.get("suggestion", ""),
            })

    # ═══════════════════════════════════════════════════════════
    # on_chat_finished()
    # 对接 models/tts/tts_manager.py
    # ═══════════════════════════════════════════════════════════

    def on_chat_finished(self, word_count: int = 0):
        """
        对话结束后调用，根据对话长度更新宠物状态。

        规则:
          - 每次对话消耗少量能量（说话也累）
          - 对话越长，亲密度增长越多（交流促进感情）
          - 对话后心情趋向 happy

        :param word_count: 本次对话的字数（来自 TTS 文本长度或 NLG 输出长度）

        对接说明:
          - tts_manager.py: speak() 完成后可调用本方法
          - 主循环中在生成/播放语音后调用
        """
        ps = self.pet_state

        # 对话消耗能量（字越多越累，但上限合理）
        energy_cost = min(3, max(1, word_count // 30))
        ps.energy = max(0, ps.energy - energy_cost)

        # 对话增进亲密度（字数越多越亲近）
        intimacy_gain = min(5, max(1, word_count // 20))
        ps.intimacy = min(100, ps.intimacy + intimacy_gain)

        # 交流后心情变好
        if ps.mood in ("sad", "angry", "neutral"):
            ps.mood = "happy"

        print(f"[BehaviorRules] 对话完成 (字数={word_count}): "
              f"energy -{energy_cost}, intimacy +{intimacy_gain}, mood={ps.mood}")

        # 缓存本次对话数据
        self._last_chat_data = {
            "word_count": word_count,
            "energy_cost": energy_cost,
            "intimacy_gain": intimacy_gain,
        }

        # 触发队友C注册的逻辑回调（自动传递对话数据）
        self._notify_callback("chat_finished", {
            "word_count": word_count,
            "energy_cost": energy_cost,
            "intimacy_gain": intimacy_gain,
        })

    # ═══════════════════════════════════════════════════════════
    # get_speech_hint()
    # 主动语音提示 — 对接 tts_manager.speak()
    # ═══════════════════════════════════════════════════════════

    def get_speech_hint(self) -> Optional[str]:
        """
        根据当前 pet_state 返回一句主动提示语音文本。

        触发条件（按优先级）:
          - energy <= 10: 极度饥饿求救
          - energy <= 20: 饥饿提醒
          - energy <= 30: 轻微饥饿
          - intimacy >= 90: 超喜欢表白
          - intimacy >= 80: 开心表达
          - intimacy <= 15: 寂寞提醒
          - intimacy <= 5:  伤心抱怨
          - mood == "sad":   难过求陪伴
          - mood == "angry": 生气发脾气
          - mood == "hungry": 饥饿呼喊

        :return: 提示文本字符串，如果无需提示则返回 None

        对接说明:
          - 返回值可直接传入 tts_manager.speak(text)
          - 主循环中定时调用，如每分钟检查一次
        """
        for condition, hint_text in SPEECH_HINTS:
            if condition(self.pet_state):
                return hint_text

        return None

    # ═══════════════════════════════════════════════════════════
    # 便捷查询
    # ═══════════════════════════════════════════════════════════

    def should_speak(self) -> bool:
        """
        判断当前是否应该主动说话

        条件: energy <= 30、intimacy >= 80 或 intimacy <= 15、mood 非 neutral

        :return: True 表示应主动说话
        """
        ps = self.pet_state
        return (
            ps.energy <= 30
            or ps.intimacy >= 80
            or ps.intimacy <= 15
            or ps.mood in ("sad", "angry", "hungry")
        )

    def get_pet_id(self) -> str:
        """获取桌宠 ID（默认 "cat"）"""
        return getattr(self.pet_state, "pet_id", "cat")

    # ═══════════════════════════════════════════════════════════
    # 接口 3：接入 NLP/TTS 队友 — 注册状态更新通知
    # ═══════════════════════════════════════════════════════════

    def api_register_logic_callback(self, callback: Callable[[Dict[str, Any]], None]):
        """
        【队友C专用】NLP/TTS 队友通过此接口注册一个"监听器"。
        当 AI 对话结束时，BehaviorRules 自动把对话字数、状态等信息
        通过回调传给队友，供其计算亲密度、心情值。

        :param callback: 签名为 callback(status_dict) 的回调函数
            status_dict 示例:
            {
                "event": "chat_finished" | "user_state_updated",
                "word_count": 60,
                "mood": "happy",
                "energy": 78,
                "intimacy": 35,
                "timestamp": 1779264638.0,
            }
        """
        self._logic_status_callback = callback
        print("[BehaviorRules] 队友D的逻辑回调接口已成功绑定。")

    # ═══════════════════════════════════════════════════════════
    # 接口 4：接入 NLP/TTS 队友 — 清理/重置记忆
    # ═══════════════════════════════════════════════════════════

    def api_reset_ai_memory(self):
        """
        【队友C专用】全局重置、切换用户、或者桌宠进入睡眠状态时，
        调用此接口清空 pet_state 历史记录和最近聊天缓存。
        """
        # 清空 pet_state 的历史记录
        self.pet_state.reset_history()

        # 清空最近聊天缓存
        self._last_chat_data.clear()

        # 清空注册的回调（断开与队友C的连接）
        self._logic_status_callback = None

        print("[BehaviorRules] 桌宠状态记忆已成功清空。")

    # ═══════════════════════════════════════════════════════════
    # 接入 Vision 队友 — 注册用户状态回调
    # ═══════════════════════════════════════════════════════════

    def connect_vision_detector(self, detector):
        """
        接入 Vision 队友的 UserStateDetector.set_callback()，
        当用户状态变化时自动调用 apply_user_state()。

        :param detector: UserStateDetector 实例

        用法:
            detector = UserStateDetector()
            rules = BehaviorRules(pet_state)
            rules.connect_vision_detector(detector)
            detector.start()
            # 此后 detector 每次检测到新状态，自动同步到 pet_state
        """
        if not hasattr(detector, "set_callback"):
            print("[BehaviorRules] Vision detector 不支持 set_callback，跳过绑定。")
            return

        def _on_vision_state(user_state: dict):
            """Vision 回调：接收到新用户状态后同步到 pet_state"""
            if not user_state or not isinstance(user_state, dict):
                return
            # 调用自己的 apply_user_state 进行映射
            self.apply_user_state(user_state)
            # 如果队友C注册了回调，也通知队友C
            self._notify_callback("user_state_updated", user_state)

        detector.set_callback(_on_vision_state)
        print("[BehaviorRules] 已成功绑定 Vision detector 回调。")

    # ═══════════════════════════════════════════════════════════
    # 内部：触发注册的回调
    # ═══════════════════════════════════════════════════════════

    def _notify_callback(self, event: str, extra_data: Optional[dict] = None):
        """触发队友C注册的逻辑回调，传递状态更新通知"""
        if self._logic_status_callback is None:
            return

        ps = self.pet_state
        status = {
            "event": event,
            "pet_id": self.get_pet_id(),
            "action": self.get_action(),
            "mood": ps.mood,
            "energy": ps.energy,
            "intimacy": ps.intimacy,
            "timestamp": __import__("time").time(),
        }
        if extra_data:
            status.update(extra_data)

        try:
            self._logic_status_callback(status)
        except Exception as e:
            print(f"[BehaviorRules] 回调触发异常: {e}")


# ═══════════════════════════════════════════════════════════
# 向后兼容: 保留原有 decide_action() 函数
# ═══════════════════════════════════════════════════════════

def decide_action(pet_state) -> str:
    """
    [兼容接口] 根据桌宠状态决策应该执行的动作

    内部委托给 BehaviorRules.get_action()。

    :param pet_state: PetState对象，包含 mood/energy/intimacy 属性
    :return: 动作名称字符串
    """
    rules = BehaviorRules(pet_state)
    return rules.get_action()

