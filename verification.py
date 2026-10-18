"""Candidate-specific checks and an isolated deliberately broken-code experiment."""
import ast
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from model_client import write_json

BASE_DIR = Path(__file__).resolve().parent


def run_check(mode, candidate, tests, report_path):
    report_path = Path(report_path).resolve()
    report_path.parent.mkdir(parents=True, exist_ok=True)
    if report_path.exists():
        report_path.unlink()
    command = [sys.executable, "-X", "utf8", str(BASE_DIR / "candidate_worker.py"), mode,
               str(Path(candidate).resolve()), str(Path(tests).resolve()),
               "--report", str(report_path)]
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    try:
        result = subprocess.run(command, cwd=BASE_DIR, capture_output=True,
                                text=True, encoding="utf-8", timeout=30, env=env)
        report = json.loads(report_path.read_text(encoding="utf-8"))
        passed = report.get("passed_check", report.get("passed", False))
        report.update(return_code=result.returncode, stdout=result.stdout,
                      stderr=result.stderr, check_passed=result.returncode == 0 and bool(passed))
    except Exception as exc:
        report = {"check_passed": False, "error": f"{type(exc).__name__}: {exc}"}
    write_json(report_path, report)
    return report


def mutation_experiment(candidate, tests, output_dir):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    source = Path(candidate).read_text(encoding="utf-8")
    digest = hashlib.sha256(Path(candidate).read_bytes()).hexdigest()
    baseline = run_check("tests", candidate, tests, output_dir / "baseline.json")
    # Mutate a COPY: the real candidate is never overwritten, even on failure.
    mutant = output_dir / "mutant_all_blocked_moves.py"
    tree = ast.parse(source)
    functions = [node for node in tree.body if isinstance(node, ast.FunctionDef)
                 and node.name == "decide_next_move"]
    if len(functions) != 1:
        raise ValueError("Could not locate candidate function for mutation")
    functions[0].name = "original_decision"
    broken_source = ast.unparse(tree)
    broken_source += ('\n\ndef decide_next_move(state):\n'
        '    if all(state.get(key, False) for key in ("front_blocked", "left_blocked", "right_blocked")):\n'
        '        return "FORWARD"\n'
        '    return original_decision(state)\n')
    mutant.write_text(broken_source, encoding="utf-8")
    broken = run_check("tests", mutant, tests, output_dir / "mutant.json")
    restored = run_check("tests", candidate, tests, output_dir / "restored.json")
    killed = (not broken["check_passed"] and any(
        item.get("error_type") == "AssertionError" for item in broken.get("results", [])))
    unchanged = hashlib.sha256(Path(candidate).read_bytes()).hexdigest() == digest
    report = {"mutation": "All directions blocked incorrectly returns FORWARD",
              "candidate_sha256": digest, "baseline_passed": baseline["check_passed"],
              "mutant_killed_by_assertion": killed, "restored_passed": restored["check_passed"],
              "candidate_unchanged": unchanged,
              "passed": baseline["check_passed"] and killed and restored["check_passed"] and unchanged}
    write_json(output_dir / "mutation_report.json", report)
    return report
