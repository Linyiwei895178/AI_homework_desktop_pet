"""
Pet leveling rules: experience, level, coins, and bond score calculations.

Simple linear progression formulas. Tweak values in production.
"""

from __future__ import annotations

import math
from typing import Any, Dict


def exp_to_next_level(level: int) -> int:
    """
    Calculate experience points required to reach the next level.

    Formula: level * 100 + (level - 1) * 50
    Level 1 → 100, Level 2 → 250, Level 3 → 450, ...

    :param level: current level (>= 1)
    :returns: total exp needed to reach level+1
    """
    level = max(1, int(level))
    return level * 100 + (level - 1) * 50


def calculate_interaction_delta(action_type: str) -> Dict[str, int]:
    """
    Calculate state deltas for a given interaction type.

    :param action_type: "click", "feed", "play", "pet", "chat", "work", "level_up"
    :returns: dict with keys like exp, coins, energy, intimacy, hunger, bond_score
    """
    deltas = {
        "click": {"exp": 1, "coins": 0, "energy": -1, "intimacy": 2, "hunger": 0, "bond_score": 0},
        "feed": {"exp": 5, "coins": 0, "energy": 20, "intimacy": 5, "hunger": 30, "bond_score": 1},
        "play": {"exp": 3, "coins": 0, "energy": -10, "intimacy": 3, "hunger": -5, "bond_score": 0},
        "pet":  {"exp": 2, "coins": 0, "energy": 0, "intimacy": 4, "hunger": 0, "bond_score": 1},
        "chat":      {"exp": 1, "coins": 0, "energy": -1, "intimacy": 1, "hunger": 0, "bond_score": 0},
        "long_chat": {"exp": 3, "coins": 0, "energy": -5, "intimacy": 3, "hunger": -2, "bond_score": 1},
        "work": {"exp": 8, "coins": 15, "energy": -15, "intimacy": 0, "hunger": -10, "bond_score": 0},
        "study": {"exp": 6, "coins": 5, "energy": -10, "intimacy": 1, "hunger": -5, "bond_score": 0},
        "level_up": {"exp": 0, "coins": 50, "energy": 20, "intimacy": 10, "hunger": 0, "bond_score": 5},
    }
    return deltas.get(action_type, {"exp": 1, "coins": 0, "energy": 0, "intimacy": 0, "hunger": 0, "bond_score": 0})


def apply_leveling_state(state_dict: Dict[str, Any], action_type: str) -> Dict[str, Any]:
    """
    Apply interaction deltas to a state dict, including level-up logic.

    :param state_dict:  current state dict with level, exp, coins, etc.
    :param action_type: interaction type string
    :returns: updated state dict (mutates input dict in-place)
    """
    delta = calculate_interaction_delta(action_type)

    # Apply numeric deltas
    for key, value in delta.items():
        if key == "exp":
            state_dict["exp"] = state_dict.get("exp", 0) + value
        elif key == "coins":
            state_dict["coins"] = max(0, state_dict.get("coins", 0) + value)
        elif key == "energy":
            state_dict["energy"] = max(0, min(100, state_dict.get("energy", 100) + value))
        elif key == "intimacy":
            state_dict["intimacy"] = max(0, min(100, state_dict.get("intimacy", 50) + value))
        elif key == "hunger":
            state_dict["hunger"] = max(0, min(100, state_dict.get("hunger", 50) + value))
        elif key == "bond_score":
            state_dict["bond_score"] = max(0, state_dict.get("bond_score", 0) + value)

    # Check level-up
    level = state_dict.get("level", 1)
    exp = state_dict.get("exp", 0)
    next_exp = exp_to_next_level(level)
    if exp >= next_exp:
        level += 1
        state_dict["level"] = level
        state_dict["exp"] = exp - next_exp
        # Level-up bonus
        level_up_delta = calculate_interaction_delta("level_up")
        for k, v in level_up_delta.items():
            if k == "coins":
                state_dict["coins"] = state_dict.get("coins", 0) + v
            elif k == "energy":
                state_dict["energy"] = min(100, state_dict.get("energy", 100) + v)
            elif k == "intimacy":
                state_dict["intimacy"] = min(100, state_dict.get("intimacy", 50) + v)
            elif k == "bond_score":
                state_dict["bond_score"] = state_dict.get("bond_score", 0) + v
        state_dict["_leveled_up"] = True
        state_dict["_new_level"] = level

    return state_dict


def get_level_progress(level: int, exp: int) -> Dict[str, Any]:
    """
    Get level progress info.

    :param level: current level
    :param exp:   current exp
    :returns: dict with level, exp, next_level_exp, progress (0.0-1.0)
    """
    needed = exp_to_next_level(level)
    progress = min(1.0, exp / max(needed, 1))
    return {
        "level": level,
        "exp": exp,
        "next_level_exp": needed,
        "progress": round(progress, 4),
        "remaining": max(0, needed - exp),
    }
