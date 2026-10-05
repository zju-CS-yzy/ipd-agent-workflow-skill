from __future__ import annotations

import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from ipdctl.cli import main
from ipdctl.state import create_initial_state, load_state, write_state


class ValidateJsonContractTests(unittest.TestCase):
    def invoke(self, arguments: list[str]) -> tuple[int, str, str]:
        stdout = io.StringIO()
        stderr = io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            code = main(arguments)
        return code, stdout.getvalue(), stderr.getvalue()

    def test_valid_project_emits_one_machine_readable_report(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "project"
            code, output, error = self.invoke(
                ["init", str(root), "--name", "validate-json", "--locale", "zh-CN"]
            )
            self.assertEqual(code, 0, output + error)

            code, output, error = self.invoke(["validate", str(root), "--json"])
            self.assertEqual(code, 0, output + error)
            self.assertEqual(error, "")
            report = json.loads(output)
            self.assertEqual(report["schema_version"], "1.0")
            self.assertEqual(report["command"], "validate")
            self.assertEqual(report["status"], "passed")
            self.assertEqual(report["locale"], "zh-CN")
            self.assertEqual(report["scope"], "project")
            self.assertEqual(report["checks"]["state"], "passed")
            self.assertEqual(report["checks"]["bindings"], "passed")
            self.assertEqual(report["issues"], [])

    def test_invalid_state_is_structured_and_keeps_machine_fields_english(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "project"
            self.assertEqual(
                self.invoke(
                    ["init", str(root), "--name", "中文项目", "--locale", "zh-CN"]
                )[0],
                0,
            )
            state_path = root / ".ipd" / "project_state.yaml"
            state = load_state(state_path)
            state["project"]["phase"] = "not-a-phase"
            write_state(state_path, state)

            code, output, error = self.invoke(["validate", str(root), "--json"])
            self.assertEqual(code, 1)
            self.assertEqual(error, "")
            report = json.loads(output)
            self.assertEqual(report["status"], "failed")
            self.assertEqual(report["checks"]["state"], "failed")
            self.assertTrue(report["issues"])
            self.assertTrue(
                all(issue["severity"] == "error" for issue in report["issues"])
            )
            self.assertIn("STATE_VALIDATION_ERROR", {i["code"] for i in report["issues"]})

    def test_unreadable_state_and_invalid_policy_remain_json(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            state_path = root / "broken.yaml"
            state_path.write_text("project: [\n", encoding="utf-8")
            policy_path = root / "policy.json"
            policy_path.write_text("{}\n", encoding="utf-8")

            code, output, error = self.invoke(
                [
                    "validate",
                    str(state_path),
                    "--policy",
                    str(policy_path),
                    "--json",
                ]
            )
            self.assertEqual(code, 1)
            self.assertEqual(error, "")
            report = json.loads(output)
            self.assertEqual(report["scope"], "state")
            self.assertEqual(report["checks"]["state"], "failed")
            self.assertEqual(report["checks"]["policy"], "failed")
            self.assertEqual(report["checks"]["bindings"], "not_applicable")
            self.assertEqual(
                {issue["code"] for issue in report["issues"]},
                {"STATE_INPUT_INVALID", "POLICY_INVALID"},
            )

    def test_state_file_scope_does_not_require_project_bindings(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state_path = Path(directory) / "state.yaml"
            write_state(state_path, create_initial_state("standalone"))
            code, output, error = self.invoke(
                ["validate", str(state_path), "--json"]
            )
            self.assertEqual(code, 0, output + error)
            report = json.loads(output)
            self.assertEqual(report["scope"], "state")
            self.assertEqual(report["checks"]["bindings"], "not_applicable")


class CliUtf8ContractTests(unittest.TestCase):
    def test_console_script_reconfigures_stdout_and_stderr_to_utf8(self) -> None:
        environment = dict(os.environ)
        environment["PYTHONIOENCODING"] = "cp1252"
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "ipdctl",
                "init",
                "--locale",
                "zh-CN",
                "--help",
            ],
            cwd=Path(__file__).resolve().parents[1],
            env=environment,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        stdout = result.stdout.decode("utf-8", errors="strict")
        stderr = result.stderr.decode("utf-8", errors="strict")
        self.assertEqual(result.returncode, 0, stderr)
        self.assertIn("创建 IPD 项目工作区", stdout)
        self.assertEqual(stderr, "")

        invalid = subprocess.run(
            [
                sys.executable,
                "-m",
                "ipdctl",
                "init",
                "--locale",
                "zh-CN",
                "--unknown-option",
            ],
            cwd=Path(__file__).resolve().parents[1],
            env=environment,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        self.assertEqual(invalid.returncode, 2)
        decoded_error = invalid.stderr.decode("utf-8", errors="strict")
        self.assertIn("错误", decoded_error)


if __name__ == "__main__":
    unittest.main()
