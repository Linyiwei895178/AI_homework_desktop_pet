"""
CloudSyncScheduler: periodic cloud sync using a QTimer-like approach.

Provides start() / stop() / sync_once() interfaces.
Actual sync logic is delegated to SharedPetRoomManager.
"""

from __future__ import annotations

import threading
import time
from typing import Any, Callable, Optional


class CloudSyncScheduler:
    """
    Periodic cloud sync manager.

    Usage:
        scheduler = CloudSyncScheduler(cloud_manager=my_manager, interval_sec=60)
        scheduler.set_on_sync_result(callback)
        scheduler.start()
        # ... later ...
        scheduler.stop()
    """

    def __init__(
        self,
        cloud_manager: Optional[Any] = None,
        interval_sec: float = 60.0,
    ):
        """
        :param cloud_manager: SharedPetRoomManager instance (or None)
        :param interval_sec: sync interval in seconds
        """
        self.cloud_manager = cloud_manager
        self.interval_sec = max(5.0, float(interval_sec))
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._on_sync_result: Optional[Callable[[bool, str], None]] = None

    def set_cloud_manager(self, manager: Any) -> None:
        """Set or update the cloud manager reference."""
        self.cloud_manager = manager

    def set_on_sync_result(self, callback: Optional[Callable[[bool, str], None]]) -> None:
        """
        Register a callback for sync results.

        :param callback: callable(success: bool, message: str)
        """
        self._on_sync_result = callback

    def start(self) -> None:
        """Start the periodic sync loop in a daemon thread."""
        if self._running:
            return
        self._running = True
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        print("[CloudSyncScheduler] Started.")

    def stop(self) -> None:
        """Stop the periodic sync loop."""
        self._running = False
        self._stop_event.set()

    def sync_once(self, local_pet_state: Optional[Any] = None) -> bool:
        """
        Perform a single sync cycle.

        :param local_pet_state: optional PetState or dict to sync
        :returns: True if sync succeeded
        """
        if self.cloud_manager is None:
            self._notify(False, "Cloud manager not configured.")
            return False

        try:
            # TODO: real sync with conflict resolution
            # self.cloud_manager.sync_now(local_pet_state)
            result = self.cloud_manager.sync_now(local_pet_state) if hasattr(self.cloud_manager, "sync_now") else None
            success = result is not False  # None or True means OK
            self._notify(success, "Sync completed." if success else "Sync returned no data.")
            return success
        except Exception as exc:
            self._notify(False, f"Sync error: {exc}")
            return False

    def _loop(self) -> None:
        """Internal loop: sync every `interval_sec` seconds."""
        while self._running and not self._stop_event.is_set():
            # TODO: fetch local pet state from AppContext before syncing
            self.sync_once()
            self._stop_event.wait(self.interval_sec)

    def _notify(self, success: bool, message: str) -> None:
        if self._on_sync_result:
            try:
                self._on_sync_result(success, message)
            except Exception as exc:
                print(f"[CloudSyncScheduler] callback error: {exc}")

    def is_running(self) -> bool:
        return self._running
