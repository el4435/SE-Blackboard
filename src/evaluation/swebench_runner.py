"""SWE-bench evaluation runner: real and mock implementations."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path
from typing import Any

from src.blackboard.schema import TestResult

logger = logging.getLogger(__name__)
# Windows compatibility: stub out Unix-only 'resource' module
if sys.platform == "win32":
    # Stub out Unix-only 'resource' module
    if "resource" not in sys.modules:
        import types as _types
        _res = _types.ModuleType("resource")
        _res.getrlimit = lambda x: (0, 0)  # type: ignore[attr-defined]
        _res.setrlimit = lambda x, y: None  # type: ignore[attr-defined]
        _res.RLIMIT_NOFILE = 7  # type: ignore[attr-defined]
        sys.modules["resource"] = _res

    # Set DOCKER_HOST for Docker Desktop so docker.from_env() works everywhere
    if not os.environ.get("DOCKER_HOST"):
        os.environ["DOCKER_HOST"] = "npipe:////./pipe/dockerDesktopLinuxEngine"


class SWEBenchRunner:
    """Real SWE-bench evaluation runner.

    Uses local git clones for code context retrieval and the swebench Docker
    harness for test evaluation.
    """

    def __init__(
        self,
        workdir: str = "data/workspaces",
        issues_path: str = "data/selected_issues.json",
    ) -> None:
        self._workdir = Path(workdir)
        self._workdir.mkdir(parents=True, exist_ok=True)
        self._repos_dir = self._workdir / "_repos"
        self._repos_dir.mkdir(parents=True, exist_ok=True)

        # Load issue data keyed by instance_id
        self._issues: dict[str, dict[str, Any]] = {}
        ipath = Path(issues_path)
        if ipath.exists():
            data = json.loads(ipath.read_text(encoding="utf-8"))
            self._issues = {item["instance_id"]: item for item in data}
            logger.info("Loaded %d issues from %s", len(self._issues), issues_path)
    # Setup: clone repo, checkout base_commit

    async def setup_instance(self, instance_id: str) -> str:
        """Clone the repo (once) and checkout the correct base_commit.

        Returns the absolute workspace path with real source code.
        """
        issue = self._issues.get(instance_id)
        if not issue:
            raise ValueError(f"Instance {instance_id} not found in issues data")

        repo = issue["repo"]  # e.g. "django/django"
        base_commit = issue["base_commit"]
        repo_key = repo.replace("/", "__")  # "django__django"
        repo_dir = self._repos_dir / repo_key

        # Clone once (bare-ish shared repo)
        if not (repo_dir / ".git").exists():
            logger.info("Cloning %s ...", repo)
            await self._run_cmd(
                ["git", "clone", f"https://github.com/{repo}.git", str(repo_dir)],
                cwd=str(self._repos_dir),
                timeout=600,
            )

        # Checkout the base_commit
        logger.info("Checking out %s @ %s", instance_id, base_commit[:10])
        await self._run_cmd(
            ["git", "checkout", "-f", base_commit],
            cwd=str(repo_dir),
        )
        # Clean any leftover changes
        await self._run_cmd(
            ["git", "clean", "-fdx"],
            cwd=str(repo_dir),
            check=False,
        )

        self.current_workspace = str(repo_dir)
        return str(repo_dir)
    # Code context retrieval

    async def get_repo_structure(self, workspace: str, max_depth: int = 3) -> str:
        """Return a tree-like representation of the repository structure."""
        lines: list[str] = []
        root = Path(workspace)
        for path in sorted(root.rglob("*")):
            rel = path.relative_to(root)
            if len(rel.parts) > max_depth:
                continue
            if any(part.startswith(".") for part in rel.parts):
                continue
            indent = "  " * (len(rel.parts) - 1)
            name = rel.name + ("/" if path.is_dir() else "")
            lines.append(f"{indent}{name}")
            if len(lines) > 500:
                lines.append("... (truncated)")
                break
        return "\n".join(lines)

    async def get_file_content(self, workspace: str, file_path: str) -> str:
        """Read and return the contents of a file in the workspace."""
        full_path = Path(workspace) / file_path
        if not full_path.is_file():
            raise FileNotFoundError(f"{file_path} not found in workspace")
        return full_path.read_text(encoding="utf-8", errors="replace")

    async def search_code(self, workspace: str, query: str) -> list[dict[str, Any]]:
        """Search for code in the workspace matching *query* using git grep."""
        try:
            result = await self._run_cmd(
                ["git", "grep", "-n", "--no-color", query, "--", "*.py"],
                cwd=workspace,
                check=False,
            )
            matches: list[dict[str, Any]] = []
            for line in result.stdout.splitlines()[:50]:
                parts = line.split(":", 2)
                if len(parts) >= 3:
                    matches.append({
                        "file": parts[0],
                        "line": int(parts[1]) if parts[1].isdigit() else 0,
                        "content": parts[2].strip(),
                    })
            return matches
        except Exception:
            return []
    # Patch application

    async def apply_patch(self, workspace: str, patch_diff: str) -> bool:
        """Apply a unified diff patch to the workspace. Return True on success.

        Legacy interface — delegates to :meth:`apply_patch_with_fallback` when
        *fallback_apply* is enabled on the instance, otherwise uses strict
        ``git apply`` only.
        """
        if getattr(self, "fallback_apply", False):
            result = await self.apply_patch_with_fallback(
                workspace, patch_diff,
            )
            return result["success"]

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".patch", delete=False, dir=workspace,
            encoding="utf-8",
        ) as f:
            f.write(patch_diff)
            patch_file = f.name

        try:
            await self._run_cmd(
                ["git", "apply", "--check", patch_file], cwd=workspace
            )
            await self._run_cmd(
                ["git", "apply", patch_file], cwd=workspace
            )
            return True
        except subprocess.CalledProcessError:
            return False
        finally:
            os.unlink(patch_file)

    async def apply_patch_with_fallback(
        self, workspace: str, patch_diff: str,
    ) -> dict[str, Any]:
        """Apply a patch with fallback strategies.

        Tries in order:
        1. ``git apply`` (strict)
        2. ``patch -p1 -F0`` (strict POSIX patch)
        3. ``patch -p1 -F3`` (fuzzy matching, up to 3 context lines)

        Returns:
            ``{"success": bool, "method": str, "stderr": str, "patch_output": str}``

            *method* is one of ``"git_apply"``, ``"patch_strict"``,
            ``"patch_fuzz3"``, or ``"failed"``.
        """
        import re as _re

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".patch", delete=False, dir=workspace,
            encoding="utf-8",
        ) as f:
            f.write(patch_diff)
            patch_file = f.name

        strategies = [
            {
                "name": "git_apply",
                "check_cmd": ["git", "apply", "--check", patch_file],
                "apply_cmd": ["git", "apply", patch_file],
                "needs_git_add": False,
            },
            {
                "name": "patch_strict",
                "check_cmd": ["patch", "-p1", "--dry-run", "-F0", "-i", patch_file],
                "apply_cmd": ["patch", "-p1", "-F0", "-i", patch_file],
                "needs_git_add": True,
            },
            {
                "name": "patch_fuzz3",
                "check_cmd": ["patch", "-p1", "--dry-run", "-F3", "-i", patch_file],
                "apply_cmd": ["patch", "-p1", "-F3", "-i", patch_file],
                "needs_git_add": True,
            },
        ]

        last_stderr = ""
        try:
            for strategy in strategies:
                try:
                    # Dry-run check
                    check_result = await self._run_cmd(
                        strategy["check_cmd"], cwd=workspace, check=False,
                    )
                    if check_result.returncode != 0:
                        last_stderr = check_result.stderr.strip()
                        logger.debug(
                            "Patch strategy %s dry-run failed: %s",
                            strategy["name"], last_stderr,
                        )
                        continue

                    # Dry run passed — actually apply
                    apply_result = await self._run_cmd(
                        strategy["apply_cmd"], cwd=workspace, check=False,
                    )
                    if apply_result.returncode != 0:
                        last_stderr = apply_result.stderr.strip()
                        logger.warning(
                            "Patch strategy %s apply failed after dry-run: %s",
                            strategy["name"], last_stderr,
                        )
                        continue

                    # Success — log patch output (offset/fuzz info)
                    patch_output = apply_result.stdout.strip()
                    if patch_output:
                        logger.info(
                            "Patch applied via %s: %s",
                            strategy["name"], patch_output,
                        )

                    # `patch` command doesn't stage changes; do git add
                    if strategy["needs_git_add"]:
                        await self._run_cmd(
                            ["git", "add", "."], cwd=workspace, check=False,
                        )

                    return {
                        "success": True,
                        "method": strategy["name"],
                        "stderr": "",
                        "patch_output": patch_output,
                    }

                except FileNotFoundError:
                    # Command not found (e.g. `patch` missing)
                    logger.warning(
                        "Command not found for strategy %s, skipping",
                        strategy["name"],
                    )
                    continue
                except Exception as exc:
                    logger.warning(
                        "Unexpected error in strategy %s: %s",
                        strategy["name"], exc,
                    )
                    last_stderr = str(exc)
                    continue

            return {
                "success": False,
                "method": "failed",
                "stderr": last_stderr,
                "patch_output": "",
            }
        finally:
            try:
                os.unlink(patch_file)
            except OSError:
                pass
    # Test execution via swebench Docker harness

    async def run_tests(self, instance_id: str, patch_diff: str) -> TestResult:
        """Run tests using the swebench Docker harness.

        1. Write a predictions file with the patch.
        2. Call swebench's run_instance() which handles Docker container
           setup, patch application, test execution, and result parsing.
        3. Parse the evaluation output into a TestResult.
        """
        issue = self._issues.get(instance_id)
        if not issue:
            return TestResult(
                patch_version=0, passed=False, fail_count=1,
                error_traces=[f"Instance {instance_id} not in issues data."],
            )

        if not patch_diff or not patch_diff.strip():
            return TestResult(
                patch_version=0, passed=False, fail_count=1,
                error_traces=["Empty patch diff provided."],
            )

        run_id = f"run_{uuid.uuid4().hex[:8]}"

        try:
            result = await asyncio.get_event_loop().run_in_executor(
                None, self._run_swebench_eval, instance_id, patch_diff, run_id,
            )
            return result
        except Exception as exc:
            logger.error("swebench harness failed for %s: %s", instance_id, exc)
            return TestResult(
                patch_version=0, passed=False, fail_count=1,
                error_traces=[f"swebench harness error: {exc}"],
            )

    def _run_swebench_eval(
        self, instance_id: str, patch_diff: str, run_id: str,
    ) -> TestResult:
        """Synchronous wrapper: build TestSpec, run Docker evaluation."""
        import pathlib
        import docker
        from swebench.harness.test_spec.test_spec import make_test_spec
        from swebench.harness.run_evaluation import run_instance

        issue = self._issues[instance_id]

        # Build a SWEbenchInstance-compatible dict
        swe_instance = {
            "repo": issue["repo"],
            "instance_id": instance_id,
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
        }

        # Create TestSpec
        test_spec = make_test_spec(swe_instance)

        # Normalize patch to fix common LLM formatting issues
        patch_diff = self._normalize_patch(patch_diff)

        # Create prediction dict
        prediction = {
            "instance_id": instance_id,
            "model_name_or_path": "se-blackboard",
            "model_patch": patch_diff,
        }

        # Connect to Docker — try multiple endpoints for Windows compatibility
        client = self._get_docker_client()

        # Monkey-patch Path.write_text to force Unix line endings (LF only).
        # swebench generates shell scripts & patches via write_text() which
        # defaults to CRLF on Windows — these break inside Linux containers.
        _orig_write_text = pathlib.Path.write_text

        def _write_text_lf(self_path, data, *args, **kwargs):
            kwargs.setdefault("newline", "\n")
            return _orig_write_text(self_path, data, *args, **kwargs)

        pathlib.Path.write_text = _write_text_lf  # type: ignore[assignment]
        try:
            # Run the evaluation
            report = run_instance(
                test_spec=test_spec,
                pred=prediction,
                rm_image=False,
                force_rebuild=False,
                client=client,
                run_id=run_id,
                timeout=300,
            )
        finally:
            pathlib.Path.write_text = _orig_write_text  # type: ignore[assignment]

        # Parse the report
        resolved = report.get("resolved", False)

        if resolved:
            return TestResult(
                patch_version=0,
                passed=True,
                pass_count=1,
                fail_count=0,
            )
        else:
            error_info = []
            if not report.get("completed", False):
                error_info.append("Evaluation did not complete.")
            else:
                error_info.append("Tests failed — patch did not resolve the issue.")

            return TestResult(
                patch_version=0,
                passed=False,
                pass_count=0,
                fail_count=1,
                error_traces=error_info,
            )

    @staticmethod
    def _normalize_patch(patch_diff: str) -> str:
        """Normalize an LLM-generated patch to fix common formatting issues.

        Fixes:
        - Strips markdown code fences (```diff ... ```)
        - Ensures Unix line endings (LF only)
        - Removes trailing whitespace from each line
        - Ensures the patch ends with a newline
        """
        import re

        diff = patch_diff.strip()

        # Strip markdown code fences
        diff = re.sub(r"^```(?:diff|patch)?\s*\n", "", diff)
        diff = re.sub(r"\n```\s*$", "", diff)

        # Ensure LF line endings
        diff = diff.replace("\r\n", "\n").replace("\r", "\n")

        # Remove trailing whitespace per line (but preserve leading space for context lines)
        lines = [line.rstrip() for line in diff.split("\n")]
        diff = "\n".join(lines)

        # Ensure final newline
        if not diff.endswith("\n"):
            diff += "\n"

        return diff

    @staticmethod
    def _get_docker_client() -> Any:
        """Create a Docker client, trying multiple connection methods."""
        import docker

        # Try default (works on Linux, macOS, and some Windows configs)
        try:
            client = docker.from_env()
            client.ping()
            return client
        except docker.errors.DockerException:
            pass

        # Try common Windows named pipes (Desktop Linux Engine first)
        for pipe in [
            "npipe:////./pipe/dockerDesktopLinuxEngine",
            "npipe:////./pipe/docker_engine",
        ]:
            try:
                client = docker.DockerClient(base_url=pipe)
                client.ping()
                return client
            except docker.errors.DockerException:
                continue

        # Try TCP (common in Docker Toolbox / remote setups)
        try:
            client = docker.DockerClient(base_url="tcp://localhost:2375")
            client.ping()
            return client
        except docker.errors.DockerException:
            pass

        raise RuntimeError(
            "Cannot connect to Docker. Ensure Docker Desktop is running. "
            "On Windows, enable 'Expose daemon on tcp://localhost:2375' in "
            "Docker Desktop settings, or start Docker Desktop."
        )
    # Helpers

    @staticmethod
    async def _run_cmd(
        cmd: list[str],
        cwd: str | None = None,
        check: bool = True,
        timeout: int = 300,
    ) -> subprocess.CompletedProcess[str]:
        """Run a subprocess command asynchronously."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            lambda: subprocess.run(
                cmd, capture_output=True, text=True, cwd=cwd,
                check=check, timeout=timeout,
            ),
        )


class MockSWEBenchRunner:
    """Mock SWE-bench runner for debugging and end-to-end flow testing.

    Returns plausible but synthetic results without actually cloning repos
    or running tests.
    """

    def __init__(self, pass_rate: float = 0.3) -> None:
        """
        Args:
            pass_rate: Probability that a given patch "passes" the tests.
        """
        self._pass_rate = pass_rate
        self._call_count = 0

    async def setup_instance(self, instance_id: str) -> str:
        self.current_workspace = f"/tmp/mock_workspace/{instance_id}"
        return self.current_workspace

    async def get_repo_structure(self, workspace: str, max_depth: int = 3) -> str:
        return (
            "src/\n"
            "  models/\n"
            "    query.py\n"
            "    base.py\n"
            "  views/\n"
            "    generic.py\n"
            "tests/\n"
            "  test_queries.py\n"
            "  test_views.py\n"
        )

    async def get_file_content(self, workspace: str, file_path: str) -> str:
        return f"# Mock content for {file_path}\n# This is a placeholder.\n"

    async def apply_patch(self, workspace: str, patch_diff: str) -> bool:
        return True

    async def apply_patch_with_fallback(
        self, workspace: str, patch_diff: str,
    ) -> dict[str, Any]:
        """Mock fallback apply — always succeeds via git_apply."""
        return {
            "success": True,
            "method": "git_apply",
            "stderr": "",
            "patch_output": "",
        }

    async def run_tests(self, instance_id: str, patch_diff: str) -> TestResult:
        """Return a mock test result based on configured pass rate."""
        import hashlib
        self._call_count += 1

        # Deterministic "randomness" based on instance_id + call count
        h = hashlib.md5(f"{instance_id}:{self._call_count}".encode()).hexdigest()
        score = int(h[:4], 16) / 0xFFFF
        passed = score < self._pass_rate

        if passed:
            return TestResult(
                patch_version=self._call_count,
                passed=True,
                pass_count=42,
                fail_count=0,
            )
        else:
            return TestResult(
                patch_version=self._call_count,
                passed=False,
                pass_count=38,
                fail_count=4,
                failing_tests=[
                    f"tests/test_queries.py::TestQuerySet::test_union_{i}"
                    for i in range(4)
                ],
                error_traces=[
                    "AssertionError: Expected ordered result set",
                    "ValueError: Column mismatch in UNION query",
                ],
            )

    async def search_code(self, workspace: str, query: str) -> list[dict[str, Any]]:
        return [
            {"file": "src/models/query.py", "line": 42, "content": f"# match: {query}"},
        ]
