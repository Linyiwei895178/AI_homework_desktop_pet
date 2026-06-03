"""
Cloud data models: dataclasses for cloud-pet state and events.

All models provide to_dict() and from_dict() for JSON serialization.
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional


# ──────────────────────────────────────────────
# CloudPetState
# ──────────────────────────────────────────────


@dataclass
class CloudPetState:
    """Serializable cloud-pet state that can be synced across devices."""

    room_code: str = ""
    pet_name: str = "Echo"
    pet_id: str = "cat"
    mood: str = "neutral"
    energy: int = 100
    intimacy: int = 50
    level: int = 1
    exp: int = 0
    coins: int = 0
    hunger: int = 50
    bond_score: int = 0
    updated_at: Optional[str] = None
    updated_by: Optional[str] = None

    # ── internal tracking ──
    _extra: Dict[str, Any] = field(default_factory=dict, repr=False)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to a plain dict, excluding internal `_extra` and private fields."""
        result: Dict[str, Any] = {}
        for f in dataclasses.fields(self):
            if f.name.startswith("_"):
                continue
            val = getattr(self, f.name)
            if val is not None or f.name in (
                "room_code", "pet_name", "pet_id", "mood",
                "energy", "intimacy", "level", "exp", "coins",
                "hunger", "bond_score",
            ):
                result[f.name] = val
        # Merge extra keys
        for k, v in self._extra.items():
            if k not in result:
                result[k] = v
        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CloudPetState":
        """Create an instance from a plain dict; unknown keys go to _extra."""
        known = {f.name for f in dataclasses.fields(cls) if not f.name.startswith("_")}
        kwargs: Dict[str, Any] = {}
        extra: Dict[str, Any] = {}
        for k, v in data.items():
            if k in known:
                kwargs[k] = v
            else:
                extra[k] = v
        obj = cls(**kwargs)
        obj._extra = extra
        return obj


# ──────────────────────────────────────────────
# CloudPetEvent
# ──────────────────────────────────────────────


@dataclass
class CloudPetEvent:
    """An interaction event record logged to the cloud."""

    event_type: str = "interaction"
    action_type: Optional[str] = None
    actor_name: str = "队友"
    message: Optional[str] = None
    delta: Dict[str, Any] = field(default_factory=dict)
    created_at: Optional[str] = None

    # internal
    _extra: Dict[str, Any] = field(default_factory=dict, repr=False)

    def to_dict(self) -> Dict[str, Any]:
        result: Dict[str, Any] = {}
        for f in dataclasses.fields(self):
            if f.name.startswith("_"):
                continue
            val = getattr(self, f.name)
            if val is not None:
                result[f.name] = val
        for k, v in self._extra.items():
            if k not in result:
                result[k] = v
        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CloudPetEvent":
        known = {f.name for f in dataclasses.fields(cls) if not f.name.startswith("_")}
        kwargs: Dict[str, Any] = {}
        extra: Dict[str, Any] = {}
        for k, v in data.items():
            if k in known:
                kwargs[k] = v
            else:
                extra[k] = v
        obj = cls(**kwargs)
        obj._extra = extra
        return obj
