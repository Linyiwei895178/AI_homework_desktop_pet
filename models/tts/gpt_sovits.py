from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import requests

from utils.config import config


DEFAULT_GPT_SOVITS_API_URL = "http://127.0.0.1:9880"
DEFAULT_MEDIA_TYPE = "wav"

GPT_SOVITS_PROVIDER_ALIASES = {
    "gpt-sovits",
    "gpt_sovits",
    "gptsovits",
    "so-vits",
    "sovits",
    "voice-clone",
    "voice_clone",
}


def normalize_gpt_sovits_provider(value: Any) -> str:
    provider = str(value or "").strip().lower().replace("_", "-")
    if provider in {alias.replace("_", "-") for alias in GPT_SOVITS_PROVIDER_ALIASES}:
        return "gpt-sovits"
    return provider


def is_gpt_sovits_provider(value: Any) -> bool:
    return normalize_gpt_sovits_provider(value) == "gpt-sovits"


def normalize_gpt_sovits_api_url(value: Any = "") -> str:
    raw = str(value or config.get("GPT_SOVITS_API_URL", "") or os.getenv("GPT_SOVITS_API_URL", "")).strip()
    if not raw:
        raw = DEFAULT_GPT_SOVITS_API_URL
    return raw.rstrip("/")


def gpt_sovits_language(language_id: Any, default: str = "zh") -> str:
    value = str(language_id or "").strip().lower().replace("_", "-")
    if not value:
        return default
    if value.startswith("zh-hk") or value.startswith("zh-mo") or value.startswith("yue"):
        return "yue"
    if value.startswith("zh"):
        return "zh"
    if value.startswith("en"):
        return "en"
    if value.startswith("ja") or value.startswith("jp"):
        return "ja"
    if value.startswith("ko") or value.startswith("kr"):
        return "ko"
    return default


def build_voice_pack_backend(
    *,
    sample_paths: list[str],
    language_id: str,
    prompt_text: str = "",
    api_url: str = "",
    media_type: str = DEFAULT_MEDIA_TYPE,
) -> dict[str, Any]:
    samples = [str(path).replace("\\", "/") for path in sample_paths if str(path or "").strip()]
    if not samples:
        raise ValueError("GPT-SoVITS voice clone requires at least one reference audio sample.")

    language = gpt_sovits_language(language_id)
    backend: dict[str, Any] = {
        "provider": "gpt-sovits",
        "api_url": normalize_gpt_sovits_api_url(api_url),
        "ref_audio_path": samples[0],
        "aux_ref_audio_paths": samples[1:],
        "prompt_text": str(prompt_text or "").strip(),
        "prompt_lang": language,
        "text_lang": language,
        "media_type": _normalize_media_type(media_type),
        "text_split_method": "cut5",
        "batch_size": 1,
        "speed_factor": 1.0,
        "streaming_mode": False,
        "parallel_infer": True,
        "repetition_penalty": 1.35,
    }
    return backend


class GPTSoVITSClient:
    def __init__(self, api_url: str = "", timeout: float | None = None) -> None:
        self.api_url = normalize_gpt_sovits_api_url(api_url)
        self.timeout = timeout if timeout is not None else _float_config("GPT_SOVITS_TIMEOUT", 90.0)

    def synthesize(self, *, text: str, output_path: str | Path, backend: dict[str, Any]) -> Path:
        if not isinstance(backend, dict):
            raise RuntimeError("GPT-SoVITS backend settings are missing.")

        ref_audio_path = str(backend.get("ref_audio_path") or "").strip()
        if not ref_audio_path:
            raise RuntimeError("GPT-SoVITS reference audio is missing.")
        if not Path(ref_audio_path).exists():
            raise FileNotFoundError(ref_audio_path)

        payload = self._payload(text=text, backend=backend, ref_audio_path=ref_audio_path)
        response = requests.post(
            f"{self.api_url}/tts",
            json=payload,
            timeout=self.timeout,
        )
        if response.status_code >= 400:
            raise RuntimeError(_response_error(response))

        content_type = str(response.headers.get("content-type") or "").lower()
        if "application/json" in content_type:
            raise RuntimeError(_response_error(response))

        content = response.content or b""
        if not content:
            raise RuntimeError("GPT-SoVITS returned an empty audio response.")

        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        return path

    @staticmethod
    def _payload(*, text: str, backend: dict[str, Any], ref_audio_path: str) -> dict[str, Any]:
        media_type = _normalize_media_type(backend.get("media_type") or DEFAULT_MEDIA_TYPE)
        payload: dict[str, Any] = {
            "text": text,
            "text_lang": str(backend.get("text_lang") or "zh"),
            "ref_audio_path": ref_audio_path,
            "aux_ref_audio_paths": _existing_paths(backend.get("aux_ref_audio_paths")),
            "prompt_text": str(backend.get("prompt_text") or ""),
            "prompt_lang": str(backend.get("prompt_lang") or backend.get("text_lang") or "zh"),
            "top_k": _int_value(backend.get("top_k"), 5),
            "top_p": _float_value(backend.get("top_p"), 1.0),
            "temperature": _float_value(backend.get("temperature"), 1.0),
            "text_split_method": str(backend.get("text_split_method") or "cut5"),
            "batch_size": _int_value(backend.get("batch_size"), 1),
            "batch_threshold": _float_value(backend.get("batch_threshold"), 0.75),
            "split_bucket": bool(backend.get("split_bucket", True)),
            "speed_factor": _float_value(backend.get("speed_factor"), 1.0),
            "fragment_interval": _float_value(backend.get("fragment_interval"), 0.3),
            "seed": _int_value(backend.get("seed"), -1),
            "media_type": media_type,
            "streaming_mode": bool(backend.get("streaming_mode", False)),
            "parallel_infer": bool(backend.get("parallel_infer", True)),
            "repetition_penalty": _float_value(backend.get("repetition_penalty"), 1.35),
        }
        if "sample_steps" in backend:
            payload["sample_steps"] = _int_value(backend.get("sample_steps"), 32)
        if "super_sampling" in backend:
            payload["super_sampling"] = bool(backend.get("super_sampling"))
        return payload


def _existing_paths(value: Any) -> list[str]:
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, list):
        return []
    return [str(path) for path in value if str(path or "").strip() and Path(str(path)).exists()]


def _response_error(response: Any) -> str:
    text = str(getattr(response, "text", "") or "").strip()
    if text:
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            data = None
        if isinstance(data, dict):
            detail = data.get("detail") or data.get("message") or data.get("error")
            if detail:
                return f"GPT-SoVITS request failed: {detail}"
        return f"GPT-SoVITS request failed: {text[:500]}"
    return f"GPT-SoVITS request failed with HTTP {getattr(response, 'status_code', 'error')}"


def _normalize_media_type(value: Any) -> str:
    media_type = str(value or DEFAULT_MEDIA_TYPE).strip().lower().lstrip(".")
    if media_type not in {"wav", "mp3", "ogg", "aac", "raw"}:
        return DEFAULT_MEDIA_TYPE
    return media_type


def _float_config(key: str, default: float) -> float:
    raw = config.get(key, os.getenv(key, default))
    try:
        return max(1.0, float(raw))
    except (TypeError, ValueError):
        return default


def _float_value(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _int_value(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default
