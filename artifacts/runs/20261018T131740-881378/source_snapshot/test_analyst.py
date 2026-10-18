import json
from pathlib import Path

from analyst_agent import run_analyst


def main():
    base_dir = Path(__file__).parent
    brief_path = base_dir / "brief.txt"
    artifacts_dir = base_dir / "artifacts"
    output_path = artifacts_dir / "requirements.json"

    brief_text = brief_path.read_text(encoding="utf-8")
    requirements = run_analyst(brief_text)

    artifacts_dir.mkdir(exist_ok=True)
    output_path.write_text(
        json.dumps(requirements, indent=4),
        encoding="utf-8",
    )

    print(json.dumps(requirements, indent=4))
    print()
    print("Saved to artifacts/requirements.json")


if __name__ == "__main__":
    main()
