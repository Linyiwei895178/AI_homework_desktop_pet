"""
自由游走辅助函数（由 DesktopPet 独立定时器驱动；追鼠标亦在 DesktopPet 内）。
"""

from __future__ import annotations

import random

AUTO_WALK_MARGIN = 48.0
AUTO_WALK_ARRIVE_EPS = 10.0


def screen_walk_bounds(
    origin_x: float,
    origin_y: float,
    area_w: float,
    area_h: float,
    pet_w: float,
    pet_h: float,
) -> tuple[float, float, float, float]:
    """窗口左上角可移动范围 (min_x, min_y, max_x, max_y)。"""
    min_x = float(origin_x)
    min_y = float(origin_y)
    max_x = min_x + max(100.0, float(area_w)) - max(80.0, float(pet_w))
    max_y = min_y + max(100.0, float(area_h)) - max(80.0, float(pet_h))
    return min_x, min_y, max_x, max_y


def random_auto_walk_target(
    origin_x: float,
    origin_y: float,
    area_w: float,
    area_h: float,
    pet_w: float,
    pet_h: float,
    margin: float = AUTO_WALK_MARGIN,
) -> tuple[float, float]:
    """在屏幕可用区域内随机生成游走目标（避开边缘）。"""
    min_x, min_y, max_x, max_y = screen_walk_bounds(
        origin_x, origin_y, area_w, area_h, pet_w, pet_h
    )
    inner_min_x = min_x + margin
    inner_max_x = max_x - margin
    inner_min_y = min_y + margin
    inner_max_y = max_y - margin
    if inner_max_x <= inner_min_x:
        inner_min_x, inner_max_x = min_x, max_x
    if inner_max_y <= inner_min_y:
        inner_min_y, inner_max_y = min_y, max_y
    return (
        random.uniform(inner_min_x, inner_max_x),
        random.uniform(inner_min_y, inner_max_y),
    )


def clamp_window_position(
    x: float,
    y: float,
    origin_x: float,
    origin_y: float,
    area_w: float,
    area_h: float,
    pet_w: float,
    pet_h: float,
) -> tuple[float, float]:
    """将窗口左上角坐标限制在屏幕可用区域内。"""
    min_x, min_y, max_x, max_y = screen_walk_bounds(
        origin_x, origin_y, area_w, area_h, pet_w, pet_h
    )
    return (
        max(min_x, min(max_x, float(x))),
        max(min_y, min(max_y, float(y))),
    )
