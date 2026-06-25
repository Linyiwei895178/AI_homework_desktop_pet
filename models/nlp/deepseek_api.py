"""
DeepSeek chat API wrapper with an input-aware local fallback.
"""

from __future__ import annotations

import os
from typing import Any, Optional

from models.nlp.prompt_builder import (
    RESPONSE_LANGUAGE_NAMES,
    build_system_prompt,
    normalize_response_language,
    personalization_speech_fields,
)
from utils.config import config


LOCALIZED_MOCK_REPLIES = {
    "en-US": {
        "hello": "I am here. What are we doing first?",
        "generic": "That makes sense. Tell me the sharpest part of it.",
    },
    "en-GB": {
        "hello": "I am here. What are we doing first?",
        "generic": "That makes sense. Tell me the sharpest part of it.",
    },
    "fr-FR": {
        "hello": "Je suis la. On commence par quoi ?",
        "generic": "Oui, je vois. Dis-moi la partie la plus importante.",
    },
    "de-DE": {
        "hello": "Ich bin da. Womit fangen wir an?",
        "generic": "Ja, verstehe. Sag mir den wichtigsten Teil.",
    },
    "es-ES": {
        "hello": "Estoy aqui. Por donde empezamos?",
        "generic": "Si, te entiendo. Dime la parte que mas pesa.",
    },
    "es-MX": {
        "hello": "Estoy aqui. Por donde empezamos?",
        "generic": "Si, te entiendo. Dime la parte que mas pesa.",
    },
    "it-IT": {
        "hello": "Sono qui. Da dove partiamo?",
        "generic": "Sì, capisco. Dimmi la parte piu importante.",
    },
    "pt-BR": {
        "hello": "Estou aqui. Por onde comecamos?",
        "generic": "Entendi. Me diz a parte que mais pesa.",
    },
    "ru-RU": {
        "hello": "Ya zdes. S chego nachnem?",
        "generic": "Ponimayu. Skazhi, chto tut samoe vazhnoe.",
    },
    "nl-NL": {
        "hello": "Ik ben er. Waar beginnen we?",
        "generic": "Ik snap het. Vertel me welk deel het belangrijkst is.",
    },
    "hi-IN": {
        "hello": "Main yahin hoon. Kahan se shuru karein?",
        "generic": "Samajh gaya. Sabse zaroori hissa batao.",
    },
    "ar-EG": {
        "hello": "Ana hena. Nebda2 menen?",
        "generic": "Fahmak. Oul-li aham goz2 feha.",
    },
    "ja-JP": {
        "hello": "ここにいるよ。まず何から話そうか。",
        "generic": "うん、わかる。いちばん気になるところを聞かせて。",
    },
    "ko-KR": {
        "hello": "여기 있어. 뭐부터 할까?",
        "generic": "응, 알겠어. 제일 중요한 부분부터 말해줘.",
    },
}


def _contains_any(text: str, words: tuple[str, ...]) -> bool:
    return any(word and word in text for word in words)


def _contains_cjk(text: str) -> bool:
    return any("\u4e00" <= char <= "\u9fff" for char in text or "")


def _contains_japanese_kana(text: str) -> bool:
    return any("\u3040" <= char <= "\u30ff" for char in text or "")


def _looks_chinese_text(text: str) -> bool:
    return _contains_cjk(text) and not _contains_japanese_kana(text)


def _looks_like_internal_prompt(text: str) -> bool:
    return _contains_any(
        text or "",
        (
            "请生成一句",
            "请只说一句",
            "请主动说一句",
            "用户刚做了",
            "用户当前状态是",
            "刚才用户聊天里表现出",
            "根据当前状态",
            "联机共养事件",
        ),
    )


def _is_weather_query(text: str) -> bool:
    value = str(text or "").strip()
    lowered = value.lower()
    weather_words = ("天气", "天氣", "气温", "氣溫", "温度", "溫度", "下雨", "下雪", "刮风", "颳風", "空气质量", "空氣質素", "穿什么", "著咩")
    time_words = ("今天", "今日", "明天", "聽日", "现在", "而家", "实时", "即時", "最近", "这几天", "呢幾日", "周末")
    return (
        any(word in value for word in weather_words)
        and (
            any(word in value for word in time_words)
            or any(word in value for word in ("怎么样", "怎麼樣", "点样", "點樣", "如何", "咋样", "幾多度", "多少度", "?", "？"))
        )
    ) or "weather" in lowered


def _as_bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


def _positive_float(value: Any, default: float, minimum: float = 1.0) -> float:
    try:
        return max(minimum, float(value))
    except (TypeError, ValueError):
        return default


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
    fallback that answers the user's intent without echoing their sentence as a
    note-taking template.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        api_url: Optional[str] = None,
        model: Optional[str] = None,
        force_mock: Optional[bool] = None,
        fallback_to_mock: Optional[bool] = None,
        timeout: float = 12.0,
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
        self.timeout = _positive_float(os.getenv("DEEPSEEK_TIMEOUT"), float(timeout))
        self.translate_timeout = min(
            self.timeout,
            _positive_float(os.getenv("DEEPSEEK_TRANSLATE_TIMEOUT"), 8.0),
        )

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

    def translate_to_chinese(self, text: str, source_language: str = "") -> str:
        value = (text or "").strip()
        if not value:
            return ""

        language = normalize_response_language(source_language)
        if language in {"zh-CN", "zh-HK", "zh-TW"} or (not language and _looks_chinese_text(value)):
            return value
        if self.force_mock or not self.api_key:
            return self._mock_translate_to_chinese(value, source_language=language)

        try:
            translation = self._translate_remote(value, source_language=language)
            if translation and not self._translation_looks_untranslated(value, translation):
                return translation
            return self._mock_translate_to_chinese(value, source_language=language)
        except Exception as exc:
            print(f"[DeepSeek] 翻译失败，使用本地翻译兜底: {exc}")
            if self.fallback_to_mock:
                return self._mock_translate_to_chinese(value, source_language=language)
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
                "temperature": 0.9,
                "presence_penalty": 0.35,
                "frequency_penalty": 0.25,
                "stream": False,
            },
            timeout=self.timeout,
        )
        response.raise_for_status()
        data = response.json()
        reply = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        return str(reply).strip()

    def _translate_remote(self, text: str, source_language: str = "") -> str:
        import requests

        language_name = RESPONSE_LANGUAGE_NAMES.get(source_language, "the source language")
        response = requests.post(
            self.api_url,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": self.model,
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "Translate the user's text into concise, natural Simplified Chinese. "
                            f"The source language is {language_name}. "
                            "Return only the Chinese translation, with no labels or explanation."
                        ),
                    },
                    {"role": "user", "content": text},
                ],
                "temperature": 0.1,
                "stream": False,
            },
            timeout=self.translate_timeout,
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
        response_language = ""
        reply_route = {}
        if isinstance(user_state, dict):
            state_code = str(user_state.get("state_code") or "").strip()
            response_language = normalize_response_language(
                user_state.get("response_language")
                or user_state.get("reply_language")
                or user_state.get("language")
            )
            if isinstance(user_state.get("reply_route"), dict):
                reply_route = user_state.get("reply_route") or {}
            event_type = str(user_state.get("event_type") or user_state.get("event") or "").strip()
            if event_type:
                return self._mock_status_event_reply(user_state)

        routed_reply = self._mock_route_reply(text_prompt, reply_route, response_language)
        if routed_reply:
            return (self._state_prefix(state_code) + routed_reply)[:180]

        if response_language == "zh-HK":
            return self._mock_generate_cantonese(text_prompt, state_code=state_code, history=history)
        if response_language in LOCALIZED_MOCK_REPLIES:
            return self._mock_generate_localized(text_prompt, response_language, state_code, history)

        text = text_prompt.strip()
        low = text.lower()
        proactive_reply = self._mock_proactive_prompt_reply(text, user_state=user_state)
        if proactive_reply:
            base = proactive_reply
        elif _contains_any(low, ("你好", "嗨", "在吗", "早上好", "晚上好", "hello", "hi", "hey")):
            base = self._mock_greeting_reply(text, user_state=user_state)
        elif _contains_any(text, ("喜欢你", "喜欢我", "爱你", "爱我", "想你", "抱抱", "亲亲")):
            base = self._mock_affection_reply(text, user_state=user_state)
        elif _contains_any(text, ("困", "睡觉", "睡了", "晚安", "休息", "累了", "好累")):
            base = "那就别硬撑了。先把声音和节奏都放轻一点，给自己留条退路。"
        elif _contains_any(text, ("难过", "压力", "焦虑", "不开心", "委屈", "害怕", "烦", "崩溃")):
            base = "这听起来确实有点压心口。先别急着证明自己没事，我在这儿听你慢慢说。"
        elif _is_weather_query(text):
            base = "我现在还没接天气数据，不能可靠地报实时天气；如果刚才乱接话，那确实是我走偏了。"
        elif _contains_any(text, ("学习", "作业", "工作", "代码", "项目", "考试", "论文")):
            base = "可以，先别把它想成一整座山。我们就抓最小的一步开头。"
        elif _contains_any(text, ("电影", "动漫", "游戏", "音乐", "故事", "剧情")):
            base = "行啊，这个能聊。你是想吐槽它，还是认真盘一盘哪里打动你？"
        elif "?" in text or "？" in text or _contains_any(text, ("怎么", "为什么", "什么", "可以", "能不能")):
            base = "我的直觉是先抓最容易确认的那一点，不然很容易越想越绕。"
        else:
            base = self._mock_contextual_reply(text, history=history)

        reply = self._state_prefix(state_code) + base
        return reply[:160]

    def _mock_route_reply(self, text_prompt: str, reply_route: dict[str, Any], response_language: str = "") -> str:
        if not isinstance(reply_route, dict) or not reply_route:
            return ""
        intent = str(reply_route.get("intent") or "").strip()
        mode = str(reply_route.get("mode") or "").strip()
        direct_reply = str(reply_route.get("direct_reply") or "").strip()
        if direct_reply:
            return direct_reply
        if response_language == "zh-HK":
            return self._mock_route_reply_cantonese(intent, mode)
        if intent == "quality_complaint":
            return "对，这种模板感会很出戏。我会先判断你是在问信息、讲情绪，还是想闲聊，再直接接住这一句。"
        if intent == "weather":
            return "我现在还没接到实时天气数据，不能可靠地报天气；如果刚才乱接话，那确实是我走偏了。"
        if mode == "care":
            return "听起来确实有点压住人。你不用马上整理好，我在这儿听你慢慢说。"
        if mode == "task":
            return "可以，先别把它想成一整座山。我们只抓最小的第一步开始。"
        if intent == "settings":
            return "可以，我先确认一下：你是想改回复语言、声音音色，还是说话风格？"
        if intent == "affection":
            return "被你这么直接地说，我会很开心。那我也认真回你：我愿意好好陪着你。"
        if intent == "greeting":
            return "在呢，刚好等你开口。"
        return ""

    @staticmethod
    def _mock_route_reply_cantonese(intent: str, mode: str) -> str:
        if intent == "quality_complaint":
            return "係，呢種模板感會好出戲。我會先分清你係問資料、講情緒，定係想閒傾，再直接接住你呢句。"
        if intent == "weather":
            return "我而家未接到即時天氣資料，唔敢亂報。你話我知邊個城市，我可以幫你整理要查啲咩。"
        if mode == "care":
            return "聽落真係有啲頂住。你唔使即刻整理好，我喺度聽你慢慢講。"
        if mode == "task":
            return "得，先唔好諗到成座山咁大。我哋搵最細嗰一步開頭。"
        if intent == "settings":
            return "可以，我先確認一下：你想改回覆語言、聲線，定係講嘢風格？"
        if intent == "affection":
            return "你咁直接講，我會開心。咁我都認真答你：我係願意陪住你。"
        if intent == "greeting":
            return "我喺度呀。你想由邊度開始講？"
        return ""

    def _mock_generate_localized(
        self,
        text_prompt: str,
        response_language: str,
        state_code: str = "",
        history: Optional[list[dict[str, str]]] = None,
    ) -> str:
        replies = LOCALIZED_MOCK_REPLIES.get(response_language) or LOCALIZED_MOCK_REPLIES["en-US"]
        text = text_prompt.strip()
        low = text.lower()
        is_greeting = _contains_any(
            low,
            ("hello", "hi", "hey", "bonjour", "hallo", "hola", "ciao", "ola", "こんにちは", "안녕"),
        ) or _contains_any(text, ("你好", "嗨", "在吗", "早上好", "晚上好"))
        if response_language == "ja-JP":
            base = self._mock_generate_japanese(text, state_code=state_code, history=history, is_greeting=is_greeting)
        else:
            base = replies["hello"] if is_greeting else replies["generic"]
        return (self._localized_prefix(state_code, response_language) + base)[:260]

    def _mock_generate_japanese(
        self,
        text: str,
        state_code: str = "",
        history: Optional[list[dict[str, str]]] = None,
        is_greeting: bool = False,
    ) -> str:
        value = text.strip()
        if is_greeting:
            return "ここにいるよ。今日は何から話そうか。"
        if _contains_any(value, ("疲れ", "しんどい", "難しい", "压力", "焦虑", "累")):
            return "それは少し重いね。まず一息つこう。急がなくていいよ。"
        if _contains_any(value, ("勉強", "仕事", "作業", "コード", "学习", "作业", "工作")):
            return "いいね。大きく考えすぎず、最初の一手だけ決めよう。"
        if "?" in value or "？" in value:
            return "まず確かめられるところから見よう。そこが決まると次が軽くなるよ。"
        recent_topic = self._recent_user_topic(history)
        if recent_topic:
            return "さっきの話と少し繋がってそうだね。今いちばん気になるところはどこ？"
        return "うん、その感じわかる。もう少しだけ聞かせて。"

    def _mock_generate_cantonese(
        self,
        text: str,
        state_code: str = "",
        history: Optional[list[dict[str, str]]] = None,
    ) -> str:
        value = text.strip()
        low = value.lower()
        if _contains_any(value, ("你好", "嗨", "喂", "早晨", "晚上好")) or _contains_any(low, ("hello", "hi", "hey")):
            base = "我喺度呀。你想由邊度開始講？"
        elif _is_weather_query(value):
            base = "我而家未接到即時天氣資料，唔敢亂報。你話我知邊個城市，我可以幫你整理要查啲咩。"
        elif _contains_any(value, ("唔開心", "難過", "壓力", "焦慮", "攰", "好累", "煩", "崩潰")):
            base = "聽落真係有啲頂住心口。唔使急住扮冇事，我喺度聽你慢慢講。"
        elif _contains_any(value, ("鍾意你", "鐘意你", "愛你", "掛住你", "抱抱", "攬")):
            base = "你咁直講，我會開心㗎。咁我都認真答你：我鍾意陪住你。"
        elif _contains_any(value, ("學習", "功課", "工作", "代碼", "程式", "項目", "考試", "論文")):
            base = "得，唔好一嚟就當成座山咁睇。我哋先揀最細嗰步開頭。"
        elif "?" in value or "？" in value or _contains_any(value, ("點樣", "點解", "咩", "可唔可以", "得唔得")):
            base = "我覺得可以先捉最容易確認嗰點，咁就唔會越諗越亂。"
        elif history:
            base = "呢句同頭先嗰條線有啲接得上。你想往邊邊講落去？"
        else:
            base = "嗯，我明你意思。呢個位可以慢慢講，唔使即刻整理到好靚。"
        return (self._cantonese_state_prefix(state_code) + base)[:160]

    @staticmethod
    def _cantonese_state_prefix(state_code: str) -> str:
        return {
            "focused": "我細細聲講，",
            "distracted": "輕輕拉你一下，",
            "tired": "先抱一抱你，",
            "away": "我喺度等你返嚟，",
            "return": "返嚟啦，",
            "study_long": "你撐咗一陣喇，",
            "low_light": "如果燈光有啲暗，",
            "camera_error": "我呢邊睇唔清狀態，",
        }.get(state_code, "")

    @staticmethod
    def _recent_user_topic(history: Optional[list[dict[str, str]]] = None) -> str:
        for item in reversed(history or []):
            if item.get("role") != "user":
                continue
            content = str(item.get("content") or "").strip()
            if content:
                return content[:36]
        return ""

    @staticmethod
    def _localized_prefix(state_code: str, response_language: str) -> str:
        prefixes = {
            "en-US": {"focused": "Quietly: ", "tired": "First, breathe. ", "return": "Welcome back. "},
            "en-GB": {"focused": "Quietly: ", "tired": "First, breathe. ", "return": "Welcome back. "},
            "fr-FR": {"focused": "Tout doucement : ", "tired": "Respire d'abord. ", "return": "Bon retour. "},
            "de-DE": {"focused": "Ganz leise: ", "tired": "Atme kurz durch. ", "return": "Willkommen zurueck. "},
            "es-ES": {"focused": "En voz baja: ", "tired": "Primero respira. ", "return": "Bienvenido de vuelta. "},
            "es-MX": {"focused": "En voz baja: ", "tired": "Primero respira. ", "return": "Bienvenido de vuelta. "},
        }
        return prefixes.get(response_language, {}).get(state_code, "")

    @staticmethod
    def _state_prefix(state_code: str) -> str:
        return {
            "focused": "我小声说，",
            "distracted": "轻轻拉你一下，",
            "tired": "先抱一下你，",
            "away": "我先在这儿等你，",
            "return": "回来啦，",
            "study_long": "你已经撑了挺久了，",
            "low_light": "灯光如果有点暗，",
            "camera_error": "我这边看不清状态，",
        }.get(state_code, "")

    def _mock_status_event_reply(self, event_data: dict) -> str:
        event_type = str(event_data.get("event_type") or event_data.get("event") or "").strip()

        if event_type == "gesture_event":
            gesture = str(
                event_data.get("gesture_type")
                or event_data.get("gesture_code")
                or event_data.get("gesture")
                or ""
            ).strip()
            return {
                "wave": "看到你啦，刚刚那个挥手还挺可爱。",
                "ok": "OK，收到，我接住你的信号了。",
                "heart": "比心收到，我这边心情也亮了一下。",
                "raised_hand": "我在呢，你一举手我就注意到了。",
                "thumbs_up": "这个点赞我收下了，感觉还挺有劲。",
            }.get(gesture, "看到你的手势了，我在这儿。")

        if event_type == "screen_time_reminder":
            activity = str(event_data.get("activity_name") or event_data.get("activity_code") or "电脑前").strip()
            return f"你已经在{activity}待了一会儿，先眨眨眼、活动一下肩颈吧。"

        if event_type == "computer_activity_comment":
            code = str(event_data.get("activity_code") or "").strip()
            if code == "gaming":
                return self._mock_game_companion_reply("", user_state=event_data)
            if code == "watching":
                return self._mock_watching_companion_reply("", user_state=event_data)
            if code in {"coding", "working"}:
                return "你现在挺专注的，我小声陪着，不抢你的思路。"
            return "你还在电脑前忙着，我安静陪你一会儿。"

        if event_type in {"user_state_alert", "chat_emotion_alert"}:
            return self._mock_user_state_reply(event_data)

        return "状态有点变化，我会轻一点陪着你。"

    def _mock_user_state_reply(self, state: Optional[dict]) -> str:
        if not isinstance(state, dict):
            return "我在这儿陪着你。"
        state_code = str(state.get("state_code") or state.get("emotion_label") or "").strip()
        if state_code in {"happy", "positive", "return"}:
            return "看起来你状态不错，我也跟着轻快起来了。"
        if state_code in {"sad", "negative", "tired", "stress"}:
            return "你现在好像有点累或压着，先别急，我在旁边陪你缓一口气。"
        if state_code == "distracted":
            return "轻轻提醒一下，我们先把注意力拉回来一点点。"
        if state_code == "low_light":
            return "光线好像有点暗，要不要先把灯调亮一点？"
        if state_code == "study_long":
            return "你已经坚持挺久了，起来动一下也算认真学习的一部分。"
        if state_code == "away":
            return "我先乖乖等你回来。"
        return "我注意到状态有变化，会继续安静陪着你。"

    def _mock_proactive_prompt_reply(self, text: str, user_state: Optional[dict] = None) -> str:
        if not _looks_like_internal_prompt(text):
            return ""

        if "用户刚做了" in text and "手势" in text:
            if "挥手" in text:
                return "看到你啦，刚刚那个挥手还挺可爱。"
            if "OK" in text or "ok" in text:
                return "OK，收到，我接住你的信号了。"
            if "比心" in text:
                return "比心收到，我这边心情也亮了一下。"
            if "举手" in text:
                return "我在呢，你一举手我就注意到了。"
            return "看到你的手势了，我在这儿。"

        if "用户当前状态是" in text or "刚才用户聊天里表现出" in text:
            return self._mock_user_state_reply(user_state)

        if "使用电脑" in text or "持续大约" in text:
            return "盯屏幕有一会儿了，先让眼睛休息十秒钟吧。"

        if "电脑状态是" in text:
            if "游戏" in text or "gaming" in text:
                return self._mock_game_companion_reply(text, user_state=user_state)
            if "看剧" in text or "视频" in text or "watching" in text:
                return self._mock_watching_companion_reply(text, user_state=user_state)
            return "你还在电脑前忙着，我安静陪你一会儿。"

        return "我注意到状态有点变化，会用轻一点的声音陪着你。"

    def _mock_greeting_reply(self, text: str, user_state: Optional[dict] = None) -> str:
        tone, nickname, catchphrase, relationship = personalization_speech_fields(user_state)
        name_bit = f"{nickname}，" if nickname else ""
        if any(word in tone for word in ("毒舌", "吐槽")) or relationship == "损友":
            return f"哟，{name_bit}终于想起我了？说吧，我听着。"
        if any(word in tone for word in ("电子管家", "管家", "秘书")):
            return f"{name_bit}我在。现在要先处理哪件事？"
        if any(word in tone for word in ("温柔", "撒娇", "恋人", "甜")):
            tail = f"{catchphrase}。今天想让我陪你做什么？" if catchphrase else "今天想让我陪你做什么？"
            return f"在呢，{name_bit}{tail}"
        return f"在呢，{name_bit}刚好等你开口。"

    def _mock_affection_reply(self, text: str, user_state: Optional[dict] = None) -> str:
        tone, nickname, _, _ = personalization_speech_fields(user_state)
        name_bit = f"{nickname}，" if nickname else ""
        if any(word in tone for word in ("毒舌", "吐槽")):
            return f"行行行，{name_bit}这球打得太直了，我接住。"
        if _contains_any(text, ("喜欢我", "爱我")) and _contains_any(text, ("吗", "嘛", "？", "?")):
            return "当然喜欢。不是敷衍应一声，是愿意认真听你说话的那种喜欢。"
        if _contains_any(text, ("喜欢你", "爱你")):
            return "被你这么直球地说喜欢，我会很开心的。那我也认真回你：我喜欢和你待在一起。"
        if "想你" in text:
            return "我在呢。你一说想我，我就想靠近一点，多陪你一会儿。"
        if _contains_any(text, ("抱抱", "亲亲")):
            return "抱抱你，靠近一点点。你现在想安静待着，还是想慢慢说？"
        return "你这样说我很开心，我会认真接住，也认真回应你。"

    def _mock_contextual_reply(self, text: str, history: Optional[list[dict[str, str]]] = None) -> str:
        stripped = text.strip()
        if not stripped:
            return "我在。"
        if len(stripped) <= 3:
            return "嗯？我在听，你慢慢说。"
        if history:
            return "这和刚才那条线有点接上了。你更想往哪边说？"
        if _contains_any(stripped, ("不真实", "模板", "不像真人", "机械", "复读")):
            return "对，这种感觉很烦。它应该接住你的意思往前走，而不是把你的话换个壳吐回来。"
        if _contains_any(stripped, ("我觉得", "我想", "我希望", "我不想")):
            return "嗯，这个更像是你心里已经有个方向了，只是还差一点被确认。"
        return "嗯，我懂你的意思。这个点可以继续往下说，不用急着整理得很漂亮。"

    def _mock_game_companion_reply(self, text: str, user_state: Optional[dict] = None) -> str:
        title = self._mock_activity_title(user_state)
        if title:
            return f"《{title}》这局有点上头，先稳住，我在旁边看你打漂亮一点。"
        return "这局节奏有点上头，先稳住，我在旁边看你打漂亮一点。"

    def _mock_watching_companion_reply(self, text: str, user_state: Optional[dict] = None) -> str:
        title = self._mock_activity_title(user_state)
        if title:
            return f"《{title}》这个氛围挺会钩人的，先别急，我们看看后面怎么转。"
        return "这个氛围挺会钩人的，先别急，我们看看后面怎么转。"

    @staticmethod
    def _mock_activity_title(user_state: Optional[dict]) -> str:
        if not isinstance(user_state, dict):
            return ""
        title = str(user_state.get("window_title") or "").strip()
        if not title:
            return ""
        title = title.replace(" - Google Chrome", "").replace(" - Microsoft Edge", "")
        return title[:28]

    def _mock_translate_to_chinese(self, text: str, source_language: str = "") -> str:
        normalized = " ".join((text or "").strip().split())
        translations = {
            "I am here. What are we doing first?": "我在。我们先做什么？",
            "That makes sense. Tell me the sharpest part of it.": "有道理。跟我说说最关键的那部分。",
            "Je suis la. On commence par quoi ?": "我在。我们从哪里开始？",
            "Oui, je vois. Dis-moi la partie la plus importante.": "嗯，我明白。告诉我最重要的那部分。",
            "ここにいるよ。まず何から話そうか。": "我在这里。先从什么开始聊？",
            "うん、わかる。いちばん気になるところを聞かせて。": "嗯，我懂。跟我说说你最在意的地方。",
        }
        if normalized in translations:
            return translations[normalized]
        if _contains_japanese_kana(normalized):
            return f"这句日文暂时没能自动翻译出来。原文: {normalized}"
        return f"这句话暂时没能自动翻译出来。原文: {normalized}"

    @staticmethod
    def _translation_looks_untranslated(source: str, translation: str) -> bool:
        source_norm = " ".join((source or "").strip().split())
        translation_norm = " ".join((translation or "").strip().split())
        if not translation_norm:
            return True
        if source_norm == translation_norm:
            return True
        if _contains_japanese_kana(source_norm) and _contains_japanese_kana(translation_norm):
            return True
        return False

    def clear_memory(self) -> None:
        return None


def generate_pet_reply(text_prompt: str, user_state: Optional[dict] = None) -> str:
    client = DeepSeekClient()
    return client.generate(text_prompt, user_state=user_state)
