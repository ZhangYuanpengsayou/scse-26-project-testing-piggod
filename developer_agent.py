import ast
import json
import re
import urllib.request


MODEL_NAME = "qwen3:8b"
ALLOWED_ACTIONS = {"FORWARD", "LEFT", "RIGHT", "STOP"}


DEVELOPER_SYSTEM_PROMPT = """You are a developer agent for a robot navigation software project.
You receive only the validated navigation plan artifact from the planner agent.
Your task is to generate simple, readable Python code for robot navigation.
Return Python code only.
Do not use markdown.
Do not explain your answer."""


def ask_qwen(system_prompt, user_prompt):
    data = {
        "model": MODEL_NAME,
        "messages": [
            {
                "role": "system",
                "content": system_prompt,
            },
            {
                "role": "user",
                "content": user_prompt,
            },
        ],
        "stream": False,
    }

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


def validate_plan(plan):
    if not isinstance(plan, dict):
        return False

    if set(plan.keys()) != {"strategy", "decisions", "stop_condition"}:
        return False

    if not isinstance(plan["strategy"], str) or not plan["strategy"].strip():
        return False

    if not isinstance(plan["decisions"], list) or not plan["decisions"]:
        return False

    for decision in plan["decisions"]:
        if not isinstance(decision, dict):
            return False

        if set(decision.keys()) != {"condition", "action", "reason"}:
            return False

        if decision["action"] not in ALLOWED_ACTIONS:
            return False

    return isinstance(plan["stop_condition"], str) and bool(plan["stop_condition"].strip())


def validate_python_code(code_text):
    try:
        tree = ast.parse(code_text)
    except SyntaxError:
        return False

    function_names = {
        node.name
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
    }

    return "choose_navigation_action" in function_names


def run_developer(plan):
    if not validate_plan(plan):
        raise ValueError("The Developer Agent received an invalid plan.")

    user_prompt = f"""Generate Python code from this validated navigation plan:

{json.dumps(plan, indent=4)}

Rules:
- Return Python code only.
- The code must define a function named choose_navigation_action(sensor_data).
- sensor_data is a dictionary.
- Use sensor_data.get("key_name", default_value) instead of direct dictionary indexing.
- Useful sensor keys are goal_ahead, goal_on_left, goal_on_right, front_blocked, left_blocked, right_blocked.
- Do not use goal_reached, front_clear, left_clear, or right_clear.
- Use this priority order:
  1. If goal_ahead is true and front_blocked is false, return FORWARD.
  2. If goal_on_left is true and left_blocked is false, return LEFT.
  3. If goal_on_right is true and right_blocked is false, return RIGHT.
  4. If front_blocked is false, return FORWARD.
  5. If left_blocked is false, return LEFT.
  6. If right_blocked is false, return RIGHT.
  7. Otherwise return STOP.
- The function must return only one of these strings: FORWARD, LEFT, RIGHT, STOP.
- The function should use obstacle information from sensor_data.
- The function should stop if no safe movement is available.
- Keep the code simple enough for a beginner Python student to understand."""

    response_text = ask_qwen(DEVELOPER_SYSTEM_PROMPT, user_prompt)
    code_text = strip_markdown_fence(response_text)

    if not validate_python_code(code_text):
        raise ValueError("Qwen did not return valid Python navigation code.")

    return code_text
