import hashlib
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
    if report.get("error") or report.get("return_code", 0) != 0 or not report.get("reached_goal", False):
        return "failed"

    if 0 < report.get("steps_taken", 0) <= EFFICIENT_STEP_LIMIT:
        return "efficient"

    return "acceptable_but_inefficient"


def run_irsim_benchmark_for_world(world_file, timeout=180, navigation_path=None, output_dir=None):
    world_file = Path(world_file).resolve()
    navigation_path = Path(navigation_path or BASE_DIR / "generated" / "navigation_logic.py").resolve()
    output_dir = Path(output_dir or ARTIFACTS_DIR / "benchmark_runs").resolve()
    work_dir = output_dir / world_file.stem
    work_dir.mkdir(parents=True, exist_ok=True)
    report_path = work_dir / "artifacts" / "irsim_report.json"
    if report_path.exists():
        report_path.unlink()
    env = os.environ.copy()
    env.update(MPLBACKEND="Agg", PYTHONIOENCODING="utf-8")
    command = [sys.executable, "-X", "utf8", str(BASE_DIR / "candidate_worker.py"),
               "irsim", str(navigation_path), str(world_file)]
    report = {"reached_goal": False, "collision_or_done": True, "steps_taken": 0,
              "return_code": None}
    try:
        completed = subprocess.run(command, cwd=work_dir, capture_output=True,
                                   text=True, encoding="utf-8", timeout=timeout, env=env)
        (work_dir / "stdout.log").write_text(completed.stdout, encoding="utf-8")
        (work_dir / "stderr.log").write_text(completed.stderr, encoding="utf-8")
        report["return_code"] = completed.returncode
        if completed.returncode != 0:
            raise RuntimeError(f"Simulator exited with {completed.returncode}; see stderr.log")
        raw = json.loads(report_path.read_text(encoding="utf-8"))
        if (type(raw.get("reached_goal")) is not bool
                or type(raw.get("collision_or_done")) is not bool
                or type(raw.get("steps_taken")) is not int
                or not 0 < raw["steps_taken"] <= 300):
            raise ValueError("Malformed simulator report")
        report.update(raw)
    except Exception as exc:
        report.update(error=f"{type(exc).__name__}: {exc}", reached_goal=False)
    report.update(world_file=str(world_file), world_name=world_file.name,
                  candidate_sha256=hashlib.sha256(navigation_path.read_bytes()).hexdigest(),
                  world_sha256=hashlib.sha256(world_file.read_bytes()).hexdigest())
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


def run_benchmark(navigation_path=None, output_dir=None):
    output_dir = Path(output_dir or ARTIFACTS_DIR)
    worlds = world_files()
    if not worlds:
        raise ValueError("No benchmark worlds found")
    results = [run_irsim_benchmark_for_world(path, navigation_path=navigation_path,
               output_dir=output_dir / "world_runs") for path in worlds]
    report = build_benchmark_report(results)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "irsim_benchmark_report.json").write_text(
        json.dumps(report, indent=4), encoding="utf-8")
    return report



def main():
    report = run_benchmark()
    print(json.dumps(report, indent=4))
    print()
    print("Saved to artifacts/irsim_benchmark_report.json")


if __name__ == "__main__":
    main()
