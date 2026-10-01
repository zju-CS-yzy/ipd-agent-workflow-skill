from __future__ import annotations

import io
import json
import subprocess
import sys
import tempfile
import time
import unittest
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from ipdctl.cli import main
from ipdctl.state import load_state, write_state
from ipdctl.transaction import ProjectTransactionError, recover_pending_transaction


class CliV032LifecycleTests(unittest.TestCase):
    def invoke(self, arguments: list[str]) -> tuple[int, str, str]:
        stdout = io.StringIO()
        stderr = io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            code = main(arguments)
        return code, stdout.getvalue(), stderr.getvalue()

    def initialize(self, root: Path) -> None:
        self.assertEqual(self.invoke(["init", str(root), "--name", "demo"])[0], 0)
        self.assertEqual(self.invoke(["tailor", str(root)])[0], 0)

    def test_adopt_baseline_preview_authorization_and_idempotency(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "project"
            self.initialize(root)
            runtime_path = root / ".ipd" / "agent_runtime.yaml"
            state_path = root / ".ipd" / "project_state.yaml"
            before_runtime = runtime_path.read_bytes()
            before_state = state_path.read_bytes()

            code, output, error = self.invoke(
                ["adopt-baseline", str(root), "--preview", "--json"]
            )
            self.assertEqual(code, 0, error)
            self.assertTrue(json.loads(output)["preview"])
            self.assertEqual(runtime_path.read_bytes(), before_runtime)
            self.assertEqual(state_path.read_bytes(), before_state)

            code, _, _ = self.invoke(["adopt-baseline", str(root), "--json"])
            self.assertEqual(code, 1)
            self.assertEqual(runtime_path.read_bytes(), before_runtime)

            arguments = [
                "adopt-baseline",
                str(root),
                "--actor",
                "release-owner",
                "--actor-type",
                "human",
                "--authorized",
                "--reason",
                "accept existing working tree",
                "--json",
            ]
            code, output, error = self.invoke(arguments)
            self.assertEqual(code, 0, error)
            first = json.loads(output)
            self.assertTrue(first["adopted"])
            adopted_bytes = runtime_path.read_bytes()
            runtime = load_state(runtime_path)
            self.assertEqual(runtime["events"][-1]["action"], "artifact_baseline_adopted")
            self.assertEqual(state_path.read_bytes(), before_state)

            code, output, error = self.invoke(arguments)
            self.assertEqual(code, 0, error)
            self.assertTrue(json.loads(output)["idempotent"])
            self.assertEqual(runtime_path.read_bytes(), adopted_bytes)

    def test_claim_window_and_invalid_binding_preflight_are_atomic(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "project"
            self.initialize(root)
            deliverable = "concept.problem_definition"
            code, _, error = self.invoke(
                [
                    "claim",
                    deliverable,
                    "--project-root",
                    str(root),
                    "--actor",
                    "agent-a",
                ]
            )
            self.assertEqual(code, 0, error)
            runtime = load_state(root / ".ipd" / "agent_runtime.yaml")
            event = next(item for item in reversed(runtime["events"]) if item["action"] == "claim")
            self.assertEqual(
                set(event["binding_window"]),
                {
                    "schema_version",
                    "bindings_sha256",
                    "baseline_id",
                    "opened_paths",
                    "snapshot_sha256",
                },
            )
            runtime_path = root / ".ipd" / "agent_runtime.yaml"
            state_path = root / ".ipd" / "project_state.yaml"
            evidence = root / "evidence" / deliverable / "draft.md"
            evidence.parent.mkdir(parents=True, exist_ok=True)
            evidence.write_text("work started\n", encoding="utf-8")
            runtime_before = runtime_path.read_bytes()
            state_before = state_path.read_bytes()
            code, _, error = self.invoke(
                [
                    "claim",
                    deliverable,
                    "--project-root",
                    str(root),
                    "--actor",
                    "agent-a",
                ]
            )
            self.assertEqual(code, 0, error)
            self.assertEqual(runtime_path.read_bytes(), runtime_before)
            self.assertEqual(state_path.read_bytes(), state_before)

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "project"
            self.initialize(root)
            bindings_path = root / ".ipd" / "artifact_bindings.yaml"
            bindings_path.write_text("bindings: [\n", encoding="utf-8")
            state_path = root / ".ipd" / "project_state.yaml"
            runtime_path = root / ".ipd" / "agent_runtime.yaml"
            before_state = state_path.read_bytes()
            before_runtime = runtime_path.read_bytes()
            code, _, _ = self.invoke(
                [
                    "claim",
                    "concept.problem_definition",
                    "--project-root",
                    str(root),
                    "--actor",
                    "agent-a",
                ]
            )
            self.assertEqual(code, 1)
            self.assertEqual(state_path.read_bytes(), before_state)
            self.assertEqual(runtime_path.read_bytes(), before_runtime)

    def test_claim_runtime_write_failure_rolls_back_project_state(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "project"
            self.initialize(root)
            state_path = root / ".ipd" / "project_state.yaml"
            runtime_path = root / ".ipd" / "agent_runtime.yaml"
            before_state = state_path.read_bytes()
            before_runtime = runtime_path.read_bytes()
            with patch(
                "ipdctl.cli_v2.save_runtime",
                side_effect=OSError("injected runtime write failure"),
            ):
                code, _, error = self.invoke(
                    [
                        "claim",
                        "concept.problem_definition",
                        "--project-root",
                        str(root),
                        "--actor",
                        "agent-a",
                    ]
                )
            self.assertEqual(code, 1)
            self.assertIn("injected runtime write failure", error)
            self.assertEqual(state_path.read_bytes(), before_state)
            self.assertEqual(runtime_path.read_bytes(), before_runtime)
            code, output, error = self.invoke(["context", str(root), "--json"])
            self.assertEqual(code, 0, error)
            self.assertEqual(json.loads(output)["recoverable_claims"], [])

    def test_next_command_recovers_claim_interrupted_by_process_exit(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "project"
            self.initialize(root)
            state_path = root / ".ipd" / "project_state.yaml"
            runtime_path = root / ".ipd" / "agent_runtime.yaml"
            before_state = state_path.read_bytes()
            before_runtime = runtime_path.read_bytes()
            script = "\n".join(
                (
                    "import os",
                    "from ipdctl import cli_v2",
                    "def crash(*args, **kwargs): os._exit(77)",
                    "cli_v2.save_runtime = crash",
                    "cli_v2.main(" + repr(
                        [
                            "claim",
                            "concept.problem_definition",
                            "--project-root",
                            str(root),
                            "--actor",
                            "agent-a",
                        ]
                    ) + ")",
                )
            )
            crashed = subprocess.run(
                [sys.executable, "-B", "-c", script],
                cwd=Path(__file__).resolve().parents[1],
                check=False,
                capture_output=True,
                text=True,
                timeout=60,
            )
            self.assertEqual(crashed.returncode, 77)
            self.assertNotEqual(state_path.read_bytes(), before_state)
            self.assertTrue(
                (root / ".ipd" / ".ipdctl-transaction").is_dir()
            )

            code, output, error = self.invoke(["context", str(root), "--json"])
            self.assertEqual(code, 0, error)
            self.assertEqual(state_path.read_bytes(), before_state)
            self.assertEqual(runtime_path.read_bytes(), before_runtime)
            self.assertEqual(json.loads(output)["recoverable_claims"], [])
            self.assertFalse(
                (root / ".ipd" / ".ipdctl-transaction").exists()
            )

    def test_dead_transaction_recovery_is_cross_process_serialized(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            temporary = Path(directory)
            root = temporary / "project"
            self.initialize(root)
            state_path = root / ".ipd" / "project_state.yaml"
            runtime_path = root / ".ipd" / "agent_runtime.yaml"
            before_state = state_path.read_bytes()
            before_runtime = runtime_path.read_bytes()
            crash_script = "\n".join(
                (
                    "import os",
                    "from ipdctl import cli_v2",
                    "def crash(*args, **kwargs): os._exit(77)",
                    "cli_v2.save_runtime = crash",
                    "cli_v2.main(" + repr(
                        [
                            "claim",
                            "concept.problem_definition",
                            "--project-root",
                            str(root),
                            "--actor",
                            "agent-a",
                        ]
                    ) + ")",
                )
            )
            crashed = subprocess.run(
                [sys.executable, "-B", "-c", crash_script],
                cwd=Path(__file__).resolve().parents[1],
                check=False,
                capture_output=True,
                text=True,
                timeout=60,
            )
            self.assertEqual(crashed.returncode, 77)

            ready = temporary / "recovery-started"
            release = temporary / "release-recovery"
            recovery_script = "\n".join(
                (
                    "import time",
                    "from pathlib import Path",
                    "from ipdctl import transaction",
                    "real_restore = transaction._restore_transaction",
                    "def delayed_restore(*args, **kwargs):",
                    f"    Path({str(ready)!r}).write_text('ready', encoding='utf-8')",
                    f"    while not Path({str(release)!r}).exists(): time.sleep(0.02)",
                    "    return real_restore(*args, **kwargs)",
                    "transaction._restore_transaction = delayed_restore",
                    "recovered = transaction.recover_pending_transaction(" + repr(str(root)) + ")",
                    "raise SystemExit(0 if recovered else 9)",
                )
            )
            recovery = subprocess.Popen(
                [sys.executable, "-B", "-c", recovery_script],
                cwd=Path(__file__).resolve().parents[1],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            try:
                deadline = time.monotonic() + 20
                while not ready.exists() and time.monotonic() < deadline:
                    time.sleep(0.02)
                self.assertTrue(ready.is_file())
                code, _, error = self.invoke(["context", str(root), "--json"])
                self.assertEqual(code, 1)
                self.assertIn("another project transaction started concurrently", error)
            finally:
                release.write_text("release", encoding="utf-8")
            stdout, stderr = recovery.communicate(timeout=60)
            self.assertEqual(recovery.returncode, 0, stderr + stdout)

            self.assertEqual(state_path.read_bytes(), before_state)
            self.assertEqual(runtime_path.read_bytes(), before_runtime)
            self.assertFalse(
                (root / ".ipd" / ".ipdctl-transaction").exists()
            )
            code, output, error = self.invoke(["context", str(root), "--json"])
            self.assertEqual(code, 0, error)
            self.assertEqual(json.loads(output)["recoverable_claims"], [])

    def test_force_init_process_exit_restores_authority_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "project"
            self.initialize(root)
            authority_paths = [
                root / ".ipd" / "task_profile.yaml",
                root / ".ipd" / "project_state.yaml",
                root / ".ipd" / "agent_runtime.yaml",
                root / ".ipd" / "artifact_bindings.yaml",
            ]
            before = {path: path.read_bytes() for path in authority_paths}
            script = "\n".join(
                (
                    "import os",
                    "from ipdctl import cli_v2, project",
                    "real_write = project.write_state",
                    "calls = 0",
                    "def crash_on_second_write(path, value):",
                    "    global calls",
                    "    calls += 1",
                    "    result = real_write(path, value)",
                    "    if calls == 2: os._exit(66)",
                    "    return result",
                    "project.write_state = crash_on_second_write",
                    "raise SystemExit(cli_v2.main(" + repr(
                        [
                            "init",
                            str(root),
                            "--name",
                            "replacement",
                            "--force",
                        ]
                    ) + "))",
                )
            )
            crashed = subprocess.run(
                [sys.executable, "-B", "-c", script],
                cwd=Path(__file__).resolve().parents[1],
                check=False,
                capture_output=True,
                text=True,
                timeout=60,
            )
            self.assertEqual(crashed.returncode, 66)
            self.assertNotEqual(authority_paths[0].read_bytes(), before[authority_paths[0]])
            self.assertNotEqual(authority_paths[1].read_bytes(), before[authority_paths[1]])
            self.assertTrue(
                (root / ".ipd" / ".ipdctl-transaction").is_dir()
            )

            code, _, error = self.invoke(["context", str(root)])
            self.assertEqual(code, 0, error)
            self.assertEqual(
                {path: path.read_bytes() for path in authority_paths}, before
            )

    def test_cleanup_crash_preserves_committed_claim(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "project"
            self.initialize(root)
            script = "\n".join(
                (
                    "import os",
                    "from ipdctl import cli_v2, transaction",
                    "real_rmtree = transaction.shutil.rmtree",
                    "def crash_on_committed(path, *args, **kwargs):",
                    "    if '.ipdctl-transaction.committed-' in str(path):",
                    "        os._exit(88)",
                    "    return real_rmtree(path, *args, **kwargs)",
                    "transaction.shutil.rmtree = crash_on_committed",
                    "cli_v2.main(" + repr(
                        [
                            "claim",
                            "concept.problem_definition",
                            "--project-root",
                            str(root),
                            "--actor",
                            "agent-a",
                        ]
                    ) + ")",
                )
            )
            crashed = subprocess.run(
                [sys.executable, "-B", "-c", script],
                cwd=Path(__file__).resolve().parents[1],
                check=False,
                capture_output=True,
                text=True,
                timeout=60,
            )
            self.assertEqual(crashed.returncode, 88)
            self.assertFalse(
                (root / ".ipd" / ".ipdctl-transaction").exists()
            )
            self.assertTrue(
                any(
                    path.name.startswith(".ipdctl-transaction.committed-")
                    for path in (root / ".ipd").iterdir()
                )
            )

            code, output, error = self.invoke(["context", str(root), "--json"])
            self.assertEqual(code, 0, error)
            context = json.loads(output)
            self.assertEqual(
                context["active_claims"]["concept.problem_definition"]["actor"],
                "agent-a",
            )
            runtime = load_state(root / ".ipd" / "agent_runtime.yaml")
            self.assertEqual(
                [event["action"] for event in runtime["events"]].count("claim"),
                1,
            )
            self.assertFalse(
                any(
                    path.name.startswith(".ipdctl-transaction.committed-")
                    for path in (root / ".ipd").iterdir()
                )
            )

    def test_concurrent_claim_cannot_report_two_successes_or_lose_history(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "project"
            self.initialize(root)
            claim_args = [
                "claim",
                "concept.problem_definition",
                "--project-root",
                str(root),
                "--actor",
                "agent-a",
            ]
            delayed_script = "\n".join(
                (
                    "import time",
                    "from ipdctl import cli_v2",
                    "real_claim = cli_v2._cmd_claim",
                    "def delayed_claim(args):",
                    "    time.sleep(2)",
                    "    return real_claim(args)",
                    "cli_v2._cmd_claim = delayed_claim",
                    "raise SystemExit(cli_v2.main(" + repr(claim_args) + "))",
                )
            )
            first = subprocess.Popen(
                [sys.executable, "-B", "-c", delayed_script],
                cwd=Path(__file__).resolve().parents[1],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            transaction = root / ".ipd" / ".ipdctl-transaction"
            deadline = time.monotonic() + 20
            while not transaction.exists() and time.monotonic() < deadline:
                time.sleep(0.05)
            self.assertTrue(transaction.is_dir())

            second_args = [*claim_args[:-1], "agent-b"]
            second_script = (
                "from ipdctl.cli_v2 import main; "
                "raise SystemExit(main(" + repr(second_args) + "))"
            )
            second = subprocess.run(
                [sys.executable, "-B", "-c", second_script],
                cwd=Path(__file__).resolve().parents[1],
                check=False,
                capture_output=True,
                text=True,
                timeout=60,
            )
            first_stdout, first_stderr = first.communicate(timeout=60)
            self.assertEqual(first.returncode, 0, first_stderr + first_stdout)
            self.assertEqual(second.returncode, 1, second.stderr + second.stdout)

            runtime = load_state(root / ".ipd" / "agent_runtime.yaml")
            claims = [
                event for event in runtime["events"] if event["action"] == "claim"
            ]
            self.assertEqual(len(claims), 1)
            self.assertEqual(claims[0]["actor"], "agent-a")
            self.assertEqual(
                runtime["active_claims"]["concept.problem_definition"]["actor"],
                "agent-a",
            )

    def test_snapshot_is_taken_only_after_the_transaction_lock_is_acquired(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            temporary = Path(directory)
            root = temporary / "project"
            self.initialize(root)
            ready = temporary / "contender-ready"
            release = temporary / "release-contender"
            claim = [
                "claim",
                "concept.problem_definition",
                "--project-root",
                str(root),
                "--actor",
                "agent-b",
            ]
            delayed_script = "\n".join(
                (
                    "import time",
                    "from pathlib import Path",
                    "from ipdctl import cli_v2, transaction",
                    "real_rename = transaction.os.rename",
                    "def delayed_lock(src, dst):",
                    "    source = Path(src)",
                    "    target = Path(dst)",
                    "    if (source.name.startswith('.ipdctl-transaction.prepare-') "
                    "and target.name == '.ipdctl-transaction'):",
                    f"        Path({str(ready)!r}).write_text('ready', encoding='utf-8')",
                    f"        while not Path({str(release)!r}).exists(): time.sleep(0.02)",
                    "    return real_rename(src, dst)",
                    "transaction.os.rename = delayed_lock",
                    "raise SystemExit(cli_v2.main(" + repr(claim) + "))",
                )
            )
            contender = subprocess.Popen(
                [sys.executable, "-B", "-c", delayed_script],
                cwd=Path(__file__).resolve().parents[1],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            deadline = time.monotonic() + 20
            while not ready.exists() and time.monotonic() < deadline:
                time.sleep(0.02)
            reached_barrier = ready.is_file()
            code, _, error = self.invoke([*claim[:-1], "agent-a"])
            release.write_text("release", encoding="utf-8")
            stdout, stderr = contender.communicate(timeout=60)
            self.assertTrue(reached_barrier)
            self.assertEqual(code, 1)
            self.assertIn("another project transaction started concurrently", error)
            self.assertEqual(contender.returncode, 0, stderr + stdout)

            runtime = load_state(root / ".ipd" / "agent_runtime.yaml")
            claims = [
                event for event in runtime["events"] if event["action"] == "claim"
            ]
            self.assertEqual(len(claims), 1)
            self.assertEqual(claims[0]["actor"], "agent-b")
            self.assertEqual(
                runtime["active_claims"]["concept.problem_definition"]["actor"],
                "agent-b",
            )

    def test_preparing_transaction_blocks_a_concurrent_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            temporary = Path(directory)
            root = temporary / "project"
            self.initialize(root)
            ready = temporary / "lock-acquired"
            release = temporary / "release-owner"
            claim = [
                "claim",
                "concept.problem_definition",
                "--project-root",
                str(root),
                "--actor",
                "agent-b",
            ]
            owner_script = "\n".join(
                (
                    "import time",
                    "from pathlib import Path",
                    "from ipdctl import cli_v2, transaction",
                    "real_relative = transaction._relative_path",
                    "paused = False",
                    "def pause_before_snapshot(root, path):",
                    "    global paused",
                    "    if not paused:",
                    "        paused = True",
                    f"        Path({str(ready)!r}).write_text('ready', encoding='utf-8')",
                    f"        while not Path({str(release)!r}).exists(): time.sleep(0.02)",
                    "    return real_relative(root, path)",
                    "transaction._relative_path = pause_before_snapshot",
                    "raise SystemExit(cli_v2.main(" + repr(claim) + "))",
                )
            )
            owner = subprocess.Popen(
                [sys.executable, "-B", "-c", owner_script],
                cwd=Path(__file__).resolve().parents[1],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            deadline = time.monotonic() + 20
            while not ready.exists() and time.monotonic() < deadline:
                time.sleep(0.02)
            reached_barrier = ready.is_file()
            code, _, error = self.invoke([*claim[:-1], "agent-a"])
            release.write_text("release", encoding="utf-8")
            stdout, stderr = owner.communicate(timeout=60)
            self.assertTrue(reached_barrier)
            self.assertEqual(code, 1)
            self.assertIn("another project transaction started concurrently", error)
            self.assertEqual(owner.returncode, 0, stderr + stdout)

            runtime = load_state(root / ".ipd" / "agent_runtime.yaml")
            claims = [
                event for event in runtime["events"] if event["action"] == "claim"
            ]
            self.assertEqual(len(claims), 1)
            self.assertEqual(claims[0]["actor"], "agent-b")

    def test_transaction_recovery_cleans_preparing_journal_and_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "project"
            transaction = root / ".ipd" / ".ipdctl-transaction"
            transaction.mkdir(parents=True)
            manifest = {
                "schema_version": "1.0",
                "phase": "preparing",
                "owner_pid": 4312,
                "owner_token": "test-token",
                "files": [],
                "dashboard": {"included": False, "existed": False},
            }
            (transaction / "manifest.json").write_text(
                json.dumps(manifest), encoding="utf-8"
            )
            with patch("ipdctl.transaction._process_liveness", return_value=False):
                self.assertTrue(recover_pending_transaction(root))
            self.assertFalse(transaction.exists())

            transaction.mkdir()
            manifest["phase"] = "ready"
            (transaction / "manifest.json").write_text(
                json.dumps(manifest), encoding="utf-8"
            )
            with patch("ipdctl.transaction._process_liveness", return_value=None):
                with self.assertRaisesRegex(
                    ProjectTransactionError,
                    "cannot determine whether project transaction owner process 4312",
                ):
                    recover_pending_transaction(root)
            self.assertTrue(transaction.is_dir())

    def test_claim_uses_one_instant_for_expiry_and_takeover_decision(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "project"
            self.initialize(root)
            deliverable = "concept.problem_definition"
            code, _, error = self.invoke(
                [
                    "claim",
                    deliverable,
                    "--project-root",
                    str(root),
                    "--actor",
                    "agent-a",
                ]
            )
            self.assertEqual(code, 0, error)
            runtime_path = root / ".ipd" / "agent_runtime.yaml"
            runtime = load_state(runtime_path)
            instant = datetime(2026, 10, 2, 8, 0, 0, tzinfo=timezone.utc)
            runtime["active_claims"][deliverable]["started_at"] = (
                instant - timedelta(minutes=1)
            ).isoformat().replace("+00:00", "Z")
            runtime["active_claims"][deliverable]["expires_at"] = (
                instant + timedelta(seconds=1)
            ).isoformat().replace("+00:00", "Z")
            write_state(runtime_path, runtime)
            before = runtime_path.read_bytes()

            with patch("ipdctl.cli_v2.utc_now", return_value=instant), patch(
                "ipdctl.runtime.utc_now", return_value=instant + timedelta(seconds=2)
            ):
                code, _, error = self.invoke(
                    [
                        "claim",
                        deliverable,
                        "--project-root",
                        str(root),
                        "--actor",
                        "agent-b",
                    ]
                )
            self.assertEqual(code, 1)
            self.assertIn("agent-a", error)
            self.assertEqual(runtime_path.read_bytes(), before)

    def test_verify_records_baseline_and_project_validate_checks_bindings(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "project"
            self.initialize(root)
            self.assertEqual(self.invoke(["refresh", str(root)])[0], 0)
            code, output, error = self.invoke(["verify", str(root), "--json"])
            self.assertEqual(code, 0, error + output)
            runtime = load_state(root / ".ipd" / "agent_runtime.yaml")
            baseline = runtime["last_verification"]["artifact_baseline"]
            verify_event = next(
                item
                for item in reversed(runtime["events"])
                if item["action"] == "verify" and item["status"] == "passed"
            )
            self.assertEqual(verify_event["artifact_baseline"], baseline)

            bindings_path = root / ".ipd" / "artifact_bindings.yaml"
            bindings_path.unlink()
            self.assertEqual(self.invoke(["validate", str(root)])[0], 1)
            self.assertEqual(
                self.invoke(["validate", str(root / ".ipd" / "project_state.yaml")])[0],
                0,
            )

    def test_verify_rejects_and_repairs_tampered_manifest_contract_fields(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "project"
            self.initialize(root)
            self.assertEqual(self.invoke(["refresh", str(root)])[0], 0)
            self.assertEqual(self.invoke(["verify", str(root)])[0], 0)
            manifest_path = root / ".ipd" / "dashboard" / "manifest.json"
            original = json.loads(manifest_path.read_text(encoding="utf-8"))
            tampered = dict(original)
            tampered.update(
                {
                    "project": "forged-project",
                    "source_revision": -1,
                    "process_schema_version": "forged",
                    "output_directory": "elsewhere",
                    "files": ["forged.txt"],
                    "views": {"dashboard": "forged.html"},
                }
            )
            manifest_path.write_text(
                json.dumps(tampered, indent=2) + "\n", encoding="utf-8"
            )

            code, output, error = self.invoke(["verify", str(root), "--json"])
            self.assertEqual(code, 1, error)
            report = json.loads(output)
            mismatches = {
                issue["path"]
                for issue in report["issues"]
                if issue.get("code") == "dashboard_manifest_contract_mismatch"
            }
            self.assertEqual(
                mismatches,
                {
                    "$.dashboard.project",
                    "$.dashboard.source_revision",
                    "$.dashboard.process_schema_version",
                    "$.dashboard.output_directory",
                    "$.dashboard.files",
                    "$.dashboard.views",
                },
            )
            repaired = json.loads(manifest_path.read_text(encoding="utf-8"))
            for field in (
                "project",
                "source_revision",
                "process_schema_version",
                "output_directory",
                "files",
                "views",
            ):
                self.assertEqual(repaired[field], original[field])
            code, output, error = self.invoke(["verify", str(root), "--json"])
            self.assertEqual(code, 0, error + output)

    def test_dirty_iteration_baseline_keeps_immediate_second_verify_fresh(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "project"
            root.mkdir()
            subprocess.run(
                ["git", "init", "-b", "main"],
                cwd=root,
                check=True,
                capture_output=True,
            )
            subprocess.run(
                ["git", "config", "user.name", "IPD Test"], cwd=root, check=True
            )
            subprocess.run(
                ["git", "config", "user.email", "ipd-test@example.invalid"],
                cwd=root,
                check=True,
            )
            (root / "README.md").write_text("# test\n", encoding="utf-8")
            subprocess.run(["git", "add", "README.md"], cwd=root, check=True)
            subprocess.run(
                ["git", "commit", "-m", "baseline"],
                cwd=root,
                check=True,
                capture_output=True,
            )
            self.assertEqual(
                self.invoke(
                    [
                        "init",
                        str(root),
                        "--name",
                        "demo",
                        "--task-type",
                        "software",
                        "--task-type",
                        "robotics",
                    ]
                )[0],
                0,
            )
            self.assertEqual(self.invoke(["tailor", str(root)])[0], 0)
            deliverable = "concept.problem_definition"
            self.assertEqual(self.invoke(["refresh", str(root)])[0], 0)
            self.assertEqual(self.invoke(["verify", str(root)])[0], 0)
            self.assertEqual(
                self.invoke(
                    [
                        "claim",
                        deliverable,
                        "--project-root",
                        str(root),
                        "--actor",
                        "agent-a",
                    ]
                )[0],
                0,
            )
            work = root / "evidence" / deliverable / "work.md"
            review = root / "evidence" / deliverable / "approval.md"
            work.parent.mkdir(parents=True, exist_ok=True)
            work.write_text("work created after Claim\n", encoding="utf-8")
            review.write_text("authorized approval\n", encoding="utf-8")
            work_ref = work.relative_to(root).as_posix()
            review_ref = review.relative_to(root).as_posix()
            commands = (
                [
                    "close",
                    deliverable,
                    "--project-root",
                    str(root),
                    "--actor",
                    "agent-a",
                    "--evidence",
                    work_ref,
                ],
                [
                    "review",
                    deliverable,
                    "--project-root",
                    str(root),
                    "--reviewer",
                    "review-agent",
                ],
                [
                    "approve",
                    deliverable,
                    "--project-root",
                    str(root),
                    "--reviewer",
                    "design-authority",
                    "--actor-type",
                    "human",
                    "--authorized",
                    "--evidence",
                    review_ref,
                ],
                ["refresh", str(root)],
            )
            for command in commands:
                code, output, error = self.invoke(command)
                self.assertEqual(code, 0, output + error)

            first_code, first_output, first_error = self.invoke(
                ["verify", str(root), "--json"]
            )
            self.assertEqual(first_code, 0, first_error + first_output)
            second_code, second_output, second_error = self.invoke(
                ["verify", str(root), "--json"]
            )
            self.assertEqual(second_code, 0, second_error + second_output)
            self.assertEqual(json.loads(second_output)["status"], "passed")

            unclaimed = deliverable
            unclaimed_evidence = root / "evidence" / unclaimed / "unclaimed.md"
            unclaimed_evidence.parent.mkdir(parents=True, exist_ok=True)
            unclaimed_evidence.write_text(
                "change made without Claim\n", encoding="utf-8"
            )
            failed_code, failed_output, failed_error = self.invoke(
                ["verify", str(root), "--json"]
            )
            self.assertEqual(failed_code, 1, failed_error)
            failed = json.loads(failed_output)
            self.assertEqual(failed["status"], "failed")
            self.assertTrue(
                any(
                    "BINDING_UNCLAIMED_DELIVERABLE" in str(issue)
                    for issue in failed["issues"]
                )
            )
            code, output, error = self.invoke(["context", str(root), "--json"])
            self.assertEqual(code, 0, error)
            context = json.loads(output)
            self.assertFalse(context["claim_readiness"]["eligible"])
            self.assertEqual(context["available_tasks"], [])
            dashboard = json.loads(
                (root / ".ipd" / "dashboard" / "data" / "state.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertFalse(dashboard["claim_readiness"]["eligible"])
            self.assertEqual(dashboard["available_tasks"], [])
            self.assertEqual(
                self.invoke(
                    [
                        "claim",
                        unclaimed,
                        "--project-root",
                        str(root),
                        "--actor",
                        "agent-b",
                    ]
                )[0],
                1,
            )

    def test_expired_claim_recovery_inherits_original_binding_window(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "project"
            self.initialize(root)
            deliverable = "concept.problem_definition"
            self.assertEqual(self.invoke(["refresh", str(root)])[0], 0)
            self.assertEqual(self.invoke(["verify", str(root)])[0], 0)
            code, _, error = self.invoke(
                [
                    "claim",
                    deliverable,
                    "--project-root",
                    str(root),
                    "--actor",
                    "agent-a",
                ]
            )
            self.assertEqual(code, 0, error)
            evidence = root / "evidence" / deliverable / "recovered.md"
            evidence.parent.mkdir(parents=True, exist_ok=True)
            evidence.write_text(
                "work created under the original Claim\n", encoding="utf-8"
            )

            runtime_path = root / ".ipd" / "agent_runtime.yaml"
            runtime = load_state(runtime_path)
            first_claim = next(
                event
                for event in reversed(runtime["events"])
                if event.get("action") == "claim"
                and event.get("deliverable") == deliverable
            )
            runtime["active_claims"][deliverable]["started_at"] = (
                "1999-01-01T00:00:00Z"
            )
            runtime["active_claims"][deliverable]["expires_at"] = (
                "2000-01-01T00:00:00Z"
            )
            write_state(runtime_path, runtime)

            code, _, error = self.invoke(
                [
                    "claim",
                    deliverable,
                    "--project-root",
                    str(root),
                    "--actor",
                    "agent-b",
                ]
            )
            self.assertEqual(code, 0, error)
            recovered = load_state(runtime_path)
            claim_events = [
                event
                for event in recovered["events"]
                if event.get("action") == "claim"
                and event.get("deliverable") == deliverable
            ]
            self.assertEqual(len(claim_events), 2)
            self.assertEqual(
                claim_events[-1]["binding_window"], first_claim["binding_window"]
            )

            relative_evidence = evidence.relative_to(root).as_posix()
            code, _, error = self.invoke(
                [
                    "close",
                    deliverable,
                    "--project-root",
                    str(root),
                    "--actor",
                    "agent-b",
                    "--status",
                    "blocked",
                    "--note",
                    "exercise recovery provenance",
                    "--evidence",
                    relative_evidence,
                ]
            )
            self.assertEqual(code, 0, error)
            self.assertEqual(self.invoke(["refresh", str(root)])[0], 0)
            code, output, error = self.invoke(["verify", str(root), "--json"])
            self.assertEqual(code, 0, error + output)

    def test_legacy_expired_claim_requires_and_reuses_human_adoption_window(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "project"
            self.initialize(root)
            deliverable = "concept.problem_definition"
            code, _, error = self.invoke(
                [
                    "claim",
                    deliverable,
                    "--project-root",
                    str(root),
                    "--actor",
                    "legacy-agent",
                ]
            )
            self.assertEqual(code, 0, error)
            runtime_path = root / ".ipd" / "agent_runtime.yaml"
            runtime = load_state(runtime_path)
            legacy_claim = next(
                event
                for event in runtime["events"]
                if event.get("action") == "claim"
                and event.get("deliverable") == deliverable
            )
            legacy_claim.pop("binding_window")
            runtime["active_claims"][deliverable]["started_at"] = (
                "1999-01-01T00:00:00Z"
            )
            runtime["active_claims"][deliverable]["expires_at"] = (
                "2000-01-01T00:00:00Z"
            )
            write_state(runtime_path, runtime)

            self.assertEqual(self.invoke(["context", str(root)])[0], 0)
            recovery_args = [
                "claim",
                deliverable,
                "--project-root",
                str(root),
                "--actor",
                "migration-agent",
                "--recover",
            ]
            self.assertEqual(self.invoke(recovery_args)[0], 1)

            code, output, error = self.invoke(
                [
                    "adopt-baseline",
                    str(root),
                    "--actor",
                    "release-owner",
                    "--actor-type",
                    "human",
                    "--authorized",
                    "--reason",
                    "Authorize the reviewed legacy Claim migration boundary",
                    "--json",
                ]
            )
            self.assertEqual(code, 0, error)
            stale_adoption = json.loads(output)["artifact_baseline"]

            bindings_path = root / ".ipd" / "artifact_bindings.yaml"
            bindings = load_state(bindings_path)
            bindings["description"] = "Reviewed migration binding boundary S2"
            write_state(bindings_path, bindings)
            self.assertEqual(self.invoke(recovery_args)[0], 1)
            code, output, error = self.invoke(
                [
                    "adopt-baseline",
                    str(root),
                    "--actor",
                    "release-owner",
                    "--actor-type",
                    "human",
                    "--authorized",
                    "--reason",
                    "Replace stale S1 with the reviewed current S2 boundary",
                    "--json",
                ]
            )
            self.assertEqual(code, 0, error)
            adopted = json.loads(output)["artifact_baseline"]
            self.assertNotEqual(
                stale_adoption["baseline_id"], adopted["baseline_id"]
            )
            code, _, error = self.invoke(recovery_args)
            self.assertEqual(code, 0, error)
            recovered = load_state(runtime_path)
            claims = [
                event
                for event in recovered["events"]
                if event.get("action") == "claim"
                and event.get("deliverable") == deliverable
            ]
            self.assertEqual(len(claims), 2)
            migration_window = claims[-1]["binding_window"]
            self.assertEqual(migration_window["baseline_id"], adopted["baseline_id"])
            self.assertEqual(migration_window["opened_paths"], adopted["paths"])

            recovered["active_claims"][deliverable]["started_at"] = (
                "1999-01-01T00:00:00Z"
            )
            recovered["active_claims"][deliverable]["expires_at"] = (
                "2000-01-01T00:00:00Z"
            )
            write_state(runtime_path, recovered)
            self.assertEqual(self.invoke(["context", str(root)])[0], 0)
            recovery_args[5] = "successor-agent"
            code, _, error = self.invoke(recovery_args)
            self.assertEqual(code, 0, error)
            twice_recovered = load_state(runtime_path)
            claims = [
                event
                for event in twice_recovered["events"]
                if event.get("action") == "claim"
                and event.get("deliverable") == deliverable
            ]
            self.assertEqual(len(claims), 3)
            self.assertEqual(claims[-1]["binding_window"], migration_window)
            adoptions = [
                event
                for event in twice_recovered["events"]
                if event.get("action") == "artifact_baseline_adopted"
            ]
            self.assertEqual(len(adoptions), 2)

    def test_rejected_work_is_not_advertised_until_refresh_and_verify(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "project"
            self.initialize(root)
            deliverable = "concept.problem_definition"
            self.assertEqual(self.invoke(["refresh", str(root)])[0], 0)
            self.assertEqual(self.invoke(["verify", str(root)])[0], 0)

            work = root / "evidence" / deliverable / "work.md"
            review = root / "evidence" / deliverable / "reject.md"
            work.parent.mkdir(parents=True, exist_ok=True)
            work.write_text("completed attempt\n", encoding="utf-8")
            review.write_text("authorized rejection\n", encoding="utf-8")
            work_ref = work.relative_to(root).as_posix()
            review_ref = review.relative_to(root).as_posix()
            commands = (
                [
                    "claim",
                    deliverable,
                    "--project-root",
                    str(root),
                    "--actor",
                    "agent-a",
                ],
                [
                    "close",
                    deliverable,
                    "--project-root",
                    str(root),
                    "--actor",
                    "agent-a",
                    "--evidence",
                    work_ref,
                ],
                [
                    "review",
                    deliverable,
                    "--project-root",
                    str(root),
                    "--reviewer",
                    "review-agent",
                ],
                [
                    "reject",
                    deliverable,
                    "--project-root",
                    str(root),
                    "--reviewer",
                    "design-authority",
                    "--actor-type",
                    "human",
                    "--authorized",
                    "--evidence",
                    review_ref,
                ],
            )
            for command in commands:
                code, output, error = self.invoke(command)
                self.assertEqual(code, 0, output + error)

            code, output, error = self.invoke(["context", str(root), "--json"])
            self.assertEqual(code, 0, error)
            context = json.loads(output)
            self.assertFalse(context["claim_readiness"]["eligible"])
            self.assertEqual(context["available_tasks"], [])
            self.assertEqual(
                self.invoke(
                    [
                        "claim",
                        deliverable,
                        "--project-root",
                        str(root),
                        "--actor",
                        "agent-b",
                    ]
                )[0],
                1,
            )

            self.assertEqual(self.invoke(["refresh", str(root)])[0], 0)
            dashboard_path = root / ".ipd" / "dashboard" / "data" / "state.json"
            dashboard = json.loads(dashboard_path.read_text(encoding="utf-8"))
            self.assertFalse(dashboard["claim_readiness"]["eligible"])
            self.assertEqual(dashboard["available_tasks"], [])

            code, output, error = self.invoke(["verify", str(root), "--json"])
            self.assertEqual(code, 0, error + output)
            code, output, error = self.invoke(["context", str(root), "--json"])
            self.assertEqual(code, 0, error)
            context = json.loads(output)
            self.assertTrue(context["claim_readiness"]["eligible"])
            self.assertIn(
                deliverable, {item["id"] for item in context["available_tasks"]}
            )
            dashboard = json.loads(dashboard_path.read_text(encoding="utf-8"))
            self.assertTrue(dashboard["claim_readiness"]["eligible"])
            self.assertIn(
                deliverable, {item["id"] for item in dashboard["available_tasks"]}
            )
            code, _, error = self.invoke(
                [
                    "claim",
                    deliverable,
                    "--project-root",
                    str(root),
                    "--actor",
                    "agent-b",
                ]
            )
            self.assertEqual(code, 0, error)


if __name__ == "__main__":
    unittest.main()
