"""
Small LinePutScript reader for VPet content files.

VPet stores most moddable content as lines like:
    food:|name#water:|type#Drink:|StrengthDrink#120:|

The parser here intentionally supports the subset used by catalog, food,
work, theme and text manifests. It keeps field names case-insensitive while
preserving the original value text.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class LpsRecord:
    name: str
    info: str = ""
    fields: dict[str, str] = field(default_factory=dict)

    def get(self, key: str, default: str = "") -> str:
        return self.fields.get(key.lower(), default)

    def has(self, key: str) -> bool:
        return key.lower() in self.fields

    def get_float(self, key: str, default: float = 0.0) -> float:
        value = self.get(key, "")
        if value == "":
            return default
        try:
            return float(value)
        except ValueError:
            return default

    def get_int(self, key: str, default: int = 0) -> int:
        value = self.get(key, "")
        if value == "":
            return default
        try:
            return int(float(value))
        except ValueError:
            return default

    def get_bool(self, key: str, default: bool = False) -> bool:
        value = self.get(key, "")
        if value == "":
            return default
        return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def _parse_segment(segment: str) -> tuple[str, str]:
    if "#" not in segment:
        return segment.strip(), ""
    key, value = segment.split("#", 1)
    return key.strip(), value.strip()


def parse_lps_line(line: str) -> LpsRecord | None:
    text = line.strip()
    if not text or text.startswith("///") or text.startswith("//"):
        return None
    segments = [part.strip() for part in text.split(":|") if part.strip()]
    if not segments:
        return None

    name, info = _parse_segment(segments[0])
    if not name:
        return None

    fields: dict[str, str] = {}
    for segment in segments[1:]:
        if segment.startswith("///") or segment.startswith("//"):
            continue
        key, value = _parse_segment(segment)
        if key:
            fields[key.lower()] = value
    return LpsRecord(name=name.lower(), info=info, fields=fields)


def parse_lps(text: str) -> list[LpsRecord]:
    records: list[LpsRecord] = []
    for line in text.splitlines():
        record = parse_lps_line(line)
        if record is not None:
            records.append(record)
    return records


def load_lps_file(path: str | Path, encoding: str = "utf-8") -> list[LpsRecord]:
    return parse_lps(Path(path).read_text(encoding=encoding))


def load_lps_files(paths: Iterable[str | Path]) -> list[LpsRecord]:
    records: list[LpsRecord] = []
    for path in paths:
        records.extend(load_lps_file(path))
    return records
