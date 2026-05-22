"""
EchoTeamCInterface - TTS / NLP 接口管理层

┌─────────────────────────────────────────────────┐
│  队员C 接口管理层                                 │
│  专门对接：队员A (UI)、队员D (State)              │
│  队员C负责：大模型对话 + TTS语音输出               │
└─────────────────────────────────────────────────┘

对接说明：
- 队员A（UI）：通过 api_user_speak() 发送用户文本，
              通过 api_play_system_voice() 播放固定台词
- 队员D（State）：注册逻辑回调，对话结束后更新状态
"""

import threading
import time
from typing import Callable, Dict, Any, Optional

from models.nlp.deepseek_api import generate_pet_reply, DeepSeekClient
from models.tts.tts_manager import speak


class EchoTeamCInterface:
    """
    接口管理层：专门对接队员A (UI) 和队员D (State)

    队员C的核心能力：
    - 大模型对话生成（DeepSeek API）
    - TTS 语音合成与播放
    - 主动语音提示（根据队员D的状态触发）

    用法:
        team_c = EchoTeamCInterface()
        # 对接队员D
        team_c.api_register_logic_callback(team_d.api_on_chat_finished)
        # 队员A调用
        team_c.api_user_speak("你好", current_state, ui_callback)
        team_c.api_play_system_voice("喵～")
    """

    def __init__(self, deepseek_client: Optional[DeepSeekClient] = None):
        """
        :param deepseek_client: DeepSeekClient 实例，不传则自动创建
        """
        self.deepseek = deepseek_client or DeepSeekClient()

        # 队员D注册的逻辑状态更新回调
        # 签名为 callback(event_dict: dict) -> None
        self._logic_status_callback: Optional[Callable[[Dict[str, Any]], None]] = None

        # 最近一次对话缓存
        self._last_chat_text: str = ""
        self._last_chat_time: float = 0.0

    # =========================================================================
    # 接口 1：提供给 【队员A (UI)】 —— 用户主动发送文本时调用
    # =========================================================================
    def api_user_speak(self, text: str,
                       current_state: Dict[str, Any],
                       ui_callback: Callable[[str], None]):
        """
        【队员A专用】当用户在桌宠UI输入文字并发送时调用此接口。

        :param text: 用户输入的文本字符串
        :param current_state: 队员B通过 get_state() 获取的当前标准状态字典
        :param ui_callback: 队员A传入的UI刷新函数，用于实现文字流式逐字蹦出

        流程:
            1. 调用 DeepSeek 大模型生成回复（流式回调给 ui_callback）
            2. 对话结束后，调用 TTS 播放语音
            3. 通知队员D更新状态（能量/亲密度）
        """
        if not text or not text.strip():
            return

        def run():
            """后台线程执行，不阻塞 UI"""
            try:
                # 1. 调用大模型生成回复（流式回调）
                full_reply = self.deepseek.generate(
                    text_prompt=text.strip(),
                    user_state=current_state,
                )

                # 2. 通过 ui_callback 将完整回复传给 UI（逐字效果由 UI 实现）
                if ui_callback:
                    ui_callback(full_reply)

                # 3. TTS 语音播放
                pet_state = current_state.get("state_code", "neutral")
                speak(
                    text=full_reply,
                    state=pet_state,
                    action="speak",
                )

                # 4. 对话结束后，主动通知队员D去更新状态
                if self._logic_status_callback:
                    event_data = {
                        "event_type": "user_chat",
                        "user_input": text.strip(),
                        "ai_reply": full_reply,
                        "word_count": len(full_reply),
                    }
                    self._logic_status_callback(event_data)

                # 缓存最近对话
                self._last_chat_text = full_reply
                self._last_chat_time = time.time()

            except Exception as e:
                print(f"[EchoTeamCInterface] api_user_speak 异常: {e}")
                if ui_callback:
                    ui_callback(f"喵…出错了: {e}")

        threading.Thread(target=run, daemon=True).start()

    # =========================================================================
    # 接口 2：提供给 【队员A (UI)】 —— 纯语音播放（如点击桌宠触发固定台词）
    # =========================================================================
    def api_play_system_voice(self, text: str,
                              state: str = "neutral",
                              action: str = "speak"):
        """
        【队员A专用】当桌宠因为被点击、晃动或者触发特定UI动画，
        需要单向发出声音时调用。（绕过大模型，直接TTS发声）

        :param text: 要播放的文本
        :param state: 状态标签（用于文件命名）
        :param action: 动作标签（用于文件命名）
        """
        def run():
            try:
                speak(text=text, state=state, action=action)
            except Exception as e:
                print(f"[EchoTeamCInterface] api_play_system_voice 异常: {e}")

        threading.Thread(target=run, daemon=True).start()

    # =========================================================================
    # 接口 3：提供给 【队员A (UI)】 —— 主动语音提示（根据队员D状态）
    # =========================================================================
    def api_play_speech_hint(self, hint_text: str):
        """
        【队员A专用】播放队员D提供的主动语音提示文本。
        队员D通过 api_get_speech_hint() 获取提示文本后，交由本接口播放。

        :param hint_text: 提示文本
        """
        if not hint_text or not hint_text.strip():
            return
        self.api_play_system_voice(hint_text, state="hint", action="speak")

    # =========================================================================
    # 接口 4：提供给 【队员D (State)】 —— 注册状态更新通知
    # =========================================================================
    def api_register_logic_callback(self, callback: Callable[[Dict[str, Any]], None]):
        """
        【队员D专用】队员D通过此接口注册一个"监听器"。
        当 AI 对话结束时，队员C会自动把对话字数、内容传给队员D，供其计算亲密度、心情值。

        :param callback: 签名为 callback(event_dict) 的回调函数
            event_dict 格式:
            {
                "event_type": "user_chat",
                "user_input": "你好",
                "ai_reply": "喵～你好呀！",
                "word_count": 6,
            }

        队员D收到后应调用:
            team_d.api_on_chat_finished(word_count=event_dict["word_count"])
        """
        self._logic_status_callback = callback
        print("[EchoTeamCInterface] 队员D的逻辑回调接口已成功绑定。")

    # =========================================================================
    # 接口 5：提供给 【队员D (State)】 —— 清理/重置记忆
    # =========================================================================
    def api_reset_ai_memory(self):
        """
        【队员D专用】全局重置、切换用户、或者桌宠进入睡眠状态时，
        调用此接口清空 DeepSeek 对话记忆上下文。
        """
        # 清空 DeepSeek 的对话上下文（如果有记忆功能）
        if hasattr(self.deepseek, 'clear_memory'):
            self.deepseek.clear_memory()

        # 清空本地缓存
        self._last_chat_text = ""
        self._last_chat_time = 0.0

        print("[EchoTeamCInterface] 桌宠对话记忆已成功清空。")

    # =========================================================================
    # 接口 6：提供给 【队员A (UI)】 —— 获取最近对话文本
    # =========================================================================
    def api_get_last_chat(self) -> str:
        """
        【队员A专用】获取最近一次 AI 回复的文本（用于显示在气泡中）。

        :return: 最近一次回复文本，若无则返回空字符串
        """
        return self._last_chat_text
