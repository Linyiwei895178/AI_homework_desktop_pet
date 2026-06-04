"""
Cloud / Supabase integration for shared pet rooms.

Modules:
    cloud_config         - load_cloud_config() -> dict
    cloud_models         - CloudPetState, CloudPetEvent (dataclasses)
    cloud_service        - SupabaseCloudService
    shared_pet_room      - SharedPetRoomManager
"""

from models.cloud.cloud_config import load_cloud_config
from models.cloud.cloud_models import CloudPetState, CloudPetEvent
from models.cloud.cloud_service import SupabaseCloudService
from models.cloud.shared_pet_room import SharedPetRoomManager

__all__ = [
    "load_cloud_config",
    "CloudPetState",
    "CloudPetEvent",
    "SupabaseCloudService",
    "SharedPetRoomManager",
]
