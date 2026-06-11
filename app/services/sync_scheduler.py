"""
CloudSyncScheduler: dual-frequency periodic cloud sync.

Two independent timers:
  - State sync: every 3-5 seconds (pet mood/energy/intimacy/level/action/event)
  - Presence sync: every 5-10 seconds (online member heartbeat + fetch)

Plus: instant event sync is handled by EventHandler, not by this scheduler.

Usage:
    scheduler = CloudSyncScheduler(
        cloud_manager=my_manager,
        state_interval_sec=4.0,
        presence_interval_sec=8.0,
    )
    scheduler.set_member_id("user_abc")
    scheduler.set_local_state_provider(lambda: my_pet_state)
    scheduler.start()
"""

from __future__ import annotations

import threading
import time
from typing import Any, Callable, Optional


class CloudSyncScheduler:
    """Dual-frequency cloud sync manager."""

    def __init__(
        self,
        cloud_manager: Optional[Any] = None,
        state_interval_sec: float = 4.0,
        presence_interval_sec: float = 8.0,
    ):
        """
        :param cloud_manager: SharedPetRoomManager instance (or None)
        :param state_interval_sec: state sync interval (3-5 sec recommended)
        :param presence_interval_sec: presence sync interval (5-10 sec recommended)
        """
        self.cloud_manager = cloud_manager
        self.state_interval_sec = max(3.0, min(5.0, float(state_interval_sec)))
        self.presence_interval_sec = max(5.0, min(10.0, float(presence_interval_sec)))

        self._running = False
        self._stop_event = threading.Event()
        self._state_thread: Optional[threading.Thread] = None
        self._presence_thread: Optional[threading.Thread] = None

        self._member_id: str = ""
        self._pet_name: str = "Echo"

        # Callbacks
        self._on_sync_result: Optional[Callable[[bool, str], None]] = None
        self._on_members_update: Optional[Callable[[list], None]] = None
        self._local_state_provider: Optional[Callable[[], Any]] = None

    # -- Configuration --

    def set_cloud_manager(self, manager: Any) -> None:
        self.cloud_manager = manager

    def set_member_id(self, member_id: str) -> None:
        self._member_id = member_id

    def set_pet_name(self, pet_name: str) -> None:
        self._pet_name = pet_name

    def set_on_sync_result(self, callback: Optional[Callable[[bool, str], None]]) -> None:
        self._on_sync_result = callback

    def set_on_members_update(self, callback: Optional[Callable[[list], None]]) -> None:
        self._on_members_update = callback

    def set_local_state_provider(self, provider: Callable[[], Any]) -> None:
        """Set a callable that returns the current local PetState (or dict)."""
        self._local_state_provider = provider

    # -- Lifecycle --

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._stop_event.clear()
        self._state_thread = threading.Thread(target=self._state_loop, daemon=True)
        self._state_thread.start()
        self._presence_thread = threading.Thread(target=self._presence_loop, daemon=True)
        self._presence_thread.start()
        print("[CloudSyncScheduler] Dual-frequency sync started "
              f"(state={self.state_interval_sec}s, presence={self.presence_interval_sec}s).")

    def stop(self) -> None:
        self._running = False
        self._stop_event.set()

    # -- Sync operations --

    def sync_state_once(self) -> bool:
        """Sync pet state to cloud (one shot)."""
        if self.cloud_manager is None:
            self._notify(False, "Cloud manager not configured.")
            return False
        try:
            local_state = None
            if self._local_state_provider:
                local_state = self._local_state_provider()
            result = self.cloud_manager.sync_now(local_state)
            ok = bool(result.get("ok", False)) if isinstance(result, dict) else False
            self._notify(ok, "State sync OK." if ok else f"State sync failed: {result.get('error') if isinstance(result, dict) else 'unknown'}")
            return ok
        except Exception as exc:
            self._notify(False, f"State sync error: {exc}")
            return False

    def sync_presence_once(self) -> bool:
        """Send heartbeat and fetch online members (one shot)."""
        if self.cloud_manager is None:
            return False
        try:
            mgr = self.cloud_manager
            if hasattr(mgr, "send_heartbeat") and self._member_id:
                mgr.send_heartbeat(self._member_id, self._pet_name)
            if hasattr(mgr, "get_online_members"):
                result = mgr.get_online_members(ttl_sec=15.0)
                if isinstance(result, dict) and result.get("ok"):
                    members = result.get("data", {}).get("members", [])
                    if self._on_members_update:
                        self._on_members_update(members)
                    return True
            return False
        except Exception:
            return False

    # -- Internal loops --

    def _state_loop(self) -> None:
        while self._running and not self._stop_event.is_set():
            self.sync_state_once()
            self._stop_event.wait(self.state_interval_sec)

    def _presence_loop(self) -> None:
        while self._running and not self._stop_event.is_set():
            self.sync_presence_once()
            self._stop_event.wait(self.presence_interval_sec)

    def _notify(self, success: bool, message: str) -> None:
        if self._on_sync_result:
            try:
                self._on_sync_result(success, message)
            except Exception:
                pass

    def is_running(self) -> bool:
        return self._running
