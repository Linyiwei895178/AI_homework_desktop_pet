"""
Tests for Team C NLP/TTS integration.
"""

import json
import math
import os
import sys
import tempfile
import threading
import types
import wave
import zipfile
from pathlib import Path

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.nlp.chat_memory import ChatMemory
from models.nlp.deepseek_api import DeepSeekClient
from models.cloud.cloud_models import CloudPetEvent
from models.nlp.emotion_analyzer import analyze_chat_emotion
from models.nlp.proactive_event_builder import build_cloud_pet_event, build_screen_time_event
from models.nlp.prompt_builder import build_proactive_prompt, build_system_prompt, response_language_from_edge_voice
from models.tts import gpt_sovits as gpt_sovits_module
from models.tts import voice_pack as voice_pack_module
from models.tts.ai_voice_assistant import AIChatVoiceAssistant
from models.tts.echo_team_c_interface import EchoTeamCInterface
from models.tts.long_text_reader import combine_documents, read_book_file, split_text_for_tts
from models.tts.proactive_speech import ProactiveSpeechPolicy, build_local_event_reply
from models.tts.tts_manager import AsyncTTSQueue, TTSManager, _edge_synthesis_text
from models.tts.language_match import (
    detect_text_language,
    language_from_edge_voice,
    language_label,
    languages_match,
)
from models.tts.voice_pack import VoicePackManager, create_imported_voice_pack
from models.tts.voice_style_pack import resolve_voice_style_pack_settings
from models.state.echo_team_d_interface import EchoTeamDInterface
from models.state.pet_state import PetState
from models.state.user_profile import UserProfile


class FakeLLM:
    def generate(self, text_prompt, user_state=None, history=None):
        return f"收到：{text_prompt}"

    def clear_memory(self):
        return None


class RecordingTTS:
    def __init__(self):
        self.calls = []
        self.voice_pack_ids = []
        self.tts_settings = []

    def speak(self, text, pet_id="cat", state="neutral", action="speak"):
        self.calls.append(
            {
                "text": text,
                "pet_id": pet_id,
                "state": state,
                "action": action,
            }
        )
        return None

    def set_voice_pack_id(self, pack_id):
        self.voice_pack_ids.append(pack_id)

    def apply_runtime_settings(self, settings):
        self.tts_settings.append(dict(settings or {}))


def build_test_assistant():
    return AIChatVoiceAssistant(
        llm_client=FakeLLM(),
        tts_manager=TTSManager(enabled=False),
        memory=ChatMemory(max_rounds=2),
        auto_tts=True,
        stream_delay=0,
    )


def test_ai_chat_voice_assistant_streams_and_remembers():
    assistant = build_test_assistant()
    chunks = []

    reply = assistant.chat_with_context(
        "你好",
        current_state={"state_code": "normal"},
        callback_ui=chunks.append,
    )

    assert reply == "收到：你好"
    assert "".join(chunks) == reply
    messages = assistant.get_memory_messages()
    assert messages[-2]["role"] == "user"
    assert messages[-1]["role"] == "assistant"


def test_analyze_chat_emotion_returns_required_fields():
    result = analyze_chat_emotion("我压力好大，真的有点撑不住了")

    assert result["emotion_label"] == "stress"
    assert result["confidence"] > 0.5
    assert result["reason"]
    assert result["suggestion"]
    assert result["need_care"] is True


def test_response_language_override_is_separate_from_edge_voice():
    captured = {}

    class CapturingLLM:
        def generate(self, text_prompt, user_state=None, history=None):
            captured["text_prompt"] = text_prompt
            captured["user_state"] = dict(user_state or {})
            return "I am here."

    assistant = AIChatVoiceAssistant(
        llm_client=CapturingLLM(),
        tts_manager=TTSManager(enabled=False),
        memory=ChatMemory(max_rounds=2),
        auto_tts=False,
        stream_delay=0,
    )
    assistant.set_tts_settings(
        {
            "response_language": "en-US",
            "edge_voice": "zh-CN-XiaoyiNeural",
        }
    )

    assistant.chat_with_context("你好", current_state={"state_code": "normal"})

    assert captured["user_state"]["response_language"] == "en-US"


def test_voice_style_pack_resolves_voice_by_reply_language():
    manager = TTSManager(enabled=False, voice_pack_enabled=False)
    manager.apply_runtime_settings(
        {
            "voice_style_pack": "sweet_girl",
            "response_language": "en-US",
            "edge_voice": "zh-CN-XiaoyiNeural",
        }
    )

    settings = manager._voice_settings(pet_id="cat", state="normal", action="speak")

    assert settings["edge_voice"] == "en-US-JennyNeural"
    assert settings["cute_style"] is True


def test_boss_style_uses_low_steady_locked_prosody():
    settings = resolve_voice_style_pack_settings("boss", "zh-CN")

    assert settings["edge_voice"] == "zh-CN-YunxiNeural"
    assert settings["edge_rate"] == "-14%"
    assert settings["edge_pitch"] == "-20Hz"
    assert settings["edge_volume"] == "+7%"
    assert settings["prosody_style"] == "boss"
    assert settings["voice_style_pack_locks_prosody"] is True


def test_voice_style_pack_prosody_overrides_stale_saved_sliders():
    manager = TTSManager(enabled=False, voice_pack_enabled=False)
    manager.apply_runtime_settings(
        {
            "voice_style_pack": "boss",
            "voice_style_pack_enabled": True,
            "edge_rate": "+20%",
            "edge_pitch": "+24Hz",
            "edge_volume": "-4%",
        }
    )

    settings = manager._voice_settings(pet_id="cat", state="normal", action="speak")

    assert settings["edge_rate"] == "-14%"
    assert settings["edge_pitch"] == "-20Hz"
    assert settings["edge_volume"] == "+7%"


def test_runtime_edge_voice_without_style_pack_is_not_overridden_by_default_style():
    manager = TTSManager(enabled=False, voice_pack_enabled=False)
    manager.apply_runtime_settings({"edge_voice": "en-US-JennyNeural"})

    settings = manager._voice_settings(pet_id="cat", state="normal", action="speak")

    assert settings["edge_voice"] == "en-US-JennyNeural"


def test_boss_style_adds_steady_synthesis_pauses_without_changing_words():
    settings = resolve_voice_style_pack_settings("boss", "zh-CN")

    text = _edge_synthesis_text("别急，这件事我来处理！", settings)

    assert text == ", 别急， 这件事我来处理！"


def test_taiwan_style_uses_taiwan_voice_for_chinese_reply_language():
    settings = resolve_voice_style_pack_settings("taiwan", "zh-CN")

    assert settings["edge_voice"] == "zh-TW-HsiaoYuNeural"
    assert settings["edge_pitch"] == "+0Hz"
    assert settings["edge_playback_guard"] is False


def test_taiwan_style_avoids_edge_comma_guard_and_normalizes_cjk_spacing():
    settings = resolve_voice_style_pack_settings("taiwan", "zh-CN")

    text = _edge_synthesis_text("我 在 这边陪你  ，  慢慢说就好。", settings)

    assert text == "我在这边陪你，慢慢说就好。"


def test_taiwan_style_ignores_stale_saved_pitch_overrides():
    manager = TTSManager(enabled=False, voice_pack_enabled=False)
    manager.apply_runtime_settings(
        {
            "voice_style_pack": "taiwan",
            "response_language": "zh-CN",
            "edge_rate": "+2%",
            "edge_pitch": "+6Hz",
            "edge_volume": "+4%",
            "edge_playback_guard": True,
        }
    )

    settings = manager._voice_settings(pet_id="cat", state="normal", action="speak")

    assert settings["edge_rate"] == "-2%"
    assert settings["edge_pitch"] == "+0Hz"
    assert settings["edge_volume"] == "+2%"
    assert settings["edge_playback_guard"] is False


def test_disabled_voice_style_pack_keeps_local_voice_pack_profile():
    with tempfile.TemporaryDirectory() as tmpdir:
        base_dir = Path(tmpdir) / "packs"
        pack_dir = base_dir / "local"
        pack_dir.mkdir(parents=True)
        (pack_dir / "voice_pack.json").write_text(
            json.dumps(
                {
                    "voice_profiles": {
                        "default": {
                            "edge_voice": "zh-CN-XiaomoNeural",
                            "edge_rate": "-4%",
                        }
                    }
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        manager = TTSManager(
            enabled=False,
            voice_pack_id="local",
            voice_pack_dir=base_dir,
            voice_pack_enabled=True,
        )
        manager.apply_runtime_settings(
            {
                "voice_style_pack": "sweet_girl",
                "voice_style_pack_enabled": False,
            }
        )

        settings = manager._voice_settings(pet_id="cat", state="normal", action="speak")

        assert settings["edge_voice"] == "zh-CN-XiaomoNeural"
        assert settings["edge_rate"] == "-4%"


def test_tts_cute_profile_softens_short_spoken_text():
    manager = TTSManager(enabled=False, voice_profile="cute", cute_style=True, pitch_shift=1.0)

    assert manager._prepare_spoken_text("我在这儿陪你。") == "我在这儿陪你呀。"
    assert manager._prepare_spoken_text("要喝水吗？") == "要喝水吗？"
    assert manager._prepare_spoken_text("https://example.com") == "https://example.com"


def test_tts_pyttsx3_fallback_prefers_cute_voice():
    class FakeVoice:
        def __init__(self, voice_id, name, gender="", languages=None):
            self.id = voice_id
            self.name = name
            self.gender = gender
            self.languages = languages or []

    class FakeEngine:
        def getProperty(self, key):
            if key == "voices":
                return [
                    FakeVoice("david", "Microsoft David Desktop", "Male", [b"\x05en-US"]),
                    FakeVoice("xiaoyi", "Microsoft Xiaoyi Desktop", "Female", [b"\x05zh-CN"]),
                ]
            return None

    manager = TTSManager(enabled=False, voice_profile="cute", cute_style=False)

    assert manager._select_voice_id(FakeEngine()) == "xiaoyi"


def test_voice_pack_matches_keywords_then_event():
    with tempfile.TemporaryDirectory() as tmpdir:
        base_dir = Path(tmpdir) / "packs"
        pack_dir = base_dir / "daji"
        pack_dir.mkdir(parents=True)
        for filename in ("hello.wav", "click.wav", "speak.wav"):
            (pack_dir / filename).write_bytes(b"fake-audio")
        (pack_dir / "voice_pack.json").write_text(
            json.dumps(
                {
                    "clips": {
                        "neutral.click": ["click.wav"],
                        "speak": ["speak.wav"],
                    },
                    "keywords": {
                        "你好": ["hello.wav"],
                    },
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        manager = VoicePackManager(pack_id="daji", base_dir=base_dir, enabled=True)

        assert manager.pick_clip("你好呀", state="neutral", action="speak").name == "hello.wav"
        assert manager.pick_clip("摸摸头", state="neutral", action="click").name == "click.wav"
        assert manager.pick_clip("随便说点", state="sad", action="speak").name == "speak.wav"


def test_tts_manager_prefers_voice_pack_before_synthesis():
    with tempfile.TemporaryDirectory() as tmpdir:
        base_dir = Path(tmpdir) / "packs"
        pack_dir = base_dir / "angela"
        pack_dir.mkdir(parents=True)
        clip = pack_dir / "click.wav"
        clip.write_bytes(b"fake-audio")
        (pack_dir / "voice_pack.json").write_text(
            json.dumps({"clips": {"neutral.click": ["click.wav"]}}, ensure_ascii=False),
            encoding="utf-8",
        )
        played = []
        manager = TTSManager(
            provider="pyttsx3",
            voice_pack_id="angela",
            voice_pack_dir=str(base_dir),
            voice_pack_enabled=True,
            voice_pack_mode="prefer",
        )
        manager._play_media = played.append

        assert manager.speak("点击反馈", state="neutral", action="click") == str(clip)
        assert played == [clip]


def test_tts_manager_long_read_skips_short_voice_pack_clips():
    with tempfile.TemporaryDirectory() as tmpdir:
        base_dir = Path(tmpdir) / "packs"
        pack_dir = base_dir / "story"
        pack_dir.mkdir(parents=True)
        clip = pack_dir / "speak.wav"
        clip.write_bytes(b"RIFFfake")
        (pack_dir / "voice_pack.json").write_text(
            json.dumps(
                {
                    "id": "story",
                    "clips": {"speak": ["speak.wav"]},
                    "voice_profiles": {"default": {"edge_voice": "zh-CN-XiaoyiNeural"}},
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        manager = TTSManager(
            provider="pyttsx3",
            enabled=False,
            voice_pack_id="story",
            voice_pack_dir=str(base_dir),
            voice_pack_enabled=True,
            voice_pack_mode="prefer",
        )

        assert manager.speak("这一段应该走文本合成，而不是短音效。", action="read") is None


def test_tts_manager_uses_gpt_sovits_voice_pack_backend(monkeypatch, tmp_path):
    base_dir = tmp_path / "packs"
    pack_dir = base_dir / "clone"
    pack_dir.mkdir(parents=True)
    ref = pack_dir / "ref.wav"
    ref.write_bytes(b"RIFFref")
    (pack_dir / "voice_pack.json").write_text(
        json.dumps(
            {
                "id": "clone",
                "voice_profiles": {
                    "default": {
                        "provider": "gpt-sovits",
                        "cute_style": False,
                        "edge_voice": "zh-CN-XiaoyiNeural",
                        "gpt_sovits": {
                            "api_url": "http://127.0.0.1:9880",
                            "ref_audio_path": "ref.wav",
                            "prompt_text": "hello",
                            "prompt_lang": "zh",
                            "text_lang": "zh",
                            "media_type": "wav",
                        },
                    }
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    captured = {}

    class FakeResponse:
        status_code = 200
        headers = {"content-type": "audio/wav"}
        content = b"RIFFgenerated"
        text = ""

    def fake_post(url, json, timeout):
        captured["url"] = url
        captured["json"] = json
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr(gpt_sovits_module.requests, "post", fake_post)
    manager = TTSManager(
        provider="auto",
        enabled=True,
        voice_pack_id="clone",
        voice_pack_dir=str(base_dir),
        voice_pack_enabled=True,
    )
    manager.sounds_dir = tmp_path / "sounds"
    played = []
    manager._play_media = played.append

    output = manager.speak("hello", state="neutral", action="speak")

    assert output is not None
    assert Path(output).read_bytes() == b"RIFFgenerated"
    assert played == [Path(output)]
    assert captured["url"] == "http://127.0.0.1:9880/tts"
    assert captured["json"]["ref_audio_path"] == str(ref)
    assert captured["json"]["prompt_text"] == "hello"
    assert captured["json"]["text"] == "hello"


def test_tts_edge_adds_playback_guard_before_synthesis(monkeypatch, tmp_path):
    captured = {}

    class FakeCommunicate:
        def __init__(self, text, **_kwargs):
            captured["text"] = text

        async def save(self, output_path):
            Path(output_path).write_bytes(b"fake-mp3")

    monkeypatch.setitem(sys.modules, "edge_tts", types.SimpleNamespace(Communicate=FakeCommunicate))
    manager = TTSManager(provider="edge", enabled=True, voice_pack_enabled=False)
    manager.sounds_dir = tmp_path
    manager._play_media = lambda _path: None

    output = manager._speak_edge(
        "Hello world.",
        pet_id="cat",
        state="neutral",
        action="read",
        settings={
            "edge_voice": "en-US-JennyNeural",
            "edge_rate": "+0%",
            "edge_volume": "+0%",
            "edge_pitch": "+0Hz",
        },
    )

    assert captured["text"] == ", Hello world."
    assert Path(output).exists()


def test_tts_edge_can_play_openvoice_converted_audio(monkeypatch, tmp_path):
    captured = {}

    class FakeCommunicate:
        def __init__(self, text, **_kwargs):
            captured["text"] = text

        async def save(self, output_path):
            Path(output_path).write_bytes(b"fake-mp3")

    class FakeOpenVoice:
        def convert_if_enabled(self, source_path, _voice_pack, settings):
            assert settings["openvoice_enabled"] is True
            converted = Path(source_path).with_suffix(".openvoice.wav")
            converted.write_bytes(b"fake-wav")
            return converted

    monkeypatch.setitem(sys.modules, "edge_tts", types.SimpleNamespace(Communicate=FakeCommunicate))
    played = []
    manager = TTSManager(provider="edge", enabled=True, voice_pack_enabled=False)
    manager.sounds_dir = tmp_path
    manager.openvoice = FakeOpenVoice()
    manager._play_media = lambda path: played.append(Path(path))

    output = manager._speak_edge(
        "Hello world.",
        pet_id="cat",
        state="neutral",
        action="read",
        settings={
            "edge_voice": "en-US-JennyNeural",
            "edge_rate": "+0%",
            "edge_volume": "+0%",
            "edge_pitch": "+0Hz",
            "openvoice_enabled": True,
        },
    )

    assert captured["text"] == ", Hello world."
    assert output.endswith(".openvoice.wav")
    assert played == [Path(output)]


def test_tts_manager_reads_voice_profile_without_audio_files():
    with tempfile.TemporaryDirectory() as tmpdir:
        base_dir = Path(tmpdir) / "packs"
        pack_dir = base_dir / "cat"
        pack_dir.mkdir(parents=True)
        (pack_dir / "voice_pack.json").write_text(
            json.dumps(
                {
                    "voice_profiles": {
                        "happy.speak": {
                            "edge_voice": "zh-CN-XiaoxiaoNeural",
                            "edge_rate": "+15%",
                            "edge_pitch": "+20Hz",
                            "cute_style": False,
                        }
                    }
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        manager = TTSManager(
            enabled=False,
            voice_pack_id="cat",
            voice_pack_dir=str(base_dir),
            voice_pack_enabled=True,
        )
        settings = manager._voice_settings(pet_id="cat", state="happy", action="speak")

        assert settings["edge_voice"] == "zh-CN-XiaoxiaoNeural"
        assert settings["edge_rate"] == "+15%"
        assert settings["edge_pitch"] == "+20Hz"
        assert settings["cute_style"] is False


def test_voice_pack_profile_can_mark_spoken_text_playful():
    with tempfile.TemporaryDirectory() as tmpdir:
        base_dir = Path(tmpdir) / "packs"
        pack_dir = base_dir / "cat"
        pack_dir.mkdir(parents=True)
        (pack_dir / "voice_pack.json").write_text(
            json.dumps(
                {
                    "voice_profiles": {
                        "default": {
                            "voice_profile": "playful",
                            "cute_style": True,
                        }
                    }
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        manager = TTSManager(
            enabled=False,
            voice_pack_id="cat",
            voice_pack_dir=str(base_dir),
            voice_pack_enabled=True,
        )
        settings = manager._voice_settings(pet_id="cat", state="neutral", action="speak")

        assert settings["voice_profile"] == "playful"
        assert manager._prepare_spoken_text(
            "我来了。",
            cute_style=settings["cute_style"],
            voice_profile=settings["voice_profile"],
        ) == "我来了呀。"


def test_create_imported_voice_pack_generates_simulated_profile(tmp_path: Path):
    sample = tmp_path / "voice.wav"
    with wave.open(str(sample), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(16000)
        wav.writeframes(b"\x00\x00" * 1600)

    base_dir = tmp_path / "packs"
    manifest = create_imported_voice_pack(
        display_name="我的粤语包",
        language_id="zh-HK",
        sample_paths=[sample],
        base_dir=base_dir,
    )

    pack_dir = base_dir / manifest["id"]
    manifest_path = pack_dir / "voice_pack.json"
    copied_sample = pack_dir / manifest["samples"][0]
    denoised_sample = pack_dir / manifest["noise_reduction"]["processed_samples"][0]

    assert manifest_path.exists()
    assert copied_sample.exists()
    assert denoised_sample.exists()
    assert copied_sample.read_bytes() == sample.read_bytes()
    assert manifest["display_name"] == "粤语我的粤语包"
    assert manifest["user_name"] == "我的粤语包"
    assert manifest["language"]["id"] == "zh-HK"
    assert manifest["voice_profiles"]["default"]["edge_voice"] == "zh-HK-HiuGaaiNeural"
    assert manifest["analysis"]["sample_count"] == 1
    assert manifest["analysis"]["known_duration_seconds"] == 0.1
    assert manifest["noise_reduction"]["mode"] == "light_conservative"
    assert manifest["noise_reduction"]["original_priority"] is True
    assert manifest["noise_reduction"]["processed_count"] == 1

    manager = VoicePackManager(pack_id=manifest["id"], base_dir=base_dir, enabled=True)
    settings = manager.voice_profile(state="neutral", action="speak")

    assert settings["edge_voice"] == "zh-HK-HiuGaaiNeural"
    assert manager.pick_clip("任意一句话", state="neutral", action="speak") is None


def test_delete_voice_pack_removes_valid_pack_dir(tmp_path: Path):
    base_dir = tmp_path / "packs"
    pack_dir = base_dir / "custom"
    sample_dir = pack_dir / "samples"
    sample_dir.mkdir(parents=True)
    (pack_dir / "voice_pack.json").write_text("{}", encoding="utf-8")
    (sample_dir / "voice.wav").write_bytes(b"voice")

    assert voice_pack_module.delete_voice_pack("custom", base_dir=base_dir) is True
    assert not pack_dir.exists()


def test_delete_voice_pack_rejects_path_traversal(tmp_path: Path):
    base_dir = tmp_path / "packs"
    outside_dir = tmp_path / "outside"
    outside_dir.mkdir()
    (outside_dir / "voice_pack.json").write_text("{}", encoding="utf-8")

    with pytest.raises(ValueError):
        voice_pack_module.delete_voice_pack("../outside", base_dir=base_dir)

    assert outside_dir.exists()


def test_imported_voice_pack_fits_edge_profile_from_pitch(tmp_path: Path):
    sample = tmp_path / "bright.wav"
    rate = 16000
    with wave.open(str(sample), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(rate)
        frames = []
        for i in range(rate):
            value = int(12000 * math.sin(2 * math.pi * 230 * (i / rate)))
            frames.append(value.to_bytes(2, byteorder="little", signed=True))
        wav.writeframes(b"".join(frames))

    manifest = create_imported_voice_pack(
        display_name="明亮音色",
        language_id="zh-CN",
        sample_paths=[sample],
        base_dir=tmp_path / "packs",
    )
    profile = manifest["voice_profiles"]["default"]
    features = manifest["analysis"]["voice_features"]

    assert features["estimated_pitch_hz"] > 200
    assert profile["fit_source"] == "audio_features"
    assert profile["edge_voice"] == "zh-CN-XiaoyiNeural"
    assert profile["edge_pitch"] in {"+16Hz", "+24Hz"}


def test_create_imported_voice_pack_can_use_gpt_sovits_backend(tmp_path: Path):
    sample = tmp_path / "voice.wav"
    with wave.open(str(sample), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(16000)
        wav.writeframes(b"\x00\x00" * 1600)

    manifest = create_imported_voice_pack(
        display_name="clone",
        language_id="zh-CN",
        sample_paths=[sample],
        base_dir=tmp_path / "packs",
        clone_backend="gpt-sovits",
        prompt_text="hello",
        gpt_sovits_api_url="http://127.0.0.1:9880",
    )

    default_profile = manifest["voice_profiles"]["default"]
    clone_backend = manifest["clone_backend"]

    assert default_profile["provider"] == "gpt-sovits"
    assert default_profile["gpt_sovits"]["ref_audio_path"] == manifest["samples"][0]
    assert default_profile["gpt_sovits"]["prompt_text"] == "hello"
    assert default_profile["gpt_sovits"]["text_lang"] == "zh"
    assert clone_backend["provider"] == "gpt-sovits"
    assert clone_backend["mode"] == "zero_shot_reference"


def test_voice_pack_language_preset_supports_common_european_languages():
    french = voice_pack_module.voice_pack_language_preset("fr-FR")
    german = voice_pack_module.voice_pack_language_preset("de-DE")
    spanish = voice_pack_module.voice_pack_language_preset("es-ES")

    assert french["edge_voice"] == "fr-FR-DeniseNeural"
    assert german["edge_voice"] == "de-DE-KatjaNeural"
    assert spanish["edge_voice"] == "es-ES-ElviraNeural"


def test_create_imported_voice_pack_converts_mp4_to_mp3(tmp_path: Path, monkeypatch):
    source = tmp_path / "clip.mp4"
    source.write_bytes(b"fake-video")

    def fake_convert(_src: Path, dest: Path) -> None:
        dest.write_bytes(b"fake-mp3")

    monkeypatch.setattr(voice_pack_module, "_convert_mp4_to_mp3", fake_convert)

    manifest = voice_pack_module.create_imported_voice_pack(
        display_name="小林音色",
        language_id="zh-HK",
        sample_paths=[source],
        base_dir=tmp_path / "packs",
    )
    pack_dir = tmp_path / "packs" / manifest["id"]
    converted = pack_dir / manifest["samples"][0]
    original = pack_dir / manifest["source_media"][0]

    assert manifest["display_name"] == "粤语小林音色"
    assert manifest["conversions"][0]["kind"] == "mp4_to_mp3"
    assert converted.suffix == ".mp3"
    assert converted.read_bytes() == b"fake-mp3"
    assert original.suffix == ".mp4"
    assert original.read_bytes() == b"fake-video"
    assert manifest["analysis"]["formats"] == ["mp3"]


def test_voice_pack_reference_sample_prefers_imported_audio(tmp_path: Path):
    base_dir = tmp_path / "packs"
    pack_dir = base_dir / "custom"
    sample_dir = pack_dir / "samples"
    sample_dir.mkdir(parents=True)
    wav_sample = sample_dir / "voice.wav"
    wav_sample.write_bytes(b"fake-wav")
    (pack_dir / "voice_pack.json").write_text(
        json.dumps(
            {
                "id": "custom",
                "samples": ["samples/voice.wav"],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    manager = VoicePackManager(pack_id="custom", base_dir=base_dir, enabled=True)

    assert manager.reference_sample() == wav_sample


def test_voice_profile_event_settings_inherit_default_profile():
    with tempfile.TemporaryDirectory() as tmpdir:
        base_dir = Path(tmpdir) / "packs"
        pack_dir = base_dir / "cat"
        pack_dir.mkdir(parents=True)
        (pack_dir / "voice_pack.json").write_text(
            json.dumps(
                {
                    "voice_profiles": {
                        "default": {
                            "edge_voice": "zh-CN-XiaomoNeural",
                            "edge_rate": "-4%",
                            "edge_pitch": "-8Hz",
                            "cute_style": False,
                        },
                        "happy.speak": {
                            "edge_rate": "+2%",
                        },
                    }
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        manager = TTSManager(
            enabled=False,
            voice_pack_id="cat",
            voice_pack_dir=str(base_dir),
            voice_pack_enabled=True,
        )
        settings = manager._voice_settings(pet_id="cat", state="happy", action="speak")

        assert settings["edge_voice"] == "zh-CN-XiaomoNeural"
        assert settings["edge_rate"] == "+2%"
        assert settings["edge_pitch"] == "-8Hz"
        assert settings["cute_style"] is False


def test_tts_manager_can_override_voice_pack_without_changing_pet_id():
    with tempfile.TemporaryDirectory() as tmpdir:
        base_dir = Path(tmpdir) / "packs"
        pack_dir = base_dir / "sweet"
        pack_dir.mkdir(parents=True)
        (pack_dir / "voice_pack.json").write_text(
            json.dumps(
                {
                    "voice_profiles": {
                        "default": {
                            "edge_voice": "zh-CN-XiaoyiNeural",
                            "edge_rate": "+14%",
                            "edge_pitch": "+22Hz",
                            "cute_style": True,
                        }
                    }
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        manager = TTSManager(
            enabled=False,
            voice_pack_dir=str(base_dir),
            voice_pack_enabled=True,
        )
        manager.set_voice_pack_id("sweet")
        settings = manager._voice_settings(pet_id="mao_pro_zh", state="neutral", action="speak")

        assert settings["edge_voice"] == "zh-CN-XiaoyiNeural"
        assert settings["edge_rate"] == "+14%"
        assert settings["edge_pitch"] == "+22Hz"


def test_tts_runtime_settings_override_voice_pack_profile():
    with tempfile.TemporaryDirectory() as tmpdir:
        base_dir = Path(tmpdir) / "packs"
        pack_dir = base_dir / "cat"
        pack_dir.mkdir(parents=True)
        (pack_dir / "voice_pack.json").write_text(
            json.dumps(
                {
                    "voice_profiles": {
                        "default": {
                            "edge_voice": "zh-CN-XiaomoNeural",
                            "edge_rate": "-4%",
                            "edge_pitch": "-8Hz",
                        }
                    }
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        manager = TTSManager(
            enabled=False,
            voice_pack_id="cat",
            voice_pack_dir=str(base_dir),
            voice_pack_enabled=True,
        )
        manager.apply_runtime_settings(
            {
                "enabled": True,
                "provider": "edge",
                "edge_voice": "en-US-JennyNeural",
                "voice_profile": "cute",
                "cute_style": True,
            }
        )
        settings = manager._voice_settings(pet_id="cat", state="neutral", action="speak")

        assert manager.enabled is True
        assert manager._provider_order()[0] == "edge"
        assert settings["edge_voice"] == "en-US-JennyNeural"
        assert settings["edge_rate"] == "-4%"
        assert manager.voice_profile == "cute"


def test_tts_cute_suffix_stays_chinese_only_for_english_voice():
    manager = TTSManager(enabled=False, voice_profile="playful", cute_style=True)

    spoken = manager._prepare_spoken_text(
        "Hello there.",
        cute_style=True,
        voice_profile="playful",
        edge_voice="en-US-JennyNeural",
    )

    assert spoken == "Hello there."


def test_tts_emotion_style_auto_follows_voice_state_without_overriding_pack():
    with tempfile.TemporaryDirectory() as tmpdir:
        base_dir = Path(tmpdir) / "packs"
        pack_dir = base_dir / "cat"
        pack_dir.mkdir(parents=True)
        (pack_dir / "voice_pack.json").write_text(
            json.dumps(
                {
                    "voice_profiles": {
                        "happy.speak": {
                            "edge_rate": "+7%",
                            "edge_pitch": "+9Hz",
                        }
                    }
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        manager = TTSManager(
            enabled=False,
            voice_pack_id="cat",
            voice_pack_dir=str(base_dir),
            voice_pack_enabled=True,
        )
        manager.apply_runtime_settings({"emotion_style": "auto"})
        settings = manager._voice_settings(pet_id="cat", state="happy", action="speak")

        assert settings["edge_rate"] == "+7%"
        assert settings["edge_pitch"] == "+9Hz"


def test_tts_selected_emotion_style_overrides_pack_profile():
    with tempfile.TemporaryDirectory() as tmpdir:
        base_dir = Path(tmpdir) / "packs"
        pack_dir = base_dir / "cat"
        pack_dir.mkdir(parents=True)
        (pack_dir / "voice_pack.json").write_text(
            json.dumps(
                {
                    "voice_profiles": {
                        "default": {
                            "edge_rate": "+1%",
                            "edge_pitch": "+1Hz",
                        }
                    }
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        manager = TTSManager(
            enabled=False,
            voice_pack_id="cat",
            voice_pack_dir=str(base_dir),
            voice_pack_enabled=True,
        )
        manager.apply_runtime_settings({"emotion_style": "comfort"})
        settings = manager._voice_settings(pet_id="cat", state="happy", action="speak")

        assert settings["edge_rate"] == "-10%"
        assert settings["edge_pitch"] == "-4Hz"
        assert settings["cute_style"] is False


def test_team_c_uses_pet_state_for_voice_feedback():
    tts = RecordingTTS()
    assistant = AIChatVoiceAssistant(
        llm_client=FakeLLM(),
        tts_manager=tts,
        memory=ChatMemory(max_rounds=2),
        auto_tts=True,
        stream_delay=0,
        pet_id="cat",
    )

    assistant.chat_with_context("陪我一下", current_state={"mood": "sad", "energy": 18})

    assert tts.calls[-1]["pet_id"] == "cat"
    assert tts.calls[-1]["state"] == "sad"
    assert tts.calls[-1]["action"] == "speak"


def test_team_c_pet_id_can_follow_active_desktop_pet():
    tts = RecordingTTS()
    assistant = AIChatVoiceAssistant(
        llm_client=FakeLLM(),
        tts_manager=tts,
        memory=ChatMemory(max_rounds=2),
        auto_tts=True,
        stream_delay=0,
        pet_id="cat",
    )
    interface = EchoTeamCInterface(assistant)

    interface.api_set_pet_id("zhegou")
    thread = interface.api_user_speak("你好", {"mood": "happy"}, lambda chunk: None)
    thread.join(timeout=3)

    assert tts.calls[-1]["pet_id"] == "zhegou"
    assert tts.calls[-1]["state"] == "happy"


def test_team_c_can_switch_voice_pack_without_changing_pet_id():
    tts = RecordingTTS()
    assistant = AIChatVoiceAssistant(
        llm_client=FakeLLM(),
        tts_manager=tts,
        memory=ChatMemory(max_rounds=2),
        auto_tts=True,
        stream_delay=0,
        pet_id="cat",
    )
    interface = EchoTeamCInterface(assistant)

    interface.api_set_pet_id("mao_pro_zh")
    interface.api_set_voice_pack_id("custom_voice")
    thread = interface.api_user_speak("你好", {"mood": "happy"}, lambda chunk: None)
    thread.join(timeout=3)

    assert tts.calls[-1]["pet_id"] == "mao_pro_zh"
    assert tts.voice_pack_ids[-1] == "custom_voice"


def test_team_c_can_update_tts_runtime_settings():
    tts = RecordingTTS()
    assistant = AIChatVoiceAssistant(
        llm_client=FakeLLM(),
        tts_manager=tts,
        memory=ChatMemory(max_rounds=2),
        auto_tts=True,
        stream_delay=0,
        pet_id="cat",
    )
    interface = EchoTeamCInterface(assistant)

    interface.api_set_tts_settings(
        {
            "enabled": True,
            "provider": "edge",
            "edge_voice": "en-US-JennyNeural",
            "quality": "neural",
            "emotion_style": "serious",
        }
    )

    assert tts.tts_settings[-1]["provider"] == "edge"
    assert tts.tts_settings[-1]["edge_voice"] == "en-US-JennyNeural"
    assert tts.tts_settings[-1]["emotion_style"] == "serious"


def test_team_c_system_voice_uses_current_voice_context():
    tts = RecordingTTS()
    assistant = AIChatVoiceAssistant(
        llm_client=FakeLLM(),
        tts_manager=tts,
        memory=ChatMemory(max_rounds=2),
        auto_tts=True,
        stream_delay=0,
        pet_id="cat",
    )
    interface = EchoTeamCInterface(assistant)

    interface.api_set_pet_id("mao_pro_zh")
    thread = interface.api_play_system_voice(
        "click feedback",
        current_state={
            "mood": "happy",
            "voice_action": "click",
            "tts_settings": {
                "provider": "edge",
                "edge_voice": "zh-HK-HiuGaaiNeural",
                "emotion_style": "cheerful",
            },
        },
    )
    thread.join(timeout=3)

    assert tts.tts_settings[-1]["edge_voice"] == "zh-HK-HiuGaaiNeural"
    assert tts.calls[-1]["pet_id"] == "mao_pro_zh"
    assert tts.calls[-1]["state"] == "happy"
    assert tts.calls[-1]["action"] == "click"


def test_team_c_adds_response_language_from_english_voice():
    class CapturingLLM:
        def __init__(self):
            self.user_state = None

        def generate(self, text_prompt, user_state=None, history=None):
            self.user_state = dict(user_state or {})
            return "Sure, I am here."

    llm = CapturingLLM()
    assistant = AIChatVoiceAssistant(
        llm_client=llm,
        tts_manager=TTSManager(enabled=False),
        memory=ChatMemory(max_rounds=2),
        auto_tts=False,
        stream_delay=0,
    )
    assistant.set_tts_settings({"provider": "edge", "edge_voice": "en-US-JennyNeural"})

    assistant.chat_with_context("hello", current_state={"state_code": "normal"})

    assert llm.user_state["response_language"] == "en-US"


def test_team_c_displays_foreign_reply_with_line_by_line_chinese_translation():
    class TranslatingLLM:
        def generate(self, text_prompt, user_state=None, history=None):
            return "Hello there.\nHow are you?"

        def translate_to_chinese(self, text, source_language=""):
            return {
                "Hello there.": "你好呀。",
                "How are you?": "你还好吗？",
            }[text]

    tts = RecordingTTS()
    chunks = []
    assistant = AIChatVoiceAssistant(
        llm_client=TranslatingLLM(),
        tts_manager=tts,
        memory=ChatMemory(max_rounds=2),
        auto_tts=True,
        stream_delay=0,
    )
    assistant.set_tts_settings({"provider": "edge", "edge_voice": "en-US-JennyNeural"})

    display = assistant.chat_with_context("hello", current_state={"state_code": "normal"}, callback_ui=chunks.append)

    assert display == "Hello there.\n你好呀。\nHow are you?\n你还好吗？"
    assert "".join(chunks) == display
    assert tts.calls[-1]["text"] == "Hello there.\nHow are you?"
    assert assistant.get_memory_messages()[-1]["content"] == "Hello there.\nHow are you?"


def test_team_c_translates_non_chinese_reply_even_when_voice_language_is_chinese():
    class TranslatingLLM:
        def __init__(self):
            self.source_languages = []

        def generate(self, text_prompt, user_state=None, history=None):
            return "Hello there."

        def translate_to_chinese(self, text, source_language=""):
            self.source_languages.append(source_language)
            return "你好呀。"

    llm = TranslatingLLM()
    assistant = AIChatVoiceAssistant(
        llm_client=llm,
        tts_manager=TTSManager(enabled=False),
        memory=ChatMemory(max_rounds=2),
        auto_tts=False,
        stream_delay=0,
    )

    display = assistant.chat_with_context("hello", current_state={"response_language": "zh-CN"})

    assert display == "你好呀。"
    assert llm.source_languages == ["en-US"]


def test_team_c_speaks_translated_reply_when_chinese_voice_gets_japanese_text():
    class TranslatingLLM:
        def generate(self, text_prompt, user_state=None, history=None):
            return "こんにちは、そばにいるよ。"

        def translate_to_chinese(self, text, source_language=""):
            assert source_language == "ja-JP"
            return "你好呀，我在你身边。"

    tts = RecordingTTS()
    chunks = []
    assistant = AIChatVoiceAssistant(
        llm_client=TranslatingLLM(),
        tts_manager=tts,
        memory=ChatMemory(max_rounds=2),
        auto_tts=True,
        stream_delay=0,
    )
    assistant.set_tts_settings({"provider": "edge", "edge_voice": "zh-CN-XiaomoNeural"})

    display = assistant.chat_with_context("你好", current_state={"state_code": "normal"}, callback_ui=chunks.append)

    assert display == "你好呀，我在你身边。"
    assert "".join(chunks) == display
    assert tts.calls[-1]["text"] == "你好呀，我在你身边。"
    assert assistant.get_memory_messages()[-1]["content"] == "你好呀，我在你身边。"


def test_ai_chat_voice_assistant_uses_friendly_fallback_on_llm_error():
    class BrokenLLM:
        def generate(self, text_prompt, user_state=None, history=None):
            raise RuntimeError("secret api failure")

    tts = RecordingTTS()
    chunks = []
    assistant = AIChatVoiceAssistant(
        llm_client=BrokenLLM(),
        tts_manager=tts,
        memory=ChatMemory(max_rounds=2),
        auto_tts=True,
        stream_delay=0,
    )

    display = assistant.chat_with_context("你好", current_state={"state_code": "normal"}, callback_ui=chunks.append)

    assert "走神" in display
    assert "secret" not in display
    assert "".join(chunks) == display
    assert tts.calls[-1]["text"] == display


def test_team_c_filters_mismatched_history_for_selected_voice_language():
    class CapturingLLM:
        def __init__(self):
            self.history = None

        def generate(self, text_prompt, user_state=None, history=None):
            self.history = list(history or [])
            return "你好呀。"

    memory = ChatMemory(max_rounds=4)
    memory.append_user("你好")
    memory.append_assistant("こんにちは！今日も一緒にいようね。")
    memory.append_user("我想睡觉")
    memory.append_assistant("早点休息呀。")
    llm = CapturingLLM()
    assistant = AIChatVoiceAssistant(
        llm_client=llm,
        tts_manager=TTSManager(enabled=False),
        memory=memory,
        auto_tts=False,
        stream_delay=0,
    )
    assistant.set_tts_settings({"provider": "edge", "edge_voice": "zh-CN-XiaomoNeural"})

    assistant.chat_with_context("你好", current_state={"state_code": "normal"})

    assert llm.history == [
        {"role": "user", "content": "我想睡觉"},
        {"role": "assistant", "content": "早点休息呀。"},
    ]


def test_deepseek_uses_official_chat_url_and_current_default_model():
    client = DeepSeekClient(api_key="sk-test", api_url="https://api.deepseek.com", force_mock=True)

    assert client.api_url == "https://api.deepseek.com/chat/completions"
    assert client.model == "deepseek-v4-flash"


def test_deepseek_mock_does_not_hide_user_text_when_state_is_normal():
    client = DeepSeekClient(api_key="", force_mock=True)

    reply = client.generate("我想聊电影", user_state={"state_code": "normal"})

    assert "我想聊电影" in reply
    assert reply != "我在这儿陪你呀，今天的节奏看起来不错。"


def test_deepseek_mock_answers_affection_instead_of_only_recording_it():
    client = DeepSeekClient(api_key="", force_mock=True)

    reply = client.generate("我喜欢你呀", user_state={"state_code": "normal"})

    assert "记下" not in reply
    assert "喜欢" in reply
    assert "开心" in reply


def test_deepseek_mock_default_reply_is_contextual_not_note_taking():
    client = DeepSeekClient(api_key="", force_mock=True)

    reply = client.generate("今天窗外下雨了", user_state={"state_code": "normal"})

    assert "记下" not in reply
    assert "今天窗外下雨了" in reply


def test_deepseek_mock_gesture_event_does_not_repeat_internal_prompt():
    client = DeepSeekClient(api_key="", force_mock=True)

    reply = client.generate(
        "用户刚做了“挥手”手势。请用桌宠口吻回应一句，短、自然、别解释识别过程。",
        user_state={"event_type": "gesture_event", "gesture_type": "wave"},
    )

    assert "请用桌宠口吻" not in reply
    assert "用户刚做了" not in reply
    assert "看到" in reply


def test_ai_voice_assistant_filters_internal_prompt_before_tts():
    class PromptEchoLLM:
        def generate(self, text_prompt, user_state=None, history=None):
            return "用户刚做了“OK”手势。请用桌宠口吻回应一句，短、自然、别解释识别过程。"

    tts = RecordingTTS()
    assistant = AIChatVoiceAssistant(
        llm_client=PromptEchoLLM(),
        tts_manager=tts,
        memory=ChatMemory(max_rounds=2),
        auto_tts=True,
        stream_delay=0,
    )

    reply = assistant.respond_to_status_event(
        {"event_type": "gesture_event", "gesture_type": "ok", "mood": "happy"}
    )

    assert "请用桌宠口吻" not in reply
    assert "用户刚做了" not in reply
    assert "OK" in reply
    assert tts.calls[-1]["text"] == reply


def test_team_c_proactive_events_use_short_local_reply_and_cooldown():
    tts = RecordingTTS()
    assistant = AIChatVoiceAssistant(
        llm_client=FakeLLM(),
        tts_manager=tts,
        memory=ChatMemory(max_rounds=2),
        auto_tts=True,
        stream_delay=0,
    )

    first = assistant.respond_to_status_event({"event_type": "gesture_event", "gesture_type": "wave"})
    second = assistant.respond_to_status_event({"event_type": "gesture_event", "gesture_type": "wave"})

    assert first
    assert second == ""
    assert "wave" not in first.lower()
    assert len(tts.calls) == 1
    assert tts.calls[-1]["text"] == first


def test_team_c_proactive_policy_waits_during_user_chat():
    policy = ProactiveSpeechPolicy()

    allowed_chat = policy.should_speak({"event_type": "user_chat"}, user_chat_active=True, now=100.0)
    blocked_alert = policy.should_speak(
        {"event_type": "screen_time_reminder", "minutes": 90},
        user_chat_active=True,
        now=100.0,
    )

    assert allowed_chat is True
    assert blocked_alert is False


def test_team_c_local_event_templates_cover_required_event_types():
    assert build_local_event_reply({"event_type": "user_state_alert", "state_code": "tired"})
    assert build_local_event_reply({"event_type": "screen_time_reminder", "minutes": 80})
    assert build_local_event_reply({"event_type": "cloud_room_event", "action_type": "join"})
    assert build_local_event_reply({"event_type": "pet_state_event", "state": "hungry"})


def test_async_tts_queue_returns_immediately_and_shutdowns():
    class SlowManager:
        def __init__(self):
            self.started = threading.Event()
            self.release = threading.Event()
            self.calls = []

        def speak(self, text, pet_id="cat", state="neutral", action="speak"):
            self.started.set()
            self.release.wait(timeout=1)
            self.calls.append((text, pet_id, state, action))

    manager = SlowManager()
    queue = AsyncTTSQueue(manager, maxsize=2)

    assert queue.speak("hello", pet_id="cat", state="happy", action="speak") is True
    assert manager.started.wait(timeout=1)
    assert queue.speak("hello", pet_id="cat", state="happy", action="speak") is False
    manager.release.set()
    queue.shutdown(timeout=1)
    assert manager.calls == [("hello", "cat", "happy", "speak")]


def test_prompt_builder_uses_english_for_english_response_language():
    prompt = build_system_prompt({"response_language": "en-US", "state_code": "normal"})

    assert "natural English conversation" in prompt
    assert "Always answer in natural English" in prompt


def test_prompt_builder_uses_common_language_from_edge_voice():
    prompt = build_system_prompt({"edge_voice": "fr-FR-DeniseNeural", "state_code": "normal"})

    assert "natural French conversation" in prompt
    assert "Always answer in natural French" in prompt


def test_prompt_builder_uses_personalization_without_exposing_field_names():
    prompt = build_system_prompt(
        {
            "state_code": "normal",
            "personalization_settings": {
                "speech_style": {
                    "tone": "毒舌吐槽",
                    "nickname": "小夏",
                    "catchphrase": "我在呢",
                },
                "interaction_frequency": {"proactive_level": 20, "quiet_when_busy": True},
            },
            "user_profile": {
                "relationship": "并肩搭子",
                "comfort_level": 30,
                "recent_emotions": [{"emotion_label": "stress"}],
                "activity_stats": {"chat_count": 3, "care_needed_count": 2},
            },
        }
    )

    assert "小夏" in prompt
    assert "轻微吐槽" in prompt
    assert "我在呢" in prompt
    assert "压力" in prompt
    assert "nickname" not in prompt
    assert "comfort_level" not in prompt


def test_build_proactive_prompt_supports_screen_time_and_cloud_events():
    screen_event = build_screen_time_event(
        95,
        activity_name="长时间工作",
        is_focused=True,
        personalization_settings={
            "interaction_frequency": {"proactive_level": 15, "quiet_when_busy": True},
            "companion_mode": {"focus_silence": True},
        },
    )
    screen_prompt = build_proactive_prompt(screen_event)
    assert "95" in screen_prompt
    assert "极轻" in screen_prompt
    assert "只输出一句话" in screen_prompt

    cloud_prompt = build_proactive_prompt(
        build_cloud_pet_event(
            CloudPetEvent(
                actor_name="阿梨",
                action_type="feed",
                pet_name="小猫",
                level=4,
                exp_gain=12,
                coins_gain=3,
                bond_bonus=2,
            )
        )
    )
    assert "阿梨刚刚喂了小猫" in cloud_prompt
    assert "等级 4" in cloud_prompt
    assert "宠物口吻中文短句" in cloud_prompt


def test_response_language_detects_common_edge_voice_locales():
    assert response_language_from_edge_voice("de-DE-KatjaNeural") == "de-DE"
    assert response_language_from_edge_voice("es-ES-ElviraNeural") == "es-ES"
    assert response_language_from_edge_voice("pt-BR-FranciscaNeural") == "pt-BR"


def test_text_reader_language_detection_matches_voice_families():
    assert detect_text_language("你好，今天一起加油。") == "zh-CN"
    assert detect_text_language("Hello, I am here with you.") == "en-US"
    assert detect_text_language("Bonjour, je suis là avec toi.") == "fr-FR"
    assert detect_text_language("こんにちは、そばにいるよ。") == "ja-JP"
    assert languages_match("en-GB", "en-US")
    assert languages_match("zh-HK", "zh-CN")
    assert not languages_match("en-US", "zh-CN")


def test_text_reader_language_label_and_edge_voice_language():
    language = language_from_edge_voice("ko-KR-SunHiNeural")

    assert language == "ko-KR"
    assert language_label(language) == "韩语"


def test_long_text_reader_imports_multiple_book_formats(tmp_path: Path):
    txt = tmp_path / "story.txt"
    txt.write_text("第一章\n你好，世界。", encoding="utf-8")
    docx = tmp_path / "notes.docx"
    with zipfile.ZipFile(docx, "w") as archive:
        archive.writestr(
            "word/document.xml",
            """<?xml version="1.0" encoding="UTF-8"?>
            <w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
              <w:body><w:p><w:r><w:t>Word 段落内容</w:t></w:r></w:p></w:body>
            </w:document>""",
        )
    epub = tmp_path / "book.epub"
    with zipfile.ZipFile(epub, "w") as archive:
        archive.writestr("OPS/chapter.xhtml", "<html><body><h1>章节</h1><p>EPUB 正文内容</p></body></html>")

    documents = [read_book_file(path) for path in (txt, docx, epub)]
    combined = combine_documents(documents)

    assert "你好，世界" in combined
    assert "Word 段落内容" in combined
    assert "EPUB 正文内容" in combined


def test_team_c_reads_long_text_in_tts_chunks():
    tts = RecordingTTS()
    assistant = AIChatVoiceAssistant(
        llm_client=FakeLLM(),
        tts_manager=tts,
        memory=ChatMemory(max_rounds=2),
        auto_tts=False,
        stream_delay=0,
        pet_id="cat",
    )
    interface = EchoTeamCInterface(assistant)
    text = "第一段很适合朗读。" * 140
    expected_chunks = split_text_for_tts(text, max_chars=700)

    thread = interface.api_read_long_text(text, current_state={"mood": "happy"}, title="测试书")
    thread.join(timeout=3)

    assert len(expected_chunks) > 1
    assert len(tts.calls) == len(expected_chunks)
    assert {call["action"] for call in tts.calls} == {"read"}
    assert {call["state"] for call in tts.calls} == {"happy"}


def test_deepseek_mock_uses_english_for_english_response_language():
    client = DeepSeekClient(api_key="", force_mock=True)

    reply = client.generate("hello", user_state={"response_language": "en-US"})

    assert "I am here" in reply
    assert "在" not in reply


def test_deepseek_mock_uses_french_for_french_response_language():
    client = DeepSeekClient(api_key="", force_mock=True)

    reply = client.generate("bonjour", user_state={"response_language": "fr-FR"})

    assert "Je suis la" in reply
    assert "在" not in reply


def test_deepseek_mock_translates_common_foreign_reply_to_chinese():
    client = DeepSeekClient(api_key="", force_mock=True)

    translation = client.translate_to_chinese(
        "Je suis la. Qu'aimerais-tu que je fasse avec toi aujourd'hui ?",
        source_language="fr-FR",
    )

    assert translation == "我在这里。今天你想让我陪你做点什么？"


def test_team_c_interface_sends_event_dict_callback():
    assistant = build_test_assistant()
    interface = EchoTeamCInterface(assistant)
    done = threading.Event()
    received = {}

    def callback(event_dict):
        received.update(event_dict)
        done.set()

    interface.api_register_logic_callback(callback)
    thread = interface.api_user_speak("继续学习", {"state_code": "focused"}, lambda chunk: None)
    thread.join(timeout=3)

    assert done.wait(0.2)
    assert received["event_type"] == "user_chat"
    assert received["word_count"] == len("收到：继续学习")
    assert received["emotion_result"]["emotion_label"] in {"neutral", "positive", "confused"}
    assert set(received["emotion_result"]) >= {"confidence", "reason", "suggestion", "need_care"}


def test_team_c_emotion_event_can_update_team_d_profile(monkeypatch):
    monkeypatch.setattr(UserProfile, "load", classmethod(lambda cls, filepath=None: cls()))
    monkeypatch.setattr(UserProfile, "save", lambda self, filepath=None: None)
    assistant = build_test_assistant()
    interface = EchoTeamCInterface(assistant)
    pet_state = PetState(mood="neutral", energy=80, intimacy=50)
    team_d = EchoTeamDInterface(pet_state)
    done = threading.Event()

    def callback(event_dict):
        team_d.api_update_from_chat_emotion(event_dict)
        done.set()

    interface.api_register_logic_callback(callback)
    thread = interface.api_user_speak("我压力好大，真的有点撑不住", {"state_code": "normal"}, lambda chunk: None)
    thread.join(timeout=3)

    assert done.wait(0.2)
    assert team_d.user_profile.recent_emotions[-1]["emotion_label"] == "stress"
    assert pet_state.mood == "sad"
    assert pet_state.energy < 80


def test_team_c_interface_compat_word_count_callback():
    assistant = build_test_assistant()
    interface = EchoTeamCInterface(assistant)
    done = threading.Event()
    received = []

    def api_on_chat_finished(word_count: int):
        received.append(word_count)
        done.set()

    interface.api_register_logic_callback(api_on_chat_finished)
    thread = interface.api_user_speak("休息一下", {"state_code": "tired"}, lambda chunk: None)
    thread.join(timeout=3)

    assert done.wait(0.2)
    assert received == [len("收到：休息一下")]


def test_team_c_can_bind_real_team_d_chat_finished_api():
    assistant = build_test_assistant()
    interface = EchoTeamCInterface(assistant)
    pet_state = PetState(mood="neutral", energy=100, intimacy=50)
    team_d = EchoTeamDInterface(pet_state)

    interface.api_register_logic_callback(team_d.api_on_chat_finished)
    thread = interface.api_user_speak("今天状态不错", {"state_code": "normal"}, lambda chunk: None)
    thread.join(timeout=3)

    assert pet_state.energy < 100
    assert pet_state.intimacy > 50
    assert pet_state.mood == "happy"


def test_team_d_status_listener_emits_one_user_state_alert():
    pet_state = PetState(mood="neutral", energy=80, intimacy=50)
    team_d = EchoTeamDInterface(pet_state)
    done = threading.Event()
    received = []

    def callback(event_dict):
        received.append(event_dict)
        done.set()

    team_d.api_register_status_listener(callback)
    team_d.api_apply_user_state(
        {
            "state_code": "tired",
            "confidence": 0.9,
            "duration": 12,
            "need_response": True,
            "suggestion": "提醒用户休息一下",
        }
    )

    assert done.wait(0.5)
    assert len(received) == 1
    assert received[0]["event_type"] == "user_state_alert"
    assert received[0]["mood"] == "sad"
    assert received[0]["action"] == "sad"
