"""Strict live-model pipeline. A completed process is not necessarily a passed run."""
import hashlib
import json
import os
import shutil
import sys
import traceback
import urllib.request
from datetime import datetime
from importlib.metadata import version
from pathlib import Path

from analyst_agent import run_analyst
from benchmark_irsim import run_benchmark
from developer_agent import run_developer, run_developer_revision
from model_client import write_json
from planner_agent import run_planner
from reviewer_agent import run_reviewer_agent
from reviewer_benchmark_agent import run_benchmark_reviewer_agent
from test_agent import run_test_agent
from verification import mutation_experiment, run_check

BASE_DIR = Path(__file__).resolve().parent
ARTIFACTS_DIR = BASE_DIR / "artifacts"
GENERATED_DIR = BASE_DIR / "generated"
TRACE_PATH = BASE_DIR / "trace.log"


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    run_dir = ARTIFACTS_DIR / "runs" / datetime.now().strftime("%Y%m%dT%H%M%S-%f")
    run_dir.mkdir(parents=True)
    previous_evidence_dir = os.environ.get("SCSE_EVIDENCE_DIR")
    os.environ["SCSE_EVIDENCE_DIR"] = str(run_dir / "model_calls")
    previous = run_dir / "previous_outputs"
    previous.mkdir()
    files = list(ARTIFACTS_DIR.glob("*.json")) + list(GENERATED_DIR.glob("*.py"))
    files += [TRACE_PATH, BASE_DIR / "test_generated_navigation_logic.py"]
    for path in files:
        if path.exists():
            destination = previous / path.relative_to(BASE_DIR)
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, destination)
    TRACE_PATH.write_text("", encoding="utf-8")

    def log(message):
        line = f"{datetime.now().isoformat(timespec='seconds')} {message}\n"
        for path in [TRACE_PATH, run_dir / "trace.log"]:
            with path.open("a", encoding="utf-8") as stream:
                stream.write(line)
        print(line.rstrip(), flush=True)

    summary = {"run_id": run_dir.name, "status": "running", "mode": "strict_live",
               "fallback_allowed": False, "run_directory": str(run_dir),
               "reviewer_source": "deterministic_rules",
               "safety_scope": "Provided simulator terminal-state proxy, not a physical-safety proof"}
    write_json(run_dir / "run_summary.json", summary)
    source_dir = run_dir / "source_snapshot"
    source_dir.mkdir()
    for path in list(BASE_DIR.glob("*.py")) + [BASE_DIR / "brief.txt", BASE_DIR / "run_visual.sh"]:
        if path.exists():
            shutil.copy2(path, source_dir / path.name)
    shutil.copytree(BASE_DIR / "irsim_worlds", source_dir / "irsim_worlds")
    summary["source_hashes"] = {str(path.relative_to(source_dir)): sha256(path)
                                for path in source_dir.rglob("*") if path.is_file()}

    def evaluate(candidate, tests, folder):
        folder.mkdir(parents=True, exist_ok=True)
        log(f"Executing generated tests against {candidate.name}")
        tests_report = run_check("tests", candidate, tests, folder / "generated_tests_report.json")
        simulation = run_check("simulation", candidate, tests, folder / "simulation_report.json")
        if "total_scenarios" not in simulation:
            raise RuntimeError(f"Candidate simulation could not execute: {simulation}")
        review = run_reviewer_agent(simulation)
        write_json(folder / "simulation_review.json", review)
        log(f"{candidate.name}: tests={tests_report['check_passed']}, "
            f"logical scenarios={simulation['passed']}/64; starting IR-SIM")
        benchmark = run_benchmark(candidate, folder)
        benchmark_review = run_benchmark_reviewer_agent(benchmark)
        write_json(folder / "irsim_benchmark_review.json", benchmark_review)
        log(f"{candidate.name}: IR-SIM goals={benchmark['goals_reached']}/{benchmark['total_worlds']}, "
            f"efficient={benchmark['efficient_worlds']}")
        passed = (tests_report["check_passed"] and simulation["check_passed"]
                  and benchmark["total_worlds"] >= 4 and not benchmark_review["needs_revision"])
        return {"tests": tests_report, "simulation": simulation, "review": review,
                "benchmark": benchmark, "benchmark_review": benchmark_review, "passed": passed}

    try:
        log(f"Run started: {run_dir.name}; strict live Qwen, no cached fallback")
        with urllib.request.urlopen("http://127.0.0.1:11434/api/tags", timeout=5) as response:
            write_json(run_dir / "model_inventory.json", json.load(response))
        summary["environment"] = {"python": sys.version, "executable": sys.executable,
                                  "ir_sim": version("ir-sim"), "numpy": version("numpy")}
        brief = (BASE_DIR / "brief.txt").read_text(encoding="utf-8")
        log("Calling Analyst Agent (live Qwen)")
        requirements = run_analyst(brief)
        write_json(run_dir / "requirements.json", requirements)
        log("Analyst requirements validated; calling Planner Agent (live Qwen)")
        plan = run_planner(requirements)
        write_json(run_dir / "plan.json", plan)
        log("Planner schema validated; calling Developer Agent (live Qwen)")
        code = run_developer(plan)
        original = run_dir / "navigation_logic.py"
        original.write_text(code + "\n", encoding="utf-8")
        log("Developer code structurally validated; calling Test Agent with brief and actual code")
        tests = run_dir / "test_generated_navigation_logic.py"
        tests.write_text(run_test_agent(requirements, plan, brief, code) + "\n", encoding="utf-8")
        initial = evaluate(original, tests, run_dir / "initial")
        summary["initial_passed"] = initial["passed"]
        notes = {
            "simulation_review": initial["review"], "benchmark_review": initial["benchmark_review"],
            "test_results": initial["tests"],
            "robustness_results": initial["simulation"]["robustness_checks"],
            "failed_scenarios": [item for item in initial["simulation"]["results"] if not item["passed"]],
            "revision_purpose": (
                "Final reviewed revision for the assignment; do not invent a benchmark failure. "
                "Additionally harden the API: if state is not a dict OR ANY of front_blocked, "
                "left_blocked, right_blocked is missing, return STOP. This is an explicit "
                "defensive extension beyond the six-boolean contract. Preserve all 64 valid "
                "states, optional goal flags, and NumPy goal booleans. Implement a short "
                "input guard if needed; no imports. Address actual reported failures."),
        }
        write_json(run_dir / "revision_request.json", notes)
        log("Calling Developer Revision Agent with actual reports and defensive-input review")
        revised = run_dir / "navigation_logic_revised.py"
        revised_code = run_developer_revision(code, notes, initial["benchmark"],
                                               requirements, plan, output_path=revised)
        final = evaluate(revised, tests, run_dir / "revised")
        mutation = mutation_experiment(revised, tests, run_dir / "mutation")
        summary.update(
            revised_passed=final["passed"],
            revised_robustness_passed=final["simulation"]["robustness_passed"],
            revision_changed_source=code.strip() != revised_code.strip(),
            initial_sha256=sha256(original), revised_sha256=sha256(revised),
            tests_sha256=sha256(tests), mutation_passed=mutation["passed"],
            initial_success_rate=initial["benchmark"]["success_rate"],
            revised_success_rate=final["benchmark"]["success_rate"],
            initial_average_steps=initial["benchmark"]["average_steps_taken"],
            revised_average_steps=final["benchmark"]["average_steps_taken"])
        if not (final["passed"] and final["simulation"]["robustness_passed"] and mutation["passed"]):
            raise RuntimeError("Final candidate failed a validation gate; inspect per-stage reports.")
        # Publish only a fully validated run. Previous root artifacts remain archived.
        GENERATED_DIR.mkdir(exist_ok=True)
        shutil.copy2(original, GENERATED_DIR / original.name)
        shutil.copy2(revised, GENERATED_DIR / revised.name)
        shutil.copy2(tests, BASE_DIR / tests.name)
        for name in ("requirements.json", "plan.json"):
            shutil.copy2(run_dir / name, ARTIFACTS_DIR / name)
        for name in ("simulation_report.json", "simulation_review.json",
                     "irsim_benchmark_report.json", "irsim_benchmark_review.json",
                     "generated_tests_report.json"):
            shutil.copy2(run_dir / "initial" / name, ARTIFACTS_DIR / name)
            shutil.copy2(run_dir / "revised" / name, ARTIFACTS_DIR / ("revised_" + name))
        shutil.copy2(run_dir / "mutation" / "mutation_report.json", ARTIFACTS_DIR / "mutation_report.json")
        last_world = initial["benchmark"]["results"][-1]["world_name"]
        raw_report = run_dir / "initial" / "world_runs" / Path(last_world).stem / "artifacts" / "irsim_report.json"
        shutil.copy2(raw_report, ARTIFACTS_DIR / "irsim_report.json")
        write_json(ARTIFACTS_DIR / "revision_review.json", notes)
        summary["status"] = "passed"
        log("Pipeline PASSED: live model stages, executed tests, original/revised benchmarks, mutation check")
        return 0
    except (Exception, KeyboardInterrupt) as exc:
        summary.update(status="failed", error=f"{type(exc).__name__}: {exc}",
                       traceback=traceback.format_exc())
        log(f"Pipeline FAILED: {exc}. No success claimed; evidence preserved.")
        return 1
    finally:
        summary["finished_at"] = datetime.now().isoformat()
        write_json(run_dir / "run_summary.json", summary)
        write_json(ARTIFACTS_DIR / "latest_run.json", summary)
        if previous_evidence_dir is None:
            os.environ.pop("SCSE_EVIDENCE_DIR", None)
        else:
            os.environ["SCSE_EVIDENCE_DIR"] = previous_evidence_dir


if __name__ == "__main__":
    raise SystemExit(main())
