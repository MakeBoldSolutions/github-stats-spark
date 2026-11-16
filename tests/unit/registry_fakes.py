"""In-memory stand-ins for the parts of PyGithub that discovery uses."""

from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Dict, List, Optional

from github import GithubException


def make_repo(full_name: str, **overrides):
    values = dict(
        full_name=full_name,
        description=None,
        language="Python",
        html_url=f"https://github.com/{full_name}",
        default_branch="main",
        pushed_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        fork=False,
        private=False,
        archived=False,
    )
    values.update(overrides)
    return SimpleNamespace(**values)


class Owner:
    def __init__(self, login: str, repos: List, fail_at: Optional[int] = None):
        self.login = login
        self._repos = repos
        self._fail_at = fail_at

    def get_repos(self, **_kwargs):
        # Yield lazily so a mid-listing failure behaves like a failing page.
        for index, repo in enumerate(self._repos):
            if self._fail_at is not None and index == self._fail_at:
                raise GithubException(502, {"message": "Bad Gateway"}, {})
            yield repo


class FakeGithub:
    """``orgs``/``users`` map login -> list of repos or an exception."""

    def __init__(
        self,
        orgs: Optional[Dict] = None,
        users: Optional[Dict] = None,
        repos: Optional[Dict] = None,
    ):
        self.orgs = orgs or {}
        self.users = users or {}
        self.repo_map = repos or {}
        self.calls: List[str] = []

    def _lookup(self, table: Dict, key: str, kind: str):
        self.calls.append(f"{kind}:{key}")
        for name, value in table.items():
            if name.lower() == key.lower():
                if isinstance(value, Exception):
                    raise value
                return value
        raise GithubException(404, {"message": "Not Found"}, {})

    def get_organization(self, login):
        value = self._lookup(self.orgs, login, "org")
        return value if isinstance(value, Owner) else Owner(login, value)

    def get_user(self, login):
        value = self._lookup(self.users, login, "user")
        return value if isinstance(value, Owner) else Owner(login, value)

    def get_repo(self, full_name):
        return self._lookup(self.repo_map, full_name, "repo")
