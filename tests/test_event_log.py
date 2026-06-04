"""
Event Log unit tests.

覆盖 append_event / read_recent_events / clear_events + 结构验证。
"""
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.event_log import EventLog


def test_append_and_read():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False, encoding="utf-8") as f:
        tmp_path = f.name

    try:
        log = EventLog(tmp_path)

        log.append_event({
            "event_type": "feed",
            "actor": "local",
            "pet_id": "cat",
            "delta": {"energy": 20, "hunger": 30, "exp": 5},
            "source": "click",
        })
        log.append_event({
            "event_type": "play",
            "actor": "local",
            "pet_id": "cat",
            "delta": {"energy": -10, "exp": 3},
            "source": "click",
        })
        log.append_event({
            "event_type": "chat",
            "actor": "local",
            "pet_id": "doge",
            "delta": {"intimacy": 2, "exp": 2},
            "source": "nlp",
        })

        # 读最近 2 条
        recent = log.read_recent_events(2)
        assert len(recent) == 2
        assert recent[0]["event_type"] == "chat"  # 最新
        assert recent[1]["event_type"] == "play"
        assert "timestamp" in recent[0]
        print("[PASS] test_append_and_read")
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


def test_clear_events():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False, encoding="utf-8") as f:
        tmp_path = f.name

    try:
        log = EventLog(tmp_path)
        log.append_event({
            "event_type": "feed",
            "actor": "local",
            "pet_id": "cat",
            "delta": {},
            "source": "click",
        })
        assert log.count_events() == 1

        log.clear_events()
        assert log.count_events() == 0
        assert log.read_recent_events(10) == []
        print("[PASS] test_clear_events")
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


def test_empty_log_graceful():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False, encoding="utf-8") as f:
        tmp_path = f.name

    try:
        # 空文件
        log = EventLog(tmp_path)
        assert log.read_recent_events(10) == []
        assert log.count_events() == 0
        print("[PASS] test_empty_log_graceful")
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


def test_missing_timestamp_auto_filled():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False, encoding="utf-8") as f:
        tmp_path = f.name

    try:
        log = EventLog(tmp_path)
        log.append_event({
            "event_type": "level_up",
            "actor": "system",
            "pet_id": "cat",
            "delta": {"level": 2},
            "source": "leveling",
            # 故意不写 timestamp
        })
        events = log.read_recent_events(1)
        assert len(events) == 1
        assert "timestamp" in events[0]
        assert events[0]["event_type"] == "level_up"
        print("[PASS] test_missing_timestamp_auto_filled")
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


def test_all_required_fields():
    """验证每条事件都包含 6 个必需字段"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False, encoding="utf-8") as f:
        tmp_path = f.name

    try:
        log = EventLog(tmp_path)
        for et in ("feed", "play", "chat", "level_up", "reminder", "cloud_sync"):
            log.append_event({
                "event_type": et,
                "actor": "local",
                "pet_id": "cat",
                "delta": {"k": 1},
                "source": "test",
            })
        events = log.read_recent_events(20)
        assert len(events) == 6
        required = {"timestamp", "event_type", "actor", "pet_id", "delta", "source"}
        for e in events:
            missing = required - set(e.keys())
            assert not missing, f"Missing fields: {missing} in event: {e}"
        print("[PASS] test_all_required_fields")
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


def run_all_tests():
    test_append_and_read()
    test_clear_events()
    test_empty_log_graceful()
    test_missing_timestamp_auto_filled()
    test_all_required_fields()
    print("\n[ALL TESTS PASSED]")


if __name__ == "__main__":
    run_all_tests()
