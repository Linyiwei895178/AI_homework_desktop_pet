from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from models.vpet.items import Food


class ModeType(str, Enum):
    HAPPY = "Happy"
    NOMAL = "Nomal"
    POOR_CONDITION = "PoorCondition"
    ILL = "Ill"


def _clamp(value: float, low: float, high: float) -> float:
    return min(high, max(low, value))


@dataclass
class VPetGameSave:
    name: str = "pet"
    host_name: str = ""
    money: float = 100.0
    level: int = 1
    level_max: int = 0
    exp: float = 0.0
    strength: float = 100.0
    store_strength: float = 0.0
    strength_food: float = 100.0
    store_strength_food: float = 0.0
    strength_drink: float = 100.0
    store_strength_drink: float = 0.0
    feeling: float = 60.0
    health: float = 100.0
    likability: float = 0.0
    likability_max: float = 100.0
    mode: ModeType = ModeType.NOMAL
    change_strength: float = 0.0
    change_strength_food: float = 0.0
    change_strength_drink: float = 0.0
    change_feeling: float = 0.0

    @property
    def strength_max(self) -> float:
        return 100 + int((self.level * (1 + self.level_max)) ** 0.75 * 4)

    @property
    def feeling_max(self) -> float:
        return 100 + int((self.level * (1 + self.level_max)) ** 0.75 * 2)

    def level_up_need(self) -> int:
        return 200 * self.level - 100

    def add_exp(self, value: float) -> None:
        value = self.exp + value
        need = self.level_up_need()
        while value >= need:
            value -= need
            self.likability_max += 10
            self.level += 1
            if self.level > 1000 + self.level_max * 100:
                self.level_max += 1
                self.level = 100 * self.level_max
            need = self.level_up_need()
        self.exp = max(0.0, value)

    def total_exp_gained(self) -> float:
        total = 0.0
        for i in range(1, self.level_max + 1):
            for j in range(100 * i + 1, 1000 + 100 * i + 1):
                total += 200 * j - 100
        total += (self.level - 100 * self.level_max) * (200 * (self.level - 1) - 100)
        return total + self.exp

    def strength_change(self, value: float) -> None:
        self.change_strength += value
        self.strength = _clamp(self.strength + value, 0.0, self.strength_max)

    def strength_food_change(self, value: float) -> None:
        self.change_strength_food += value
        next_value = min(self.strength_max, self.strength_food + value)
        if next_value <= 0:
            self.health = _clamp(self.health + next_value, 0.0, 100.0)
            self.strength_food = 0.0
        else:
            self.strength_food = next_value

    def strength_drink_change(self, value: float) -> None:
        self.change_strength_drink += value
        next_value = min(self.strength_max, self.strength_drink + value)
        if next_value <= 0:
            self.health = _clamp(self.health + next_value, 0.0, 100.0)
            self.strength_drink = 0.0
        else:
            self.strength_drink = next_value

    def feeling_change(self, value: float) -> None:
        self.change_feeling += value
        next_value = min(self.feeling_max, self.feeling + value)
        if next_value <= 0:
            self.health = _clamp(self.health + next_value / 2, 0.0, 100.0)
            self.likability = _clamp(self.likability + next_value / 2, 0.0, self.likability_max)
            self.feeling = 0.0
        else:
            self.feeling = next_value

    def clean_change(self) -> None:
        self.change_strength /= 2
        self.change_strength_food /= 2
        self.change_strength_drink /= 2
        self.change_feeling /= 2

    def store_take(self) -> None:
        ratio = 10.0
        for store_attr, change_method in (
            ("store_strength", self.strength_change),
            ("store_strength_food", self.strength_food_change),
            ("store_strength_drink", self.strength_drink_change),
        ):
            stored = getattr(self, store_attr)
            delta = stored / ratio
            setattr(self, store_attr, stored - delta)
            if abs(getattr(self, store_attr)) < 1:
                setattr(self, store_attr, 0.0)
            else:
                change_method(delta)

    def eat_food(self, food: Food, buff: float = 1.0) -> None:
        self.add_exp(food.exp * buff)
        delta = food.strength / 2 * buff
        self.strength_change(delta)
        self.store_strength += delta
        delta = food.strength_food / 2 * buff
        self.strength_food_change(delta)
        self.store_strength_food += delta
        delta = food.strength_drink / 2 * buff
        self.strength_drink_change(delta)
        self.store_strength_drink += delta
        self.feeling_change(food.feeling * buff)
        self.health = _clamp(self.health + food.health * buff, 0.0, 100.0)
        self.likability = _clamp(self.likability + food.likability * buff, 0.0, self.likability_max)
        self.mode = self.cal_mode()

    def cal_mode(self) -> ModeType:
        real_health = 60
        if self.feeling / self.feeling_max >= 0.80:
            real_health -= 12
        if self.likability >= 80:
            real_health -= 12
        elif self.likability >= 40:
            real_health -= 6
        if self.health <= real_health:
            if self.health <= real_health / 2:
                return ModeType.ILL
            return ModeType.POOR_CONDITION
        real_feeling = 0.90
        if self.likability >= 80:
            real_feeling -= 0.20
        elif self.likability >= 40:
            real_feeling -= 0.10
        feeling_percent = self.feeling / self.feeling_max
        if feeling_percent >= real_feeling:
            return ModeType.HAPPY
        if feeling_percent <= real_feeling / 2:
            return ModeType.POOR_CONDITION
        return ModeType.NOMAL

    def to_dict(self) -> dict:
        data = dict(self.__dict__)
        data["mode"] = self.mode.value
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "VPetGameSave":
        values = dict(data)
        mode = values.get("mode", ModeType.NOMAL.value)
        if not isinstance(mode, ModeType):
            try:
                values["mode"] = ModeType(mode)
            except ValueError:
                values["mode"] = ModeType.NOMAL
        return cls(**values)

    def save_json(self, path: str | Path) -> None:
        Path(path).write_text(json.dumps(self.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")

    @classmethod
    def load_json(cls, path: str | Path) -> "VPetGameSave":
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))
