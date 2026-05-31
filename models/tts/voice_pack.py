from __future__ import annotations

import json
import random
from pathlib import Path


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
