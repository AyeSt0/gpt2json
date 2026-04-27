from __future__ import annotations

from dataclasses import dataclass

from .mail_backends import (
    BACKEND_API,
    BACKEND_GRAPH,
    BACKEND_IMAP,
    BACKEND_IMAP_XOAUTH2,
    BACKEND_JMAP,
    BACKEND_POP3,
    CRED_APP_PASSWORD,
    CRED_COOKIE,
    CRED_OAUTH2,
    CRED_PASSWORD,
    CRED_REFRESH_TOKEN,
    CRED_TOKEN,
    BackendPlan,
    CredentialKind,
    build_backend_plan,
    normalize_credential_kind,
    url_backend_plan,
)
from .models import AccountRow
from .parsing import is_url_source, normalize_email


@dataclass(frozen=True)
class MailProviderProfile:
    id: str
    display_name: str
    domains: tuple[str, ...]
    credential_kinds: tuple[CredentialKind, ...]
    preferred_backends: tuple[str, ...]
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
    preferred_backends=(BACKEND_IMAP, BACKEND_IMAP_XOAUTH2),
    notes="Fallback profile for domains that do not have a dedicated adapter yet.",
)


PROVIDERS: tuple[MailProviderProfile, ...] = (
    MailProviderProfile(
        id="microsoft",
        display_name="Outlook / Hotmail / Live",
        domains=("outlook.com", "hotmail.com", "live.com", "msn.com", "passport.com"),
        credential_kinds=(CRED_PASSWORD, CRED_APP_PASSWORD, CRED_TOKEN, CRED_REFRESH_TOKEN, CRED_OAUTH2),
        preferred_backends=(BACKEND_GRAPH, BACKEND_IMAP_XOAUTH2, BACKEND_IMAP),
        notes="Prefer Graph/OAuth token when provided; app password/basic IMAP can be added as fallback.",
    ),
    MailProviderProfile(
        id="gmail",
        display_name="Gmail",
        domains=("gmail.com", "googlemail.com"),
        credential_kinds=(CRED_APP_PASSWORD, CRED_TOKEN, CRED_REFRESH_TOKEN, CRED_OAUTH2),
        preferred_backends=(BACKEND_API, BACKEND_IMAP_XOAUTH2, BACKEND_IMAP),
        notes="Prefer API/OAuth; basic account password is usually not accepted.",
    ),
    MailProviderProfile(
        id="fastmail",
        display_name="Fastmail",
        domains=("fastmail.com", "fastmail.fm", "fastmail.cn", "messagingengine.com"),
        credential_kinds=(CRED_APP_PASSWORD, CRED_TOKEN, CRED_PASSWORD),
        preferred_backends=(BACKEND_JMAP, BACKEND_IMAP),
        notes="Fastmail commonly uses app passwords for IMAP/JMAP integrations.",
    ),
    MailProviderProfile(
        id="icloud",
        display_name="iCloud Mail",
        domains=("icloud.com", "me.com", "mac.com"),
        credential_kinds=(CRED_APP_PASSWORD,),
        preferred_backends=(BACKEND_IMAP,),
        notes="iCloud mail access normally requires an app-specific password.",
    ),
    MailProviderProfile(
        id="qq",
        display_name="QQ Mail",
        domains=("qq.com", "vip.qq.com", "foxmail.com"),
        credential_kinds=(CRED_APP_PASSWORD, CRED_PASSWORD, CRED_TOKEN),
        preferred_backends=(BACKEND_IMAP, BACKEND_POP3, BACKEND_API),
        notes="QQ/foxmail often use an authorization code instead of the normal mailbox password.",
    ),
    MailProviderProfile(
        id="netease",
        display_name="163 / 126 / Yeah",
        domains=("163.com", "126.com", "yeah.net", "vip.163.com", "vip.126.com"),
        credential_kinds=(CRED_APP_PASSWORD, CRED_PASSWORD, CRED_TOKEN),
        preferred_backends=(BACKEND_IMAP, BACKEND_POP3, BACKEND_API),
        notes="NetEase mail commonly uses client authorization code for IMAP/POP.",
    ),
    MailProviderProfile(
        id="atomicmail",
        display_name="Atomic Mail",
        domains=("atomicmail.io", "atomicmail.com"),
        credential_kinds=(CRED_PASSWORD, CRED_APP_PASSWORD, CRED_TOKEN, CRED_REFRESH_TOKEN),
        preferred_backends=(BACKEND_API, BACKEND_IMAP),
        notes="Dedicated adapter can choose API/token or IMAP depending on supplied credential.",
    ),
    MailProviderProfile(
        id="luckmail",
        display_name="LuckMail",
        domains=("luckmail.com", "luckmail.net", "luckmail.org"),
        credential_kinds=(CRED_PASSWORD, CRED_APP_PASSWORD, CRED_TOKEN, CRED_REFRESH_TOKEN, CRED_COOKIE),
        preferred_backends=(BACKEND_API, BACKEND_IMAP, BACKEND_POP3),
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


def backend_plan_for_row(row: AccountRow) -> BackendPlan:
    if is_url_source(row.otp_source):
        return url_backend_plan()
    context = mailbox_context_from_row(row)
    provider = context.provider if context else detect_mail_provider(row.otp_email or row.otp_source or row.login_email)
    kind = context.credential_kind if context else ""
    return build_backend_plan(
        source_kind="mailbox",
        provider=provider.id,
        display_name=provider.display_name,
        domain=email_domain((context.email if context else row.otp_email or row.otp_source or row.login_email)),
        credential_kind=kind,
        preferred_backends=provider.preferred_backends,
    )


def list_mail_providers() -> list[MailProviderProfile]:
    return list(PROVIDERS) + [GENERIC_IMAP]


def list_supported_domains() -> list[str]:
    return sorted(PROVIDER_BY_DOMAIN)
