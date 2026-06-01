"""
EchoTeamDInterface - State / 行为决策 接口管理层

┌─────────────────────────────────────────────────┐
│  队员D 接口管理层                                 │
│  专门对接：队员A (UI)、队员B (Vision)、队员C (TTS) │
│  队员D负责：桌宠状态管理 + 行为决策                │
└─────────────────────────────────────────────────┘

对接说明：
- 队员A（UI）：获取状态、决策动作、状态历史
- 队员B（Vision）：接收用户检测状态
- 队员C（NLP/TTS）：对话后状态更新、主动语音提示

用法:
    pet_state = PetState()
    team_d = EchoTeamDInterface(pet_state)

    # 绑定 Vision 检测器（队员B）
    detector = UserStateDetector()
    team_d.api_bind_vision_detector(detector)
    detector.start()

    # 绑定 TTS 回调（队员C）
    team_d.api_register_status_listener(team_c_callback)
"""

import threading
import time
from typing import Callable, Dict, Any, Optional

from models.state.pet_state import PetState
from models.state.behavior_rules import BehaviorRules
from models.state.user_profile import UserProfile


class EchoTeamDInterface:
    """
    接口管理层：专门对接队员A、队员B、队员C。

    队员D的内部核心类：
    - PetState       → 管理 mood / energy / intimacy
    - BehaviorRules  → 行为决策 + 主动语音 + 回调通知
    """

    def __init__(self, pet_state_instance: PetState):
        """
        接口管理层初始化

        :param pet_state_instance: 队员D的核心 PetState 实例
        """
        self.pet_state = pet_state_instance
        self.rules = BehaviorRules(pet_state_instance)
        self.user_profile = UserProfile.load()

        # 队员C注册的状态变化监听器
        self._status_change_listener: Optional[Callable[[Dict[str, Any]], None]] = None

    # =========================================================================
    # 接口 1：提供给 【队员A (UI)】 —— 获取桌宠当前完整状态
    # =========================================================================
    def api_get_pet_status(self) -> Dict[str, Any]:
        """
        【队员A专用】读取桌宠当前的心情、能量、亲密度，用于更新 UI 面板。

        :return: {"mood": str, "energy": int, "intimacy": int}
        """
        return self.pet_state.get_state_info()

    # =========================================================================
    # 接口 2：提供给 【队员A (UI)】 —— 决策桌宠当前应执行的动作
    # =========================================================================
    def api_decide_action(self) -> str:
        """
        【队员A专用】根据当前 pet_state 决策应执行什么动作。
        UI 层拿到返回值后，切换桌宠表情/动画。

        :return: "idle" | "happy" | "sad" | "hungry" | "angry"
        """
        return self.rules.get_action()

    # =========================================================================
    # 接口 3：提供给 【队员A (UI)】 —— 获取状态变化历史
    # =========================================================================
    def api_get_status_history(self, n: int = 10) -> list:
        """
        【队员A专用】获取最近 n 条状态变化历史记录（调试面板或日志用）。

        :param n: 返回条数
        :return: 历史记录列表，每条为 {event, mood, energy, intimacy, timestamp}
        """
        return self.pet_state.get_history(n)

    # =========================================================================
    # 接口 4：提供给 【队员B (Vision)】 —— 传入用户检测状态
    # =========================================================================
    def api_apply_user_state(self, user_state: Dict[str, Any]):
        """
        【队员B专用】队员B检测到用户状态后，调用此接口同步给队员D。
        队员D会根据 state_code 自动更新桌宠的 mood / energy / intimacy。

        :param user_state: 来自 UserStateDetector.get_state() 的标准字典
            必含字段: state_code, confidence, duration, need_response, suggestion 等
        """
        if not user_state or not isinstance(user_state, dict):
            return

        # 1. 更新桌宠内在状态（委托给 BehaviorRules）
        self.rules.apply_user_state(user_state)

        # 2. 如果用户需要回应 且 队员C注册了监听器，通知队员C
        if user_state.get("need_response", False) and self._status_change_listener:
            event_data = {
                "event_type": "user_state_alert",
                "state_code": user_state.get("state_code", "unknown"),
                "suggestion": user_state.get("suggestion", ""),
                "action": self.api_decide_action(),
                "pet_id": self.pet_state.pet_id,
                "mood": self.pet_state.mood,
                "energy": self.pet_state.energy,
                "intimacy": self.pet_state.intimacy,
            }
            threading.Thread(
                target=self._status_change_listener, args=(event_data,), daemon=True
            ).start()

        print(f"[EchoTeamDInterface] 已接收用户状态: {user_state.get('state_code')}")

    # =========================================================================
    # 接口 5：提供给 【队员B (Vision)】 —— 一键绑定视觉检测器
    # =========================================================================
    def api_bind_vision_detector(self, detector):
        """
        【队员B专用】将队员B的 UserStateDetector 与队员D自动绑定。
        绑定后，detector 每次检测到新状态都会自动调用 api_apply_user_state。

        :param detector: UserStateDetector 实例（需支持 set_callback 方法）

        用法:
            detector = UserStateDetector()
            team_d.api_bind_vision_detector(detector)
            detector.start()  # 此后全自动同步
        """
        if not hasattr(detector, "set_callback"):
            print("[EchoTeamDInterface] 警告: detector 不支持 set_callback，无法自动绑定")
            return

        def _on_vision_result(user_state: dict):
            self.api_apply_user_state(user_state)

        detector.set_callback(_on_vision_result)
        print("[EchoTeamDInterface] 已成功绑定 Vision detector，用户状态将自动同步。")

    # =========================================================================
    # 接口 6：提供给 【队员C (NLP/TTS)】 —— 对话结束后更新状态
    # =========================================================================
    def api_on_chat_finished(self, word_count: int):
        """
        【队员C专用】每次 AI 对话 / TTS 语音播完后调用此接口。
        队员D会根据对话字数自动更新桌宠的能量和亲密度。

        规则:
        - 每约30字消耗1点能量（上限3点）
        - 每约20字增加1点亲密度（上限5点）
        - 心情自动趋向 "happy"

        :param word_count: AI 回复的文本字数（可用 len(reply_text) 获取）
        """
        if word_count <= 0:
            return

        self.rules.on_chat_finished(word_count)

        # 通知队员C的状态监听器（如果有注册）
        if self._status_change_listener:
            event_data = {
                "event_type": "chat_finished",
                "word_count": word_count,
                "action": self.api_decide_action(),
                "pet_id": self.pet_state.pet_id,
                "mood": self.pet_state.mood,
                "energy": self.pet_state.energy,
                "intimacy": self.pet_state.intimacy,
            }
            threading.Thread(
                target=self._status_change_listener, args=(event_data,), daemon=True
            ).start()

    def api_update_from_chat_emotion(self, emotion_result: Dict[str, Any]) -> None:
        """
        【队员C专用】根据聊天情绪分析结果更新用户画像和桌宠状态。

        `emotion_result` 可以是 analyze_chat_emotion 的结果，也可以是
        Team C 发出的 user_chat 事件字典，其中包含 emotion_result 字段。
        """
        result = emotion_result.get("emotion_result") if isinstance(emotion_result, dict) else None
        if not isinstance(result, dict):
            result = emotion_result if isinstance(emotion_result, dict) else {}
        if not result:
            return

        self.user_profile.update_from_chat_emotion(result)
        try:
            self.user_profile.save()
        except OSError as exc:
            print(f"[EchoTeamDInterface] 用户画像保存失败: {exc}")

        label = str(result.get("emotion_label") or "neutral").strip()
        confidence = _safe_float(result.get("confidence"), 0.0)
        need_care = bool(result.get("need_care"))
        ps = self.pet_state

        if label == "positive":
            ps.mood = "happy"
            ps.intimacy = min(100, ps.intimacy + 2)
            ps.energy = max(0, ps.energy - 1)
        elif label == "angry":
            ps.mood = "angry"
            ps.energy = max(0, ps.energy - 2)
        elif label in {"stress", "sad", "tired", "confused"}:
            ps.mood = "sad"
            ps.energy = max(0, ps.energy - (2 if label in {"stress", "tired"} else 1))
            if need_care and confidence >= 0.55:
                ps.intimacy = min(100, ps.intimacy + 1)
        else:
            if ps.mood == "angry":
                ps.mood = "neutral"

        if hasattr(ps, "_history"):
            ps._history.append(
                {
                    "event": f"chat_emotion:{label}",
                    "mood": ps.mood,
                    "energy": ps.energy,
                    "intimacy": ps.intimacy,
                    "emotion_result": dict(result),
                    "timestamp": time.time(),
                }
            )

        if need_care and self._status_change_listener:
            event_data = {
                "event_type": "chat_emotion_alert",
                "emotion_result": dict(result),
                "state_code": label,
                "suggestion": result.get("suggestion", ""),
                "action": self.api_decide_action(),
                "pet_id": self.pet_state.pet_id,
                "mood": self.pet_state.mood,
                "energy": self.pet_state.energy,
                "intimacy": self.pet_state.intimacy,
                "user_profile": self.user_profile.to_prompt_context(),
            }
            threading.Thread(
                target=self._status_change_listener, args=(event_data,), daemon=True
            ).start()

    # =========================================================================
    # 接口 7：提供给 【队员C (NLP/TTS)】 —— 获取主动语音提示文本
    # =========================================================================
    def api_get_speech_hint(self) -> Optional[str]:
        """
        【队员C专用】获取一句桌宠主动说话的提示文本。
        如果当前状态不需要主动说话，返回 None。

        :return: 提示文本或 None
        触发条件: energy<=10 / energy<=20 / energy<=30 /
                  intimacy>=90 / intimacy>=80 / intimacy<=15 / intimacy<=5 /
                  mood=="sad" / mood=="angry" / mood=="hungry"
        """
        return self.rules.get_speech_hint()

    # =========================================================================
    # 接口 8：提供给 【队员C (NLP/TTS)】 —— 判断是否该主动说话
    # =========================================================================
    def api_should_speak(self) -> bool:
        """
        【队员C专用】判断桌宠当前是否应该主动发出语音。

        :return: True = 应该说话，False = 保持安静
        """
        return self.rules.should_speak()

    # =========================================================================
    # 接口 9：提供给 【队员C (NLP/TTS)】 —— 获取桌宠ID
    # =========================================================================
    def api_get_pet_id(self) -> str:
        """
        【队员C专用】获取当前桌宠的 ID，供 TTS 文件命名使用。

        :return: "cat"（默认）或其他桌宠 ID
        """
        return self.rules.get_pet_id()

    def api_set_pet_id(self, pet_id: str) -> None:
        """
        【队员A/队员C专用】同步当前桌宠 ID，供动作决策和音色选择使用。
        """
        if hasattr(self.pet_state, "set_pet_id"):
            self.pet_state.set_pet_id(pet_id)

    # =========================================================================
    # 接口 10：提供给 【队员C (NLP/TTS)】 —— 注册状态变化监听
    # =========================================================================
    def api_register_status_listener(self, callback: Callable[[Dict[str, Any]], None]):
        """
        【队员C专用】队员C通过此接口注册一个"监听器"。
        当以下事件发生时，队员D会自动回调通知队员C：
        - 队员B检测到用户需要回应 (event_type: "user_state_alert")
        - AI 对话完成 (event_type: "chat_finished")

        :param callback: 签名为 callback(event_dict) 的回调函数
        """
        self._status_change_listener = callback
        print("[EchoTeamDInterface] 队员C的状态监听器已成功绑定。")

    # =========================================================================
    # 接口 11：提供给 【队员C (NLP/TTS)】 —— 重置/清理状态记忆
    # =========================================================================
    def api_reset_state_memory(self):
        """
        【队员C专用】全局重置、切换用户、或桌宠进入睡眠状态时调用此接口。
        会清空：
        - 桌宠状态变化历史
        - 最近聊天缓存
        - 队员C注册的监听器
        """
        self.rules.api_reset_ai_memory()
        self._status_change_listener = None
        print("[EchoTeamDInterface] 桌宠状态记忆已成功清空。")

    # =========================================================================
    # 接口 12：提供给 【队员C (NLP/TTS)】 —— 持久化状态
    # =========================================================================
    def api_save_state(self, filepath: Optional[str] = None):
        """
        【队员C专用】将当前桌宠状态持久化到 JSON 文件。

        :param filepath: 保存路径，默认 logs/pet_state.json
        """
        self.pet_state.save_state(filepath)

    # =========================================================================
    # 接口 13：提供给 【队员C (NLP/TTS)】 —— 恢复状态
    # =========================================================================
    def api_load_state(self, filepath: Optional[str] = None):
        """
        【队员C专用】从 JSON 文件恢复桌宠状态。

        :param filepath: 读取路径，默认 logs/pet_state.json
        """
        self.pet_state.load_state(filepath)


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default
