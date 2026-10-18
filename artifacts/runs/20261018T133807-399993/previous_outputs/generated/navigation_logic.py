def decide_next_move(state):
    if state.get("goal_ahead", False) and not state.get("front_blocked", False):
        return "FORWARD"
    if state.get("goal_on_left", False) and not state.get("left_blocked", False):
        return "LEFT"
    if state.get("goal_on_right", False) and not state.get("right_blocked", False):
        return "RIGHT"
    if not state.get("front_blocked", False):
        return "FORWARD"
    if not state.get("left_blocked", False):
        return "LEFT"
    if not state.get("right_blocked", False):
        return "RIGHT"
    return "STOP"
