REQUIRED_KEYS = {
    "issue",
    "likely_cause",
    "recommendation",
    "safety_passed",
    "goal_completion_passed",
    "efficiency_passed",
    "needs_revision",
}


BENCHMARK_REVIEWER_SYSTEM_PROMPT = """You are a benchmark reviewer agent.
Analyze an IR-SIM benchmark report and return valid JSON only with these keys:
issue, likely_cause, recommendation, safety_passed, goal_completion_passed,
efficiency_passed, needs_revision."""


def validate_benchmark_review(data):
    if not isinstance(data, dict):
        raise ValueError("Benchmark review must be a JSON object.")

    if set(data.keys()) != REQUIRED_KEYS:
        raise ValueError("Benchmark review does not contain the required keys.")

    for key in ["issue", "likely_cause", "recommendation"]:
        if not isinstance(data[key], str):
            raise ValueError(f"{key} must be a string.")

    for key in [
        "safety_passed",
        "goal_completion_passed",
        "efficiency_passed",
        "needs_revision",
    ]:
        if not isinstance(data[key], bool):
            raise ValueError(f"{key} must be a boolean.")

    return data


def build_deterministic_benchmark_review(benchmark_report):
    results = benchmark_report.get("results", [])
    unsafe_results = [
        result
        for result in results
        if result.get("collision_or_done") and not result.get("reached_goal")
    ]

    safety_passed = len(unsafe_results) == 0
    goal_completion_passed = benchmark_report.get("success_rate", 0) >= 1.0
    efficiency_passed = (
        benchmark_report.get("inefficient_success_worlds", 0) == 0
        and benchmark_report.get("efficiency_rate", 0) >= 1.0
    )
    needs_revision = not (
        safety_passed
        and goal_completion_passed
        and efficiency_passed
    )

    if not safety_passed:
        issue = "Unsafe benchmark behavior detected"
        likely_cause = "At least one world ended before reaching the goal, indicating collision, timeout, or terminal failure."
        recommendation = "Revise obstacle handling and re-run every IR-SIM world."
    elif not goal_completion_passed:
        issue = "Goal completion failure"
        likely_cause = "The robot did not reach the goal in every benchmark world."
        recommendation = "Improve goal-directed movement and blocked-direction handling."
    elif not efficiency_passed:
        issue = "Successful but inefficient navigation"
        likely_cause = "The robot reached goals but required too many steps in at least one world."
        recommendation = "Improve turn selection and reduce unnecessary movement."
    else:
        issue = "Benchmark passed"
        likely_cause = "All benchmark worlds reached the goal safely and efficiently."
        recommendation = "No revision is required."

    return validate_benchmark_review({
        "issue": issue,
        "likely_cause": likely_cause,
        "recommendation": recommendation,
        "safety_passed": safety_passed,
        "goal_completion_passed": goal_completion_passed,
        "efficiency_passed": efficiency_passed,
        "needs_revision": needs_revision,
    })


def run_benchmark_reviewer_agent(benchmark_report):
    return build_deterministic_benchmark_review(benchmark_report)
