"""
Team C core: LLM conversation + voice playback.

`AIChatVoiceAssistant` is the object that the interface layer owns. It keeps
chat memory, calls the NLP client, streams text chunks to Team A, and delegates
speech playback to TTSManager.
"""

from __future__ import annotations

import threading
import time
from typing import Any, Callable, Dict, List, Optional

from models.nlp.chat_memory import ChatMemory
from models.nlp.deepseek_api import DeepSeekClient
from models.nlp.prompt_builder import build_proactive_prompt
from models.tts.tts_manager import TTSManager


UICallback = Callable[[str], None]


class AIChatVoiceAssistant:
    """Core assistant for Team C."""

    def __init__(
        self,
        llm_client: Optional[DeepSeekClient] = None,
        tts_manager: Optional[TTSManager] = None,
        memory: Optional[ChatMemory] = None,
        pet_id: str = "cat",
        auto_tts: bool = True,
        stream_delay: float = 0.015,
    ):
        self.llm = llm_client or DeepSeekClient()
        self.tts = tts_manager or TTSManager()
        self.memory = memory or ChatMemory()
        self.pet_id = pet_id
        self.auto_tts = bool(auto_tts)
        self.stream_delay = max(0.0, float(stream_delay))
        self._last_reply = ""
        self._lock = threading.RLock()

    def set_pet_id(self, pet_id: str) -> None:
        value = (pet_id or "").strip()
        if value:
            self.pet_id = value

    def set_voice_pack_id(self, pack_id: str) -> None:
        setter = getattr(self.tts, "set_voice_pack_id", None)
        if callable(setter):
            setter((pack_id or "").strip())

    def set_tts_settings(self, settings: Dict[str, Any] | None) -> None:
        setter = getattr(self.tts, "apply_runtime_settings", None)
        if callable(setter):
            setter(settings or {})

    def chat_with_context(
        self,
        user_input: str,
        current_state: Optional[Dict[str, Any]] = None,
        callback_ui: Optional[UICallback] = None,
    ) -> str:
        """
        Generate a reply using current user/pet state.

        `callback_ui` receives small text chunks. Team A can append chunks to a
        bubble to create a typewriter effect.
        """
        text = (user_input or "").strip()
        if not text:
            return ""

        with self._lock:
            history = self.memory.get_messages()

        reply = self.llm.generate(text, user_state=current_state, history=history).strip()
        if not reply:
            reply = "我刚刚有点走神了，可以再说一次吗？"

        self._stream_to_ui(reply, callback_ui)

        with self._lock:
            self.memory.append_user(text)
            self.memory.append_assistant(reply)
            self._last_reply = reply

        if self.auto_tts:
            state, action = self._voice_context(current_state)
            self._play_voice(reply, state=state, action=action)

        return reply

    def respond_to_status_event(
        self,
        event_data: Dict[str, Any],
        callback_ui: Optional[UICallback] = None,
    ) -> str:
        """
        Handle proactive status events from Team D.

        For `chat_finished` events the assistant stays silent to avoid callback
        loops. For user-state alerts it generates one short proactive sentence.
        """
        if not isinstance(event_data, dict):
            return ""

        event_type = event_data.get("event_type") or event_data.get("event")
        if event_type == "chat_finished":
            return ""

        prompt = build_proactive_prompt(event_data)
        return self.chat_with_context(prompt, current_state=event_data, callback_ui=callback_ui)

    def clear_memory(self) -> None:
        with self._lock:
            self.memory.clear()
            self._last_reply = ""
        if hasattr(self.llm, "clear_memory"):
            self.llm.clear_memory()

    def save_memory(self, filepath: str) -> None:
        self.memory.save_json(filepath)

    def load_memory(self, filepath: str) -> None:
        self.memory.load_json(filepath)

    def get_memory_messages(self) -> List[Dict[str, str]]:
        return self.memory.get_messages()

    def get_last_reply(self) -> str:
        with self._lock:
            return self._last_reply

    def _play_voice(self, text: str, state: str = "neutral", action: str = "speak") -> Optional[str]:
        return self.tts.speak(text, pet_id=self.pet_id, state=state, action=action)

    def _voice_context(self, current_state: Optional[Dict[str, Any]]) -> tuple[str, str]:
        if not isinstance(current_state, dict):
            return "neutral", "speak"

        mood = str(current_state.get("mood") or "").strip()
        state_code = str(current_state.get("state_code") or "").strip()
        state = mood or _state_code_to_voice_state(state_code) or "neutral"
        action = str(current_state.get("voice_action") or current_state.get("tts_action") or "speak").strip()
        return state, action or "speak"

    def _stream_to_ui(self, reply: str, callback_ui: Optional[UICallback]) -> None:
        if callback_ui is None:
            return
        for char in reply:
            try:
                callback_ui(char)
            except Exception as exc:
                print(f"[AIChatVoiceAssistant] UI 回调异常: {exc}")
                return
            if self.stream_delay > 0:
                time.sleep(self.stream_delay)


def _state_code_to_voice_state(state_code: str) -> str:
    return {
        "normal": "neutral",
        "focused": "neutral",
        "distracted": "sad",
        "tired": "sad",
        "away": "sad",
        "return": "happy",
        "study_long": "hungry",
        "low_light": "sad",
        "camera_error": "angry",
    }.get(state_code, "")
