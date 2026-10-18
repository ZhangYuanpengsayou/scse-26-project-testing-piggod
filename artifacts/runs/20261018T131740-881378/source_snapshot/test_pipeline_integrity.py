"""Offline regression tests for orchestration, not substitutes for the live run."""
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import analyst_agent
import developer_agent
import model_client
import planner_agent
import test_agent
from benchmark_irsim import classify_result, run_irsim_benchmark_for_world
from candidate_worker import run_tests
from verification import mutation_experiment, run_check

BASE_DIR = Path(__file__).resolve().parent


class PipelineIntegrityTests(unittest.TestCase):
    def test_unsafe_requirements_rejected(self):
        data = {"goal": "navigate", "allowed_actions": ["FORWARD", "LEFT", "RIGHT", "STOP"],
                "safe_stop": True, "avoid_obstacles": True}
        self.assertTrue(analyst_agent.validate_requirements(data))
        for change in [{"goal": ""}, {"goal": "navigation objective"},
                       {"safe_stop": False}, {"avoid_obstacles": False}]:
            self.assertFalse(analyst_agent.validate_requirements(dict(data, **change)))

    def test_connection_error_is_not_hidden(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.dict(os.environ, {"SCSE_EVIDENCE_DIR": directory}):
                with patch("model_client.urllib.request.urlopen", side_effect=ConnectionRefusedError("offline")):
                    with self.assertRaises(RuntimeError):
                        model_client.chat("test", "system", "user")
            evidence = json.loads(next(Path(directory).glob("*.json")).read_text())
            self.assertEqual(evidence["status"], "error")
            self.assertIn("offline", evidence["error"])

    def test_developer_does_not_fallback(self):
        with patch("developer_agent.ask_qwen", side_effect=RuntimeError("offline")):
            with self.assertRaises(RuntimeError):
                developer_agent.run_developer({})
        with patch("developer_agent.ask_qwen", return_value="not python"):
            with self.assertRaises(ValueError):
                developer_agent.run_developer({})

    def test_revision_does_not_fallback(self):
        with patch("developer_agent.ask_qwen", side_effect=RuntimeError("offline")):
            with self.assertRaises(RuntimeError):
                developer_agent.run_developer_revision("", {}, {}, {}, {})

    def test_test_agent_requires_actual_inputs(self):
        with self.assertRaises(ValueError):
            test_agent.run_test_agent({}, {})
        with patch("test_agent.ask_qwen", side_effect=RuntimeError("offline")):
            with self.assertRaises(RuntimeError):
                test_agent.run_test_agent({}, {}, "brief", "code")

    def test_test_agent_prompt_contains_code_and_brief(self):
        with patch("test_agent.ask_qwen", return_value="invalid") as call:
            with self.assertRaises(ValueError):
                test_agent.run_test_agent({}, {}, "unique brief", "unique code")
        self.assertIn("unique brief", call.call_args.args[1])
        self.assertIn("unique code", call.call_args.args[1])

    def test_wrong_signature_rejected(self):
        self.assertFalse(developer_agent.validate_navigation_code(
            'def decide_next_move():\n    return "STOP" # FORWARD LEFT RIGHT'))

    def test_planner_cannot_omit_fallback_decisions(self):
        plan = {"strategy": "first match wins", "stop_condition": "all blocked",
                "decisions": [{"condition": "condition", "action": action, "reason": "reason"}
                              for action in ["FORWARD", "LEFT", "RIGHT", "STOP"]]}
        self.assertFalse(planner_agent.validate_plan(plan))
        plan["decisions"] = [{"condition": "condition", "action": action, "reason": "reason"}
                             for action in ["FORWARD", "LEFT", "RIGHT", "FORWARD", "LEFT", "RIGHT", "STOP"]]
        self.assertTrue(planner_agent.validate_plan(plan))

    def test_no_tests_is_not_a_pass(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            candidate = path / "candidate.py"
            candidate.write_text('def decide_next_move(state):\n    return "STOP"\n')
            tests = path / "tests.py"
            tests.write_text('print("All tests passed")\n')
            report = run_check("tests", candidate, tests, path / "report.json")
            self.assertFalse(report["check_passed"])
            self.assertIn("No test functions", report["error"])

    def test_explicit_candidate_and_assertion_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            candidate = path / "revised.py"
            candidate.write_text('def decide_next_move(state):\n    return "STOP"\n')
            tests = path / "tests.py"
            tests.write_text('from generated.navigation_logic import decide_next_move\n'
                'def test_wrong():\n    assert decide_next_move({}) == "FORWARD"\n')
            report = run_check("tests", candidate, tests, path / "report.json")
            self.assertFalse(report["check_passed"])
            self.assertEqual(report["results"][0]["error_type"], "AssertionError")

    def test_all_64_states_required(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            candidate = path / "candidate.py"
            candidate.write_text('def decide_next_move(state):\n    return "STOP"\n')
            tests = path / "tests.py"
            tests.write_text('from generated.navigation_logic import decide_next_move\n'
                'def test_empty():\n    assert decide_next_move({}) == "STOP"\n')
            self.assertFalse(run_tests(candidate, tests)["passed"])

    def test_nonzero_simulator_cannot_pass(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch("benchmark_irsim.subprocess.run") as run:
                run.return_value.returncode = 7
                run.return_value.stdout = ""
                run.return_value.stderr = "failure"
                report = run_irsim_benchmark_for_world(BASE_DIR / "irsim_worlds/world_easy.yaml",
                                                       output_dir=Path(directory))
            self.assertFalse(report["reached_goal"])
            self.assertEqual(report["efficiency_status"], "failed")

    def test_efficiency_rejects_error(self):
        self.assertEqual(classify_result({"reached_goal": True, "steps_taken": 10,
                                         "return_code": 1}), "failed")

    def test_mutation_is_detected_without_editing_candidate(self):
        with tempfile.TemporaryDirectory() as directory:
            report = mutation_experiment(BASE_DIR / "generated/navigation_logic.py",
                BASE_DIR / "test_generated_navigation_logic.py", Path(directory))
            self.assertTrue(report["passed"], report)


if __name__ == "__main__":
    unittest.main()
