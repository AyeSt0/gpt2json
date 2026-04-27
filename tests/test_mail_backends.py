from gpt2json.mail_backends import (
    BACKEND_GRAPH,
    BACKEND_HTTP_URL,
    BACKEND_IMAP,
    BACKEND_IMAP_XOAUTH2,
    BACKEND_JMAP,
    CRED_APP_PASSWORD,
    CRED_REFRESH_TOKEN,
    backend_supports_credential,
    build_backend_plan,
    normalize_credential_kind,
    url_backend_plan,
)


def test_backend_registry_is_backend_first():
    assert backend_supports_credential(BACKEND_IMAP, CRED_APP_PASSWORD)
    assert backend_supports_credential(BACKEND_IMAP_XOAUTH2, CRED_REFRESH_TOKEN)
    assert backend_supports_credential(BACKEND_GRAPH, CRED_REFRESH_TOKEN)
    assert backend_supports_credential(BACKEND_JMAP, CRED_APP_PASSWORD)
    assert not backend_supports_credential(BACKEND_GRAPH, CRED_APP_PASSWORD)


def test_backend_plan_prefers_first_supported_backend():
    plan = build_backend_plan(
        source_kind="mailbox",
        provider="domain_hint",
        display_name="Domain hint",
        domain="example.test",
        credential_kind="refresh-token",
        preferred_backends=(BACKEND_IMAP, BACKEND_GRAPH, BACKEND_IMAP_XOAUTH2),
    )
    assert plan.credential_kind == CRED_REFRESH_TOKEN
    assert plan.planned_backends == [BACKEND_IMAP, BACKEND_GRAPH, BACKEND_IMAP_XOAUTH2]
    assert plan.primary_backend == BACKEND_GRAPH
    event = plan.to_event()
    assert event["primary_backend"] == BACKEND_GRAPH
    assert event["backend_candidates"][0]["credential_supported"] is False
    assert event["backend_candidates"][1]["credential_supported"] is True


def test_url_backend_plan_is_http_url():
    plan = url_backend_plan()
    assert plan.primary_backend == BACKEND_HTTP_URL
    assert plan.credential_supported is True


def test_credential_aliases_normalize():
    assert normalize_credential_kind("app-pass") == CRED_APP_PASSWORD
    assert normalize_credential_kind("refresh-token") == CRED_REFRESH_TOKEN

