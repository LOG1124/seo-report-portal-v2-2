import json
import io
import hashlib
import os
import socket
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from contextlib import redirect_stderr
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE / "scripts"))

import google_api_collector  # noqa: E402
from google_api_collector import main, read_ready_complete_month_archive, save_new_month_archive  # noqa: E402


def write_registry(root: Path, domain: str, slug: str) -> None:
    (root / "customer-registry.json").write_text(
        json.dumps(
            {
                "customers": [
                    {
                        "canonical_domain": domain,
                        "portal_slug": slug,
                        "status": "active",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )


class GoogleArchiveStorageTest(unittest.TestCase):
    def test_ready_reader_binds_one_complete_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_registry(root, "example.com", "example-com")
            original = {
                "domain": "example.com", "period": ["2026-07-01", "2026-07-31"],
                "ga4": {"session_count": 1}, "gsc": {"organic_clicks": 1},
            }
            path = save_new_month_archive(root, "example.com", "2026-07", original)
            snapshot = read_ready_complete_month_archive(root, "example.com", "2026-07")
            replacement = {**original, "ga4": {"session_count": 99}}
            content = json.dumps(replacement).encode("utf-8")
            path.write_bytes(content)
            path.with_suffix(".json.ready").write_text(
                json.dumps({"sha256": hashlib.sha256(content).hexdigest()}), encoding="utf-8"
            )
            self.assertEqual(snapshot.payload["ga4"]["session_count"], 1)
            self.assertEqual(snapshot.sha256, hashlib.sha256(snapshot.content).hexdigest())

    def test_existing_month_preserves_original_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_registry(root, "example.com", "example-com")
            payload = {
                "domain": "example.com",
                "period": ["2026-07-01", "2026-07-31"],
                "ga4": {"session_count": 1},
                "gsc": {"organic_clicks": 1},
            }

            path = save_new_month_archive(root, "example.com", "2026-07", payload)
            original = path.read_bytes()

            with self.assertRaisesRegex(FileExistsError, "档案已存在，未改写"):
                save_new_month_archive(root, "example.com", "2026-07", {**payload, "ga4": {"changed": True}})

            self.assertEqual(path, root / "ga4-gsc" / "example.com" / "2026-07.json")
            self.assertEqual(path.read_bytes(), original)
            self.assertEqual(
                json.loads(path.with_suffix(".json.ready").read_text(encoding="utf-8")),
                {"sha256": hashlib.sha256(original).hexdigest()},
            )

    def test_final_path_created_after_check_is_not_replaced(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_registry(root, "example.com", "example-com")
            archive_path = root / "ga4-gsc" / "example.com" / "2026-07.json"
            original = b'{"written_by":"another_writer"}\n'
            original_write = google_api_collector._exclusive_write

            def create_final_before_write(destination, content, *args, **kwargs):
                if Path(destination) == archive_path:
                    archive_path.write_bytes(original)
                    archive_path.with_suffix(".json.ready").write_text(
                        json.dumps({"sha256": hashlib.sha256(original).hexdigest()}), encoding="utf-8"
                    )
                return original_write(destination, content, *args, **kwargs)

            payload = {
                "domain": "example.com",
                "period": ["2026-07-01", "2026-07-31"],
                "ga4": {"session_count": 1},
                "gsc": {"organic_clicks": 1},
            }
            with patch.object(google_api_collector, "_exclusive_write", new=create_final_before_write):
                with self.assertRaisesRegex(FileExistsError, "档案已存在，未改写"):
                    save_new_month_archive(root, "example.com", "2026-07", payload)

            self.assertEqual(archive_path.read_bytes(), original)
            self.assertFalse(list(archive_path.parent.glob("*.tmp")))
            self.assertFalse(archive_path.with_suffix(".json.lock").exists())

    def test_failed_safe_commit_leaves_no_partial_target(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_registry(root, "example.com", "example-com")
            archive_path = root / "ga4-gsc" / "example.com" / "2026-07.json"
            original_write = google_api_collector._exclusive_write

            def fail_final_write(destination, content, *args, **kwargs):
                if Path(destination) == archive_path:
                    raise OSError("simulated SMB failure")
                return original_write(destination, content, *args, **kwargs)

            payload = {
                "domain": "example.com",
                "period": ["2026-07-01", "2026-07-31"],
                "ga4": {"session_count": 1},
                "gsc": {"organic_clicks": 1},
            }
            with patch.object(google_api_collector, "_exclusive_write", new=fail_final_write):
                with self.assertRaisesRegex(OSError, "simulated SMB failure"):
                    save_new_month_archive(root, "example.com", "2026-07", payload)

            self.assertFalse(archive_path.exists())
            self.assertFalse(archive_path.with_suffix(".json.lock").exists())
            self.assertFalse(list(archive_path.parent.glob("*.tmp")))

    def test_partial_json_write_keeps_lock_and_never_creates_ready_marker(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_registry(root, "example.com", "example-com")
            archive_path = root / "ga4-gsc" / "example.com" / "2026-07.json"
            original_write = google_api_collector._exclusive_write

            def leave_partial_json(destination, content, *args, **kwargs):
                if Path(destination) == archive_path:
                    with archive_path.open("xb") as handle:
                        handle.write(b'{"partial":')
                    raise OSError("simulated SMB interrupted write")
                return original_write(destination, content, *args, **kwargs)

            payload = {
                "domain": "example.com", "period": ["2026-07-01", "2026-07-31"],
                "ga4": {"session_count": 1}, "gsc": {"organic_clicks": 1},
            }
            with patch.object(google_api_collector, "_exclusive_write", new=leave_partial_json):
                with self.assertRaisesRegex(OSError, "interrupted write"):
                    save_new_month_archive(root, "example.com", "2026-07", payload)

            self.assertTrue(archive_path.is_file())
            self.assertTrue(archive_path.with_suffix(".json.lock").is_file())
            self.assertFalse(archive_path.with_suffix(".json.ready").exists())

    def test_lock_contains_provenance_while_writer_runs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_registry(root, "example.com", "example-com")
            archive_path = root / "ga4-gsc" / "example.com" / "2026-07.json"
            lock = archive_path.with_suffix(".json.lock")
            observed = {}
            original_write = google_api_collector._exclusive_write

            def capture_lock(destination, content, *args, **kwargs):
                result = original_write(destination, content, *args, **kwargs)
                if Path(destination) == lock:
                    observed.update(json.loads(lock.read_text(encoding="utf-8")))
                return result

            payload = {
                "domain": "example.com",
                "period": ["2026-07-01", "2026-07-31"],
                "ga4": {"session_count": 1},
                "gsc": {"organic_clicks": 1},
            }
            with patch.object(google_api_collector, "_exclusive_write", new=capture_lock):
                save_new_month_archive(root, "example.com", "2026-07", payload)

            self.assertEqual(observed["hostname"], socket.gethostname())
            self.assertEqual(observed["pid"], os.getpid())
            created_at = datetime.fromisoformat(observed["created_at_utc"])
            self.assertEqual(created_at.tzinfo, timezone.utc)
            self.assertFalse(lock.exists())

    def test_cleanup_failure_after_commit_keeps_success_and_lock(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_registry(root, "example.com", "example-com")
            archive_path = root / "ga4-gsc" / "example.com" / "2026-07.json"
            lock = archive_path.with_suffix(".json.lock")
            original_unlink = Path.unlink

            def fail_lock_cleanup(path, *args, **kwargs):
                if path == lock:
                    raise OSError("simulated SMB cleanup failure")
                return original_unlink(path, *args, **kwargs)

            payload = {
                "domain": "example.com",
                "period": ["2026-07-01", "2026-07-31"],
                "ga4": {"session_count": 1},
                "gsc": {"organic_clicks": 1},
            }
            stderr = io.StringIO()
            with patch.object(Path, "unlink", new=fail_lock_cleanup), redirect_stderr(stderr):
                self.assertEqual(save_new_month_archive(root, "example.com", "2026-07", payload), archive_path)

            self.assertTrue(archive_path.is_file())
            self.assertTrue(lock.is_file())
            self.assertIn("原始档案已提交", stderr.getvalue())
            self.assertIn(str(lock), stderr.getvalue())

    def test_invalid_identity_or_period_leaves_no_archive_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_registry(root, "example.com", "example-com")

            with self.assertRaisesRegex(ValueError, "归档域名不匹配"):
                save_new_month_archive(
                    root,
                    "example.com",
                    "2026-07",
                    {"domain": "other.example", "period": ["2026-07-01", "2026-07-31"]},
                )
            with self.assertRaisesRegex(ValueError, "归档周期必须是指定自然月"):
                save_new_month_archive(
                    root,
                    "example.com",
                    "2026-07",
                    {"domain": "example.com", "period": ["2026-07-02", "2026-07-31"]},
                )

            self.assertFalse((root / "ga4-gsc").exists())

    def test_incomplete_existing_target_or_ready_marker_is_never_repaired(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_registry(root, "example.com", "example-com")
            path = root / "ga4-gsc" / "example.com" / "2026-07.json"
            path.parent.mkdir(parents=True)
            path.write_bytes(b'{"partial":true}')
            payload = {
                "domain": "example.com", "period": ["2026-07-01", "2026-07-31"],
                "ga4": {"session_count": 1}, "gsc": {"organic_clicks": 1},
            }
            with self.assertRaisesRegex(ValueError, "缺少 ready 标记"):
                save_new_month_archive(root, "example.com", "2026-07", payload)
            self.assertEqual(path.read_bytes(), b'{"partial":true}')

            path.unlink()
            path.with_suffix(".json.ready").write_text('{"sha256":"0"}', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "ready 标记缺少 JSON"):
                save_new_month_archive(root, "example.com", "2026-07", payload)


class GoogleArchiveArgumentContractTest(unittest.TestCase):
    def test_archive_root_is_required_and_archive_dir_is_not_accepted(self) -> None:
        cases = (
            ([], "the following arguments are required: --archive-root"),
            (["--archive-root", "root", "--archive-dir", "ignored"], "unrecognized arguments: --archive-dir ignored"),
        )
        for args, message in cases:
            with self.subTest(args=args), patch.object(sys, "argv", ["google_api_collector.py", *args]):
                stderr = io.StringIO()
                with redirect_stderr(stderr), self.assertRaises(SystemExit) as raised:
                    main()
            self.assertEqual(raised.exception.code, 2)
            self.assertIn(message, stderr.getvalue())

    def test_non_ascii_or_noncanonical_month_is_rejected_before_config_or_api_access(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            for month in ("2026-7", "２０２６-０７", "٢٠٢٦-٠٧"):
                with self.subTest(month=month):
                    args = ["--archive-root", tmp, "--month", month]
                    with patch.object(sys, "argv", ["google_api_collector.py", *args]), patch.object(
                        google_api_collector,
                        "_load_object",
                        side_effect=AssertionError("invalid month must stop before config access"),
                    ):
                        with self.assertRaises(SystemExit) as raised:
                            main()
                    self.assertEqual(raised.exception.code, 2)

    def test_non_dry_run_single_platform_is_rejected_before_config_or_api_access(self) -> None:
        for platform in ("ga4", "gsc"):
            with self.subTest(platform=platform), patch.object(
                sys, "argv", ["google_api_collector.py", "--archive-root", "root", "--month", "2026-07", "--platform", platform]
            ), patch.object(
                google_api_collector, "_load_object", side_effect=AssertionError("single platform must stop before config access"),
            ):
                with self.assertRaises(SystemExit) as raised:
                    main()
                self.assertEqual(raised.exception.code, 2)

    def test_dry_run_does_not_reach_archive_or_collected_data_write(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            collected_data = root / "collected_data.json"
            self._run_with_mocked_collection(
                ["--archive-root", str(root), "--month", "2026-07", "--dry-run", "--collected-data", str(collected_data)],
                save_result=AssertionError("dry-run must not save an archive"),
            )
            self.assertFalse(collected_data.exists())

    def test_archive_only_does_not_write_collected_data(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            collected_data = root / "collected_data.json"
            self._run_with_mocked_collection(
                ["--archive-root", str(root), "--month", "2026-07", "--archive-only", "--collected-data", str(collected_data)],
                save_result=root / "ga4-gsc" / "example.com" / "2026-07.json",
            )
            self.assertFalse(collected_data.exists())

    def _run_with_mocked_collection(self, args, *, save_result) -> None:
        context = SimpleNamespace(domain="example.com", report_start="2026-07-01", report_end="2026-07-31")
        config = {"service_account_email": "service@example.com", "ga4": {"property_id": "123"}, "gsc": {"site_url": "https://example.com"}}
        with patch.object(sys, "argv", ["google_api_collector.py", *args]), patch.object(
            google_api_collector, "_load_object", return_value=config
        ), patch.object(google_api_collector.ProjectContext, "from_file", return_value=context), patch.object(
            google_api_collector, "_credential_path", return_value=Path("credential.json")
        ), patch.object(google_api_collector, "_validate_credential_identity"), patch.object(
            google_api_collector, "build_clients", return_value=(object(), object())
        ), patch.object(
            google_api_collector, "collect_ga4", return_value={"session_count": 1}
        ), patch.object(
            google_api_collector, "collect_gsc", return_value={"organic_clicks": 1, "ranked_keyword_count": 1}
        ), patch.object(google_api_collector, "save_new_month_archive") as save_archive:
            if isinstance(save_result, BaseException):
                save_archive.side_effect = save_result
            else:
                save_archive.return_value = save_result
            self.assertEqual(main(), 0)


if __name__ == "__main__":
    unittest.main()
