#!/usr/bin/env python3
"""Collect read-only GA4 and Google Search Console data via Google APIs."""

from __future__ import annotations

import argparse
import calendar
import json
import os
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple
from urllib.parse import quote

from collection import CollectedDataStore, ProjectContext, normalized_domain


GA4_SCOPE = "https://www.googleapis.com/auth/analytics.readonly"
GSC_SCOPE = "https://www.googleapis.com/auth/webmasters.readonly"
GA4_SOURCE_URL = "https://analyticsdata.googleapis.com/"
GSC_SOURCE_URL = "https://www.googleapis.com/webmasters/v3/"

CHANNEL_NAMES = {
    "Direct": "直接访问",
    "Organic Search": "自然搜索",
    "Paid Search": "付费搜索",
    "Organic Social": "自然社交",
    "Paid Social": "付费社交",
    "Referral": "引荐流量",
    "Email": "电子邮件",
    "Display": "展示广告",
    "Cross-network": "跨网络",
    "Organic Video": "自然视频",
    "Unassigned": "未分配",
}


class SearchConsoleRestClient:
    """Small authenticated REST client that avoids discovery-document timeouts."""

    def __init__(self, credentials: Any, timeout: int = 60):
        from google.auth.transport.requests import AuthorizedSession

        self.session = AuthorizedSession(credentials)
        self.timeout = timeout

    def query_search_analytics(self, site_url: str, body: Dict[str, Any]) -> Dict[str, Any]:
        encoded_site = quote(site_url, safe="")
        url = f"https://www.googleapis.com/webmasters/v3/sites/{encoded_site}/searchAnalytics/query"
        response = self.session.post(url, json=body, timeout=self.timeout)
        if response.status_code >= 400:
            raise RuntimeError(f"GSC API {response.status_code}: {response.text[:1200]}")
        return response.json()

    def inspect_url(self, site_url: str, inspection_url: str) -> Dict[str, Any]:
        response = self.session.post(
            "https://searchconsole.googleapis.com/v1/urlInspection/index:inspect",
            json={"inspectionUrl": inspection_url, "siteUrl": site_url, "languageCode": "zh-CN"},
            timeout=self.timeout,
        )
        if response.status_code >= 400:
            raise RuntimeError(f"URL Inspection API {response.status_code}: {response.text[:1200]}")
        return response.json()


def _load_object(path: Path) -> Dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON 顶层必须是对象: {path}")
    return payload


def _credential_path(config: Dict[str, Any], config_path: Path) -> Path:
    configured = str(config.get("credentials_file", "")).strip()
    environment = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "").strip()
    value = environment or configured
    if not value:
        raise ValueError("缺少 Google 凭据：请设置 GOOGLE_APPLICATION_CREDENTIALS 或 credentials_file")
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = Path.cwd() / path
    if not path.is_file():
        raise FileNotFoundError(f"Google 服务账号凭据不存在: {path}")
    return path


def _validate_credential_identity(credentials_file: Path, expected_email: str) -> None:
    payload = _load_object(credentials_file)
    if payload.get("type") != "service_account":
        raise ValueError("Google 凭据文件不是 service_account 类型")
    actual_email = str(payload.get("client_email", "")).strip().lower()
    expected = expected_email.strip().lower()
    if not expected:
        raise ValueError("google_api.json 缺少 service_account_email")
    if actual_email != expected:
        raise ValueError(f"服务账号不匹配：配置为 {expected}，密钥属于 {actual_email or '未知账号'}")


def build_clients(credentials_file: Path, *, ga4: bool, gsc: bool) -> Tuple[Any, Any]:
    """Build Google clients lazily so unit tests do not require Google SDKs."""
    try:
        from google.oauth2 import service_account
    except ImportError as exc:
        raise RuntimeError("缺少 google-auth；请先安装 requirements.txt") from exc

    scopes = [scope for enabled, scope in ((ga4, GA4_SCOPE), (gsc, GSC_SCOPE)) if enabled]
    credentials = service_account.Credentials.from_service_account_file(
        str(credentials_file), scopes=scopes
    )
    ga4_client = None
    gsc_client = None
    if ga4:
        try:
            from google.analytics.data_v1beta import BetaAnalyticsDataClient
        except ImportError as exc:
            raise RuntimeError("缺少 google-analytics-data；请先安装 requirements.txt") from exc
        # REST avoids common gRPC/TLS handshake failures on macOS and restricted networks.
        ga4_client = BetaAnalyticsDataClient(credentials=credentials, transport="rest")
    if gsc:
        gsc_client = SearchConsoleRestClient(credentials)
    return ga4_client, gsc_client


def _number(value: str) -> Any:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return value
    return int(number) if number.is_integer() else round(number, 6)


def _ga4_report(
    client: Any,
    property_id: str,
    start: str,
    end: str,
    dimensions: Sequence[str],
    metrics: Sequence[str],
    limit: int,
) -> List[Dict[str, Any]]:
    from google.analytics.data_v1beta.types import DateRange, Dimension, Metric, RunReportRequest

    request = RunReportRequest(
        property=f"properties/{property_id}",
        date_ranges=[DateRange(start_date=start, end_date=end)],
        dimensions=[Dimension(name=name) for name in dimensions],
        metrics=[Metric(name=name) for name in metrics],
        limit=limit,
    )
    response = client.run_report(request=request)
    rows: List[Dict[str, Any]] = []
    for row in response.rows:
        item: Dict[str, Any] = {}
        for index, name in enumerate(dimensions):
            item[name] = row.dimension_values[index].value
        for index, name in enumerate(metrics):
            item[name] = _number(row.metric_values[index].value)
        rows.append(item)
    return rows


def _add_average_engagement_per_session(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Match GA4 Traffic acquisition's average engagement time per session."""
    for row in rows:
        sessions = float(row.get("sessions", 0) or 0)
        engagement_seconds = float(row.get("userEngagementDuration", 0) or 0)
        row["averageEngagementTimePerSession"] = round(engagement_seconds / sessions, 2) if sessions else 0
    return rows


def collect_ga4(
    client: Any,
    property_id: str,
    start: str,
    end: str,
    row_limit: int = 1000,
) -> Dict[str, Any]:
    if not property_id.strip().isdigit():
        raise ValueError("GA4 property_id 必须是纯数字属性 ID")
    row_limit = max(1, min(int(row_limit), 100000))

    totals = _ga4_report(
        client,
        property_id,
        start,
        end,
        [],
        ["sessions", "engagedSessions", "totalUsers", "screenPageViews", "averageSessionDuration", "userEngagementDuration", "bounceRate", "keyEvents"],
        1,
    )
    if not totals:
        raise ValueError("GA4 在指定周期内没有返回汇总数据")
    quality_metrics = ["sessions", "engagedSessions", "totalUsers", "screenPageViews", "averageSessionDuration", "userEngagementDuration", "bounceRate", "keyEvents"]
    channels = _ga4_report(client, property_id, start, end, ["sessionDefaultChannelGroup"], quality_metrics, row_limit)
    sources = _ga4_report(client, property_id, start, end, ["sessionSource"], quality_metrics, row_limit)
    countries = _ga4_report(client, property_id, start, end, ["country"], ["sessions", "totalUsers", "engagedSessions"], row_limit)
    landing_pages = _ga4_report(client, property_id, start, end, ["landingPagePlusQueryString"], quality_metrics, row_limit)
    devices = _ga4_report(client, property_id, start, end, ["deviceCategory"], quality_metrics, row_limit)
    daily = _ga4_report(client, property_id, start, end, ["date"], quality_metrics, row_limit)

    for report_rows in (totals, channels, sources, countries, landing_pages, devices, daily):
        _add_average_engagement_per_session(report_rows)

    by_sessions = lambda rows: sorted(rows, key=lambda item: float(item.get("sessions", 0)), reverse=True)
    channels = by_sessions(channels)
    sources = by_sessions(sources)
    countries = by_sessions(countries)
    landing_pages = by_sessions(landing_pages)
    devices = by_sessions(devices)
    daily.sort(key=lambda item: str(item.get("date", "")))

    primary_raw = str(channels[0]["sessionDefaultChannelGroup"]) if channels else "未分配"
    secondary_raw = str(channels[1]["sessionDefaultChannelGroup"]) if len(channels) > 1 else "未分配"
    return {
        "session_count": int(totals[0]["sessions"]),
        "engaged_session_count": int(totals[0]["engagedSessions"]),
        "ga4_total_users": int(totals[0].get("totalUsers", 0)),
        "ga4_page_views": int(totals[0].get("screenPageViews", 0)),
        "ga4_avg_session_duration": round(float(totals[0].get("averageSessionDuration", 0)), 2),
        "ga4_avg_engagement_time_per_session": round(float(totals[0].get("averageEngagementTimePerSession", 0)), 2),
        "ga4_bounce_rate": round(float(totals[0].get("bounceRate", 0)) * 100, 2),
        "ga4_key_events": int(totals[0].get("keyEvents", 0)),
        "traffic_primary_channel": CHANNEL_NAMES.get(primary_raw, primary_raw),
        "traffic_secondary_channel": CHANNEL_NAMES.get(secondary_raw, secondary_raw),
        "session_top_source": str(sources[0]["sessionSource"]) if sources else "未分配",
        "country_region_count": len(countries),
        "top_country_region": str(countries[0]["country"]) if countries else "未分配",
        "ga4_channels": channels,
        "ga4_sources": sources,
        "ga4_countries": countries,
        "ga4_landing_pages": landing_pages,
        "ga4_devices": devices,
        "ga4_daily": daily,
        "_raw_channels": {"primary": primary_raw, "secondary": secondary_raw},
    }


def _gsc_query(
    service: Any,
    site_url: str,
    start: str,
    end: str,
    dimensions: Optional[Sequence[str]] = None,
    row_limit: int = 25000,
) -> List[Dict[str, Any]]:
    body: Dict[str, Any] = {
        "startDate": start,
        "endDate": end,
        "type": "web",
        "dataState": "final",
        "rowLimit": max(1, min(int(row_limit), 25000)),
    }
    if dimensions:
        body["dimensions"] = list(dimensions)
    if hasattr(service, "query_search_analytics"):
        response = service.query_search_analytics(site_url, body)
    else:
        response = service.searchanalytics().query(siteUrl=site_url, body=body).execute()
    rows: List[Dict[str, Any]] = []
    for row in response.get("rows", []):
        item = {
            "clicks": _number(row.get("clicks", 0)),
            "impressions": _number(row.get("impressions", 0)),
            "ctr": round(float(row.get("ctr", 0)) * 100, 4),
            "position": round(float(row.get("position", 0)), 4),
        }
        for index, name in enumerate(dimensions or []):
            item[name] = row.get("keys", [])[index]
        rows.append(item)
    return rows


def _page_type(url: str) -> str:
    from urllib.parse import urlparse

    path = urlparse(url).path.strip("/")
    if not path:
        return "主页"
    if path.lower().endswith(".pdf"):
        return "PDF"
    return "产品或内容页"


def collect_gsc(
    service: Any,
    site_url: str,
    expected_domain: str,
    start: str,
    end: str,
    row_limit: int = 25000,
    inspection_limit: int = 20,
) -> Dict[str, Any]:
    value = site_url.removeprefix("sc-domain:")
    if normalized_domain(value) != expected_domain:
        raise ValueError(f"GSC 资源域名不匹配：当前项目为 {expected_domain}，配置为 {site_url}")

    summary = _gsc_query(service, site_url, start, end, row_limit=1)
    if not summary:
        raise ValueError("GSC 在指定周期内没有返回效果数据")
    queries = _gsc_query(service, site_url, start, end, ["query"], row_limit)
    pages = _gsc_query(service, site_url, start, end, ["page"], row_limit)
    countries = _gsc_query(service, site_url, start, end, ["country"], row_limit)
    devices = _gsc_query(service, site_url, start, end, ["device"], row_limit)
    daily = _gsc_query(service, site_url, start, end, ["date"], row_limit)
    daily.sort(key=lambda item: str(item.get("date", "")))

    index_status: List[Dict[str, Any]] = []
    if hasattr(service, "inspect_url"):
        for page in pages[:max(0, min(int(inspection_limit), 50))]:
            page_url = str(page.get("page", ""))
            try:
                response = service.inspect_url(site_url, page_url)
                inspection = response.get("inspectionResult", {})
                status = inspection.get("indexStatusResult", {})
                index_status.append({
                    "page": page_url,
                    "verdict": status.get("verdict", "VERDICT_UNSPECIFIED"),
                    "coverageState": status.get("coverageState", ""),
                    "indexingState": status.get("indexingState", ""),
                    "pageFetchState": status.get("pageFetchState", ""),
                    "lastCrawlTime": status.get("lastCrawlTime", ""),
                    "googleCanonical": status.get("googleCanonical", ""),
                    "userCanonical": status.get("userCanonical", ""),
                    "inspectionResultLink": inspection.get("inspectionResultLink", ""),
                })
            except Exception as exc:
                index_status.append({"page": page_url, "verdict": "ERROR", "error": str(exc)[:300]})

    top_page_types: List[str] = []
    for page in pages:
        page_type = _page_type(str(page.get("page", "")))
        if page_type not in top_page_types:
            top_page_types.append(page_type)
        if len(top_page_types) == 2:
            break
    while len(top_page_types) < 2:
        top_page_types.append("其他页面")

    total = summary[0]
    return {
        "organic_clicks": int(total["clicks"]),
        "organic_impressions": int(total["impressions"]),
        "organic_ctr": round(float(total["ctr"]), 2),
        "average_position": round(float(total["position"]), 2),
        "ranked_keyword_count": len(queries),
        "top_landing_page_type": top_page_types[0],
        "second_landing_page_type": top_page_types[1],
        "gsc_queries": queries,
        "gsc_pages": pages,
        "gsc_countries": countries,
        "gsc_devices": devices,
        "gsc_daily": daily,
        "gsc_index_status": index_status,
    }


def _record_fields(store: CollectedDataStore, fields: Dict[str, Any], source_name: str, source_url: str) -> List[str]:
    recorded: List[str] = []
    raw_channels = fields.get("_raw_channels", {})
    for field, value in fields.items():
        if field.startswith("_"):
            continue
        raw_value = None
        if field == "traffic_primary_channel":
            raw_value = raw_channels.get("primary")
        elif field == "traffic_secondary_channel":
            raw_value = raw_channels.get("secondary")
        store.record(
            field,
            value,
            source_type="api",
            source_name=source_name,
            source_url=source_url,
            raw_value=raw_value,
        )
        recorded.append(field)
    return recorded


def _period_from_args(context: ProjectContext, month: Optional[str], start: Optional[str], end: Optional[str]) -> Tuple[str, str, str]:
    if month:
        try:
            year, month_number = (int(part) for part in month.split("-", 1))
            last_day = calendar.monthrange(year, month_number)[1]
        except (ValueError, TypeError) as exc:
            raise ValueError("--month 必须使用 YYYY-MM 格式") from exc
        return f"{year:04d}-{month_number:02d}-01", f"{year:04d}-{month_number:02d}-{last_day:02d}", f"{year:04d}-{month_number:02d}"
    start_value = start or context.report_start
    end_value = end or context.report_end
    start_date = date.fromisoformat(start_value)
    end_date = date.fromisoformat(end_value)
    if end_date < start_date:
        raise ValueError("采集结束日期不能早于开始日期")
    label = start_value[:7] if start_value[:7] == end_value[:7] else f"{start_value}_to_{end_value}"
    return start_value, end_value, label


def _save_archive(directory: Path, label: str, payload: Dict[str, Any]) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{label}.json"
    existing = _load_object(path) if path.exists() else {}
    existing.update(payload)
    existing["archived_at"] = datetime.now().astimezone().isoformat(timespec="seconds")
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(existing, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)
    return path


def main() -> int:
    parser = argparse.ArgumentParser(description="通过只读 API 采集 GA4 与 Google Search Console 数据")
    parser.add_argument("--platform", choices=("all", "ga4", "gsc"), default="all")
    parser.add_argument("--config", default="workflows/automation/config/google_api.json")
    parser.add_argument("--project-input", default="workflows/automation/config/project_input.json")
    parser.add_argument("--collected-data", default="workflows/automation/input/collected_data.json")
    parser.add_argument("--archive-dir", default="workflows/automation/input/google_api_archive")
    parser.add_argument("--month", help="按自然月采集并归档，格式 YYYY-MM")
    parser.add_argument("--start", help="自定义开始日期 YYYY-MM-DD")
    parser.add_argument("--end", help="自定义结束日期 YYYY-MM-DD")
    parser.add_argument("--dry-run", action="store_true", help="调用 API 并输出摘要，但不写入 collected_data.json")
    parser.add_argument("--archive-only", action="store_true", help="写入月度归档，但不改写 collected_data.json")
    args = parser.parse_args()

    config_path = Path(args.config)
    config = _load_object(config_path)
    context = ProjectContext.from_file(Path(args.project_input))
    period_start, period_end, archive_label = _period_from_args(context, args.month, args.start, args.end)
    use_ga4 = args.platform in ("all", "ga4")
    use_gsc = args.platform in ("all", "gsc")
    credentials_file = _credential_path(config, config_path)
    _validate_credential_identity(credentials_file, str(config.get("service_account_email", "")))
    ga4_client, gsc_client = build_clients(credentials_file, ga4=use_ga4, gsc=use_gsc)
    store = CollectedDataStore(Path(args.collected_data))
    result: Dict[str, Any] = {"domain": context.domain, "period": [period_start, period_end], "recorded": []}
    archive_payload: Dict[str, Any] = {"domain": context.domain, "period": [period_start, period_end]}

    if use_ga4:
        ga4_config = config.get("ga4", {})
        ga4_fields = collect_ga4(
            ga4_client,
            str(ga4_config.get("property_id", "")),
            period_start,
            period_end,
            int(ga4_config.get("row_limit", 1000)),
        )
        result["ga4"] = {"sessions": ga4_fields["session_count"], "detail_fields": 6}
        archive_payload["ga4"] = {field: value for field, value in ga4_fields.items() if not field.startswith("_")}
        if not args.dry_run and not args.archive_only:
            result["recorded"].extend(_record_fields(store, ga4_fields, "Google Analytics Data API", GA4_SOURCE_URL))

    if use_gsc:
        gsc_config = config.get("gsc", {})
        gsc_fields = collect_gsc(
            gsc_client,
            str(gsc_config.get("site_url", "")),
            context.domain,
            period_start,
            period_end,
            int(gsc_config.get("row_limit", 25000)),
            int(gsc_config.get("inspection_limit", 20)),
        )
        result["gsc"] = {"clicks": gsc_fields["organic_clicks"], "queries": gsc_fields["ranked_keyword_count"], "detail_fields": 5}
        archive_payload["gsc"] = gsc_fields
        if not args.dry_run and not args.archive_only:
            result["recorded"].extend(_record_fields(store, gsc_fields, "Google Search Console API", GSC_SOURCE_URL))

    if not args.dry_run:
        archive_path = _save_archive(Path(args.archive_dir), archive_label, archive_payload)
        result["archive"] = str(archive_path)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"连接失败 [{type(exc).__name__}]: {exc}", file=sys.stderr)
        raise SystemExit(2)
