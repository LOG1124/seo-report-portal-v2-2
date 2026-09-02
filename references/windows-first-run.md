# Windows 首次配置

本说明仅适用于 Windows 工作区。不要运行 macOS 的 `chmod`、`/Volumes/共享盘` 或 `.venv/bin/python` 命令。

## 1. 本地工具与私密文件

在 PowerShell 的客户工作区执行。`$skill` 是 Codex 已安装的现役 v2.2 Skill，不是旧版本：

```powershell
$skill = Join-Path $env:USERPROFILE '.codex\skills\seo-report-portal-v2-2'
New-Item -ItemType Directory -Force private, scripts | Out-Null
Copy-Item "$skill\assets\dataforseo.env.example" 'private\dataforseo.env'
Copy-Item "$skill\assets\oss.env.example" 'private\oss.env'
Copy-Item "$skill\assets\ossutilconfig.example" 'private\ossutilconfig'
Copy-Item "$skill\scripts\publish_oss_report.py" 'scripts\publish_oss_report.py'
```

通过安全渠道手动放置 Google 服务账号 JSON 到 `private\google-service-account.json`。不要让 Codex 输出、上传或复制凭据内容。

安装 Python 后，运行时优先使用 `.venv\Scripts\python.exe`；没有虚拟环境时使用 `py -3`。不要使用 macOS 路径 `.venv/bin/python`。

## 2. 连接 SMB 公盘

优先将公司 SMB 公盘映射为固定盘符，例如 `Z:`；也可在 Python 发布器中使用 UNC 路径。映射后先在资源管理器确认能打开并创建测试文件，再删除该测试文件。

在 `private\oss.env` 中填写**一种**本机路径：

```dotenv
# 推荐：映射盘
OSS_ARCHIVE_ROOT=Z:\seo-report-portal

# 或者：UNC
# OSS_ARCHIVE_ROOT=\\192.168.110.26\共享盘\seo-report-portal
```

不要填写 macOS 的 `/Volumes/共享盘/seo-report-portal`。SMB 用户名和密码由 Windows 凭据管理器处理，不能写入 `oss.env`。

## 3. OSS 配置与无写入验证

在 `private\ossutilconfig` 中填写该同事独立的 RAM AccessKey；在 `private\oss.env` 中指定 `ossutil.exe` 的实际路径或保持 `OSSUTIL_BIN=ossutil`（仅在它已加入 PATH 时）。不要把 AccessKey 贴入聊天。

先用以下命令做无写入验证：

```powershell
.\.venv\Scripts\python.exe .\scripts\publish_oss_report.py --local-report-dir <report-dir> --client-slug <client-slug> --type <monthly|quarterly|yearly> --period <period> --dry-run
```

若没有 `.venv`，将命令开头替换为：

```powershell
py -3 .\scripts\publish_oss_report.py
```

`--dry-run` 仅检查本地报告与 SMB 根路径，绝不写入 SMB、OSS 或线上链接。真实发布仍须先完成报告复核并取得本次报告的明确批准。
