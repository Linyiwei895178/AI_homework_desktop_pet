"""
AppContext: central data class holding all module instances.

Makes it easy to pass around pet/team_c/team_d/profile/cloud references
without modifying every constructor.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class AppContext:
    """
    Central application context.

    All fields are optional; they are populated as modules are initialized.
    """

    # Team A - UI
    pet: Optional[Any] = None
    pet_controller: Optional[Any] = None
    event_handler: Optional[Any] = None

    # Team B - Vision
    user_state_detector: Optional[Any] = None
    computer_activity_detector: Optional[Any] = None
    screen_usage_tracker: Optional[Any] = None
    gesture_detector: Optional[Any] = None

    # Team C - NLP/TTS
    team_c: Optional[Any] = None  # EchoTeamCInterface
    deepseek_client: Optional[Any] = None

    # Team D - State
    team_d: Optional[Any] = None  # EchoTeamDInterface
    pet_state: Optional[Any] = None

    # Cloud
    cloud_manager: Optional[Any] = None  # SharedPetRoomManager
    cloud_service: Optional[Any] = None

    # Profile
    user_profile: Optional[Any] = None

    # Event bus
    event_bus: Optional[Any] = None

    # Cloud sync scheduler
    sync_scheduler: Optional[Any] = None

    # Extra storage for loose references
    extra: Dict[str, Any] = field(default_factory=dict)

    def __repr__(self) -> str:
        fields = []
        for name, val in self.__dict__.items():
            if name == "extra":
                continue
            if val is not None:
                fields.append(f"{name}={type(val).__name__}")
        return f"AppContext({', '.join(fields)})"
