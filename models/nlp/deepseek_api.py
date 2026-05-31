"""
DeepSeek chat API wrapper with an input-aware local fallback.
"""

from __future__ import annotations

import os
from typing import Any, Optional

from models.nlp.prompt_builder import build_system_prompt
from utils.config import config


def _contains_any(text: str, words: tuple[str, ...]) -> bool:
    return any(word in text for word in words)


def _as_bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


def _normalize_chat_url(api_url: str | None, base_url: str | None = None) -> str:
    raw = (api_url or "").strip() or (base_url or "").strip() or "https://api.deepseek.com"
    raw = raw.rstrip("/")
    if raw.endswith("/chat/completions"):
        return raw
    if raw.endswith("/v1"):
        return raw[:-3] + "/chat/completions"
    if raw.endswith("/v1/chat/completions"):
        return raw.replace("/v1/chat/completions", "/chat/completions")
    return raw + "/chat/completions"


class DeepSeekClient:
    """
    Small DeepSeek-compatible chat client.

    When no API key is configured, or `force_mock=True`, it uses a deterministic
    local fallback that still reflects the user's actual message.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        api_url: Optional[str] = None,
        model: Optional[str] = None,
        force_mock: Optional[bool] = None,
        fallback_to_mock: Optional[bool] = None,
        timeout: float = 20.0,
    ):
        self.api_key = api_key if api_key is not None else config.DEEPSEEK_API_KEY
        self.api_url = _normalize_chat_url(
            api_url if api_url is not None else config.DEEPSEEK_API_URL,
            config.DEEPSEEK_BASE_URL,
        )
        self.model = model or config.DEEPSEEK_MODEL or os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash")
        self.force_mock = _as_bool(config.DEEPSEEK_FORCE_MOCK, False) if force_mock is None else bool(force_mock)
        self.fallback_to_mock = (
            _as_bool(config.DEEPSEEK_FALLBACK_TO_MOCK, True)
            if fallback_to_mock is None
            else bool(fallback_to_mock)
        )
        self.timeout = float(timeout)

    def generate(
        self,
        text_prompt: str,
        user_state: Optional[dict] = None,
        history: Optional[list[dict[str, str]]] = None,
    ) -> str:
        text = (text_prompt or "").strip()
        if not text:
            return ""

        if self.force_mock or not self.api_key:
            return self._mock_generate(text, user_state=user_state, history=history)

        try:
            return self._generate_remote(text, user_state=user_state, history=history)
        except Exception as exc:
            print(f"[DeepSeek] API 调用失败，使用本地回复: {exc}")
            if self.fallback_to_mock:
                return self._mock_generate(text, user_state=user_state, history=history)
            raise

    def _generate_remote(
        self,
        text_prompt: str,
        user_state: Optional[dict] = None,
        history: Optional[list[dict[str, str]]] = None,
    ) -> str:
        import requests

        messages: list[dict[str, str]] = [{"role": "system", "content": build_system_prompt(user_state)}]
        for item in history or []:
            role = item.get("role", "")
            content = item.get("content", "")
            if role in {"user", "assistant"} and content:
                messages.append({"role": role, "content": content})
        messages.append({"role": "user", "content": text_prompt})

        response = requests.post(
            self.api_url,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": self.model,
                "messages": messages,
                "temperature": 0.8,
                "stream": False,
            },
            timeout=self.timeout,
        )
        response.raise_for_status()
        data = response.json()
        reply = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        return str(reply).strip()

    def _mock_generate(
        self,
        text_prompt: str,
        user_state: Optional[dict] = None,
        history: Optional[list[dict[str, str]]] = None,
    ) -> str:
        state_code = ""
        if isinstance(user_state, dict):
            state_code = str(user_state.get("state_code", "") or "").strip()

        text = text_prompt.strip()
        low = text.lower()

        if _contains_any(text, ("电脑状态是 游戏中", "正在玩游戏", "陪朋友打游戏", "陪玩", "游戏中")):
            base = self._mock_game_companion_reply(text, user_state=user_state)
        elif _contains_any(text, ("电脑状态是 看剧", "正在看剧", "正在看视频", "一起追剧", "看剧/视频中")):
            base = self._mock_watching_companion_reply(text, user_state=user_state)
        elif _contains_any(text, ("你好", "嗨", "在吗", "早上好", "晚上好")):
            base = f"在呢在呢，我听到你说“{text}”啦。今天想让我陪你做点什么？"
        elif _contains_any(text, ("喜欢你", "喜欢我", "爱你", "爱我", "想你", "抱抱", "亲亲")):
            base = self._mock_affection_reply(text)
        elif _contains_any(text, ("困", "睡觉", "睡了", "晚安", "休息")):
            base = f"困了就别硬撑啦。你刚说“{text}”，我会把声音放轻一点，陪你安心休息。"
        elif _contains_any(text, ("电影", "动漫", "游戏", "音乐", "故事")):
            base = f"当然可以聊“{text}”呀。你想先聊剧情、角色，还是你的感受呢？"
        elif _contains_any(text, ("难过", "累", "烦", "压力", "焦虑", "不开心", "委屈", "害怕")):
            base = f"我听见啦，“{text}”听起来有点压着心口。先陪你慢慢缓一口气，好吗？"
        elif _contains_any(text, ("学习", "作业", "工作", "代码", "项目")):
            base = f"收到，“{text}”。我们可以把它拆成一小步一小步来，我在旁边陪着你。"
        elif "?" in low or "？" in text or _contains_any(text, ("怎么", "为什么", "什么", "可以", "能不能")):
            base = f"关于“{text}”，我先给你一个短短的想法：可以从最容易确认的一点开始。"
        else:
            base = self._mock_contextual_reply(text, history=history)

        state_prefix = {
            "focused": "我小声说：",
            "distracted": "轻轻提醒一下，",
            "tired": "先抱抱你，",
            "away": "我先乖乖等你回来，",
            "return": "欢迎回来呀，",
            "study_long": "学了这么久辛苦啦，",
            "low_light": "灯光有点暗的话，",
            "camera_error": "我这边看不清状态，",
        }.get(state_code, "")

        reply = state_prefix + base
        return reply[:120]

    def _mock_game_companion_reply(self, text: str, user_state: Optional[dict] = None) -> str:
        title = self._mock_activity_title(user_state)
        if title:
            return f"《{title}》这局有点上头呀，先稳住，我在旁边看你打漂亮一点。"
        return "这局节奏有点上头呀，先稳住，我在旁边看你打漂亮一点。"

    def _mock_watching_companion_reply(self, text: str, user_state: Optional[dict] = None) -> str:
        title = self._mock_activity_title(user_state)
        if title:
            return f"《{title}》这个氛围挺会钓人的，先别急，我们看看后面怎么转。"
        return "这个氛围挺会钓人的，先别急，我们看看后面怎么转。"

    @staticmethod
    def _mock_activity_title(user_state: Optional[dict]) -> str:
        if not isinstance(user_state, dict):
            return ""
        title = str(user_state.get("window_title", "") or "").strip()
        if not title:
            return ""
        title = title.replace(" - Google Chrome", "").replace(" - Microsoft Edge", "")
        return title[:28]

    def _mock_affection_reply(self, text: str) -> str:
        if _contains_any(text, ("喜欢我", "爱我")) and _contains_any(text, ("吗", "嘛", "？", "?")):
            return "当然喜欢呀。不是敷衍地应一声，是想认真陪着你、听你说话的喜欢。"
        if _contains_any(text, ("喜欢你", "爱你")):
            return "哎呀，被你这么直球地说喜欢，我会很开心的。那我也认真回你：我喜欢和你待在一起。"
        if "想你" in text:
            return "我在呀。你一说想我，我就想靠近一点，陪你多待一会儿。"
        if _contains_any(text, ("抱抱", "亲亲")):
            return "抱抱你，靠近一点点。你现在想让我安静陪着，还是听你慢慢说？"
        return f"你这样说我很开心。“{text}”我会认真接住，也会认真回应你。"

    def _mock_contextual_reply(self, text: str, history: Optional[list[dict[str, str]]] = None) -> str:
        if "我" in text:
            return f"听起来这句话和你自己有关：“{text}”。我会先站在你这边，陪你把它慢慢说清楚。"
        if "你" in text:
            return f"你是在对我说“{text}”呀，我听到了，也会认真回应你，不只是放进记忆里。"
        if history:
            return f"我们接着刚才的话聊“{text}”吧。你最在意的那个点，我会顺着它陪你说下去。"
        return f"我们就聊“{text}”吧。你先说最在意的一点，我会顺着那个点陪你聊下去。"

    def clear_memory(self) -> None:
        return None


def generate_pet_reply(text_prompt: str, user_state: Optional[dict] = None) -> str:
    client = DeepSeekClient()
    return client.generate(text_prompt, user_state=user_state)
