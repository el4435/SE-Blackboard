"""Run few-shot validation: 10 issues x 3 configs = 30 experiments.

Usage:
    python experiments/run_fewshot_validation.py
"""
import asyncio
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Set result suffix BEFORE importing run_experiment
import experiments.run_experiment as runner
runner._RESULT_SUFFIX = "fewshot"

ISSUES = [
    # Success group (v3 BB resolved these)
    "django__django-11179",
    "django__django-12700",
    "django__django-12915",
    "django__django-13028",
    # Apply error group (v3 non-empty but failed)
    "django__django-11564",
    "django__django-11620",
    "django__django-12908",
    # Empty patch group (v3 empty patches)
    "astropy__astropy-14182",
    "astropy__astropy-14995",
    "pylint-dev__pylint-5859",
]

CONFIGS = [
    ("sequential", "message_passing"),
    ("sequential", "blackboard"),
    ("sequential", "hybrid"),
]


async def main():
    issues_path = "data/selected_issues.json"
    all_issues = runner.load_issues(issues_path)
    selected = [i for i in all_issues if i["instance_id"] in ISSUES]
    print(f"Selected {len(selected)} issues for validation")

    for topology, communication in CONFIGS:
        print(f"\n{'='*60}")
        print(f"  Running: {topology} / {communication}")
        print(f"{'='*60}")
        results = await runner.run_experiment_config(
            topology, communication, selected, use_mock=False, issues_path=issues_path
        )
        resolved = sum(1 for r in results if r.resolved)
        print(f"\n  Result: {resolved}/{len(results)} resolved")

    # Summary
    print(f"\n{'='*60}")
    print("  FEW-SHOT VALIDATION SUMMARY")
    print(f"{'='*60}")

    for topology, communication in CONFIGS:
        name = f"{topology}_{communication}"
        d = runner.result_dir(topology, communication)
        resolved = 0
        total = 0
        for p in sorted(d.glob("*.json")):
            if p.name.startswith("_"):
                continue
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
                total += 1
                if data.get("resolved"):
                    resolved += 1
            except (json.JSONDecodeError, KeyError):
                pass
        print(f"  {name}: {resolved}/{total}")


if __name__ == "__main__":
    asyncio.run(main())
