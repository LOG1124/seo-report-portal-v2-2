# 第三方数据使用规则

## 固定分工

- **DataForSEO**：GSC 已筛选机会词的搜索量、CPC、付费竞争度、搜索趋势与少量 SERP 快照。
- **SEOAgent**：优先优化主题、竞品关键词方向与本站外部关键词发现。

两类第三方数据都不能替代 GSC 的搜索表现或 GA4 的流量、互动和关键事件。

## DataForSEO：先确认，再执行

1. 从当前报告期 GSC 查询词中选出看板要展示的机会词。
2. 在执行前列出域名、国家/语言、词数、SERP 数、用途和费用上限。
3. 等待明确确认后，先运行 `dataforseo_keyword_enrichment.py --dry-run`。
4. 只有确认仍有效时才运行 `--execute`。
5. 失败时停止并报告；不得自动重试付费请求。

默认试水范围为“5 个重点词市场指标 + 1 个重点词 SERP”。把响应保存到域名隔离的 DataForSEO 归档目录；生成报告时通过 `--dataforseo-archive-dir` 显式加载。

## SEOAgent：归档而非核心指标

每位同事在自己电脑上配置其获授权的 SEOAgent MCP。不要将 MCP 地址、Token 或导出的凭据放入工作区、技能包或聊天。

把已批准的查询结果按 `assets/seoagent-archive.example.json` 结构保存到域名隔离的 SEOAgent 归档目录。至少提供：`provider`、`domain`、`collection_month`、`status`、查询范围和三类响应数据。

生成报告时通过 `--seoagent-archive-dir` 显式加载。没有匹配归档时，报告应正常生成，只不显示策略机会模块。

SEOAgent 的排名、流量、搜索量或 CPC 等估算字段只可作为策略观察，不得写入 GSC/GA4 核心 KPI 或 DataForSEO 市场验证列。
