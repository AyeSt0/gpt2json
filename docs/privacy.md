# 隐私与数据处理

GPT2JSON 是本地导出工具。它的设计目标是：账号输入只在本地处理，输出文件由用户自己检查和导入。

## 本地保存

桌面版会保存少量 GUI 偏好：

```text
%LOCALAPPDATA%\GPT2JSON\settings.ini
```

这些偏好包括主题、输出目录等，不包含账号密码或导出的 token JSON。

## 输出文件

桌面版默认写入程序所在目录下的 `output/`；用户手动选择过其它输出目录后，后续会记住该目录。每次导出都会写入输出根目录下的新批次目录：

```text
GPT2JSON_<时间戳>_<短编码>/
```

其中 `sub2api_accounts.secret.json` 和 `CPA_<批次>/` 目录中的单账号 JSON 包含可用 token，应当按敏感文件处理。

如果仍有可恢复失败，客户端还会生成 `failed_rerun.secret.txt`。它包含失败账号的原始输入行，用于 GUI “重跑失败账号”，可能包含 GPT 登录密码和完整取码源，也必须按敏感文件处理。

## 日志与诊断

运行日志和失败报告尽量使用：

- 脱敏邮箱；
- 邮箱 hash；
- 阶段名；
- 错误类别；
- 建议动作。

它们不应包含明文密码、token、cookie 或完整取码源。

## GitHub 反馈建议

提交 issue / PR 时请不要粘贴：

- 真实账号；
- GPT 密码或邮箱密码；
- access token / refresh token / cookie；
- `*.secret.json`；
- `*.secret.txt`；
- 邮箱正文；
- 带本机用户名的完整路径。

推荐使用 `example.test`、`otp.example` 等合成域名复现问题。
