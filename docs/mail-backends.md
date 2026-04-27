# Mailbox OTP backend plan

GPT2JSON keeps OTP retrieval backend-first. Provider/domain detection maps an account row to a likely backend plan, but the login flow only calls `OtpFetcher.poll_row()`.

## Implemented backends

| Backend | Status | Notes |
| --- | --- | --- |
| HTTP no-login URL | Implemented | Fetches JSON/text and extracts a 6-digit code. Supports `{email}` URL templates. |
| External command | Implemented | Runs a user-provided command and extracts a 6-digit code from stdout. |

## Planned backends

| Backend | Credential kinds | Notes |
| --- | --- | --- |
| IMAP | password, app_password | Generic mailbox polling and message search. |
| IMAP XOAUTH2 | token, refresh_token | OAuth-capable IMAP flow. |
| Graph | token, refresh_token | API mailbox query for Graph-compatible accounts. |
| JMAP | token, app_password | Useful for JMAP-capable providers. |
| POP3 | password, app_password | Fallback for simple mailbox access. |
| Provider API | token, cookie, api_key | Adapter slot for services that expose custom mail APIs. |

## Provider detection

`gpt2json/mail_providers.py` contains lightweight provider profiles. Each profile declares domains, supported credential kinds, and preferred backend names. This keeps provider-specific decisions out of the OAuth login code.

## Adapter requirements

A backend adapter should:

1. receive an `AccountRow` or mailbox context;
2. never mutate GPT credentials;
3. poll with the global timeout/interval settings;
4. extract OTP codes through shared helpers in `gpt2json/otp.py`;
5. avoid logging secrets;
6. include synthetic unit tests.
