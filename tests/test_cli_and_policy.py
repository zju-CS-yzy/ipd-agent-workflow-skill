from __future__ import annotations

import io
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from ipdctl.cli import main
from ipdctl.policy import PolicyError, load_policy, validate_policy
from ipdctl.repository import inspect_repository


ROOT = Path(__file__).resolve().parents[1]


class CliAndPolicyTests(unittest.TestCase):
    def test_cli_init_validate_and_status(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = io.StringIO()
            with redirect_stdout(output):
                self.assertEqual(main(["init", directory, "--name", "demo"]), 0)
                self.assertEqual(main(["validate", directory]), 0)
                self.assertEqual(main(["status", directory, "--json"]), 0)
            self.assertTrue((Path(directory) / ".ipd" / "project_state.yaml").is_file())
            self.assertIn('"workflow_step": "context"', output.getvalue())

    def test_cli_does_not_overwrite_without_force(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                self.assertEqual(main(["init", directory, "--name", "demo"]), 0)
                self.assertEqual(main(["init", directory, "--name", "demo"]), 1)

    def test_default_policy_loads(self) -> None:
        policy = load_policy(ROOT / "policies" / "default" / "tailoring_rules.yaml")
        self.assertEqual(policy["version"], 1)
        self.assertEqual(validate_policy(policy), [])

    def test_non_negotiable_policy_cannot_be_disabled(self) -> None:
        policy = load_policy(ROOT / "policies" / "default" / "tailoring_rules.yaml")
        policy["defaults"]["preserve_traceability"] = False
        self.assertTrue(any("cannot be tailored out" in item for item in validate_policy(policy)))
        with self.assertRaises(PolicyError):
            load_policy(ROOT / "does-not-exist.yaml")

    def test_repository_detection_degrades_to_none(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            info = inspect_repository(directory)
        self.assertEqual(info.kind, "none")
        self.assertIsNone(info.revision)


if __name__ == "__main__":
    unittest.main()
