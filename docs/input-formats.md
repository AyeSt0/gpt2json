# Input format extension guide

GPT2JSON uses a parser registry so new account file formats can be added without changing the OAuth or export layers.

## Canonical model

Every parser returns `AccountRow` instances:

```python
AccountRow(
    line_no=1,
    login_email="user@example.test",
    password="gpt-login-password",
    otp_source="https://otp-service.test/latest?mail={email}",
    source_format="dash_otp",
)
```

Credential separation is mandatory:

| Field | Purpose |
| --- | --- |
| `password` / `gpt_password` | GPT/OpenAI login password. |
| `email_credential_kind` | Mailbox credential type, e.g. `password`, `app_password`, `token`, `refresh_token`, `cookie`. |
| `email_password` | Mailbox password or app-specific password. |
| `email_token` | Mailbox access token. |
| `email_refresh_token` | Mailbox refresh token. |
| `email_client_id` | OAuth client identifier when supplied by a format. |
| `email_extra` | Provider/backend-specific metadata. |
| `otp_source` | OTP retrieval source. |

## Current format

```text
GPT_EMAIL----GPT_PASSWORD----OTP_SOURCE
```

This maps to:

```python
password = GPT_PASSWORD          # GPT login password
email_password = ""             # not present in this format
email_token = ""                # not present in this format
otp_source = OTP_SOURCE
```

## Adding a parser

1. Implement a parser in `gpt2json/parsing.py`.
2. Return `AccountRow` instances with explicit `source_format`.
3. Register it in `INPUT_FORMATS`.
4. Add tests with synthetic data only.

Example skeleton:

```python
def parse_custom_lines(lines: Iterable[str]) -> list[AccountRow]:
    rows = []
    for line_no, line in enumerate(lines, 1):
        # parse synthetic-safe fields
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
