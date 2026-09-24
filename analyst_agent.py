import json
import re
import urllib.request


MODEL_NAME = "qwen3:8b"


def ask_qwen(system_prompt, user_prompt):
    data = {
        "model": MODEL_NAME,
        "messages": [
            {
                "role": "system",
                "content": system_prompt
            },
            {
                "role": "user",
                "content": user_prompt
            }
        ],
        "stream": False
    }

    request = urllib.request.Request(
        "http://127.0.0.1:11434/api/chat",
        data=json.dumps(data).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST"
    )

    with urllib.request.urlopen(request, timeout=120) as response:
        result = json.loads(response.read().decode("utf-8"))

    return result["message"]["content"]


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


def validate_requirements(result):
    required_keys = {
        "goal",
        "allowed_actions",
        "safe_stop",
        "avoid_obstacles"
    }

    if not isinstance(result, dict):
        return False

    if set(result.keys()) != required_keys:
        return False

    if not isinstance(result["goal"], str):
        return False

    if result["allowed_actions"] != ["FORWARD", "LEFT", "RIGHT", "STOP"]:
        return False

    if not isinstance(result["safe_stop"], bool):
        return False

    if not isinstance(result["avoid_obstacles"], bool):
        return False

    return True


def run_analyst(brief_text):
    system_prompt = """You are an analyst agent for a software engineering project.
Your only responsibility is to convert a human project brief into explicit software requirements.
You must return valid JSON only.
Do not explain your answer.
Do not use markdown.
Do not add any extra keys.
The allowed robot navigation actions must be only FORWARD, LEFT, RIGHT, and STOP."""

    user_prompt = f"""Convert the following robot navigation brief into this exact JSON structure:

{{
    "goal": "string",
    "allowed_actions": ["FORWARD", "LEFT", "RIGHT", "STOP"],
    "safe_stop": true,
    "avoid_obstacles": true
}}

Rules:
- The "goal" value must describe the navigation objective from the brief.
- The "allowed_actions" value must be exactly ["FORWARD", "LEFT", "RIGHT", "STOP"].
- The "safe_stop" value must be true if the robot should stop when no safe path exists.
- The "avoid_obstacles" value must be true if the robot must avoid blocked directions.
- Return only the JSON object.

Brief:
{brief_text}"""

    response_text = ask_qwen(system_prompt, user_prompt)
    requirements = parse_json_response(response_text)

    if not validate_requirements(requirements):
        raise ValueError("Qwen did not return valid requirements JSON.")

    return requirements
