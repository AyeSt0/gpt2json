from __future__ import annotations

from dataclasses import dataclass

CredentialKind = str
BackendId = str

CRED_PASSWORD: CredentialKind = "password"
CRED_APP_PASSWORD: CredentialKind = "app_password"
CRED_TOKEN: CredentialKind = "token"
CRED_REFRESH_TOKEN: CredentialKind = "refresh_token"
CRED_COOKIE: CredentialKind = "cookie"
CRED_OAUTH2: CredentialKind = "oauth2"
CRED_API_KEY: CredentialKind = "api_key"
CRED_URL: CredentialKind = "url"
CRED_COMMAND: CredentialKind = "command"

BACKEND_HTTP_URL: BackendId = "http_url"
BACKEND_COMMAND: BackendId = "command"
BACKEND_IMAP: BackendId = "imap"
BACKEND_IMAP_XOAUTH2: BackendId = "imap_xoauth2"
BACKEND_GRAPH: BackendId = "graph"
BACKEND_JMAP: BackendId = "jmap"
BACKEND_POP3: BackendId = "pop3"
BACKEND_API: BackendId = "api"


@dataclass(frozen=True)
class MailBackendProfile:
    id: BackendId
    display_name: str
    credential_kinds: tuple[CredentialKind, ...]
    status: str
    notes: str = ""


@dataclass(frozen=True)
class BackendCandidate:
    id: BackendId
    display_name: str
    status: str
    credential_supported: bool


@dataclass(frozen=True)
class BackendPlan:
    source_kind: str
    provider: str
    display_name: str
    domain: str
    credential_kind: CredentialKind
    candidates: tuple[BackendCandidate, ...]

    @property
    def planned_backends(self) -> list[str]:
        return [candidate.id for candidate in self.candidates]

    @property
    def credential_supported(self) -> bool:
        return not self.credential_kind or any(candidate.credential_supported for candidate in self.candidates)

    @property
    def primary_backend(self) -> str:
        for candidate in self.candidates:
            if candidate.credential_supported:
                return candidate.id
        return self.candidates[0].id if self.candidates else ""

    def to_event(self) -> dict[str, object]:
        return {
            "source_kind": self.source_kind,
            "provider": self.provider,
            "display_name": self.display_name,
            "domain": self.domain,
            "credential_kind": self.credential_kind,
            "credential_supported": self.credential_supported,
            "primary_backend": self.primary_backend,
            "planned_backends": self.planned_backends,
            "backend_candidates": [
                {
                    "id": candidate.id,
                    "display_name": candidate.display_name,
                    "status": candidate.status,
                    "credential_supported": candidate.credential_supported,
                }
                for candidate in self.candidates
            ],
        }


BACKENDS: dict[BackendId, MailBackendProfile] = {
    BACKEND_HTTP_URL: MailBackendProfile(
        id=BACKEND_HTTP_URL,
        display_name="HTTP no-login URL",
        credential_kinds=(CRED_URL,),
        status="implemented",
        notes="Fetch JSON/text endpoint and extract a verification code.",
    ),
    BACKEND_COMMAND: MailBackendProfile(
        id=BACKEND_COMMAND,
        display_name="External command",
        credential_kinds=(CRED_COMMAND,),
        status="implemented",
        notes="Delegate OTP retrieval to a local command hook.",
    ),
    BACKEND_IMAP: MailBackendProfile(
        id=BACKEND_IMAP,
        display_name="IMAP",
        credential_kinds=(CRED_PASSWORD, CRED_APP_PASSWORD),
        status="planned",
        notes="Generic mailbox polling with password or app password.",
    ),
    BACKEND_IMAP_XOAUTH2: MailBackendProfile(
        id=BACKEND_IMAP_XOAUTH2,
        display_name="IMAP XOAUTH2",
        credential_kinds=(CRED_TOKEN, CRED_REFRESH_TOKEN, CRED_OAUTH2),
        status="planned",
        notes="OAuth-capable IMAP flow for token-based mailboxes.",
    ),
    BACKEND_GRAPH: MailBackendProfile(
        id=BACKEND_GRAPH,
        display_name="Graph",
        credential_kinds=(CRED_TOKEN, CRED_REFRESH_TOKEN, CRED_OAUTH2),
        status="planned",
        notes="Graph-compatible mailbox query backend.",
    ),
    BACKEND_JMAP: MailBackendProfile(
        id=BACKEND_JMAP,
        display_name="JMAP",
        credential_kinds=(CRED_TOKEN, CRED_APP_PASSWORD, CRED_API_KEY),
        status="planned",
        notes="JMAP-capable mailbox query backend.",
    ),
    BACKEND_POP3: MailBackendProfile(
        id=BACKEND_POP3,
        display_name="POP3",
        credential_kinds=(CRED_PASSWORD, CRED_APP_PASSWORD),
        status="planned",
        notes="Simple fallback mailbox polling backend.",
    ),
    BACKEND_API: MailBackendProfile(
        id=BACKEND_API,
        display_name="Provider API",
        credential_kinds=(CRED_TOKEN, CRED_REFRESH_TOKEN, CRED_COOKIE, CRED_API_KEY, CRED_PASSWORD, CRED_APP_PASSWORD),
        status="planned",
        notes="Custom provider API backend slot.",
    ),
}


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
        "oauth2": CRED_OAUTH2,
        "api": CRED_API_KEY,
        "api_token": CRED_API_KEY,
        "apikey": CRED_API_KEY,
    }
    return aliases.get(value, value)


def backend_supports_credential(backend_id: BackendId, credential_kind: str) -> bool:
    kind = normalize_credential_kind(credential_kind)
    backend = BACKENDS.get(backend_id)
    return bool(backend and (not kind or kind in backend.credential_kinds))


def build_backend_plan(
    *,
    source_kind: str,
    provider: str,
    display_name: str,
    domain: str,
    credential_kind: str,
    preferred_backends: tuple[BackendId, ...],
) -> BackendPlan:
    kind = normalize_credential_kind(credential_kind)
    candidates: list[BackendCandidate] = []
    for backend_id in preferred_backends:
        backend = BACKENDS.get(backend_id)
        if not backend:
            continue
        candidates.append(
            BackendCandidate(
                id=backend.id,
                display_name=backend.display_name,
                status=backend.status,
                credential_supported=backend_supports_credential(backend.id, kind),
            )
        )
    return BackendPlan(
        source_kind=source_kind,
        provider=provider,
        display_name=display_name,
        domain=domain,
        credential_kind=kind,
        candidates=tuple(candidates),
    )


def url_backend_plan() -> BackendPlan:
    return build_backend_plan(
        source_kind="url",
        provider="no_login_url",
        display_name="No-login OTP URL",
        domain="",
        credential_kind=CRED_URL,
        preferred_backends=(BACKEND_HTTP_URL,),
    )


def command_backend_plan() -> BackendPlan:
    return build_backend_plan(
        source_kind="command",
        provider="external_command",
        display_name="External command",
        domain="",
        credential_kind=CRED_COMMAND,
        preferred_backends=(BACKEND_COMMAND,),
    )


def list_mail_backends() -> list[MailBackendProfile]:
    return list(BACKENDS.values())

