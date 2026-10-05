from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from ipdctl.cli import main
from ipdctl.i18n import (
    DEFAULT_LOCALE,
    LocaleError,
    MessageFormatError,
    SUPPORTED_LOCALES,
    catalog_keys,
    get_translator,
    load_project_locale,
    localized_exception_message,
    locale_from_profile,
    normalize_locale,
)
from ipdctl.transaction import ProjectTransactionError
from ipdctl.state import load_state, write_state


class I18nTests(unittest.TestCase):
    def invoke(self, arguments: list[str]) -> tuple[int, str, str]:
        stdout = io.StringIO()
        stderr = io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            result = main(arguments)
        return result, stdout.getvalue(), stderr.getvalue()

    def test_supported_locales_and_catalog_keys_are_stable(self) -> None:
        self.assertEqual(DEFAULT_LOCALE, "en")
        self.assertEqual(SUPPORTED_LOCALES, ("en", "zh-CN"))
        self.assertEqual(catalog_keys("en"), catalog_keys("zh-CN"))
        self.assertIn("cli.init.completed", catalog_keys())
        self.assertIn("dashboard.current_phase", catalog_keys())

    def test_locale_normalization_is_strict(self) -> None:
        self.assertEqual(normalize_locale("en"), "en")
        self.assertEqual(normalize_locale(" zh-CN "), "zh-CN")
        for value in ("zh", "zh_CN", "EN", "", None):
            with self.subTest(value=value), self.assertRaises(LocaleError):
                normalize_locale(value)

    def test_legacy_profile_defaults_to_english(self) -> None:
        self.assertEqual(locale_from_profile({"schema_version": "1.0"}), "en")
        self.assertEqual(
            locale_from_profile(
                {"schema_version": "1.0", "presentation": {"locale": "zh-CN"}}
            ),
            "zh-CN",
        )

    def test_invalid_profile_locale_fails_instead_of_falling_back(self) -> None:
        with self.assertRaises(LocaleError):
            locale_from_profile({"presentation": {"locale": "fr"}})
        with self.assertRaises(LocaleError):
            locale_from_profile({"presentation": "zh-CN"})

    def test_missing_profile_uses_english_and_invalid_yaml_fails(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.assertEqual(load_project_locale(root), "en")
            (root / ".ipd").mkdir()
            (root / ".ipd" / "task_profile.yaml").write_text(
                "presentation: [\n", encoding="utf-8"
            )
            with self.assertRaises(LocaleError):
                load_project_locale(root)

    def test_translator_is_project_scoped_and_formatting_is_checked(self) -> None:
        english = get_translator("en")
        chinese = get_translator("zh-CN")
        self.assertEqual(english.locale, "en")
        self.assertEqual(chinese.locale, "zh-CN")
        self.assertEqual(english.text("status.planned"), "Planned")
        self.assertEqual(chinese.text("status.planned"), "已规划")
        self.assertEqual(chinese.text("unknown.message.key"), "unknown.message.key")
        with self.assertRaises(MessageFormatError):
            chinese.text("cli.context.project")

    def test_transaction_errors_are_localized_without_changing_technical_values(self) -> None:
        chinese = get_translator("zh-CN")
        active = ProjectTransactionError(
            "project transaction is still active in process 4312"
        )
        concurrent = ProjectTransactionError(
            "another project transaction started concurrently"
        )
        rollback = ProjectTransactionError(
            "project rollback failed after RuntimeError: injected failure"
        )
        unknown_owner = ProjectTransactionError(
            "cannot determine whether project transaction owner process 4312 is active"
        )

        self.assertEqual(
            localized_exception_message(active, chinese),
            "项目事务仍由进程 4312 执行",
        )
        self.assertEqual(
            localized_exception_message(concurrent, chinese),
            "另一个项目事务已并发启动；请重试该命令",
        )
        self.assertEqual(
            localized_exception_message(rollback, chinese),
            "项目事务在 RuntimeError 后回滚失败：injected failure",
        )
        self.assertEqual(
            localized_exception_message(unknown_owner, chinese),
            "无法确定项目事务所属进程 4312 是否仍在运行；请确认没有 ipdctl 命令在执行后重试",
        )

    def test_process_migration_errors_are_localized_without_changing_ids(self) -> None:
        chinese = get_translator("zh-CN")
        cases = (
            (
                "re-tailoring requires explicit --apply-migrations for historical "
                "deliverables: old.requirements",
                "历史交付件迁移需要显式提供 --apply-migrations：old.requirements",
            ),
            (
                "re-tailoring would remove unmapped historical deliverables: "
                "old.architecture",
                "重新裁剪将移除未映射的历史交付件：old.architecture",
            ),
            (
                "state-only superseded history has invalid replacements or trace "
                "links: old.design",
                "已取代历史节点的替代目标无效：old.design",
            ),
        )
        for source, expected in cases:
            with self.subTest(source=source):
                self.assertEqual(
                    localized_exception_message(RuntimeError(source), chinese),
                    expected,
                )

    def test_init_writes_locale_and_localizes_output(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "project"
            code, output, error = self.invoke(
                ["init", str(root), "--name", "演示", "--locale", "zh-CN"]
            )
            self.assertEqual(code, 0, error)
            self.assertIn("已初始化 IPD 项目", output)
            profile = load_state(root / ".ipd" / "task_profile.yaml")
            self.assertEqual(profile["presentation"]["locale"], "zh-CN")

    def test_init_defaults_to_english_locale(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "project"
            code, output, error = self.invoke(["init", str(root), "--name", "demo"])
            self.assertEqual(code, 0, error)
            self.assertIn("Initialized IPD project", output)
            profile = load_state(root / ".ipd" / "task_profile.yaml")
            self.assertEqual(profile["presentation"]["locale"], "en")

    def test_invalid_init_locale_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            code, _, error = self.invoke(
                ["init", directory, "--name", "demo", "--locale", "fr"]
            )
            self.assertEqual(code, 1)
            self.assertIn("unsupported locale", error)
            self.assertFalse((Path(directory) / ".ipd").exists())

    def test_legacy_project_without_presentation_remains_english(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "project"
            self.assertEqual(self.invoke(["init", str(root), "--name", "demo"])[0], 0)
            profile_path = root / ".ipd" / "task_profile.yaml"
            profile = load_state(profile_path)
            profile.pop("presentation")
            write_state(profile_path, profile)
            code, output, error = self.invoke(["context", str(root)])
            self.assertEqual(code, 0, error)
            self.assertIn("Project: demo", output)
            self.assertNotIn("项目：", output)

    def test_json_output_keeps_machine_contract_in_english(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "project"
            self.assertEqual(
                self.invoke(
                    ["init", str(root), "--name", "演示", "--locale", "zh-CN"]
                )[0],
                0,
            )
            code, output, error = self.invoke(["context", str(root), "--json"])
            self.assertEqual(code, 0, error)
            value = json.loads(output)
            self.assertEqual(value["phase"], "concept")
            self.assertEqual(value["workflow_step"], "context")
            self.assertIn("available_tasks", value)

    def test_init_help_can_be_selected_in_chinese_before_project_exists(self) -> None:
        stdout = io.StringIO()
        with self.assertRaises(SystemExit) as raised, redirect_stdout(stdout):
            main(["init", "--locale", "zh-CN", "--help"])
        self.assertEqual(raised.exception.code, 0)
        self.assertIn("创建 IPD 项目工作区", stdout.getvalue())
        self.assertIn("显示语言", stdout.getvalue())

    def test_locale_change_makes_dashboard_stale_until_refresh(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "project"
            self.assertEqual(self.invoke(["init", str(root), "--name", "demo"])[0], 0)
            self.assertEqual(self.invoke(["tailor", str(root)])[0], 0)
            self.assertEqual(self.invoke(["refresh", str(root)])[0], 0)
            self.assertEqual(self.invoke(["verify", str(root), "--json"])[0], 0)

            profile_path = root / ".ipd" / "task_profile.yaml"
            profile = load_state(profile_path)
            profile["presentation"]["locale"] = "zh-CN"
            write_state(profile_path, profile)

            code, output, error = self.invoke(["verify", str(root), "--json"])
            self.assertEqual(code, 1, error)
            report = json.loads(output)
            self.assertEqual(report["locale"], "zh-CN")
            self.assertIn(
                "dashboard_locale_stale",
                {issue.get("code") for issue in report["issues"]},
            )

            self.assertEqual(self.invoke(["refresh", str(root)])[0], 0)
            code, output, error = self.invoke(["verify", str(root), "--json"])
            self.assertEqual(code, 0, (output, error))
            self.assertEqual(json.loads(output)["locale"], "zh-CN")


if __name__ == "__main__":
    unittest.main()
