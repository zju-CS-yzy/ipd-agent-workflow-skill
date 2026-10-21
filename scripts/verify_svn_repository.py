"""Qualify read-only adapters against an isolated, real local SVN repository.

Requires svn and svnadmin on PATH. Missing clients are a failure, not a skip.
Setup commits and updates belong to this synthetic fixture; Skill operations
are recorded separately and must issue only read commands without byte changes.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ipdctl.documents import RequirementError
from ipdctl.reconcile import reconcile_project
from ipdctl.repository import changed_paths, inspect_repository
from ipdctl.requirements import _accepted_source, apply_plan, preview
from ipdctl.state import load_state, write_state


def hashes(root: Path) -> dict[str, str]:
    return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(root.rglob("*")) if p.is_file()}


def run(locale: str = "en") -> dict:
    for executable in ("svn", "svnadmin"):
        if not shutil.which(executable):
            raise RuntimeError(executable + " is required for real SVN qualification")
    execute = subprocess.run
    version = execute(["svn", "--version", "--quiet"], check=True, capture_output=True,
                      text=True).stdout.strip()
    with tempfile.TemporaryDirectory(prefix="ipd-real-svn-") as temporary:
        work = Path(temporary).resolve()
        repository, first, second = work / "repository", work / "first", work / "second"
        previous_ceiling = os.environ.get("GIT_CEILING_DIRECTORIES")
        os.environ["GIT_CEILING_DIRECTORIES"] = str(work)
        calls: list[list[str]] = []

        def command(*args: str, cwd: Path = work) -> str:
            result = execute(list(args), cwd=cwd, capture_output=True, text=True,
                             encoding="utf-8", timeout=120)
            if result.returncode:
                raise RuntimeError(result.stderr or result.stdout)
            return result.stdout.strip()

        def readonly(operation):
            before = {name: hashes(path) for name, path in
                      (("repository", repository), ("first", first), ("second", second))}

            def audited(args, **kwargs):
                values = [str(value) for value in args]
                executable = Path(values[0]).stem.lower()
                allowed = {"svn": {"info", "status", "cat"},
                           "git": {"rev-parse", "status", "symbolic-ref", "remote", "config"}}
                if executable not in allowed or len(values) < 2 or values[1] not in allowed[executable]:
                    raise AssertionError("Unexpected adapter command: " + repr(values))
                calls.append(values)
                return execute(args, **kwargs)

            with patch("subprocess.run", side_effect=audited):
                result = operation()
            after = {name: hashes(path) for name, path in
                     (("repository", repository), ("first", first), ("second", second))}
            if before != after:
                raise AssertionError("Read-only operation changed repository or working-copy bytes")
            return result

        try:
            command("svnadmin", "create", str(repository))
            repository_url = repository.as_uri()
            trunk = repository_url + "/trunk"
            command("svn", "mkdir", trunk, "-m", "Create synthetic trunk", "--non-interactive")
            command("svn", "checkout", trunk, str(first), "--non-interactive")
            command("svn", "checkout", trunk, str(second), "--non-interactive")
            environment = dict(os.environ, PYTHONPATH=str(ROOT), PYTHONUTF8="1",
                               PYTHONDONTWRITEBYTECODE="1")
            for arguments in (("init", str(first), "--name", "Synthetic SVN qualification", "--locale", locale),
                              ("tailor", str(first))):
                result = execute([sys.executable, "-B", "-m", "ipdctl", *arguments],
                                 cwd=work, env=environment, capture_output=True, text=True,
                                 encoding="utf-8", timeout=120)
                if result.returncode:
                    raise RuntimeError(result.stderr or result.stdout)
            plan = preview(first, {"request_id": "svn-enable", "operation": "enable",
                                  "reason": "Synthetic SVN qualification", "increment": "mvp",
                                  "product_version": "0.1"})
            apply_plan(first, plan, actor="synthetic-human", authorized=True)
            state = load_state(first / ".ipd/project_state.yaml")
            owner = state["deliverables"][0]["id"]
            bindings = load_state(first / ".ipd/artifact_bindings.yaml")
            bindings["bindings"].append({"id": "svn-documents", "glob": "docs/**",
                                         "deliverable": owner, "role": "owner", "critical": True})
            write_state(first / ".ipd/artifact_bindings.yaml", bindings)
            relative = "docs/接口 @ shared document.md"
            document = first / relative
            document.write_text("Synthetic accepted document\n", encoding="utf-8")
            command("svn", "add", "--force", ".", "--non-interactive", cwd=first)
            command("svn", "commit", "-m", "Accept synthetic facts", "--non-interactive", cwd=first)
            command("svn", "update", "--non-interactive", cwd=first)
            command("svn", "update", "--non-interactive", cwd=second)
            revision = command("svn", "info", "--show-item", "revision", str(first))
            source = {"backend": "svn", "repository": repository_url,
                      "revision": revision, "path": "trunk"}
            accepted_facts = hashes(first / ".ipd")
            if accepted_facts != hashes(second / ".ipd"):
                raise AssertionError("Two working copies did not reproduce the accepted facts")
            for working_copy in (first, second):
                info = readonly(lambda: inspect_repository(working_copy))
                if info.kind != "svn" or info.revision != revision or info.dirty or info.remote != trunk:
                    raise AssertionError("Clean SVN metadata differs: " + repr(info))
                if readonly(lambda: changed_paths(working_copy))[1]:
                    raise AssertionError("Clean SVN working copy has changed paths")
                readonly(lambda: _accepted_source(working_copy, source))

            document.write_text("Synthetic edited document\n", encoding="utf-8")
            (first / "tests").mkdir(exist_ok=True)
            (first / "tests/unbound.py").write_text("# Synthetic unbound change\n", encoding="utf-8")
            (first / "notes.txt").write_text("Synthetic unbound note\n", encoding="utf-8")
            expected = sorted([relative, "tests/unbound.py", "notes.txt"])
            dirty, paths = readonly(lambda: changed_paths(first))
            if not dirty.dirty or paths != expected:
                raise AssertionError("SVN changed paths differ: " + repr(paths))
            report = readonly(lambda: reconcile_project(first, state, write=False))
            if relative not in report["mapping"]["deliverables"][owner]:
                raise AssertionError("Unicode document was not mapped to its Owner")
            unbound = {i.get("path"): i["severity"] for i in report["issues"]
                       if i["code"] == "UNBOUND_CHANGED_PATH"}
            if unbound.get("tests/unbound.py") != "error" or unbound.get("notes.txt") != "warning":
                raise AssertionError("SVN unbound change severities differ: " + repr(unbound))
            profile = first / ".ipd/task_profile.yaml"
            profile.write_bytes(profile.read_bytes() + b"\n# unaccepted working change\n")

            def reject_changed_facts():
                try:
                    _accepted_source(first, source)
                except RequirementError as error:
                    if "BASELINE_SOURCE" not in str(error):
                        raise
                    return
                raise AssertionError("Unaccepted SVN working facts were accepted")

            readonly(reject_changed_facts)
            readonly(lambda: _accepted_source(second, source))
            if accepted_facts != hashes(second / ".ipd"):
                raise AssertionError("Dirty first copy affected the accepted second copy")
            cat_calls = [c for c in calls if Path(c[0]).stem.lower() == "svn" and c[1] == "cat"]
            if not cat_calls or not all(c[2:5] == ["--non-interactive", "-r", revision]
                                        and c[-1].endswith("@" + revision) for c in cat_calls):
                raise AssertionError("SVN source reads were not revision pinned")
            return {"status": "passed", "locale": locale, "svn_version": version,
                    "working_copies": 2, "accepted_revision": revision,
                    "accepted_facts_identical": True, "unaccepted_facts_rejected": True,
                    "unicode_and_space_paths": True, "readonly_bytes_unchanged": True,
                    "adapter_read_commands": len(calls), "revision_pinned_cat_commands": len(cat_calls),
                    "scope": "local file://; metadata, change mapping, read-only reconciliation and accepted-source comparison",
                    "not_qualified": ["remote authentication", "mixed-revision detection", "team operation acceptance"]}
        finally:
            if previous_ceiling is None:
                os.environ.pop("GIT_CEILING_DIRECTORIES", None)
            else:
                os.environ["GIT_CEILING_DIRECTORIES"] = previous_ceiling


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--locale", choices=("en", "zh-CN"), default="en")
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    result = run(arguments.locale)
    text = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if arguments.output:
        arguments.output.parent.mkdir(parents=True, exist_ok=True)
        arguments.output.write_text(text, encoding="utf-8")
    print(text, end="")
