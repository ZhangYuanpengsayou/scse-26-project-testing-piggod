import json
from datetime import datetime
from pathlib import Path

from analyst_agent import run_analyst
from benchmark_irsim import run_benchmark
from developer_agent import run_developer, run_developer_revision
from planner_agent import run_planner
from reviewer_agent import run_reviewer_agent
from reviewer_benchmark_agent import run_benchmark_reviewer_agent
from runner import run_simulation
from test_agent import run_test_agent


BASE_DIR = Path(__file__).resolve().parent
ARTIFACTS_DIR = BASE_DIR / "artifacts"
GENERATED_DIR = BASE_DIR / "generated"
TRACE_PATH = BASE_DIR / "trace.log"


def log_event(message):
    timestamp = datetime.now().isoformat(timespec="seconds")
    with open(TRACE_PATH, "a", encoding="utf-8") as file:
        file.write(f"{timestamp} {message}\n")


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path, data):
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(data, indent=4), encoding="utf-8")


def main():
    ARTIFACTS_DIR.mkdir(exist_ok=True)
    GENERATED_DIR.mkdir(exist_ok=True)
    TRACE_PATH.write_text("", encoding="utf-8")

    brief_path = BASE_DIR / "brief.txt"
    requirements_path = ARTIFACTS_DIR / "requirements.json"
    plan_path = ARTIFACTS_DIR / "plan.json"
    navigation_path = GENERATED_DIR / "navigation_logic.py"
    generated_tests_path = BASE_DIR / "test_generated_navigation_logic.py"
    simulation_report_path = ARTIFACTS_DIR / "simulation_report.json"
    simulation_review_path = ARTIFACTS_DIR / "simulation_review.json"
    benchmark_review_path = ARTIFACTS_DIR / "irsim_benchmark_review.json"
    revised_navigation_path = GENERATED_DIR / "navigation_logic_revised.py"

    brief_text = brief_path.read_text(encoding="utf-8")
    log_event("Loaded brief.txt")

    try:
        requirements = run_analyst(brief_text)
        log_event("Analyst Agent created requirements.json")
    except Exception as exc:
        requirements = read_json(requirements_path)
        log_event(f"Analyst Agent fallback loaded existing requirements.json: {exc}")
    write_json(requirements_path, requirements)

    try:
        plan = run_planner(requirements)
        log_event("Planner Agent created plan.json")
    except Exception as exc:
        plan = read_json(plan_path)
        log_event(f"Planner Agent fallback loaded existing plan.json: {exc}")
    write_json(plan_path, plan)

    navigation_code = run_developer(plan)
    navigation_path.write_text(navigation_code + "\n", encoding="utf-8")
    log_event("Developer Agent created generated/navigation_logic.py")

    test_code = run_test_agent(requirements, plan)
    generated_tests_path.write_text(test_code + "\n", encoding="utf-8")
    log_event("Test Agent created test_generated_navigation_logic.py")

    simulation_report = run_simulation()
    write_json(simulation_report_path, simulation_report)
    log_event("Simulation Runner created simulation_report.json")

    simulation_review = run_reviewer_agent(simulation_report)
    write_json(simulation_review_path, simulation_review)
    log_event("Reviewer Agent created simulation_review.json")

    benchmark_report = run_benchmark()
    log_event("IR-SIM benchmark created irsim_benchmark_report.json")

    benchmark_review = run_benchmark_reviewer_agent(benchmark_report)
    write_json(benchmark_review_path, benchmark_review)
    log_event("Benchmark Reviewer created irsim_benchmark_review.json")

    if simulation_review["needs_revision"] or benchmark_review["needs_revision"]:
        revised_code = run_developer_revision(
            navigation_code,
            {
                "simulation_review": simulation_review,
                "benchmark_review": benchmark_review,
            },
            benchmark_report,
            requirements,
            plan,
            output_path=revised_navigation_path,
        )
        log_event("Developer Revision Agent created generated/navigation_logic_revised.py")
        print(revised_code)
    else:
        log_event("Developer Revision Agent skipped because no revision was required")

    log_event("Pipeline completed")
    print("Pipeline completed. See trace.log and artifacts/.")


if __name__ == "__main__":
    main()
