# 安全策略

## 支持版本

GPT2JSON 当前处于 0.x 阶段。安全修复优先面向 `main` 分支和最新 Release。

| 版本 | 支持状态 |
| --- | --- |
| 最新 Release | ✅ 支持 |
| `main` | ✅ 支持 |
| 更早 0.x | ⚠️ 视情况修复，建议升级 |

## 报告安全问题

如发现安全问题，请优先使用 GitHub Private Vulnerability Reporting（如果仓库已启用）。如果只能提交公开 issue，请只提供最小复现，不要包含任何真实凭据。

不要在公开 issue / PR / 日志中粘贴：

- 真实账号；
- GPT 密码、邮箱密码、app-password；
- access token、refresh token、cookie；
- 邮箱正文或验证码；
- 导出的 JSON；
- 本地数据库、日志、缓存或带用户名的完整路径。

## Secret 处理约定

- `*.secret.json`、`*.secret.txt`、`output/`、本地构建产物默认被 `.gitignore` 忽略。
- 日志和失败报告只应输出脱敏邮箱、hash、阶段名、错误类别和建议。
- 文档、测试、截图只使用 `example.test`、`otp.example` 等合成数据。
- Release 资产不应包含任何本地导出结果。
