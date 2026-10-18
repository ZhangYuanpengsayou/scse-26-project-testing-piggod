from itertools import product  
from generated.navigation_logic import decide_next_move  

def test_all_states():  
    keys = ['goal_ahead', 'front_blocked', 'goal_on_left', 'left_blocked',  
            'goal_on_right', 'right_blocked']  
    safe_actions = [('FORWARD', 'goal_ahead', 'front_blocked'), ('LEFT', 'goal_on_left', 'left_blocked'),  
                    ('RIGHT', 'goal_on_right', 'right_blocked')]  
    for values in product([False, True], repeat=6):  
        state = dict(zip(keys, values))  
        for action, goal_key, blocked_key in safe_actions:  
            if state[goal_key] and not state[blocked_key]:  
                expected = action  
                break  
        else:  
            for action, _, _ in safe_actions:  
                if not state[action.split('_')[1]+'_blocked']:  
                    expected = action  
                    break  
            else:  
                expected = 'STOP'  
        assert decide_next_move(state) == expected  

def test_typical_case():  
    state = {'goal_ahead': True, 'front_blocked': False,  
             'goal_on_left': False, 'left_blocked': True,  
             'goal_on_right': False, 'right_blocked': True}  
    assert decide_next_move(state) == 'FORWARD'  

def test_optional_goals():  
    for values in product([False, True], repeat=6):  
        state = dict(zip(['goal_ahead', 'front_blocked', 'goal_on_left', 'left_blocked',  
                         'goal_on_right', 'right_blocked'], values))  
        if not any(state.get(k) for k in ['goal_ahead', 'goal_on_left', 'goal_on_right']):  
            for action in ['FORWARD', 'LEFT', 'RIGHT']:  
                blocked_key = action.split('_')[1]+'_blocked'  
                if not state[blocked_key]:  
                    expected = action  
                    break  
            else:  
                expected = 'STOP'  
            assert decide_next_move(state) == expected  

if __name__ == '__main__':  
    test_all_states()  
    test_typical_case()  
    test_optional_goals()  
    print("success")
