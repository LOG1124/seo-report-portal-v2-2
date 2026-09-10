"""Offline tests for importing immutable legacy Google archives."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE / "scripts"))

from import_google_archive import main  # noqa: E402
from customer_registry import CustomerRecord, google_archive_path  # noqa: E402


def write_registry(root: Path) -> None:
    (root / "customer-registry.json").write_text(json.dumps({"customers": [{
        "canonical_domain": "example.com", "portal_slug": "example-com", "status": "active",
    }]}), encoding="utf-8")


def source_payload(**changes: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "domain": "example.com",
        "period": ["2026-07-01", "2026-07-31"],
        "ga4": {"session_count": 1},
        "gsc": {"organic_clicks": 1},
    }
    payload.update(changes)
    return payload


class GoogleArchiveImportTest(unittest.TestCase):
    def run_import(self, root: Path, source: Path, month: str = "2026-07") -> int:
        with patch.object(sys, "argv", [
            "import_google_archive.py", "--archive-root", str(root), "--source-file", str(source), "--month", month,
        ]):
            return main()

    def write_source(self, root: Path, payload: dict[str, object]) -> tuple[Path, bytes]:
        source = root / "legacy.json"
        content = (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        source.write_bytes(content)
        return source, content

    def test_valid_import_preserves_original_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "archive"
            root.mkdir()
            write_registry(root)
            source, content = self.write_source(root, source_payload())
            self.assertEqual(self.run_import(root, source), 0)
            self.assertEqual((root / "ga4-gsc" / "example.com" / "2026-07.json").read_bytes(), content)

    def test_existing_target_is_unchanged(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "archive"
            root.mkdir()
            write_registry(root)
            source, content = self.write_source(root, source_payload())
            target = root / "ga4-gsc" / "example.com" / "2026-07.json"
            target.parent.mkdir(parents=True)
            target.write_bytes(b'{"original":true}\n')
            with self.assertRaisesRegex(FileExistsError, "档案已存在，未改写"):
                self.run_import(root, source)
            self.assertEqual(target.read_bytes(), b'{"original":true}\n')
            self.assertEqual(source.read_bytes(), content)

    def test_partial_or_mismatched_source_is_rejected_without_archive(self) -> None:
        cases = (
            source_payload(ga4={}),
            source_payload(domain="other.example"),
            source_payload(period=["2026-07-02", "2026-07-31"]),
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "archive"
            root.mkdir()
            write_registry(root)
            for index, payload in enumerate(cases):
                source, _ = self.write_source(root, payload)
                with self.subTest(index=index), self.assertRaises(ValueError):
                    self.run_import(root, source)
            self.assertFalse((root / "ga4-gsc").exists())

    def test_windows_unc_root_string_is_not_rewritten(self) -> None:
        root = Path(r"\\server\共享盘\seo-report-source-archive")
        path = google_archive_path(root, CustomerRecord("example.com", "example-com", "active"), "2026-07")
        self.assertEqual(str(path), r"\\server\共享盘\seo-report-source-archive/ga4-gsc/example.com/2026-07.json")


if __name__ == "__main__":
    unittest.main()
