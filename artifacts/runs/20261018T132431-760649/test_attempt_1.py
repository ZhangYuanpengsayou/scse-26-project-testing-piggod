from itertools import product; from generated.navigation_logic import decide_next_move

def test_all_states():
    keys = ['goal_ahead', 'goal_on_left', 'goal_on_right']
    safe_actions = ['FORWARD', 'LEFT', 'RIGHT']
    action_tuples = [('FORWARD', 'goal_ahead', 'front_blocked'),
                     ('LEFT', 'goal_on_left', 'left_blocked'),
                     ('RIGHT', 'goal_on_right', 'right_blocked')]
    for values in product([False, True], repeat=6):
        state = dict(zip(keys + ['front_blocked', 'left_blocked', 'right_blocked'], values))
        for action, goal_key, blocked_key in action_tuples:
            if state[goal_key] and not state[blocked_key]:
                expected = action
                break
        else:
            safe = [a for a in safe_actions if not state[f"{a}_blocked"]]
            expected = safe[0] if safe else 'STOP'
        assert decide_next_move(state) == expected

def test_typical_case():
    state = {'goal_ahead': True, 'front_blocked': False}
    assert decide_next_move(state) == 'FORWARD'

def test_optional_goals():
    keys = ['front_blocked', 'left_blocked', 'right_blocked']
    for values in product([False, True], repeat=3):
        state = dict(zip(keys, values))
        blocked = [state[f"{a}_blocked"] for a in ['front', 'left', 'right']]
        free = [i for i, b in enumerate(blocked) if not b]
        expected = ['FORWARD', 'LEFT', 'RIGHT'][free[0]] if free else 'STOP'
        assert decide_next_move(state) == expected

if __name__ == '__main__':
    test_all_states(); test_typical_case(); test_optional_goals()
    print("success")
