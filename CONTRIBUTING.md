# Contributing

Thanks for helping improve GPT2JSON.

## Development setup

```bash
git clone https://github.com/AyeSt0/gpt2json.git
cd gpt2json
python -m pip install -e .[gui,dev]
python -m pytest -q
```

## Guidelines

- Do not commit real account lines, tokens, cookies, mailbox credentials, exported JSON, databases, or logs.
- Add parser fixtures with synthetic values only.
- Keep provider support backend-first: implement reusable IMAP/Graph/JMAP/POP3/API adapters instead of hard-coding provider logic into the OAuth flow.
- Add tests for every new input format or OTP backend.
- Keep UI changes consistent with the compact single-window workflow.

## Adding an input format

1. Add a parser in `gpt2json/parsing.py` that returns canonical `AccountRow` objects.
2. Register it in `INPUT_FORMATS`.
3. Fill GPT credentials and mailbox credentials separately:
   - `password` / `gpt_password`: GPT/OpenAI login password.
   - `email_credential_kind`, `email_password`, `email_token`, `email_refresh_token`: mailbox-side credentials.
4. Add tests in `tests/test_parsing.py`.

## Adding an OTP backend

1. Prefer generic backend modules by protocol/API capability.
2. Keep provider detection in `gpt2json/mail_providers.py`.
3. Wire row-level polling through `OtpFetcher.poll_row()`.
4. Add synthetic tests and avoid network-dependent unit tests.
