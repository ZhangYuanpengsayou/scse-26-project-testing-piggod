import ast
import json
from developer_agent import strip_markdown_fence
from model_client import MODEL_NAME, chat


def ask_qwen(system_prompt, user_prompt):
    return chat("test_agent", system_prompt, user_prompt)


def assemble_test_code(response):
    """Add fixed dependencies; never replace or edit model-generated assertions."""
    code = strip_markdown_fence(response)
    try:
        tree = ast.parse(code)
    except SyntaxError as exc:
        raise ValueError("Generated test source is not valid Python") from exc
    imports = {(node.module, alias.name) for node in tree.body
               if isinstance(node, ast.ImportFrom) and node.level == 0
               for alias in node.names if alias.asname is None}
    header = ["# Qwen-generated tests; missing standard imports are supplied by test_agent.py."]
    for module, name in [("itertools", "product"), ("generated.navigation_logic", "decide_next_move")]:
        if (module, name) not in imports:
            header.append(f"from {module} import {name}")
    return "\n".join(header) + "\n\n" + code


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
    prompt = """Generate Python tests. Use exactly 3 zero-argument test functions, no fixtures.
Import product from itertools and decide_next_move from generated.navigation_logic.
Use this EXPLICIT mapping; action strings and sensor keys are not interchangeable:
directions = [('FORWARD', 'goal_ahead', 'front_blocked'),
              ('LEFT', 'goal_on_left', 'left_blocked'),
              ('RIGHT', 'goal_on_right', 'right_blocked')]

test_all_states:
- keys are goal_ahead, goal_on_left, goal_on_right, front_blocked, left_blocked, right_blocked.
- Loop over product([False, True], repeat=6); state = dict(zip(keys, values)).
- Compute safe = [a for a, g, b in directions if not state[b]].
- Compute toward = [a for a, g, b in directions if state[g] and not state[b]].
- Assert decide_next_move(state) == (toward or safe or ['STOP'])[0].

test_typical_case:
- Include ALL SIX keys. goal_ahead=True; all other five values=False.
- Assert the action is FORWARD. All THREE obstacle keys are mandatory.

test_optional_goals:
- keys are ONLY front_blocked, left_blocked, right_blocked.
- Loop over product([False, True], repeat=3); state = dict(zip(keys, values)).
- safe = [a for a, g, b in directions if not state[b]].
- Assert decide_next_move(state) == (safe or ['STOP'])[0].

Add an __main__ block invoking the three functions and printing success.
Return only complete Python code, fewer than 60 lines. No numbered individual cases.
Do not define the navigation function; import it. No imports other than the two specified.
The following real project context is evidence for the tests:\n"""
    context = {"brief": brief_text, "requirements": requirements, "plan": plan,
               "candidate_code": navigation_code}
    if feedback is not None:
        report = feedback.get("execution_report", {})
        context["previous_failure"] = {
            "errors": [{key: item.get(key) for key in ("test", "error_type", "error")}
                       for item in report.get("results", []) if not item.get("passed")],
            "invalid_test_inputs": report.get("invalid_test_inputs", []),
            "coverage": report.get("unique_boolean_states_exercised", 0),
            "optional_coverage": report.get("unique_optional_goal_states_exercised", 0),
        }
    prompt += json.dumps(context, indent=2)
    prompt += """
FINAL CHECK BEFORE RETURNING CODE:
Use the supplied directions tuples in BOTH list comprehensions.
Use state[b], NEVER state[f'{a}_blocked'], NEVER derive sensor keys with split/lower.
FORWARD maps to front_blocked, not FORWARD_blocked or forward_blocked.
The typical-case dictionary must have all six keys.
The optional-goal dictionary must have exactly the three obstacle keys.
Generate tests from scratch following this algorithm; do not copy a previous faulty test.
"""
    code = assemble_test_code(ask_qwen(
        "You write compact, executable Python tests using the explicit algorithm provided. Return code only.",
        prompt))
    if not validate_test_code(code):
        raise ValueError("Generated tests failed structural validation; no fallback used.")
    return code
