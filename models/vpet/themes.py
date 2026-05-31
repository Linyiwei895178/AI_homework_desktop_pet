from __future__ import annotations

from dataclasses import dataclass, field

from models.vpet.lps import LpsRecord


@dataclass
class Theme:
    name: str
    x_name: str = ""
    image: str = ""
    colors: dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_records(cls, records: list[LpsRecord]) -> "Theme | None":
        if not records:
            return None
        head = records[0]
        theme = cls(name=head.info or head.name, x_name=head.name, image=head.get("image", ""))
        for record in records[1:]:
            if record.info:
                theme.colors[record.name] = record.info
        return theme

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "x_name": self.x_name,
            "image": self.image,
            "colors": dict(self.colors),
        }
