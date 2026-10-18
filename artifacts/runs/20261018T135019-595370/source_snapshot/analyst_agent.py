import json
from model_client import MODEL_NAME, chat


def ask_qwen(system_prompt, user_prompt):
    return chat("analyst", system_prompt, user_prompt, "json")


def parse_json_response(response_text):
    try:
        return json.loads(response_text)
    except json.JSONDecodeError:
        return None


def validate_requirements(result):
    return (
        isinstance(result, dict)
        and set(result) == {"goal", "allowed_actions", "safe_stop", "avoid_obstacles"}
        and isinstance(result["goal"], str) and bool(result["goal"].strip())
        and result["goal"].strip().lower() not in {"navigation objective", "string", "goal"}
        and result["allowed_actions"] == ["FORWARD", "LEFT", "RIGHT", "STOP"]
        and result["safe_stop"] is True and result["avoid_obstacles"] is True
    )


def run_analyst(brief_text):
    response = ask_qwen(
        "You are a requirements analyst. Return only the exact JSON schema requested.",
        'Convert this brief into {"goal":"navigation objective",'
        '"allowed_actions":["FORWARD","LEFT","RIGHT","STOP"],'
        '"safe_stop":true,"avoid_obstacles":true}. No extra keys. '
        'Replace the goal placeholder with a specific sentence summarizing this brief: '
        'moving the mobile robot toward its goal while avoiding blocked directions, '
        'and stopping when no safe path exists. Never copy the placeholder.\n' + brief_text)
    requirements = parse_json_response(response)
    if not validate_requirements(requirements):
        raise ValueError("Qwen returned invalid or unsafe requirements; no fallback used.")
    return requirements
