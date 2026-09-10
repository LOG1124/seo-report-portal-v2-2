"""Shared customer identity registry and canonical Google archive paths."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
DOMAIN_RE = re.compile(
    r"(?=.{1,253}\Z)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+"
    r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?"
)
WINDOWS_RESERVED_DOMAIN_RE = re.compile(
    r"(?:con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\..*)?", re.IGNORECASE
)
MONTH_RE = re.compile(r"\d{4}-\d{2}")
VALID_STATUSES = {"active", "retired"}


@dataclass(frozen=True)
class CustomerRecord:
    canonical_domain: str
    portal_slug: str
    status: str


def _normalise_domain(value: Any) -> str:
    if not isinstance(value, str):
        raise ValueError("canonical_domain 必须是字符串")
    domain = value.lower()
    if not DOMAIN_RE.fullmatch(domain) or WINDOWS_RESERVED_DOMAIN_RE.fullmatch(domain):
        raise ValueError("canonical_domain 无效")
    return domain


def _parse_customer(item: Any) -> CustomerRecord:
    if not isinstance(item, dict):
        raise ValueError("customers 中的每项必须是对象")

    domain = _normalise_domain(item.get("canonical_domain"))
    slug = item.get("portal_slug")
    if not isinstance(slug, str) or not SLUG_RE.fullmatch(slug):
        raise ValueError("portal_slug 无效")
    status = item.get("status")
    if not isinstance(status, str) or status not in VALID_STATUSES:
        raise ValueError("status 必须是 active 或 retired")
    return CustomerRecord(domain, slug, status)


def load_registry(archive_root: Path) -> dict[str, CustomerRecord]:
    """Load and validate ``<archive_root>/customer-registry.json``."""
    registry_path = Path(archive_root) / "customer-registry.json"
    payload = json.loads(registry_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or not isinstance(payload.get("customers"), list):
        raise ValueError("customer-registry.json 的 customers 必须是列表")

    records: dict[str, CustomerRecord] = {}
    active_domains: set[str] = set()
    active_slugs: set[str] = set()
    for item in payload["customers"]:
        record = _parse_customer(item)
        if record.status == "active":
            if record.canonical_domain in active_domains:
                raise ValueError(f"重复活动域名：{record.canonical_domain}")
            if record.portal_slug in active_slugs:
                raise ValueError(f"重复活动 slug：{record.portal_slug}")
            active_domains.add(record.canonical_domain)
            active_slugs.add(record.portal_slug)
            records[record.canonical_domain] = record
        else:
            records.setdefault(record.canonical_domain, record)
    return records


def require_active_customer(archive_root: Path, domain: str) -> CustomerRecord:
    """Return the active canonical customer record for ``domain``."""
    canonical_domain = _normalise_domain(domain)
    record = load_registry(archive_root).get(canonical_domain)
    if record is None:
        raise ValueError(f"客户未在注册表中登记：{canonical_domain}")
    if record.status != "active":
        raise ValueError(f"客户不是活动客户：{canonical_domain}")
    return record


def google_archive_path(archive_root: Path, record: CustomerRecord, month: str) -> Path:
    """Build the canonical, cross-platform source archive path for one month."""
    if not isinstance(month, str) or not MONTH_RE.fullmatch(month):
        raise ValueError("月份格式必须为 YYYY-MM")
    return Path(archive_root) / "ga4-gsc" / record.canonical_domain / f"{month}.json"
