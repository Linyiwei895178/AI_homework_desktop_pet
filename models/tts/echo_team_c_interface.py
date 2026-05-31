"""
Team C interface: NLP conversation plus TTS playback.
"""

from __future__ import annotations

import inspect
import threading
from typing import Any, Callable, Dict, Optional

from models.nlp.deepseek_api import DeepSeekClient
from models.tts.ai_voice_assistant import AIChatVoiceAssistant
from utils.config import config


class EchoTeamCInterface:
    """
    Interface layer used by Team A UI and Team D state logic.

    The public API stays compatible with the original project, while the
    implementation delegates real chat work to `AIChatVoiceAssistant`.
    """

    def __init__(
        self,
        assistant: Optional[AIChatVoiceAssistant] = None,
        deepseek_client: Optional[DeepSeekClient] = None,
    ):
        if assistant is not None and hasattr(assistant, "chat_with_context"):
            self.assistant = assistant
        else:
            self.assistant = AIChatVoiceAssistant(llm_client=deepseek_client)
        self._logic_status_callback: Optional[Callable[..., None]] = None
        self._explicit_voice_pack_id = str(config.get("VOICE_PACK_ID", "") or "").strip()

    def api_user_speak(
        self,
        text: str,
        current_state: Dict[str, Any],
        ui_callback: Callable[[str], None] | None,
    ) -> threading.Thread:
        """
        Generate an AI reply on a background thread and stream chunks to UI.
        """
        value = (text or "").strip()
        if not value:
            thread = threading.Thread(target=lambda: None, daemon=True)
            thread.start()
            return thread

        def run() -> None:
            try:
                reply = self.assistant.chat_with_context(
                    value,
                    current_state=current_state,
                    callback_ui=ui_callback,
                )
                self._notify_logic_callback(
                    {
                        "event_type": "user_chat",
                        "user_input": value,
                        "ai_reply": reply,
                        "word_count": len(reply),
                    }
                )
            except Exception as exc:
                print(f"[EchoTeamCInterface] api_user_speak 异常: {exc}")
                if ui_callback:
                    ui_callback(f"喵...出错了：{exc}")

        thread = threading.Thread(target=run, daemon=True)
        thread.start()
        return thread

    def api_play_system_voice(self, text: str, state: str = "neutral", action: str = "speak") -> threading.Thread:
        def run() -> None:
            self.assistant._play_voice(text, state=state, action=action)

        thread = threading.Thread(target=run, daemon=True)
        thread.start()
        return thread

    def api_play_speech_hint(self, hint_text: str) -> threading.Thread | None:
        if not hint_text or not hint_text.strip():
            return None
        return self.api_play_system_voice(hint_text, state="hint", action="speak")

    def api_register_logic_callback(self, callback: Callable[..., None]) -> None:
        self._logic_status_callback = callback
        print("[EchoTeamCInterface] 队员D逻辑回调已绑定。")

    def api_reset_ai_memory(self) -> None:
        self.assistant.clear_memory()
        print("[EchoTeamCInterface] 桌宠对话记忆已清空。")

    def api_get_last_chat(self) -> str:
        return self.assistant.get_last_reply()

    def api_set_pet_id(self, pet_id: str) -> None:
        self.assistant.set_pet_id(pet_id)
        if not self._explicit_voice_pack_id and self._auto_voice_pack_by_pet():
            self.assistant.set_voice_pack_id(pet_id)

    def api_set_voice_pack_id(self, pack_id: str) -> None:
        self._explicit_voice_pack_id = (pack_id or "").strip()
        if self._explicit_voice_pack_id:
            self.assistant.set_voice_pack_id(self._explicit_voice_pack_id)
            return
        if self._auto_voice_pack_by_pet():
            self.assistant.set_voice_pack_id(getattr(self.assistant, "pet_id", ""))
        else:
            self.assistant.set_voice_pack_id("")

    def api_set_tts_settings(self, settings: Dict[str, Any] | None) -> None:
        setter = getattr(self.assistant, "set_tts_settings", None)
        if callable(setter):
            setter(settings or {})

    def api_on_status_event(self, event_data: Dict[str, Any], ui_callback: Callable[[str], None] | None = None) -> str:
        return self.assistant.respond_to_status_event(event_data, callback_ui=ui_callback)

    def _notify_logic_callback(self, event_data: Dict[str, Any]) -> None:
        callback = self._logic_status_callback
        if callback is None:
            return
        try:
            if self._callback_wants_word_count(callback):
                callback(event_data["word_count"])
            else:
                callback(event_data)
        except TypeError:
            callback(event_data["word_count"])

    @staticmethod
    def _auto_voice_pack_by_pet() -> bool:
        return str(config.get("VOICE_PACK_AUTO_BY_PET", "true")).lower() != "false"

    @staticmethod
    def _callback_wants_word_count(callback: Callable[..., None]) -> bool:
        try:
            signature = inspect.signature(callback)
        except (TypeError, ValueError):
            return False
        params = list(signature.parameters.values())
        if len(params) != 1:
            return False
        param = params[0]
        if param.name in {"word_count", "count"}:
            return True
        annotation = param.annotation
        return annotation is int or annotation == "int"
