def decide_next_move(state):
    if state.get("goal_ahead", False) and not state.get("front_blocked", False):
        return "FORWARD"
    elif state.get("goal_on_left", False) and not state.get("left_blocked", False):
        return "LEFT"
    elif state.get("goal_on_right", False) and not state.get("right_blocked", False):
        return "RIGHT"
    elif not state.get("front_blocked", False):
        return "FORWARD"
    elif not state.get("left_blocked", False):
        return "LEFT"
    elif not state.get("right_blocked", False):
        return "RIGHT"
    else:
        return "STOP"
