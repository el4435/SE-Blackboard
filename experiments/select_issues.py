"""Select a stratified subset of 50 issues from SWE-bench Lite.

Selection strategy:
- Total: 50 issues (20 easy + 20 medium + 10 hard)
- Difficulty based on gold patch stats (file count + changed line count)
- Stratified across repositories for diversity
- Excludes known broken instances and repos with complex env setup

Output: data/selected_issues.json

Usage:
    python experiments/select_issues.py
    python experiments/select_issues.py --num 50 --seed 42
"""

from __future__ import annotations

import argparse
import json
import random
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from rich.console import Console
from rich.table import Table

console = Console()
# Exclusion lists

# Repos known to need complex env setup
EXCLUDED_REPOS = {
    "matplotlib/matplotlib",   # heavy native deps, SSL issues
    "scikit-learn/scikit-learn",  # Cython build required
}

# Known broken / flaky instances from SWE-bench community
EXCLUDED_INSTANCES = {
    "matplotlib__matplotlib-23987",
    "psf__requests-1963",
    "psf__requests-2317",
    "psf__requests-2674",
    "sympy__sympy-13177",
    "sympy__sympy-13146",
    "sympy__sympy-11870",      # extremely slow (16+ min)
    "matplotlib__matplotlib-20488",  # SSL/HTTPS failures
}

# Difficulty thresholds calibrated for SWE-bench Lite distribution:
#   Easy:   <= 6 changed lines, 1 file    (~152 instances available)
#   Medium: 7-18 changed lines, 1-2 files (~108 instances available)
#   Hard:   > 18 changed lines or 3+ files (~40 instances available)
EASY_MAX_LINES = 6
MEDIUM_MAX_LINES = 18
# Patch parsing

def parse_patch_stats(patch: str) -> tuple[int, int]:
    """Parse a unified diff to count files touched and lines changed.

    Returns:
        (num_files, num_changed_lines) where changed = added + removed.
    """
    files: set[str] = set()
    added = 0
    removed = 0
    for line in patch.split("\n"):
        if line.startswith("diff --git"):
            m = re.search(r"b/(.+)", line)
            if m:
                files.add(m.group(1))
        elif line.startswith("+") and not line.startswith("+++"):
            added += 1
        elif line.startswith("-") and not line.startswith("---"):
            removed += 1
    return len(files), added + removed


def classify_difficulty(num_files: int, num_lines: int) -> str:
    """Classify an instance's difficulty based on gold patch stats."""
    if num_files >= 3 or num_lines > MEDIUM_MAX_LINES:
        return "hard"
    if num_files >= 2 or num_lines > EASY_MAX_LINES:
        return "medium"
    return "easy"
# Selection

def select_issues(
    dataset: list[dict[str, Any]],
    num_easy: int = 20,
    num_medium: int = 20,
    num_hard: int = 10,
    seed: int = 42,
) -> list[dict[str, Any]]:
    """Stratified sampling: difficulty-first, then repo-proportional within each tier."""
    rng = random.Random(seed)
    total = num_easy + num_medium + num_hard

    # 1. Filter excluded repos and instances
    filtered = [
        item for item in dataset
        if item.get("repo", "") not in EXCLUDED_REPOS
        and item.get("instance_id", "") not in EXCLUDED_INSTANCES
    ]

    # 2. Parse patch stats and classify difficulty
    enriched: list[dict[str, Any]] = []
    for item in filtered:
        patch = item.get("patch", "")
        nf, nl = parse_patch_stats(patch)
        difficulty = classify_difficulty(nf, nl)
        enriched.append({
            **item,
            "_difficulty": difficulty,
            "_gold_patch_files": nf,
            "_gold_patch_lines": nl,
        })

    # 3. Group by difficulty
    by_difficulty: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in enriched:
        by_difficulty[item["_difficulty"]].append(item)

    # 4. Sample from each difficulty tier, with repo diversity
    selected: list[dict[str, Any]] = []
    targets = {"easy": num_easy, "medium": num_medium, "hard": num_hard}

    for difficulty, target in targets.items():
        pool = by_difficulty.get(difficulty, [])
        sampled = _repo_stratified_sample(pool, target, rng)
        selected.extend(sampled)

    return selected[:total]


def _repo_stratified_sample(
    pool: list[dict[str, Any]],
    target: int,
    rng: random.Random,
) -> list[dict[str, Any]]:
    """Sample *target* items from *pool* with proportional repo representation."""
    if len(pool) <= target:
        return pool[:]

    # Group by repo
    by_repo: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in pool:
        by_repo[item.get("repo", "unknown")].append(item)

    repos = sorted(by_repo.keys(), key=lambda r: -len(by_repo[r]))
    total_available = len(pool)
    selected: list[dict[str, Any]] = []

    for repo in repos:
        repo_pool = by_repo[repo]
        share = max(1, round(len(repo_pool) / total_available * target))
        share = min(share, len(repo_pool), target - len(selected))
        if share <= 0:
            continue
        rng.shuffle(repo_pool)
        selected.extend(repo_pool[:share])
        if len(selected) >= target:
            break

    # Fill if under-selected
    if len(selected) < target:
        used_ids = {item["instance_id"] for item in selected}
        remaining = [item for item in pool if item["instance_id"] not in used_ids]
        rng.shuffle(remaining)
        selected.extend(remaining[: target - len(selected)])

    return selected[:target]
# Serialization

def _convert_to_serializable(item: dict[str, Any]) -> dict[str, Any]:
    """Extract the fields we need for experiment input."""
    return {
        "instance_id": item.get("instance_id", ""),
        "repo": item.get("repo", ""),
        "base_commit": item.get("base_commit", ""),
        "problem_statement": item.get("problem_statement", ""),
        "hints_text": item.get("hints_text", ""),
        "test_patch": item.get("test_patch", ""),
        "difficulty": item.get("_difficulty", "unknown"),
        "gold_patch_files": item.get("_gold_patch_files", 0),
        "gold_patch_lines": item.get("_gold_patch_lines", 0),
    }
# Statistics

def print_statistics(items: list[dict[str, Any]]) -> None:
    """Print a rich summary of the selected issues."""
    # Difficulty distribution
    diff_table = Table(title="Difficulty Distribution")
    diff_table.add_column("Difficulty", style="cyan")
    diff_table.add_column("Count", justify="right")
    diff_table.add_column("Avg Files", justify="right")
    diff_table.add_column("Avg Lines", justify="right")

    for diff in ("easy", "medium", "hard"):
        subset = [i for i in items if i["difficulty"] == diff]
        if not subset:
            diff_table.add_row(diff, "0", "-", "-")
            continue
        avg_f = sum(i["gold_patch_files"] for i in subset) / len(subset)
        avg_l = sum(i["gold_patch_lines"] for i in subset) / len(subset)
        diff_table.add_row(diff, str(len(subset)), f"{avg_f:.1f}", f"{avg_l:.1f}")

    console.print(diff_table)
    console.print()

    # Repo distribution
    repo_table = Table(title="Repository Distribution")
    repo_table.add_column("Repository", style="cyan", min_width=25)
    repo_table.add_column("Count", justify="right")
    repo_table.add_column("Easy", justify="right")
    repo_table.add_column("Medium", justify="right")
    repo_table.add_column("Hard", justify="right")

    repos: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for item in items:
        repos[item["repo"]][item["difficulty"]] += 1
        repos[item["repo"]]["total"] += 1

    for repo in sorted(repos, key=lambda r: -repos[r]["total"]):
        r = repos[repo]
        repo_table.add_row(
            repo,
            str(r["total"]),
            str(r.get("easy", 0)),
            str(r.get("medium", 0)),
            str(r.get("hard", 0)),
        )

    console.print(repo_table)
# Main

def main() -> None:
    parser = argparse.ArgumentParser(description="Select issues from SWE-bench Lite")
    parser.add_argument("--num-easy", type=int, default=20)
    parser.add_argument("--num-medium", type=int, default=20)
    parser.add_argument("--num-hard", type=int, default=10)
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    parser.add_argument("--output", type=str, default="data/selected_issues.json")
    args = parser.parse_args()

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        from datasets import load_dataset

        console.print("[cyan]Loading SWE-bench Lite dataset...[/cyan]")
        ds = load_dataset("princeton-nlp/SWE-bench_Lite", split="test")
        all_items = [dict(item) for item in ds]
        console.print(f"Loaded {len(all_items)} instances from SWE-bench Lite.")
    except ImportError:
        console.print("[yellow]'datasets' library not installed. Using fallback dataset.[/yellow]")
        console.print("Install with: pip install datasets")
        all_items = _fallback_dataset()
    except Exception as exc:
        console.print(f"[yellow]Could not load SWE-bench Lite ({exc}). Using fallback dataset.[/yellow]")
        all_items = _fallback_dataset()

    # Show pool distribution before selection
    console.print()
    console.rule("[bold]Pool Analysis (before selection)[/bold]")
    pool_easy = pool_med = pool_hard = 0
    for item in all_items:
        patch = item.get("patch", "")
        nf, nl = parse_patch_stats(patch) if patch else (0, 0)
        diff = classify_difficulty(nf, nl)
        if diff == "easy":
            pool_easy += 1
        elif diff == "medium":
            pool_med += 1
        else:
            pool_hard += 1
    console.print(f"  Available: easy={pool_easy}, medium={pool_med}, hard={pool_hard}")
    console.print(f"  Excluded repos: {EXCLUDED_REPOS}")
    console.print(f"  Excluded instances: {len(EXCLUDED_INSTANCES)}")
    console.print()

    selected = select_issues(
        all_items,
        num_easy=args.num_easy,
        num_medium=args.num_medium,
        num_hard=args.num_hard,
        seed=args.seed,
    )
    serializable = [_convert_to_serializable(item) for item in selected]

    output_path.write_text(
        json.dumps(serializable, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    console.rule(f"[bold green]Selected {len(serializable)} issues -> {output_path}[/bold green]")
    console.print()
    print_statistics(serializable)


def _fallback_dataset() -> list[dict[str, Any]]:
    """Minimal set of well-known SWE-bench Lite issues for offline testing."""
    return [
        {
            "instance_id": "django__django-11099",
            "problem_statement": "UsernameValidator allows trailing newline in usernames.",
            "repo": "django/django",
            "base_commit": "d5276b9e65fdd0473e8fa50fad1b6fdb5e9891be",
            "patch": "diff --git a/django/contrib/auth/validators.py b/django/contrib/auth/validators.py\n--- a/django/contrib/auth/validators.py\n+++ b/django/contrib/auth/validators.py\n@@ -7,7 +7,7 @@ class ASCIIUsernameValidator(validators.RegexValidator):\n-    regex = r'^[\\w.@+-]+$'\n+    regex = r'\\A[\\w.@+-]+\\Z'\n",
        },
        {
            "instance_id": "django__django-11179",
            "problem_statement": "delete() on instances of models without any dependencies doesn't clear PKs.",
            "repo": "django/django",
            "base_commit": "3193e0a38d68ef5ec5fb24f7aa55bde50783d5c0",
            "patch": "diff --git a/django/db/models/deletion.py b/django/db/models/deletion.py\n--- a/django/db/models/deletion.py\n+++ b/django/db/models/deletion.py\n@@ -1 +1 @@\n-old\n+new\n",
        },
        {
            "instance_id": "django__django-11283",
            "problem_statement": "Migration auth.0011 is too slow.",
            "repo": "django/django",
            "base_commit": "8c0886b068ba4e224dd78104a93cbcb78f79c6e5",
            "patch": "diff --git a/django/contrib/auth/migrations/0011_update_proxy_permissions.py b/django/contrib/auth/migrations/0011_update_proxy_permissions.py\n--- a/f.py\n+++ b/f.py\n@@ -1,5 +1,10 @@\n-old1\n-old2\n-old3\n+new1\n+new2\n+new3\n+new4\n+new5\n+new6\n+new7\n+new8\n+new9\n+new10\n+new11\n+new12\n+new13\n+new14\n+new15\n+new16\n+new17\n+new18\n+new19\n+new20\n+new21\n+new22\n+new23\n+new24\n+new25\n+new26\n+new27\n+new28\n+new29\n+new30\n",
        },
        {
            "instance_id": "sympy__sympy-18087",
            "problem_statement": "Simplify of expression including factorial can be very slow.",
            "repo": "sympy/sympy",
            "base_commit": "b17ef6effe26923a01fa1d5e1e3b37a1f8a4347a",
            "patch": "diff --git a/sympy/simplify/simplify.py b/sympy/simplify/simplify.py\n--- a/f.py\n+++ b/f.py\n@@ -1,3 +1,5 @@\n-old\n+new1\n+new2\n+new3\n",
        },
        {
            "instance_id": "astropy__astropy-12907",
            "problem_statement": "Modeling's `separability_matrix` does not compute separability correctly for nested CompoundModels.",
            "repo": "astropy/astropy",
            "base_commit": "d16bfe05a744909de4b27f5875fe0d4c35571c91",
            "patch": "diff --git a/astropy/modeling/separable.py b/astropy/modeling/separable.py\n--- a/f.py\n+++ b/f.py\n@@ -1,2 +1,4 @@\n-old\n+new1\n+new2\n",
        },
        {
            "instance_id": "flask__flask-4045",
            "problem_statement": "Raise error when blueprint name contains a dot.",
            "repo": "pallets/flask",
            "base_commit": "5e5e18e53f0d7e0e78b7105c0cd00bca65428de4",
            "patch": "diff --git a/src/flask/blueprints.py b/src/flask/blueprints.py\n--- a/f.py\n+++ b/f.py\n@@ -1 +1,2 @@\n-old\n+new\n+new2\n",
        },
        {
            "instance_id": "requests__requests-3362",
            "problem_statement": "Allow lists in the dict values of the 'hooks' argument.",
            "repo": "psf/requests",
            "base_commit": "36453b95b1380fdd5add76fbe8d1d426fa436abd",
            "patch": "diff --git a/requests/models.py b/requests/models.py\n--- a/f.py\n+++ b/f.py\n@@ -1 +1 @@\n-old\n+new\n",
        },
        {
            "instance_id": "pytest__pytest-5221",
            "problem_statement": "Display the return value of a test function when running tests with -v.",
            "repo": "pytest-dev/pytest",
            "base_commit": "9fb5b2b1eb270e6cb04c485a270c4c5f7a5e67a0",
            "patch": "diff --git a/src/_pytest/terminal.py b/src/_pytest/terminal.py\n--- a/f.py\n+++ b/f.py\n@@ -1,4 +1,6 @@\n-old1\n-old2\n+new1\n+new2\n+new3\n+new4\n",
        },
        {
            "instance_id": "sphinx__sphinx-8273",
            "problem_statement": "Generate man page section directories.",
            "repo": "sphinx-doc/sphinx",
            "base_commit": "271a8a7b3ee9d30cd05d7b2045857a735ae75b64",
            "patch": "diff --git a/sphinx/builders/manpage.py b/sphinx/builders/manpage.py\n--- a/f.py\n+++ b/f.py\n@@ -1,3 +1,8 @@\n-old1\n-old2\n+new1\n+new2\n+new3\n+new4\n+new5\n+new6\n+new7\n+new8\n+new9\n",
        },
        {
            "instance_id": "xarray__xarray-3364",
            "problem_statement": "Ignore missing variables when concatenating datasets.",
            "repo": "pydata/xarray",
            "base_commit": "26f05ffaa3dbd077e2ac46b0e289a1aab07d2b8c",
            "patch": "diff --git a/xarray/core/concat.py b/xarray/core/concat.py\n--- a/f.py\n+++ b/f.py\n@@ -1,2 +1,5 @@\n-old\n+new1\n+new2\n+new3\n+new4\n",
        },
    ]


if __name__ == "__main__":
    main()
