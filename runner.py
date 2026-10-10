import json
import sys
import importlib
from itertools import product
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
GENERATED_DIR = BASE_DIR / "generated"
sys.path.insert(0, str(GENERATED_DIR))


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


def run_simulation():
    if "navigation_logic" in sys.modules:
        del sys.modules["navigation_logic"]
    navigation_logic = importlib.import_module("navigation_logic")
    decide_next_move = navigation_logic.decide_next_move

    results = []

    for scenario in all_possible_scenarios():
        actual = decide_next_move(scenario["state"])
        passed = actual == scenario["expected"]
        results.append({
            "id": scenario["id"],
            "state": scenario["state"],
            "expected": scenario["expected"],
            "actual": actual,
            "passed": passed,
        })

    total = len(results)
    passed_count = sum(1 for result in results if result["passed"])
    failed_count = total - passed_count

    return {
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
