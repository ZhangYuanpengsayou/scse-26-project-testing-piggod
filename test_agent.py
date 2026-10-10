import json
import re
import urllib.request


MODEL_NAME = "qwen3:8b"


TEST_AGENT_SYSTEM_PROMPT = """You are a test agent for robot navigation logic.
Generate pytest-style tests for a decide_next_move(state) function.
Return Python code only.
Do not use markdown.
Do not explain your answer."""


DETERMINISTIC_TEST_CODE = '''import sys
from itertools import product
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
GENERATED_DIR = BASE_DIR / "generated"
sys.path.insert(0, str(GENERATED_DIR))

from navigation_logic import decide_next_move


VALID_ACTIONS = {"FORWARD", "LEFT", "RIGHT", "STOP"}


def expected_action(state):
    if state["goal_ahead"] and not state["front_blocked"]:
        return "FORWARD"
    if state["goal_on_left"] and not state["left_blocked"]:
        return "LEFT"
    if state["goal_on_right"] and not state["right_blocked"]:
        return "RIGHT"
    if not state["front_blocked"]:
        return "FORWARD"
    if not state["left_blocked"]:
        return "LEFT"
    if not state["right_blocked"]:
        return "RIGHT"
    return "STOP"


def all_possible_states():
    keys = [
        "goal_ahead",
        "goal_on_left",
        "goal_on_right",
        "front_blocked",
        "left_blocked",
        "right_blocked",
    ]

    for values in product([False, True], repeat=len(keys)):
        state = dict(zip(keys, values))
        yield state, expected_action(state)


def test_decide_next_move_for_all_possible_states():
    for state, expected in all_possible_states():
        action = decide_next_move(state)
        assert action in VALID_ACTIONS
        assert action == expected


def test_typical_case_from_instructions():
    state = {
        "goal_ahead": True,
        "goal_on_left": False,
        "goal_on_right": False,
        "front_blocked": False,
        "left_blocked": False,
        "right_blocked": False,
    }
    assert decide_next_move(state) == "FORWARD"


if __name__ == "__main__":
    test_decide_next_move_for_all_possible_states()
    test_typical_case_from_instructions()
    print("All generated navigation logic tests passed.")
'''


def ask_qwen(system_prompt, user_prompt):
    data = {
        "model": MODEL_NAME,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
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


def validate_test_code(code_text):
    if not isinstance(code_text, str) or not code_text.strip():
        return False

    if "```" in code_text:
        return False

    required_fragments = [
        "from navigation_logic import decide_next_move",
        "assert",
        "goal_ahead",
        "goal_on_left",
        "goal_on_right",
        "front_blocked",
        "left_blocked",
        "right_blocked",
        "FORWARD",
        "LEFT",
        "RIGHT",
        "STOP",
    ]

    return all(fragment in code_text for fragment in required_fragments)


def deterministic_test_code():
    return DETERMINISTIC_TEST_CODE.strip()


def run_test_agent(requirements, plan):
    user_prompt = f"""Generate pytest tests for generated/navigation_logic.py.

Requirements:
{json.dumps(requirements, indent=4)}

Plan:
{json.dumps(plan, indent=4)}

The generated tests must:
- Import decide_next_move from generated/navigation_logic.py.
- Cover every possible combination of the six boolean state fields.
- Validate that the returned action is one of FORWARD, LEFT, RIGHT, STOP.
- Assert the expected action for each state.
- Return Python code only."""

    try:
        code_text = strip_markdown_fence(
            ask_qwen(TEST_AGENT_SYSTEM_PROMPT, user_prompt)
        )
    except Exception:
        code_text = deterministic_test_code()

    if not validate_test_code(code_text):
        code_text = deterministic_test_code()

    return code_text
