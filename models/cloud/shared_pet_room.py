"""
SharedPetRoomManager: manages a shared pet room with cloud sync.

Provides join/pull/push/sync interfaces.
Actual conflict resolution is a TODO for later versions.
"""

from __future__ import annotations

import time
from typing import Any, Callable, Dict, List, Optional

from models.cloud.cloud_models import CloudPetEvent, CloudPetState
from models.cloud.cloud_service import SupabaseCloudService


class SharedPetRoomManager:
    """
    Manage a shared pet room.

    Current version:
    - Always uses "latest updated_at wins" for conflict resolution.
    - Does NOT actually call Supabase if not configured.

    # TODO: Implement event-based incremental merge (version 2).
    # TODO: Add offline queue and retry logic.
    """

    def __init__(self, cloud_service: Optional[SupabaseCloudService] = None):
        self._service = cloud_service or SupabaseCloudService()
        self._room_id: str = ""
        self._room_info: Dict[str, Any] = {}
        self._on_event: Optional[Callable[[Dict[str, Any]], None]] = None

    def set_on_event_callback(self, callback: Optional[Callable[[Dict[str, Any]], None]]) -> None:
        """Register a callback for incoming cloud events."""
        self._on_event = callback

    def join_room(self, room_id: str, pet_name: str = "Echo") -> bool:
        """
        Join (or create) a shared pet room.

        :param room_id:  room identifier
        :param pet_name: name for the active pet in this room
        :returns:        True on success
        """
        result = self._service.create_or_join_room(room_id, pet_name)
        if result.get("success"):
            self._room_id = room_id
            self._room_info = result.get("room", {})
            print(f"[SharedPetRoomManager] Joined room: {room_id}")
            return True
        print(f"[SharedPetRoomManager] Failed to join room: {result.get('error')}")
        return False

    def leave_room(self) -> None:
        """Leave the current room."""
        self._room_id = ""
        self._room_info = {}

    def is_in_room(self) -> bool:
        """True if currently in a room."""
        return bool(self._room_id)

    def get_room_id(self) -> str:
        return self._room_id

    def sync_now(self, local_pet_state: Any) -> bool:
        """
        Perform a full sync cycle: push local then pull remote.

        :param local_pet_state: PetState instance or dict
        :returns: True if sync succeeded
        """
        if not self.is_in_room():
            return False

        # Push local
        payload = self._build_payload(local_pet_state)
        push_result = self._service.save_cloud_pet_state(self._room_id, payload)
        if not push_result.get("success"):
            return False

        # Pull remote
        pull_result = self._service.fetch_cloud_pet_state(self._room_id)
        if pull_result.get("success") and pull_result.get("state"):
            self._on_state_pulled(pull_result["state"])

        return True

    def push_local_state(self, local_pet_state: Any) -> bool:
        """
        Push local pet state to the cloud (one-way).

        :param local_pet_state: PetState instance or dict
        :returns: True on success
        """
        if not self.is_in_room():
            return False
        payload = self._build_payload(local_pet_state)
        result = self._service.save_cloud_pet_state(self._room_id, payload)
        return bool(result.get("success"))

    def pull_remote_state(self) -> Optional[Dict[str, Any]]:
        """
        Pull remote pet state from the cloud.

        :returns: state dict or None
        """
        if not self.is_in_room():
            return None
        result = self._service.fetch_cloud_pet_state(self._room_id)
        if result.get("success"):
            return result.get("state")
        return None

    def append_interaction(self, action_type: str, actor_name: str, delta: Optional[Dict[str, float]] = None) -> bool:
        """
        Record an interaction event to the cloud.

        :param action_type: e.g. "feed", "play", "pet", "level_up"
        :param actor_name:  who performed the action
        :param delta:       state changes (e.g. {"intimacy": 5, "energy": -3})
        :returns:           True on success
        """
        if not self.is_in_room():
            return False
        event = CloudPetEvent(
            room_id=self._room_id,
            actor=actor_name,
            action_type=action_type,
            delta=delta or {},
        )
        result = self._service.append_pet_event(self._room_id, event.to_dict())
        if result.get("success") and self._on_event:
            self._on_event(event.to_dict())
        return bool(result.get("success"))

    def fetch_recent_events(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Fetch recent cloud events."""
        if not self.is_in_room():
            return []
        result = self._service.fetch_recent_pet_events(self._room_id, limit=limit)
        return result.get("events", [])

    # ── Internal helpers ──

    def _build_payload(self, state: Any) -> Dict[str, Any]:
        """Convert PetState (or dict) to a flat dict for cloud storage."""
        if isinstance(state, dict):
            payload = dict(state)
        else:
            payload = {
                "pet_id": getattr(state, "pet_id", "cat"),
                "level": getattr(state, "level", 1),
                "exp": getattr(state, "exp", 0),
                "coins": getattr(state, "coins", 0),
                "mood": getattr(state, "mood", "neutral"),
                "energy": getattr(state, "energy", 100),
                "intimacy": getattr(state, "intimacy", 50),
                "hunger": getattr(state, "hunger", 50),
                "bond_score": getattr(state, "bond_score", 0),
            }
        payload["updated_at"] = time.time()
        payload["room_id"] = self._room_id
        return payload

    def _on_state_pulled(self, state_dict: Dict[str, Any]) -> None:
        """
        Called when remote state is fetched.
        # TODO: Notify AppContext / EchoTeamDInterface to apply remote state.
        """
        pass
