"""Build all swebench env images needed for the 50 selected issues, one at a time."""
import sys
import os
import json
import pathlib
import logging

if sys.platform == "win32":
    import types
    if "resource" not in sys.modules:
        _res = types.ModuleType("resource")
        _res.getrlimit = lambda x: (0, 0)
        _res.setrlimit = lambda x, y: None
        _res.RLIMIT_NOFILE = 7
        sys.modules["resource"] = _res
    if not os.environ.get("DOCKER_HOST"):
        os.environ["DOCKER_HOST"] = "npipe:////./pipe/dockerDesktopLinuxEngine"

# Monkey-patch Path.write_text for LF
_orig_write_text = pathlib.Path.write_text
def _write_text_lf(self_path, data, *args, **kwargs):
    kwargs.setdefault("newline", "\n")
    return _orig_write_text(self_path, data, *args, **kwargs)
pathlib.Path.write_text = _write_text_lf

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
log = logging.getLogger(__name__)


def main():
    import docker
    from swebench.harness.test_spec.test_spec import make_test_spec
    from swebench.harness.docker_build import build_env_images

    issues_path = str(Path(__file__).resolve().parent.parent / "data" / "selected_issues.json")
    with open(issues_path, "r", encoding="utf-8") as f:
        issues = json.load(f)

    # Build SWE instances for all issues
    swe_instances = []
    for issue in issues:
        swe_instances.append({
            "repo": issue["repo"],
            "instance_id": issue["instance_id"],
            "base_commit": issue["base_commit"],
            "patch": issue.get("patch", ""),
            "test_patch": issue.get("test_patch", ""),
            "problem_statement": issue.get("problem_statement", ""),
            "hints_text": issue.get("hints_text", ""),
            "created_at": issue.get("created_at", ""),
            "version": issue.get("version", ""),
            "FAIL_TO_PASS": issue.get("FAIL_TO_PASS", ""),
            "PASS_TO_PASS": issue.get("PASS_TO_PASS", ""),
            "environment_setup_commit": issue.get("environment_setup_commit", ""),
        })

    # Get unique env image keys
    test_specs = [make_test_spec(inst) for inst in swe_instances]
    env_to_instances = {}
    for ts, inst in zip(test_specs, swe_instances):
        key = ts.env_image_key
        if key not in env_to_instances:
            env_to_instances[key] = []
        env_to_instances[key].append(inst)

    # Check existing images
    client = docker.from_env()
    existing = set()
    for img in client.images.list():
        for tag in img.tags:
            if "sweb.env" in tag:
                existing.add(tag)

    needed = set(env_to_instances.keys())
    to_build = sorted(needed - existing)

    log.info(f"Total unique env images needed: {len(needed)}")
    log.info(f"Already built: {len(existing & needed)}")
    log.info(f"Need to build: {len(to_build)}")

    if not to_build:
        log.info("All env images already exist!")
        return

    # Build one at a time to avoid OOM
    for i, env_key in enumerate(to_build, 1):
        log.info(f"[{i}/{len(to_build)}] Building {env_key} ...")
        # Get one representative instance for this env image
        representative = env_to_instances[env_key][:1]
        try:
            build_env_images(
                client=client,
                dataset=representative,
                instance_image_tag="latest",
                env_image_tag="latest",
            )
            log.info(f"[{i}/{len(to_build)}] SUCCESS: {env_key}")
        except Exception as e:
            log.error(f"[{i}/{len(to_build)}] FAILED: {env_key}: {e}")
            # Continue with next image

    # Final verification
    after = set()
    for img in client.images.list():
        for tag in img.tags:
            if "sweb.env" in tag:
                after.add(tag)

    built = after - existing
    still_missing = needed - after
    log.info(f"Newly built: {len(built)}")
    if still_missing:
        log.info(f"WARNING: Still missing {len(still_missing)} images:")
        for img in sorted(still_missing):
            log.info(f"  {img}")
    else:
        log.info("All env images ready!")


if __name__ == "__main__":
    main()
