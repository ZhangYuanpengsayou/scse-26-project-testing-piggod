import sys
from itertools import product
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
GENERATED_DIR = BASE_DIR / "generated"
sys.path.insert(0, str(GENERATED_DIR))

from navigation_logic import decide_next_move


VALID_ACTIONS = {"FORWARD", "LEFT", "RIGHT", "STOP"}


def expected_action(state):
    if state["goal_ahead"] and not state["front_blocked"]:
        return "FORWARD"
    if state["goal_on_left"] and not state["left_blocked"]:
        return "LEFT"
    if state["goal_on_right"] and not state["right_blocked"]:
        return "RIGHT"
    if not state["front_blocked"]:
        return "FORWARD"
    if not state["left_blocked"]:
        return "LEFT"
    if not state["right_blocked"]:
        return "RIGHT"
    return "STOP"


def all_possible_states():
    keys = [
        "goal_ahead",
        "goal_on_left",
        "goal_on_right",
        "front_blocked",
        "left_blocked",
        "right_blocked",
    ]

    for values in product([False, True], repeat=len(keys)):
        state = dict(zip(keys, values))
        yield state, expected_action(state)


def test_decide_next_move_for_all_possible_states():
    for state, expected in all_possible_states():
        action = decide_next_move(state)
        assert action in VALID_ACTIONS
        assert action == expected


def test_typical_case_from_instructions():
    state = {
        "goal_ahead": True,
        "goal_on_left": False,
        "goal_on_right": False,
        "front_blocked": False,
        "left_blocked": False,
        "right_blocked": False,
    }
    assert decide_next_move(state) == "FORWARD"


if __name__ == "__main__":
    test_decide_next_move_for_all_possible_states()
    test_typical_case_from_instructions()
    print("All generated navigation logic tests passed.")
