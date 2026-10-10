import json
import os
import subprocess
import sys
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
ARTIFACTS_DIR = BASE_DIR / "artifacts"
WORLD_DIR = BASE_DIR / "irsim_worlds"
IRSIM_REPORT_PATH = ARTIFACTS_DIR / "irsim_report.json"
BENCHMARK_REPORT_PATH = ARTIFACTS_DIR / "irsim_benchmark_report.json"
EFFICIENT_STEP_LIMIT = 200


def world_files():
    preferred_names = [
        "world_easy.yaml",
        "world_medium.yaml",
        "world_difficult.yaml",
        "world_hard.yaml",
        "world_custom.yaml",
    ]

    files = []
    for name in preferred_names:
        path = WORLD_DIR / name
        if path.exists() and path not in files:
            files.append(path)

    for path in sorted(WORLD_DIR.glob("*.yaml")):
        if path not in files:
            files.append(path)

    return files


def classify_result(report):
    if not report.get("reached_goal", False):
        return "failed"

    if report.get("steps_taken", 0) <= EFFICIENT_STEP_LIMIT:
        return "efficient"

    return "acceptable_but_inefficient"


def run_irsim_benchmark_for_world(world_file, timeout=180):
    ARTIFACTS_DIR.mkdir(exist_ok=True)

    if IRSIM_REPORT_PATH.exists():
        IRSIM_REPORT_PATH.unlink()

    env = os.environ.copy()
    env["MPLBACKEND"] = "Agg"

    command = [
        sys.executable,
        str(BASE_DIR / "test_irsim_with_agent.py"),
        str(world_file),
    ]

    try:
        completed = subprocess.run(
            command,
            cwd=BASE_DIR,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
        )

        if IRSIM_REPORT_PATH.exists():
            report = json.loads(IRSIM_REPORT_PATH.read_text(encoding="utf-8"))
        else:
            report = {
                "reached_goal": False,
                "collision_or_done": True,
                "steps_taken": 0,
                "efficiency_status": "failed",
                "efficiency_passed": False,
            }

        report["world_file"] = str(world_file)
        report["world_name"] = world_file.name
        report["return_code"] = completed.returncode
        report["stdout_tail"] = completed.stdout[-1000:]
        report["stderr_tail"] = completed.stderr[-1000:]

    except Exception as exc:
        report = {
            "world_file": str(world_file),
            "world_name": world_file.name,
            "reached_goal": False,
            "collision_or_done": True,
            "steps_taken": 0,
            "efficiency_status": "failed",
            "efficiency_passed": False,
            "return_code": None,
            "error": str(exc),
        }

    report["efficiency_status"] = classify_result(report)
    report["efficiency_passed"] = report["efficiency_status"] == "efficient"
    return report


def build_benchmark_report(results):
    total = len(results)
    reached_goal_count = sum(1 for result in results if result.get("reached_goal"))
    efficient_count = sum(1 for result in results if result.get("efficiency_status") == "efficient")
    inefficient_success_count = sum(
        1
        for result in results
        if result.get("efficiency_status") == "acceptable_but_inefficient"
    )
    failed_count = total - reached_goal_count
    total_steps = sum(result.get("steps_taken", 0) for result in results)

    return {
        "total_worlds": total,
        "goals_reached": reached_goal_count,
        "success_rate": reached_goal_count / total if total else 0,
        "efficient_worlds": efficient_count,
        "inefficient_success_worlds": inefficient_success_count,
        "failed_worlds": failed_count,
        "efficiency_rate": efficient_count / total if total else 0,
        "average_steps_taken": total_steps / total if total else 0,
        "results": results,
    }


def run_benchmark():
    results = [
        run_irsim_benchmark_for_world(path)
        for path in world_files()
    ]
    report = build_benchmark_report(results)
    ARTIFACTS_DIR.mkdir(exist_ok=True)
    BENCHMARK_REPORT_PATH.write_text(json.dumps(report, indent=4), encoding="utf-8")
    return report


def main():
    report = run_benchmark()
    print(json.dumps(report, indent=4))
    print()
    print("Saved to artifacts/irsim_benchmark_report.json")


if __name__ == "__main__":
    main()
