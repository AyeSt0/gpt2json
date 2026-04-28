# 隐私与数据处理

GPT2JSON 是本地导出工具。它的设计目标是：账号输入只在本地处理，输出文件由用户自己检查和导入。

## 本地保存

桌面版会保存少量 GUI 偏好：

```text
%LOCALAPPDATA%\GPT2JSON\settings.ini
```

这些偏好包括主题、输出目录等，不包含账号密码或导出的 token JSON。

## 输出文件

导出结果默认写入用户选择的输出根目录下的新批次目录：

```text
GPT2JSON_<时间戳>_<短编码>/
```

其中 `sub2api_accounts.secret.json` 和 `CPA_<批次>/` 目录中的单账号 JSON 包含可用 token，应当按敏感文件处理。

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
- 邮箱正文；
- 带本机用户名的完整路径。

推荐使用 `example.test`、`otp.example` 等合成域名复现问题。
