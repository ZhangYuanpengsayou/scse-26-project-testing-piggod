def decide_next_move(state):
    if state.get('goal_ahead') and not state.get('front_blocked'):
        return 'FORWARD'
    elif state.get('goal_on_left') and not state.get('left_blocked'):
        return 'LEFT'
    elif state.get('goal_on_right') and not state.get('right_blocked'):
        return 'RIGHT'
    elif not state.get('front_blocked'):
        return 'FORWARD'
    elif not state.get('left_blocked'):
        return 'LEFT'
    elif not state.get('right_blocked'):
        return 'RIGHT'
    else:
        return 'STOP'
