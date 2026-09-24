import json
from pathlib import Path

from developer_agent import run_developer


def main():
    base_dir = Path(__file__).parent
    artifacts_dir = base_dir / "artifacts"
    generated_dir = base_dir / "generated"
    plan_path = artifacts_dir / "plan.json"
    output_path = generated_dir / "navigation_logic.py"

    with open(plan_path, "r", encoding="utf-8") as file:
        plan = json.load(file)

    code_text = run_developer(plan)

    generated_dir.mkdir(exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as file:
        file.write(code_text)
        file.write("\n")

    print(code_text)
    print()
    print("Saved to generated/navigation_logic.py")


if __name__ == "__main__":
    main()
