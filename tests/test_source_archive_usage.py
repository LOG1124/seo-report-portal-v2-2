"""Tests for local, non-public Google source provenance records."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE / "scripts"))

from customer_registry import CustomerRecord  # noqa: E402
from source_archive_usage import USAGE_FILE, sha256, verify_usage, write_usage  # noqa: E402


class SourceArchiveUsageTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "archive-root"
        self.record = CustomerRecord("example.com", "example-com", "active")
        self.report_dir = Path(self.tmp.name) / "report"
        self.report_dir.mkdir()

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def archive(self, month: str, domain: str = "example.com") -> Path:
        path = self.root / "ga4-gsc" / "example.com" / f"{month}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"domain": domain, "period": [f"{month}-01", f"{month}-30"]}), encoding="utf-8")
        return path

    def other_customer_archive(self, month: str) -> Path:
        path = self.root / "ga4-gsc" / "other.example" / f"{month}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"domain": "other.example", "period": [f"{month}-01", f"{month}-30"]}), encoding="utf-8")
        return path

    def write_complete_usage(self) -> Path:
        return write_usage(
            self.report_dir, self.root, self.record, "monthly", "2026-06",
            [self.archive("2026-06")], [self.archive("2026-05")], "complete",
        )

    def test_writes_relative_hashes_and_verifies_complete_usage(self) -> None:
        """Changing a source path to an absolute workstation path must not be necessary to verify it."""
        self.write_complete_usage()
        payload = verify_usage(self.report_dir, self.root, self.record, "monthly", "2026-06", False)
        self.assertEqual([item["role"] for item in payload["archives"]], ["current", "previous"])
        self.assertTrue(all(not Path(item["relative_path"]).is_absolute() for item in payload["archives"]))

    def test_rejects_traversal_identity_and_source_changes(self) -> None:
        """Tampering with report identity, source path, or bytes must fail release verification."""
        self.write_complete_usage()
        usage_path = self.report_dir / USAGE_FILE
        payload = json.loads(usage_path.read_text(encoding="utf-8"))
        payload["archives"][0]["relative_path"] = "../outside.json"
        usage_path.write_text(json.dumps(payload), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "根目录外"):
            verify_usage(self.report_dir, self.root, self.record, "monthly", "2026-06", False)

        self.write_complete_usage()
        payload = json.loads(usage_path.read_text(encoding="utf-8"))
        payload["portal_slug"] = "wrong-slug"
        usage_path.write_text(json.dumps(payload), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "身份不一致"):
            verify_usage(self.report_dir, self.root, self.record, "monthly", "2026-06", False)

        self.write_complete_usage()
        self.archive("2026-06").write_text('{"domain":"example.com","changed":true}', encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "SHA-256 不一致"):
            verify_usage(self.report_dir, self.root, self.record, "monthly", "2026-06", False)

    def test_rejects_valid_other_customer_archive_path(self) -> None:
        """A readable archive under another customer's directory cannot be a report source."""
        self.write_complete_usage()
        usage_path = self.report_dir / USAGE_FILE
        payload = json.loads(usage_path.read_text(encoding="utf-8"))
        other = self.other_customer_archive("2026-06")
        payload["archives"][0]["relative_path"] = str(other.relative_to(self.root))
        payload["archives"][0]["sha256"] = sha256(other)
        usage_path.write_text(json.dumps(payload), encoding="utf-8")

        with self.assertRaisesRegex(ValueError, "其他客户"):
            verify_usage(self.report_dir, self.root, self.record, "monthly", "2026-06", False)

    def test_rejects_removed_current_customer_archive(self) -> None:
        """A once-valid current-customer path cannot verify after its archive is removed."""
        self.write_complete_usage()
        self.archive("2026-06").unlink()

        with self.assertRaisesRegex(ValueError, "SHA-256 不一致"):
            verify_usage(self.report_dir, self.root, self.record, "monthly", "2026-06", False)

    def test_rejects_missing_current_or_previous_and_unapproved_exception(self) -> None:
        """A usage record cannot claim a complete comparison without both roles or bypass approval."""
        self.write_complete_usage()
        usage_path = self.report_dir / USAGE_FILE
        payload = json.loads(usage_path.read_text(encoding="utf-8"))
        payload["archives"] = [item for item in payload["archives"] if item["role"] != "current"]
        usage_path.write_text(json.dumps(payload), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "缺少当期"):
            verify_usage(self.report_dir, self.root, self.record, "monthly", "2026-06", False)

        self.write_complete_usage()
        payload = json.loads(usage_path.read_text(encoding="utf-8"))
        payload["archives"] = [item for item in payload["archives"] if item["role"] != "previous"]
        usage_path.write_text(json.dumps(payload), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "缺少对比期"):
            verify_usage(self.report_dir, self.root, self.record, "monthly", "2026-06", False)

        write_usage(
            self.report_dir, self.root, self.record, "monthly", "2026-06",
            [self.archive("2026-06")], [], "current_only_exception",
        )
        with self.assertRaisesRegex(ValueError, "必须显式允许"):
            verify_usage(self.report_dir, self.root, self.record, "monthly", "2026-06", False)


if __name__ == "__main__":
    unittest.main()
