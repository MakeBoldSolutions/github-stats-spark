"""Managed lists (clients, projects, applications) and classification domains."""

import sqlite3

import pytest

from spark.registry import Registry, catalog, domains
from spark.registry.__main__ import main as registry_cli
from spark.registry.db import MIGRATIONS, connect, schema_version
from spark.registry.discovery import run_discovery
from spark.registry.export import build_portfolio
from spark.registry.store import NotFoundError, RegistryError, UnknownNameError
from tests.unit.registry_fakes import FakeGithub, make_repo

REPOS = ["Acme/a", "Acme/b", "Acme/c"]


@pytest.fixture
def registry(tmp_path):
    reg = Registry.open(tmp_path / "registry.db")
    reg.add_source("org", "Acme")
    run_discovery(reg, FakeGithub(orgs={"Acme": [make_repo(n) for n in REPOS]}))
    yield reg
    reg.close()


def held(registry, name):
    repos = {r["full_name"]: r for r in registry.list_repositories()}
    return domains.classifications(registry).get(repos[name]["id"])


# -- migration ------------------------------------------------------------------
def _v3_database(path):
    """A registry as the previous release left it, with free-text names."""
    conn = sqlite3.connect(path)
    for number, script in enumerate(MIGRATIONS[:3]):
        conn.executescript(f"BEGIN;\n{script}\nPRAGMA user_version = {number + 1};")
    stamp = "2026-11-01T00:00:00+00:00"
    conn.executescript(f"""
        INSERT INTO client (id, name, created_at) VALUES
            (1, 'Contoso', '{stamp}'), (2, 'Contoso Corp', '{stamp}');
        INSERT INTO project (id, client_id, name, created_at)
            VALUES (1, 1, 'Website', '{stamp}');
        INSERT INTO application (id, client_id, project_id, name, created_at)
            VALUES (1, 1, 1, 'Public site', '{stamp}');
        INSERT INTO source (id, type, identifier, client_id, created_at)
            VALUES (1, 'org', 'Acme', 2, '{stamp}');
        INSERT INTO repository (id, full_name, full_name_lower, owner, name,
            client_id, project_id, application_id, first_seen_at, last_seen_at)
            VALUES (1, 'Acme/a', 'acme/a', 'Acme', 'a', 1, 1, 1, '{stamp}', '{stamp}');
        INSERT INTO repository_source VALUES (1, 1);
        """)
    conn.commit()
    conn.close()


def test_migration_keeps_existing_names_and_assignments(tmp_path):
    path = tmp_path / "registry.db"
    _v3_database(path)
    registry = Registry.open(path)
    assert schema_version(registry.conn) == len(MIGRATIONS)
    assert (tmp_path / "registry.db.pre-v3.bak").exists()
    repo = registry.list_repositories()[0]
    assert (repo["client"], repo["project"], repo["application"]) == (
        "Contoso",
        "Website",
        "Public site",
    )
    assert registry.get_source(1)["client_id"] == 2
    names = [c["name"] for c in catalog.tree(registry)]
    assert names == ["Contoso", "Contoso Corp"]
    # Near-duplicates are suggested, never merged on their own.
    pair = catalog.duplicates(registry)
    assert [(d["kind"], d["a"]["name"], d["b"]["name"]) for d in pair] == [
        ("client", "Contoso", "Contoso Corp")
    ]
    registry.close()


def test_seeded_domains_and_values():
    registry = Registry(connect(":memory:"))
    seeded = {d["key"]: d for d in domains.list_domains(registry)}
    assert list(seeded) == ["tier", "type", "lifecycle", "stack"]
    assert [v["key"] for v in seeded["tier"]["values"]] == [
        "core",
        "supporting",
        "archive",
    ]
    assert {k: d["multi"] for k, d in seeded.items()} == {
        "tier": False,
        "type": False,
        "lifecycle": False,
        "stack": True,
    }
    assert len(seeded["type"]["values"]) == 7


# -- managed names --------------------------------------------------------------
def test_unknown_names_are_rejected_not_created(registry):
    with pytest.raises(UnknownNameError, match="unknown client 'Contoso'"):
        registry.associate_repository("acme/a", client="Contoso")
    with pytest.raises(UnknownNameError):
        registry.add_source("user", "Octo", client="Contoso")
    with pytest.raises(UnknownNameError):
        registry.update_source(1, client="Contoso")
    assert catalog.tree(registry) == []
    with pytest.raises(NotFoundError):
        registry.associate_repository("no/such")


def test_assignment_follows_the_hierarchy(registry):
    contoso = catalog.create_client(registry, "Contoso")
    fabrikam = catalog.create_client(registry, "Fabrikam")
    web = catalog.create_project(registry, contoso["id"], "Website")
    catalog.create_application(registry, web["id"], "Public site")
    tools = catalog.create_project(registry, None, "Tools")  # internal
    registry.associate_repository(
        "acme/a", client="Contoso", project="Website", application="Public site"
    )
    registry.associate_repository("acme/b", project="Tools")
    # A project is looked up under the chosen client only.
    with pytest.raises(UnknownNameError):
        registry.associate_repository("acme/c", client="Fabrikam", project="Website")
    with pytest.raises(RegistryError, match="belongs to a project"):
        registry.associate_repository("acme/c", application="Public site")
    tree = catalog.tree(registry)
    assert [c["name"] for c in tree] == ["Internal", "Contoso", "Fabrikam"]
    assert tree[0]["projects"][0]["id"] == tools["id"]
    assert tree[1]["repository_count"] == 1 and fabrikam["id"] == tree[2]["id"]


def test_names_are_unique_per_scope_and_trimmed(registry):
    contoso = catalog.create_client(registry, "  Contoso  ")
    assert contoso["name"] == "Contoso"
    with pytest.raises(RegistryError, match="already"):
        catalog.create_client(registry, "contoso")
    other = catalog.create_client(registry, "Fabrikam")
    catalog.create_project(registry, contoso["id"], "Website")
    catalog.create_project(registry, other["id"], "Website")  # other scope: fine
    with pytest.raises(RegistryError, match="already"):
        catalog.update(registry, "client", other["id"], name="CONTOSO")
    for bad in ("", "   ", "x" * 121):
        with pytest.raises(RegistryError):
            catalog.create_client(registry, bad)


def test_retired_entries_leave_pickers_but_stay_where_used(registry):
    contoso = catalog.create_client(registry, "Contoso")
    registry.associate_repository("acme/a", client="Contoso")
    catalog.update(registry, "client", contoso["id"], retired=True)
    assert catalog.tree(registry) == []
    assert catalog.tree(registry, include_retired=True)[0]["retired"] is True
    assert registry.list_repositories()[0]["client"] == "Contoso"
    registry.associate_repository("acme/a", client="Contoso")  # unchanged: allowed
    with pytest.raises(UnknownNameError, match="retired"):
        registry.associate_repository("acme/b", client="Contoso")
    catalog.update(registry, "client", contoso["id"], retired=False)
    registry.associate_repository("acme/b", client="Contoso")


def test_merging_clients_moves_everything_and_retires_the_merged_one(registry):
    keep = catalog.create_client(registry, "Contoso")
    typo = catalog.create_client(registry, "Contosso")
    keep_web = catalog.create_project(registry, keep["id"], "Website")
    typo_web = catalog.create_project(registry, typo["id"], "website")
    catalog.create_application(registry, typo_web["id"], "Shop")
    catalog.create_project(registry, typo["id"], "Docs")
    registry.update_source(1, client="Contosso")
    registry.associate_repository(
        "acme/a", client="Contosso", project="website", application="Shop"
    )
    registry.associate_repository("acme/b", client="Contosso", project="Docs")

    moved = catalog.merge(registry, "client", typo["id"], keep["id"])

    assert moved == {"repositories": 2, "sources": 1}
    repos = {r["full_name"]: r for r in registry.list_repositories()}
    assert (repos["Acme/a"]["client"], repos["Acme/a"]["project"]) == (
        "Contoso",
        "Website",
    )
    assert repos["Acme/a"]["application"] == "Shop"
    assert repos["Acme/b"]["project"] == "Docs"
    assert registry.get_source(1)["client_id"] == keep["id"]
    tree = catalog.tree(registry)
    assert [c["name"] for c in tree] == ["Contoso"]
    projects = {p["name"]: p for p in tree[0]["projects"]}
    assert set(projects) == {"Docs", "Website"}
    assert projects["Website"]["id"] == keep_web["id"]
    assert [a["name"] for a in projects["Website"]["applications"]] == ["Shop"]


def test_merge_is_refused_across_scopes_and_into_itself(registry):
    a = catalog.create_client(registry, "A corp")
    b = catalog.create_client(registry, "B corp")
    pa = catalog.create_project(registry, a["id"], "Web")
    pb = catalog.create_project(registry, b["id"], "Web 2")
    with pytest.raises(RegistryError, match="same client"):
        catalog.merge(registry, "project", pa["id"], pb["id"])
    with pytest.raises(RegistryError, match="different"):
        catalog.merge(registry, "client", a["id"], a["id"])
    catalog.update(registry, "client", b["id"], retired=True)
    with pytest.raises(RegistryError, match="retired"):
        catalog.merge(registry, "client", a["id"], b["id"])
    with pytest.raises(NotFoundError):
        catalog.merge(registry, "client", a["id"], 999)


def test_duplicate_suggestions(registry):
    for name in ("Acme", "Acme, Inc.", "Northwind Traders", "Northwind Trader", "Beta"):
        catalog.create_client(registry, name)
    pairs = {(d["a"]["name"], d["b"]["name"]) for d in catalog.duplicates(registry)}
    assert pairs == {("Acme", "Acme, Inc."), ("Northwind Traders", "Northwind Trader")}


# -- domains ----------------------------------------------------------------------
def test_single_choice_holds_one_value_and_multi_holds_several(registry):
    assert domains.classify(registry, ["acme/a"], "tier", ["core"]) == 1
    with pytest.raises(RegistryError, match="only one"):
        domains.classify(registry, ["acme/a"], "tier", ["core", "archive"])
    with pytest.raises(RegistryError, match="single-choice"):
        domains.classify(registry, ["acme/a"], "tier", ["archive"], mode="add")
    domains.classify(registry, ["acme/a"], "tier", ["archive"])  # replaces
    domains.classify(registry, ["acme/a"], "stack", ["python", "node-react"])
    domains.classify(registry, ["acme/a"], "stack", ["dotnet"], mode="add")
    domains.classify(registry, ["acme/a"], "stack", ["python"], mode="remove")
    assert held(registry, "Acme/a") == {
        "tier": ["archive"],
        "type": [],
        "lifecycle": [],
        "stack": ["dotnet", "node-react"],
    }
    domains.classify(registry, ["acme/a"], "tier", [])  # clears
    assert held(registry, "Acme/a")["tier"] == []


def test_unknown_values_domains_and_repositories_change_nothing(registry):
    with pytest.raises(RegistryError, match="unknown Tier value"):
        domains.classify(registry, ["acme/a"], "tier", ["gold"])
    with pytest.raises(NotFoundError):
        domains.classify(registry, ["acme/a"], "colour", ["red"])
    with pytest.raises(NotFoundError):
        domains.classify(registry, ["acme/a", "no/such"], "tier", ["core"])
    assert held(registry, "Acme/a")["tier"] == []  # the batch was all or nothing


def test_bulk_classification_changes_exactly_the_selected(registry):
    changed = domains.classify(registry, ["acme/a", "ACME/C"], "type", ["website"])
    assert changed == 2
    assert [held(registry, n)["type"] for n in REPOS] == [["website"], [], ["website"]]
    assert domains.classify(registry, ["acme/a"], "type", ["website"]) == 0


def test_retired_values_stay_where_used_but_cannot_be_newly_assigned(registry):
    tier = {d["key"]: d for d in domains.list_domains(registry)}["tier"]
    archive = next(v for v in tier["values"] if v["key"] == "archive")
    domains.classify(registry, ["acme/a"], "tier", ["archive"])
    domains.update_value(registry, archive["id"], retired=True)
    listed = {d["key"]: d for d in domains.list_domains(registry)}["tier"]
    assert "archive" not in [v["key"] for v in listed["values"]]
    assert held(registry, "Acme/a")["tier"] == ["archive"]
    domains.classify(registry, ["acme/a"], "tier", ["archive"])  # kept: allowed
    with pytest.raises(RegistryError, match="retired"):
        domains.classify(registry, ["acme/b"], "tier", ["archive"])


def test_values_in_use_are_retired_not_deleted(registry):
    tier = {d["key"]: d for d in domains.list_domains(registry)}["tier"]
    core, supporting = tier["values"][0], tier["values"][1]
    domains.classify(registry, ["acme/a"], "tier", ["core"])
    with pytest.raises(RegistryError, match="in use"):
        domains.delete_value(registry, core["id"])
    with pytest.raises(RegistryError, match="in use"):
        domains.delete_domain(registry, tier["id"])
    domains.delete_value(registry, supporting["id"])
    keys = [v["key"] for v in domains.list_domains(registry)[0]["values"]]
    assert keys == ["core", "archive"]


def test_custom_domains_and_switching_to_single_choice(registry):
    hosting = domains.create_domain(
        registry, key="Hosting", label="Hosting", multi=True
    )
    assert hosting["key"] == "hosting" and hosting["multi"] is True
    with pytest.raises(RegistryError, match="already exists"):
        domains.create_domain(registry, key="hosting", label="Again")
    with pytest.raises(RegistryError, match="key must be"):
        domains.create_domain(registry, key="bad key", label="Bad")
    for key in ("azure", "pages"):
        domains.add_value(registry, hosting["id"], key=key, label=key.title())
    with pytest.raises(RegistryError, match="already has"):
        domains.add_value(registry, hosting["id"], key="Azure", label="Dup")
    domains.classify(registry, ["acme/a"], "hosting", ["azure", "pages"])
    with pytest.raises(RegistryError, match="several values"):
        domains.update_domain(registry, hosting["id"], multi=False)
    domains.classify(registry, ["acme/a"], "hosting", ["azure"])
    single = domains.update_domain(registry, hosting["id"], multi=False, label="Host")
    assert single["multi"] is False and single["label"] == "Host"
    renamed = domains.update_value(registry, single["values"][0]["id"], label="Azure")
    assert renamed["key"] == "azure"  # keys are stable; labels change freely
    domains.update_domain(registry, hosting["id"], retired=True)
    assert "hosting" not in held(registry, "Acme/a")
    with pytest.raises(RegistryError, match="retired"):
        domains.classify(registry, ["acme/b"], "hosting", ["azure"])


def test_export_carries_classifications_and_explicit_unassigned(registry):
    domains.classify(registry, ["acme/a"], "stack", ["python"])
    portfolio = build_portfolio(registry)
    by_name = {r["full_name"]: r for r in portfolio["repositories"]}
    assert by_name["Acme/a"]["classifications"]["stack"] == ["python"]
    assert by_name["Acme/b"]["classifications"] == {
        "tier": [],
        "type": [],
        "lifecycle": [],
        "stack": [],
    }
    catalog_keys = [d["key"] for d in portfolio["domains"]]
    assert catalog_keys == ["tier", "type", "lifecycle", "stack"]
    stack = portfolio["domains"][3]
    assert stack["multi"] is True and stack["values"][0]["label"] == ".NET"


def test_pruning_a_repository_removes_its_classification(registry):
    domains.classify(registry, ["acme/a"], "tier", ["core"])
    registry.remove_source(1)
    assert registry.prune_orphans() == 3
    rows = registry.conn.execute("SELECT COUNT(*) FROM repository_classification")
    assert rows.fetchone()[0] == 0


# -- CLI --------------------------------------------------------------------------
def test_cli_rejects_unknown_names_unless_asked_to_create(tmp_path, capsys):
    db = str(tmp_path / "cli.db")
    seeded = Registry.open(db)
    seeded.add_source("org", "Acme")
    run_discovery(seeded, FakeGithub(orgs={"Acme": [make_repo("Acme/a")]}))
    seeded.close()
    assign = ["--db", db, "assign", "Acme/a", "--client", "Contoso"]
    assert registry_cli([*assign, "--project", "Web"]) == 2
    assert "unknown client" in capsys.readouterr().err
    assert registry_cli([*assign, "--project", "Web", "--create"]) == 0
    assert "created client 'Contoso'" in capsys.readouterr().out
    assert registry_cli([*assign, "--project", "web", "--create"]) == 0  # reused
    add = ["--db", db, "add", "user", "Octo", "--no-validate", "--client", "Fabrikam"]
    assert registry_cli(add) == 2
    assert registry_cli([*add, "--create"]) == 0
    check = Registry.open(db)
    assert check.list_repositories()[0]["project"] == "Web"
    assert len(catalog.tree(check)[0]["projects"]) == 1
    check.close()
