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
from typing import Callable, Dict, Any, Optional

from models.state.pet_state import PetState
from models.state.behavior_rules import BehaviorRules
from models.state.pet_leveling import apply_leveling_state
from models.state.state_serialization import pet_state_to_dict, apply_dict_to_pet_state


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

    # =========================================================================
    # 接口 14：提供给 【队员A/C】 —— 应用互动并返回状态变化
    # =========================================================================
    def api_apply_interaction(self, action_type: str, actor: str = "local") -> dict:
        """
        应用一次互动（点击/投喂/玩耍/打工等），更新桌宠状态并返回变化。

        :param action_type: 互动类型
        :param actor: 互动执行者
        :return: 状态变化字典
        """
        return self.pet_state.apply_interaction(action_type, actor)

    # =========================================================================
    # 接口 15：提供给 【Cloud】 —— 获取云端同步数据载荷
    # =========================================================================
    def api_get_cloud_sync_payload(self) -> dict:
        """
        获取当前桌宠状态的云端同步数据载荷。

        :return: 包含所有状态字段的字典
        """
        return pet_state_to_dict(self.pet_state)

    # =========================================================================
    # 接口 16：提供给 【Cloud】 —— 应用云端拉取的状态
    # =========================================================================
    def api_apply_cloud_state(self, state_dict: dict) -> None:
        """
        将云端拉取的状态应用到本地桌宠。
        # TODO: 冲突解决（updated_at 最新覆盖 / 事件增量合并）

        :param state_dict: 云端状态字典
        """
        apply_dict_to_pet_state(self.pet_state, state_dict)

    # =========================================================================
    # 接口 17：提供给 【队员C】 —— 从聊天情绪分析结果更新状态
    # =========================================================================
    def api_update_from_chat_emotion(self, emotion_result: dict) -> None:
        """
        根据聊天情绪分析结果更新桌宠状态。

        :param emotion_result: emotion_analyzer.analyze_chat_emotion() 的输出
        """
        if not isinstance(emotion_result, dict):
            return
        label = emotion_result.get("emotion_label", "neutral")
        need_care = emotion_result.get("need_care", False)
        if need_care:
            self.pet_state.mood = label if label in ("sad", "angry", "hungry") else self.pet_state.mood
        print(f"[EchoTeamDInterface] 情绪分析更新: {label}, need_care={need_care}")

    # =========================================================================
    # 接口 18：提供给 【NLP】 —— 获取用户画像上下文
    # =========================================================================
    def api_get_user_profile_context(self) -> dict:
        """
        获取用户画像的prompt上下文。
        # TODO: 接入 UserProfile 实例

        :return: 用户画像上下文字典，未接入时返回空字典
        """
        if hasattr(self, "_user_profile") and self._user_profile:
            return self._user_profile.to_prompt_context()
        return {}
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
