"""
Utilities for matching text language with the active TTS voice language.
"""

from __future__ import annotations

import re
from typing import Any

from models.nlp.prompt_builder import response_language_from_edge_voice


LANGUAGE_LABELS: dict[str, str] = {
    "zh-CN": "中文",
    "zh-HK": "粤语",
    "zh-TW": "繁体中文",
    "en-US": "英语",
    "en-GB": "英语",
    "fr-FR": "法语",
    "de-DE": "德语",
    "es-ES": "西班牙语",
    "es-MX": "西班牙语",
    "it-IT": "意大利语",
    "pt-BR": "葡萄牙语",
    "ru-RU": "俄语",
    "nl-NL": "荷兰语",
    "hi-IN": "印地语",
    "ar-EG": "阿拉伯语",
    "ja-JP": "日语",
    "ko-KR": "韩语",
}

LANGUAGE_FAMILIES: dict[str, str] = {
    "zh-CN": "zh",
    "zh-HK": "zh",
    "zh-TW": "zh",
    "en-US": "en",
    "en-GB": "en",
    "fr-FR": "fr",
    "de-DE": "de",
    "es-ES": "es",
    "es-MX": "es",
    "it-IT": "it",
    "pt-BR": "pt",
    "ru-RU": "ru",
    "nl-NL": "nl",
    "hi-IN": "hi",
    "ar-EG": "ar",
    "ja-JP": "ja",
    "ko-KR": "ko",
}

_LANGUAGE_ALIASES: dict[str, str] = {
    "zh": "zh-CN",
    "zh-cn": "zh-CN",
    "cn": "zh-CN",
    "chinese": "zh-CN",
    "中文": "zh-CN",
    "mandarin": "zh-CN",
    "zh-hk": "zh-HK",
    "yue": "zh-HK",
    "cantonese": "zh-HK",
    "粤语": "zh-HK",
    "zh-tw": "zh-TW",
    "traditional chinese": "zh-TW",
    "en": "en-US",
    "en-us": "en-US",
    "en-gb": "en-GB",
    "english": "en-US",
    "英语": "en-US",
    "fr": "fr-FR",
    "fr-fr": "fr-FR",
    "french": "fr-FR",
    "法语": "fr-FR",
    "de": "de-DE",
    "de-de": "de-DE",
    "german": "de-DE",
    "德语": "de-DE",
    "es": "es-ES",
    "es-es": "es-ES",
    "es-mx": "es-MX",
    "spanish": "es-ES",
    "西班牙语": "es-ES",
    "it": "it-IT",
    "it-it": "it-IT",
    "italian": "it-IT",
    "意大利语": "it-IT",
    "pt": "pt-BR",
    "pt-br": "pt-BR",
    "portuguese": "pt-BR",
    "葡萄牙语": "pt-BR",
    "ru": "ru-RU",
    "ru-ru": "ru-RU",
    "russian": "ru-RU",
    "俄语": "ru-RU",
    "nl": "nl-NL",
    "nl-nl": "nl-NL",
    "dutch": "nl-NL",
    "荷兰语": "nl-NL",
    "hi": "hi-IN",
    "hi-in": "hi-IN",
    "hindi": "hi-IN",
    "印地语": "hi-IN",
    "ar": "ar-EG",
    "ar-eg": "ar-EG",
    "arabic": "ar-EG",
    "阿拉伯语": "ar-EG",
    "ja": "ja-JP",
    "jp": "ja-JP",
    "ja-jp": "ja-JP",
    "japanese": "ja-JP",
    "日语": "ja-JP",
    "ko": "ko-KR",
    "kr": "ko-KR",
    "ko-kr": "ko-KR",
    "korean": "ko-KR",
    "韩语": "ko-KR",
}

_LATIN_MARKERS: dict[str, dict[str, int]] = {
    "en-US": {
        "hello": 4,
        "hi": 3,
        "hey": 3,
        "the": 2,
        "and": 2,
        "you": 2,
        "your": 2,
        "this": 2,
        "that": 2,
        "with": 2,
        "for": 1,
        "today": 2,
        "read": 2,
        "text": 2,
        "i": 1,
        "am": 1,
        "is": 1,
        "are": 1,
    },
    "fr-FR": {
        "bonjour": 4,
        "merci": 4,
        "salut": 3,
        "avec": 2,
        "pour": 1,
        "vous": 2,
        "nous": 2,
        "suis": 2,
        "est": 1,
        "une": 1,
        "dans": 1,
        "pas": 1,
        "oui": 2,
    },
    "de-DE": {
        "hallo": 3,
        "danke": 4,
        "bitte": 3,
        "ich": 3,
        "und": 2,
        "nicht": 3,
        "ein": 1,
        "eine": 1,
        "der": 1,
        "die": 1,
        "das": 1,
        "ist": 1,
        "mit": 1,
    },
    "es-ES": {
        "hola": 4,
        "gracias": 4,
        "estoy": 3,
        "esta": 1,
        "este": 1,
        "que": 1,
        "para": 1,
        "con": 1,
        "una": 1,
        "los": 1,
        "las": 1,
        "por": 1,
        "como": 1,
    },
    "it-IT": {
        "ciao": 4,
        "grazie": 4,
        "sono": 3,
        "che": 1,
        "per": 1,
        "con": 1,
        "una": 1,
        "non": 1,
        "come": 1,
        "oggi": 2,
    },
    "pt-BR": {
        "ola": 4,
        "olá": 4,
        "obrigado": 4,
        "obrigada": 4,
        "estou": 3,
        "voce": 3,
        "você": 3,
        "que": 1,
        "para": 1,
        "com": 1,
        "uma": 1,
        "nao": 2,
        "não": 2,
    },
    "nl-NL": {
        "hallo": 3,
        "dank": 3,
        "bedankt": 4,
        "voor": 2,
        "met": 1,
        "een": 1,
        "het": 1,
        "niet": 3,
        "ben": 2,
        "jij": 3,
        "vandaag": 3,
    },
}

_LATIN_DIACRITIC_SCORES: tuple[tuple[str, str, int], ...] = (
    ("fr-FR", "àâçéèêëîïôùûüÿœæ", 4),
    ("de-DE", "äöüß", 4),
    ("es-ES", "ñ¿¡áéíóúü", 4),
    ("pt-BR", "ãõçáéíóúâêôà", 4),
    ("it-IT", "àèéìíîòóù", 3),
)


def normalize_language_id(language: Any) -> str:
    value = str(language or "").strip()
    if not value:
        return ""
    key = value.replace("_", "-").lower()
    for locale in LANGUAGE_LABELS:
        if key == locale.lower():
            return locale
    if key in _LANGUAGE_ALIASES:
        return _LANGUAGE_ALIASES[key]
    if key.startswith("zh-hk"):
        return "zh-HK"
    if key.startswith("zh-tw"):
        return "zh-TW"
    for prefix, locale in (
        ("zh", "zh-CN"),
        ("en-gb", "en-GB"),
        ("en", "en-US"),
        ("fr", "fr-FR"),
        ("de", "de-DE"),
        ("es-mx", "es-MX"),
        ("es", "es-ES"),
        ("it", "it-IT"),
        ("pt", "pt-BR"),
        ("ru", "ru-RU"),
        ("nl", "nl-NL"),
        ("hi", "hi-IN"),
        ("ar", "ar-EG"),
        ("ja", "ja-JP"),
        ("ko", "ko-KR"),
    ):
        if key.startswith(prefix):
            return locale
    return ""


def language_from_edge_voice(edge_voice: Any) -> str:
    value = str(edge_voice or "").strip()
    if not value:
        return ""
    return normalize_language_id(response_language_from_edge_voice(value) or value)


def language_family(language: Any) -> str:
    normalized = normalize_language_id(language)
    if not normalized:
        return ""
    return LANGUAGE_FAMILIES.get(normalized, normalized.split("-", 1)[0].lower())


def language_label(language: Any) -> str:
    normalized = normalize_language_id(language)
    if not normalized:
        return "未知语言"
    return LANGUAGE_LABELS.get(normalized, normalized)


def languages_match(expected_language: Any, actual_language: Any) -> bool:
    expected_family = language_family(expected_language)
    actual_family = language_family(actual_language)
    return bool(expected_family and actual_family and expected_family == actual_family)


def detect_text_language(text: Any) -> str:
    value = str(text or "").strip()
    if not value:
        return ""

    counts = {
        "zh-CN": 0,
        "ja-JP": 0,
        "ko-KR": 0,
        "ru-RU": 0,
        "ar-EG": 0,
        "hi-IN": 0,
        "latin": 0,
    }
    for char in value:
        code = ord(char)
        if "\u3040" <= char <= "\u30ff":
            counts["ja-JP"] += 1
        elif "\uac00" <= char <= "\ud7af":
            counts["ko-KR"] += 1
        elif "\u0400" <= char <= "\u04ff":
            counts["ru-RU"] += 1
        elif "\u0600" <= char <= "\u06ff":
            counts["ar-EG"] += 1
        elif "\u0900" <= char <= "\u097f":
            counts["hi-IN"] += 1
        elif "\u4e00" <= char <= "\u9fff":
            counts["zh-CN"] += 1
        elif ("A" <= char <= "Z") or ("a" <= char <= "z") or (0x00C0 <= code <= 0x024F):
            counts["latin"] += 1

    total_letters = sum(counts.values())
    if total_letters <= 0:
        return ""

    non_latin = {key: count for key, count in counts.items() if key != "latin"}
    script_language, script_count = max(non_latin.items(), key=lambda item: item[1])
    latin_count = counts["latin"]
    if script_count > 0 and (script_count >= latin_count or script_count / total_letters >= 0.35):
        if counts["ja-JP"] > 0:
            return "ja-JP"
        return script_language

    if latin_count > 0:
        return _detect_latin_language(value)
    return script_language if script_count > 0 else ""


def _detect_latin_language(text: str) -> str:
    lowered = text.lower()
    words = re.findall(r"[a-zA-ZÀ-ÖØ-öø-ÿ]+", lowered)
    if not words:
        return ""

    scores = {language: 0 for language in _LATIN_MARKERS}
    for language, chars, weight in _LATIN_DIACRITIC_SCORES:
        scores[language] += sum(weight for char in lowered if char in chars)
    if "¿" in text or "¡" in text:
        scores["es-ES"] += 6

    for word in words:
        ascii_word = _strip_latin_accents(word)
        for language, markers in _LATIN_MARKERS.items():
            scores[language] += markers.get(word, 0)
            if ascii_word != word:
                scores[language] += markers.get(ascii_word, 0)

    best_language, best_score = max(scores.items(), key=lambda item: item[1])
    if best_score <= 0:
        return "en-US"
    return best_language


def _strip_latin_accents(value: str) -> str:
    replacements = str.maketrans(
        {
            "á": "a",
            "à": "a",
            "â": "a",
            "ä": "a",
            "ã": "a",
            "å": "a",
            "é": "e",
            "è": "e",
            "ê": "e",
            "ë": "e",
            "í": "i",
            "ì": "i",
            "î": "i",
            "ï": "i",
            "ó": "o",
            "ò": "o",
            "ô": "o",
            "ö": "o",
            "õ": "o",
            "ú": "u",
            "ù": "u",
            "û": "u",
            "ü": "u",
            "ç": "c",
            "ñ": "n",
        }
    )
    return value.translate(replacements)
