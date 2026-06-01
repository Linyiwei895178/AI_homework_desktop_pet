"""
Cloud data models: CloudPetState and CloudPetEvent.

These dataclasses define the schema for cloud sync payloads.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional


@dataclass
class CloudPetState:
    """
    Pet state snapshot for cloud sync.

    All numeric fields have defaults so the dict can be incomplete.
    """
    pet_id: str = "cat"
    level: int = 1
    exp: int = 0
    coins: int = 0
    mood: str = "neutral"
    energy: int = 100
    intimacy: int = 50
    hunger: int = 50
    bond_score: int = 0
    updated_at: float = 0.0

    def __post_init__(self):
        if not self.updated_at:
            self.updated_at = time.time()

    def to_dict(self) -> Dict[str, Any]:
        """Convert to a plain dict for JSON serialization."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CloudPetState":
        """Create from a dict, ignoring unknown keys."""
        known = {f.name for f in cls.__dataclass_fields__}
        filtered = {k: v for k, v in data.items() if k in known and v is not None}
        return cls(**filtered)


@dataclass
class CloudPetEvent:
    """
    A single pet interaction event for cloud sync.

    Examples: "pet", "feed", "play", "level_up", "chat"
    """
    room_id: str = ""
    actor: str = "local"
    action_type: str = "pet"
    target_pet_id: str = "cat"
    delta: Dict[str, float] = field(default_factory=dict)
    message: str = ""
    created_at: float = 0.0

    def __post_init__(self):
        if not self.created_at:
            self.created_at = time.time()

    def to_dict(self) -> Dict[str, Any]:
        """Convert to a plain dict for JSON serialization."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CloudPetEvent":
        """Create from a dict, ignoring unknown keys."""
        known = {f.name for f in cls.__dataclass_fields__}
        filtered = {k: v for k, v in data.items() if k in known and v is not None}
        return cls(**filtered)
