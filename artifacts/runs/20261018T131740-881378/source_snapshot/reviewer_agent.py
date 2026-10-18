REQUIRED_KEYS = {
    "issue",
    "likely_cause",
    "recommendation",
    "needs_revision",
}


REVIEWER_SYSTEM_PROMPT = """You are a reviewer agent.
Analyze a robot navigation simulation report.
Return valid JSON only with these keys:
issue, likely_cause, recommendation, needs_revision."""


def validate_review(data):
    if not isinstance(data, dict):
        raise ValueError("Review must be a JSON object.")

    if set(data.keys()) != REQUIRED_KEYS:
        raise ValueError("Review does not contain the required keys.")

    for key in ["issue", "likely_cause", "recommendation"]:
        if not isinstance(data[key], str):
            raise ValueError(f"{key} must be a string.")

    if not isinstance(data["needs_revision"], bool):
        raise ValueError("needs_revision must be a boolean.")

    return data


def build_deterministic_review(simulation_report):
    failed = simulation_report.get("failed", 0)
    success_rate = simulation_report.get("success_rate", 0)

    if failed > 0:
        review = {
            "issue": "Simulation failures detected",
            "likely_cause": "decide_next_move returned an action that did not match the expected safe navigation rule.",
            "recommendation": "Revise the navigation logic so it prefers safe goal-directed movement and stops only when no safe movement exists.",
            "needs_revision": True,
        }
    elif success_rate < 1.0:
        review = {
            "issue": "Incomplete simulation success",
            "likely_cause": "Some scenarios were not handled correctly.",
            "recommendation": "Review failed scenarios and update branch conditions in decide_next_move.",
            "needs_revision": True,
        }
    else:
        review = {
            "issue": "No simulation issue detected",
            "likely_cause": "All enumerated navigation scenarios matched the expected behavior.",
            "recommendation": "No revision is required for the deterministic scenario simulation.",
            "needs_revision": False,
        }

    return validate_review(review)


def run_reviewer_agent(simulation_report):
    return build_deterministic_review(simulation_report)
