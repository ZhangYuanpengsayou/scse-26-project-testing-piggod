from itertools import product

from generated_navigation_logic import choose_navigation_action


def expected_action(sensor_data):
    if sensor_data["goal_ahead"] and not sensor_data["front_blocked"]:
        return "FORWARD"

    if sensor_data["goal_on_left"] and not sensor_data["left_blocked"]:
        return "LEFT"

    if sensor_data["goal_on_right"] and not sensor_data["right_blocked"]:
        return "RIGHT"

    if not sensor_data["front_blocked"]:
        return "FORWARD"

    if not sensor_data["left_blocked"]:
        return "LEFT"

    if not sensor_data["right_blocked"]:
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
        sensor_data = dict(zip(keys, values))
        yield sensor_data, expected_action(sensor_data)


def test_choose_navigation_action_for_all_possible_states():
    for sensor_data, expected in all_possible_states():
        assert choose_navigation_action(sensor_data) == expected


def test_typical_case_from_instructions():
    sensor_data = {
        "goal_ahead": True,
        "goal_on_left": False,
        "goal_on_right": False,
        "front_blocked": False,
        "left_blocked": False,
        "right_blocked": False,
    }

    assert choose_navigation_action(sensor_data) == "FORWARD"


if __name__ == "__main__":
    test_choose_navigation_action_for_all_possible_states()
    test_typical_case_from_instructions()
    print("All generated navigation logic tests passed.")
