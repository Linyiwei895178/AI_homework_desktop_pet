from __future__ import annotations

import hashlib
import json
import random
import re
import shutil
import struct
import subprocess
import time
import wave
from pathlib import Path
from typing import Any


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
        "label": "英语",
        "edge_voice": "en-US-JennyNeural",
        "edge_rate": "+0%",
        "edge_pitch": "+2Hz",
        "edge_volume": "+4%",
        "voice_profile": "default",
        "cute_style": False,
        "sample_text": "Hi, I am here with you.",
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
        profile = {
            "edge_voice": preset["edge_voice"],
            "edge_rate": preset["edge_rate"],
            "edge_pitch": preset["edge_pitch"],
            "edge_volume": preset["edge_volume"],
            "voice_profile": preset["voice_profile"],
            "cute_style": bool(preset["cute_style"]),
        }
        manifest: dict[str, Any] = {
            "id": pack_id,
            "display_name": display_name_with_language,
            "user_name": name,
            "icon": "🎙️",
            "description": (
                f"本地导入的{preset['label']}语音样本；"
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
            "simulation": {
                "mode": "language_profile",
                "note": "当前版本按所选语言和音频样本信息生成近似音色参数；原始样本优先保留，不克隆具体真人声纹。",
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


def analyze_audio_samples(paths: list[str | Path]) -> dict[str, Any]:
    formats: set[str] = set()
    sample_rates: set[int] = set()
    channels: set[int] = set()
    total_size = 0
    total_duration = 0.0
    duration_count = 0

    for raw in paths:
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

        if path.suffix.lower() != ".wav":
            continue
        try:
            with wave.open(str(path), "rb") as wav:
                rate = int(wav.getframerate() or 0)
                frame_count = int(wav.getnframes() or 0)
                channel_count = int(wav.getnchannels() or 0)
                if rate > 0 and frame_count > 0:
                    total_duration += frame_count / rate
                    duration_count += 1
                    sample_rates.add(rate)
                if channel_count > 0:
                    channels.add(channel_count)
        except (OSError, wave.Error):
            continue

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
    return analysis


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
        if params.comptype != "NONE" or params.sampwidth not in (1, 2, 4):
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
    if sample_width == 4:
        return [item[0] for item in struct.iter_unpack("<i", frames)]
    return []


def _encode_pcm_samples(samples: list[int], sample_width: int) -> bytes:
    if sample_width == 1:
        return bytes(max(0, min(255, sample + 128)) for sample in samples)
    if sample_width == 2:
        return b"".join(struct.pack("<h", sample) for sample in samples)
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

    @staticmethod
    def _pick_existing(pack_dir: Path, files) -> Path | None:
        if isinstance(files, str):
            files = [files]
        if not isinstance(files, list) or not files:
            return None
        candidates = [pack_dir / str(name) for name in files]
        existing = [path for path in candidates if path.exists()]
        return random.choice(existing) if existing else None
