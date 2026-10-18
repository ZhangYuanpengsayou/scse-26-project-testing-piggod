import ast
import json
import re
from pathlib import Path
from model_client import MODEL_NAME, chat

NAVIGATION_CONTRACT = """Define exactly one pure function decide_next_move(state), without imports.
Return only FORWARD, LEFT, RIGHT, STOP. Use state.get for keys.
For the six boolean keys, select the FIRST safe goal-directed action in this order:
goal_ahead/front_blocked/FORWARD, goal_on_left/left_blocked/LEFT,
goal_on_right/right_blocked/RIGHT. If none, select the FIRST unblocked action
in order FORWARD, LEFT, RIGHT. STOP only if all directions are blocked.
Goal flags are optional and default False; do not require goal_reached (the simulator
handles arrival). Goal values can be Python bool or NumPy boolean scalars, so use
truth testing, not identity comparison with True. Do not mutate the input.
Return only Python source, no prose or markdown."""


def ask_qwen(system_prompt, user_prompt, response_format=None):
    stage = "revision" if "revision" in system_prompt.lower() else "developer"
    return chat(stage, system_prompt, user_prompt, response_format)


def strip_markdown_fence(text):
    match = re.fullmatch(r"```(?:python)?\s*(.*?)\s*```", text.strip(), re.DOTALL)
    return match.group(1).strip() if match else text.strip()


def validate_navigation_code(code_text):
    try:
        tree = ast.parse(code_text)
    except (SyntaxError, TypeError):
        return False
    if len(tree.body) != 1 or not isinstance(tree.body[0], ast.FunctionDef):
        return False
    function = tree.body[0]
    if (function.name != "decide_next_move" or function.decorator_list
            or len(function.args.args) != 1 or function.args.args[0].arg != "state"
            or function.args.defaults or function.args.kwonlyargs
            or function.args.posonlyargs or function.args.vararg or function.args.kwarg):
        return False
    # A narrow code-review guard, NOT a security sandbox for hostile code.
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom, ast.Global, ast.Nonlocal, ast.While)):
            return False
        if isinstance(node, ast.Attribute) and node.attr != "get":
            return False
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id not in {"bool", "isinstance", "all", "any", "len", "zip"}:
                return False
            if not isinstance(node.func, (ast.Name, ast.Attribute)):
                return False
    return all(action in code_text for action in ("FORWARD", "LEFT", "RIGHT", "STOP"))


def checked_code(response):
    code = strip_markdown_fence(response)
    if not validate_navigation_code(code):
        raise ValueError("Generated navigation failed structural validation; no fallback used.")
    return code


def run_developer(plan):
    return checked_code(ask_qwen("You are a Python developer agent.",
        NAVIGATION_CONTRACT + "\nValidated plan:\n" + json.dumps(plan, indent=2)))


def run_developer_revision(original_navigation_code, review_notes, benchmark_report,
                           requirements, plan, output_path=None):
    context = {"original_navigation_code": original_navigation_code,
               "review_notes": review_notes, "benchmark_report": benchmark_report,
               "requirements": requirements, "plan": plan}
    revised = checked_code(ask_qwen("You are a Python developer revision agent.",
        NAVIGATION_CONTRACT + "\nRevise using this evidence. Preserve verified behavior.\n"
        + json.dumps(context, indent=2)))
    if output_path is not None:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(revised + "\n", encoding="utf-8")
    return revised
