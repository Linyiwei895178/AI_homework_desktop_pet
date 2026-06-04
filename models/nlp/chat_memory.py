from __future__ import annotations

import json
from pathlib import Path


class ChatMemory:
    """Small rolling chat memory for Team C."""

    def __init__(
        self,
        max_rounds: int = 6,
        persist_path: str | Path | None = None,
        autosave: bool = True,
    ):
        self.max_rounds = max(1, int(max_rounds))
        self._messages: list[dict[str, str]] = []
        self.persist_path = Path(persist_path) if persist_path else None
        self.autosave = bool(autosave)
        if self.persist_path:
            self.load_json(self.persist_path)

    def set_persist_path(self, filepath: str | Path | None, load_existing: bool = True) -> None:
        self.persist_path = Path(filepath) if filepath else None
        if self.persist_path and load_existing:
            self.load_json(self.persist_path)

    def append_user(self, text: str) -> None:
        self._append("user", text)

    def append_assistant(self, text: str) -> None:
        self._append("assistant", text)

    def _append(self, role: str, text: str) -> None:
        value = (text or "").strip()
        if not value:
            return
        self._messages.append({"role": role, "content": value})
        max_messages = self.max_rounds * 2
        if len(self._messages) > max_messages:
            self._messages = self._messages[-max_messages:]
        self._save_if_needed()

    def get_messages(self) -> list[dict[str, str]]:
        return [dict(item) for item in self._messages]

    def clear(self) -> None:
        self._messages.clear()
        self._save_if_needed()

    def save_json(self, filepath: str | Path) -> None:
        path = Path(filepath)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self._messages, ensure_ascii=False, indent=2), encoding="utf-8")

    def load_json(self, filepath: str | Path) -> None:
        path = Path(filepath)
        if not path.exists():
            self.clear()
            return
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            data = data.get("messages", data.get("msgs", []))
        self._messages = [
            {"role": str(item.get("role", "")), "content": str(item.get("content", ""))}
            for item in data
            if isinstance(item, dict) and item.get("role") in {"user", "assistant"} and item.get("content")
        ][-(self.max_rounds * 2):]

    def _save_if_needed(self) -> None:
        if self.autosave and self.persist_path:
            self.save_json(self.persist_path)
