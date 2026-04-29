# 输入格式扩展指南

GPT2JSON 通过 parser 注册表支持多种账号文本格式。文本可以来自文件、桌面 GUI 粘贴框或 CLI stdin。新增格式时，只需要把原始行解析成统一的 `AccountRow`，不需要改 OAuth 登录和 JSON 导出层。

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

当前内置格式注册为 `dash_otp`，桌面端显示为 `号商格式 / 三段式`。目前暂时只支持号商页面 <https://pay.ldxp.cn/shop/plus7> 提供的账号格式，后续格式适配敬请期待。用户侧默认可以保持 `auto`，由 parser 注册表自动匹配。

桌面端也会展示若干未来预制格式，例如号商邮箱账密、号商邮箱令牌、号商自定义取码、CSV/表格批量等；这些预制项当前仅用于展示路线，处于禁用状态，不能被选中。实际开放顺序以号商提供的交付格式为准。

```text
GPT邮箱----GPT登录密码----免登录取码源
```

映射关系：

```python
password = GPT登录密码         # GPT/OpenAI 登录密码
email_password = ""           # 当前格式不提供邮箱密码
email_token = ""              # 当前格式不提供邮箱 token
otp_source = 免登录取码源
```

当前 parser 会按登录邮箱去重，避免同一个 GPT 账号在同批输入中重复执行。导出层会为每次运行创建唯一 `CPA_<批次>/` 目录，并对 CPA 文件名做二次防覆盖保护：如果服务端返回的 token 邮箱重复，会自动生成 `name.json`、`name_002.json` 这类文件名。

## 用户界面约定

- 下拉栏默认显示 `自动识别（推荐）`。
- 已实现格式可以选择；未实现预制格式只展示路线，不允许选中。
- 粘贴框提示文案不绑定某一种格式，字段含义以当前识别到的 parser 为准。
- 预检查只统计可解析账号，不会访问登录接口或取码源。

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
