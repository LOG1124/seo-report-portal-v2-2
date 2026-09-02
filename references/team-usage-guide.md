# 团队使用说明

本说明覆盖每月工作流；同事首次配置 Google、第三方数据、SMB、公盘归档、RAM、ossutil 和发布校验时，先阅读 `references/team-first-run-guide.md`。所有凭据只保存在本机私密目录，不写进 Skill 包、报告或聊天。

已安装 v2.2 的同事同步 v2.2.1 时，只按 `references/team-first-run-guide.md` 的“已安装 v2.2 的安全更新”替换全局 Skill 目录。不要重新创建或覆盖客户工作区的 `private/`、Google 服务账号、第三方归档、报告输出或 `~/.codex/config.toml`；旧全局目录必须先移动到备份目录，更新后重启 Codex 即可。

## 管理员可提前完成

在同事开始前，管理员只需准备以下四项；这能把同事的首次配置缩减为“填本机私密文件 + 重启 Codex”。

1. **DataForSEO 账户**：确认账户已可用、已启用 API Access 且有可用余额；决定使用“每人独立凭据”还是“受控团队凭据”。推荐独立凭据，便于额度与权限追踪。
2. **安全交付**：通过密码管理器共享 DataForSEO API Login 与 API Password；不要发送到聊天、邮件正文、ZIP 或共享表格。
3. **SEOAgent 访问权**：为每位同事发放个人 Token（优先）或批准的团队 Token，并确认其有 SEOAgent MCP 使用权限。不要复用管理员的个人 Token。
4. **共同默认范围**：先约定首次试用范围为 United States / English / Google desktop、最多 5 个 GSC 已筛选机会词的市场指标 + 1 个 SERP 快照；每次执行前仍须单独确认域名、范围和费用上限。

将负责人、凭据位置名称和审批人填入 `references/company-access-handover.template.md`；该清单不记录任何密钥本身。

## 首次配置 A：DataForSEO（3 步）

### 第 1 步：建立仅本机可见的凭据文件

在**同事自己的私有工作区**中执行以下命令。以下命令适用于 macOS/Linux；Windows 请改按 [Windows 配置](windows-first-run.md)。若技能安装位置不同，只替换第一行的来源路径；不要修改文件内容之外的任何项目配置。

```bash
mkdir -p private
cp ~/.codex/skills/seo-report-portal-v2-2/assets/dataforseo.env.example private/dataforseo.env
chmod 600 private/dataforseo.env
```

打开 `private/dataforseo.env`，通过密码管理器粘贴管理员提供的两项值：

```dotenv
DATAFORSEO_LOGIN=<API_LOGIN>
DATAFORSEO_PASSWORD=<API_PASSWORD>
```

保存后关闭文件。这个文件必须保持在 `private/`，不能提交、上传、打包或贴进聊天。

### 第 2 步：让 Codex 先生成范围与预算，不执行付费请求

在客户工作区对 Codex 发送：

```text
使用 $seo-report-portal-v2-2 为 <domain> 准备 DataForSEO 试用配置。
只从 <YYYY-MM> 的 GSC 归档中挑选看板需要的机会词；市场为 United States、语言 English、设备 Google desktop。
先列出关键词数、SERP 数、用途与费用上限，并只执行 dry-run；不要发起付费请求。
```

同事应核对：域名、报告月份、关键词确实来自本期 GSC、关键词数不超过 5、SERP 数不超过 1，以及费用上限明确。`dry-run` 不调用外部接口，也不扣费。

### 第 3 步：明确确认后才执行一次

仅在负责人明确回复“确认”且范围与费用上限未变时，才让 Codex 执行。完成后应回报实际请求范围、实际费用（保留原币种）、归档路径和是否成功；失败即停止，**不得自动重试**。

DataForSEO 只提供搜索需求、CPC、付费竞争度、趋势与有限 SERP 快照；它不替代 GSC 的点击、展示、CTR、平均排名，也不替代 GA4 的会话和事件。

## 首次配置 B：SEOAgent MCP（3 步）

### 第 1 步：安全取得 Token

从管理员的密码管理器取得自己的 `<PERSONAL_OR_TEAM_TOKEN>`。不要把真实 Token 发给 Codex、写入报告或放进工作区。管理员应优先提供个人 Token；若使用团队 Token，必须由指定负责人管理轮换与撤销。

### 第 2 步：只追加本机 Codex 配置

打开 `~/.codex/config.toml`，保留所有既有内容，在**文件末尾**追加以下内容；仅把尖括号中的占位符替换成自己从密码管理器取得的 Token：

```toml
[mcp_servers.seoagent]
enabled = true
url = "https://www.seoagent.vip/mcp"

[mcp_servers.seoagent.http_headers]
Authorization = "Bearer <PERSONAL_OR_TEAM_TOKEN>"
```

不要重复添加同名 `[mcp_servers.seoagent]` 表。若已有该表，只核对 `enabled`、`url` 与 `Authorization` 三项并更新 Token；不要删除其他 MCP 配置。

### 第 3 步：重启并做无消费验收

**重启 Codex 桌面应用或 CLI 后再新开任务。**仅新开对话通常不足以重新加载全局 MCP 配置。重启后先检查 MCP 是否显示为 `seoagent`；若未显示，停止并检查 TOML 是否有重复表或引号错误，切勿用真实查询“试试看”。

首次真正采集时，先对 Codex 发送：

```text
使用 $seo-report-portal-v2-2 为 <domain> 准备 SEOAgent 策略快照。
查询范围：United States / English；本站关键词最多 20、机会主题最多 20；最多 3 个竞品、每个最多 5 个关键词。
先只给出查询范围、预计费用和归档路径，不发起查询。
```

负责人确认费用上限后才可执行。建议将真实响应规范化后保存在 `workflows/automation/input/seoagent_archive/<domain>/<YYYY-MM>.json`，结构以 `assets/seoagent-archive.example.json` 为准。

SEOAgent 的优先优化主题、竞品关键词方向和本站外部关键词发现属于策略快照；其排名、流量、搜索量或 CPC 估算不能写入 GSC/GA4 核心 KPI，也不能覆盖 DataForSEO 市场验证列。

## 每月工作流

1. 采集并归档客户当月的 GSC 与 GA4 官方数据。
2. 生成只含官方数据的本地月报，检查客户、周期和来源是否正确。
3. 如要加入市场机会验证，按上面的 DataForSEO 流程：范围与预算 → 明确确认 → 执行一次 → 归档。
4. 如要加入策略机会，按上面的 SEOAgent 流程：范围与预算 → 明确确认 → 采集 → 按示例结构归档。
5. 使用报告生成器的 `--dataforseo-archive-dir` 和 `--seoagent-archive-dir` 显式载入第三方归档。
6. 审核本地 HTML、`summary.md` 与内部诊断；得到明确发布授权后，按 `references/team-first-run-guide.md` 的“本地 → SMB → OSS”流程发布并回读校验线上链接。最终客户回复中的“文字总结”只逐字复制该份已审核 `summary.md` 的 `## 运营总结` 标题与编号正文，不得改写、删减、重排、补充或替换。客户可见的根路径 `/` 一律显示为“首页”，但不改写原始数据；运营总结的页面排行按 GSC 点击量，月报取当月，季报/年报取整个报告期合计；运营总结关键词第 2 条按 GSC 非品牌查询的报告期平均排名，数值越小越靠前；第 6 条国家/地区只按 GA4 `organicGoogleSearchClicks`（Google 搜索自然点击次数）选择，缺失时显示“暂无可用数据”，不得改用会话、GSC 点击或展示。

## 月报与季报

- 月报使用一个自然月的官方归档。首次归档月不伪造环比。
- 季报要求连续三个月的官方归档；点击、展示、会话等求和，CTR 和平均排名按正式聚合规则计算。
- DataForSEO 的季度快照默认是在季度机会词筛选完成后执行一次，不等于每个月自动重复采集。
- SEOAgent 是采集时点的策略快照，应显示采集时间和市场；它不等于报告期内的官方表现。

## 安全与故障处理

- 第三方归档按域名和采集月份分开保存，绝不改写 Google 月度原始档案。
- DataForSEO 付费调用失败时停止并报告；不得自动重试。
- SEOAgent 估算值不能覆盖 GSC、GA4 或 DataForSEO 的正式字段。
- 缺少任一第三方归档时，继续生成 GSC/GA4 基础报告，不用零值伪造第三方结果。
