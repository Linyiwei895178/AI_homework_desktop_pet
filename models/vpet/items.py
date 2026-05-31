from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from models.vpet.lps import LpsRecord


class FoodType(str, Enum):
    FOOD = "Food"
    STAR = "Star"
    MEAL = "Meal"
    SNACK = "Snack"
    DRINK = "Drink"
    FUNCTIONAL = "Functional"
    DRUG = "Drug"
    GIFT = "Gift"


@dataclass
class Item:
    name: str
    item_type: str = "Item"
    price: float = 0.0
    desc: str = ""
    image: str | None = None
    count: int = 1
    data: str = ""
    can_use: bool = True
    star: bool = False
    is_single: bool = False
    visibility: bool = True

    @classmethod
    def from_lps_record(cls, record: LpsRecord) -> "Item":
        return cls(
            name=record.get("name", record.info or record.name),
            item_type=record.get("itemtype", "Item"),
            price=record.get_float("price", 0.0),
            desc=record.get("desc", ""),
            image=record.get("image", "") or None,
            count=record.get_int("count", 1),
            data=record.get("data", ""),
            can_use=record.get_bool("canuse", True),
            star=record.get_bool("star", False),
            is_single=record.get_bool("issingle", False),
            visibility=record.get_bool("visibility", True),
        )

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "item_type": self.item_type,
            "price": self.price,
            "desc": self.desc,
            "image": self.image,
            "count": self.count,
            "data": self.data,
            "can_use": self.can_use,
            "star": self.star,
            "is_single": self.is_single,
            "visibility": self.visibility,
        }


@dataclass
class Food(Item):
    item_type: str = "Food"
    food_type: FoodType = FoodType.FOOD
    exp: float = 0.0
    strength: float = 0.0
    strength_food: float = 0.0
    strength_drink: float = 0.0
    feeling: float = 0.0
    health: float = 0.0
    likability: float = 0.0
    graph: str | None = None

    @classmethod
    def from_lps_record(cls, record: LpsRecord) -> "Food":
        item = Item.from_lps_record(record)
        raw_type = record.get("type", FoodType.FOOD.value)
        try:
            food_type = FoodType(raw_type)
        except ValueError:
            food_type = FoodType.FOOD
        return cls(
            name=item.name,
            price=item.price,
            desc=item.desc,
            image=item.image,
            count=item.count,
            data=item.data,
            can_use=item.can_use,
            star=item.star,
            is_single=item.is_single,
            visibility=item.visibility,
            food_type=food_type,
            exp=record.get_float("exp", 0.0),
            strength=record.get_float("strength", 0.0),
            strength_food=record.get_float("strengthfood", 0.0),
            strength_drink=record.get_float("strengthdrink", 0.0),
            feeling=record.get_float("feeling", 0.0),
            health=record.get_float("health", 0.0),
            likability=record.get_float("likability", 0.0),
            graph=record.get("graph", "") or None,
        )

    @property
    def real_price(self) -> float:
        return (
            (self.exp / 3 + self.strength / 5 + self.strength_drink / 3 + self.strength_food / 2 + self.feeling / 6) / 3
            + self.health
            + self.likability * 10
        )

    @property
    def graph_name(self) -> str:
        if self.graph:
            return self.graph
        if self.food_type == FoodType.DRINK:
            return "drink"
        if self.food_type == FoodType.GIFT:
            return "gift"
        return "eat"

    def is_overload(self) -> bool:
        return self.price < (self.real_price - 10) * 0.7

    def description_values(self) -> dict[str, float]:
        values = {
            "exp": self.exp,
            "strength_food": self.strength_food,
            "strength_drink": self.strength_drink,
            "strength": self.strength,
            "feeling": self.feeling,
            "health": self.health,
            "likability": self.likability,
        }
        return {key: value for key, value in values.items() if value != 0}

    def to_dict(self) -> dict:
        data = super().to_dict()
        data.update(
            {
                "food_type": self.food_type.value,
                "exp": self.exp,
                "strength": self.strength,
                "strength_food": self.strength_food,
                "strength_drink": self.strength_drink,
                "feeling": self.feeling,
                "health": self.health,
                "likability": self.likability,
                "graph": self.graph,
            }
        )
        return data
