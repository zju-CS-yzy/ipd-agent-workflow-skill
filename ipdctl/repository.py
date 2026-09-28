"""Read-only Git/SVN repository discovery for evidence metadata."""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class RepositoryInfo:
    kind: str
    root: str | None = None
    revision: str | None = None
    dirty: bool | None = None

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _run(command: list[str], cwd: Path) -> subprocess.CompletedProcess[str] | None:
    try:
        return subprocess.run(
            command,
            cwd=cwd,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None


def inspect_repository(start: str | Path = ".") -> RepositoryInfo:
    """Inspect the enclosing Git or SVN working copy without changing it."""

    location = Path(start).resolve()
    if location.is_file():
        location = location.parent

    git = shutil.which("git")
    if git:
        root_result = _run([git, "rev-parse", "--show-toplevel"], location)
        if root_result and root_result.returncode == 0:
            root = root_result.stdout.strip()
            revision_result = _run([git, "rev-parse", "HEAD"], location)
            status_result = _run([git, "status", "--porcelain"], location)
            revision = (
                revision_result.stdout.strip()
                if revision_result and revision_result.returncode == 0
                else None
            )
            dirty = (
                bool(status_result.stdout.strip())
                if status_result and status_result.returncode == 0
                else None
            )
            return RepositoryInfo("git", root or None, revision, dirty)

    svn = shutil.which("svn")
    if svn:
        root_result = _run([svn, "info", "--show-item", "wc-root"], location)
        if root_result and root_result.returncode == 0:
            root = root_result.stdout.strip()
            revision_result = _run([svn, "info", "--show-item", "revision"], location)
            status_result = _run([svn, "status", "--quiet"], location)
            revision = (
                revision_result.stdout.strip()
                if revision_result and revision_result.returncode == 0
                else None
            )
            dirty = (
                bool(status_result.stdout.strip())
                if status_result and status_result.returncode == 0
                else None
            )
            return RepositoryInfo("svn", root or None, revision, dirty)

    return RepositoryInfo("none")
