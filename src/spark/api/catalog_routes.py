"""Admin routes for managed lists (clients, projects, applications) and
classification domains. Mounted by ``create_app``, which supplies the
registry and signed-in-administrator dependencies."""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from spark.registry import Registry, catalog, domains
from spark.registry.store import NotFoundError, RegistryError, UnknownNameError


class NameIn(BaseModel):
    name: str = Field(max_length=120)


class ProjectIn(BaseModel):
    name: str = Field(max_length=120)
    client_id: Optional[int] = None


class ListPatch(BaseModel):
    name: Optional[str] = Field(default=None, max_length=120)
    retired: Optional[bool] = None


class MergeIn(BaseModel):
    into_id: int


class DomainIn(BaseModel):
    key: str = Field(max_length=40)
    label: str = Field(max_length=80)
    description: Optional[str] = Field(default=None, max_length=300)
    multi: bool = False


class DomainPatch(BaseModel):
    label: Optional[str] = Field(default=None, max_length=80)
    description: Optional[str] = Field(default=None, max_length=300)
    multi: Optional[bool] = None
    retired: Optional[bool] = None
    sort_order: Optional[int] = None


class ValueIn(BaseModel):
    key: str = Field(max_length=40)
    label: str = Field(max_length=80)
    description: Optional[str] = Field(default=None, max_length=300)


class ValuePatch(BaseModel):
    label: Optional[str] = Field(default=None, max_length=80)
    description: Optional[str] = Field(default=None, max_length=300)
    retired: Optional[bool] = None
    sort_order: Optional[int] = None


class ClassifyIn(BaseModel):
    full_names: List[str] = Field(min_length=1, max_length=1000)
    domain: str = Field(max_length=40)
    values: List[str] = Field(default_factory=list, max_length=50)
    mode: str = "set"


def http_error(error: RegistryError) -> HTTPException:
    """Missing record -> 404; unknown name -> 422 ``unknown_name``; any other
    invalid input -> 422 ``invalid``."""
    if isinstance(error, NotFoundError):
        return HTTPException(404, {"code": "not_found", "message": str(error)})
    code = "unknown_name" if isinstance(error, UnknownNameError) else "invalid"
    return HTTPException(422, {"code": code, "message": str(error)})


def build_router(admin: Any, get_registry: Callable[..., Any]) -> APIRouter:
    router = APIRouter()
    registry_dep = Depends(get_registry)

    def run(action: Callable[[], Any]) -> Any:
        try:
            return action()
        except RegistryError as error:
            raise http_error(error) from error

    # -- managed lists ----------------------------------------------------------
    @router.get("/api/portfolio")
    def portfolio(
        include_retired: bool = False,
        session=admin,
        registry: Registry = registry_dep,
    ) -> List[Dict[str, Any]]:
        return catalog.tree(registry, include_retired=include_retired)

    @router.get("/api/portfolio/duplicates")
    def duplicates(
        session=admin, registry: Registry = registry_dep
    ) -> List[Dict[str, Any]]:
        return catalog.duplicates(registry)

    @router.post("/api/clients", status_code=201)
    def add_client(
        body: NameIn, session=admin, registry: Registry = registry_dep
    ) -> Dict[str, Any]:
        return run(lambda: catalog.create_client(registry, body.name))

    @router.post("/api/projects", status_code=201)
    def add_project(
        body: ProjectIn, session=admin, registry: Registry = registry_dep
    ) -> Dict[str, Any]:
        return run(lambda: catalog.create_project(registry, body.client_id, body.name))

    @router.post("/api/clients/{client_id}/projects", status_code=201)
    def add_client_project(
        client_id: int, body: NameIn, session=admin, registry: Registry = registry_dep
    ) -> Dict[str, Any]:
        try:
            return catalog.create_project(registry, client_id, body.name)
        except RegistryError as error:  # an unknown parent is invalid input here
            raise HTTPException(
                422, {"code": "invalid", "message": str(error)}
            ) from error

    @router.post("/api/projects/{project_id}/applications", status_code=201)
    def add_application(
        project_id: int, body: NameIn, session=admin, registry: Registry = registry_dep
    ) -> Dict[str, Any]:
        try:
            return catalog.create_application(registry, project_id, body.name)
        except RegistryError as error:
            raise HTTPException(
                422, {"code": "invalid", "message": str(error)}
            ) from error

    for kind, plural in (
        ("client", "clients"),
        ("project", "projects"),
        ("application", "applications"),
    ):
        _list_entry_routes(router, admin, registry_dep, run, kind, plural)

    # -- domains -------------------------------------------------------------------
    @router.get("/api/domains")
    def list_domains(
        include_retired: bool = False,
        session=admin,
        registry: Registry = registry_dep,
    ) -> List[Dict[str, Any]]:
        return domains.list_domains(registry, include_retired=include_retired)

    @router.post("/api/domains", status_code=201)
    def add_domain(
        body: DomainIn, session=admin, registry: Registry = registry_dep
    ) -> Dict[str, Any]:
        return run(lambda: domains.create_domain(registry, **body.model_dump()))

    @router.patch("/api/domains/{domain_id}")
    def edit_domain(
        domain_id: int,
        body: DomainPatch,
        session=admin,
        registry: Registry = registry_dep,
    ) -> Dict[str, Any]:
        return run(
            lambda: domains.update_domain(
                registry, domain_id, **body.model_dump(exclude_none=True)
            )
        )

    @router.delete("/api/domains/{domain_id}", status_code=204)
    def remove_domain(
        domain_id: int, session=admin, registry: Registry = registry_dep
    ) -> None:
        run(lambda: domains.delete_domain(registry, domain_id))

    @router.post("/api/domains/{domain_id}/values", status_code=201)
    def add_value(
        domain_id: int,
        body: ValueIn,
        session=admin,
        registry: Registry = registry_dep,
    ) -> Dict[str, Any]:
        return run(lambda: domains.add_value(registry, domain_id, **body.model_dump()))

    @router.patch("/api/domain-values/{value_id}")
    def edit_value(
        value_id: int,
        body: ValuePatch,
        session=admin,
        registry: Registry = registry_dep,
    ) -> Dict[str, Any]:
        return run(
            lambda: domains.update_value(
                registry, value_id, **body.model_dump(exclude_none=True)
            )
        )

    @router.delete("/api/domain-values/{value_id}", status_code=204)
    def remove_value(
        value_id: int, session=admin, registry: Registry = registry_dep
    ) -> None:
        run(lambda: domains.delete_value(registry, value_id))

    @router.post("/api/repositories/classify")
    def classify(
        body: ClassifyIn, session=admin, registry: Registry = registry_dep
    ) -> Dict[str, int]:
        changed = run(
            lambda: domains.classify(
                registry, body.full_names, body.domain, body.values, body.mode
            )
        )
        return {"changed": changed}

    return router


def _list_entry_routes(router, admin, registry_dep, run, kind, plural) -> None:
    """Rename/retire/restore and merge for one kind of managed list entry."""

    def edit(
        item_id: int, body: ListPatch, session=admin, registry: Registry = registry_dep
    ) -> Dict[str, Any]:
        return run(
            lambda: catalog.update(
                registry, kind, item_id, name=body.name, retired=body.retired
            )
        )

    def merge(
        item_id: int, body: MergeIn, session=admin, registry: Registry = registry_dep
    ) -> Dict[str, int]:
        return run(lambda: catalog.merge(registry, kind, item_id, body.into_id))

    router.add_api_route(
        f"/api/{plural}/{{item_id}}", edit, methods=["PATCH"], name=f"edit_{kind}"
    )
    router.add_api_route(
        f"/api/{plural}/{{item_id}}/merge",
        merge,
        methods=["POST"],
        name=f"merge_{kind}",
    )
