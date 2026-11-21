"""The administration API: a thin layer over the registry modules.

Every route except ``/api/health`` and sign-in requires a valid session;
state-changing routes also require the session's CSRF token and a matching
Origin. Credentials are accepted but never returned.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Callable, Dict, Iterator, List, Optional
from urllib.parse import urlparse

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from github import Auth, Github
from pydantic import BaseModel, Field

from spark.api import security
from spark.api.catalog_routes import build_router, http_error
from spark.registry import Registry, connections, domains
from spark.registry.discovery import (
    ERROR_HINTS,
    classify_error,
    discover_source,
    validate_access,
)
from spark.registry.secrets import SecretBox, SecretError
from spark.registry.store import RegistryError, normalize_identifier

COOKIE = "spark_session"


def default_github(token: str):
    return Github(auth=Auth.Token(token), timeout=30) if token else Github(timeout=30)


class Credentials(BaseModel):
    username: str = Field(max_length=64)
    password: str = Field(max_length=256)


class SourceIn(BaseModel):
    type: str
    identifier: str = Field(max_length=140)
    client: Optional[str] = Field(default=None, max_length=120)
    connection_id: Optional[int] = None


class SourcePatch(BaseModel):
    enabled: Optional[bool] = None
    client: Optional[str] = Field(default=None, max_length=120)
    connection_id: Optional[int] = None
    clear_connection: bool = False


class RepositoryPatch(BaseModel):
    full_name: str = Field(max_length=200)
    excluded: Optional[bool] = None
    assign: bool = False
    client: Optional[str] = Field(default=None, max_length=120)
    project: Optional[str] = Field(default=None, max_length=120)
    application: Optional[str] = Field(default=None, max_length=120)


class ConnectionIn(BaseModel):
    name: str = Field(max_length=80)
    token: str = Field(max_length=300)
    owner: Optional[str] = Field(default=None, max_length=80)
    expires_at: Optional[str] = Field(default=None, max_length=40)


def create_app(
    db_path: Path,
    *,
    secret_box: Optional[SecretBox] = None,
    github_factory: Callable[[str], Any] = default_github,
    default_token: Optional[str] = None,
    cookie_secure: bool = False,
    session_hours: float = 12,
    throttle: Optional[security.LoginThrottle] = None,
) -> FastAPI:
    box = secret_box or SecretBox(None)
    throttle = throttle or security.LoginThrottle()
    app = FastAPI(title="Stats Spark admin API", docs_url=None, redoc_url=None)

    # -- plumbing -----------------------------------------------------------
    def get_registry() -> Iterator[Registry]:
        registry = Registry.open(db_path)
        try:
            yield registry
        finally:
            registry.close()

    def fallback_token() -> str:
        return (
            default_token
            if default_token is not None
            else os.environ.get("GITHUB_TOKEN", "")
        )

    @app.middleware("http")
    async def harden(request: Request, call_next):
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        return response

    def require_admin(
        request: Request, registry: Registry = Depends(get_registry)
    ) -> Dict[str, str]:
        session = security.lookup_session(registry, request.cookies.get(COOKIE))
        if not session:
            raise HTTPException(401, "sign in required")
        if request.method not in ("GET", "HEAD", "OPTIONS"):
            origin = request.headers.get("origin")
            if origin and urlparse(origin).netloc != request.headers.get("host"):
                raise HTTPException(403, "cross-origin request refused")
            if not security.csrf_matches(
                session["csrf_token"], request.headers.get("x-csrf-token")
            ):
                raise HTTPException(403, "missing or invalid CSRF token")
        return session

    def bad_request(error: Exception, status: int = 422) -> HTTPException:
        return HTTPException(status, {"code": "invalid", "message": str(error)})

    def token_for(registry: Registry, connection_id: Optional[int]) -> str:
        source = {"connection_id": connection_id}
        try:
            return connections.resolve_token(
                registry, box, source, default=fallback_token()
            )
        except SecretError as error:
            raise HTTPException(
                422,
                {
                    "code": "connection_unusable",
                    "message": f"{ERROR_HINTS['connection_unusable']} ({error})",
                },
            ) from error

    def present_source(registry: Registry, source: Dict[str, Any]) -> Dict[str, Any]:
        client = None
        if source.get("client_id"):
            row = registry.conn.execute(
                "SELECT name FROM client WHERE id = ?", (source["client_id"],)
            ).fetchone()
            client = row[0] if row else None
        return {
            **{
                key: source[key]
                for key in (
                    "id",
                    "type",
                    "identifier",
                    "state",
                    "error_code",
                    "error_message",
                    "repository_count",
                    "last_discovery_at",
                    "connection_id",
                )
            },
            "enabled": bool(source["enabled"]),
            "client": client,
        }

    admin = Depends(require_admin)

    # -- public ---------------------------------------------------------------
    @app.get("/api/health")
    def health() -> Dict[str, Any]:
        return {"ok": True}

    @app.post("/api/session")
    def sign_in(
        body: Credentials,
        response: Response,
        registry: Registry = Depends(get_registry),
    ) -> Dict[str, Any]:
        if throttle.blocked(body.username):
            raise HTTPException(429, "too many failed sign-ins; try again later")
        user_id = security.authenticate(registry, body.username, body.password)
        if user_id is None:
            throttle.fail(body.username)
            raise HTTPException(401, "invalid username or password")
        throttle.reset(body.username)
        token, csrf = security.create_session(registry, user_id, session_hours)
        response.set_cookie(
            COOKIE,
            token,
            max_age=int(session_hours * 3600),
            httponly=True,
            samesite="strict",
            secure=cookie_secure,
            path="/api",
        )
        return {"username": body.username, "csrf_token": csrf}

    # -- session --------------------------------------------------------------
    @app.get("/api/session")
    def whoami(session=admin) -> Dict[str, Any]:
        return {
            "username": session["username"],
            "csrf_token": session["csrf_token"],
            "encryption_available": box.available,
        }

    @app.delete("/api/session", status_code=204)
    def sign_out(
        request: Request,
        response: Response,
        session=admin,
        registry: Registry = Depends(get_registry),
    ) -> None:
        security.end_session(registry, request.cookies.get(COOKIE))
        response.delete_cookie(COOKIE, path="/api")

    # -- sources --------------------------------------------------------------
    @app.get("/api/sources")
    def list_sources(
        session=admin, registry: Registry = Depends(get_registry)
    ) -> List[Dict[str, Any]]:
        return [present_source(registry, s) for s in registry.list_sources()]

    @app.post("/api/sources", status_code=201)
    def add_source(
        body: SourceIn,
        session=admin,
        registry: Registry = Depends(get_registry),
    ) -> Dict[str, Any]:
        try:
            identifier = normalize_identifier(body.type, body.identifier)
            registry.client_id_for(body.client)
        except RegistryError as error:
            raise http_error(error) from error
        existing = registry.find_source(body.type, identifier)
        if existing:
            raise HTTPException(
                409,
                {"code": "duplicate", "message": "that source is already registered"},
            )
        if body.connection_id is not None:
            try:
                connections.get_connection(registry, body.connection_id)
            except RegistryError as error:
                raise bad_request(error) from error
        token = token_for(registry, body.connection_id)
        # Validate first: a source that cannot be read is not saved.
        _, problem = validate_access(github_factory(token), body.type, identifier)
        if problem is not None:
            raise HTTPException(422, {"code": problem.code, "message": problem.message})
        source = registry.add_source(body.type, identifier, client=body.client)
        if body.connection_id is not None:
            source = registry.update_source(
                source["id"], connection_id=body.connection_id
            )
        # Discover now so the admin sees the repositories immediately.
        discover_source(registry, github_factory(token), source)
        return present_source(registry, registry.get_source(source["id"]))

    @app.patch("/api/sources/{source_id}")
    def edit_source(
        source_id: int,
        body: SourcePatch,
        session=admin,
        registry: Registry = Depends(get_registry),
    ) -> Dict[str, Any]:
        try:
            source = registry.get_source(source_id)
            # Check the client before changing anything, so a rejected
            # request leaves the source as it was.
            registry.client_id_for(body.client, current=source["client_id"])
            if body.enabled is not None:
                registry.set_source_enabled(source_id, body.enabled)
            if (
                body.client is not None
                or body.connection_id is not None
                or body.clear_connection
            ):
                registry.update_source(
                    source_id,
                    client=body.client,
                    connection_id=body.connection_id,
                    clear_connection=body.clear_connection,
                )
            return present_source(registry, registry.get_source(source_id))
        except RegistryError as error:
            raise http_error(error) from error

    @app.delete("/api/sources/{source_id}", status_code=204)
    def remove_source(
        source_id: int, session=admin, registry: Registry = Depends(get_registry)
    ) -> None:
        try:
            registry.remove_source(source_id)
        except RegistryError as error:
            raise HTTPException(
                404, {"code": "not_found", "message": str(error)}
            ) from error

    # -- repositories and portfolio ------------------------------------------------
    @app.get("/api/repositories")
    def list_repositories(
        session=admin, registry: Registry = Depends(get_registry)
    ) -> List[Dict[str, Any]]:
        keep = (
            "full_name",
            "description",
            "language",
            "html_url",
            "is_fork",
            "is_private",
            "is_archived",
            "excluded",
            "client",
            "project",
            "application",
            "sources",
        )
        flags = ("is_fork", "is_private", "is_archived", "excluded")
        classified = domains.classifications(registry)
        return [
            {
                **{key: bool(repo[key]) if key in flags else repo[key] for key in keep},
                "classifications": classified.get(repo["id"]),
            }
            for repo in registry.list_repositories()
        ]

    @app.patch("/api/repositories")
    def edit_repository(
        body: RepositoryPatch,
        session=admin,
        registry: Registry = Depends(get_registry),
    ) -> Dict[str, bool]:
        try:
            # The assignment is validated (and rejected) before anything is
            # written, so a refused request leaves the repository unchanged.
            if body.assign:
                registry.associate_repository(
                    body.full_name,
                    client=body.client or None,
                    project=body.project or None,
                    application=body.application or None,
                )
            if body.excluded is not None:
                registry.set_repository_excluded(body.full_name, body.excluded)
        except RegistryError as error:
            raise http_error(error) from error
        return {"ok": True}

    app.include_router(build_router(admin, get_registry))

    # -- connections -----------------------------------------------------------
    @app.get("/api/connections")
    def list_connections(
        session=admin, registry: Registry = Depends(get_registry)
    ) -> List[Dict[str, Any]]:
        return connections.list_connections(registry)

    @app.post("/api/connections", status_code=201)
    def add_connection(
        body: ConnectionIn,
        session=admin,
        registry: Registry = Depends(get_registry),
    ) -> Dict[str, Any]:
        if not box.available:
            raise HTTPException(
                409,
                {
                    "code": "no_encryption_key",
                    "message": "Set SPARK_SECRET_KEY on the API and worker before "
                    "saving tokens (python -m spark.api generate-key).",
                },
            )
        try:
            github_factory(
                body.token
            ).get_user().login  # noqa: B018 - proves the token works
        except Exception as error:  # noqa: BLE001
            problem = classify_error(error)
            raise HTTPException(
                422, {"code": problem.code, "message": problem.message}
            ) from error
        try:
            created = connections.create_connection(
                registry,
                box,
                name=body.name,
                token=body.token,
                owner=body.owner,
                expires_at=body.expires_at,
            )
        except RegistryError as error:
            raise bad_request(error) from error
        connections.mark_validated(registry, created["id"])
        return connections.get_connection(registry, created["id"])

    @app.delete("/api/connections/{connection_id}")
    def remove_connection(
        connection_id: int,
        session=admin,
        registry: Registry = Depends(get_registry),
    ) -> Dict[str, int]:
        try:
            return {
                "detached_sources": connections.delete_connection(
                    registry, connection_id
                )
            }
        except RegistryError as error:
            raise HTTPException(
                404, {"code": "not_found", "message": str(error)}
            ) from error

    # -- refresh --------------------------------------------------------------
    @app.post("/api/refresh", status_code=202)
    def refresh(
        session=admin, registry: Registry = Depends(get_registry)
    ) -> Dict[str, Any]:
        """Ask the worker to collect now; the worker picks this up within seconds."""
        request_id = registry.request_refresh()
        return {"requested": True, "id": request_id}

    return app
