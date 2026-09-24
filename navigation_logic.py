def choose_navigation_action(sensor_data):
    if sensor_data.get("goal_reached", False):
        return "STOP"
    if sensor_data.get("front_clear", False):
        return "FORWARD"
    if sensor_data.get("left_clear", False):
        return "LEFT"
    if sensor_data.get("right_clear", False):
        return "RIGHT"
    return "STOP"
