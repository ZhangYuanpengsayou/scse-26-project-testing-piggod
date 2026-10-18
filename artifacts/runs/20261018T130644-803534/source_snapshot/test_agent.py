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
    return (bool(tests) and any(isinstance(node, ast.Assert) for node in ast.walk(tree))
            and all(not test.args.args and not test.decorator_list for test in tests)
            and "import decide_next_move" in code)


def run_test_agent(requirements, plan, brief_text="", navigation_code=""):
    if not brief_text or not navigation_code:
        raise ValueError("Test Agent needs the brief AND the actual candidate code.")
    prompt = """Generate standalone Python tests with zero-argument test_* functions.
Only imports allowed: from itertools import product; from generated.navigation_logic import decide_next_move.
Do not use pytest, sys, pathlib, fixtures, decorators, or redefine decide_next_move.
Enumerate all 64 combinations using product([False, True], repeat=6).
Assert legal output, never a blocked action, STOP iff all blocked, and the exact
goal-first tie-breaking contract. Use an independent oracle, not a copy of the implementation.
Include a typical goal-ahead case and goal-flags-omitted cases.
Add if __name__ == '__main__': invoking every test and then printing success.
Keep code under 120 lines. Return code only.\n"""
    context = {"brief": brief_text, "requirements": requirements, "plan": plan,
               "candidate_code": navigation_code}
    code = strip_markdown_fence(ask_qwen("You are a Python Test Agent.",
        prompt + "\nThe following describes the FUNCTION UNDER TEST; do not implement it yourself:\n"
        + NAVIGATION_CONTRACT + "\n" + json.dumps(context, indent=2)))
    if not validate_test_code(code):
        raise ValueError("Generated tests failed structural validation; no fallback used.")
    return code
