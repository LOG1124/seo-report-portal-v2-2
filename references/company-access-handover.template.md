# SEO Report Portal 公司交接清单

> 不要在此文件填写密码、服务账号 JSON 内容、API 凭据、MCP Token、私钥或恢复码。仅记录负责人和受控凭据位置名称。

## 负责人

- 业务负责人：
- 技术负责人：
- 最后更新日期：

## 团队工作区与发布

- 私有工作区位置：
- SMB 公盘地址与挂载点：
- SMB 写入权限负责人：
- OSS Bucket：`jzyseo-reports`
- OSS 报告前缀：`reports/`
- 公开域名：`https://reports.jzyseo.com`
- RAM 用户组：`SEOReportPublishers`
- RAM 发布策略名称：`SEOReportPublisherPolicy`
- RAM AccessKey 凭据位置名称：

## Google 数据访问

- Google Cloud 项目名称：
- 服务账号邮箱的凭据位置名称：
- 已授权客户列表：
- 服务账号密钥上次轮换日期：
- 下次权限审查日期：

## 第三方数据访问

- DataForSEO 账户负责人：
- DataForSEO 凭据位置名称：
- DataForSEO 凭据方式：每人独立 / 受控团队凭据
- SEOAgent MCP 配置负责人：
- SEOAgent Token 凭据位置名称：
- SEOAgent Token 方式：每人独立 / 受控团队 Token
- 付费采集审批负责人：
- 默认首次试用范围与费用上限：

## 应急处理

- 凭据疑似泄露：立即在对应平台撤销或轮换，并审查共享仓库历史。
- 发布异常：确认 SMB 已挂载且可写、RAM 用户属于 `SEOReportPublishers`、策略仍限制为 `jzyseo-reports/reports/*`，再保留 ossutil 原始输出。
- 数据异常：保留原始归档，记录问题，未经审批不得用替代值覆盖。
