---
name: seo-report-portal-v2-1
description: Create, review, and publish client-isolated monthly, quarterly, and yearly SEO dashboards from GA4, GSC, approved DataForSEO keyword-market snapshots, and SEOAgent strategy archives. Use for team SEO reporting, first-party performance analysis, limited keyword-market verification, and strategy-opportunity reporting.
---

# SEO Report Portal v2.1

**Active identity: `seo-report-portal-v2-1`.** Do not use, install, package, or inspect legacy `seo-report-portal` assets except as an explicitly requested rollback reference.

Work from a team workspace, never from this installed skill directory. Read `references/team-usage-guide.md` before first use. Read `references/third-party-data-guide.md` before any third-party collection or archive import.

## Core rules

- GSC owns search performance and dashboard opportunity-keyword selection. GA4 owns traffic, engagement, and key events. Never replace either with third-party estimates.
- DataForSEO owns selected-keyword search volume, CPC, paid competition, monthly trend, and limited live SERP. Request only exact GSC-selected dashboard keywords.
- SEOAgent owns strategy opportunities: priority optimization themes, competitor keyword directions, and external keyword discoveries. Its estimates never enter first-party KPIs or DataForSEO market columns.
- Before any paid DataForSEO or SEOAgent request, show the customer/domain, market, language, keyword count, SERP count, maximum cost, and purpose. Wait for explicit confirmation. Never retry a paid request automatically.
- Keep provider archives isolated by domain and collection month. Never overwrite GSC/GA4 source archives.
- Credentials are local only. Do not put API credentials, service-account JSON, MCP tokens, customer archives, or published reports in the skill package or a public repository.
- DataForSEO and SEOAgent are optional report inputs. A report without either archive must still generate from GSC/GA4 data.
- Validate every current and predecessor GA4/GSC archive against the requested domain before aggregation. A missing predecessor creates a current-period-only report; any cross-domain archive blocks generation.
- The report-period aggregate is canonical. Monthly selection may change only monthly detail panels; it must never alter management summary, report-period KPIs, channels, strategy metadata, or action plans.
- Hide an optional DataForSEO or SEOAgent panel when its archive scope is invalid. Never fill an empty panel with another month, another client, or a third-party estimate.
- Every run writes secret-safe internal diagnostics outside public dashboard directories. Tell the user the execution state, location, verified detection, impact, safe actions taken, and next action.
- Review the local report before publishing. Publish only after explicit approval.

## Workflow

1. Configure the local Google service account and customer read-only access as described in `references/team-usage-guide.md`.
2. Collect immutable monthly GA4/GSC archives with `scripts/google_api_collector.py`.
3. Generate a base dashboard with `scripts/generate_dashboard_report.py`.
4. For market validation, first determine the GSC-selected terms. Propose the bounded DataForSEO scope and cost, obtain confirmation, run `scripts/dataforseo_keyword_enrichment.py --dry-run`, then run `--execute` only after confirmation.
5. For strategy opportunities, collect through the teammate's locally configured SEOAgent MCP, normalize the response into the archive schema in `assets/seoagent-archive.example.json`, and store it outside the skill package.
6. Re-generate the dashboard with explicit optional inputs. Keep the diagnostics path outside `output/dashboards/`:

```text
--dataforseo-archive-dir <domain-specific-dataforseo-archive-dir>
--seoagent-archive-dir <domain-specific-seoagent-archive-dir>
--diagnostics-root <internal-diagnostic-root>
```

7. Validate the exact local artifact before it can be copied:

```text
python scripts/validate_report_artifact.py --report-dir <output/dashboards/domain/type/period> --domain-root <output/dashboards/domain>
```

8. Check the local HTML, summary, and internal `diagnostic.md`. Obtain explicit approval for this exact report before publishing.
9. Publish only with `scripts/publish_oss_report.py`: validate the three reviewed files, copy them to the approved SMB archive, compare SHA-256 values, upload from the SMB archive to OSS, and verify the public `index.html` SHA-256. Configure the SMB archive root for the local OS (macOS mount, Windows mapped drive, or Windows UNC path); never assume another teammate's mount path. The only supported public path is:

```text
https://reports.jzyseo.com/reports/<client-slug>/<monthly|quarterly|yearly>/<period>/
```

Read `references/team-first-run-guide.md` before a teammate's first end-to-end run. It covers Google access, optional providers, SMB, individual RAM credentials, ossutil, approval, and the required local-to-SMB-to-OSS order.
On Windows, also read `references/windows-first-run.md` before configuring paths or running the publisher.

9. Before replacing the v2 ZIP or global v2 installation, create a staged ZIP and require parity for `SKILL.md`, template, generator, and `agents/openai.yaml`:

```text
python scripts/check_package_parity.py --source <seo-report-portal-v2-1-source> --staged-zip <candidate.zip> --installed <global-seo-report-portal-v2-1>
```

## Resources

- `references/team-usage-guide.md` — teammate setup and daily workflow.
- `references/team-first-run-guide.md` — first-use checklist for the complete collection-to-public-link workflow.
- `references/windows-first-run.md` — Windows paths, SMB mapping, Python, and publisher setup.
- `references/third-party-data-guide.md` — provider scope, cost gate, archive rules, and dashboard meaning.
- `references/seo-data-source-contract.json` — authoritative field ownership.
- `assets/dataforseo-trial.example.json` — safe DataForSEO configuration example.
- `assets/dataforseo.env.example` — empty credential-file template.
- `assets/oss.env.example` and `assets/ossutilconfig.example` — safe local OSS configuration templates.
- `assets/oss-report-publisher-policy.json` — minimum RAM policy for the `jzyseo-reports/reports/*` upload prefix.
- `assets/seoagent-archive.example.json` — normalized SEOAgent archive example.
