import json
from pathlib import Path

from developer_agent import run_developer


def main():
    base_dir = Path(__file__).parent
    artifacts_dir = base_dir / "artifacts"
    generated_dir = base_dir / "generated"
    plan_path = artifacts_dir / "plan.json"
    output_path = generated_dir / "navigation_logic.py"

    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    code_text = run_developer(plan)

    generated_dir.mkdir(exist_ok=True)
    output_path.write_text(code_text + "\n", encoding="utf-8")

    print(code_text)
    print()
    print("Saved to generated/navigation_logic.py")


if __name__ == "__main__":
    main()
