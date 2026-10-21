"""Probe explicit model adoption using a project authored by published v0.5.1."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def run() -> dict:
    with tempfile.TemporaryDirectory(prefix="ipd-v051-upgrade-") as temporary:
        work = Path(temporary)
        archive = work / "legacy.zip"
        subprocess.run(["git", "archive", "v0.5.1-beta", "--format=zip", "--output=" + str(archive)], cwd=ROOT, check=True)
        old = work / "legacy"
        with zipfile.ZipFile(archive) as handle:
            handle.extractall(old)
        project = work / "project"
        project.mkdir()
        # A fixture below another checkout must not inherit its repository or
        # artifact baseline. Exercise the same standalone Git project in CI
        # and in caller-selected temporary directories.
        for arguments in (["init", "-b", "main"],
                          ["config", "user.name", "Synthetic upgrade fixture"],
                          ["config", "user.email", "fixture@example.invalid"]):
            subprocess.run(["git", *arguments], cwd=project, check=True, capture_output=True)
        (project / "README.md").write_text("# Synthetic v0.5.1 upgrade fixture\n", encoding="utf-8")
        subprocess.run(["git", "add", "README.md"], cwd=project, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "Create synthetic baseline"],
                       cwd=project, check=True, capture_output=True)
        def invoke(source: Path, *args: str):
            env = dict(os.environ, PYTHONPATH=str(source), PYTHONUTF8="1", PYTHONDONTWRITEBYTECODE="1")
            result = subprocess.run([sys.executable, "-B", "-m", "ipdctl", *args], cwd=work,
                                    env=env, text=True, encoding="utf-8", capture_output=True)
            if result.returncode:
                raise RuntimeError(result.stderr or result.stdout)
            return result.stdout
        invoke(old, "init", str(project), "--name", "Synthetic published-project upgrade", "--locale", "zh-CN")
        invoke(old, "tailor", str(project))
        invoke(old, "refresh", str(project))
        invoke(old, "verify", str(project), "--json")
        evidence = project / "evidence" / "initial.md"
        subject = "concept.problem_definition"
        invoke(old, "claim", subject, "--project-root", str(project), "--actor", "agent")
        evidence.parent.mkdir()
        evidence.write_text("Synthetic historical work and explicit human decision\n", encoding="utf-8")
        invoke(old, "close", subject, "--project-root", str(project), "--actor", "agent", "--evidence", "evidence/initial.md")
        invoke(old, "review", subject, "--project-root", str(project), "--reviewer", "review-agent")
        invoke(old, "approve", subject, "--project-root", str(project), "--reviewer", "human", "--actor-type", "human", "--authorized", "--evidence", "evidence/initial.md")
        import yaml
        state_path = project / ".ipd/project_state.yaml"
        runtime_path = project / ".ipd/agent_runtime.yaml"
        before = yaml.safe_load(state_path.read_text(encoding="utf-8"))
        runtime = yaml.safe_load(runtime_path.read_text(encoding="utf-8"))
        files_before = {p.relative_to(project).as_posix(): p.read_bytes() for p in project.rglob("*") if p.is_file()}
        request = work / "request.json"
        request.write_text(json.dumps({"request_id": "adopt-model", "operation": "enable", "reason": "Explicit adoption of published project", "increment": "next", "product_version": "0.2"}), encoding="utf-8")
        preview = invoke(ROOT, "requirements", str(project), "--request", str(request), "--json")
        if files_before != {p.relative_to(project).as_posix(): p.read_bytes() for p in project.rglob("*") if p.is_file()}:
            raise RuntimeError("migration preview wrote project files")
        plan = work / "plan.json"
        plan.write_text(preview, encoding="utf-8")
        invoke(ROOT, "requirements", str(project), "--apply", str(plan), "--actor", "human", "--authorized")
        after = yaml.safe_load(state_path.read_text(encoding="utf-8"))
        after_runtime = yaml.safe_load(runtime_path.read_text(encoding="utf-8"))
        if before["deliverables"] != after["deliverables"] or before["claims"] != after["claims"] or before["gates"] != after["gates"]:
            raise RuntimeError("migration changed historical subjects, Claims or reviews")
        if after_runtime["events"][:len(runtime["events"])] != runtime["events"]:
            raise RuntimeError("migration lost Runtime history")
        if after["revision"] != before["revision"] + 1:
            raise RuntimeError("migration revision was not monotonic")
        if after_runtime["schema_version"] != "1.1":
            raise RuntimeError("model-enabled Runtime did not declare its new contract")
        frozen = {p.relative_to(project).as_posix(): p.read_bytes() for p in project.rglob("*") if p.is_file()}
        try:
            invoke(old, "verify", str(project), "--json")
        except RuntimeError:
            pass
        else:
            raise RuntimeError("old Skill unexpectedly accepted the new Runtime contract")
        if frozen != {p.relative_to(project).as_posix(): p.read_bytes() for p in project.rglob("*") if p.is_file()}:
            raise RuntimeError("rejected old Skill changed model-enabled facts")
        invoke(ROOT, "refresh", str(project))
        invoke(ROOT, "verify", str(project), "--json")
        return {"status": "passed", "source_tag": "v0.5.1-beta", "preview_writes": 0,
                "history_preserved": True, "revision_delta": 1, "locale": "zh-CN",
                "old_skill_rejected_without_writes": True, "runtime_schema": "1.1"}


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False, indent=2))
