"""Admin API routes for managed lists and classification domains."""

import pytest
from fastapi.testclient import TestClient

from spark.api import security
from spark.api.app import create_app
from spark.registry import Registry
from spark.registry.secrets import SecretBox, generate_key
from tests.unit.registry_fakes import make_repo
from tests.unit.test_api import PASSWORD, TokenAwareGithub


@pytest.fixture
def admin(tmp_path):
    db_path = tmp_path / "registry.db"
    registry = Registry.open(db_path)
    security.create_admin(registry, "admin", PASSWORD)
    registry.close()
    world = dict(orgs={"Acme": [make_repo("Acme/a"), make_repo("Acme/b")]})
    app = create_app(
        db_path,
        secret_box=SecretBox(generate_key()),
        github_factory=lambda token: TokenAwareGithub(token, **world),
        default_token="default-token",
    )
    client = TestClient(app, base_url="http://testserver")
    signed_in = client.post(
        "/api/session", json={"username": "admin", "password": PASSWORD}
    )
    client.headers["X-CSRF-Token"] = signed_in.json()["csrf_token"]
    client.post("/api/sources", json={"type": "org", "identifier": "Acme"})
    return client


def detail(response):
    return response.json()["detail"]


def test_new_routes_require_sign_in(tmp_path):
    app = create_app(tmp_path / "r.db")
    client = TestClient(app, base_url="http://testserver")
    for method, path in [
        ("get", "/api/portfolio/duplicates"),
        ("get", "/api/domains"),
        ("post", "/api/domains"),
        ("patch", "/api/domains/1"),
        ("delete", "/api/domains/1"),
        ("post", "/api/domains/1/values"),
        ("patch", "/api/domain-values/1"),
        ("delete", "/api/domain-values/1"),
        ("post", "/api/repositories/classify"),
        ("post", "/api/projects"),
        ("patch", "/api/clients/1"),
        ("post", "/api/clients/1/merge"),
        ("patch", "/api/projects/1"),
        ("post", "/api/applications/1/merge"),
    ]:
        assert getattr(client, method)(path).status_code == 401, (method, path)


def test_writes_require_the_csrf_token(admin):
    del admin.headers["X-CSRF-Token"]
    response = admin.post("/api/domains", json={"key": "x", "label": "X"})
    assert response.status_code == 403


def test_list_entries_can_be_renamed_retired_and_merged(admin):
    keep = admin.post("/api/clients", json={"name": "Contoso"}).json()
    typo = admin.post("/api/clients", json={"name": "Contoso Inc"}).json()
    internal = admin.post("/api/projects", json={"name": "Tools"})
    assert internal.status_code == 201 and internal.json()["client_id"] is None
    pairs = admin.get("/api/portfolio/duplicates").json()
    assert pairs[0]["a"]["id"] == keep["id"] and pairs[0]["b"]["id"] == typo["id"]

    admin.patch("/api/sources/1", json={"client": "Contoso Inc"})
    merged = admin.post(
        f"/api/clients/{typo['id']}/merge", json={"into_id": keep["id"]}
    )
    assert merged.json() == {"repositories": 0, "sources": 1}
    assert admin.get("/api/sources").json()[0]["client"] == "Contoso"
    names = [c["name"] for c in admin.get("/api/portfolio").json()]
    assert names == ["Internal", "Contoso"]
    everything = admin.get("/api/portfolio", params={"include_retired": True}).json()
    assert [c["retired"] for c in everything] == [False, False, True]

    renamed = admin.patch(f"/api/clients/{keep['id']}", json={"name": "Contoso Ltd"})
    assert renamed.json()["name"] == "Contoso Ltd"
    clash = admin.patch(f"/api/clients/{keep['id']}", json={"name": "contoso inc"})
    assert clash.status_code == 422 and detail(clash)["code"] == "invalid"
    retired = admin.patch(f"/api/clients/{keep['id']}", json={"retired": True})
    assert retired.json()["retired"] is True
    assert admin.patch("/api/clients/999", json={"name": "x"}).status_code == 404
    same = admin.post(f"/api/clients/{keep['id']}/merge", json={"into_id": keep["id"]})
    assert same.status_code == 422


def test_unknown_client_on_a_new_source_is_rejected_before_saving(admin):
    response = admin.post(
        "/api/sources", json={"type": "user", "identifier": "Octo", "client": "Nope"}
    )
    assert response.status_code == 422 and detail(response)["code"] == "unknown_name"
    assert [s["identifier"] for s in admin.get("/api/sources").json()] == ["Acme"]


def test_domains_can_be_managed(admin):
    seeded = admin.get("/api/domains").json()
    assert [d["key"] for d in seeded] == ["tier", "type", "lifecycle", "stack"]
    created = admin.post(
        "/api/domains", json={"key": "hosting", "label": "Hosting", "multi": True}
    )
    assert created.status_code == 201
    domain_id = created.json()["id"]
    value = admin.post(
        f"/api/domains/{domain_id}/values", json={"key": "azure", "label": "Azure"}
    ).json()
    assert value["repository_count"] == 0
    edited = admin.patch(f"/api/domain-values/{value['id']}", json={"label": "AZ"})
    assert edited.json()["label"] == "AZ"
    bad = admin.post("/api/domains", json={"key": "has space", "label": "X"})
    assert bad.status_code == 422
    assert admin.delete(f"/api/domain-values/{value['id']}").status_code == 204
    retired = admin.patch(f"/api/domains/{domain_id}", json={"retired": True})
    assert retired.json()["retired"] is True
    assert "hosting" not in [d["key"] for d in admin.get("/api/domains").json()]
    listed = admin.get("/api/domains", params={"include_retired": True}).json()
    assert "hosting" in [d["key"] for d in listed]
    assert admin.delete(f"/api/domains/{domain_id}").status_code == 204
    assert admin.delete(f"/api/domains/{domain_id}").status_code == 404


def test_repositories_are_classified_singly_and_in_bulk(admin):
    bulk = admin.post(
        "/api/repositories/classify",
        json={"full_names": ["Acme/a", "Acme/b"], "domain": "type", "values": ["api"]},
    )
    assert bulk.json() == {"changed": 2}
    admin.post(
        "/api/repositories/classify",
        json={"full_names": ["Acme/a"], "domain": "stack", "values": ["python"]},
    )
    repos = {r["full_name"]: r for r in admin.get("/api/repositories").json()}
    assert repos["Acme/a"]["classifications"] == {
        "tier": [],
        "type": ["api"],
        "lifecycle": [],
        "stack": ["python"],
    }
    assert repos["Acme/b"]["classifications"]["stack"] == []
    two = admin.post(
        "/api/repositories/classify",
        json={
            "full_names": ["Acme/a"],
            "domain": "tier",
            "values": ["core", "archive"],
        },
    )
    assert two.status_code == 422
    missing = admin.post(
        "/api/repositories/classify",
        json={"full_names": ["no/such"], "domain": "tier", "values": ["core"]},
    )
    assert missing.status_code == 404
    empty = admin.post(
        "/api/repositories/classify",
        json={"full_names": [], "domain": "tier", "values": []},
    )
    assert empty.status_code == 422
