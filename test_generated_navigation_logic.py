# Qwen-generated tests; missing standard imports are supplied by test_agent.py.
from generated.navigation_logic import decide_next_move

from itertools import product

def test_all_states():
    directions = [('FORWARD', 'goal_ahead', 'front_blocked'),
                  ('LEFT', 'goal_on_left', 'left_blocked'),
                  ('RIGHT', 'goal_on_right', 'right_blocked')]
    keys = ['goal_ahead', 'goal_on_left', 'goal_on_right', 'front_blocked', 'left_blocked', 'right_blocked']
    for values in product([False, True], repeat=6):
        state = dict(zip(keys, values))
        safe = [a for a, g, b in directions if not state[b]]
        toward = [a for a, g, b in directions if state[g] and not state[b]]
        assert decide_next_move(state) == (toward or safe or ['STOP'])[0]

def test_typical_case():
    state = {
        'goal_ahead': True,
        'goal_on_left': False,
        'goal_on_right': False,
        'front_blocked': False,
        'left_blocked': False,
        'right_blocked': False
    }
    assert decide_next_move(state) == 'FORWARD'

def test_optional_goals():
    directions = [('FORWARD', 'goal_ahead', 'front_blocked'),
                  ('LEFT', 'goal_on_left', 'left_blocked'),
                  ('RIGHT', 'goal_on_right', 'right_blocked')]
    keys = ['front_blocked', 'left_blocked', 'right_blocked']
    for values in product([False, True], repeat=3):
        state = dict(zip(keys, values))
        safe = [a for a, g, b in directions if not state[b]]
        assert decide_next_move(state) == (safe or ['STOP'])[0]

if __name__ == '__main__':
    test_all_states()
    test_typical_case()
    test_optional_goals()
    print("All tests passed.")
