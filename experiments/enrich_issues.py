"""Enrich selected issues with SWE-bench Lite metadata.

Adds FAIL_TO_PASS, PASS_TO_PASS, version, and environment_setup_commit
fields from the HuggingFace SWE-bench Lite dataset to our selected issues.

Usage:
    python experiments/enrich_issues.py
    python experiments/enrich_issues.py --issues data/selected_issues.json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Stub out the Unix-only 'resource' module on Windows
if sys.platform == "win32":
    import types
    import sys as _sys
    if "resource" not in _sys.modules:
        _res = types.ModuleType("resource")
        _res.getrlimit = lambda x: (0, 0)  # type: ignore[attr-defined]
        _res.setrlimit = lambda x, y: None  # type: ignore[attr-defined]
        _res.RLIMIT_NOFILE = 7  # type: ignore[attr-defined]
        _sys.modules["resource"] = _res

from swebench.harness.run_evaluation import load_swebench_dataset


def enrich_issues(issues_path: str = "data/selected_issues.json") -> None:
    """Load SWE-bench Lite data and merge key fields into our issues file."""
    path = Path(issues_path)
    if not path.exists():
        print(f"Issues file not found: {issues_path}")
        sys.exit(1)

    issues = json.loads(path.read_text(encoding="utf-8"))
    instance_ids = [issue["instance_id"] for issue in issues]
    print(f"Loaded {len(issues)} issues from {issues_path}")

    # Load SWE-bench Lite dataset from HuggingFace
    print("Loading SWE-bench Lite dataset from HuggingFace...")
    dataset = load_swebench_dataset(
        "princeton-nlp/SWE-bench_Lite",
        split="test",
        instance_ids=instance_ids,
    )

    # Index dataset by instance_id
    dataset_map = {item["instance_id"]: item for item in dataset}
    print(f"Found {len(dataset_map)} matching instances in SWE-bench Lite")

    # Enrich each issue
    enriched_count = 0
    missing = []
    for issue in issues:
        iid = issue["instance_id"]
        if iid in dataset_map:
            swe_item = dataset_map[iid]
            issue["FAIL_TO_PASS"] = swe_item.get("FAIL_TO_PASS", "")
            issue["PASS_TO_PASS"] = swe_item.get("PASS_TO_PASS", "")
            issue["version"] = swe_item.get("version", "")
            issue["environment_setup_commit"] = swe_item.get("environment_setup_commit", "")
            issue["patch"] = swe_item.get("patch", "")
            enriched_count += 1
        else:
            missing.append(iid)

    if missing:
        print(f"WARNING: {len(missing)} issues not found in SWE-bench Lite:")
        for m in missing:
            print(f"  - {m}")

    # Save back
    path.write_text(json.dumps(issues, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Enriched {enriched_count}/{len(issues)} issues. Saved to {issues_path}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Enrich issues with SWE-bench Lite data")
    parser.add_argument("--issues", default="data/selected_issues.json", help="Path to issues JSON")
    args = parser.parse_args()
    enrich_issues(args.issues)
