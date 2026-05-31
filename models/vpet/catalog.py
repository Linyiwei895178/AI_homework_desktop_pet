from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from models.vpet.items import Food, FoodType
from models.vpet.lps import LpsRecord, load_lps_file
from models.vpet.texts import TextRule
from models.vpet.themes import Theme
from models.vpet.work import Work, WorkType


@dataclass
class VPetCatalog:
    foods: list[Food] = field(default_factory=list)
    works: list[Work] = field(default_factory=list)
    texts: list[TextRule] = field(default_factory=list)
    themes: list[Theme] = field(default_factory=list)

    @classmethod
    def builtin(cls) -> "VPetCatalog":
        return cls(
            foods=[
                Food(
                    name="water",
                    food_type=FoodType.DRINK,
                    price=3.0,
                    desc="Clean water.",
                    exp=2,
                    strength_drink=45,
                    health=1,
                    feeling=2,
                    graph="drink",
                ),
                Food(
                    name="sandwich",
                    food_type=FoodType.MEAL,
                    price=9.0,
                    desc="A light meal.",
                    exp=8,
                    strength=20,
                    strength_food=55,
                    feeling=12,
                    graph="eat",
                ),
                Food(
                    name="coffee",
                    food_type=FoodType.FUNCTIONAL,
                    price=7.5,
                    desc="A quick energy boost.",
                    exp=6,
                    strength=45,
                    strength_drink=12,
                    health=-1,
                    feeling=4,
                    graph="drink",
                ),
            ],
            works=[
                Work(
                    name="writing",
                    work_type=WorkType.WORK,
                    money_base=8,
                    graph="work",
                    strength_food=3.5,
                    strength_drink=2.5,
                    feeling=1,
                    time=60,
                    finish_bonus=0.1,
                ),
                Work(
                    name="study",
                    work_type=WorkType.STUDY,
                    money_base=80,
                    graph="study",
                    strength_food=2,
                    strength_drink=2,
                    feeling=3,
                    time=45,
                    finish_bonus=0.2,
                ),
                Work(
                    name="play_game",
                    work_type=WorkType.PLAY,
                    money_base=18,
                    graph="play",
                    strength_food=1,
                    strength_drink=1.5,
                    feeling=-1,
                    time=30,
                    finish_bonus=0.2,
                ),
            ],
            texts=[
                TextRule(text="Need anything, {hostname}?", kind="clicktext", like_min=0),
                TextRule(text="Food is at {food}, drink is at {drink}.", kind="lowtext", food_max=30),
                TextRule(text="Level {level}, money {money}.", kind="selecttext"),
            ],
            themes=[
                Theme(
                    name="default",
                    x_name="default",
                    colors={
                        "Primary": "FF81d4fa",
                        "PrimaryText": "FF000000",
                        "Secondary": "FF90caf9",
                    },
                )
            ],
        )

    @classmethod
    def from_mod_dir(cls, path: str | Path) -> "VPetCatalog":
        root = Path(path)
        catalog = cls()
        if not root.exists():
            return catalog
        for file_path in sorted(root.glob("food/*.lps")):
            catalog.extend_records(load_lps_file(file_path))
        for file_path in sorted(root.glob("text/*.lps")):
            catalog.extend_records(load_lps_file(file_path))
        for file_path in sorted(root.glob("pet/*.lps")):
            catalog.extend_records(load_lps_file(file_path))
        for file_path in sorted(root.glob("theme/*.lps")):
            theme = Theme.from_records(load_lps_file(file_path))
            if theme:
                catalog.themes.append(theme)
        return catalog

    def extend_records(self, records: list[LpsRecord]) -> None:
        for record in records:
            if record.name == "food":
                self.foods.append(Food.from_lps_record(record))
            elif record.name == "work":
                self.works.append(Work.from_lps_record(record))
            elif record.name in {"clicktext", "lowtext", "selecttext"}:
                self.texts.append(TextRule.from_lps_record(record))

    def merge(self, other: "VPetCatalog") -> "VPetCatalog":
        return VPetCatalog(
            foods=self.foods + other.foods,
            works=self.works + other.works,
            texts=self.texts + other.texts,
            themes=self.themes + other.themes,
        )

    def find_food(self, name: str) -> Food | None:
        key = name.lower()
        return next((food for food in self.foods if food.name.lower() == key), None)

    def find_work(self, name: str) -> Work | None:
        key = name.lower()
        return next((work for work in self.works if work.name.lower() == key), None)
