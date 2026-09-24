def choose_navigation_action(sensor_data):
    if sensor_data.get("goal_ahead", False) and not sensor_data.get("front_blocked", False):
        return "FORWARD"
    elif sensor_data.get("goal_on_left", False) and not sensor_data.get("left_blocked", False):
        return "LEFT"
    elif sensor_data.get("goal_on_right", False) and not sensor_data.get("right_blocked", False):
        return "RIGHT"
    elif not sensor_data.get("front_blocked", False):
        return "FORWARD"
    elif not sensor_data.get("left_blocked", False):
        return "LEFT"
    elif not sensor_data.get("right_blocked", False):
        return "RIGHT"
    else:
        return "STOP"
