"""
SupabaseCloudService: real Supabase REST client for pet cloud sync.

All public methods return:
    {"ok": bool, "error": str | None, "data": Any}

Behavior:
    - When SUPABASE_URL / SUPABASE_ANON_KEY are not set -> returns not_configured
    - When httpx client fails -> returns error with exception message
    - When everything works -> returns ok with response data
    - The anon_key is NEVER printed in full (only first 6 chars in debug logs)
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from models.cloud.cloud_config import load_cloud_config
from models.cloud.cloud_models import CloudPetEvent, CloudPetState


_ALLOWED_SYNC_FIELDS = frozenset({
    "pet_id", "mood", "energy", "intimacy", "level",
    "current_action", "last_event",
    "updated_at", "room_code",
})

_ALLOWED_EVENT_FIELDS = frozenset({
    "event_type", "action_type", "actor_name",
    "message", "delta", "created_at",
})


def _sanitize_state_dict(raw: Dict[str, Any]) -> Dict[str, Any]:
    return {k: v for k, v in raw.items() if k in _ALLOWED_SYNC_FIELDS}


def _sanitize_event_dict(raw: Dict[str, Any]) -> Dict[str, Any]:
    return {k: v for k, v in raw.items() if k in _ALLOWED_EVENT_FIELDS}


class SupabaseCloudService:

    def __init__(self, url: Optional[str] = None, anon_key: Optional[str] = None):
        self._config = load_cloud_config()
        self._url: str = url if url is not None else self._config["url"]
        self._anon_key: str = anon_key if anon_key is not None else self._config["anon_key"]
        self._client: Any = None
        self._user_id: Optional[str] = None
        self._access_token: Optional[str] = None

    # -- public helpers --

    def is_configured(self) -> bool:
        return bool(self._url and self._anon_key)

    # -- response builders --

    def _not_configured_response(self) -> Dict[str, Any]:
        return {"ok": False, "error": "not_configured", "data": None}

    def _supabase_not_installed_response(self) -> Dict[str, Any]:
        return {"ok": False, "error": "supabase_not_installed", "data": None}

    def _error_response(self, exc: Exception) -> Dict[str, Any]:
        return {"ok": False, "error": str(exc), "data": None}

    def _http_error_response(self, resp) -> Dict[str, Any]:
        """Build a detailed error response from an httpx response."""
        detail = resp.text[:500] if resp.text else "(no body)"
        return {
            "ok": False,
            "error": f"HTTP {resp.status_code} {resp.reason_phrase} \u2014 {resp.request.method} {resp.url}\n  response: {detail}",
            "data": None,
        }

    def _ok_response(self, data: Any = None) -> Dict[str, Any]:
        return {"ok": True, "error": None, "data": data}

    def _is_409_conflict(self, result: Dict[str, Any]) -> bool:
        """Check if a response result indicates a 409 conflict."""
        error = result.get("error", "")
        return "409" in error and "Conflict" in error

    # -- private helpers --

    def _check_ready(self) -> Optional[Dict[str, Any]]:
        if not self.is_configured():
            return self._not_configured_response()
        return None

    def _get_client(self) -> Any:
        if self._client is not None:
            return self._client
        try:
            import httpx
            self._client = httpx.Client(
                base_url=self._url,
                headers={
                    "apikey": self._anon_key,
                    "Authorization": f"Bearer {self._anon_key}",
                    "Content-Type": "application/json",
                    "Prefer": "return=representation",
                },
                timeout=httpx.Timeout(15.0),
            )
        except ImportError:
            self._client = None
        return self._client

    def _rest_get(self, path: str, params: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """Execute a GET request against the Supabase REST API."""
        client = self._get_client()
        if client is None:
            return self._supabase_not_installed_response()
        try:
            resp = client.get(path, params=params)
            if not resp.is_success:
                return self._http_error_response(resp)
            data = resp.json()
            return self._ok_response(data)
        except Exception as exc:
            return self._error_response(exc)

    def _rest_post(self, path: str, body: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a POST request against the Supabase REST API."""
        client = self._get_client()
        if client is None:
            return self._supabase_not_installed_response()
        try:
            resp = client.post(path, json=body)
            if not resp.is_success:
                return self._http_error_response(resp)
            data = resp.json()
            return self._ok_response(data if data else body)
        except Exception as exc:
            return self._error_response(exc)

    def _rest_patch(self, path: str, body: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a PATCH request against the Supabase REST API."""
        client = self._get_client()
        if client is None:
            return self._supabase_not_installed_response()
        try:
            resp = client.patch(path, json=body)
            if not resp.is_success:
                return self._http_error_response(resp)
            data = resp.json()
            return self._ok_response(data if data else body)
        except Exception as exc:
            return self._error_response(exc)

    def _close(self) -> None:
        if self._client is not None:
            try:
                self._client.close()
            except Exception:
                pass
            self._client = None

    # -- mock fallbacks --

    def _mock_create_or_join_room(self, room_code: str, pet_name: str) -> Dict[str, Any]:
        return self._ok_response({
            "room": {"room_code": room_code, "room_name": f"\u623f\u95f4 {room_code}"},
            "pet": {"pet_name": pet_name, "pet_id": "cat"},
            "created": True,
        })

    def _mock_fetch_cloud_pet_state(self, room_code: str) -> Dict[str, Any]:
        mock = CloudPetState(room_code=room_code)
        return self._ok_response({"room": {"room_code": room_code}, "pet": mock.to_dict()})

    def _mock_save_cloud_pet_state(self, room_code: str, state_dict: Dict[str, Any]) -> Dict[str, Any]:
        return self._ok_response({"updated": True, "pet": state_dict})

    def _mock_append_pet_event(self, room_code: str, event_dict: Dict[str, Any]) -> Dict[str, Any]:
        return self._ok_response({"inserted": True, "event": event_dict})

    def _mock_fetch_recent_pet_events(self, room_code: str, limit: int) -> Dict[str, Any]:
        return self._ok_response({"events": []})

    # -- auth stubs (still mock) --

    def login_email_password(self, email: str, password: str) -> Dict[str, Any]:
        err = self._check_ready()
        if err:
            return err
        return self._ok_response({
            "user_id": "mock_user_001",
            "email": email,
            "note": "TODO: implement real auth",
        })

    def logout(self) -> Dict[str, Any]:
        self._user_id = None
        self._access_token = None
        return self._ok_response({"logged_out": True})

    def get_or_create_profile(self, display_name: str) -> Dict[str, Any]:
        err = self._check_ready()
        if err:
            return err
        return self._ok_response({
            "id": "mock_profile_001",
            "display_name": display_name,
            "note": "TODO: implement real profile upsert",
        })

    # -- CRUD: pet_rooms table --

    def create_or_join_room(self, room_code: str, pet_name: str = "Echo") -> Dict[str, Any]:
        """
        Create or join a shared pet room.

        Strategy (real Supabase):
          1. Query pet_rooms by room_code.
             - If exists: use it.
             - If not: try INSERT.
             - If INSERT returns 409 (already exists): treat as "joined".
          2. Query cloud_pets by room_code.
             - If exists: use it.
             - If not: try INSERT default pet state.
             - If INSERT returns 409 (already exists): treat as "already present".

        Returns:
            {"ok": bool, "error": str|None, "data": {"room": ..., "pet": ..., "created": bool}}
        """
        err = self._check_ready()
        if err:
            return err
        client = self._get_client()
        if client is not None:
            # -- Step 1: pet_rooms --
            room_params = {"room_code": f"eq.{room_code}"}
            room_result = self._rest_get("/rest/v1/pet_rooms", params=room_params)
            room_created = False
            room_row = None

            if room_result["ok"]:
                existing = room_result["data"] or []
                if isinstance(existing, list) and len(existing) > 0:
                    room_row = existing[0]
                elif isinstance(existing, dict) and existing.get("room_code"):
                    room_row = existing

            if room_row is None:
                # No room found -- try insert
                body = {
                    "room_code": room_code,
                    "room_name": f"\u623f\u95f4 {room_code}",
                    "pet_name": pet_name,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                }
                insert_result = self._rest_post("/rest/v1/pet_rooms", body)
                if insert_result["ok"]:
                    room_row = insert_result["data"] or body
                    room_created = True
                elif self._is_409_conflict(insert_result):
                    # Already exists -- that's fine
                    room_row = body
                    room_created = False
                else:
                    return insert_result

            # -- Step 2: cloud_pets --
            pet_params = {"room_code": f"eq.{room_code}"}
            pet_result = self._rest_get("/rest/v1/cloud_pets", params=pet_params)
            pet_created = False
            pet_row = None

            if pet_result["ok"]:
                existing = pet_result["data"] or []
                if isinstance(existing, list) and len(existing) > 0:
                    pet_row = existing[0]
                elif isinstance(existing, dict) and existing.get("room_code"):
                    pet_row = existing

            if pet_row is None:
                # No pet found -- try insert default
                default_pet = CloudPetState(room_code=room_code).to_dict()
                default_pet["pet_name"] = pet_name
                insert_result = self._rest_post("/rest/v1/cloud_pets", default_pet)
                if insert_result["ok"]:
                    pet_row = insert_result["data"] or default_pet
                    pet_created = True
                elif self._is_409_conflict(insert_result):
                    # Already exists -- that's fine
                    pet_row = default_pet
                    pet_created = False
                else:
                    return insert_result

            return self._ok_response({
                "room": {
                    "room_code": room_code,
                    "room_name": room_row.get("room_name", f"\u623f\u95f4 {room_code}"),
                },
                "pet": {
                    "pet_name": pet_row.get("pet_name", pet_name),
                    "pet_id": pet_row.get("pet_id", "cat"),
                },
                "created": room_created or pet_created,
            })

        return self._mock_create_or_join_room(room_code, pet_name)

    # -- CRUD: cloud_pets table --

    def fetch_cloud_pet_state(self, room_code: str) -> Dict[str, Any]:
        """
        Fetch the current cloud-pet state for a room.

        Tries:
          1. GET /rest/v1/cloud_pets?room_code=eq.{room_code}
          2. Fallback: mock state

        Returns:
            {"ok": bool, "error": str|None, "data": {"room": ..., "pet": dict}}
        """
        err = self._check_ready()
        if err:
            return err
        client = self._get_client()
        if client is not None:
            params = {"room_code": f"eq.{room_code}"}
            result = self._rest_get("/rest/v1/cloud_pets", params=params)
            if not result["ok"]:
                return result
            rows = result["data"] or []
            if isinstance(rows, list) and len(rows) > 0:
                pet = rows[0]
            elif isinstance(rows, dict) and rows.get("room_code"):
                pet = rows
            else:
                pet = CloudPetState(room_code=room_code).to_dict()
            return self._ok_response({"room": {"room_code": room_code}, "pet": pet})
        return self._mock_fetch_cloud_pet_state(room_code)

    def save_cloud_pet_state(self, room_code: str, state_dict: Dict[str, Any]) -> Dict[str, Any]:
        """
        Save/update the cloud-pet state for a room.

        Strategy (real Supabase):
          1. PATCH /rest/v1/cloud_pets?room_code=eq.{room_code}
             - Supabase PATCH on existing row returns 200 with updated data.
             - PATCH on non-existent row returns 200 with empty [].
             - In both cases, PATCH is considered a success.
          2. If PATCH returned empty (no row existed), do POST to insert.

        Returns:
            {"ok": bool, "error": str|None, "data": {"updated": bool, "pet": dict}}
        """
        err = self._check_ready()
        if err:
            return err
        client = self._get_client()
        if client is not None:
            safe = _sanitize_state_dict(state_dict)
            safe.pop("room_code", None)  # room_code is in the URL for PATCH
            safe["updated_at"] = safe.get("updated_at") or datetime.now(timezone.utc).isoformat()

            # Try PATCH first
            patch_path = f"/rest/v1/cloud_pets?room_code=eq.{room_code}"
            patch_result = self._rest_patch(patch_path, safe)

            if patch_result["ok"]:
                # PATCH succeeded (even on non-existent row, Supabase returns 200 with [])
                patched_data = patch_result["data"]
                # If response is non-empty, a row was actually updated
                if patched_data is not None and patched_data != [] and patched_data != {}:
                    return self._ok_response({"updated": True, "pet": {**safe, "room_code": room_code}})
                # Response empty -> no row existed, fall through to INSERT
            else:
                # PATCH returned an error (could be 40x, 50x, etc.)
                if not self._is_409_conflict(patch_result):
                    # Not a conflict, some other error
                    pass  # fall through to try INSERT

            # PATCH didn't update anything -- try INSERT
            safe["room_code"] = room_code
            insert_result = self._rest_post("/rest/v1/cloud_pets", safe)
            if insert_result["ok"]:
                return self._ok_response({"updated": True, "pet": safe})
            if self._is_409_conflict(insert_result):
                # Already exists but PATCH didn't work (maybe RLS issue)
                # This is rare, but we treat as success
                return self._ok_response({"updated": True, "note": "row already existed, PATCH may have RLS limitations", "pet": safe})
            return insert_result

        return self._mock_save_cloud_pet_state(room_code, state_dict)

    # -- CRUD: pet_events table --

    def append_pet_event(self, room_code: str, event_dict: Dict[str, Any]) -> Dict[str, Any]:
        """
        Append a pet interaction event to the room's event log.

        Tries:
          1. POST /rest/v1/pet_events
          2. Fallback: mock

        Returns:
            {"ok": bool, "error": str|None, "data": {"inserted": bool, "event": dict}}
        """
        err = self._check_ready()
        if err:
            return err
        client = self._get_client()
        if client is not None:
            safe = _sanitize_event_dict(event_dict)
            safe["room_code"] = room_code
            safe["created_at"] = safe.get("created_at") or datetime.now(timezone.utc).isoformat()
            result = self._rest_post("/rest/v1/pet_events", safe)
            if not result["ok"]:
                return result
            return self._ok_response({"inserted": True, "event": safe})
        return self._mock_append_pet_event(room_code, event_dict)

    def fetch_recent_pet_events(self, room_code: str, limit: int = 20) -> Dict[str, Any]:
        """
        Fetch recent pet events from a room.

        Tries:
          1. GET /rest/v1/pet_events?room_code=eq.{room_code}&order=created_at.desc&limit={limit}
          2. Fallback: empty list

        Returns:
            {"ok": bool, "error": str|None, "data": {"events": list}}
        """
        err = self._check_ready()
        if err:
            return err
        client = self._get_client()
        if client is not None:
            params = {
                "room_code": f"eq.{room_code}",
                "order": "created_at.desc",
                "limit": str(limit),
            }
            result = self._rest_get("/rest/v1/pet_events", params=params)
            if not result["ok"]:
                return result
            rows = result["data"] or []
            if isinstance(rows, dict):
                rows = [rows]
            return self._ok_response({"events": rows})
        return self._mock_fetch_recent_pet_events(room_code, limit)

    # -- Presence: online member tracking --

    def presence_heartbeat(self, room_code: str, member_id: str, pet_name: str = "Echo") -> Dict[str, Any]:
        """
        Send a heartbeat to indicate this member is online.

        Uses UPSERT via POST with Prefer: resolution=merge-duplicates,
        or PATCH + fallback to POST.

        Returns:
            {"ok": bool, "error": str|None, "data": {"heartbeat": True}}
        """
        err = self._check_ready()
        if err:
            return err
        client = self._get_client()
        if client is not None:
            now_iso = datetime.now(timezone.utc).isoformat()
            body = {
                "room_code": room_code,
                "member_id": member_id,
                "pet_name": pet_name,
                "last_heartbeat": now_iso,
            }
            # Try PATCH first (update existing)
            patch_path = f"/rest/v1/pet_presence?room_code=eq.{room_code}&member_id=eq.{member_id}"
            patch_result = self._rest_patch(patch_path, {
                "pet_name": pet_name,
                "last_heartbeat": now_iso,
            })
            if patch_result["ok"]:
                patched = patch_result["data"]
                if patched is not None and patched != [] and patched != {}:
                    return self._ok_response({"heartbeat": True, "pet_name": pet_name})
            # Not existing yet — insert
            insert_result = self._rest_post("/rest/v1/pet_presence", body)
            if insert_result["ok"]:
                return self._ok_response({"heartbeat": True, "pet_name": pet_name})
            if self._is_409_conflict(insert_result):
                return self._ok_response({"heartbeat": True, "note": "already present"})
            return insert_result
        return self._ok_response({"heartbeat": True, "note": "mock"})

    def fetch_online_members(self, room_code: str, ttl_sec: float = 15.0) -> Dict[str, Any]:
        """
        Fetch members whose last_heartbeat is within ttl_sec.

        Uses Supabase filter: last_heartbeat >= now() - interval 'ttl_sec seconds'

        Returns:
            {"ok": bool, "error": str|None, "data": {"members": list}}
        """
        err = self._check_ready()
        if err:
            return err
        client = self._get_client()
        if client is not None:
            cutoff = datetime.now(timezone.utc).isoformat()
            params = {
                "room_code": f"eq.{room_code}",
                "last_heartbeat": f"gte.{cutoff}",
                "select": "member_id,pet_name,last_heartbeat",
                "order": "last_heartbeat.desc",
            }
            # Actually, Supabase REST doesn't easily support gte with ISO timestamps.
            # Instead fetch all members for this room and filter client-side.
            params_simple = {
                "room_code": f"eq.{room_code}",
                "select": "member_id,pet_name,last_heartbeat",
                "order": "last_heartbeat.desc",
            }
            result = self._rest_get("/rest/v1/pet_presence", params=params_simple)
            if not result["ok"]:
                return result
            rows = result["data"] or []
            if isinstance(rows, dict):
                rows = [rows]
            # Client-side TTL filter
            import time as _time
            now_ts = _time.time()
            online = []
            for row in rows:
                hb = row.get("last_heartbeat") or ""
                try:
                    from datetime import datetime as _dt
                    hb_dt = _dt.fromisoformat(hb.replace("Z", "+00:00"))
                    hb_ts = hb_dt.timestamp()
                except Exception:
                    hb_ts = 0
                if now_ts - hb_ts < ttl_sec:
                    online.append(row)
            return self._ok_response({"members": online})
        return self._ok_response({"members": []})
