"""
Minimal cloud co-parenting event models.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class CloudPetEvent:
    actor_name: str = "队友"
    action_type: str = "update"
    pet_name: str = "小宠物"
    level: int | None = None
    exp_gain: int | None = None
    coins_gain: int | None = None
    bond_bonus: int | float | None = None
