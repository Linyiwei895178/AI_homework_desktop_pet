"""
Tests for Supabase cloud service.

Requirements:
    - All methods must never raise exceptions.
    - When not configured, must return {"ok": False, "error": "not_configured", "data": None}.
    - When configured, must return ok with mock/real data.
      (Tests that rely on real DB tables use a service that won't try real calls.)
"""

from __future__ import annotations

import os
import pytest
from typing import Any

from models.cloud.cloud_config import load_cloud_config
from models.cloud.cloud_service import SupabaseCloudService
from models.cloud.shared_pet_room import SharedPetRoomManager


_NOT_CONFIGURED = {"ok": False, "error": "not_configured", "data": None}


def _make_unconfigured_service() -> SupabaseCloudService:
    """Create a service that is definitely not configured."""
    return SupabaseCloudService(url="", anon_key="")


class _MockOnlyService(SupabaseCloudService):
    """
    A service that never tries real HTTP calls.
    Overrides _get_client to always return None (= mock fallback).
    """
    def _get_client(self) -> Any:
        return None


# ---------------------------------------------------------------------------
# cloud_config
# ---------------------------------------------------------------------------


class TestCloudConfig:
    def test_load_cloud_config_returns_dict(self):
        cfg = load_cloud_config()
        assert isinstance(cfg, dict)
        assert "url" in cfg
        assert "anon_key" in cfg
        assert "configured" in cfg

    def test_load_cloud_config_no_exception(self):
        cfg = load_cloud_config()
        assert isinstance(cfg, dict)


# ---------------------------------------------------------------------------
# SupabaseCloudService (unconfigured)
# ---------------------------------------------------------------------------


class TestSupabaseCloudServiceNotConfigured:
    """All methods must return not_configured when service is unconfigured."""

    @pytest.fixture
    def svc(self):
        return _make_unconfigured_service()

    def test_is_configured_false(self, svc):
        assert svc.is_configured() is False

    def test_login_returns_not_configured(self, svc):
        assert svc.login_email_password("a@b.com", "pw") == _NOT_CONFIGURED

    def test_logout_returns_ok(self, svc):
        """Logout should still work even when unconfigured."""
        result = svc.logout()
        assert result["ok"] is True

    def test_get_or_create_profile_not_configured(self, svc):
        assert svc.get_or_create_profile("X") == _NOT_CONFIGURED

    def test_create_or_join_room_not_configured(self, svc):
        assert svc.create_or_join_room("X", "X") == _NOT_CONFIGURED

    def test_fetch_cloud_pet_state_not_configured(self, svc):
        assert svc.fetch_cloud_pet_state("X") == _NOT_CONFIGURED

    def test_save_cloud_pet_state_not_configured(self, svc):
        assert svc.save_cloud_pet_state("X", {}) == _NOT_CONFIGURED

    def test_append_pet_event_not_configured(self, svc):
        assert svc.append_pet_event("X", {}) == _NOT_CONFIGURED

    def test_fetch_recent_pet_events_not_configured(self, svc):
        assert svc.fetch_recent_pet_events("X", limit=5) == _NOT_CONFIGURED

    def test_no_exception_on_any_method(self, svc):
        """All methods should never raise exceptions."""
        methods = [
            lambda: svc.login_email_password("a@b.com", "pw"),
            lambda: svc.logout(),
            lambda: svc.get_or_create_profile("X"),
            lambda: svc.create_or_join_room("X", "X"),
            lambda: svc.fetch_cloud_pet_state("X"),
            lambda: svc.save_cloud_pet_state("X", {}),
            lambda: svc.append_pet_event("X", {}),
            lambda: svc.fetch_recent_pet_events("X"),
        ]
        for method in methods:
            try:
                result = method()
                assert isinstance(result, dict), f"Expected dict, got {type(result)}"
            except Exception as exc:
                pytest.fail(f"Unexpected exception: {exc}")


# ---------------------------------------------------------------------------
# SupabaseCloudService (configured, mock-only)
# ---------------------------------------------------------------------------


class TestSupabaseCloudServiceConfigured:
    """
    Tests for when Supabase IS configured (your .env has the keys).
    Uses _MockOnlyService to avoid real HTTP calls (no Supabase tables required).
    """

    def test_is_configured_matches_env(self):
        svc = SupabaseCloudService()
        expected = bool(os.getenv("SUPABASE_URL")) and bool(os.getenv("SUPABASE_ANON_KEY"))
        assert svc.is_configured() == expected

    def test_login_returns_ok_with_mock_user(self):
        svc = _MockOnlyService()
        result = svc.login_email_password("test@example.com", "password123")
        assert result["ok"] is True
        assert result["data"]["email"] == "test@example.com"

    def test_logout_returns_ok(self):
        svc = _MockOnlyService()
        result = svc.logout()
        assert result["ok"] is True
        assert result["data"]["logged_out"] is True

    def test_get_or_create_profile_returns_ok(self):
        svc = _MockOnlyService()
        result = svc.get_or_create_profile("TestUser")
        assert result["ok"] is True
        assert "id" in result["data"]

    def test_create_or_join_room_returns_ok(self):
        svc = _MockOnlyService()
        result = svc.create_or_join_room("TEST_ROOM", "TestPet")
        assert result["ok"] is True
        assert result["data"]["room"]["room_code"] == "TEST_ROOM"

    def test_fetch_cloud_pet_state_returns_ok(self):
        svc = _MockOnlyService()
        result = svc.fetch_cloud_pet_state("TEST_ROOM")
        assert result["ok"] is True
        assert "pet" in result["data"]

    def test_save_cloud_pet_state_returns_ok(self):
        svc = _MockOnlyService()
        result = svc.save_cloud_pet_state("TEST_ROOM", {"level": 2})
        assert result["ok"] is True

    def test_append_pet_event_returns_ok(self):
        svc = _MockOnlyService()
        result = svc.append_pet_event("TEST_ROOM", {"event_type": "test"})
        assert result["ok"] is True

    def test_fetch_recent_pet_events_returns_ok(self):
        svc = _MockOnlyService()
        result = svc.fetch_recent_pet_events("TEST_ROOM", limit=5)
        assert result["ok"] is True

    def test_no_exception_on_any_method(self):
        svc = _MockOnlyService()
        methods = [
            lambda: svc.login_email_password("a@b.com", "pw"),
            lambda: svc.logout(),
            lambda: svc.get_or_create_profile("X"),
            lambda: svc.create_or_join_room("X", "X"),
            lambda: svc.fetch_cloud_pet_state("X"),
            lambda: svc.save_cloud_pet_state("X", {}),
            lambda: svc.append_pet_event("X", {}),
            lambda: svc.fetch_recent_pet_events("X"),
        ]
        for method in methods:
            try:
                result = method()
                assert isinstance(result, dict), f"Expected dict, got {type(result)}"
            except Exception as exc:
                pytest.fail(f"Unexpected exception: {exc}")


# ---------------------------------------------------------------------------
# SharedPetRoomManager (unconfigured)
# ---------------------------------------------------------------------------


class TestSharedPetRoomManagerNotConfigured:
    """SharedPetRoomManager with an unconfigured service must handle graceful fallback."""

    @pytest.fixture
    def mgr(self):
        svc = _make_unconfigured_service()
        return SharedPetRoomManager(svc)

    def test_init_no_exception(self, mgr):
        assert mgr is not None
        assert mgr.is_in_room() is False

    def test_join_room_not_configured(self, mgr):
        result = mgr.join_room("TEST", "Pet")
        assert result == _NOT_CONFIGURED

    def test_sync_now_not_in_room(self, mgr):
        result = mgr.sync_now({"level": 1})
        assert result["ok"] is False
        assert result["error"] == "not_in_room"

    def test_push_local_state_not_in_room(self, mgr):
        result = mgr.push_local_state({"level": 1})
        assert result["ok"] is False

    def test_pull_remote_state_not_in_room(self, mgr):
        result = mgr.pull_remote_state()
        assert result["ok"] is False

    def test_append_interaction_not_in_room(self, mgr):
        result = mgr.append_interaction("feed", "local", {"hunger": 10})
        assert result["ok"] is False

    def test_fetch_recent_events_not_in_room(self, mgr):
        result = mgr.fetch_recent_events()
        assert result["ok"] is False

    def test_leave_room_does_not_crash(self, mgr):
        result = mgr.leave_room()
        assert result["ok"] is True

    def test_set_on_event_callback_no_crash(self, mgr):
        def my_callback(event):
            pass
        mgr.set_on_event_callback(my_callback)
        mgr.set_on_event_callback(None)


# ---------------------------------------------------------------------------
# SharedPetRoomManager (configured, mock-only)
# ---------------------------------------------------------------------------


class TestSharedPetRoomManagerConfigured:
    """Integration tests with a mock-only service."""

    def test_join_room_returns_ok(self):
        svc = _MockOnlyService()
        mgr = SharedPetRoomManager(svc, room_code="TEST")
        result = mgr.join_room("TEST", "Pet")
        assert result["ok"] is True

    def test_sync_now_not_in_room_returns_not_in_room(self):
        svc = _MockOnlyService()
        mgr = SharedPetRoomManager(svc)
        result = mgr.sync_now({"level": 1})
        assert result["ok"] is False
        assert result["error"] == "not_in_room"

    def test_join_then_sync_works(self):
        svc = _MockOnlyService()
        mgr = SharedPetRoomManager(svc, room_code="SYNC_TEST")
        join_result = mgr.join_room("SYNC_TEST", "SyncPet")
        assert join_result["ok"] is True

        sync_result = mgr.sync_now({"level": 5, "mood": "happy"})
        assert sync_result["ok"] is True
        assert sync_result["data"]["pushed"] is True

    def test_join_then_pull_push_interaction(self):
        svc = _MockOnlyService()
        mgr = SharedPetRoomManager(svc, room_code="WORKFLOW_TEST")
        mgr.join_room("WORKFLOW_TEST", "WorkPet")

        push_r = mgr.push_local_state({"level": 10, "coins": 100})
        assert push_r["ok"] is True

        pull_r = mgr.pull_remote_state()
        assert pull_r["ok"] is True

        ia_r = mgr.append_interaction("feed", "tester", {"hunger": 15})
        assert ia_r["ok"] is True

        ev_r = mgr.fetch_recent_events(limit=10)
        assert ev_r["ok"] is True
