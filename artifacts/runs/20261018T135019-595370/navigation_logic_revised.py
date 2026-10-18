def decide_next_move(state):
    if not isinstance(state, dict):
        return 'STOP'
    if not all(k in state for k in ['front_blocked', 'left_blocked', 'right_blocked']):
        return 'STOP'
    if (state.get('goal_ahead') and not state.get('front_blocked')) or \
       (state.get('goal_on_left') and not state.get('left_blocked')) or \
       (state.get('goal_on_right') and not state.get('right_blocked')):
        return 'FORWARD' if (state.get('goal_ahead') and not state.get('front_blocked')) else ('LEFT' if (state.get('goal_on_left') and not state.get('left_blocked')) else 'RIGHT')
    if not state.get('front_blocked'):
        return 'FORWARD'
    elif not state.get('left_blocked'):
        return 'LEFT'
    elif not state.get('right_blocked'):
        return 'RIGHT'
    else:
        return 'STOP'
