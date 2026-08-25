"""Tests for safe, actionable report-generation diagnostics."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE / "scripts"))

from report_diagnostics import diagnostic, write_diagnostics  # noqa: E402


class ReportDiagnosticsTests(unittest.TestCase):
    def test_scope_mismatch_diagnostic_is_chinese_actionable_and_secret_safe(self) -> None:
        """Provider scope failures must explain impact without leaking collection credentials."""
        record = diagnostic(
            "DATAFORSEO_ARCHIVE_SCOPE_MISMATCH",
            stage="extension_validation",
            scope={"domain": "example.com", "report": "quarterly/2026-06_to_2026-08"},
            detected={"archive_month": "2026-05", "authorization": "Bearer should-not-appear", "token": "secret"},
            impact="已隐藏 DataForSEO 市场机会模块；GSC/GA4 官方指标未改变。",
            next_action="核对域名、报告期、市场和语言后导入匹配归档。",
            status="warning",
        )
        self.assertEqual(record["code"], "DATAFORSEO_ARCHIVE_SCOPE_MISMATCH")
        self.assertEqual(record["write_state"], {"archives": "unchanged", "report": "unchanged", "publish": "not_started"})
        self.assertNotIn("should-not-appear", json.dumps(record, ensure_ascii=False))
        self.assertNotIn("secret", json.dumps(record, ensure_ascii=False))
        self.assertIn("问题位置", record["user_message"])
        self.assertIn("下一步", record["user_message"])

    def test_diagnostics_are_written_outside_public_dashboard_directory(self) -> None:
        """Generation diagnostics belong in an internal directory, never in a Pages report path."""
        record = diagnostic(
            "PREVIOUS_PERIOD_ARCHIVE_MISSING",
            stage="archive_validation",
            scope={"domain": "example.com"}, detected={"missing_months": ["2026-03"]},
            impact="不生成未经验证的对比。", next_action="补齐同域官方归档。", status="warning",
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            destination = write_diagnostics(root / "internal-diagnostics", [record])
            self.assertTrue((destination / "diagnostic.json").exists())
            self.assertTrue((destination / "diagnostic.md").exists())
            self.assertNotIn("dashboards", str(destination))


if __name__ == "__main__":
    unittest.main()
