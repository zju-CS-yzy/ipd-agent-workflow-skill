"""Read-only Git/SVN repository discovery for evidence metadata.

The adapter intentionally limits itself to local working-copy commands. It
never fetches, pulls, updates, commits, pushes, or changes repository state.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlsplit, urlunsplit


@dataclass(frozen=True)
class RepositoryInfo:
    """Locally observable repository metadata.

    ``revision`` and ``dirty`` retain their original positional slots for
    compatibility with the v0.1 public API. New callers should prefer keyword
    arguments.
    """

    kind: str
    root: str | None = None
    revision: str | None = None
    dirty: bool | None = None
    branch: str | None = None
    remote: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _run(command: list[str], cwd: Path) -> subprocess.CompletedProcess[str] | None:
    """Run a bounded, non-interactive, read-only repository command."""

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


def sanitize_remote_url(remote: str | None) -> str | None:
    """Remove embedded credentials and credential-like query parameters.

    SCP-style SSH remotes such as ``git@example.test:team/project.git`` are
    preserved because their user name is an SSH account, not a secret. URL
    user-info, query values, and fragments are omitted. Query strings are not
    needed for evidence display and can carry provider-specific credentials.
    """

    if remote is None:
        return None
    value = remote.strip()
    if not value:
        return None
    try:
        parsed = urlsplit(value)
    except ValueError:
        return None

    if not parsed.scheme or not parsed.netloc:
        return value

    try:
        host = parsed.hostname
        port = parsed.port
    except ValueError:
        return None
    if not host:
        return None
    if ":" in host and not host.startswith("["):
        host = f"[{host}]"
    netloc = f"{host}:{port}" if port is not None else host
    return urlunsplit((parsed.scheme, netloc, parsed.path, "", ""))


def _successful_text(
    command: list[str], cwd: Path, *, empty_is_none: bool = True
) -> str | None:
    result = _run(command, cwd)
    if result is None or result.returncode != 0:
        return None
    value = result.stdout.strip()
    if empty_is_none and not value:
        return None
    return value


def inspect_repository(start: str | Path = ".") -> RepositoryInfo:
    """Inspect the enclosing Git or SVN working copy without changing it."""

    location = Path(start).resolve()
    if location.is_file():
        location = location.parent

    git = shutil.which("git")
    if git:
        root_text = _successful_text([git, "rev-parse", "--show-toplevel"], location)
        if root_text:
            root_path = Path(root_text).resolve()
            revision = _successful_text(
                [git, "rev-parse", "--verify", "HEAD"], root_path
            )
            branch = _successful_text(
                [git, "symbolic-ref", "--quiet", "--short", "HEAD"], root_path
            )
            status = _run(
                [git, "status", "--porcelain=v1", "--untracked-files=normal"],
                root_path,
            )
            dirty = (
                bool(status.stdout.strip())
                if status is not None and status.returncode == 0
                else None
            )

            remote: str | None = None
            names_text = _successful_text(
                [git, "remote"], root_path, empty_is_none=False
            )
            names = [
                line.strip()
                for line in (names_text or "").splitlines()
                if line.strip()
            ]
            if names:
                name = "origin" if "origin" in names else names[0]
                remote = sanitize_remote_url(
                    _successful_text([git, "remote", "get-url", name], root_path)
                )

            return RepositoryInfo(
                kind="git",
                root=str(root_path),
                revision=revision,
                dirty=dirty,
                branch=branch,
                remote=remote,
            )

    svn = shutil.which("svn")
    if svn:
        root_text = _successful_text(
            [
                svn,
                "info",
                "--non-interactive",
                "--show-item",
                "wc-root",
                str(location),
            ],
            location,
        )
        if root_text:
            root_path = Path(root_text).resolve()
            revision = _successful_text(
                [
                    svn,
                    "info",
                    "--non-interactive",
                    "--show-item",
                    "revision",
                    str(root_path),
                ],
                root_path,
            )
            remote = sanitize_remote_url(
                _successful_text(
                    [
                        svn,
                        "info",
                        "--non-interactive",
                        "--show-item",
                        "url",
                        str(root_path),
                    ],
                    root_path,
                )
            )
            status = _run(
                [svn, "status", "--non-interactive", str(root_path)], root_path
            )
            dirty = (
                bool(status.stdout.strip())
                if status is not None and status.returncode == 0
                else None
            )
            return RepositoryInfo(
                kind="svn",
                root=str(root_path),
                revision=revision,
                dirty=dirty,
                remote=remote,
            )

    return RepositoryInfo("none")


def _nul_paths(result: subprocess.CompletedProcess[str] | None) -> Iterable[str]:
    if result is None or result.returncode != 0:
        return ()
    return (item for item in result.stdout.split("\0") if item)


def _normalize_path(path: str | Path) -> str:
    value = str(path).replace("\\", "/")
    while value.startswith("./"):
        value = value[2:]
    return value.strip("/")


def _scope_paths(
    paths: Iterable[str], repository_root: Path, project_root: Path
) -> list[str]:
    """Return repository paths relative to the requested project root."""

    scoped: set[str] = set()
    for raw in paths:
        candidate = Path(os.path.normpath(str(repository_root / Path(raw))))
        try:
            relative = candidate.relative_to(project_root)
        except ValueError:
            continue
        normalized = _normalize_path(relative)
        if normalized:
            scoped.add(normalized)
    return sorted(scoped)


def _git_changed_paths(
    root: Path, *, staged: bool = False, base: str | None = None
) -> list[str]:
    git = shutil.which("git")
    if not git:
        return []

    paths: set[str] = set()
    if base:
        result = _run(
            [git, "diff", "--name-only", "-z", f"{base}...HEAD", "--"], root
        )
        if result is None or result.returncode != 0:
            result = _run(
                [git, "diff", "--name-only", "-z", base, "HEAD", "--"], root
            )
        paths.update(_normalize_path(path) for path in _nul_paths(result))
        return sorted(path for path in paths if path)

    if staged:
        result = _run(
            [git, "diff", "--cached", "--name-only", "-z", "--"], root
        )
        paths.update(_normalize_path(path) for path in _nul_paths(result))
        return sorted(path for path in paths if path)

    commands = (
        [git, "diff", "--name-only", "-z", "--"],
        [git, "diff", "--cached", "--name-only", "-z", "--"],
        [git, "ls-files", "--others", "--exclude-standard", "-z", "--"],
    )
    for command in commands:
        paths.update(_normalize_path(path) for path in _nul_paths(_run(command, root)))
    return sorted(path for path in paths if path)


def _svn_changed_paths(root: Path) -> list[str]:
    svn = shutil.which("svn")
    if not svn:
        return []
    result = _run(
        [svn, "status", "--non-interactive", "--xml", str(root)], root
    )
    if result is None or result.returncode != 0:
        return []
    try:
        tree = ET.fromstring(result.stdout)
    except ET.ParseError:
        return []

    paths: set[str] = set()
    for entry in tree.findall(".//entry"):
        raw = entry.attrib.get("path", "").strip()
        if not raw:
            continue
        path = Path(raw)
        if path.is_absolute():
            try:
                path = path.relative_to(root)
            except ValueError:
                continue
        normalized = _normalize_path(path)
        if normalized:
            paths.add(normalized)
    return sorted(paths)


def changed_paths(
    project_root: str | Path = ".",
    staged: bool = False,
    base: str | None = None,
) -> tuple[RepositoryInfo, list[str]]:
    """Return local changed paths without contacting or modifying a remote.

    Paths are normalized to POSIX separators and scoped relative to
    ``project_root``. Git includes staged, unstaged, and untracked files by
    default; ``staged=True`` limits the result to the index, while ``base``
    compares committed history with the named local revision. SVN reports its
    local working-copy status.
    """

    location = Path(project_root).resolve()
    if location.is_file():
        location = location.parent
    info = inspect_repository(location)
    if not info.root:
        return info, []

    repository_root = Path(info.root).resolve()
    if info.kind == "git":
        paths = _git_changed_paths(repository_root, staged=staged, base=base)
    elif info.kind == "svn":
        paths = _svn_changed_paths(repository_root)
    else:
        paths = []
    return info, _scope_paths(paths, repository_root, location)


# v1.4 used ``detect_vcs``. Keep the alias for migrating callers while
# preserving ``inspect_repository`` as the canonical public name.
detect_vcs = inspect_repository
