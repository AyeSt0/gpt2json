from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .models import AccountRow
from .parsing import is_url_source, normalize_email


CredentialKind = str

CRED_PASSWORD: CredentialKind = "password"
CRED_APP_PASSWORD: CredentialKind = "app_password"
CRED_TOKEN: CredentialKind = "token"
CRED_REFRESH_TOKEN: CredentialKind = "refresh_token"
CRED_COOKIE: CredentialKind = "cookie"
CRED_OAUTH2: CredentialKind = "oauth2"


@dataclass(frozen=True)
class MailProviderProfile:
    id: str
    display_name: str
    domains: tuple[str, ...]
    credential_kinds: tuple[CredentialKind, ...]
    backends: tuple[str, ...]
    notes: str = ""


@dataclass(frozen=True)
class MailboxContext:
    provider: MailProviderProfile
    email: str
    credential_kind: CredentialKind
    password: str = ""
    token: str = ""
    refresh_token: str = ""
    client_id: str = ""
    extra: dict[str, str] | None = None

    @property
    def has_secret(self) -> bool:
        return bool(self.password or self.token or self.refresh_token or self.extra)


GENERIC_IMAP = MailProviderProfile(
    id="generic_imap",
    display_name="Generic IMAP",
    domains=(),
    credential_kinds=(CRED_PASSWORD, CRED_APP_PASSWORD, CRED_TOKEN, CRED_REFRESH_TOKEN),
    backends=("imap",),
    notes="Fallback profile for domains that do not have a dedicated adapter yet.",
)


PROVIDERS: tuple[MailProviderProfile, ...] = (
    MailProviderProfile(
        id="microsoft",
        display_name="Outlook / Hotmail / Live",
        domains=("outlook.com", "hotmail.com", "live.com", "msn.com", "passport.com"),
        credential_kinds=(CRED_PASSWORD, CRED_APP_PASSWORD, CRED_TOKEN, CRED_REFRESH_TOKEN, CRED_OAUTH2),
        backends=("graph", "imap_xoauth2", "imap"),
        notes="Prefer Graph/OAuth token when provided; app password/basic IMAP can be added as fallback.",
    ),
    MailProviderProfile(
        id="gmail",
        display_name="Gmail",
        domains=("gmail.com", "googlemail.com"),
        credential_kinds=(CRED_APP_PASSWORD, CRED_TOKEN, CRED_REFRESH_TOKEN, CRED_OAUTH2),
        backends=("gmail_api", "imap_xoauth2", "imap"),
        notes="Prefer Gmail API/OAuth; basic account password is usually not accepted.",
    ),
    MailProviderProfile(
        id="fastmail",
        display_name="Fastmail",
        domains=("fastmail.com", "fastmail.fm", "fastmail.cn", "messagingengine.com"),
        credential_kinds=(CRED_APP_PASSWORD, CRED_TOKEN, CRED_PASSWORD),
        backends=("imap", "jmap"),
        notes="Fastmail commonly uses app passwords for IMAP/JMAP integrations.",
    ),
    MailProviderProfile(
        id="icloud",
        display_name="iCloud Mail",
        domains=("icloud.com", "me.com", "mac.com"),
        credential_kinds=(CRED_APP_PASSWORD,),
        backends=("imap",),
        notes="iCloud mail access normally requires an app-specific password.",
    ),
    MailProviderProfile(
        id="qq",
        display_name="QQ Mail",
        domains=("qq.com", "vip.qq.com", "foxmail.com"),
        credential_kinds=(CRED_APP_PASSWORD, CRED_PASSWORD, CRED_TOKEN),
        backends=("imap", "pop3"),
        notes="QQ/foxmail often use an authorization code instead of the normal mailbox password.",
    ),
    MailProviderProfile(
        id="netease",
        display_name="163 / 126 / Yeah",
        domains=("163.com", "126.com", "yeah.net", "vip.163.com", "vip.126.com"),
        credential_kinds=(CRED_APP_PASSWORD, CRED_PASSWORD, CRED_TOKEN),
        backends=("imap", "pop3"),
        notes="NetEase mail commonly uses client authorization code for IMAP/POP.",
    ),
    MailProviderProfile(
        id="atomicmail",
        display_name="Atomic Mail",
        domains=("atomicmail.io", "atomicmail.com"),
        credential_kinds=(CRED_PASSWORD, CRED_APP_PASSWORD, CRED_TOKEN, CRED_REFRESH_TOKEN),
        backends=("imap", "api"),
        notes="Dedicated adapter can choose API/token or IMAP depending on supplied credential.",
    ),
    MailProviderProfile(
        id="luckmail",
        display_name="LuckMail",
        domains=("luckmail.com", "luckmail.net", "luckmail.org"),
        credential_kinds=(CRED_PASSWORD, CRED_APP_PASSWORD, CRED_TOKEN, CRED_REFRESH_TOKEN, CRED_COOKIE),
        backends=("api", "imap", "pop3"),
        notes="Provider slot reserved for LuckMail-style account/password or token-based mailbox access.",
    ),
)


PROVIDER_BY_ID: dict[str, MailProviderProfile] = {provider.id: provider for provider in PROVIDERS}
PROVIDER_BY_DOMAIN: dict[str, MailProviderProfile] = {
    domain: provider for provider in PROVIDERS for domain in provider.domains
}


def email_domain(email: str) -> str:
    text = normalize_email(email)
    return text.rsplit("@", 1)[1] if "@" in text else ""


def detect_mail_provider(email_or_domain: str) -> MailProviderProfile:
    text = str(email_or_domain or "").strip().lower()
    domain = email_domain(text) if "@" in text else text.lstrip("@")
    if "luckmail" in domain:
        return PROVIDER_BY_ID["luckmail"]
    return PROVIDER_BY_DOMAIN.get(domain, GENERIC_IMAP)


def normalize_credential_kind(kind: str) -> CredentialKind:
    value = str(kind or "").strip().lower().replace("-", "_")
    aliases = {
        "pass": CRED_PASSWORD,
        "pwd": CRED_PASSWORD,
        "mail_password": CRED_PASSWORD,
        "app_pwd": CRED_APP_PASSWORD,
        "app_pass": CRED_APP_PASSWORD,
        "auth_code": CRED_APP_PASSWORD,
        "authorization_code": CRED_APP_PASSWORD,
        "access_token": CRED_TOKEN,
        "refresh": CRED_REFRESH_TOKEN,
        "refresh_token": CRED_REFRESH_TOKEN,
        "oauth": CRED_OAUTH2,
    }
    return aliases.get(value, value)


def provider_supports_credential(provider: MailProviderProfile, kind: str) -> bool:
    normalized = normalize_credential_kind(kind)
    return not normalized or normalized in provider.credential_kinds


def mailbox_context_from_row(row: AccountRow) -> MailboxContext | None:
    email = normalize_email(row.otp_email or row.otp_source or row.login_email)
    provider = detect_mail_provider(email)
    kind = normalize_credential_kind(row.email_credential_kind)
    if not kind and row.email_password:
        kind = CRED_PASSWORD
    if not kind and (row.email_token or row.email_refresh_token):
        kind = CRED_TOKEN if row.email_token else CRED_REFRESH_TOKEN
    if not kind:
        return None
    return MailboxContext(
        provider=provider,
        email=email,
        credential_kind=kind,
        password=row.email_password,
        token=row.email_token,
        refresh_token=row.email_refresh_token,
        client_id=row.email_client_id,
        extra=dict(row.email_extra or {}),
    )


def provider_plan_for_row(row: AccountRow) -> dict[str, object]:
    if is_url_source(row.otp_source):
        return {
            "provider": "no_login_url",
            "display_name": "No-login OTP URL",
            "domain": "",
            "credential_kind": "url",
            "credential_supported": True,
            "planned_backends": ["http_url"],
        }
    context = mailbox_context_from_row(row)
    provider = context.provider if context else detect_mail_provider(row.otp_email or row.otp_source or row.login_email)
    kind = context.credential_kind if context else ""
    return {
        "provider": provider.id,
        "display_name": provider.display_name,
        "domain": email_domain((context.email if context else row.otp_email or row.otp_source or row.login_email)),
        "credential_kind": kind,
        "credential_supported": provider_supports_credential(provider, kind),
        "planned_backends": list(provider.backends),
    }


def list_mail_providers() -> list[MailProviderProfile]:
    return list(PROVIDERS) + [GENERIC_IMAP]


def list_supported_domains() -> list[str]:
    return sorted(PROVIDER_BY_DOMAIN)
