import ast
import json
from developer_agent import NAVIGATION_CONTRACT, strip_markdown_fence
from model_client import MODEL_NAME, chat


def ask_qwen(system_prompt, user_prompt):
    return chat("test_agent", system_prompt, user_prompt)


def validate_test_code(code):
    try:
        tree = ast.parse(code)
    except (SyntaxError, TypeError):
        return False
    tests = [node for node in tree.body if isinstance(node, ast.FunctionDef)
             and node.name.startswith("test_")]
    allowed_imports = {"itertools", "generated.navigation_logic", "navigation_logic"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            if any(alias.name not in allowed_imports for alias in node.names):
                return False
        if isinstance(node, ast.ImportFrom) and node.module not in allowed_imports:
            return False
        if isinstance(node, ast.Name) and node.id in {"eval", "exec", "open", "__import__", "compile"}:
            return False
        if isinstance(node, ast.Attribute) and node.attr.startswith("__"):
            return False
    uses_product = any(isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                       and node.func.id == "product" for node in ast.walk(tree))
    return (len(tests) == 3 and uses_product
            and any(isinstance(node, ast.Assert) for node in ast.walk(tree))
            and all(not test.args.args and not test.decorator_list for test in tests)
            and "import decide_next_move" in code)


def run_test_agent(requirements, plan, brief_text="", navigation_code="", feedback=None):
    if not brief_text or not navigation_code:
        raise ValueError("Test Agent needs the brief AND the actual candidate code.")
    prompt = """Write COMPACT Python tests, less than 60 lines total. No explanations or docstrings.
Define EXACTLY THREE zero-argument functions:
1. test_all_states: use ONE loop over product([False, True], repeat=6).
   Construct each state with dict(zip(keys, values)). Do NOT write literal state dictionaries
   for each combination. Do NOT create numbered tests like test_0001.
   Use safe-action and goal-action lists as the independent expected-action oracle.
   Use explicit tuples (action, goal_key, blocked_key):
   ('FORWARD', 'goal_ahead', 'front_blocked'),
   ('LEFT', 'goal_on_left', 'left_blocked'),
   ('RIGHT', 'goal_on_right', 'right_blocked').
   Filter these tuples using their blocked_key and goal_key. Never derive sensor keys
   from action strings: FORWARD does NOT contain an underscore. Never use split().
   Build safe = list of safe action names, toward = list of safe goal action names,
   then expected = (toward or safe or ['STOP'])[0].
   Assert the returned action equals the first safe goal action, otherwise the first
   safe action, otherwise STOP. Actions ordered FORWARD, LEFT, RIGHT.
2. test_typical_case: one explicit unobstructed goal-ahead case expects FORWARD.
3. test_optional_goals: a loop over the EIGHT obstacle combinations only, with no goal
   keys present; assert the first free direction in FORWARD, LEFT, RIGHT order, else STOP.
   Use product([False, True], repeat=3) and keys
   ['front_blocked', 'left_blocked', 'right_blocked']. Do NOT put goal keys in this state.
   Use an explicit action-to-blocked-key mapping, not string operations.
Only imports allowed: from itertools import product; from generated.navigation_logic import decide_next_move.
Do not use pytest, sys, pathlib, fixtures, decorators, or redefine decide_next_move.
Add if __name__ == '__main__': invoking every test and then printing success.
Return complete code only. Loops are REQUIRED; never unroll the 64 cases.\n"""
    context = {"brief": brief_text, "requirements": requirements, "plan": plan,
               "candidate_code": navigation_code}
    if feedback is not None:
        context["previous_test_failure"] = feedback
        prompt += "\nRepair the previous TEST code using the traceback and unchanged behavioral contract.\n"
    code = strip_markdown_fence(ask_qwen(
        "You are a Python Test Agent. Generate three compact test functions using loops, never numbered cases.",
        prompt + "\nThe following describes the FUNCTION UNDER TEST; do not implement it yourself:\n"
        + "\n".join(NAVIGATION_CONTRACT.splitlines()[1:-1]) + "\n" + json.dumps(context, indent=2)))
    if not validate_test_code(code):
        raise ValueError("Generated tests failed structural validation; no fallback used.")
    return code
