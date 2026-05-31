from __future__ import annotations

import random
from dataclasses import dataclass, field

from models.vpet.lps import LpsRecord
from models.vpet.save import ModeType, VPetGameSave


MODE_FLAGS = {
    ModeType.HAPPY: 1,
    ModeType.NOMAL: 2,
    ModeType.POOR_CONDITION: 4,
    ModeType.ILL: 8,
}


@dataclass
class TextRule:
    text: str
    kind: str = "clicktext"
    tags: set[str] = field(default_factory=lambda: {"all"})
    mode_flags: int = 7
    state: str | None = None
    working: str | None = None
    like_min: float = 0.0
    like_max: float = float("inf")
    health_min: float = 0.0
    health_max: float = float("inf")
    level_min: float = 0.0
    level_max: float = float("inf")
    money_min: float = float("-inf")
    money_max: float = float("inf")
    food_min: float = 0.0
    food_max: float = float("inf")
    drink_min: float = 0.0
    drink_max: float = float("inf")
    feel_min: float = 0.0
    feel_max: float = float("inf")
    strength_min: float = 0.0
    strength_max: float = float("inf")
    money: float = 0.0
    exp: float = 0.0
    strength: float = 0.0
    strength_food: float = 0.0
    strength_drink: float = 0.0
    feeling: float = 0.0
    health: float = 0.0
    likability: float = 0.0

    @classmethod
    def from_lps_record(cls, record: LpsRecord) -> "TextRule":
        tags = {tag.strip() for tag in record.get("tag", "all").split(",") if tag.strip()}
        return cls(
            text=record.get("text", record.info),
            kind=record.name,
            tags=tags or {"all"},
            mode_flags=record.get_int("mode", 7),
            state=record.get("state", "") or None,
            working=record.get("working", "") or None,
            like_min=record.get_float("likemin", 0.0),
            like_max=record.get_float("likemax", float("inf")),
            health_min=record.get_float("healthmin", 0.0),
            health_max=record.get_float("healthmax", float("inf")),
            level_min=record.get_float("levelmin", 0.0),
            level_max=record.get_float("levelmax", float("inf")),
            money_min=record.get_float("moneymin", float("-inf")),
            money_max=record.get_float("moneymax", float("inf")),
            food_min=record.get_float("foodmin", 0.0),
            food_max=record.get_float("foodmax", float("inf")),
            drink_min=record.get_float("drinkmin", 0.0),
            drink_max=record.get_float("drinkmax", float("inf")),
            feel_min=record.get_float("feelmin", 0.0),
            feel_max=record.get_float("feelmax", float("inf")),
            strength_min=record.get_float("strengthmin", 0.0),
            strength_max=record.get_float("strengthmax", float("inf")),
            money=record.get_float("money", 0.0),
            exp=record.get_float("exp", 0.0),
            strength=record.get_float("strength", 0.0),
            strength_food=record.get_float("strengthfood", 0.0),
            strength_drink=record.get_float("strengthdrink", 0.0),
            feeling=record.get_float("feeling", 0.0),
            health=record.get_float("health", 0.0),
            likability=record.get_float("likability", 0.0),
        )

    def matches(
        self,
        save: VPetGameSave,
        *,
        state: str | None = None,
        working: str | None = None,
        tags: set[str] | None = None,
    ) -> bool:
        if not self.text:
            return False
        if MODE_FLAGS.get(save.mode, 2) & self.mode_flags == 0:
            return False
        if self.state and state and self.state.lower() != state.lower():
            return False
        if self.working and working and self.working != working:
            return False
        if tags and "all" not in self.tags and self.tags.isdisjoint(tags):
            return False
        return (
            self.like_min <= save.likability <= self.like_max
            and self.health_min <= save.health <= self.health_max
            and self.level_min <= save.level <= self.level_max
            and self.money_min <= save.money <= self.money_max
            and self.food_min <= save.strength_food <= self.food_max
            and self.drink_min <= save.strength_drink <= self.drink_max
            and self.feel_min <= save.feeling <= self.feel_max
            and self.strength_min <= save.strength <= self.strength_max
        )

    def apply_effects(self, save: VPetGameSave) -> None:
        save.money += self.money
        save.add_exp(self.exp)
        save.strength_change(self.strength)
        save.strength_food_change(self.strength_food)
        save.strength_drink_change(self.strength_drink)
        save.feeling_change(self.feeling)
        save.health = min(100.0, max(0.0, save.health + self.health))
        save.likability = min(save.likability_max, max(0.0, save.likability + self.likability))
        save.mode = save.cal_mode()

    def render(self, save: VPetGameSave) -> str:
        return (
            self.text.replace("{name}", save.name)
            .replace("{food}", f"{save.strength_food:.0f}")
            .replace("{drink}", f"{save.strength_drink:.0f}")
            .replace("{feel}", f"{save.feeling:.0f}")
            .replace("{strength}", f"{save.strength:.0f}")
            .replace("{money}", f"{save.money:.0f}")
            .replace("{level}", f"{save.level:.0f}")
            .replace("{health}", f"{save.health:.0f}")
            .replace("{hostname}", save.host_name)
        )


def choose_text(
    rules: list[TextRule],
    save: VPetGameSave,
    *,
    kind: str = "clicktext",
    state: str | None = None,
    working: str | None = None,
    tags: set[str] | None = None,
) -> TextRule | None:
    candidates = [
        rule
        for rule in rules
        if rule.kind == kind and rule.matches(save, state=state, working=working, tags=tags)
    ]
    return random.choice(candidates) if candidates else None
