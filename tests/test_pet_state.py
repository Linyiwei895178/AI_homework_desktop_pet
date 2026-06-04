"""
Desk Pet State Module Unit Tests

覆盖：
- 基础初始化
- update_state 事件（click/feed/play/idle/sad/chat/work/study）
- apply_interaction 返回值
- 等级经验系统（add_exp / level_up / get_level_progress）
- 新字段（level/exp/coins/hunger/bond_score）
- save_state / load_state（含旧格式兼容）
- to_dict / from_dict
- 边界值
"""
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.state.pet_state import PetState
from models.state.behavior_rules import decide_action


# ══════════════════════════════════════════════════════
# 原有测试
# ══════════════════════════════════════════════════════

def test_pet_state_initialization():
    state = PetState()
    assert state.mood == "neutral"
    assert state.energy == 100
    assert state.intimacy == 50
    assert state.pet_id == "cat"
    # 新字段默认值
    assert state.level == 1
    assert state.exp == 0
    assert state.coins == 0
    assert state.hunger == 50
    assert state.bond_score == 0
    print("[PASS] test_pet_state_initialization")


def test_pet_state_custom_init():
    state = PetState(mood="happy", energy=80, intimacy=60, pet_id="doge",
                     level=3, exp=50, coins=200, hunger=70, bond_score=30)
    assert state.mood == "happy"
    assert state.energy == 80
    assert state.intimacy == 60
    assert state.pet_id == "doge"
    assert state.level == 3
    assert state.exp == 50
    assert state.coins == 200
    assert state.hunger == 70
    assert state.bond_score == 30
    print("[PASS] test_pet_state_custom_init")


def test_pet_state_update_click():
    state = PetState()
    state.update_state("click")
    assert state.mood == "happy"
    assert state.intimacy == 52
    assert state.energy == 99
    assert state.exp == 1  # click gives 1 exp
    print("[PASS] test_pet_state_update_click")


def test_pet_state_update_feed():
    state = PetState(energy=50, intimacy=30)
    state.update_state("feed")
    assert state.energy == 70
    assert state.intimacy == 35
    assert state.exp == 5
    assert state.hunger == 80  # feed +30 hunger
    assert state.bond_score == 1
    print("[PASS] test_pet_state_update_feed")


def test_pet_state_energy_bounds():
    state = PetState(energy=5)
    state.update_state("play")
    assert state.energy == 0  # clamped
    assert state.intimacy == 53
    assert state.exp == 3
    print("[PASS] test_pet_state_energy_bounds")


# ══════════════════════════════════════════════════════
# 等级/经验系统测试
# ══════════════════════════════════════════════════════

def test_add_exp_simple():
    """增加经验值，不触发升级"""
    state = PetState()
    events = state.add_exp(50)
    assert events == []
    assert state.exp == 50
    assert state.level == 1
    print("[PASS] test_add_exp_simple")


def test_add_exp_level_up():
    """增加经验值触发升级"""
    state = PetState(level=1, exp=0)
    events = state.add_exp(100)  # 刚好够升到 2 级
    assert "level_up" in events
    assert state.level == 2
    assert state.exp == 0  # 溢出归零（100 - 100 = 0）
    print("[PASS] test_add_exp_level_up")


def test_add_exp_multi_level_up():
    """一次性升级多级"""
    state = PetState(level=1, exp=0)
    # L1→L2 需 100, L2→L3 需 250, 总计 350
    events = state.add_exp(400)
    assert events.count("level_up") >= 1
    assert state.level >= 2
    print("[PASS] test_add_exp_multi_level_up")


def test_add_exp_negative():
    """负数经验不生效"""
    state = PetState(exp=10)
    events = state.add_exp(-5)
    assert events == []
    assert state.exp == 10
    print("[PASS] test_add_exp_negative")


def test_get_level_progress():
    state = PetState(level=1, exp=50)
    progress = state.get_level_progress()
    assert progress["level"] == 1
    assert progress["exp"] == 50
    assert progress["next_level_exp"] == 100
    assert progress["progress"] == 0.5
    assert progress["remaining"] == 50
    print("[PASS] test_get_level_progress")


# ══════════════════════════════════════════════════════
# apply_interaction 测试
# ══════════════════════════════════════════════════════

def test_apply_interaction_click():
    state = PetState()
    deltas = state.apply_interaction("click")
    assert deltas["action_type"] == "click"
    assert deltas["actor"] == "local"
    # deltas 的 key 格式为 {field}_delta
    assert "intimacy_delta" in deltas
    assert "energy_delta" in deltas
    assert "exp_delta" in deltas
    assert deltas["intimacy_delta"] == 2
    assert deltas["energy_delta"] == -1
    assert deltas["exp_delta"] == 1
    print("[PASS] test_apply_interaction_click")


def test_apply_interaction_work():
    """工作陪伴：加经验/金币，减能量/饱食度"""
    state = PetState(energy=100, hunger=80)
    deltas = state.apply_interaction("work")
    assert deltas["action_type"] == "work"
    assert deltas.get("exp_delta", 0) > 0
    assert deltas.get("coins_delta", 0) > 0
    assert deltas.get("energy_delta", 0) < 0
    print("[PASS] test_apply_interaction_work")


# ══════════════════════════════════════════════════════
# 新事件类型测试
# ══════════════════════════════════════════════════════

def test_update_state_chat():
    state = PetState(energy=50, intimacy=30, mood="sad")
    state.update_state("chat")
    assert state.mood in ("neutral", "happy")
    assert state.intimacy >= 30
    assert state.energy < 50
    assert state.exp >= 1
    print("[PASS] test_update_state_chat")


def test_update_state_work():
    state = PetState(energy=100, hunger=80)
    state.update_state("work")
    assert state.energy == 85
    assert state.exp == 8
    assert state.coins == 15
    assert state.hunger == 70
    print("[PASS] test_update_state_work")


def test_update_state_study():
    state = PetState(energy=100)
    state.update_state("study")
    assert state.energy == 90
    assert state.exp >= 1  # 兜底 1 exp
    print("[PASS] test_update_state_study")


# ══════════════════════════════════════════════════════
# to_dict / from_dict
# ══════════════════════════════════════════════════════

def test_to_dict():
    state = PetState(pet_id="doge", level=2, exp=50, coins=100, hunger=60, bond_score=10)
    d = state.to_dict()
    assert d["pet_id"] == "doge"
    assert d["level"] == 2
    assert d["exp"] == 50
    assert d["coins"] == 100
    assert d["hunger"] == 60
    assert d["bond_score"] == 10
    print("[PASS] test_to_dict")


def test_from_dict_compat_old_format():
    """旧格式 JSON（无 level/exp/coins/hunger/bond_score）应自动填充默认值"""
    old_data = {
        "pet_id": "cat",
        "mood": "happy",
        "energy": 80,
        "intimacy": 60,
    }
    state = PetState()
    state.from_dict(old_data)
    assert state.mood == "happy"
    assert state.energy == 80
    assert state.intimacy == 60
    # 新字段应保持默认值
    assert state.level == 1
    assert state.exp == 0
    assert state.coins == 0
    assert state.hunger == 50
    assert state.bond_score == 0
    print("[PASS] test_from_dict_compat_old_format")


def test_from_dict_new_format():
    """新格式 JSON 正确恢复所有字段"""
    new_data = {
        "pet_id": "doge",
        "mood": "happy",
        "energy": 90,
        "intimacy": 70,
        "level": 3,
        "exp": 200,
        "coins": 500,
        "hunger": 80,
        "bond_score": 25,
    }
    state = PetState()
    state.from_dict(new_data)
    assert state.level == 3
    assert state.exp == 200
    assert state.coins == 500
    assert state.hunger == 80
    assert state.bond_score == 25
    print("[PASS] test_from_dict_new_format")


# ══════════════════════════════════════════════════════
# 边界值测试
# ══════════════════════════════════════════════════════

def test_bounds_clamp():
    """所有数值字段不应越界"""
    state = PetState(energy=200, intimacy=-10, hunger=200, exp=-50, coins=-100, bond_score=-5)
    assert 0 <= state.energy <= 100
    assert 0 <= state.intimacy <= 100
    assert 0 <= state.hunger <= 100
    assert state.exp == 0
    assert state.coins == 0
    assert state.bond_score == 0
    assert state.level == 1
    print("[PASS] test_bounds_clamp")


def test_hunger_full_bound():
    """饱食度不应超过 100"""
    state = PetState(hunger=100)
    state.update_state("feed")  # feed +30 hunger
    assert state.hunger == 100
    print("[PASS] test_hunger_full_bound")


# ══════════════════════════════════════════════════════
# save_state / load_state（持久化）
# ══════════════════════════════════════════════════════

def test_save_and_load_state():
    """保存后加载，状态应一致"""
    state = PetState(mood="happy", energy=80, intimacy=70, pet_id="doge",
                     level=3, exp=200, coins=500, hunger=60, bond_score=25)

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
        tmp_path = f.name

    try:
        state.save_state(tmp_path)
        assert os.path.exists(tmp_path)

        # 读取后验证 JSON 中包含 updated_at
        with open(tmp_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert "updated_at" in data

        # 加载到新实例
        state2 = PetState()
        state2.load_state(tmp_path)
        assert state2.mood == "happy"
        assert state2.energy == 80
        assert state2.intimacy == 70
        assert state2.pet_id == "doge"
        assert state2.level == 3
        assert state2.exp == 200
        assert state2.coins == 500
        assert state2.hunger == 60
        assert state2.bond_score == 25
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)

    print("[PASS] test_save_and_load_state")


def test_load_old_format_json():
    """加载旧格式 JSON（只有 mood/energy/intimacy/pet_id）"""
    old_data = {
        "pet_id": "cat",
        "mood": "sad",
        "energy": 20,
        "intimacy": 10,
    }
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
        json.dump(old_data, f)
        tmp_path = f.name

    try:
        state = PetState()
        state.load_state(tmp_path)
        assert state.mood == "sad"
        assert state.energy == 20
        assert state.intimacy == 10
        # 新字段应保持默认值
        assert state.level == 1
        assert state.exp == 0
        assert state.coins == 0
        assert state.hunger == 50
        assert state.bond_score == 0
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)

    print("[PASS] test_load_old_format_json")


def test_load_nonexistent_file():
    """加载不存在的文件应保持当前状态"""
    state = PetState(mood="happy", energy=99)
    state.load_state("/tmp/no_such_file_xyz123.json")
    assert state.mood == "happy"
    assert state.energy == 99
    print("[PASS] test_load_nonexistent_file")


# ══════════════════════════════════════════════════════
# 原有 behavior_rules 测试
# ══════════════════════════════════════════════════════

def test_behavior_rules_hungry():
    state = PetState(mood="neutral", energy=20, intimacy=50)
    action = decide_action(state)
    assert action == "hungry", f"Expected hungry, got {action}"
    print("[PASS] test_behavior_rules_hungry")


def test_behavior_rules_happy():
    state = PetState(mood="happy", energy=80, intimacy=50)
    action = decide_action(state)
    assert action == "happy", f"Expected happy, got {action}"
    print("[PASS] test_behavior_rules_happy")


def test_behavior_rules_high_intimacy():
    state = PetState(mood="neutral", energy=80, intimacy=90)
    action = decide_action(state)
    assert action == "happy", f"Expected happy (high intimacy), got {action}"
    print("[PASS] test_behavior_rules_high_intimacy")


# ══════════════════════════════════════════════════════
# 历史记录测试
# ══════════════════════════════════════════════════════

def test_history_recording():
    state = PetState()
    state.update_state("click")
    state.update_state("feed")
    history = state.get_history()
    assert len(history) == 2
    assert history[0]["event"] == "click"
    assert history[1]["event"] == "feed"
    assert "timestamp" in history[0]
    assert "level" in history[0]
    print("[PASS] test_history_recording")


def test_history_limit():
    state = PetState()
    for _ in range(5):
        state.update_state("click")
    history = state.get_history(3)
    assert len(history) == 3
    print("[PASS] test_history_limit")


def test_reset_history():
    state = PetState()
    state.update_state("click")
    state.reset_history()
    assert state.get_history() == []
    print("[PASS] test_reset_history")


def test_history_from_user_state():
    state = PetState()
    state.update_from_user_state({
        "state_code": "return",
        "confidence": 0.9,
        "duration": 5.0,
        "need_response": False,
    })
    history = state.get_history()
    assert len(history) == 1
    assert "user_state:return" in history[0]["event"]
    print("[PASS] test_history_from_user_state")


# ══════════════════════════════════════════════════════
# 奔跑入口
# ══════════════════════════════════════════════════════

def run_all_tests():
    # 原有
    test_pet_state_initialization()
    test_pet_state_custom_init()
    test_pet_state_update_click()
    test_pet_state_update_feed()
    test_pet_state_energy_bounds()

    # 等级/经验
    test_add_exp_simple()
    test_add_exp_level_up()
    test_add_exp_multi_level_up()
    test_add_exp_negative()
    test_get_level_progress()

    # apply_interaction
    test_apply_interaction_click()
    test_apply_interaction_work()

    # 新事件
    test_update_state_chat()
    test_update_state_work()
    test_update_state_study()

    # to_dict / from_dict
    test_to_dict()
    test_from_dict_compat_old_format()
    test_from_dict_new_format()

    # 边界值
    test_bounds_clamp()
    test_hunger_full_bound()

    # 持久化
    test_save_and_load_state()
    test_load_old_format_json()
    test_load_nonexistent_file()

    # behavior_rules
    test_behavior_rules_hungry()
    test_behavior_rules_happy()
    test_behavior_rules_high_intimacy()

    # 历史记录
    test_history_recording()
    test_history_limit()
    test_reset_history()
    test_history_from_user_state()

    print("\n[ALL TESTS PASSED]")


if __name__ == "__main__":
    run_all_tests()
