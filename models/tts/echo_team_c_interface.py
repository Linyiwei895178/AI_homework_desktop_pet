"""
Team C interface: NLP conversation plus TTS playback.
"""

from __future__ import annotations

import inspect
import re
import threading
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from models.nlp.deepseek_api import DeepSeekClient
from models.tts.ai_voice_assistant import AIChatVoiceAssistant
from models.tts.long_text_reader import split_text_for_tts
from utils.config import config


PROJECT_ROOT = Path(__file__).resolve().parents[2]


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
            self._owns_assistant = False
        else:
            self.assistant = AIChatVoiceAssistant(llm_client=deepseek_client)
            self._owns_assistant = True
        self._logic_status_callback: Optional[Callable[..., None]] = None
        self._explicit_voice_pack_id = str(config.get("VOICE_PACK_ID", "") or "").strip()
        self._long_text_stop = threading.Event()
        if self._owns_assistant:
            self._sync_memory_for_pet(getattr(self.assistant, "pet_id", "cat"))

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

    def api_play_system_voice(
        self,
        text: str,
        state: str | None = None,
        action: str | None = None,
        current_state: Dict[str, Any] | None = None,
    ) -> threading.Thread:
        voice_state = (state or "neutral").strip() or "neutral"
        voice_action = (action or "speak").strip() or "speak"
        if isinstance(current_state, dict):
            settings = current_state.get("tts_settings")
            if isinstance(settings, dict):
                self.api_set_tts_settings(settings)
            ctx_state, ctx_action = self.assistant._voice_context(current_state)
            if state is None:
                voice_state = ctx_state
            if action is None:
                voice_action = ctx_action

        def run() -> None:
            self.assistant._play_voice(text, state=voice_state, action=voice_action)

        thread = threading.Thread(target=run, daemon=True)
        thread.start()
        return thread

    def api_read_long_text(
        self,
        text: str,
        current_state: Dict[str, Any] | None = None,
        title: str = "",
        progress_callback: Callable[[Dict[str, Any]], None] | None = None,
    ) -> threading.Thread:
        """
        Read imported long text through the active pet voice/TTS settings.
        """
        chunks = split_text_for_tts(text, max_chars=700)
        self._long_text_stop.clear()
        voice_state, _voice_action = self.assistant._voice_context(current_state or {})

        def emit(event: Dict[str, Any]) -> None:
            if progress_callback:
                try:
                    progress_callback(event)
                except Exception as exc:
                    print(f"[EchoTeamCInterface] long text progress callback 异常: {exc}")

        def run() -> None:
            emit({"event_type": "long_text_started", "title": title, "total": len(chunks)})
            try:
                for index, chunk in enumerate(chunks, start=1):
                    if self._long_text_stop.is_set():
                        emit({"event_type": "long_text_stopped", "title": title, "index": index - 1, "total": len(chunks)})
                        return
                    emit(
                        {
                            "event_type": "long_text_chunk",
                            "title": title,
                            "index": index,
                            "total": len(chunks),
                        }
                    )
                    self.assistant._play_voice(chunk, state=voice_state, action="read")
                emit({"event_type": "long_text_finished", "title": title, "total": len(chunks)})
            except Exception as exc:
                print(f"[EchoTeamCInterface] api_read_long_text 异常: {exc}")
                emit({"event_type": "long_text_error", "title": title, "error": str(exc), "total": len(chunks)})

        thread = threading.Thread(target=run, daemon=True)
        thread.start()
        return thread

    def api_stop_long_text(self) -> None:
        self._long_text_stop.set()

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
        if self._owns_assistant:
            self._sync_memory_for_pet(pet_id)
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

    def _sync_memory_for_pet(self, pet_id: str) -> None:
        setter = getattr(self.assistant, "set_memory_path", None)
        if not callable(setter):
            return
        memory_dir = PROJECT_ROOT / "assets" / "ai_memory"
        safe_pet_id = _safe_memory_pet_id(pet_id)
        try:
            setter(str(memory_dir / f"{safe_pet_id}.json"), load_existing=True)
        except Exception as exc:
            print(f"[EchoTeamCInterface] AI 记忆加载失败: {exc}")

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


def _safe_memory_pet_id(pet_id: str) -> str:
    value = re.sub(r'[\\/:*?"<>|\s]+', "_", str(pet_id or "").strip())
    return value.strip("._") or "cat"
