"""
Optional OpenVoice tone-color conversion for generated TTS audio.

The main app can run without OpenVoice installed. When enabled and configured,
this bridge shells out to a separate Python environment that contains the
OpenVoice repo and checkpoints, then falls back to the original TTS audio if
conversion is not available.
"""

from __future__ import annotations

import hashlib
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from models.tts.voice_pack import _find_ffmpeg


PROJECT_ROOT = Path(__file__).resolve().parents[2]
TRUE_VALUES = {"1", "true", "yes", "y", "on", "enable", "enabled", "开启", "启用"}


class OpenVoicePostProcessor:
    def __init__(self, project_root: str | Path = PROJECT_ROOT) -> None:
        self.project_root = Path(project_root)
        self.work_dir = self.project_root / "assets" / "openvoice_work"

    def convert_if_enabled(self, source_path: str | Path, voice_pack: Any, settings: dict[str, Any]) -> Path:
        source = Path(source_path)
        if not self._enabled(settings):
            return source
        reference = self._reference_sample(voice_pack)
        if reference is None:
            print("[OpenVoice] 未找到当前语音包的参考样本，跳过声纹转换")
            return source

        runtime = self._runtime(settings)
        missing = self._missing_runtime(runtime)
        if missing:
            print(f"[OpenVoice] 环境未就绪，跳过声纹转换：{missing}")
            return source

        self.work_dir.mkdir(parents=True, exist_ok=True)
        source_wav = self._audio_to_wav(source, self.work_dir / f"{source.stem}_openvoice_src.wav")
        reference_wav = self._cached_reference_wav(reference)
        if source_wav is None or reference_wav is None:
            print("[OpenVoice] 音频预处理失败，跳过声纹转换")
            return source

        output = source.with_name(f"{source.stem}_openvoice.wav")
        command = [
            str(runtime["python"]),
            str(PROJECT_ROOT / "models" / "tts" / "openvoice_convert.py"),
            "--repo-dir",
            str(runtime["repo_dir"]),
            "--checkpoint-dir",
            str(runtime["checkpoint_dir"]),
            "--source",
            str(source_wav),
            "--reference",
            str(reference_wav),
            "--output",
            str(output),
            "--device",
            str(runtime["device"]),
            "--tau",
            str(runtime["tau"]),
        ]
        timeout = float(runtime["timeout"])
        try:
            result = subprocess.run(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                check=False,
                timeout=timeout,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            print(f"[OpenVoice] 转换启动失败：{exc}")
            return source

        if result.returncode != 0:
            detail = (result.stderr or result.stdout or "").strip().splitlines()
            reason = detail[-1] if detail else f"退出码 {result.returncode}"
            print(f"[OpenVoice] 转换失败，已回退原始 TTS：{reason}")
            return source
        if not output.exists() or output.stat().st_size <= 0:
            print("[OpenVoice] 转换后没有生成可用音频，已回退原始 TTS")
            return source
        print(f"[OpenVoice] 已生成声纹转换音频: {output}")
        return output

    def _enabled(self, settings: dict[str, Any]) -> bool:
        value = settings.get("openvoice_enabled")
        env_value = os.getenv("OPENVOICE_ENABLED", "")
        return _bool_setting(value) or _bool_setting(env_value)

    def _runtime(self, settings: dict[str, Any]) -> dict[str, Any]:
        repo_dir = _path_setting(
            settings.get("openvoice_repo_dir"),
            os.getenv("OPENVOICE_REPO_DIR"),
            self.project_root / "third_party" / "OpenVoice",
        )
        checkpoint_dir = _path_setting(
            settings.get("openvoice_checkpoint_dir"),
            os.getenv("OPENVOICE_CHECKPOINT_DIR"),
            repo_dir / "checkpoints_v2",
        )
        python_exe = _path_setting(
            settings.get("openvoice_python"),
            os.getenv("OPENVOICE_PYTHON"),
            self.project_root / ".openvoice" / "Scripts" / "python.exe",
        )
        if not python_exe.exists():
            python_exe = Path(sys.executable)
        return {
            "python": python_exe,
            "repo_dir": repo_dir,
            "checkpoint_dir": checkpoint_dir,
            "device": str(settings.get("openvoice_device") or os.getenv("OPENVOICE_DEVICE") or "auto"),
            "tau": str(settings.get("openvoice_tau") or os.getenv("OPENVOICE_TAU") or "0.3"),
            "timeout": str(settings.get("openvoice_timeout") or os.getenv("OPENVOICE_TIMEOUT") or "120"),
        }

    def _missing_runtime(self, runtime: dict[str, Any]) -> str:
        python_exe = Path(runtime["python"])
        repo_dir = Path(runtime["repo_dir"])
        checkpoint_dir = Path(runtime["checkpoint_dir"])
        if not python_exe.exists():
            return f"Python 不存在：{python_exe}"
        if not (repo_dir / "openvoice" / "api.py").exists():
            return f"OpenVoice 仓库不存在：{repo_dir}"
        if not (checkpoint_dir / "converter" / "config.json").exists():
            return f"checkpoint 不存在：{checkpoint_dir / 'converter'}"
        if not (checkpoint_dir / "converter" / "checkpoint.pth").exists():
            return f"checkpoint 不完整：{checkpoint_dir / 'converter' / 'checkpoint.pth'}"
        return ""

    def _reference_sample(self, voice_pack: Any) -> Path | None:
        if voice_pack is None or not hasattr(voice_pack, "reference_sample"):
            return None
        try:
            sample = voice_pack.reference_sample()
        except Exception:
            return None
        return Path(sample) if sample else None

    def _audio_to_wav(self, src: Path, dest: Path) -> Path | None:
        ffmpeg = _find_ffmpeg()
        if not ffmpeg:
            return src if src.suffix.lower() == ".wav" else None
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

    def _cached_reference_wav(self, reference: Path) -> Path | None:
        try:
            stat = reference.stat()
            key = f"{reference.resolve()}|{stat.st_mtime_ns}|{stat.st_size}"
        except OSError:
            return None
        digest = hashlib.sha1(key.encode("utf-8", errors="ignore")).hexdigest()[:16]
        dest = self.work_dir / f"reference_{digest}.wav"
        if dest.exists() and dest.stat().st_size > 0:
            return dest
        return self._audio_to_wav(reference, dest)


def _bool_setting(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in TRUE_VALUES


def _path_setting(value: Any, env_value: Any, default: str | Path) -> Path:
    raw = str(value or env_value or default).strip()
    path = Path(raw).expanduser()
    if path.is_absolute():
        return path
    return PROJECT_ROOT / path
