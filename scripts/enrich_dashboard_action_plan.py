#!/usr/bin/env python3
"""Populate a dashboard's action-plan cards with the report's actual metrics."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def number(value: object, digits: int = 0) -> str:
    value = float(value or 0)
    return f"{value:.{digits}f}" if digits else f"{value:,.0f}"


def page_label(path: object) -> str:
    normalized = str(path or "/").rstrip("/") or "/"
    if normalized == "/":
        return "首页"
    labels = {
        "/certificates": "认证资质页面",
        "/about-us": "关于我们页面",
        "/contact-us": "联系我们页面",
        "/custom-formulation": "定制配方页面",
        "/product-category/product": "产品分类页",
        "/product-category/products": "产品分类页",
        "/natural-skin-care-manufacturers-7-best-picks-for-your-brand": "天然护肤品制造商页面",
    }
    if normalized in labels:
        return labels[normalized]
    if "/product/" in normalized:
        return "重点产品页"
    if "category" in normalized:
        return "重点产品分类页"
    return "重点落地页"


def action_plans(data: dict) -> list[dict[str, str]]:
    month = data["months"][-1]
    pages = month.get("pages", [])
    site_ctr = float(month.get("metrics", {}).get("ctr", 0) or 0)
    ctr_pages = [row for row in pages if float(row.get("impressions", 0) or 0) > 0]
    ctr_page = max(
        (row for row in ctr_pages if float(row.get("ctr", 0) or 0) < site_ctr),
        key=lambda row: float(row.get("impressions", 0) or 0),
        default=max(ctr_pages, key=lambda row: float(row.get("impressions", 0) or 0), default=None),
    )
    index_page = next((row for row in pages if row.get("indexVerdict") not in ("PASS", "NOT_INSPECTED", "ERROR")), None)
    keywords = [
        row for row in month.get("keywords", [])
        if 10 <= float(row.get("position", 0) or 0) <= 30
    ]
    keyword = max(keywords, key=lambda row: float(row.get("impressions", 0) or 0), default=None)
    experience_page = max(
        (row for row in pages if float(row.get("sessions", 0) or 0) > 0),
        key=lambda row: float(row.get("bounceRate", 0) or 0),
        default=None,
    )

    plans: list[dict[str, str]] = []
    if ctr_page:
        plans.append({
            "period": "1–30 天",
            "title": f"提升{page_label(ctr_page.get('path'))}的搜索点击率",
            "copy": (
                f"该页本期获得 {number(ctr_page.get('impressions'))} 次曝光、"
                f"{number(ctr_page.get('clicks'))} 次点击，CTR {number(ctr_page.get('ctr'), 2)}%，"
                f"平均排名第 {number(ctr_page.get('position'), 1)} 位。"
                "优先改写标题、描述、首屏卖点和询盘入口。"
            ),
            "kpi": "观察：该页曝光、CTR、自然点击与询盘关键事件",
        })
    if index_page:
        plans.append({
            "period": "31–60 天",
            "title": f"处理{page_label(index_page.get('path'))}的规范页信号",
            "copy": (
                f"该页本期有 {number(index_page.get('impressions'))} 次曝光、"
                f"{number(index_page.get('clicks'))} 次点击，当前状态为“{index_page.get('coverageState') or '待确认'}”。"
                "检查 canonical、分类层级和站内链接，确认是否需要保留独立索引。"
            ),
            "kpi": "观察：规范页判定、索引状态、该页曝光与排名",
        })
    elif keyword:
        keyword_name = str(keyword.get("query", "")).strip('"')
        plans.append({
            "period": "31–60 天",
            "title": "推进 OEM 关键词进入前十",
            "copy": (
                f"关键词“{keyword_name}”本期获得 {number(keyword.get('impressions'))} 次曝光，"
                f"平均排名第 {number(keyword.get('position'), 1)} 位。"
                "围绕采购场景补充 OEM 能力、MOQ、认证和案例，并从相关产品页添加内链。"
            ),
            "kpi": "观察：该关键词排名、曝光、自然点击与相关落地页会话",
        })
    if experience_page:
        plans.append({
            "period": "61–90 天",
            "title": f"改善{page_label(experience_page.get('path'))}的页面承接",
            "copy": (
                f"该页本期有 {number(experience_page.get('sessions'))} 次会话、"
                f"跳出率 {number(experience_page.get('bounceRate'), 2)}%。"
                "优化首屏价值说明、相关产品内链和询盘 CTA，提升访问后的下一步行动。"
            ),
            "kpi": "观察：跳出率、平均互动时长、CTA 点击与关键事件",
        })
    return plans


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dashboard-dir", type=Path, required=True)
    args = parser.parse_args()
    data_path = args.dashboard_dir / "dashboard-data.json"
    html_path = args.dashboard_dir / "index.html"
    data = json.loads(data_path.read_text(encoding="utf-8"))
    plans = action_plans(data)
    if len(plans) < 3:
        raise ValueError("当前归档缺少生成三阶段数据计划所需的页面或关键词数据")
    payload = json.dumps(plans, ensure_ascii=False).replace("<", "\\u003c")
    injection = f'''\n<script id="report-data-action-plan">\n(() => {{\n  const plans = {payload};\n  const root = document.getElementById('seo-growth-dashboard-v2');\n  const panel = root?.querySelector('[data-panel="plan"]');\n  const timeline = panel?.querySelector('.timeline');\n  if (!panel || !timeline) return;\n  const heading = panel.querySelector('h2');\n  const subtitle = panel.querySelector('.apple-section-heading p');\n  if (heading) heading.textContent = '90 天行动计划';\n  if (subtitle) subtitle.textContent = '从本月实际搜索、页面与关键词数据出发制定';\n  timeline.innerHTML = plans.map(plan => `\n    <div class="phase">\n      <div class="phase-period text-small">${{plan.period}}</div>\n      <div class="rail"><span class="node"></span></div>\n      <div>\n        <div class="phase-title">${{plan.title}}</div>\n        <div class="phase-copy">${{plan.copy}}</div>\n        <div class="phase-kpi text-small">${{plan.kpi}}</div>\n      </div>\n    </div>`).join('');\n}})();\n</script>\n'''
    html = html_path.read_text(encoding="utf-8")
    marker = '<script id="report-data-action-plan">'
    if marker in html:
        start = html.index(marker)
        end = html.index("</script>", start) + len("</script>")
        html = html[:start] + injection + html[end:]
    else:
        html = html.replace("</body>", injection + "</body>") if "</body>" in html else html + injection
    html_path.write_text(html, encoding="utf-8")
    print(json.dumps({"dashboard": str(args.dashboard_dir), "plans": plans}, ensure_ascii=False))


if __name__ == "__main__":
    main()
