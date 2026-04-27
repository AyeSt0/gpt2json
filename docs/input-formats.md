# 输入格式扩展指南

GPT2JSON 通过 parser 注册表支持多种账号文件格式。新增格式时，只需要把原始行解析成统一的 `AccountRow`，不需要改 OAuth 登录和 JSON 导出层。

## Canonical model

每个 parser 都返回 `AccountRow`：

```python
AccountRow(
    line_no=1,
    login_email="user@example.test",
    password="gpt-login-password",
    otp_source="https://otp-service.test/latest?mail={email}",
    source_format="dash_otp",
)
```

必须区分 GPT 凭据和邮箱凭据：

| 字段 | 用途 |
| --- | --- |
| `password` / `gpt_password` | GPT/OpenAI 登录密码。 |
| `email_credential_kind` | 邮箱侧凭据类型，如 `password`、`app_password`、`token`、`refresh_token`、`cookie`。 |
| `email_password` | 邮箱密码或 app-specific password。 |
| `email_token` | 邮箱 access token。 |
| `email_refresh_token` | 邮箱 refresh token。 |
| `email_client_id` | 格式中提供的 OAuth client id。 |
| `email_extra` | provider/backend 需要的额外元数据。 |
| `otp_source` | OTP 取码源。 |

## 当前内置格式

```text
GPT邮箱----GPT密码----OTP取码源
```

映射关系：

```python
password = GPT密码             # GPT 登录密码
email_password = ""           # 当前格式不提供邮箱密码
email_token = ""              # 当前格式不提供邮箱 token
otp_source = OTP取码源
```

## 新增 parser

1. 在 `gpt2json/parsing.py` 中实现 parser。
2. 返回带 `source_format` 的 `AccountRow`。
3. 注册到 `INPUT_FORMATS`。
4. 使用合成数据补测试，不要提交真实账号或 token。

示例骨架：

```python
def parse_custom_lines(lines: Iterable[str]) -> list[AccountRow]:
    rows = []
    for line_no, line in enumerate(lines, 1):
        rows.append(
            AccountRow(
                line_no=line_no,
                login_email=gpt_email,
                password=gpt_password,
                otp_source=mailbox_email,
                email_credential_kind="refresh_token",
                email_refresh_token=mail_refresh_token,
                source_format="custom",
            )
        )
    return rows
```
