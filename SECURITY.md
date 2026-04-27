# Security Policy

## Supported versions

The project is currently pre-1.0. Security fixes target the latest `main` branch and the latest published release.

## Reporting a vulnerability

Please report vulnerabilities through GitHub private vulnerability reporting if it is enabled for the repository, or open a minimal issue that does not include secrets or live credentials.

Do not include real account credentials, tokens, cookies, mailbox contents, exported JSON files, or private logs in public issues.

## Secret handling

GPT2JSON is designed so source code and release artifacts do not contain user credentials. Generated output files and logs are ignored by `.gitignore`; keep them outside commits and releases.
