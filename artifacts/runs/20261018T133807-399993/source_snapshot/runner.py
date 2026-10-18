import json
from candidate_worker import load_candidate
from itertools import product
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
GENERATED_DIR = BASE_DIR / "generated"


def expected_action(state):
    directions = [("FORWARD", "front_blocked", "goal_ahead"),
                  ("LEFT", "left_blocked", "goal_on_left"),
                  ("RIGHT", "right_blocked", "goal_on_right")]
    safe = [item for item in directions if not state[item[1]]]
    goal_directed = [item for item in safe if state.get(item[2], False)]
    choices = goal_directed or safe
    return choices[0][0] if choices else "STOP"


def all_possible_scenarios():
    keys = [
        "goal_ahead",
        "goal_on_left",
        "goal_on_right",
        "front_blocked",
        "left_blocked",
        "right_blocked",
    ]

    for index, values in enumerate(product([False, True], repeat=len(keys)), start=1):
        state = dict(zip(keys, values))
        yield {
            "id": f"scenario-{index:02d}",
            "state": state,
            "expected": expected_action(state),
        }


def run_simulation(navigation_path=None):
    navigation_path = navigation_path or GENERATED_DIR / "navigation_logic.py"
    navigation_logic, digest = load_candidate(navigation_path)
    decide_next_move = navigation_logic.decide_next_move

    results = []

    for scenario in all_possible_scenarios():
        error = None
        state = scenario["state"].copy()
        try:
            actual = decide_next_move(state)
            passed = actual == scenario["expected"] and state == scenario["state"]
        except Exception as exc:
            actual, passed, error = None, False, str(exc)
        results.append({
            "id": scenario["id"],
            "state": scenario["state"],
            "expected": scenario["expected"],
            "actual": actual,
            "passed": passed,
            "error": error,
        })

    total = len(results)
    passed_count = sum(1 for result in results if result["passed"])
    failed_count = total - passed_count

    optional_goals = []
    for values in product([False, True], repeat=3):
        state = dict(zip(("front_blocked", "left_blocked", "right_blocked"), values))
        expected = expected_action(state)
        try:
            actual = decide_next_move(state.copy())
            optional_goals.append({"state": state, "expected": expected,
                                   "actual": actual, "passed": actual == expected})
        except Exception as exc:
            optional_goals.append({"state": state, "passed": False, "error": str(exc)})

    robustness = []
    for state in [None, {}, {"front_blocked": False},
                  {"front_blocked": False, "left_blocked": False},
                  {"left_blocked": False, "right_blocked": False},
                  {"front_blocked": False, "right_blocked": False}]:
        try:
            action = decide_next_move(state)
            robustness.append({"state": state, "expected": "STOP", "actual": action,
                               "passed": action == "STOP"})
        except Exception as exc:
            robustness.append({"state": state, "passed": False, "error": str(exc)})

    return {
        "candidate_sha256": digest,
        "optional_goal_checks": optional_goals,
        "optional_goals_passed": all(item["passed"] for item in optional_goals),
        "robustness_checks": robustness,
        "robustness_passed": all(item["passed"] for item in robustness),
        "total_scenarios": total,
        "passed": passed_count,
        "failed": failed_count,
        "success_rate": passed_count / total if total else 0,
        "results": results,
    }


def main():
    report = run_simulation()
    artifacts_dir = BASE_DIR / "artifacts"
    artifacts_dir.mkdir(exist_ok=True)
    output_path = artifacts_dir / "simulation_report.json"
    output_path.write_text(json.dumps(report, indent=4), encoding="utf-8")
    print(json.dumps(report, indent=4))
    print()
    print("Saved to artifacts/simulation_report.json")


if __name__ == "__main__":
    main()
