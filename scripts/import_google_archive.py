#!/usr/bin/env python3
"""Import one verified legacy GA4/GSC JSON without changing its original bytes."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from google_api_collector import validate_complete_month_archive, write_new_archive_bytes


def main() -> int:
    parser = argparse.ArgumentParser(description="导入已验证的旧版 GA4/GSC 月度原始档案")
    parser.add_argument("--archive-root", type=Path, required=True)
    parser.add_argument("--source-file", type=Path, required=True)
    parser.add_argument("--month", required=True)
    args = parser.parse_args()

    content = args.source_file.read_bytes()
    payload = json.loads(content)
    if not isinstance(payload, dict):
        raise ValueError("归档 JSON 必须是对象")
    domain = payload.get("domain")
    _, path = validate_complete_month_archive(args.archive_root, domain, args.month, payload)
    print(write_new_archive_bytes(path, content))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
