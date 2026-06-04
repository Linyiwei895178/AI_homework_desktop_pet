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

from app.ui.ui_settings_store import load_ui_settings, merge_personalization_into_state
from models.nlp.chat_memory import ChatMemory
from models.nlp.deepseek_api import DeepSeekClient
from models.nlp.prompt_builder import (
    build_proactive_prompt,
    normalize_response_language,
    response_language_from_edge_voice,
)
from models.state.user_profile import UserProfile
from models.tts.language_match import detect_text_language, language_family, languages_match
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
        self._tts_settings: Dict[str, Any] = {}
        self._lock = threading.RLock()

    def set_pet_id(self, pet_id: str) -> None:
        value = (pet_id or "").strip()
        if value:
            self.pet_id = value

    def set_memory_path(self, filepath: str | None, load_existing: bool = True) -> None:
        setter = getattr(self.memory, "set_persist_path", None)
        if callable(setter):
            setter(filepath, load_existing=load_existing)

    def set_voice_pack_id(self, pack_id: str) -> None:
        setter = getattr(self.tts, "set_voice_pack_id", None)
        if callable(setter):
            setter((pack_id or "").strip())

    def set_tts_settings(self, settings: Dict[str, Any] | None) -> None:
        self._tts_settings = dict(settings or {})
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

        voice_state, voice_action = self._voice_context(current_state)
        llm_state = self._state_with_response_language(current_state, voice_state, voice_action)
        response_language = self._response_language_from_state(llm_state)
        with self._lock:
            history = self._history_for_response_language(self.memory.get_messages(), response_language)
        try:
            reply = self.llm.generate(text, user_state=llm_state, history=history).strip()
        except Exception as exc:
            print(f"[AIChatVoiceAssistant] LLM 生成失败，使用本地降级回复: {exc}")
            reply = _friendly_fallback_reply(llm_state)
        if not reply:
            reply = _friendly_fallback_reply(llm_state)
        if _looks_like_internal_prompt(reply):
            reply = _status_event_fallback_reply(llm_state)
        tts_started = False
        if self.auto_tts and _can_start_tts_before_display(reply, response_language):
            self._play_voice_async(reply, state=voice_state, action=voice_action)
            tts_started = True
        display_reply = self._display_reply(reply, response_language=response_language)
        spoken_reply = self._spoken_reply(reply, display_reply, response_language=response_language)

        self._stream_to_ui(display_reply, callback_ui)

        with self._lock:
            self.memory.append_user(text)
            self.memory.append_assistant(spoken_reply)
            self._last_reply = display_reply

        if self.auto_tts and not tts_started:
            self._safe_play_voice(spoken_reply, state=voice_state, action=voice_action)

        return display_reply

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

    def _play_voice_async(self, text: str, state: str = "neutral", action: str = "speak") -> None:
        def run() -> None:
            try:
                self._play_voice(text, state=state, action=action)
            except Exception as exc:
                print(f"[AIChatVoiceAssistant] TTS 播放异常: {exc}")

        threading.Thread(target=run, daemon=True).start()

    def _voice_context(self, current_state: Optional[Dict[str, Any]]) -> tuple[str, str]:
        if not isinstance(current_state, dict):
            return "neutral", "speak"

        mood = str(current_state.get("mood") or "").strip()
        state_code = str(current_state.get("state_code") or "").strip()
        state = mood or _state_code_to_voice_state(state_code) or "neutral"
        action = str(current_state.get("voice_action") or current_state.get("tts_action") or "speak").strip()
        return state, action or "speak"

    def _state_with_response_language(
        self,
        current_state: Optional[Dict[str, Any]],
        state: str,
        action: str,
    ) -> Optional[Dict[str, Any]]:
        enriched = dict(current_state) if isinstance(current_state, dict) else {}
        self._inject_personalization_context(enriched)

        language = self._response_language_for_voice_context(state=state, action=action)
        if not language:
            return enriched or current_state
        if isinstance(current_state, dict):
            if normalize_response_language(enriched.get("response_language")):
                return enriched
        enriched["response_language"] = language
        return enriched

    @staticmethod
    def _inject_personalization_context(state: Dict[str, Any]) -> None:
        try:
            merge_personalization_into_state(state)
        except Exception as exc:
            print(f"[AIChatVoiceAssistant] 加载桌宠个性化设置失败: {exc}")
        if "user_profile" not in state:
            try:
                state["user_profile"] = UserProfile.load().to_prompt_context()
            except Exception as exc:
                print(f"[AIChatVoiceAssistant] 用户画像读取失败: {exc}")

    def _response_language_for_voice_context(self, state: str = "neutral", action: str = "speak") -> str:
        explicit = normalize_response_language(
            self._tts_settings.get("response_language")
            or self._tts_settings.get("reply_language")
            or self._tts_settings.get("language")
        )
        if explicit:
            return explicit

        runtime_voice = str(self._tts_settings.get("edge_voice") or "").strip()
        language = response_language_from_edge_voice(runtime_voice)
        if language:
            return language

        voice_settings = getattr(self.tts, "_voice_settings", None)
        if callable(voice_settings):
            try:
                settings = voice_settings(pet_id=self.pet_id, state=state, action=action)
            except TypeError:
                try:
                    settings = voice_settings(state=state, action=action)
                except Exception:
                    settings = {}
            except Exception:
                settings = {}
            if isinstance(settings, dict):
                return response_language_from_edge_voice(settings.get("edge_voice"))
        return ""

    @staticmethod
    def _response_language_from_state(state: Optional[Dict[str, Any]]) -> str:
        if not isinstance(state, dict):
            return ""
        return normalize_response_language(
            state.get("response_language")
            or state.get("reply_language")
            or state.get("language")
        )

    def _display_reply(self, reply: str, response_language: str = "") -> str:
        value = (reply or "").strip()
        if not value or not _needs_chinese_translation(value, response_language):
            return reply

        if _is_chinese_language(response_language):
            return self._translate_reply_to_chinese(value, response_language=response_language) or reply

        bilingual = self._bilingual_reply_with_line_translations(value, response_language=response_language)
        if bilingual:
            return bilingual

        translation = self._translate_reply_to_chinese(value, response_language=response_language)
        if translation and translation.strip() and translation.strip() != value:
            return f"{value}\n{translation.strip()}"
        return reply

    def _spoken_reply(self, reply: str, display_reply: str, response_language: str = "") -> str:
        if _is_chinese_language(response_language) and _needs_chinese_translation(reply, response_language):
            return (display_reply or reply).strip()
        return reply

    def _translate_reply_to_chinese(self, text: str, response_language: str = "") -> str:
        value = (text or "").strip()
        if not value:
            return ""
        lines = [line.strip() for line in value.splitlines()]
        non_empty_lines = [line for line in lines if line]
        if len(non_empty_lines) > 1:
            translated_lines: list[str] = []
            for line in lines:
                if not line:
                    translated_lines.append("")
                    continue
                translation = self._translate_line_to_chinese(line, response_language=response_language).strip()
                translated_lines.append(translation or line)
            return "\n".join(translated_lines).strip()
        translation = self._translate_line_to_chinese(value, response_language=response_language)
        return translation.strip() if translation.strip() else value

    def _bilingual_reply_with_line_translations(self, text: str, response_language: str = "") -> str:
        lines = [line.strip() for line in (text or "").strip().splitlines()]
        if len([line for line in lines if line]) <= 1:
            return ""

        display_lines: list[str] = []
        changed = False
        for line in lines:
            if not line:
                if display_lines and display_lines[-1]:
                    display_lines.append("")
                continue
            display_lines.append(line)
            translation = self._translate_line_to_chinese(line, response_language=response_language).strip()
            if translation and translation != line:
                display_lines.append(translation)
                changed = True
        if not changed:
            return ""
        return "\n".join(display_lines).strip()

    def _translate_line_to_chinese(self, text: str, response_language: str = "") -> str:
        translator = getattr(self.llm, "translate_to_chinese", None)
        language = normalize_response_language(response_language)
        detected_language = detect_text_language(text)
        if detected_language and (not language or not languages_match(language, detected_language)):
            source_language = detected_language
        elif language in {"zh-CN", "zh-HK", "zh-TW"}:
            source_language = ""
        else:
            source_language = language
        if callable(translator):
            try:
                return str(translator(text, source_language=source_language) or "").strip()
            except Exception as exc:
                print(f"[AIChatVoiceAssistant] 翻译到中文失败: {exc}")

        fallback = {
            "I am here. What would you like me to stay with you for today?": "我在这里。今天你想让我陪你做点什么？",
            "Sure, I am here.": "当然，我在这里。",
            "Je suis la. Qu'aimerais-tu que je fasse avec toi aujourd'hui ?": "我在这里。今天你想让我陪你做点什么？",
            "Parlons-en. Dis-moi ce qui compte le plus pour toi.": "我们聊聊这个吧。告诉我对你来说最重要的部分。",
        }
        normalized = " ".join((text or "").strip().split())
        return fallback.get(normalized, f"这句话的中文意思：{normalized}")

    @staticmethod
    def _history_for_response_language(history: List[Dict[str, str]], response_language: str = "") -> List[Dict[str, str]]:
        language = normalize_response_language(response_language)
        if not language:
            return [dict(item) for item in history]

        filtered: list[dict[str, str]] = []
        for item in history:
            role = str(item.get("role") or "")
            content = str(item.get("content") or "").strip()
            if role not in {"user", "assistant"} or not content:
                continue
            if role == "assistant" and _language_mismatch(content, language):
                if filtered and filtered[-1].get("role") == "user":
                    filtered.pop()
                continue
            filtered.append({"role": role, "content": content})
        return filtered

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

    def _safe_play_voice(self, text: str, state: str = "neutral", action: str = "speak") -> Optional[str]:
        try:
            return self._play_voice(text, state=state, action=action)
        except Exception as exc:
            print(f"[AIChatVoiceAssistant] TTS 播放失败: {exc}")
            return None


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


def _needs_chinese_translation(text: str, response_language: str = "") -> bool:
    language = normalize_response_language(response_language)
    value = (text or "").strip()
    if not value:
        return False
    detected_language = detect_text_language(value)
    if language in {"zh-CN", "zh-HK", "zh-TW"}:
        if detected_language:
            return not languages_match(language, detected_language)
        return not _contains_cjk(value) and any(char.isalpha() for char in value)
    if language:
        return True
    if detected_language:
        return not languages_match("zh-CN", detected_language)
    return not _contains_cjk(value) and any(char.isalpha() for char in value)


def _language_mismatch(text: str, expected_language: str = "") -> bool:
    expected = normalize_response_language(expected_language)
    detected = detect_text_language(text)
    return bool(expected and detected and not languages_match(expected, detected))


def _is_chinese_language(language: str = "") -> bool:
    return language_family(normalize_response_language(language)) == "zh"


def _can_start_tts_before_display(text: str, response_language: str = "") -> bool:
    language = normalize_response_language(response_language)
    if not language or _is_chinese_language(language):
        return False
    detected = detect_text_language(text)
    return not detected or languages_match(language, detected)


def _contains_cjk(value: str) -> bool:
    return any("\u4e00" <= char <= "\u9fff" for char in value or "")


def _friendly_fallback_reply(current_state: Optional[Dict[str, Any]] = None) -> str:
    state_code = ""
    if isinstance(current_state, dict):
        state_code = str(current_state.get("state_code") or current_state.get("mood") or "").strip()
    if state_code in {"tired", "sad", "stress"}:
        return "我刚刚有点走神啦，但我还在，先陪你慢慢缓一下。"
    return "我刚刚有点走神啦，我们再试一次～"


def _looks_like_internal_prompt(text: str) -> bool:
    value = str(text or "")
    markers = (
        "请用桌宠口吻",
        "请生成一句",
        "请只说一句",
        "请主动说一句",
        "用户刚做了",
        "用户当前状态是",
        "刚刚用户聊天里表现出",
        "根据当前状态",
    )
    return any(marker in value for marker in markers)


def _status_event_fallback_reply(current_state: Optional[Dict[str, Any]] = None) -> str:
    if not isinstance(current_state, dict):
        return _friendly_fallback_reply(current_state)

    event_type = str(current_state.get("event_type") or current_state.get("event") or "").strip()
    if event_type == "gesture_event":
        gesture = str(
            current_state.get("gesture_type")
            or current_state.get("gesture_code")
            or current_state.get("gesture")
            or ""
        ).strip()
        return {
            "wave": "我看到你啦，刚刚那个挥手很可爱。",
            "ok": "收到，OK，我已经接住你的信号啦。",
            "heart": "哎呀，比心收到，我也开心起来了。",
            "raised_hand": "我在呢，你举手我就马上注意到你啦。",
        }.get(gesture, "我看到你的手势啦。")

    state_code = str(current_state.get("state_code") or current_state.get("emotion_label") or "").strip()
    if state_code in {"happy", "positive", "return"}:
        return "看起来你心情不错呀，我也跟着开心起来了。"
    if state_code in {"sad", "negative", "tired", "stress"}:
        return "我看到你有点不舒服，先慢慢呼吸一下，我在旁边陪你。"
    if state_code == "distracted":
        return "轻轻提醒一下，我们先把注意力拉回来一点点。"
    return _friendly_fallback_reply(current_state)
