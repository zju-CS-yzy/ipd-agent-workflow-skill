"""Best-effort command transaction guard for project-local authority files."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
import time
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path
from typing import Any, Iterator, Sequence

from .runtime import runtime_path
from .state import resolve_state_path


TRANSACTION_DIRECTORY = ".ipdctl-transaction"
_SCHEMA_VERSION = "1.0"
_ACTIVE_TRANSACTIONS: ContextVar[
    tuple[tuple[Path, frozenset[Path], bool], ...]
] = ContextVar("ipdctl_active_transactions", default=())
_ACTIVE_PROJECT_MUTEXES: ContextVar[tuple[Path, ...]] = ContextVar(
    "ipdctl_active_project_mutexes", default=()
)


class ProjectTransactionError(ValueError):
    """Raised when a project transaction cannot start or recover safely."""


def _project_lock_path(root: Path) -> Path:
    """Return a stable, non-project lock path without exposing the project path."""

    normalized = os.path.normcase(str(root.resolve())).encode("utf-8")
    digest = hashlib.sha256(normalized).hexdigest()
    directory = Path(tempfile.gettempdir()) / "ipdctl-project-locks"
    directory.mkdir(parents=True, exist_ok=True)
    return directory / f"{digest}.lock"


def _acquire_file_lock(handle: Any) -> None:
    if os.name == "nt":
        import msvcrt

        handle.seek(0, os.SEEK_END)
        if handle.tell() == 0:
            handle.write(b"\0")
            handle.flush()
            os.fsync(handle.fileno())
        handle.seek(0)
        msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        return

    import fcntl

    fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)


def _release_file_lock(handle: Any) -> None:
    if os.name == "nt":
        import msvcrt

        handle.seek(0)
        msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        return

    import fcntl

    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


@contextmanager
def _project_mutex(project_root: str | Path) -> Iterator[None]:
    """Hold the crash-released cross-process mutex for one project path."""

    root = Path(project_root).resolve()
    active = _ACTIVE_PROJECT_MUTEXES.get()
    if root in active:
        yield
        return

    handle = _project_lock_path(root).open("a+b")
    try:
        try:
            _acquire_file_lock(handle)
        except OSError as exc:
            raise ProjectTransactionError(
                "another project transaction started concurrently"
            ) from exc
        token = _ACTIVE_PROJECT_MUTEXES.set(active + (root,))
        try:
            yield
        finally:
            _ACTIVE_PROJECT_MUTEXES.reset(token)
            _release_file_lock(handle)
    finally:
        handle.close()


def _restore_file(path: Path, content: bytes | None) -> None:
    if content is None:
        path.unlink(missing_ok=True)
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "wb", dir=path.parent, prefix=f".{path.name}.", suffix=".rollback", delete=False
        ) as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
            temporary = handle.name
        os.replace(temporary, path)
    finally:
        if temporary:
            Path(temporary).unlink(missing_ok=True)


def _relative_path(root: Path, path: Path) -> str:
    try:
        relative = path.resolve().relative_to(root)
    except ValueError as exc:
        raise ProjectTransactionError(
            f"transaction path leaves project root: {path}"
        ) from exc
    return relative.as_posix()


def _process_liveness(pid: Any) -> bool | None:
    """Return whether a process is alive, or ``None`` when it is unknowable.

    Recovery must fail closed when the operating system refuses a process
    query.  Treating an access error as a dead owner could roll back a live
    command.
    """

    if type(pid) is not int or pid <= 0:
        return False
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes

        process = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)
        if not process:
            error = ctypes.windll.kernel32.GetLastError()
            return False if error == 87 else None
        try:
            exit_code = wintypes.DWORD()
            if not ctypes.windll.kernel32.GetExitCodeProcess(
                process, ctypes.byref(exit_code)
            ):
                return None
            return exit_code.value == 259
        finally:
            ctypes.windll.kernel32.CloseHandle(process)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return None
    return True


def _process_token(pid: Any) -> str | None:
    """Return a process creation token so a reused PID cannot hold the lock."""

    if type(pid) is not int or pid <= 0:
        return None
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes

        process = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)
        if not process:
            return None
        try:
            created = wintypes.FILETIME()
            exited = wintypes.FILETIME()
            kernel = wintypes.FILETIME()
            user = wintypes.FILETIME()
            if not ctypes.windll.kernel32.GetProcessTimes(
                process,
                ctypes.byref(created),
                ctypes.byref(exited),
                ctypes.byref(kernel),
                ctypes.byref(user),
            ):
                return None
            value = (created.dwHighDateTime << 32) | created.dwLowDateTime
            return f"windows-filetime:{value}"
        finally:
            ctypes.windll.kernel32.CloseHandle(process)
    stat = Path(f"/proc/{pid}/stat")
    try:
        text = stat.read_text(encoding="utf-8")
        remainder = text[text.rfind(")") + 2 :].split()
        return f"proc-starttime:{remainder[19]}"
    except (OSError, IndexError):
        return None


def _load_manifest(transaction: Path) -> dict[str, Any]:
    manifest_path = transaction / "manifest.json"
    try:
        value = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ProjectTransactionError(
            f"cannot read pending project transaction: {exc}"
        ) from exc
    if not isinstance(value, dict) or value.get("schema_version") != _SCHEMA_VERSION:
        raise ProjectTransactionError("pending project transaction has an invalid schema")
    if not isinstance(value.get("files"), list):
        raise ProjectTransactionError("pending project transaction has invalid files")
    return value


def _restore_transaction(root: Path, transaction: Path) -> None:
    manifest = _load_manifest(transaction)
    for record in manifest["files"]:
        if not isinstance(record, dict) or not isinstance(record.get("path"), str):
            raise ProjectTransactionError("pending transaction file record is invalid")
        path = (root / record["path"]).resolve()
        _relative_path(root, path)
        if record.get("existed") is True:
            backup_name = record.get("backup")
            if not isinstance(backup_name, str):
                raise ProjectTransactionError("pending transaction backup is missing")
            backup = (transaction / backup_name).resolve()
            try:
                backup.relative_to(transaction.resolve())
            except ValueError as exc:
                raise ProjectTransactionError(
                    "pending transaction backup leaves its directory"
                ) from exc
            if not backup.is_file():
                raise ProjectTransactionError("pending transaction backup is missing")
            _restore_file(path, backup.read_bytes())
        else:
            _restore_file(path, None)

    dashboard_record = manifest.get("dashboard", {})
    if isinstance(dashboard_record, dict) and dashboard_record.get("included") is True:
        dashboard = root / ".ipd" / "dashboard"
        if dashboard.exists():
            shutil.rmtree(dashboard)
        if dashboard_record.get("existed") is True:
            backup = transaction / "dashboard"
            if not backup.is_dir():
                raise ProjectTransactionError(
                    "pending transaction Dashboard backup is missing"
                )
            shutil.copytree(backup, dashboard)


def _retire_transaction(transaction: Path, *, outcome: str) -> None:
    """Atomically remove the canonical lock before best-effort cleanup."""

    tombstone = transaction.parent / (
        f"{TRANSACTION_DIRECTORY}.{outcome}-{os.getpid()}-{time.time_ns()}"
    )
    os.rename(transaction, tombstone)
    shutil.rmtree(tombstone, ignore_errors=True)


def _clean_retired_transactions(ipd: Path) -> None:
    for outcome in ("aborted", "committed", "rolled-back", "recovered"):
        for tombstone in ipd.glob(f"{TRANSACTION_DIRECTORY}.{outcome}-*"):
            if tombstone.is_dir():
                shutil.rmtree(tombstone, ignore_errors=True)


def _recover_pending_transaction_unlocked(project_root: str | Path) -> bool:
    root = Path(project_root).resolve()
    ipd = root / ".ipd"
    transaction = ipd / TRANSACTION_DIRECTORY
    if not transaction.exists():
        if ipd.is_dir():
            _clean_retired_transactions(ipd)
        return False
    manifest = _load_manifest(transaction)
    owner_pid = manifest.get("owner_pid")
    owner_token = manifest.get("owner_token")
    liveness = _process_liveness(owner_pid)
    if liveness is None:
        raise ProjectTransactionError(
            f"cannot determine whether project transaction owner process "
            f"{owner_pid} is active"
        )
    current_token = _process_token(owner_pid) if liveness else None
    same_process = liveness and (
        not isinstance(owner_token, str)
        or current_token is None
        or owner_token == current_token
    )
    if same_process:
        raise ProjectTransactionError(
            f"project transaction is still active in process {owner_pid}"
        )
    phase = manifest.get("phase", "ready")
    if phase == "preparing":
        _retire_transaction(transaction, outcome="aborted")
        _clean_retired_transactions(ipd)
        return True
    if phase != "ready":
        raise ProjectTransactionError("pending project transaction has an invalid schema")
    _restore_transaction(root, transaction)
    _retire_transaction(transaction, outcome="recovered")
    _clean_retired_transactions(ipd)
    return True


def recover_pending_transaction(project_root: str | Path) -> bool:
    """Recover a terminated transaction while excluding every project command."""

    with _project_mutex(project_root):
        return _recover_pending_transaction_unlocked(project_root)


@contextmanager
def project_access_guard(project_root: str | Path) -> Iterator[None]:
    """Recover once, then hold a stable read view for a non-mutating command."""

    with _project_mutex(project_root):
        _recover_pending_transaction_unlocked(project_root)
        yield


def _prepare_transaction(
    root: Path,
    files: Sequence[Path],
    *,
    include_dashboard: bool,
) -> Path:
    ipd = root / ".ipd"
    ipd.mkdir(parents=True, exist_ok=True)
    transaction = ipd / TRANSACTION_DIRECTORY
    staging = Path(
        tempfile.mkdtemp(prefix=f"{TRANSACTION_DIRECTORY}.prepare-", dir=ipd)
    )
    acquired = False
    try:
        preparing_manifest = {
            "schema_version": _SCHEMA_VERSION,
            "phase": "preparing",
            "owner_pid": os.getpid(),
            "owner_token": _process_token(os.getpid()),
            "files": [],
            "dashboard": {"included": False, "existed": False},
        }
        manifest_path = staging / "manifest.json"
        with manifest_path.open("w", encoding="utf-8", newline="\n") as handle:
            json.dump(preparing_manifest, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.rename(staging, transaction)
        except OSError as exc:
            raise ProjectTransactionError(
                "another project transaction started concurrently"
            ) from exc
        acquired = True

        # The canonical transaction directory is the lock.  Snapshot only
        # after acquiring it so a losing contender can never capture stale
        # bytes and later roll back a command that already committed.
        records: list[dict[str, Any]] = []
        backup_root = transaction / "files"
        backup_root.mkdir()
        for index, path in enumerate(files):
            relative = _relative_path(root, path)
            existed = path.is_file()
            record: dict[str, Any] = {"path": relative, "existed": existed}
            if existed:
                backup_name = f"files/{index}.bin"
                backup = transaction / backup_name
                backup.write_bytes(path.read_bytes())
                record["backup"] = backup_name
            records.append(record)
        dashboard = root / ".ipd" / "dashboard"
        dashboard_existed = include_dashboard and dashboard.is_dir()
        if dashboard_existed:
            shutil.copytree(dashboard, transaction / "dashboard")
        manifest = {
            "schema_version": _SCHEMA_VERSION,
            "phase": "ready",
            "owner_pid": os.getpid(),
            "owner_token": _process_token(os.getpid()),
            "files": records,
            "dashboard": {
                "included": include_dashboard,
                "existed": dashboard_existed,
            },
        }
        ready_manifest = transaction / "manifest.ready.json"
        with ready_manifest.open("w", encoding="utf-8", newline="\n") as handle:
            json.dump(manifest, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(ready_manifest, transaction / "manifest.json")
        return transaction
    except BaseException:
        if acquired and transaction.exists():
            _retire_transaction(transaction, outcome="aborted")
        raise
    finally:
        if staging.exists():
            shutil.rmtree(staging, ignore_errors=True)


@contextmanager
def project_mutation_guard(
    project_root: str | Path,
    *,
    extra_files: Sequence[str | Path] = (),
    include_dashboard: bool = False,
) -> Iterator[None]:
    """Commit a multi-file command or recover it after exception/process loss."""

    root = Path(project_root).resolve()
    tracked = [resolve_state_path(root), runtime_path(root)]
    for value in extra_files:
        path = Path(value)
        tracked.append((root / path).resolve() if not path.is_absolute() else path.resolve())
    unique_files = tuple(dict.fromkeys(tracked))

    active = _ACTIVE_TRANSACTIONS.get()
    for active_root, active_files, active_dashboard in reversed(active):
        if active_root != root:
            continue
        missing = set(unique_files) - set(active_files)
        if missing or (include_dashboard and not active_dashboard):
            rendered = ", ".join(sorted(path.as_posix() for path in missing))
            raise ProjectTransactionError(
                "nested project transaction exceeds the outer transaction scope"
                + (f": {rendered}" if rendered else "")
            )
        yield
        return

    with _project_mutex(root):
        _recover_pending_transaction_unlocked(root)
        transaction = _prepare_transaction(
            root, unique_files, include_dashboard=include_dashboard
        )
        token = _ACTIVE_TRANSACTIONS.set(
            active + ((root, frozenset(unique_files), include_dashboard),)
        )
        try:
            try:
                yield
            except BaseException as original:
                try:
                    _restore_transaction(root, transaction)
                    _retire_transaction(transaction, outcome="rolled-back")
                except Exception as rollback_error:
                    raise ProjectTransactionError(
                        f"project rollback failed after {type(original).__name__}: "
                        f"{rollback_error}"
                    ) from original
                raise
            else:
                _retire_transaction(transaction, outcome="committed")
        finally:
            _ACTIVE_TRANSACTIONS.reset(token)


__all__ = [
    "ProjectTransactionError",
    "TRANSACTION_DIRECTORY",
    "project_access_guard",
    "project_mutation_guard",
    "recover_pending_transaction",
]
