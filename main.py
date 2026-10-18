"""Strict live-model pipeline. A completed process is not necessarily a passed run."""
import argparse
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

from analyst_agent import run_analyst, validate_requirements
from benchmark_irsim import run_benchmark
from developer_agent import run_developer, run_developer_revision, validate_navigation_code
from model_client import write_json
from planner_agent import run_planner, validate_plan
from reviewer_agent import run_reviewer_agent
from reviewer_benchmark_agent import run_benchmark_reviewer_agent
from test_agent import run_test_agent, validate_test_code
from verification import mutation_experiment, run_check

BASE_DIR = Path(__file__).resolve().parent
ARTIFACTS_DIR = BASE_DIR / "artifacts"
GENERATED_DIR = BASE_DIR / "generated"
TRACE_PATH = BASE_DIR / "trace.log"


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_review_inputs(source_run):
    source_run = Path(source_run).resolve()
    if not source_run.is_relative_to((ARTIFACTS_DIR / "runs").resolve()):
        raise ValueError("Review source must be an archived run in this repository.")
    manifest = json.loads((source_run / "run_summary.json").read_text(encoding="utf-8"))
    if manifest.get("status") != "passed":
        raise ValueError("Explicit review continuation requires a previously passed run.")
    paths = {name: source_run / name for name in (
        "requirements.json", "plan.json", "navigation_logic.py",
        "navigation_logic_revised.py", "test_generated_navigation_logic.py")}
    for name, key in [("navigation_logic.py", "initial_sha256"),
                      ("navigation_logic_revised.py", "revised_sha256"),
                      ("test_generated_navigation_logic.py", "tests_sha256")]:
        if sha256(paths[name]) != manifest[key]:
            raise ValueError(f"Archived artifact changed: {name}")
    snapshot = source_run / "source_snapshot"
    if sha256(BASE_DIR / "brief.txt") != sha256(snapshot / "brief.txt"):
        raise ValueError("Brief changed; run the full live workflow instead.")
    old_worlds = {p.name: sha256(p) for p in (snapshot / "irsim_worlds").glob("*.yaml")}
    new_worlds = {p.name: sha256(p) for p in (BASE_DIR / "irsim_worlds").glob("*.yaml")}
    if old_worlds != new_worlds:
        raise ValueError("Worlds changed; run the full live workflow instead.")
    requirements = json.loads(paths["requirements.json"].read_text(encoding="utf-8"))
    plan = json.loads(paths["plan.json"].read_text(encoding="utf-8"))
    code = paths["navigation_logic.py"].read_text(encoding="utf-8").strip()
    tests = paths["test_generated_navigation_logic.py"].read_text(encoding="utf-8").strip()
    previous_revision = paths["navigation_logic_revised.py"].read_text(encoding="utf-8").strip()
    if not (validate_requirements(requirements) and validate_plan(plan)
            and validate_navigation_code(code) and validate_navigation_code(previous_revision)
            and validate_test_code(tests)):
        raise ValueError("Archived inputs do not satisfy the current structural contract.")
    if manifest.get("mode") == "strict_live":
        calls = [json.loads(p.read_text(encoding="utf-8")) for p in sorted((source_run / "model_calls").glob("*.json"))]
        for stage, artifact in [("analyst", requirements), ("planner", plan)]:
            received = [item for item in calls if item["stage"] == stage and item["status"] == "received"]
            if not received or json.loads(received[-1]["response"]["message"]["content"]) != artifact:
                raise ValueError(f"Archived {stage} output does not match its live model evidence.")
    elif manifest.get("reused_artifact_sha256"):
        for name in ("requirements.json", "plan.json"):
            if sha256(paths[name]) != manifest["reused_artifact_sha256"][name]:
                raise ValueError(f"Archived {name} changed since explicit reuse.")
    return requirements, plan, code, tests, previous_revision, {name: sha256(path) for name, path in paths.items()}


def main(review_run=None):
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

    summary = {"run_id": run_dir.name, "status": "running",
               "mode": "review_continuation" if review_run else "strict_live",
               "fallback_allowed": False, "run_directory": str(run_dir),
               "reviewer_source": "deterministic_rules",
               "safety_scope": "Provided simulator terminal-state proxy, not a physical-safety proof"}
    write_json(run_dir / "run_summary.json", summary)
    write_json(ARTIFACTS_DIR / "latest_run.json", summary)
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
        log(f"Run started: {run_dir.name}; mode={summary['mode']}; no automatic fallback")
        with urllib.request.urlopen("http://127.0.0.1:11434/api/tags", timeout=5) as response:
            write_json(run_dir / "model_inventory.json", json.load(response))
        summary["environment"] = {"python": sys.version, "executable": sys.executable,
                                  "ir_sim": version("ir-sim"), "numpy": version("numpy")}
        brief = (BASE_DIR / "brief.txt").read_text(encoding="utf-8")
        original = run_dir / "navigation_logic.py"
        tests = run_dir / "test_generated_navigation_logic.py"
        revision_base = None
        if review_run:
            requirements, plan, code, test_code, revision_base, hashes = load_review_inputs(review_run)
            summary.update(source_run=str(Path(review_run).resolve()), reused_artifact_sha256=hashes,
                           reused_stages=["analyst", "planner", "developer", "test_agent"])
            log(f"Explicit review continuation from {Path(review_run).name}; reused validated artifacts, not new calls for those four stages")
        else:
            log("Calling Analyst Agent (live Qwen)")
            requirements = run_analyst(brief)
            log("Analyst requirements validated; calling Planner Agent (live Qwen)")
            plan = run_planner(requirements)
            log("Planner schema validated; calling Developer Agent (live Qwen)")
            code = run_developer(plan)
            log("Developer code structurally validated; calling Test Agent with brief and actual code")
            test_code = run_test_agent(requirements, plan, brief, code)
        write_json(run_dir / "requirements.json", requirements)
        write_json(run_dir / "plan.json", plan)
        original.write_text(code + "\n", encoding="utf-8")
        tests.write_text(test_code + "\n", encoding="utf-8")
        preflight = run_check("simulation", original, tests, run_dir / "preflight_simulation.json")
        for attempt in range(1, 4):
            saved_tests = run_dir / f"test_attempt_{attempt}.py"
            shutil.copy2(tests, saved_tests)
            check = run_check("tests", original, tests, run_dir / f"test_attempt_{attempt}_report.json")
            if check["check_passed"] or not preflight["check_passed"]:
                break
            if review_run:
                raise RuntimeError("Frozen tests from the review source failed; no test regeneration allowed in review continuation.")
            if attempt == 3:
                raise RuntimeError("Test Agent failed after three attempts against the independently verified candidate.")
            log(f"Test Agent attempt {attempt} failed while independent logic checks passed; requesting test repair")
            feedback = {"previous_tests": tests.read_text(encoding="utf-8"), "execution_report": check,
                        "independent_simulation": "All 64 Boolean states and 8 optional-goal states passed. Fix the tests, not the contract."}
            tests.write_text(run_test_agent(requirements, plan, brief, code, feedback) + "\n", encoding="utf-8")
        log("Generated test suite frozen for original/revised comparison")
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
                "input guard if needed; no imports. Address actual reported failures. "
                "Before ANY membership test or .get call, use: if not isinstance(state, dict): return 'STOP'. "
                "Checking only state is None does not protect integers, booleans, floats, lists or strings."),
        }
        if review_run:
            previous_path = run_dir / "previous_revision.py"
            previous_path.write_text(revision_base + "\n", encoding="utf-8")
            previous_audit = run_check("simulation", previous_path, tests, run_dir / "previous_revision_audit.json")
            notes["previous_revision_robustness_failures"] = [
                item for item in previous_audit["robustness_checks"] if not item["passed"]]
            summary["revision_base_sha256"] = sha256(previous_path)
        write_json(run_dir / "revision_request.json", notes)
        log("Calling Developer Revision Agent with actual reports and defensive-input review")
        revised = run_dir / "navigation_logic_revised.py"
        revised_code = run_developer_revision(revision_base or code, notes, initial["benchmark"],
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
    parser = argparse.ArgumentParser()
    parser.add_argument("--review-run", type=Path,
                        help="Explicitly continue review of an existing passed run; reuse its frozen inputs with provenance checks.")
    raise SystemExit(main(parser.parse_args().review_run))
