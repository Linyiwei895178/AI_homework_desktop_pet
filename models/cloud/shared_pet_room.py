"""
SharedPetRoomManager: manages a shared pet room with cloud sync.

Provides join/pull/push/sync interfaces.
First version uses request-response sync (NOT realtime).
Conflict strategy: latest updated_at wins.

Usage:
    from models.cloud.cloud_service import SupabaseCloudService
    from models.cloud.shared_pet_room import SharedPetRoomManager

    svc = SupabaseCloudService()
    mgr = SharedPetRoomManager(svc, room_code="ROOM123")
    result = mgr.join_room("ROOM123", "MyPet")
    if result["ok"]:
        sync_result = mgr.sync_now(local_pet_state)
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

from models.cloud.cloud_models import CloudPetEvent, CloudPetState
from models.cloud.cloud_service import SupabaseCloudService
from utils.event_log import get_event_log


class SharedPetRoomManager:
    """
    Manage a shared pet room.

    - join_room: create or join a room by code.
    - sync_now: pull remote -> merge -> push local.
    - push_local_state: one-way push to cloud.
    - pull_remote_state: one-way pull from cloud.
    - append_interaction: log an interaction event.
    - fetch_recent_events: fetch recent cloud events.

    All public methods return:
        {"ok": bool, "error": str | None, "data": Any}

    When the underlying cloud service is not configured,
    methods return {"ok": False, "error": "not_configured", "data": None}.
    """

    def __init__(
        self,
        cloud_service: Optional[SupabaseCloudService] = None,
        room_code: Optional[str] = None,
    ):
        self._service = cloud_service or SupabaseCloudService()
        self._room_code: str = room_code or ""
        self._room_info: Dict[str, Any] = {}
        self._on_event: Optional[Callable[[Dict[str, Any]], None]] = None
        self._event_log = get_event_log()

    def set_on_event_callback(
        self, callback: Optional[Callable[[Dict[str, Any]], None]]
    ) -> None:
        """Register a callback for incoming cloud events."""
        self._on_event = callback

    def join_room(
        self, room_code: str, pet_name: str = "Echo"
    ) -> Dict[str, Any]:
        result = self._service.create_or_join_room(room_code, pet_name)
        if result.get("ok") and result.get("data"):
            self._room_code = room_code
            self._room_info = result["data"].get("room", {})
        return result

    def leave_room(self) -> Dict[str, Any]:
        self._room_code = ""
        self._room_info = {}
        return {"ok": True, "error": None, "data": {"left": True}}

    def is_in_room(self) -> bool:
        return bool(self._room_code)

    def get_room_code(self) -> str:
        return self._room_code

    def sync_now(self, local_pet_state: Any) -> Dict[str, Any]:
        if not self.is_in_room():
            return {"ok": False, "error": "not_in_room", "data": None}

        pull_result = self._service.fetch_cloud_pet_state(self._room_code)
        remote_pet = pull_result.get("data", {}).get("pet") if pull_result.get("ok") else None

        local_payload = self._build_payload(local_pet_state)

        merged = dict(local_payload)
        if remote_pet:
            remote_ts = remote_pet.get("updated_at") or ""
            local_ts = local_payload.get("updated_at") or ""
            if remote_ts > local_ts:
                for key in ("mood", "energy", "intimacy", "level", "exp",
                            "coins", "hunger", "bond_score", "pet_name", "pet_id"):
                    if key in remote_pet:
                        merged[key] = remote_pet[key]
                merged["updated_at"] = datetime.now(timezone.utc).isoformat()

        push_result = self._service.save_cloud_pet_state(self._room_code, merged)
        pushed_ok = push_result.get("ok", False)

        return {
            "ok": pushed_ok,
            "error": None if pushed_ok else push_result.get("error"),
            "data": {
                "pushed": pushed_ok,
                "pulled": bool(remote_pet),
                "merged": merged,
            },
        }

    def push_local_state(self, local_pet_state: Any) -> Dict[str, Any]:
        if not self.is_in_room():
            return {"ok": False, "error": "not_in_room", "data": None}
        payload = self._build_payload(local_pet_state)
        return self._service.save_cloud_pet_state(self._room_code, payload)

    def pull_remote_state(self) -> Dict[str, Any]:
        if not self.is_in_room():
            return {"ok": False, "error": "not_in_room", "data": None}
        return self._service.fetch_cloud_pet_state(self._room_code)

    def append_interaction(
        self,
        action_type: str,
        actor_name: str = "local",
        delta: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        if not self.is_in_room():
            return {"ok": False, "error": "not_in_room", "data": None}

        event = CloudPetEvent(
            event_type="interaction",
            action_type=action_type,
            actor_name=actor_name,
            delta=delta or {},
        )
        result = self._service.append_pet_event(self._room_code, event.to_dict())

        # ── 写入本地事件日志 ──
        self._event_log.append_event({
            "timestamp": time.time(),
            "event_type": action_type,
            "actor": actor_name,
            "pet_id": self._room_code,
            "delta": delta or {},
            "source": "cloud",
        })

        if result.get("ok") and self._on_event:
            self._on_event(event.to_dict())
        return result

    def fetch_recent_events(self, limit: int = 20) -> Dict[str, Any]:
        if not self.is_in_room():
            return {"ok": False, "error": "not_in_room", "data": None}
        return self._service.fetch_recent_pet_events(self._room_code, limit=limit)

    def _build_payload(self, state: Any) -> Dict[str, Any]:
        if hasattr(state, "to_dict") and callable(state.to_dict):
            raw = state.to_dict()
        elif isinstance(state, dict):
            raw = dict(state)
        else:
            raw = {
                "pet_id": getattr(state, "pet_id", "cat"),
                "pet_name": getattr(state, "pet_name", "Echo"),
                "level": getattr(state, "level", 1),
                "exp": getattr(state, "exp", 0),
                "coins": getattr(state, "coins", 0),
                "mood": getattr(state, "mood", "neutral"),
                "energy": getattr(state, "energy", 100),
                "intimacy": getattr(state, "intimacy", 50),
                "hunger": getattr(state, "hunger", 50),
                "bond_score": getattr(state, "bond_score", 0),
            }

        raw["updated_at"] = raw.get("updated_at") or datetime.now(timezone.utc).isoformat()
        return raw
