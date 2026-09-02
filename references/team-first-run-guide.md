# 同事首次上手：从采集到在线报告链接

本指南适用于 `seo-report-portal-v2-2`。每位同事都能完成**本地 → SMB → OSS**，但不得跳过数据、付费或发布批准门禁。

在 Windows 首次使用前，先阅读 [Windows 配置](windows-first-run.md)；不要把 macOS 的 `/Volumes/共享盘`、`.venv/bin/python` 或 `chmod` 命令照搬到 Windows。

## 已安装 v2.2 的安全更新：v2.2.1

这是 Skill 的补丁更新，不需要重新配置 Google、DataForSEO、SEOAgent、SMB 或 OSS。管理员只需通过安全渠道提供新的 `seo-report-portal-v2-2.zip` 和 SHA-256；同事只替换全局 Skill 目录，不修改客户工作区。

更新时必须保留以下内容不变：客户工作区的 `private/`、`workflows/automation/input/`、`output/dashboards/`、`~/.codex/config.toml` 以及已经发布的报告。旧的全局 Skill 目录先移动到带时间戳的备份目录，整个过程不删除文件；若现有全局 Skill 目录内出现 `private/`，先停止并报告，不要把凭据带入新包。

macOS/Linux 已安装版本更新：

```bash
shasum -a 256 /path/to/seo-report-portal-v2-2.zip
stage_dir="$(mktemp -d)"
unzip -q /path/to/seo-report-portal-v2-2.zip -d "$stage_dir"
test -f "$stage_dir/seo-report-portal-v2-2/SKILL.md"
test ! -e "$stage_dir/seo-report-portal-v2-2/private"
skill_dir=~/.codex/skills/seo-report-portal-v2-2
backup_dir=~/.codex/skill-backups/seo-report-portal-v2-2-pre-2.2.1-$(date +%Y%m%d%H%M%S)
test ! -e "$skill_dir/private"
mkdir -p "$(dirname "$backup_dir")"
mv "$skill_dir" "$backup_dir"
mv "$stage_dir/seo-report-portal-v2-2" "$skill_dir"
```

Windows 已安装版本更新：

```powershell
$zip = 'C:\path\to\seo-report-portal-v2-2.zip'
$stage = Join-Path $env:TEMP ('seo-report-portal-v2-2-' + [guid]::NewGuid())
$skill = Join-Path $env:USERPROFILE '.codex\skills\seo-report-portal-v2-2'
$backup = Join-Path $env:USERPROFILE ('.codex\skill-backups\seo-report-portal-v2-2-pre-2.2.1-' + (Get-Date -Format yyyyMMddHHmmss))
Get-FileHash $zip -Algorithm SHA256
Expand-Archive -LiteralPath $zip -DestinationPath $stage
if (!(Test-Path (Join-Path $stage 'seo-report-portal-v2-2\SKILL.md'))) { throw '候选包缺少 SKILL.md' }
if (Test-Path (Join-Path $stage 'seo-report-portal-v2-2\private')) { throw '候选包包含 private，停止更新' }
if (Test-Path (Join-Path $skill 'private')) { throw '现有全局 Skill 包含 private，停止更新' }
New-Item -ItemType Directory -Force (Split-Path $backup) | Out-Null
Move-Item $skill $backup
Move-Item (Join-Path $stage 'seo-report-portal-v2-2') $skill
```

替换后重启 Codex，让新 Skill 生效；不需要重建客户工作区或重新填写任何密钥。出现问题时，将新目录移走，再把对应时间戳备份目录移回 `~/.codex/skills/seo-report-portal-v2-2`（Windows 使用同样的 `Move-Item`），然后重新启动 Codex。

## 管理员先完成

1. 为同事提供客户的 GA4/GSC 只读服务账号访问。
2. 如需第三方模块，通过密码管理器发放获批准的 DataForSEO 凭据和 SEOAgent Token。
3. 让同事的独立 RAM 用户加入 `SEOReportPublishers` 用户组；该组应已绑定 `SEOReportPublisherPolicy`，且仅允许上传 `jzyseo-reports/reports/*`。
4. 提供 SMB 公盘写入访问，以及同事本机可用的归档路径：macOS 挂载路径、Windows 映射盘或 Windows UNC 路径。
5. 通过密码管理器提供该同事独立的 RAM AccessKey ID、AccessKey Secret 和 OSS 地域。不要共享管理员或其他同事的 AccessKey。

## 同事首次配置

在自己的客户工作区创建 `private/` 和 `scripts/`，复制无密钥模板与跨平台发布器。命令因系统不同：macOS 可用 Shell；Windows 请按 [Windows 配置](windows-first-run.md) 使用 PowerShell 与 Python。

只在本机填写 `private/dataforseo.env`、`private/ossutilconfig` 和 Google 服务账号 JSON。`private/oss.env` 指向本机 `ossutil`、`ossutilconfig` 和已连接的 SMB 归档根路径；不要填写或提交真实凭据到其他文件。

## 无消费与无写入检查

1. 重启 Codex 后确认 `seoagent` MCP 显示正常；不要用真实查询测试。
2. 确认 `private/oss.env` 的 `OSS_ARCHIVE_ROOT` 是本机可访问的 SMB 路径。
3. 生成本地报告并运行产物校验。macOS 可使用 `./.venv/bin/python`；Windows 使用 `.venv\\Scripts\\python.exe` 或 `py -3`：

```text
python scripts/validate_report_artifact.py --report-dir <output/dashboards/domain/type/period> --domain-root <output/dashboards/domain>
```

4. 只运行跨平台发布 dry-run；它不会写入 SMB 或 OSS：

```text
python scripts/publish_oss_report.py --local-report-dir <output/dashboards/domain/type/period> --client-slug <client-slug> --type <monthly|quarterly|yearly> --period <period> --dry-run
```

## 每份报告的发布步骤

1. 采集并归档 GA4/GSC 官方月度数据，绝不改写历史档案。
2. 如需 DataForSEO 或 SEOAgent，先获得该次请求的范围、费用上限和明确确认；归档必须匹配客户和月份。
3. 生成报告并人工核对 `index.html`、`summary.md` 和内部 `diagnostic.md`。
4. 获得这份报告的明确发布批准。
5. 执行 `publish_oss_report.py`。它按以下顺序处理，任何一步失败即停止：

```text
本地 index.html/dashboard-data.json/summary.md
→ 本机配置的 SMB <archive-root>/<client-slug>/<type>/<period>/
→ oss://jzyseo-reports/reports/<client-slug>/<type>/<period>/
→ https://reports.jzyseo.com/reports/<client-slug>/<type>/<period>/
```

6. 只有脚本报告 SMB 与本地 SHA-256 一致、线上 `index.html` SHA-256 一致且公开链接 GET 成功时，才能交付。
7. 客户交付固定包含在线报告链接和文字总结。文字总结必须逐字复制已审核 `summary.md` 的 `## 运营总结` 标题与编号正文；不得因任何人的要求改写、删减、重排、补充或替换。

已有不同公盘版本时，脚本会停止。只有明确批准替换时才增加 `--replace-archive`；这会覆盖该报告周期的三个公盘文件并上传 OSS。

## 常见停止条件

- `AccessDenied`：检查 RAM 用户是否已加入 `SEOReportPublishers`，以及用户组是否仍绑定 `SEOReportPublisherPolicy`。
- SMB 路径不存在：先连接或映射指定路径；不要把别人的 `/Volumes/共享盘` 当作本机路径，也不要绕过 SMB 直接上传。
- 线上目录 HEAD 返回 404：这是 OSS 目录行为；以报告链接的 GET 结果和 SHA-256 为准。
- 付费请求失败：停止并报告原始错误，不得自动重试。
