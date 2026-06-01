import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.nlp.deepseek_api import DeepSeekClient
from models.nlp.prompt_builder import build_proactive_prompt, build_state_context
from models.vision.computer_activity_detector import (
    ACTIVITY_BROWSING,
    ACTIVITY_CHATTING,
    ACTIVITY_CODING,
    ACTIVITY_GAMING,
    ACTIVITY_UNKNOWN,
    ACTIVITY_WATCHING,
    ACTIVITY_WORKING,
    ComputerActivityDetector,
    ForegroundWindow,
    build_companion_event,
    build_local_companion_comment,
    classify_window_activity,
)


def test_classifies_known_game_window():
    state = classify_window_activity(
        process_name="Stardew Valley.exe",
        window_title="Stardew Valley",
        is_fullscreen=True,
    )

    assert state["activity_code"] == ACTIVITY_GAMING
    assert state["confidence"] >= 0.8
    assert "游戏" in state["tags"]


def test_classifies_video_site_window_as_watching():
    state = classify_window_activity(
        process_name="chrome.exe",
        window_title="第 12 集 - 哔哩哔哩 - Google Chrome",
        is_fullscreen=False,
    )

    assert state["activity_code"] == ACTIVITY_WATCHING
    assert state["confidence"] >= 0.7
    assert "陪看" in state["tags"]


@pytest.mark.parametrize(
    ("process_name", "window_title", "expected_code"),
    [
        ("Code.exe", "main.py - Visual Studio Code", ACTIVITY_CODING),
        ("chrome.exe", "GitHub - SWT-0407/AI_homework_desktop_pet", ACTIVITY_CODING),
        ("chrome.exe", "LeetCode - 两数之和 - Google Chrome", ACTIVITY_CODING),
        ("POWERPNT.EXE", "项目汇报.pptx - PowerPoint", ACTIVITY_WORKING),
        ("wps.exe", "论文.docx - WPS Writer", ACTIVITY_WORKING),
        ("chrome.exe", "飞书文档 - 项目计划", ACTIVITY_WORKING),
        ("msedge.exe", "百度搜索 - Microsoft Edge", ACTIVITY_BROWSING),
        ("random.exe", "知乎 - 搜索结果 - Chrome", ACTIVITY_BROWSING),
        ("WeChat.exe", "微信", ACTIVITY_CHATTING),
        ("chrome.exe", "Telegram Web", ACTIVITY_CHATTING),
        ("chrome.exe", "腾讯视频 - 电视剧 - Google Chrome", ACTIVITY_WATCHING),
        ("vlc.exe", "VLC 播放器", ACTIVITY_WATCHING),
        ("steam.exe", "Steam", ACTIVITY_GAMING),
        ("chrome.exe", "原神 - HoYoLAB", ACTIVITY_GAMING),
    ],
)
def test_classifies_required_activity_keywords(process_name, window_title, expected_code):
    state = classify_window_activity(
        process_name=process_name,
        window_title=window_title,
        is_fullscreen=False,
    )

    assert state["activity_code"] == expected_code
    assert state["activity_name"]
    assert state["description"]
    assert state["confidence"] > 0
    assert state["source"]


def test_classifies_unknown_window():
    state = classify_window_activity(
        process_name="mystery.exe",
        window_title="Untitled Window",
        is_fullscreen=False,
    )

    assert state["activity_code"] == ACTIVITY_UNKNOWN
    assert state["activity_name"]
    assert state["description"]
    assert state["confidence"] > 0
    assert state["source"] == ["foreground_window"]


def test_builds_companion_event_for_commentable_activity():
    state = classify_window_activity(
        process_name="PotPlayer64.exe",
        window_title="某部电影.mkv",
        is_fullscreen=True,
    )
    state["duration"] = 120.0
    event = build_companion_event(state)

    assert event["event_type"] == "computer_activity_comment"
    assert event["activity_code"] == ACTIVITY_WATCHING
    assert event["need_response"] is True
    assert "看剧" in event["suggestion"] or "视频" in event["suggestion"]


def test_default_detector_comments_on_first_game_detection():
    detector = ComputerActivityDetector()
    detector._read_foreground_window = lambda: ForegroundWindow(
        hwnd=1,
        process_name="Stardew Valley.exe",
        process_path="",
        window_title="Stardew Valley",
        is_fullscreen=True,
    )

    state = detector.get_state()

    assert state["activity_code"] == ACTIVITY_GAMING
    assert state["duration"] == 0.0
    assert state["need_response"] is True


def test_prompt_builder_includes_computer_activity_context():
    event = {
        "event_type": "computer_activity_comment",
        "activity_code": "gaming",
        "activity_name": "游戏中",
        "app_name": "Stardew Valley",
        "window_title": "Stardew Valley",
        "suggestion": "像朋友一样点评一句。",
    }

    prompt = build_proactive_prompt(event)
    context = build_state_context(event)

    assert "电脑状态" in prompt
    assert "Stardew Valley" in prompt
    assert "电脑状态：gaming" in context


def test_local_and_mock_comments_are_friend_like():
    state = classify_window_activity(
        process_name="cs2.exe",
        window_title="Counter-Strike 2",
        is_fullscreen=True,
    )
    local = build_local_companion_comment(state)
    client = DeepSeekClient(api_key="", force_mock=True)
    reply = client.generate(
        "用户电脑状态是 游戏中。请像朋友在旁边小声点评。",
        user_state={"activity_code": "gaming", "window_title": "Counter-Strike 2"},
    )

    assert local
    assert "旁边" in reply or "稳住" in reply
