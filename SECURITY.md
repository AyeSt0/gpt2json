# 安全策略

## 支持版本

当前项目处于 0.x 阶段。安全修复优先面向 `main` 分支和最新发布版本。

## 报告安全问题

如发现漏洞，请优先使用 GitHub Private Vulnerability Reporting（如果仓库已启用）。如果需要发 issue，请只提供最小复现信息，不要包含任何真实凭据。

请不要在公开 issue / PR / 日志中粘贴：

- 真实账号；
- 密码、token、refresh token、cookie；
- 邮箱内容；
- 导出的 JSON；
- 本地数据库或私有日志。

## Secret 处理

GPT2JSON 的源码和 release artifact 不应包含用户凭据。输出目录、日志、数据库和 `*.secret.json` 默认被 `.gitignore` 忽略。
