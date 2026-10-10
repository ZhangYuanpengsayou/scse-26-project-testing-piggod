import ast
import json
import re
import urllib.request
from pathlib import Path


MODEL_NAME = "qwen3:8b"
ALLOWED_ACTIONS = {"FORWARD", "LEFT", "RIGHT", "STOP"}


DEVELOPER_SYSTEM_PROMPT = """You are a developer agent for a robot navigation project.
You receive a validated navigation plan and generate Python code.
Return Python code only.
Do not use markdown.
Do not explain your answer."""


REVISION_SYSTEM_PROMPT = """You are a developer revision agent.
You receive the original navigation code, review notes, benchmark results,
requirements, and plan. Generate improved Python navigation logic.
Return Python code only.
Do not use markdown.
Do not explain your answer."""


DETERMINISTIC_NAVIGATION_CODE = '''def decide_next_move(state):
    if state.get("goal_ahead", False) and not state.get("front_blocked", False):
        return "FORWARD"
    if state.get("goal_on_left", False) and not state.get("left_blocked", False):
        return "LEFT"
    if state.get("goal_on_right", False) and not state.get("right_blocked", False):
        return "RIGHT"
    if not state.get("front_blocked", False):
        return "FORWARD"
    if not state.get("left_blocked", False):
        return "LEFT"
    if not state.get("right_blocked", False):
        return "RIGHT"
    return "STOP"
'''


def ask_qwen(system_prompt, user_prompt, response_format=None):
    data = {
        "model": MODEL_NAME,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "stream": False,
    }

    if response_format is not None:
        data["format"] = response_format

    request = urllib.request.Request(
        "http://127.0.0.1:11434/api/chat",
        data=json.dumps(data).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    with urllib.request.urlopen(request, timeout=120) as response:
        result = json.loads(response.read().decode("utf-8"))

    return result["message"]["content"]


def strip_markdown_fence(text):
    text = text.strip()
    match = re.search(r"```(?:python)?\s*(.*?)```", text, re.DOTALL)

    if match is None:
        return text

    return match.group(1).strip()


def validate_navigation_code(code_text):
    if not isinstance(code_text, str) or not code_text.strip():
        return False

    if "```" in code_text:
        return False

    try:
        tree = ast.parse(code_text)
    except SyntaxError:
        return False

    function_names = {
        node.name
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
    }

    if "decide_next_move" not in function_names:
        return False

    return all(action in code_text for action in ALLOWED_ACTIONS)


def deterministic_navigation_code():
    return DETERMINISTIC_NAVIGATION_CODE.strip()


def run_developer(plan):
    user_prompt = f"""Generate Python code from this validated navigation plan:

{json.dumps(plan, indent=4)}

Rules:
- Return Python code only.
- Define a function named decide_next_move(state).
- state is a dictionary with these boolean keys:
  goal_ahead, goal_on_left, goal_on_right, front_blocked, left_blocked, right_blocked.
- The function must return only FORWARD, LEFT, RIGHT, or STOP.
- Prefer moving toward the goal when the target direction is not blocked.
- Never move into a blocked direction.
- Return STOP if no safe movement is available.
- Use state.get("key_name", default_value), not direct dictionary indexing."""

    try:
        code_text = strip_markdown_fence(
            ask_qwen(DEVELOPER_SYSTEM_PROMPT, user_prompt)
        )
    except Exception:
        code_text = deterministic_navigation_code()

    if not validate_navigation_code(code_text):
        code_text = deterministic_navigation_code()

    return code_text


def run_developer_revision(
    original_navigation_code,
    review_notes,
    benchmark_report,
    requirements,
    plan,
    output_path=None,
):
    user_prompt = f"""Revise this robot navigation code.

Original navigation code:
{original_navigation_code}

Simulation review notes:
{json.dumps(review_notes, indent=4)}

Benchmark report:
{json.dumps(benchmark_report, indent=4)}

Requirements:
{json.dumps(requirements, indent=4)}

Plan:
{json.dumps(plan, indent=4)}

Rules:
- Return Python code only.
- Define decide_next_move(state).
- Return only FORWARD, LEFT, RIGHT, or STOP.
- Prefer safe goal-directed movement.
- Never choose a blocked direction.
- Stop when no safe movement is available."""

    try:
        revised_code = strip_markdown_fence(
            ask_qwen(REVISION_SYSTEM_PROMPT, user_prompt)
        )
    except Exception:
        revised_code = deterministic_navigation_code()

    if not validate_navigation_code(revised_code):
        revised_code = deterministic_navigation_code()

    if output_path is not None:
        path = Path(output_path)
        path.parent.mkdir(exist_ok=True)
        path.write_text(revised_code + "\n", encoding="utf-8")

    return revised_code
