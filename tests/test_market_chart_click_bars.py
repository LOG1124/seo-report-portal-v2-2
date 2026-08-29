import json
import subprocess
import unittest
from pathlib import Path


PACKAGE = Path(__file__).resolve().parents[1]
TEMPLATE = PACKAGE / "assets" / "dashboard-template.html"


class MarketChartClickBarsTest(unittest.TestCase):
    def test_market_bar_widths_and_lead_note_follow_clicks(self) -> None:
        """The click-sorted market chart must size bars and its lead note by clicks."""
        template = TEMPLATE.read_text(encoding="utf-8")
        start = template.rfind(
            "    (() => {\n      const root = document.getElementById('seo-growth-dashboard-v2');",
            0,
            template.index("countryCodeToRegion"),
        )
        end = template.index("\n    })();\n  </script>", start) + len("\n    })();")
        dashboard_data = {
            "months": [{"countries": [
                {"country": "nga", "clicks": 168, "impressions": 1612},
                {"country": "usa", "clicks": 62, "impressions": 17925},
            ]}],
        }
        harness = f"""
const result = {{}};
const chart = {{ set innerHTML(value) {{ result.chart = value; }} }};
const note = {{ set textContent(value) {{ result.note = value; }} }};
const data = {json.dumps(dashboard_data)};
const root = {{
  querySelector(selector) {{
    if (selector === '#google-seo-data') return {{ textContent: JSON.stringify(data) }};
    if (selector === '#market-chart') return chart;
    if (selector === '[data-panel=\"markets\"] .section-note') return note;
    return null;
  }},
  querySelectorAll() {{ return []; }},
}};
global.document = {{ getElementById() {{ return root; }} }};
{template[start:end]}
console.log(JSON.stringify(result));
"""
        result = subprocess.run(["node", "-e", harness], check=True, capture_output=True, text=True)
        rendered = json.loads(result.stdout)
        self.assertIn('width:100.0%', rendered["chart"])
        self.assertIn('width:36.9%', rendered["chart"])
        self.assertEqual(rendered["note"], "Nigeria 点击最多，搜索结果吸引力不足")


if __name__ == "__main__":
    unittest.main()
