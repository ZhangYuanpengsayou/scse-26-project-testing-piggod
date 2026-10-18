import json
import re
from model_client import chat


MODEL_NAME = "qwen3:8b"
ALLOWED_ACTIONS = ["FORWARD", "LEFT", "RIGHT", "STOP"]


PLANNER_SYSTEM_PROMPT = """You are a planner agent for a robot navigation software project.
You receive only the validated requirements artifact from the analyst agent.
You must not assume any extra actions beyond FORWARD, LEFT, RIGHT, and STOP.
You must create a practical navigation plan that a developer agent can turn into Python code.
Return valid JSON only.
Do not use markdown.
Do not explain your answer."""


def ask_qwen(system_prompt, user_prompt):
    return chat("planner", system_prompt, user_prompt, "json")



def parse_json_response(response_text):
    response_text = response_text.strip()

    try:
        return json.loads(response_text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", response_text, re.DOTALL)

        if match is None:
            return None

        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            return None


def validate_requirements(requirement):
    required_keys = {
        "goal",
        "allowed_actions",
        "safe_stop",
        "avoid_obstacles",
    }

    if not isinstance(requirement, dict):
        return False

    if set(requirement.keys()) != required_keys:
        return False

    if not isinstance(requirement["goal"], str) or not requirement["goal"].strip():
        return False

    if requirement["allowed_actions"] != ALLOWED_ACTIONS:
        return False

    if requirement["safe_stop"] is not True:
        return False

    if requirement["avoid_obstacles"] is not True:
        return False

    return True


def validate_plan(data):
    required_keys = {
        "strategy",
        "decisions",
        "stop_condition",
    }

    if not isinstance(data, dict):
        return False

    if set(data.keys()) != required_keys:
        return False

    if not isinstance(data["strategy"], str) or not data["strategy"].strip():
        return False

    if not isinstance(data["decisions"], list) or len(data["decisions"]) == 0:
        return False

    for decision in data["decisions"]:
        if not isinstance(decision, dict):
            return False

        if set(decision.keys()) != {"condition", "action", "reason"}:
            return False

        if not isinstance(decision["condition"], str) or not decision["condition"].strip():
            return False

        if decision["action"] not in ALLOWED_ACTIONS:
            return False

        if not isinstance(decision["reason"], str) or not decision["reason"].strip():
            return False

    if not isinstance(data["stop_condition"], str) or not data["stop_condition"].strip():
        return False

    if not any(decision["action"] == "STOP" for decision in data["decisions"]):
        return False

    planned_actions = {
        decision["action"]
        for decision in data["decisions"]
    }
    if planned_actions != set(ALLOWED_ACTIONS):
        return False

    if [item["action"] for item in data["decisions"]] != [
        "FORWARD", "LEFT", "RIGHT", "FORWARD", "LEFT", "RIGHT", "STOP"
    ]:
        return False

    return True


def run_planner(requirement):
    if not validate_requirements(requirement):
        raise ValueError("The Planner Agent received invalid requirements.")

    user_prompt = f"""Create a robot navigation plan from this validated requirements artifact:

{json.dumps(requirement, indent=4)}

Return exactly this JSON structure:

{{
    "strategy": "string describing the overall robot navigation strategy",
    "decisions": [
        {{
            "condition": "string describing sensor or navigation condition",
            "action": "one of FORWARD, LEFT, RIGHT, STOP",
            "reason": "string explaining why this action is selected"
        }}
    ],
    "stop_condition": "string describing when the robot must stop"
}}

Rules:
- Use only these actions: FORWARD, LEFT, RIGHT, STOP.
- Include at least one decision for each action: FORWARD, LEFT, RIGHT, STOP.
- Include at least one STOP decision.
- The decisions list MUST contain exactly SEVEN entries, evaluated in order,
  first matching condition wins. Output each of these seven, do not omit fallback entries:
  1. goal_ahead and not front_blocked -> FORWARD
  2. goal_on_left and not left_blocked -> LEFT
  3. goal_on_right and not right_blocked -> RIGHT
  4. not front_blocked -> FORWARD (fallback when no safe goal-directed action matched)
  5. not left_blocked -> LEFT (fallback)
  6. not right_blocked -> RIGHT (fallback)
  7. all three directions blocked -> STOP
- Explain in strategy that entries are evaluated in this order and optional goal flags default false.
- STOP when all directions are blocked. The simulator handles arrival at the goal.
- The state has front_blocked, left_blocked, right_blocked and optional goal_ahead,
  goal_on_left, goal_on_right; no goal_reached field exists.
- Ordered decisions: first SAFE goal-ahead, then SAFE goal-left, then SAFE goal-right.
  Otherwise first unblocked FORWARD, LEFT, RIGHT, otherwise STOP.
- Every moving decision must require its own direction to be unblocked.
- Describe this priority explicitly, including ties with multiple goal flags true.
- Include obstacle avoidance decisions.
- The stop_condition must respect safe_stop.
- Return only the JSON object."""

    response_text = ask_qwen(PLANNER_SYSTEM_PROMPT, user_prompt)
    plan = parse_json_response(response_text)

    if not validate_plan(plan):
        raise ValueError("Qwen did not return a valid navigation plan.")

    return plan
