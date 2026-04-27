# 贡献指南

欢迎改进 GPT2JSON。

## 开发环境

```bash
git clone https://github.com/AyeSt0/gpt2json.git
cd gpt2json
python -m pip install -e .[gui,dev]
python -m pytest -q
```

## 基本规则

- 不要提交真实账号、token、cookie、邮箱凭据、导出 JSON、数据库或日志。
- 测试和文档只能使用合成示例。
- OTP 获取优先做通用 backend：IMAP / Graph / JMAP / POP3 / API，不要把 provider 逻辑写进 OAuth 登录主流程。
- 新增输入格式或 OTP backend 必须补测试。
- GUI 变更保持单窗口、小工具、中文优先。

## 新增输入格式

1. 在 `gpt2json/parsing.py` 中新增 parser。
2. 注册到 `INPUT_FORMATS`。
3. 明确区分凭据：
   - `password` / `gpt_password`：GPT/OpenAI 登录密码；
   - `email_credential_kind`、`email_password`、`email_token`、`email_refresh_token`：邮箱侧凭据。
4. 在 `tests/test_parsing.py` 补合成测试。

## 新增 OTP backend

1. 优先实现通用协议/API 能力，而不是 provider 专用分支。
2. 在 `gpt2json/mail_backends.py` 声明 backend 能力和支持的凭据类型。
3. provider/domain 只在 `gpt2json/mail_providers.py` 中作为 backend 排序 hint。
4. 通过 `OtpFetcher.poll_row()` 接入。
5. 使用合成数据补测试，避免依赖真实网络账号。
