"""
TTS manager with optional local voice packs.
"""

from __future__ import annotations

import asyncio
import ctypes
import os
import platform
import re
import shutil
import subprocess
import threading
import time
from pathlib import Path
from typing import Any

from models.tts.openvoice_bridge import OpenVoicePostProcessor
from models.tts.voice_pack import VoicePackManager
from models.tts.voice_style_pack import resolve_voice_style_pack_settings
from utils.config import config


PROJECT_ROOT = Path(__file__).resolve().parents[2]
URL_RE = re.compile(r"^https?://", re.IGNORECASE)
TTS_RUNTIME_OVERRIDE_KEYS = (
    "edge_voice",
    "response_language",
    "voice_style_pack",
    "voice_style_pack_enabled",
    "edge_rate",
    "edge_pitch",
    "edge_volume",
    "edge_playback_guard",
    "text_normalizer",
    "prosody_style",
    "voice_style_pack_locks_prosody",
    "edge_timeout",
    "openvoice_enabled",
    "openvoice_python",
    "openvoice_repo_dir",
    "openvoice_checkpoint_dir",
    "openvoice_device",
    "openvoice_tau",
    "openvoice_timeout",
    "tts_rate",
    "tts_volume",
)

TTS_EMOTION_STYLE_PROFILES: dict[str, dict[str, Any]] = {
    "neutral": {
        "edge_rate": "+0%",
        "edge_pitch": "+0Hz",
        "edge_volume": "+0%",
        "cute_style": False,
    },
    "cheerful": {
        "edge_rate": "+18%",
        "edge_pitch": "+22Hz",
        "edge_volume": "+8%",
        "cute_style": True,
    },
    "comfort": {
        "edge_rate": "-10%",
        "edge_pitch": "-4Hz",
        "edge_volume": "+2%",
        "cute_style": False,
    },
    "serious": {
        "edge_rate": "-6%",
        "edge_pitch": "-10Hz",
        "edge_volume": "+2%",
        "cute_style": False,
    },
    "story": {
        "edge_rate": "-8%",
        "edge_pitch": "+2Hz",
        "edge_volume": "+4%",
        "cute_style": False,
    },
    "news": {
        "edge_rate": "+4%",
        "edge_pitch": "-4Hz",
        "edge_volume": "+4%",
        "cute_style": False,
    },
    "playful": {
        "edge_rate": "-2%",
        "edge_pitch": "+38Hz",
        "edge_volume": "+8%",
        "cute_style": True,
    },
}

TTS_STATE_TO_EMOTION_STYLE = {
    "happy": "cheerful",
    "return": "cheerful",
    "sad": "comfort",
    "tired": "comfort",
    "distracted": "comfort",
    "away": "comfort",
    "angry": "serious",
    "camera_error": "serious",
    "hungry": "playful",
    "study_long": "comfort",
    "focused": "serious",
}


class TTSManager:
    _speech_lock = threading.Lock()

    def __init__(
        self,
        provider: str | None = None,
        enabled: bool = True,
        voice_profile: str = "default",
        cute_style: bool | None = None,
        pitch_shift: float = 1.0,
        voice_pack_id: str = "",
        voice_pack_dir: str | Path = "assets/voice_packs",
        voice_pack_enabled: bool | None = None,
        voice_pack_mode: str | None = None,
        tts_settings: dict[str, Any] | None = None,
    ):
        self.provider = provider or config.TTS_PROVIDER or "auto"
        self.enabled = bool(enabled)
        self.voice_profile = voice_profile
        self.cute_style = bool(cute_style) if cute_style is not None else True
        self.pitch_shift = float(pitch_shift)
        self.voice_pack_mode = str(voice_pack_mode or config.get("VOICE_PACK_MODE", "prefer") or "prefer").lower()
        self.emotion_style = "auto"
        self._runtime_overrides: dict[str, Any] = {}
        self.sounds_dir = PROJECT_ROOT / "assets" / "sounds"
        self.openvoice = OpenVoicePostProcessor(PROJECT_ROOT)
        voice_pack_dir = Path(voice_pack_dir)
        if not voice_pack_dir.is_absolute():
            voice_pack_dir = PROJECT_ROOT / voice_pack_dir
        pack_enabled = (
            str(config.get("VOICE_PACK_ENABLED", "true")).lower() != "false"
            if voice_pack_enabled is None
            else bool(voice_pack_enabled)
        )
        self.voice_pack = VoicePackManager(
            pack_id=voice_pack_id or config.VOICE_PACK_ID,
            base_dir=voice_pack_dir,
            enabled=pack_enabled,
        )
        if tts_settings:
            self.apply_runtime_settings(tts_settings)

    def set_voice_pack_id(self, pack_id: str) -> None:
        self.voice_pack.set_pack_id(pack_id)

    def apply_runtime_settings(self, settings: dict[str, Any] | None) -> None:
        """Apply UI-selected TTS settings without rebuilding the manager."""
        if not isinstance(settings, dict):
            return

        if "enabled" in settings:
            self.enabled = bool(settings.get("enabled"))

        provider = str(settings.get("provider") or "").strip().lower().replace("_", "-")
        if provider:
            if provider in {"disabled", "none", "false"}:
                provider = "off"
            self.provider = provider
            if provider in {"off", "disabled", "none", "false"}:
                self.enabled = False

        profile = str(settings.get("voice_profile") or "").strip()
        if profile:
            self.voice_profile = profile
        if "cute_style" in settings:
            self.cute_style = bool(settings.get("cute_style"))
        style = str(
            settings.get("emotion_style")
            or settings.get("tts_style")
            or settings.get("style")
            or ""
        ).strip().lower()
        if style:
            self.emotion_style = style

        pack_mode = str(settings.get("voice_pack_mode") or "").strip().lower()
        if pack_mode:
            self.voice_pack_mode = pack_mode

        overrides: dict[str, Any] = {}
        for key in TTS_RUNTIME_OVERRIDE_KEYS:
            if key not in settings:
                continue
            value = settings.get(key)
            if value is None or value == "":
                continue
            overrides[key] = value
        self._runtime_overrides = overrides

    def speak(self, text: str, pet_id: str = "cat", state: str = "neutral", action: str = "speak"):
        settings = self._voice_settings(pet_id=pet_id, state=state, action=action)
        spoken = self._prepare_spoken_text(
            text,
            cute_style=bool(settings.get("cute_style", self.cute_style)),
            voice_profile=str(settings.get("voice_profile") or self.voice_profile),
            edge_voice=str(settings.get("edge_voice") or ""),
        )
        if not spoken:
            return None

        use_voice_clip = str(action or "").strip().lower() not in {"read", "long-read", "long_text", "long-text"}
        if use_voice_clip and self.voice_pack_mode in {"prefer", "only"}:
            clip = self.voice_pack.pick_clip(spoken, state=state, action=action)
            if clip:
                self._play_media(clip)
                return str(clip)
            if self.voice_pack_mode == "only":
                return None

        if not self.enabled:
            print(f"[TTS] {spoken}")
            return None

        print(
            "[TTS] "
            f"provider={self.provider}, voice={settings['edge_voice']}, "
            f"rate={settings['edge_rate']}, pitch={settings['edge_pitch']}: {spoken}"
        )

        with self._speech_lock:
            for backend in self._provider_order():
                try:
                    if backend == "edge":
                        return self._speak_edge(spoken, pet_id, state, action, settings)
                    if backend == "pyttsx3":
                        return self._speak_pyttsx3(spoken, settings)
                    if backend == "windows-sapi":
                        return self._speak_windows_sapi(spoken, settings)
                except Exception as exc:
                    print(f"[TTS] {backend} 播放失败: {exc}")
            if use_voice_clip and self.voice_pack_mode == "fallback":
                clip = self.voice_pack.pick_clip(spoken, state=state, action=action)
                if clip:
                    self._play_media(clip)
                    return str(clip)
        return None

    def _prepare_spoken_text(
        self,
        text: str,
        cute_style: bool | None = None,
        voice_profile: str | None = None,
        edge_voice: str | None = None,
    ) -> str:
        value = (text or "").strip()
        if not value:
            return ""
        if URL_RE.match(value):
            return value
        use_cute_style = self.cute_style if cute_style is None else bool(cute_style)
        active_profile = (voice_profile or self.voice_profile or "").strip().lower()
        if not use_cute_style or active_profile not in {"cute", "cheerful", "playful"}:
            return value
        active_voice = str(edge_voice or "").strip().lower()
        if active_voice and not active_voice.startswith(("zh-", "zh_")):
            return value
        if not _contains_cjk(value):
            return value
        if value.endswith(("？", "?", "！", "!", "～", "~")):
            return value
        if value.endswith("。"):
            return value[:-1] + "呀。"
        if value.endswith("."):
            return value[:-1] + "呀."
        return value + "呀"

    def _select_voice_id(self, engine: Any) -> str | None:
        voices = engine.getProperty("voices") or []
        if self.voice_profile == "cute":
            for voice in voices:
                name = f"{getattr(voice, 'name', '')} {getattr(voice, 'id', '')}".lower()
                gender = str(getattr(voice, "gender", "")).lower()
                langs = " ".join(str(x).lower() for x in getattr(voice, "languages", []) or [])
                if (
                    ("female" in gender or any(key in name for key in ("xiaoyi", "xiaoxiao", "huihui", "yaoyao")))
                    and ("zh" in langs or "zh" in name or "xiaoyi" in name)
                ):
                    return getattr(voice, "id", None)
        return getattr(voices[0], "id", None) if voices else None

    def _voice_settings(self, pet_id: str = "cat", state: str = "neutral", action: str = "speak") -> dict:
        settings = {
            "edge_voice": config.EDGE_TTS_VOICE,
            "edge_rate": os.getenv("EDGE_TTS_RATE", "+8%"),
            "edge_pitch": os.getenv("EDGE_TTS_PITCH", "+12Hz"),
            "edge_volume": os.getenv("EDGE_TTS_VOLUME", "+8%"),
            "cute_style": self.cute_style,
        }
        selected_style = self._resolve_emotion_style(state=state, action=action)
        auto_profile = TTS_EMOTION_STYLE_PROFILES.get(selected_style, {})
        if auto_profile and self._emotion_style_is_auto():
            settings.update(auto_profile)
        profile = self.voice_pack.voice_profile(state=state, action=action)
        if profile:
            settings.update(profile)
        style_pack_enabled = self._style_pack_enabled()
        if style_pack_enabled:
            voice_style_pack = resolve_voice_style_pack_settings(
                self._runtime_overrides.get("voice_style_pack"),
                self._runtime_overrides.get("response_language"),
            )
            if voice_style_pack:
                settings.update(voice_style_pack)
        if auto_profile and not self._emotion_style_is_auto():
            settings.update(auto_profile)
        runtime_overrides = dict(self._runtime_overrides)
        if style_pack_enabled:
            runtime_overrides.pop("edge_voice", None)
            if bool(settings.get("voice_style_pack_locks_prosody", True)):
                for key in (
                    "edge_rate",
                    "edge_pitch",
                    "edge_volume",
                    "edge_playback_guard",
                    "text_normalizer",
                    "prosody_style",
                    "voice_style_pack_locks_prosody",
                ):
                    runtime_overrides.pop(key, None)
        settings.update(runtime_overrides)
        return settings

    def _style_pack_enabled(self) -> bool:
        if "voice_style_pack_enabled" in self._runtime_overrides:
            return str(
                self._runtime_overrides.get("voice_style_pack_enabled", True)
            ).strip().lower() not in {"0", "false", "no", "off"}
        return bool(str(self._runtime_overrides.get("voice_style_pack") or "").strip())

    def _emotion_style_is_auto(self) -> bool:
        return (self.emotion_style or "auto").strip().lower() in {"", "auto", "follow", "follow-state"}

    def _resolve_emotion_style(self, state: str = "neutral", action: str = "speak") -> str:
        requested = (self.emotion_style or "auto").strip().lower().replace("_", "-")
        aliases = {
            "natural": "neutral",
            "default": "neutral",
            "calm": "comfort",
            "gentle": "comfort",
            "soothing": "comfort",
            "happy": "cheerful",
            "professional": "serious",
            "storytelling": "story",
            "broadcast": "news",
        }
        requested = aliases.get(requested, requested)
        if requested and requested not in {"auto", "follow", "follow-state"}:
            return requested

        for value in (state, action):
            key = str(value or "").strip().lower().replace("_", "-")
            if key in TTS_STATE_TO_EMOTION_STYLE:
                return TTS_STATE_TO_EMOTION_STYLE[key]
            if key in TTS_EMOTION_STYLE_PROFILES:
                return key
        return "neutral"

    def _provider_order(self) -> tuple[str, ...]:
        windows_fallback = ("windows-sapi",) if platform.system() == "Windows" else ()
        provider = (self.provider or "auto").strip().lower().replace("_", "-")
        if provider in {"", "auto"}:
            return ("edge", "pyttsx3") + windows_fallback
        if provider in {"edge", "edge-tts", "neural", "edge-neural", "high-realism"}:
            return ("edge", "pyttsx3") + windows_fallback
        if provider in {"pyttsx3", "offline", "local"}:
            return ("pyttsx3",) + windows_fallback
        if provider in {"off", "none", "disabled", "false"}:
            return ()
        return ("edge", "pyttsx3") + windows_fallback

    def _speak_edge(self, text: str, pet_id: str, state: str, action: str, settings: dict) -> str:
        try:
            import edge_tts
        except ImportError as exc:
            raise RuntimeError("edge-tts 未安装") from exc

        output_path = self._next_audio_path(pet_id=pet_id, state=state, action=action, suffix=".mp3")

        async def save_audio() -> None:
            communicate = edge_tts.Communicate(
                _edge_synthesis_text(text, settings),
                voice=str(settings.get("edge_voice") or config.EDGE_TTS_VOICE),
                rate=str(settings.get("edge_rate") or "+0%"),
                volume=str(settings.get("edge_volume") or "+0%"),
                pitch=str(settings.get("edge_pitch") or "+0Hz"),
            )
            await asyncio.wait_for(
                communicate.save(str(output_path)),
                timeout=_positive_float_setting(settings.get("edge_timeout"), "EDGE_TTS_TIMEOUT", 15.0),
            )

        self._run_async(save_audio)
        if not output_path.exists() or output_path.stat().st_size <= 0:
            raise RuntimeError("edge-tts 没有生成音频文件")
        playback_path = self.openvoice.convert_if_enabled(output_path, self.voice_pack, settings)
        self._play_media(playback_path)
        return str(playback_path)

    def _speak_pyttsx3(self, text: str, settings: dict) -> None:
        try:
            import pyttsx3
        except ImportError as exc:
            raise RuntimeError("pyttsx3 未安装") from exc

        engine = pyttsx3.init()
        try:
            print("[TTS] 使用 pyttsx3 离线播放")
            voice_id = self._select_voice_id(engine)
            if voice_id:
                engine.setProperty("voice", voice_id)
            engine.setProperty("rate", _int_setting(settings.get("tts_rate"), "TTS_RATE", 168))
            engine.setProperty("volume", _float_setting(settings.get("tts_volume"), "TTS_VOLUME", 0.95))
            engine.say(text)
            engine.runAndWait()
        finally:
            try:
                engine.stop()
            except Exception:
                pass
        return None

    def _speak_windows_sapi(self, text: str, settings: dict) -> None:
        if platform.system() != "Windows":
            raise RuntimeError("Windows SAPI 仅支持 Windows")

        powershell = (
            shutil.which("powershell.exe")
            or r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe"
        )
        if not powershell or not Path(powershell).exists():
            raise RuntimeError("未找到 Windows PowerShell")

        rate = max(-10, min(10, round((_int_setting(settings.get("tts_rate"), "TTS_RATE", 168) - 168) / 16)))
        volume = round(_float_setting(settings.get("tts_volume"), "TTS_VOLUME", 0.95) * 100)
        script = f"""
[Console]::InputEncoding = [System.Text.UTF8Encoding]::new($false)
Add-Type -AssemblyName System.Speech
$text = [Console]::In.ReadToEnd()
$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
$synth.Rate = {rate}
$synth.Volume = {volume}
try {{
  $synth.Speak($text)
}} finally {{
  $synth.Dispose()
}}
"""
        print("[TTS] 使用 Windows SAPI 兜底播放")
        subprocess.run(
            [powershell, "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
            input=text,
            text=True,
            encoding="utf-8",
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )
        return None

    def _play_media(self, path: str | Path) -> None:
        media_path = Path(path)
        if not media_path.exists():
            raise FileNotFoundError(media_path)
        print(f"[TTS] 播放本地音频: {media_path}")

        if platform.system() == "Windows":
            if media_path.suffix.lower() == ".wav":
                try:
                    import winsound

                    winsound.PlaySound(str(media_path), winsound.SND_FILENAME)
                    return
                except Exception:
                    pass
            self._play_media_windows(media_path)
            return

        player = self._find_player()
        if player:
            subprocess.run(player + [str(media_path)], check=True)
            return
        print("[TTS] 未找到可用播放器，已生成音频但未播放。")

    def _next_audio_path(self, pet_id: str, state: str, action: str, suffix: str) -> Path:
        self.sounds_dir.mkdir(parents=True, exist_ok=True)
        stamp = f"{int(time.time() * 1000)}_{threading.get_ident()}"
        filename = f"{_safe_name(pet_id)}_sound_{_safe_name(state)}_{_safe_name(action)}_{stamp}{suffix}"
        return self.sounds_dir / filename

    @staticmethod
    def _run_async(async_factory) -> Any:
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(async_factory())

        result: dict[str, Any] = {}

        def runner() -> None:
            try:
                result["value"] = asyncio.run(async_factory())
            except BaseException as exc:
                result["error"] = exc

        thread = threading.Thread(target=runner, daemon=True)
        thread.start()
        thread.join()
        if "error" in result:
            raise result["error"]
        return result.get("value")

    @staticmethod
    def _play_media_windows(path: Path) -> None:
        alias = f"tts_{time.time_ns()}"
        suffix = path.suffix.lower()
        if suffix == ".mp3":
            open_command = f'open "{path}" type mpegvideo alias {alias}'
        else:
            open_command = f'open "{path}" alias {alias}'
        try:
            _mci_send(open_command)
            _mci_send(f"play {alias} wait")
        finally:
            try:
                _mci_send(f"close {alias}")
            except Exception:
                pass

    @staticmethod
    def _find_player() -> list[str] | None:
        candidates = (
            ("ffplay", ["-nodisp", "-autoexit", "-loglevel", "quiet"]),
            ("afplay", []),
            ("mpg123", ["-q"]),
            ("aplay", []),
        )
        for name, args in candidates:
            exe = shutil.which(name)
            if exe:
                return [exe] + args
        return None


def _mci_send(command: str) -> None:
    error = ctypes.windll.winmm.mciSendStringW(command, None, 0, None)
    if error:
        buffer = ctypes.create_unicode_buffer(255)
        ctypes.windll.winmm.mciGetErrorStringW(error, buffer, len(buffer))
        raise RuntimeError(f"MCI error {error}: {buffer.value}")


def _safe_name(value: str) -> str:
    cleaned = re.sub(r"[^0-9A-Za-z_.-]+", "_", str(value or "").strip())
    return cleaned.strip("._") or "pet"


def _contains_cjk(value: str) -> bool:
    return any("\u4e00" <= char <= "\u9fff" for char in value or "")


def _edge_synthesis_text(text: str, settings: dict | None = None) -> str:
    value = str(text or "")
    normalizer = str((settings or {}).get("text_normalizer") or "").strip().lower()
    if normalizer == "zh_tw_natural":
        value = _normalize_zh_tw_synthesis_text(value)
    value = _normalize_voice_style_prosody_text(
        value,
        str((settings or {}).get("prosody_style") or "").strip().lower(),
    )
    return _edge_playback_guard_text(value, settings)


def _normalize_voice_style_prosody_text(text: str, prosody_style: str = "") -> str:
    value = str(text or "")
    if not value:
        return value

    style = (prosody_style or "natural").strip().lower().replace("-", "_")
    if style in {"", "natural", "taiwan"}:
        return value

    value = re.sub(r"[!！]{3,}", "！", value)
    value = re.sub(r"[?？]{3,}", "？", value)
    value = re.sub(r"[~～]{2,}", "。", value)

    if style in {"boss", "dominant"}:
        return _space_cjk_punctuation(value, strong=True)
    if style in {"mature", "gentle"}:
        return _space_cjk_punctuation(value, strong=False)
    if style in {"sharp"}:
        return re.sub(r"\s*([，。！？；：、,.!?;:])\s*", r"\1", value).strip()
    return value


def _space_cjk_punctuation(text: str, strong: bool = False) -> str:
    value = str(text or "")
    if not _contains_cjk(value):
        return value
    pause_marks = "，、；;：:"
    end_marks = "。！？!?"
    value = re.sub(rf"([{re.escape(pause_marks)}])\s*", r"\1 ", value)
    if strong:
        value = re.sub(rf"([{re.escape(end_marks)}])\s*", r"\1 ", value)
    return value.strip()


def _normalize_zh_tw_synthesis_text(text: str) -> str:
    value = str(text or "")
    if not value:
        return value
    value = re.sub(r"[ \t]*([，。！？；：、])[ \t]*", r"\1", value)
    value = re.sub(r"(?<=[\u4e00-\u9fff])\s+(?=[\u4e00-\u9fff])", "", value)
    value = re.sub(r"[，,]{2,}", "，", value)
    value = re.sub(r"[。．]{2,}", "。", value)
    value = re.sub(r"[~～]{2,}", "。", value)
    return value.strip()


def _edge_playback_guard_text(text: str, settings: dict | None = None) -> str:
    value = str(text or "")
    if not value.strip():
        return value
    guard_enabled = str(
        (settings or {}).get("edge_playback_guard", True)
    ).strip().lower() not in {"0", "false", "no", "off"}
    if not guard_enabled:
        return value
    if value.lstrip().startswith((",", ".", ";", ":", "!", "?")):
        return value
    return f", {value}"


def _int_setting(value: Any, env_key: str, default: int) -> int:
    raw = value if value is not None else os.getenv(env_key, default)
    try:
        return int(raw)
    except (TypeError, ValueError):
        return default


def _float_setting(value: Any, env_key: str, default: float) -> float:
    raw = value if value is not None else os.getenv(env_key, default)
    try:
        return max(0.0, min(1.0, float(raw)))
    except (TypeError, ValueError):
        return default


def _positive_float_setting(value: Any, env_key: str, default: float) -> float:
    raw = value if value is not None else os.getenv(env_key, default)
    try:
        return max(1.0, float(raw))
    except (TypeError, ValueError):
        return default


_default_manager: TTSManager | None = None


def _manager() -> TTSManager:
    global _default_manager
    if _default_manager is None:
        _default_manager = TTSManager()
    return _default_manager


def speak(text: str, pet_id: str = "cat", state: str = "neutral", action: str = "speak"):
    return _manager().speak(text, pet_id=pet_id, state=state, action=action)
