"""Run one exact candidate in a fresh process, without altering the supplied simulator."""
import argparse
import hashlib
import inspect
import json
import runpy
import sys
import traceback
import types
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent


def load_candidate(path):
    path = Path(path).resolve()
    source = path.read_bytes()
    module = types.ModuleType("generated.navigation_logic")
    module.__file__ = str(path)
    exec(compile(source, str(path), "exec"), module.__dict__)
    package = types.ModuleType("generated")
    package.__path__ = [str(path.parent)]
    package.navigation_logic = module
    sys.modules.update({"generated": package, "generated.navigation_logic": module,
                        "navigation_logic": module})
    return module, hashlib.sha256(source).hexdigest()


def run_tests(candidate, tests):
    module, digest = load_candidate(candidate)
    visited_states = set()
    optional_goal_states = set()
    invalid_test_inputs = []
    real_function = module.decide_next_move

    def tracked(state):
        keys = ("goal_ahead", "goal_on_left", "goal_on_right",
                "front_blocked", "left_blocked", "right_blocked")
        if not isinstance(state, dict) or not all(k in state for k in keys[3:]):
            invalid_test_inputs.append({"state": state,
                "error": "These contract tests must supply all three obstacle fields; the typical case must have all six fields."})
        if isinstance(state, dict) and all(type(state.get(k)) is bool for k in keys):
            visited_states.add(tuple(state[k] for k in keys))
        if (isinstance(state, dict) and not any(k in state for k in keys[:3])
                and all(type(state.get(k)) is bool for k in keys[3:])):
            optional_goal_states.add(tuple(state[k] for k in keys[3:]))
        return real_function(state)

    module.decide_next_move = tracked
    namespace = runpy.run_path(str(tests), run_name="generated_tests_under_review")
    functions = sorted((name, value) for name, value in namespace.items()
                       if name.startswith("test_") and inspect.isfunction(value))
    if not functions:
        raise ValueError("No test functions collected; refusing an empty success.")
    results = []
    for name, function in functions:
        try:
            function()
            results.append({"test": name, "passed": True})
        except Exception as exc:
            results.append({"test": name, "passed": False,
                            "error_type": type(exc).__name__, "error": str(exc),
                            "traceback": traceback.format_exc()})
    return {"candidate_sha256": digest, "collected": len(results),
            "unique_boolean_states_exercised": len(visited_states),
            "unique_optional_goal_states_exercised": len(optional_goal_states),
            "invalid_test_inputs": invalid_test_inputs,
            "passed": (all(item["passed"] for item in results) and len(visited_states) == 64
                       and len(optional_goal_states) == 8 and not invalid_test_inputs),
            "results": results}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["tests", "simulation", "irsim"])
    parser.add_argument("candidate", type=Path)
    parser.add_argument("target", type=Path)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    if args.mode == "irsim":
        load_candidate(args.candidate)
        script = BASE_DIR / "test_irsim_with_agent.py"
        sys.argv = [str(script), str(args.target)]
        runpy.run_path(str(script), run_name="__main__")
        return 0
    try:
        if args.mode == "tests":
            report = run_tests(args.candidate, args.target)
        else:
            from runner import run_simulation
            report = run_simulation(args.candidate)
            report["passed_check"] = (report["failed"] == 0 and report["total_scenarios"] == 64
                                      and report["optional_goals_passed"])
    except Exception as exc:
        report = {"passed": False, "error": str(exc), "traceback": traceback.format_exc()}
    args.report.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return 0 if report.get("passed_check", report.get("passed", False)) else 1


if __name__ == "__main__":
    raise SystemExit(main())
