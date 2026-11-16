"""Tests for the source registry, discovery and portfolio export (ps-003)."""

import json
import sqlite3

import pytest
from github import GithubException

from spark.registry import Registry, collection_users, seed_users
from spark.registry.db import MIGRATIONS, connect, schema_version
from spark.registry.discovery import (
    classify_error,
    discover_source,
    run_discovery,
    validate_access,
)
from spark.registry.export import build_portfolio, write_portfolio
from spark.registry.store import RegistryError, normalize_identifier
from tests.unit.registry_fakes import FakeGithub, Owner, make_repo


@pytest.fixture
def registry(tmp_path):
    reg = Registry.open(tmp_path / "registry.db")
    yield reg
    reg.close()


def names(portfolio):
    return [r["full_name"] for r in portfolio["repositories"]]


# -- migrations -------------------------------------------------------------
def test_migrations_create_schema_and_are_idempotent(tmp_path):
    path = tmp_path / "r.db"
    connect(path).close()
    conn = connect(path)
    assert schema_version(conn) == len(MIGRATIONS)
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master")}
    assert {"source", "repository", "client", "project", "observation"} <= tables
    assert conn.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
    conn.close()


def test_refuses_a_database_from_a_newer_version(tmp_path):
    path = tmp_path / "r.db"
    conn = sqlite3.connect(path)
    conn.execute(f"PRAGMA user_version = {len(MIGRATIONS) + 5}")
    conn.commit()
    conn.close()
    with pytest.raises(RuntimeError, match="newer"):
        connect(path)


def test_registry_survives_reopening_the_database(tmp_path):
    first = Registry.open(tmp_path / "r.db")
    first.add_source("org", "Acme")
    first.close()
    again = Registry.open(tmp_path / "r.db")
    assert [s["identifier"] for s in again.list_sources()] == ["Acme"]
    again.close()


# -- sources ----------------------------------------------------------------
def test_identifiers_are_validated():
    assert normalize_identifier("repo", "Acme/site") == "Acme/site"
    for bad in [("repo", "no-slash"), ("org", "has/slash"), ("user", ""), ("x", "a")]:
        with pytest.raises(RegistryError):
            normalize_identifier(*bad)


def test_adding_a_source_twice_is_case_insensitive_and_idempotent(registry):
    first = registry.add_source("org", "Acme")
    second = registry.add_source("org", "acme")
    assert first["id"] == second["id"]
    assert len(registry.list_sources()) == 1


def test_seed_users_runs_only_on_an_empty_registry(registry):
    assert seed_users(registry, ["Octo", "Hubot"]) == 2
    registry.remove_source(registry.find_source("user", "Hubot")["id"])
    assert seed_users(registry, ["Octo", "Hubot"]) == 0  # restart does not undo
    assert collection_users(registry) == ["Octo"]


# -- discovery and dedupe ---------------------------------------------------
def test_org_plus_explicit_repo_it_contains_yields_one_repository(registry):
    gh = FakeGithub(
        orgs={"Acme": [make_repo("Acme/a"), make_repo("Acme/b")]},
        repos={"acme/A": make_repo("Acme/a")},
    )
    registry.add_source("org", "Acme")
    registry.add_source("repo", "acme/A")
    run_discovery(registry, gh)

    portfolio = build_portfolio(registry)
    assert names(portfolio) == ["Acme/a", "Acme/b"]
    by_name = {r["full_name"]: r for r in portfolio["repositories"]}
    assert by_name["Acme/a"]["sources"] == ["org:Acme", "repo:acme/A"]
    assert by_name["Acme/b"]["sources"] == ["org:Acme"]


def test_every_page_of_a_large_organization_is_collected(registry):
    many = [make_repo(f"Big/r{i:03d}") for i in range(250)]
    registry.add_source("org", "Big")
    result = run_discovery(registry, FakeGithub(orgs={"Big": many}))[0]
    assert result["count"] == 250
    assert build_portfolio(registry)["repository_count"] == 250


def test_new_org_repository_appears_on_the_next_cycle(registry):
    repos = [make_repo("Acme/a")]
    gh = FakeGithub(orgs={"Acme": repos})
    registry.add_source("org", "Acme")
    run_discovery(registry, gh)
    repos.append(make_repo("Acme/new"))
    run_discovery(registry, gh)
    assert names(build_portfolio(registry)) == ["Acme/a", "Acme/new"]


def test_repository_removed_from_org_is_unlinked_but_retained(registry):
    repos = [make_repo("Acme/a"), make_repo("Acme/gone")]
    gh = FakeGithub(orgs={"Acme": repos})
    registry.add_source("org", "Acme")
    run_discovery(registry, gh)
    repos.pop()
    run_discovery(registry, gh)
    assert names(build_portfolio(registry)) == ["Acme/a"]
    assert len(registry.list_repositories()) == 2  # data kept until pruned
    assert registry.prune_orphans() == 1


def test_removing_a_source_keeps_repositories_reached_elsewhere(registry):
    gh = FakeGithub(
        orgs={"Acme": [make_repo("Acme/a"), make_repo("Acme/b")]},
        repos={"Acme/a": make_repo("Acme/a")},
    )
    org = registry.add_source("org", "Acme")
    registry.add_source("repo", "Acme/a")
    run_discovery(registry, gh)

    registry.remove_source(org["id"])

    assert names(build_portfolio(registry)) == ["Acme/a"]  # still reached
    assert len(registry.list_repositories()) == 2  # Acme/b retained, not deleted


def test_disabled_sources_are_skipped_and_hidden(registry):
    gh = FakeGithub(orgs={"Acme": [make_repo("Acme/a")]})
    src = registry.add_source("org", "Acme")
    run_discovery(registry, gh)
    registry.set_source_enabled(src["id"], False)
    assert run_discovery(registry, gh) == []
    assert build_portfolio(registry)["repositories"] == []


def test_exclude_and_include_repositories(registry):
    gh = FakeGithub(orgs={"Acme": [make_repo("Acme/a"), make_repo("Acme/b")]})
    registry.add_source("org", "Acme")
    run_discovery(registry, gh)
    registry.set_repository_excluded("ACME/B", True)
    assert names(build_portfolio(registry)) == ["Acme/a"]
    run_discovery(registry, gh)  # rediscovery must not undo the exclusion
    assert names(build_portfolio(registry)) == ["Acme/a"]
    registry.set_repository_excluded("acme/b", False)
    assert names(build_portfolio(registry)) == ["Acme/a", "Acme/b"]
    with pytest.raises(RegistryError):
        registry.set_repository_excluded("nope/nope", True)


def test_associations_are_optional_and_reflected_in_the_export(registry):
    gh = FakeGithub(orgs={"Acme": [make_repo("Acme/a"), make_repo("Acme/b")]})
    registry.add_source("org", "Acme")
    run_discovery(registry, gh)
    registry.associate_repository(
        "acme/a", client="Contoso", project="Website", application="Public site"
    )
    by_name = {r["full_name"]: r for r in build_portfolio(registry)["repositories"]}
    assert by_name["Acme/a"]["client"] == "Contoso"
    assert by_name["Acme/a"]["project"] == "Website"
    assert by_name["Acme/a"]["application"] == "Public site"
    assert by_name["Acme/b"]["client"] is None  # unassigned is valid


def test_discovery_records_observations_in_the_generic_shape(registry):
    registry.add_source("org", "Acme")
    run_discovery(registry, FakeGithub(orgs={"Acme": [make_repo("Acme/a")]}))
    row = registry.conn.execute(
        "SELECT subject, kind, value, source FROM observation"
    ).fetchone()
    assert tuple(row) == ("source:org:acme", "repository_count", "1", "discovery")


# -- error mapping ----------------------------------------------------------
@pytest.mark.parametrize(
    "status,data,headers,code",
    [
        (404, {"message": "Not Found"}, {}, "not_found"),
        (401, {"message": "Bad credentials"}, {}, "bad_credentials"),
        (403, {"message": "Resource not accessible"}, {}, "no_access"),
        (
            403,
            {"message": "Resource protected by organization SAML"},
            {},
            "sso_required",
        ),
        (403, {"message": "x"}, {"X-GitHub-SSO": "required; url=x"}, "sso_required"),
        (403, {"message": "API rate limit exceeded"}, {}, "rate_limited"),
        (403, {"message": "x"}, {"X-RateLimit-Remaining": "0"}, "rate_limited"),
        (429, {"message": "slow down"}, {}, "rate_limited"),
        (500, {"message": "boom"}, {}, "error"),
    ],
)
def test_github_errors_map_to_actionable_codes(status, data, headers, code):
    problem = classify_error(GithubException(status, data, headers))
    assert problem.code == code
    assert problem.message  # always carries a hint the admin can act on


def test_network_errors_are_classified():
    assert classify_error(ConnectionError("down")).code == "network"


def test_a_bad_source_reports_status_without_blocking_others(registry):
    gh = FakeGithub(orgs={"Good": [make_repo("Good/a")]})
    registry.add_source("org", "Missing")
    registry.add_source("org", "Good")
    results = {r["source_id"]: r for r in run_discovery(registry, gh)}
    status = {s["identifier"]: s for s in registry.list_sources()}
    assert status["Missing"]["state"] == "error"
    assert status["Missing"]["error_code"] == "not_found"
    assert "spelling" in status["Missing"]["error_message"]
    assert status["Good"]["state"] == "ok"
    assert status["Good"]["repository_count"] == 1
    assert len(results) == 2


def test_failed_rediscovery_keeps_previous_links_and_data(registry):
    repos = [make_repo("Acme/a"), make_repo("Acme/b")]
    registry.add_source("org", "Acme")
    run_discovery(registry, FakeGithub(orgs={"Acme": repos}))

    flaky = Owner("Acme", repos, fail_at=1)  # fails after the first repo
    result = run_discovery(registry, FakeGithub(orgs={"Acme": flaky}))[0]

    assert result["state"] == "error"
    assert names(build_portfolio(registry)) == ["Acme/a", "Acme/b"]  # not pruned


def test_validate_access_reports_reason_without_listing(registry):
    gh = FakeGithub(orgs={"Acme": [make_repo("Acme/a")]})
    ok, problem = validate_access(gh, "org", "Acme")
    assert ok and problem is None
    ok, problem = validate_access(gh, "org", "Nope")
    assert not ok and problem.code == "not_found"


def test_discover_source_never_raises(registry):
    src = registry.add_source("user", "ghost")
    result = discover_source(registry, FakeGithub(), src)
    assert result["state"] == "error"


# -- export -----------------------------------------------------------------
def test_portfolio_export_is_versioned_and_includes_source_status(registry, tmp_path):
    registry.add_source("org", "Acme")
    registry.add_source("org", "Missing")
    run_discovery(registry, FakeGithub(orgs={"Acme": [make_repo("Acme/a")]}))
    out = tmp_path / "data" / "portfolio.json"
    write_portfolio(registry, out)
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["schema_version"] == 1
    assert payload["repository_count"] == 1
    states = {s["identifier"]: s["error_code"] for s in payload["sources"]}
    assert states == {"Acme": None, "Missing": "not_found"}
    assert not list(out.parent.glob(".*.tmp"))
