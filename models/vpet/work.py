from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum

from models.vpet.lps import LpsRecord
from models.vpet.save import VPetGameSave


class WorkType(str, Enum):
    WORK = "Work"
    STUDY = "Study"
    PLAY = "Play"


def signed_pow(value: float, power: float) -> float:
    sign = -1 if value < 0 else 1
    return math.pow(abs(value), power) * sign


@dataclass
class Work:
    name: str
    work_type: WorkType = WorkType.WORK
    graph: str = ""
    money_base: float = 0.0
    strength_food: float = 0.0
    strength_drink: float = 0.0
    feeling: float = 0.0
    level_limit: int = 0
    time: int = 10
    finish_bonus: float = 0.0
    border_brush: str = "0290D5"
    background: str = "81d4fa"
    button_background: str = "0286C6"
    button_foreground: str = "ffffff"
    foreground: str = "0286C6"
    left: float = 100.0
    top: float = 160.0
    width: float = 300.0

    @classmethod
    def from_lps_record(cls, record: LpsRecord) -> "Work":
        raw_type = record.get("type", WorkType.WORK.value)
        try:
            work_type = WorkType(raw_type)
        except ValueError:
            work_type = WorkType.WORK
        return cls(
            name=record.get("name", record.info or record.name),
            work_type=work_type,
            graph=record.get("graph", ""),
            money_base=record.get_float("moneybase", 0.0),
            strength_food=record.get_float("strengthfood", 0.0),
            strength_drink=record.get_float("strengthdrink", 0.0),
            feeling=record.get_float("feeling", 0.0),
            level_limit=record.get_int("levellimit", 0),
            time=max(10, record.get_int("time", 10)),
            finish_bonus=max(0.0, min(2.0, record.get_float("finishbonus", 0.0))),
            border_brush=record.get("borderbrush", "0290D5"),
            background=record.get("background", "81d4fa"),
            button_background=record.get("buttonbackground", "0286C6"),
            button_foreground=record.get("buttonforeground", "ffffff"),
            foreground=record.get("foreground", "0286C6"),
            left=record.get_float("left", 100.0),
            top=record.get_float("top", 160.0),
            width=record.get_float("width", 300.0),
        )

    def get_efficiency(self) -> float:
        if self.work_type == WorkType.WORK:
            return signed_pow(abs(self.money_base) * (1 + self.finish_bonus / 2) + 1, 1.25)
        return signed_pow((abs(self.money_base) * (1 + self.finish_bonus / 2) + 1) / 10, 1.25)

    def spend_efficiency(self) -> float:
        return (
            signed_pow(self.strength_food, 1.5) / 3
            + signed_pow(self.strength_drink, 1.5) / 4
            + signed_pow(self.feeling, 1.5) / 4
            + self.level_limit / 10.0
            + signed_pow(self.strength_food + self.strength_drink + self.feeling, 1.5) / 10
        ) * 3

    def is_overload(self) -> bool:
        normalized = self.normalized()
        spend = normalized.spend_efficiency()
        gain = normalized.get_efficiency()
        ratio = gain / spend if spend else float("inf")
        if ratio < 0:
            return True
        level_limit = 1.1 * normalized.level_limit + 10
        if normalized.work_type != WorkType.WORK:
            level_limit *= 10
        if abs(normalized.money_base) > level_limit:
            return True
        return ratio > 1.4

    def normalized(self) -> "Work":
        work = self.copy()
        work.level_limit = max(0, work.level_limit)
        work.finish_bonus = max(0.0, min(2.0, work.finish_bonus))
        work.time = max(10, work.time)
        if work.work_type == WorkType.PLAY and work.feeling > 0:
            work.feeling *= -1
        return work

    def copy(self) -> "Work":
        return Work(**self.__dict__)

    def doubled(self, value: int) -> "Work":
        if value == 1:
            return self
        work = self.copy()
        work.strength_food *= 0.5 + 0.4 * value
        work.strength_drink *= 0.5 + 0.4 * value
        work.feeling *= 0.5 + 0.4 * value
        work.level_limit = (self.level_limit + 10) * value
        return fix_overload(work)

    def to_dict(self) -> dict:
        data = dict(self.__dict__)
        data["work_type"] = self.work_type.value
        return data


@dataclass
class WorkResult:
    work_name: str
    work_type: WorkType
    minutes: float
    gained: float
    finish_bonus: float
    completed: bool
    stopped_reason: str = "time_finish"

    @property
    def total_gained(self) -> float:
        return self.gained + self.finish_bonus


def fix_overload(work: Work) -> Work:
    fixed = work.normalized()
    spend = fixed.spend_efficiency()
    if spend > 0:
        fixed.money_base = 2 * (1.15 * math.pow(spend, 0.8) - 1) / (2 + fixed.finish_bonus)
        level_limit = 1.1 * fixed.level_limit + 10
        if fixed.work_type != WorkType.WORK:
            level_limit *= 10
        if fixed.work_type == WorkType.WORK:
            fixed.money_base = round(fixed.money_base, 1)
        else:
            fixed.money_base = round(fixed.money_base * 10, 1)
        fixed.money_base = min(fixed.money_base, level_limit)
    if not fixed.is_overload():
        return fixed
    if fixed.work_type == WorkType.PLAY:
        fixed.finish_bonus = 0.2
        fixed.money_base = 18
        fixed.strength_food = 1
        fixed.strength_drink = 1.5
        fixed.feeling = -1
        fixed.level_limit = 0
    elif fixed.work_type == WorkType.STUDY:
        fixed.finish_bonus = 0.2
        fixed.money_base = 80
        fixed.strength_food = 2
        fixed.strength_drink = 2
        fixed.feeling = 3
        fixed.level_limit = 0
    else:
        fixed.finish_bonus = 0.1
        fixed.money_base = 8
        fixed.strength_food = 3.5
        fixed.strength_drink = 2.5
        fixed.feeling = 1
        fixed.level_limit = 0
    return fixed


def run_work(save: VPetGameSave, work: Work, minutes: float | None = None, complete: bool = True) -> WorkResult:
    active = work.normalized()
    if save.level < active.level_limit:
        return WorkResult(active.name, active.work_type, 0.0, 0.0, 0.0, False, "level_limit")

    minutes = float(active.time if minutes is None else max(0.0, min(minutes, active.time)))
    save.clean_change()
    save.store_take()

    need_food = minutes * active.strength_food
    need_drink = minutes * active.strength_drink
    sm25 = save.strength_max * 0.25
    sm60 = save.strength_max * 0.60

    efficiency = 0.0
    add_health = -2.0
    ns_food = need_food * 0.3
    ns_drink = need_drink * 0.3
    if save.strength > sm25 + ns_food + ns_drink:
        save.strength_change(-ns_food - ns_drink)
        efficiency += 0.1
        need_food -= ns_food
        need_drink -= ns_drink

    if save.strength_food <= sm25:
        save.strength_food_change(-need_food / 2)
        efficiency += 0.2
        if save.strength >= need_food:
            save.strength_change(-need_food)
            efficiency += 0.1
        add_health -= 2
    else:
        save.strength_food_change(-need_food)
        efficiency += 0.4
        if save.strength_food >= sm60:
            add_health += 1
            efficiency += 0.1

    if save.strength_drink <= sm25:
        save.strength_drink_change(-need_drink / 2)
        efficiency += 0.2
        if save.strength >= need_drink:
            save.strength_change(-need_drink)
            efficiency += 0.1
        add_health -= 2
    else:
        save.strength_drink_change(-need_drink)
        efficiency += 0.4
        if save.strength_drink >= sm60:
            add_health += 1
            efficiency += 0.1

    if add_health > 0:
        save.health = min(100.0, save.health + add_health * minutes)

    gained = max(0.0, minutes * active.money_base * (2 * efficiency - 0.5))
    finish_bonus = gained * active.finish_bonus if complete and minutes >= active.time else 0.0
    if active.work_type == WorkType.WORK:
        save.money += gained + finish_bonus
    else:
        save.add_exp(gained + finish_bonus)

    if active.work_type == WorkType.PLAY:
        save.feeling_change(-active.feeling * minutes)
    else:
        save.feeling_change(-max(0.05, active.feeling) * minutes * 0.1)
    save.mode = save.cal_mode()
    return WorkResult(active.name, active.work_type, minutes, gained, finish_bonus, minutes >= active.time)
