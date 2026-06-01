"""
SupabaseCloudService: Supabase REST client for pet cloud sync.

All methods are structured to return manageable dicts.
When Supabase is not configured, methods return not_configured indicators.

# TODO: Connect to real Supabase REST API.
# TODO: Add proper error handling with retries.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from models.cloud.cloud_config import CloudConfig
from models.cloud.cloud_models import CloudPetEvent, CloudPetState


class SupabaseCloudService:
    """
    Supabase-backed cloud service for shared pet rooms.

    Currently all methods return mock data or not_configured responses.
    """

    def __init__(self):
        self._config = CloudConfig()
        self._user_id: Optional[str] = None
        self._access_token: Optional[str] = None

    def is_configured(self) -> bool:
        """True if both SUPABASE_URL and SUPABASE_ANON_KEY are set."""
        return self._config.is_configured

    def login_email_password(self, email: str, password: str) -> Dict[str, Any]:
        """
        Authenticate with Supabase Auth using email & password.

        # TODO: Connect Supabase auth REST API.
        """
        if not self.is_configured():
            return {"success": False, "error": "not_configured", "user": None}
        # TODO: POST /auth/v1/token?grant_type=password
        return {
            "success": True,
            "user": {"id": "mock_user_001", "email": email},
            "access_token": "mock_token",
        }

    def logout(self) -> Dict[str, Any]:
        """Log out the current user."""
        self._user_id = None
        self._access_token = None
        return {"success": True}

    def get_or_create_profile(self, display_name: str) -> Dict[str, Any]:
        """
        Get or create a user profile.

        # TODO: Upsert to `profiles` table.
        """
        if not self.is_configured():
            return {"success": False, "error": "not_configured", "profile": None}
        return {
            "success": True,
            "profile": {
                "id": "mock_profile_001",
                "display_name": display_name,
                "created_at": "2025-01-01T00:00:00Z",
            },
        }

    def create_or_join_room(self, room_id: str, pet_name: str = "Echo") -> Dict[str, Any]:
        """
        Create or join a shared pet room.

        :param room_id:   room identifier string
        :param pet_name:  name for the active pet in this room
        :returns:         dict with room info
        # TODO: Upsert to `pet_rooms` and `cloud_pets` tables.
        """
        if not self.is_configured():
            return {"success": False, "error": "not_configured", "room": None}
        return {
            "success": True,
            "room": {
                "room_id": room_id,
                "pet_name": pet_name,
                "member_count": 1,
                "created_at": "2025-01-01T00:00:00Z",
            },
        }

    def fetch_cloud_pet_state(self, room_id: str) -> Dict[str, Any]:
        """
        Fetch the current cloud-pet state for a room.

        :param room_id: room identifier
        :returns:       dict with pet state fields
        # TODO: GET /rest/v1/cloud_pets?room_id=eq.{room_id}
        """
        if not self.is_configured():
            return {"success": False, "error": "not_configured", "state": None}
        # Return a mock state
        mock_state = CloudPetState(
            pet_id="cat",
            level=1,
            exp=0,
            coins=0,
            mood="neutral",
            energy=100,
            intimacy=50,
            hunger=50,
            bond_score=0,
        )
        return {"success": True, "state": mock_state.to_dict()}

    def save_cloud_pet_state(self, room_id: str, state_dict: Dict[str, Any]) -> Dict[str, Any]:
        """
        Save/update the cloud-pet state for a room.

        :param room_id:   room identifier
        :param state_dict: dict with pet state fields
        :returns:         dict with success/error
        # TODO: UPSERT /rest/v1/cloud_pets
        """
        if not self.is_configured():
            return {"success": False, "error": "not_configured"}
        return {"success": True, "state": state_dict}

    def append_pet_event(self, room_id: str, event_dict: Dict[str, Any]) -> Dict[str, Any]:
        """
        Append a pet interaction event to the room's event log.

        :param room_id:   room identifier
        :param event_dict: event data dict
        :returns:         dict with success/error
        # TODO: INSERT /rest/v1/pet_events
        """
        if not self.is_configured():
            return {"success": False, "error": "not_configured"}
        return {"success": True, "event": event_dict}

    def fetch_recent_pet_events(self, room_id: str, limit: int = 20) -> Dict[str, Any]:
        """
        Fetch recent pet events from a room.

        :param room_id: room identifier
        :param limit:   max events to fetch
        :returns:       dict with events list
        # TODO: GET /rest/v1/pet_events?room_id=eq.{room_id}&order=created_at.desc&limit={limit}
        """
        if not self.is_configured():
            return {"success": False, "error": "not_configured", "events": []}
        return {"success": True, "events": []}
