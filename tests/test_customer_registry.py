"""Behavior checks for the shared customer registry contract."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE / "scripts"))

from customer_registry import (  # noqa: E402
    google_archive_path,
    load_registry,
    require_active_customer,
)


def write_registry(root: Path, customers: list[dict[str, str]]) -> None:
    (root / "customer-registry.json").write_text(
        json.dumps({"customers": customers}), encoding="utf-8"
    )


class CustomerRegistryTests(unittest.TestCase):
    def test_registry_resolves_one_active_domain_to_one_slug_and_month_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_registry(root, [{
                "canonical_domain": "Example-Domain.COM",
                "portal_slug": "example-domain-com",
                "status": "active",
            }])

            record = require_active_customer(root, "EXAMPLE-DOMAIN.com")

            self.assertEqual(record.canonical_domain, "example-domain.com")
            self.assertEqual(record.portal_slug, "example-domain-com")
            self.assertEqual(
                google_archive_path(root, record, "2026-07"),
                root / "ga4-gsc" / "example-domain.com" / "2026-07.json",
            )

    def test_registry_rejects_duplicate_active_domain(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_registry(root, [
                {"canonical_domain": "example.com", "portal_slug": "example-com", "status": "active"},
                {"canonical_domain": "example.com", "portal_slug": "another-slug", "status": "active"},
            ])

            with self.assertRaisesRegex(ValueError, "重复活动域名"):
                load_registry(root)

    def test_registry_rejects_duplicate_active_slug(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_registry(root, [
                {"canonical_domain": "example.com", "portal_slug": "example-com", "status": "active"},
                {"canonical_domain": "other.example", "portal_slug": "example-com", "status": "active"},
            ])

            with self.assertRaisesRegex(ValueError, "重复活动 slug"):
                load_registry(root)

    def test_registry_rejects_windows_unsafe_domain_characters_and_suffixes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for domain in ("example:com", "name?x", "example.com.", "example.com ", "con.com", "a/b.com", r"a\\b.com"):
                with self.subTest(domain=domain):
                    write_registry(root, [{
                        "canonical_domain": domain,
                        "portal_slug": "example-com",
                        "status": "active",
                    }])
                    with self.assertRaisesRegex(ValueError, "canonical_domain"):
                        load_registry(root)

    def test_registry_rejects_invalid_slug_after_valid_domain(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_registry(root, [{
                "canonical_domain": "example.com",
                "portal_slug": "Invalid_Slug",
                "status": "active",
            }])

            with self.assertRaisesRegex(ValueError, "portal_slug"):
                load_registry(root)

    def test_registry_accepts_an_explicit_legacy_public_domain_slug(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_registry(root, [{
                "canonical_domain": "dgmastermax.com",
                "portal_slug": "dgmastermax.com",
                "legacy_public_slug": True,
                "status": "active",
            }])

            record = require_active_customer(root, "dgmastermax.com")

            self.assertEqual(record.portal_slug, "dgmastermax.com")

    def test_registry_rejects_dotted_slug_without_explicit_legacy_marker(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_registry(root, [{
                "canonical_domain": "dgmastermax.com",
                "portal_slug": "dgmastermax.com",
                "status": "active",
            }])

            with self.assertRaisesRegex(ValueError, "portal_slug"):
                load_registry(root)

    def test_registry_rejects_invalid_status_after_valid_domain_and_slug(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_registry(root, [{
                "canonical_domain": "example.com",
                "portal_slug": "example-com",
                "status": "pending",
            }])

            with self.assertRaisesRegex(ValueError, "status"):
                load_registry(root)

    def test_registry_rejects_retired_customer_and_invalid_month(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_registry(root, [{
                "canonical_domain": "example.com",
                "portal_slug": "example-com",
                "status": "retired",
            }])

            with self.assertRaisesRegex(ValueError, "不是活动客户"):
                require_active_customer(root, "example.com")

            record = load_registry(root)["example.com"]
            with self.assertRaisesRegex(ValueError, "月份格式"):
                google_archive_path(root, record, "2026-7")


if __name__ == "__main__":
    unittest.main()
