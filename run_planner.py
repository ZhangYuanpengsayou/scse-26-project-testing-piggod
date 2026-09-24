import json
from pathlib import Path

from planner_agent import run_planner


def main():
    base_dir = Path(__file__).parent
    artifacts_dir = base_dir / "artifacts"
    requirements_path = artifacts_dir / "requirements.json"
    plan_path = artifacts_dir / "plan.json"

    with open(requirements_path, "r", encoding="utf-8") as file:
        requirements = json.load(file)

    plan = run_planner(requirements)

    artifacts_dir.mkdir(exist_ok=True)

    with open(plan_path, "w", encoding="utf-8") as file:
        json.dump(plan, file, indent=4)

    print(json.dumps(plan, indent=4))
    print()
    print("Saved to artifacts/plan.json")


if __name__ == "__main__":
    main()
