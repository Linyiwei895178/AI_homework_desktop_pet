"""
Desk Pet State Module Unit Tests
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.state.pet_state import PetState
from models.state.behavior_rules import decide_action


def test_pet_state_initialization():
    state = PetState()
    assert state.mood == "neutral"
    assert state.energy == 100
    assert state.intimacy == 50
    print("[PASS] test_pet_state_initialization")


def test_pet_state_update_click():
    state = PetState()
    state.update_state("click")
    assert state.mood == "happy"
    assert state.intimacy == 52
    assert state.energy == 99
    print("[PASS] test_pet_state_update_click")


def test_pet_state_update_feed():
    state = PetState(energy=50, intimacy=30)
    state.update_state("feed")
    assert state.energy == 70
    assert state.intimacy == 35
    print("[PASS] test_pet_state_update_feed")


def test_pet_state_energy_bounds():
    state = PetState(energy=5)
    state.update_state("play")
    assert state.energy == 0
    print("[PASS] test_pet_state_energy_bounds")


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


def run_all_tests():
    test_pet_state_initialization()
    test_pet_state_update_click()
    test_pet_state_update_feed()
    test_pet_state_energy_bounds()
    test_behavior_rules_hungry()
    test_behavior_rules_happy()
    test_behavior_rules_high_intimacy()
    print("[ALL TESTS PASSED]")


if __name__ == "__main__":
    run_all_tests()
