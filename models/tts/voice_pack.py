from __future__ import annotations

import hashlib
import json
import math
import random
import re
import shutil
import struct
import subprocess
import tempfile
import time
import wave
from pathlib import Path
from typing import Any

from models.tts.gpt_sovits import build_voice_pack_backend


AUDIO_SAMPLE_EXTENSIONS = (".wav", ".mp3", ".m4a", ".flac", ".ogg", ".aac", ".wma")
VIDEO_SAMPLE_EXTENSIONS = (".mp4",)
IMPORT_SAMPLE_EXTENSIONS = AUDIO_SAMPLE_EXTENSIONS + VIDEO_SAMPLE_EXTENSIONS

VOICE_PACK_LANGUAGE_PRESETS: tuple[dict[str, Any], ...] = (
    {
        "id": "zh-CN",
        "label": "中文",
        "edge_voice": "zh-CN-XiaoyiNeural",
        "edge_rate": "+8%",
        "edge_pitch": "+12Hz",
        "edge_volume": "+6%",
        "voice_profile": "cute",
        "cute_style": True,
        "sample_text": "你好呀，今天也一起加油。",
    },
    {
        "id": "zh-HK",
        "label": "粤语",
        "edge_voice": "zh-HK-HiuGaaiNeural",
        "edge_rate": "+4%",
        "edge_pitch": "+8Hz",
        "edge_volume": "+6%",
        "voice_profile": "default",
        "cute_style": True,
        "sample_text": "你好呀，我会陪住你。",
    },
    {
        "id": "en-US",
        "label": "英语（美音）",
        "edge_voice": "en-US-JennyNeural",
        "edge_rate": "+0%",
        "edge_pitch": "+2Hz",
        "edge_volume": "+4%",
        "voice_profile": "default",
        "cute_style": False,
        "sample_text": "Hi, I am here with you.",
    },
    {
        "id": "en-GB",
        "label": "英语（英音）",
        "edge_voice": "en-GB-SoniaNeural",
        "edge_rate": "+0%",
        "edge_pitch": "+2Hz",
        "edge_volume": "+4%",
        "voice_profile": "default",
        "cute_style": False,
        "sample_text": "Hello, I am right here with you.",
    },
    {
        "id": "fr-FR",
        "label": "法语",
        "edge_voice": "fr-FR-DeniseNeural",
        "edge_rate": "+0%",
        "edge_pitch": "+2Hz",
        "edge_volume": "+4%",
        "voice_profile": "default",
        "cute_style": False,
        "sample_text": "Bonjour, je suis là avec toi.",
    },
    {
        "id": "de-DE",
        "label": "德语",
        "edge_voice": "de-DE-KatjaNeural",
        "edge_rate": "+0%",
        "edge_pitch": "+0Hz",
        "edge_volume": "+4%",
        "voice_profile": "default",
        "cute_style": False,
        "sample_text": "Hallo, ich bin bei dir.",
    },
    {
        "id": "es-ES",
        "label": "西班牙语",
        "edge_voice": "es-ES-ElviraNeural",
        "edge_rate": "+0%",
        "edge_pitch": "+2Hz",
        "edge_volume": "+4%",
        "voice_profile": "default",
        "cute_style": False,
        "sample_text": "Hola, estoy aquí contigo.",
    },
    {
        "id": "es-MX",
        "label": "西班牙语（墨西哥）",
        "edge_voice": "es-MX-DaliaNeural",
        "edge_rate": "+0%",
        "edge_pitch": "+2Hz",
        "edge_volume": "+4%",
        "voice_profile": "default",
        "cute_style": False,
        "sample_text": "Hola, estoy aquí contigo.",
    },
    {
        "id": "it-IT",
        "label": "意大利语",
        "edge_voice": "it-IT-ElsaNeural",
        "edge_rate": "+0%",
        "edge_pitch": "+2Hz",
        "edge_volume": "+4%",
        "voice_profile": "default",
        "cute_style": False,
        "sample_text": "Ciao, sono qui con te.",
    },
    {
        "id": "pt-BR",
        "label": "葡萄牙语（巴西）",
        "edge_voice": "pt-BR-FranciscaNeural",
        "edge_rate": "+0%",
        "edge_pitch": "+2Hz",
        "edge_volume": "+4%",
        "voice_profile": "default",
        "cute_style": False,
        "sample_text": "Olá, estou aqui com você.",
    },
    {
        "id": "ru-RU",
        "label": "俄语",
        "edge_voice": "ru-RU-SvetlanaNeural",
        "edge_rate": "+0%",
        "edge_pitch": "+0Hz",
        "edge_volume": "+4%",
        "voice_profile": "default",
        "cute_style": False,
        "sample_text": "Привет, я рядом с тобой.",
    },
    {
        "id": "nl-NL",
        "label": "荷兰语",
        "edge_voice": "nl-NL-ColetteNeural",
        "edge_rate": "+0%",
        "edge_pitch": "+2Hz",
        "edge_volume": "+4%",
        "voice_profile": "default",
        "cute_style": False,
        "sample_text": "Hallo, ik ben hier bij je.",
    },
    {
        "id": "hi-IN",
        "label": "印地语",
        "edge_voice": "hi-IN-SwaraNeural",
        "edge_rate": "+0%",
        "edge_pitch": "+2Hz",
        "edge_volume": "+4%",
        "voice_profile": "default",
        "cute_style": False,
        "sample_text": "नमस्ते, मैं तुम्हारे साथ हूँ।",
    },
    {
        "id": "ar-EG",
        "label": "阿拉伯语",
        "edge_voice": "ar-EG-SalmaNeural",
        "edge_rate": "+0%",
        "edge_pitch": "+0Hz",
        "edge_volume": "+4%",
        "voice_profile": "default",
        "cute_style": False,
        "sample_text": "مرحبا، أنا هنا معك.",
    },
    {
        "id": "ko-KR",
        "label": "韩语",
        "edge_voice": "ko-KR-SunHiNeural",
        "edge_rate": "+0%",
        "edge_pitch": "+4Hz",
        "edge_volume": "+4%",
        "voice_profile": "default",
        "cute_style": False,
        "sample_text": "안녕하세요, 곁에 있을게요.",
    },
    {
        "id": "ja-JP",
        "label": "日语",
        "edge_voice": "ja-JP-NanamiNeural",
        "edge_rate": "+0%",
        "edge_pitch": "+4Hz",
        "edge_volume": "+4%",
        "voice_profile": "default",
        "cute_style": False,
        "sample_text": "こんにちは、そばにいるよ。",
    },
)


def voice_pack_language_preset(language_id: str) -> dict[str, Any]:
    target = str(language_id or "").strip()
    for preset in VOICE_PACK_LANGUAGE_PRESETS:
        if preset["id"] == target:
            return dict(preset)
    return dict(VOICE_PACK_LANGUAGE_PRESETS[0])


def create_imported_voice_pack(
    display_name: str,
    language_id: str,
    sample_paths: list[str | Path],
    base_dir: str | Path = "assets/voice_packs",
    clone_backend: str | None = None,
    prompt_text: str = "",
    gpt_sovits_api_url: str = "",
) -> dict[str, Any]:
    name = str(display_name or "").strip()
    if not name:
        raise ValueError("语音包名称不能为空")

    samples = _valid_sample_paths(sample_paths)
    if not samples:
        raise ValueError("请选择至少一个可用的音频文件")

    preset = voice_pack_language_preset(language_id)
    display_name_with_language = f"{preset['label']}{name}"
    base_path = Path(base_dir)
    base_path.mkdir(parents=True, exist_ok=True)
    pack_id = _unique_pack_id(f"{preset['id']}_{name}", base_path)
    pack_dir = base_path / pack_id
    sample_dir = pack_dir / "samples"
    source_media_dir = pack_dir / "source_media"
    copied: list[str] = []
    source_media: list[str] = []
    conversions: list[dict[str, str]] = []

    try:
        sample_dir.mkdir(parents=True, exist_ok=False)
        for index, src in enumerate(samples, start=1):
            if src.suffix.lower() in VIDEO_SAMPLE_EXTENSIONS:
                source_media_dir.mkdir(parents=True, exist_ok=True)
                source_name = _unique_sample_filename(source_media_dir, src, index)
                source_dest = source_media_dir / source_name
                shutil.copy2(src, source_dest)
                source_rel = source_dest.relative_to(pack_dir).as_posix()
                source_media.append(source_rel)

                converted_name = _unique_sample_filename(sample_dir, src.with_suffix(".mp3"), index)
                converted_dest = sample_dir / converted_name
                _convert_mp4_to_mp3(source_dest, converted_dest)
                converted_rel = converted_dest.relative_to(pack_dir).as_posix()
                copied.append(converted_rel)
                conversions.append(
                    {
                        "source": source_rel,
                        "sample": converted_rel,
                        "kind": "mp4_to_mp3",
                    }
                )
                continue

            dest_name = _unique_sample_filename(sample_dir, src, index)
            dest = sample_dir / dest_name
            shutil.copy2(src, dest)
            copied.append(dest.relative_to(pack_dir).as_posix())

        copied_paths = [pack_dir / rel for rel in copied]
        analysis = analyze_audio_samples(copied_paths)
        noise_reduction = create_conservative_noise_reduced_samples(copied_paths, pack_dir)
        profile = _profile_from_audio_features(preset, analysis)
        clone_backend_id = _normalize_clone_backend(clone_backend)
        clone_config: dict[str, Any] = {}
        if clone_backend_id == "gpt-sovits":
            clone_config = build_voice_pack_backend(
                sample_paths=copied,
                language_id=str(preset["id"]),
                prompt_text=prompt_text,
                api_url=gpt_sovits_api_url,
            )
            profile.update(
                {
                    "provider": "gpt-sovits",
                    "gpt_sovits": clone_config,
                }
            )
        manifest: dict[str, Any] = {
            "id": pack_id,
            "display_name": display_name_with_language,
            "user_name": name,
            "icon": "🎙️",
            "description": (
                f"本地导入的语音样本（样本语言：{preset['label']}）；"
                "系统已读取样本信息并生成近似 TTS 音色参数。"
            ),
            "sample_text": preset["sample_text"],
            "language": {
                "id": preset["id"],
                "label": preset["label"],
            },
            "is_custom": True,
            "source": "ui_import",
            "created_at": int(time.time()),
            "samples": copied,
            "source_media": source_media,
            "conversions": conversions,
            "analysis": analysis,
            "noise_reduction": noise_reduction,
            "clone_backend": _voice_pack_clone_backend_manifest(clone_config),
            "simulation": {
                "mode": "gpt_sovits_zero_shot" if clone_config else "audio_feature_profile",
                "note": "当前版本会按样本音高、响度和语音密度微调底层 TTS 参数；如启用 OpenVoice，可再进行可选声纹后处理。",
            },
            "voice_profiles": {
                "default": profile,
                "happy.speak": {
                    "edge_rate": "+12%" if preset["id"].startswith("zh") else "+6%",
                    "edge_pitch": "+16Hz" if preset["id"].startswith("zh") else "+8Hz",
                },
                "sad.speak": {
                    "edge_rate": "-6%",
                    "edge_pitch": "+0Hz",
                },
            },
        }
        (pack_dir / "voice_pack.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return manifest
    except Exception:
        if pack_dir.exists():
            shutil.rmtree(pack_dir, ignore_errors=True)
        raise


def delete_voice_pack(pack_id: str, base_dir: str | Path = "assets/voice_packs") -> bool:
    """Delete one local voice pack directory after validating its boundary."""
    pid = str(pack_id or "").strip()
    if not pid:
        raise ValueError("语音包 ID 不能为空")

    base_path = Path(base_dir).resolve()
    pack_dir = (base_path / pid).resolve()
    try:
        pack_dir.relative_to(base_path)
    except ValueError as exc:
        raise ValueError("语音包路径不在语音包目录内") from exc
    if pack_dir == base_path:
        raise ValueError("语音包路径无效")
    if not pack_dir.exists():
        return False
    if not pack_dir.is_dir() or not (pack_dir / "voice_pack.json").is_file():
        raise ValueError("目标不是有效的语音包目录")

    shutil.rmtree(pack_dir)
    return True


def analyze_audio_samples(paths: list[str | Path]) -> dict[str, Any]:
    formats: set[str] = set()
    sample_rates: set[int] = set()
    channels: set[int] = set()
    total_size = 0
    total_duration = 0.0
    duration_count = 0
    feature_rows: list[dict[str, Any]] = []

    with tempfile.TemporaryDirectory(prefix="voice_pack_analysis_") as tmpdir:
        tmp_root = Path(tmpdir)
        for index, raw in enumerate(paths, start=1):
            path = Path(raw)
            if not path.exists() or not path.is_file():
                continue
            suffix = path.suffix.lower().lstrip(".")
            if suffix:
                formats.add(suffix)
            try:
                total_size += path.stat().st_size
            except OSError:
                pass

            analysis_path = path
            if path.suffix.lower() != ".wav":
                converted = _convert_audio_to_analysis_wav(path, tmp_root / f"sample_{index:02d}.wav")
                if converted is None:
                    continue
                analysis_path = converted

            try:
                features = _analyze_wav_features(analysis_path)
            except (OSError, wave.Error, ValueError, struct.error):
                continue
            duration = float(features.get("duration_seconds") or 0.0)
            rate = int(features.get("sample_rate") or 0)
            channel_count = int(features.get("channels") or 0)
            if duration > 0:
                total_duration += duration
                duration_count += 1
            if rate > 0:
                sample_rates.add(rate)
            if channel_count > 0:
                channels.add(channel_count)
            feature_rows.append(features)

    analysis: dict[str, Any] = {
        "sample_count": len([Path(p) for p in paths if Path(p).exists()]),
        "formats": sorted(formats),
        "total_size_bytes": total_size,
    }
    if duration_count:
        analysis["known_duration_seconds"] = round(total_duration, 2)
        analysis["average_duration_seconds"] = round(total_duration / duration_count, 2)
    if sample_rates:
        analysis["sample_rates"] = sorted(sample_rates)
    if channels:
        analysis["channels"] = sorted(channels)
    if feature_rows:
        analysis["voice_features"] = _summarize_voice_features(feature_rows)
    return analysis


def _convert_audio_to_analysis_wav(src: Path, dest: Path) -> Path | None:
    ffmpeg = _find_ffmpeg()
    if not ffmpeg:
        return None
    dest.parent.mkdir(parents=True, exist_ok=True)
    command = [
        ffmpeg,
        "-y",
        "-i",
        str(src),
        "-vn",
        "-ac",
        "1",
        "-ar",
        "16000",
        "-sample_fmt",
        "s16",
        str(dest),
    ]
    try:
        result = subprocess.run(
            command,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
    except OSError:
        return None
    if result.returncode != 0 or not dest.exists() or dest.stat().st_size <= 0:
        return None
    return dest


def _analyze_wav_features(path: Path) -> dict[str, Any]:
    with wave.open(str(path), "rb") as wav:
        rate = int(wav.getframerate() or 0)
        frame_count = int(wav.getnframes() or 0)
        channel_count = int(wav.getnchannels() or 0)
        sample_width = int(wav.getsampwidth() or 0)
        if rate <= 0 or frame_count <= 0 or channel_count <= 0 or sample_width <= 0:
            raise ValueError("invalid wav metadata")
        read_frames = min(frame_count, rate * 45)
        frames = wav.readframes(read_frames)

    decoded = _decode_pcm_samples(frames, sample_width)
    if channel_count > 1:
        decoded = _downmix_interleaved_samples(decoded, channel_count)
    if not decoded:
        raise ValueError("empty wav samples")

    limit = float(_pcm_peak_value(sample_width))
    normalized = [max(-1.0, min(1.0, sample / limit)) for sample in decoded]
    rms = math.sqrt(sum(sample * sample for sample in normalized) / len(normalized))
    peak = max(abs(sample) for sample in normalized)
    silence_threshold = max(0.012, min(0.05, rms * 0.55))
    silence_ratio = sum(1 for sample in normalized if abs(sample) <= silence_threshold) / len(normalized)
    pitch_hz = _estimate_pitch_hz(normalized, rate)

    return {
        "sample_rate": rate,
        "channels": channel_count,
        "duration_seconds": frame_count / rate,
        "analyzed_seconds": len(decoded) / rate,
        "rms": rms,
        "peak": peak,
        "silence_ratio": silence_ratio,
        "estimated_pitch_hz": pitch_hz,
    }


def _summarize_voice_features(rows: list[dict[str, Any]]) -> dict[str, Any]:
    def average(key: str) -> float | None:
        values = [float(row[key]) for row in rows if row.get(key) is not None]
        if not values:
            return None
        return sum(values) / len(values)

    def median(key: str) -> float | None:
        values = sorted(float(row[key]) for row in rows if row.get(key) is not None)
        if not values:
            return None
        mid = len(values) // 2
        if len(values) % 2:
            return values[mid]
        return (values[mid - 1] + values[mid]) / 2

    summary: dict[str, Any] = {
        "duration_seconds": round(sum(float(row.get("duration_seconds") or 0.0) for row in rows), 2),
        "average_rms": round(average("rms") or 0.0, 4),
        "average_peak": round(average("peak") or 0.0, 4),
        "silence_ratio": round(average("silence_ratio") or 0.0, 3),
        "analyzed_sample_count": len(rows),
    }
    pitch = median("estimated_pitch_hz")
    if pitch:
        summary["estimated_pitch_hz"] = round(pitch, 1)
    return summary


def _profile_from_audio_features(preset: dict[str, Any], analysis: dict[str, Any]) -> dict[str, Any]:
    profile = {
        "edge_voice": preset["edge_voice"],
        "edge_rate": preset["edge_rate"],
        "edge_pitch": preset["edge_pitch"],
        "edge_volume": preset["edge_volume"],
        "voice_profile": preset["voice_profile"],
        "cute_style": bool(preset["cute_style"]),
    }
    features = analysis.get("voice_features") if isinstance(analysis.get("voice_features"), dict) else {}
    if not features:
        return profile

    language_id = str(preset.get("id") or "")
    pitch = _float_or_none(features.get("estimated_pitch_hz"))
    if pitch:
        profile["edge_voice"] = _choose_edge_voice_for_pitch(language_id, pitch, str(profile["edge_voice"]))
        profile["edge_pitch"] = _edge_pitch_for_pitch(pitch)
        if pitch >= 185 and language_id.startswith("zh"):
            profile["voice_profile"] = "cute"
            profile["cute_style"] = True
        elif pitch <= 145:
            profile["voice_profile"] = "default"
            profile["cute_style"] = False

    silence_ratio = _float_or_none(features.get("silence_ratio"))
    if silence_ratio is not None:
        if silence_ratio >= 0.58:
            profile["edge_rate"] = "-8%"
        elif silence_ratio <= 0.22:
            profile["edge_rate"] = "+8%"

    rms = _float_or_none(features.get("average_rms"))
    if rms is not None:
        if rms < 0.035:
            profile["edge_volume"] = "+12%"
        elif rms > 0.18:
            profile["edge_volume"] = "-2%"
        else:
            profile["edge_volume"] = "+4%"

    profile["fit_source"] = "audio_features"
    profile["fit_confidence"] = "medium" if pitch else "low"
    return profile


def _choose_edge_voice_for_pitch(language_id: str, pitch_hz: float, fallback: str) -> str:
    language = str(language_id or "").strip()
    low = pitch_hz < 155
    mid = 155 <= pitch_hz < 195
    voice_options: dict[str, tuple[str, str, str]] = {
        "zh-CN": ("zh-CN-YunxiNeural", "zh-CN-XiaomoNeural", "zh-CN-XiaoyiNeural"),
        "zh-HK": ("zh-HK-WanLungNeural", "zh-HK-HiuMaanNeural", "zh-HK-HiuGaaiNeural"),
        "zh-TW": ("zh-TW-YunJheNeural", "zh-TW-HsiaoChenNeural", "zh-TW-HsiaoYuNeural"),
        "en-US": ("en-US-GuyNeural", "en-US-AriaNeural", "en-US-JennyNeural"),
        "en-GB": ("en-GB-RyanNeural", "en-GB-SoniaNeural", "en-GB-SoniaNeural"),
        "ja-JP": ("ja-JP-KeitaNeural", "ja-JP-NanamiNeural", "ja-JP-NanamiNeural"),
        "ko-KR": ("ko-KR-InJoonNeural", "ko-KR-SunHiNeural", "ko-KR-SunHiNeural"),
    }
    options = voice_options.get(language)
    if not options:
        family = language.split("-", 1)[0].lower()
        options = next((value for key, value in voice_options.items() if key.lower().startswith(family)), None)
    if not options:
        return fallback
    if low:
        return options[0]
    if mid:
        return options[1]
    return options[2]


def _edge_pitch_for_pitch(pitch_hz: float) -> str:
    if pitch_hz < 115:
        value = -18
    elif pitch_hz < 145:
        value = -10
    elif pitch_hz < 175:
        value = -2
    elif pitch_hz < 215:
        value = +8
    elif pitch_hz < 255:
        value = +16
    else:
        value = +24
    return f"{value:+d}Hz"


def _float_or_none(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _downmix_interleaved_samples(samples: list[int], channels: int) -> list[int]:
    if channels <= 1:
        return samples
    frames: list[int] = []
    usable = len(samples) - (len(samples) % channels)
    for index in range(0, usable, channels):
        frames.append(round(sum(samples[index : index + channels]) / channels))
    return frames


def _pcm_peak_value(sample_width: int) -> int:
    if sample_width == 1:
        return 128
    return (1 << (sample_width * 8 - 1)) - 1


def _estimate_pitch_hz(samples: list[float], sample_rate: int) -> float | None:
    if sample_rate <= 0 or len(samples) < sample_rate // 5:
        return None
    max_samples = min(len(samples), sample_rate * 4)
    data = samples[:max_samples]
    frame_size = max(512, min(2048, int(sample_rate * 0.04)))
    hop = max(256, int(sample_rate * 0.02))
    min_lag = max(1, int(sample_rate / 420))
    max_lag = min(frame_size - 1, int(sample_rate / 70))
    if max_lag <= min_lag:
        return None

    pitches: list[float] = []
    for start in range(0, len(data) - frame_size, hop):
        frame = data[start : start + frame_size]
        energy = sum(sample * sample for sample in frame) / len(frame)
        if energy < 0.00035:
            continue
        mean = sum(frame) / len(frame)
        centered = [sample - mean for sample in frame]
        base = sum(sample * sample for sample in centered)
        if base <= 0:
            continue
        best_lag = 0
        best_score = 0.0
        for lag in range(min_lag, max_lag + 1):
            score = 0.0
            limit = frame_size - lag
            for index in range(limit):
                score += centered[index] * centered[index + lag]
            if score > best_score:
                best_score = score
                best_lag = lag
        if not best_lag:
            continue
        confidence = best_score / base
        if confidence >= 0.24:
            pitches.append(sample_rate / best_lag)

    if not pitches:
        return None
    pitches.sort()
    mid = len(pitches) // 2
    if len(pitches) % 2:
        return pitches[mid]
    return (pitches[mid - 1] + pitches[mid]) / 2


def _convert_mp4_to_mp3(src: Path, dest: Path) -> None:
    ffmpeg = _find_ffmpeg()
    if not ffmpeg:
        raise RuntimeError("导入 .mp4 需要 ffmpeg 才能抽取音轨并转为 .mp3，请先安装 ffmpeg 或改用音频文件。")

    dest.parent.mkdir(parents=True, exist_ok=True)
    command = [
        ffmpeg,
        "-y",
        "-i",
        str(src),
        "-vn",
        "-codec:a",
        "libmp3lame",
        "-q:a",
        "2",
        str(dest),
    ]
    try:
        result = subprocess.run(
            command,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
    except OSError as exc:
        raise RuntimeError(f"ffmpeg 启动失败：{exc}") from exc
    if result.returncode != 0:
        detail = (result.stderr or "").strip().splitlines()
        reason = detail[-1] if detail else "ffmpeg 转换失败"
        raise RuntimeError(f".mp4 转 .mp3 失败：{reason}")
    if not dest.exists() or dest.stat().st_size <= 0:
        raise RuntimeError(".mp4 转 .mp3 失败：没有生成可用的音频文件")


def _find_ffmpeg() -> str:
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    try:
        import imageio_ffmpeg  # type: ignore

        candidate = imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        candidate = ""
    if candidate and Path(candidate).exists():
        return str(candidate)
    return ""


def create_conservative_noise_reduced_samples(paths: list[str | Path], pack_dir: str | Path) -> dict[str, Any]:
    """Create light denoised WAV copies while keeping imported originals untouched."""
    root = Path(pack_dir)
    processed_dir = root / "processed_samples"
    processed: list[str] = []
    skipped: list[str] = []

    for raw in paths:
        src = Path(raw)
        if src.suffix.lower() != ".wav":
            skipped.append(src.name)
            continue
        try:
            processed_dir.mkdir(parents=True, exist_ok=True)
            dest = processed_dir / f"{src.stem}_light_denoise.wav"
            dest = _unique_path(dest)
            if _write_light_denoised_wav(src, dest):
                processed.append(dest.relative_to(root).as_posix())
            else:
                skipped.append(src.name)
        except (OSError, wave.Error, ValueError, struct.error):
            skipped.append(src.name)

    return {
        "enabled": True,
        "mode": "light_conservative",
        "original_priority": True,
        "original_samples_preserved": True,
        "description": "仅生成轻度降噪副本；原始音频不覆盖、不改写，原声还原优先。",
        "processed_count": len(processed),
        "processed_samples": processed,
        "skipped": skipped,
    }


def _write_light_denoised_wav(src: Path, dest: Path) -> bool:
    with wave.open(str(src), "rb") as reader:
        params = reader.getparams()
        if params.comptype != "NONE" or params.sampwidth not in (1, 2, 3, 4):
            return False
        frames = reader.readframes(params.nframes)

    samples = _decode_pcm_samples(frames, params.sampwidth)
    if not samples:
        return False

    cleaned = _light_denoise_samples(samples, params.sampwidth)
    with wave.open(str(dest), "wb") as writer:
        writer.setparams(params)
        writer.writeframes(_encode_pcm_samples(cleaned, params.sampwidth))
    return True


def _light_denoise_samples(samples: list[int], sample_width: int) -> list[int]:
    if not samples:
        return []
    limit = (1 << (sample_width * 8 - 1)) - 1
    floor = -(1 << (sample_width * 8 - 1))
    dc_offset = round(sum(samples) / len(samples))
    centered = [sample - dc_offset for sample in samples]
    abs_values = sorted(abs(value) for value in centered if value)
    if not abs_values:
        return [0 for _ in samples]

    noise_floor = abs_values[min(len(abs_values) - 1, max(0, len(abs_values) // 5))]
    threshold = min(limit * 0.015, noise_floor * 1.35)
    if threshold < max(2, limit * 0.001):
        threshold = 0

    cleaned: list[int] = []
    for value in centered:
        if threshold and abs(value) < threshold:
            value = round(value * 0.55)
        value = max(floor, min(limit, value))
        cleaned.append(int(value))
    return cleaned


def _decode_pcm_samples(frames: bytes, sample_width: int) -> list[int]:
    if sample_width == 1:
        return [byte - 128 for byte in frames]
    if sample_width == 2:
        return [item[0] for item in struct.iter_unpack("<h", frames)]
    if sample_width == 3:
        samples: list[int] = []
        for index in range(0, len(frames) - (len(frames) % 3), 3):
            chunk = frames[index : index + 3]
            sign = b"\xff" if chunk[2] & 0x80 else b"\x00"
            samples.append(int.from_bytes(chunk + sign, byteorder="little", signed=True))
        return samples
    if sample_width == 4:
        return [item[0] for item in struct.iter_unpack("<i", frames)]
    return []


def _encode_pcm_samples(samples: list[int], sample_width: int) -> bytes:
    if sample_width == 1:
        return bytes(max(0, min(255, sample + 128)) for sample in samples)
    if sample_width == 2:
        return b"".join(struct.pack("<h", sample) for sample in samples)
    if sample_width == 3:
        return b"".join(
            int(sample).to_bytes(4, byteorder="little", signed=True)[:3]
            for sample in samples
        )
    if sample_width == 4:
        return b"".join(struct.pack("<i", sample) for sample in samples)
    return b""


def _valid_sample_paths(sample_paths: list[str | Path]) -> list[Path]:
    seen: set[str] = set()
    valid: list[Path] = []
    for raw in sample_paths or []:
        path = Path(raw)
        key = str(path.resolve()).lower() if path.exists() else str(path).lower()
        if key in seen:
            continue
        seen.add(key)
        if path.is_file() and path.suffix.lower() in IMPORT_SAMPLE_EXTENSIONS:
            valid.append(path)
    return valid


def _normalize_clone_backend(value: str | None) -> str:
    backend = str(value or "").strip().lower().replace("_", "-")
    if backend in {"gpt-sovits", "gptsovits", "sovits", "voice-clone"}:
        return "gpt-sovits"
    return ""


def _voice_pack_clone_backend_manifest(clone_config: dict[str, Any]) -> dict[str, Any]:
    if not clone_config:
        return {}
    return {
        "provider": "gpt-sovits",
        "mode": "zero_shot_reference",
        "status": "ready",
        "api_url": clone_config.get("api_url", ""),
        "ref_audio_path": clone_config.get("ref_audio_path", ""),
        "aux_ref_audio_paths": clone_config.get("aux_ref_audio_paths", []),
        "prompt_text": clone_config.get("prompt_text", ""),
        "prompt_lang": clone_config.get("prompt_lang", ""),
        "text_lang": clone_config.get("text_lang", ""),
    }


def _unique_pack_id(display_name: str, base_path: Path) -> str:
    stem = re.sub(r"[^0-9A-Za-z_-]+", "_", display_name.strip()).strip("_-").lower()
    if stem:
        stem = stem[:40]
        candidate = f"user_{stem}"
    else:
        digest = hashlib.sha1(display_name.encode("utf-8", errors="ignore")).hexdigest()[:8]
        candidate = f"user_voice_{digest}"

    final = candidate
    index = 2
    while (base_path / final).exists():
        final = f"{candidate}_{index}"
        index += 1
    return final


def _unique_sample_filename(sample_dir: Path, src: Path, index: int) -> str:
    stem = re.sub(r"[^0-9A-Za-z_.-]+", "_", src.stem).strip("._-") or f"sample_{index:02d}"
    stem = stem[:48]
    ext = src.suffix.lower() if src.suffix else ".wav"
    candidate = f"{index:02d}_{stem}{ext}"
    extra = 2
    while (sample_dir / candidate).exists():
        candidate = f"{index:02d}_{stem}_{extra}{ext}"
        extra += 1
    return candidate


def _unique_path(path: Path) -> Path:
    if not path.exists():
        return path
    stem = path.stem
    suffix = path.suffix
    index = 2
    while True:
        candidate = path.with_name(f"{stem}_{index}{suffix}")
        if not candidate.exists():
            return candidate
        index += 1


class VoicePackManager:
    """Loads optional local voice clips and profile settings."""

    def __init__(self, pack_id: str = "", base_dir: str | Path = "assets/voice_packs", enabled: bool = True):
        self.pack_id = (pack_id or "").strip()
        self.base_dir = Path(base_dir)
        self.enabled = bool(enabled)
        self._cache: dict[str, dict] = {}

    def set_pack_id(self, pack_id: str) -> None:
        self.pack_id = (pack_id or "").strip()

    def _pack_dir(self, pack_id: str | None = None) -> Path:
        return self.base_dir / ((pack_id or self.pack_id).strip())

    def _manifest(self, pack_id: str | None = None) -> dict:
        pid = (pack_id or self.pack_id).strip()
        if not pid:
            return {}
        if pid in self._cache:
            return self._cache[pid]
        manifest_path = self._pack_dir(pid) / "voice_pack.json"
        if not manifest_path.exists():
            self._cache[pid] = {}
            return {}
        try:
            data = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            data = {}
        self._cache[pid] = data if isinstance(data, dict) else {}
        return self._cache[pid]

    def pick_clip(self, text: str, state: str = "neutral", action: str = "speak") -> Path | None:
        if not self.enabled or not self.pack_id:
            return None
        manifest = self._manifest()
        pack_dir = self._pack_dir()

        keywords = manifest.get("keywords", {})
        if isinstance(keywords, dict):
            for keyword, files in keywords.items():
                if keyword and str(keyword) in (text or ""):
                    clip = self._pick_existing(pack_dir, files)
                    if clip:
                        return clip

        clips = manifest.get("clips", {})
        if not isinstance(clips, dict):
            return None
        for key in (f"{state}.{action}", f"{state}.speak", action, "speak", "default"):
            clip = self._pick_existing(pack_dir, clips.get(key))
            if clip:
                return clip
        return None

    def voice_profile(self, state: str = "neutral", action: str = "speak") -> dict:
        if not self.enabled or not self.pack_id:
            return {}
        profiles = self._manifest().get("voice_profiles", {})
        if not isinstance(profiles, dict):
            return {}
        merged: dict = {}
        default = profiles.get("default", {})
        if isinstance(default, dict):
            merged.update(default)
        for key in (f"{state}.{action}", state, action):
            profile = profiles.get(key, {})
            if isinstance(profile, dict):
                merged.update(profile)
        return merged

    def sample_paths(self) -> list[Path]:
        if not self.enabled or not self.pack_id:
            return []
        manifest = self._manifest()
        pack_dir = self._pack_dir()
        samples = manifest.get("samples", [])
        if not isinstance(samples, list):
            return []
        paths = [pack_dir / str(name) for name in samples]
        return [path for path in paths if path.exists() and path.is_file()]

    def reference_sample(self) -> Path | None:
        samples = self.sample_paths()
        if not samples:
            return None
        preferred_suffixes = (".wav", ".mp3", ".flac", ".m4a", ".ogg", ".aac", ".wma")
        for suffix in preferred_suffixes:
            match = next((path for path in samples if path.suffix.lower() == suffix), None)
            if match:
                return match
        return samples[0]

    def resolve_gpt_sovits_backend(self, backend: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(backend, dict):
            return {}
        pack_dir = self._pack_dir()
        resolved = dict(backend)
        ref_audio_path = str(backend.get("ref_audio_path") or "").strip()
        resolved["ref_audio_path"] = (
            str(self._resolve_pack_path(ref_audio_path, pack_dir))
            if ref_audio_path
            else ""
        )
        aux_paths = backend.get("aux_ref_audio_paths")
        if isinstance(aux_paths, str):
            aux_paths = [aux_paths]
        if isinstance(aux_paths, list):
            resolved["aux_ref_audio_paths"] = [
                str(self._resolve_pack_path(path, pack_dir))
                for path in aux_paths
                if str(path or "").strip()
            ]
        else:
            resolved["aux_ref_audio_paths"] = []
        return resolved

    @staticmethod
    def _resolve_pack_path(value: Any, pack_dir: Path) -> Path:
        raw = str(value or "").strip()
        if not raw:
            return Path("")
        path = Path(raw)
        if path.is_absolute():
            return path
        return pack_dir / path

    @staticmethod
    def _pick_existing(pack_dir: Path, files) -> Path | None:
        if isinstance(files, str):
            files = [files]
        if not isinstance(files, list) or not files:
            return None
        candidates = [pack_dir / str(name) for name in files]
        existing = [path for path in candidates if path.exists()]
        return random.choice(existing) if existing else None
