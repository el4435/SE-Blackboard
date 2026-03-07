"""Run 10 validation issues x 3 configs to test pipeline fixes."""

import json
import os
import subprocess
import sys
import time

ISSUES = [
    "django__django-11179",
    "sphinx-doc__sphinx-10451",
    "sympy__sympy-18057",
    "astropy__astropy-14182",
    "django__django-11564",
    "sympy__sympy-14024",
    "django__django-12700",
    "django__django-15347",
    "django__django-13028",
    "django__django-13230",
]

CONFIGS = ["message_passing", "blackboard", "hybrid"]

results = {}
start = time.time()
total = len(ISSUES) * len(CONFIGS)
run_num = 0

for issue in ISSUES:
    for config in CONFIGS:
        run_num += 1
        label = f"{issue} ({config})"
        print(f"\n[{run_num}/{total}] Running {label}...")
        t0 = time.time()
        cmd = [
            sys.executable,
            "experiments/run_experiment.py",
            "--topology", "sequential",
            "--communication", config,
            "--issue-id", issue,
        ]
        r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
        elapsed = time.time() - t0

        result_dir = f"data/results/sequential_{config}"
        result_file = os.path.join(result_dir, f"{issue}.json")
        resolved = False
        if os.path.exists(result_file):
            with open(result_file, encoding="utf-8") as f:
                data = json.load(f)
            resolved = data.get("resolved", False)
            traces = data.get("agent_traces", [])
            roles = [t.get("agent_role") for t in traces]
            patch = (data.get("final_patch") or "").strip()
            tester_ran = "Tester" in roles
            print(f"  -> resolved={resolved}, patch_empty={not patch}, tester_ran={tester_ran}, {elapsed:.0f}s")
            print(f"     roles: {roles}")
        else:
            print(f"  -> NO RESULT FILE, {elapsed:.0f}s")
            if r.returncode != 0:
                print(f"  stderr: {r.stderr[-500:]}")
        results[f"{config}_{issue}"] = resolved

elapsed_total = time.time() - start
print(f"\n{'='*70}")
print(f"Validation complete in {elapsed_total / 60:.1f} min")
print(f"{'='*70}")
print()

# Summary per config
for config in CONFIGS:
    resolved_count = sum(1 for i in ISSUES if results.get(f"{config}_{i}", False))
    tester_ran_count = 0
    empty_patch_count = 0
    for i in ISSUES:
        result_file = f"data/results/sequential_{config}/{i}.json"
        if os.path.exists(result_file):
            with open(result_file, encoding="utf-8") as f:
                data = json.load(f)
            traces = data.get("agent_traces", [])
            if "Tester" in [t.get("agent_role") for t in traces]:
                tester_ran_count += 1
            if not (data.get("final_patch") or "").strip():
                empty_patch_count += 1
    print(f"  {config}: {resolved_count}/{len(ISSUES)} resolved, "
          f"tester_ran={tester_ran_count}/{len(ISSUES)}, "
          f"empty_patch={empty_patch_count}/{len(ISSUES)}")

# Save
with open("data/results/_validation_results.json", "w", encoding="utf-8") as f:
    json.dump(results, f, indent=2)
print("\nSaved to data/results/_validation_results.json")
