"""Unit tests for staged GitHub REST API version behavior."""

from types import SimpleNamespace

import pytest

from spark.cache import APICache
from spark.fetcher import GitHubFetcher


class DummyResponse:
    def __init__(self, status_code):
        self.status_code = status_code

    def json(self):
        return {}


@pytest.fixture
def fetcher(tmp_path, monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "test-token")
    cache = APICache(cache_dir=str(tmp_path / "cache"))
    return GitHubFetcher(
        cache=cache,
        api_version_settings={
            "enabled": True,
            "version": "2026-03-10",
            "fallback_to_default": True,
        },
    )


def test_build_rest_headers_with_version(fetcher):
    headers = fetcher._build_rest_headers(include_version=True)
    assert headers["Authorization"].startswith("Bearer ")
    assert headers["X-GitHub-Api-Version"] == "2026-03-10"


def test_build_rest_headers_without_version(fetcher):
    headers = fetcher._build_rest_headers(include_version=False)
    assert "X-GitHub-Api-Version" not in headers


def test_rest_get_falls_back_without_version(fetcher, monkeypatch):
    calls = []

    def fake_get(url, headers=None, params=None, timeout=30):
        calls.append(headers)
        if len(calls) == 1:
            return DummyResponse(400)
        return DummyResponse(200)

    monkeypatch.setattr("spark.fetcher.requests.get", fake_get)

    response = fetcher._rest_get("/repos/markhazleton/github-stats-spark")

    assert response.status_code == 200
    assert len(calls) == 2
    assert "X-GitHub-Api-Version" in calls[0]
    assert "X-GitHub-Api-Version" not in calls[1]


def test_rest_get_no_fallback_when_disabled(tmp_path, monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "test-token")
    cache = APICache(cache_dir=str(tmp_path / "cache-no-fallback"))
    fetcher = GitHubFetcher(
        cache=cache,
        api_version_settings={
            "enabled": True,
            "version": "2026-03-10",
            "fallback_to_default": False,
        },
    )

    monkeypatch.setattr(
        "spark.fetcher.requests.get", lambda *args, **kwargs: DummyResponse(400)
    )

    response = fetcher._rest_get("/repos/markhazleton/github-stats-spark")

    assert response.status_code == 400


def test_fetcher_initializes_github_with_auth_token(tmp_path, monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "token-from-env")
    cache = APICache(cache_dir=str(tmp_path / "cache-auth"))
    captured = {}

    monkeypatch.setattr("spark.fetcher.Auth.Token", lambda token: f"auth:{token}")

    def fake_github(*args, **kwargs):
        captured["args"] = args
        captured["kwargs"] = kwargs
        return SimpleNamespace()

    monkeypatch.setattr("spark.fetcher.Github", fake_github)

    GitHubFetcher(cache=cache)

    assert captured["args"] == ()
    assert captured["kwargs"]["auth"] == "auth:token-from-env"
