import json
from pathlib import Path

from planner_agent import run_planner


def main():
    base_dir = Path(__file__).parent
    artifacts_dir = base_dir / "artifacts"
    requirements_path = artifacts_dir / "requirements.json"
    output_path = artifacts_dir / "plan.json"

    requirements = json.loads(requirements_path.read_text(encoding="utf-8"))
    plan = run_planner(requirements)

    output_path.write_text(
        json.dumps(plan, indent=4),
        encoding="utf-8",
    )

    print(json.dumps(plan, indent=4))
    print()
    print("Saved to artifacts/plan.json")


if __name__ == "__main__":
    main()
