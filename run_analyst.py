import json
import os

from analyst_agent import run_analyst


def main():
    base_dir = os.path.dirname(__file__)
    brief_path = os.path.join(base_dir, "brief.txt")
    artifacts_dir = os.path.join(base_dir, "artifacts")
    output_path = os.path.join(artifacts_dir, "requirements.json")

    with open(brief_path, "r", encoding="utf-8") as file:
        brief_text = file.read()

    requirements = run_analyst(brief_text)

    os.makedirs(artifacts_dir, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as file:
        json.dump(requirements, file, indent=4)

    print(json.dumps(requirements, indent=4))
    print()
    print("Saved to artifacts/requirements.json")


if __name__ == "__main__":
    main()
