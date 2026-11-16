"""Tests for the admin API, authentication and stored connections (ps-004)."""

import sqlite3
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from github import GithubException

from spark.api import security
from spark.api.__main__ import bootstrap_admin
from spark.api.app import create_app
from spark.registry import Registry, connections
from spark.registry.discovery import run_discovery
from spark.registry.secrets import SecretBox, SecretError, generate_key
from tests.unit.registry_fakes import FakeGithub, make_repo

PASSWORD = "correct horse battery"
TOKEN = "github_pat_" + "x" * 40


class TokenAwareGithub(FakeGithub):
    """Fake whose visibility depends on which token it was built with."""

    def __init__(self, token, **kwargs):
        super().__init__(**kwargs)
        self.token = token

    def get_user(self, login=None):
        if login is None:
            if self.token != TOKEN:
                raise GithubException(401, {"message": "Bad credentials"}, {})
            return type("Me", (), {"login": "admin-user"})()
        return super().get_user(login)


@pytest.fixture
def db_path(tmp_path):
    return tmp_path / "registry.db"


@pytest.fixture
def box():
    return SecretBox(generate_key())


@pytest.fixture
def fake_world():
    return dict(
        orgs={"Acme": [make_repo("Acme/a"), make_repo("Acme/b")]},
        users={"Octo": [make_repo("Octo/x")]},
    )


@pytest.fixture
def client(db_path, box, fake_world):
    registry = Registry.open(db_path)
    security.create_admin(registry, "admin", PASSWORD)
    registry.close()
    app = create_app(
        db_path,
        secret_box=box,
        github_factory=lambda token: TokenAwareGithub(token, **fake_world),
        default_token="default-token",
    )
    return TestClient(app, base_url="http://testserver")


def sign_in(client, password=PASSWORD, username="admin"):
    return client.post(
        "/api/session", json={"username": username, "password": password}
    )


@pytest.fixture
def admin(client):
    response = sign_in(client)
    assert response.status_code == 200
    client.headers["X-CSRF-Token"] = response.json()["csrf_token"]
    return client


# -- authentication ---------------------------------------------------------
def test_health_is_public_and_everything_else_requires_sign_in(client):
    assert client.get("/api/health").json() == {"ok": True}
    for method, path in [
        ("get", "/api/sources"),
        ("get", "/api/repositories"),
        ("get", "/api/connections"),
        ("get", "/api/portfolio"),
        ("post", "/api/sources"),
        ("post", "/api/refresh"),
        ("post", "/api/connections"),
        ("patch", "/api/repositories"),
        ("delete", "/api/sources/1"),
    ]:
        response = getattr(client, method)(path)
        assert response.status_code == 401, (method, path)


def test_bad_credentials_are_rejected_without_revealing_which_part(client):
    wrong_pw = sign_in(client, password="wrong password!!")
    no_user = sign_in(client, username="nobody")
    assert wrong_pw.status_code == no_user.status_code == 401
    assert wrong_pw.json() == no_user.json()


def test_repeated_failures_lock_the_account_temporarily(client):
    for _ in range(5):
        assert sign_in(client, password="nope-nope-nope-1").status_code == 401
    assert sign_in(client).status_code == 429  # even the right password waits


def test_session_cookie_is_httponly_strict_and_hashed_at_rest(client, db_path):
    response = sign_in(client)
    cookie = response.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=strict" in cookie
    raw_token = client.cookies.get("spark_session")
    stored = (
        sqlite3.connect(db_path)
        .execute("SELECT token_hash FROM admin_session")
        .fetchone()[0]
    )
    assert raw_token and stored != raw_token and raw_token not in stored


def test_password_is_stored_as_a_slow_salted_hash(client, db_path):
    stored = (
        sqlite3.connect(db_path)
        .execute("SELECT password_hash FROM admin_user")
        .fetchone()[0]
    )
    assert stored.startswith("$argon2") and PASSWORD not in stored


def test_sign_out_ends_the_session(admin):
    assert admin.delete("/api/session").status_code == 204
    assert admin.get("/api/sources").status_code == 401


def test_expired_session_is_rejected(db_path):
    registry = Registry.open(db_path)
    user_id = security.create_admin(registry, "admin", PASSWORD)
    past = datetime.now(timezone.utc) - timedelta(hours=13)
    token, _ = security.create_session(registry, user_id, hours=12, now=past)
    assert security.lookup_session(registry, token) is None
    registry.close()


def test_changing_the_password_signs_everyone_out(db_path):
    registry = Registry.open(db_path)
    user_id = security.create_admin(registry, "admin", PASSWORD)
    token, _ = security.create_session(registry, user_id)
    security.set_admin_password(registry, "admin", "another long password")
    assert security.lookup_session(registry, token) is None
    assert security.authenticate(registry, "admin", "another long password")
    registry.close()


def test_short_passwords_are_refused(db_path):
    registry = Registry.open(db_path)
    with pytest.raises(Exception, match="at least 12"):
        security.create_admin(registry, "admin", "short")
    registry.close()


def test_admin_bootstraps_from_the_environment_only_once(db_path):
    registry = Registry.open(db_path)
    env = {"SPARK_ADMIN_USER": "boss", "SPARK_ADMIN_PASSWORD": PASSWORD}
    assert bootstrap_admin(registry, env) == "boss"
    assert bootstrap_admin(registry, {**env, "SPARK_ADMIN_USER": "other"}) is None
    assert security.authenticate(registry, "boss", PASSWORD)
    registry.close()


# -- CSRF and origin -----------------------------------------------------------
def test_writes_require_the_csrf_token(client):
    sign_in(client)
    response = client.post("/api/refresh")
    assert response.status_code == 403
    assert "CSRF" in response.json()["detail"]


def test_cross_origin_writes_are_refused(admin):
    response = admin.post("/api/refresh", headers={"Origin": "http://evil.example"})
    assert response.status_code == 403


def test_same_origin_writes_are_allowed(admin):
    response = admin.post("/api/refresh", headers={"Origin": "http://testserver"})
    assert response.status_code == 202


# -- sources -----------------------------------------------------------------
def test_add_org_validates_discovers_and_lists(admin):
    created = admin.post("/api/sources", json={"type": "org", "identifier": "Acme"})
    assert created.status_code == 201
    body = created.json()
    assert body["state"] == "ok" and body["repository_count"] == 2
    assert [s["identifier"] for s in admin.get("/api/sources").json()] == ["Acme"]
    names = [r["full_name"] for r in admin.get("/api/repositories").json()]
    assert names == ["Acme/a", "Acme/b"]


def test_nonexistent_org_shows_an_actionable_error_and_saves_nothing(admin):
    response = admin.post("/api/sources", json={"type": "org", "identifier": "Nope"})
    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["code"] == "not_found" and "spelling" in detail["message"]
    assert admin.get("/api/sources").json() == []


def test_invalid_identifiers_and_duplicates_are_rejected(admin):
    assert (
        admin.post("/api/sources", json={"type": "repo", "identifier": "x"}).status_code
        == 422
    )
    assert (
        admin.post(
            "/api/sources", json={"type": "bogus", "identifier": "x"}
        ).status_code
        == 422
    )
    admin.post("/api/sources", json={"type": "org", "identifier": "Acme"})
    again = admin.post("/api/sources", json={"type": "org", "identifier": "acme"})
    assert again.status_code == 409


def test_disable_edit_and_remove_a_source_keeps_repositories(admin):
    source = admin.post(
        "/api/sources", json={"type": "org", "identifier": "Acme"}
    ).json()
    patched = admin.patch(
        f"/api/sources/{source['id']}", json={"enabled": False, "client": "Contoso"}
    )
    assert patched.json()["enabled"] is False and patched.json()["client"] == "Contoso"
    assert admin.delete(f"/api/sources/{source['id']}").status_code == 204
    assert admin.get("/api/sources").json() == []
    assert len(admin.get("/api/repositories").json()) == 2  # retained until pruned
    assert admin.delete("/api/sources/999").status_code == 404


def test_exclude_and_assign_repositories_and_build_the_portfolio(admin):
    admin.post("/api/sources", json={"type": "org", "identifier": "Acme"})
    assert (
        admin.patch(
            "/api/repositories", json={"full_name": "acme/b", "excluded": True}
        ).status_code
        == 200
    )
    admin.patch(
        "/api/repositories",
        json={
            "full_name": "Acme/a",
            "assign": True,
            "client": "Contoso",
            "project": "Website",
            "application": "Public site",
        },
    )
    repos = {r["full_name"]: r for r in admin.get("/api/repositories").json()}
    assert repos["Acme/b"]["excluded"] is True
    assert repos["Acme/a"]["application"] == "Public site"
    tree = admin.get("/api/portfolio").json()
    assert tree[0]["name"] == "Contoso"
    assert tree[0]["projects"][0]["applications"][0]["name"] == "Public site"
    missing = admin.patch(
        "/api/repositories", json={"full_name": "no/such", "excluded": True}
    )
    assert missing.status_code == 404


def test_clients_projects_and_applications_can_be_created_directly(admin):
    c = admin.post("/api/clients", json={"name": "Contoso"}).json()
    p = admin.post(f"/api/clients/{c['id']}/projects", json={"name": "Shop"}).json()
    a = admin.post(f"/api/projects/{p['id']}/applications", json={"name": "Web"})
    assert a.status_code == 201
    assert admin.post("/api/clients", json={"name": "  "}).status_code == 422
    assert (
        admin.post("/api/clients/999/projects", json={"name": "x"}).status_code == 422
    )


# -- connections and secrets -----------------------------------------------------
def test_connection_token_is_validated_encrypted_and_never_returned(admin, db_path):
    created = admin.post(
        "/api/connections",
        json={
            "name": "acme-pat",
            "token": TOKEN,
            "owner": "Acme",
            "expires_at": "2099-01-01",
        },
    )
    assert created.status_code == 201
    body = created.json()
    assert body["has_secret"] is True and body["last_validated_at"]
    assert TOKEN not in created.text and TOKEN not in admin.get("/api/connections").text
    raw = (
        sqlite3.connect(db_path)
        .execute("SELECT secret_encrypted FROM connection")
        .fetchone()[0]
    )
    assert TOKEN not in raw  # ciphertext at rest


def test_invalid_token_is_rejected_with_an_actionable_error(admin):
    response = admin.post("/api/connections", json={"name": "bad", "token": "x" * 40})
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "bad_credentials"
    assert admin.get("/api/connections").json() == []


def test_saving_tokens_needs_an_encryption_key(db_path, fake_world):
    registry = Registry.open(db_path)
    security.create_admin(registry, "admin", PASSWORD)
    registry.close()
    app = create_app(
        db_path,
        secret_box=SecretBox(None),
        github_factory=lambda t: TokenAwareGithub(t, **fake_world),
    )
    c = TestClient(app, base_url="http://testserver")
    c.headers["X-CSRF-Token"] = sign_in(c).json()["csrf_token"]
    response = c.post("/api/connections", json={"name": "n", "token": TOKEN})
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "no_encryption_key"


def test_source_can_use_a_connection_and_deleting_it_detaches(admin):
    conn = admin.post(
        "/api/connections", json={"name": "acme-pat", "token": TOKEN}
    ).json()
    source = admin.post(
        "/api/sources",
        json={"type": "org", "identifier": "Acme", "connection_id": conn["id"]},
    ).json()
    assert source["connection_id"] == conn["id"]
    assert admin.delete(f"/api/connections/{conn['id']}").json() == {
        "detached_sources": 1
    }
    assert admin.get("/api/sources").json()[0]["connection_id"] is None


def test_refresh_request_is_picked_up_once_by_the_worker_side(admin, db_path):
    admin.post("/api/refresh")
    registry = Registry.open(db_path)
    assert registry.pending_refresh() is True
    assert registry.consume_refresh_requests() == 1
    assert registry.consume_refresh_requests() == 0
    registry.close()


# -- credential resolution (used by the worker) -----------------------------------
def test_resolve_token_prefers_the_connection_and_fails_loudly_when_unusable(
    db_path, box
):
    registry = Registry.open(db_path)
    good = connections.create_connection(registry, box, name="good", token=TOKEN)
    expired = connections.create_connection(
        registry, box, name="old", token=TOKEN, expires_at="2020-01-01"
    )
    assert connections.resolve_token(registry, box, {}, default="dflt") == "dflt"
    assert (
        connections.resolve_token(registry, box, {"connection_id": good["id"]}) == TOKEN
    )
    with pytest.raises(SecretError, match="expired"):
        connections.resolve_token(registry, box, {"connection_id": expired["id"]})
    with pytest.raises(SecretError):  # right ciphertext, wrong key
        connections.resolve_token(
            registry, SecretBox(generate_key()), {"connection_id": good["id"]}
        )
    registry.close()


def test_discovery_uses_each_sources_own_token_and_reports_an_expired_connection(
    db_path, box, fake_world
):
    registry = Registry.open(db_path)
    good = connections.create_connection(registry, box, name="good", token=TOKEN)
    old = connections.create_connection(
        registry, box, name="old", token=TOKEN, expires_at="2020-01-01"
    )
    a = registry.add_source("org", "Acme")
    registry.update_source(a["id"], connection_id=good["id"])
    u = registry.add_source("user", "Octo")
    registry.update_source(u["id"], connection_id=old["id"])
    seen = []

    def github_for(source):
        token = connections.resolve_token(registry, box, source, default="dflt")
        seen.append((source["identifier"], token))
        return FakeGithub(**fake_world)

    results = {
        r["source_id"]: r for r in run_discovery(registry, github_for=github_for)
    }

    assert seen == [("Acme", TOKEN)]  # the expired one never reaches GitHub
    assert results[a["id"]]["state"] == "ok"
    assert results[u["id"]]["code"] == "connection_unusable"
    status = {s["identifier"]: s for s in registry.list_sources()}
    assert "Replace the token" in status["Octo"]["error_message"]
    registry.close()
