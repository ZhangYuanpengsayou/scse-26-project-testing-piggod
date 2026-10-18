def decide_next_move(state):
    if state.get('goal_ahead') and not state.get('front_blocked'):
        return 'FORWARD'
    if state.get('goal_on_left') and not state.get('left_blocked'):
        return 'LEFT'
    if state.get('goal_on_right') and not state.get('right_blocked'):
        return 'RIGHT'
    if state.get('front_blocked') and state.get('left_blocked') and state.get('right_blocked'):
        return 'STOP'
    if not state.get('front_blocked'):
        return 'FORWARD'
    if not state.get('left_blocked'):
        return 'LEFT'
    if not state.get('right_blocked'):
        return 'RIGHT'
    return 'STOP'
