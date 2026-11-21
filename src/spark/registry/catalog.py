"""Managed lists: clients, projects and applications.

Names are created here, deliberately, and nowhere else. An entry can be
renamed, retired (hidden from pickers but kept on whatever already uses it),
restored, or merged into another entry of the same kind and scope. A project
without a client is an internal project.
"""

from __future__ import annotations

import re
import sqlite3
from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional, Tuple

from spark.registry.store import (
    NotFoundError,
    Registry,
    RegistryError,
    inserted_id,
    now_iso,
)

KINDS = ("client", "project", "application")
# The column that scopes a name: clients are global, projects belong to a
# client (or none), applications to a project.
_PARENT = {"client": None, "project": "client_id", "application": "project_id"}
_SUFFIXES = {"inc", "llc", "ltd", "corp", "corporation", "co", "company", "the"}
_SIMILAR = 0.85


def _clean_name(kind: str, name: Optional[str]) -> str:
    value = " ".join((name or "").split())
    if not value or len(value) > 120:
        raise RegistryError(f"{kind} name must be 1-120 characters")
    return value


def _get(registry: Registry, kind: str, item_id: int) -> sqlite3.Row:
    if kind not in KINDS:
        raise ValueError(kind)
    row = registry.conn.execute(
        f"SELECT * FROM {kind} WHERE id = ?", (item_id,)
    ).fetchone()
    if not row:
        raise NotFoundError(f"no {kind} with id {item_id}")
    return row


def _clash(
    registry: Registry,
    kind: str,
    name: str,
    parent: Optional[int],
    exclude: Optional[int] = None,
) -> Optional[sqlite3.Row]:
    sql = f"SELECT id, retired_at FROM {kind} WHERE name = ? COLLATE NOCASE"
    params: List[Any] = [name]
    if _PARENT[kind]:
        sql += f" AND {_PARENT[kind]} IS ?"
        params.append(parent)
    if exclude is not None:
        sql += " AND id != ?"
        params.append(exclude)
    return registry.conn.execute(sql, params).fetchone()


def _refuse_clash(registry, kind, name, parent, exclude=None) -> None:
    found = _clash(registry, kind, name, parent, exclude)
    if found:
        state = "a retired" if found["retired_at"] else "an existing"
        raise RegistryError(f"{name!r} is already {state} {kind} here")


# -- create ------------------------------------------------------------------
def create_client(registry: Registry, name: str) -> Dict[str, Any]:
    name = _clean_name("client", name)
    _refuse_clash(registry, "client", name, None)
    with registry.conn:
        new_id = inserted_id(
            registry.conn.execute(
                "INSERT INTO client (name, created_at) VALUES (?, ?)", (name, now_iso())
            )
        )
    return {"id": new_id, "name": name}


def create_project(
    registry: Registry, client_id: Optional[int], name: str
) -> Dict[str, Any]:
    name = _clean_name("project", name)
    if client_id is not None:
        _get(registry, "client", client_id)
    _refuse_clash(registry, "project", name, client_id)
    with registry.conn:
        new_id = inserted_id(
            registry.conn.execute(
                "INSERT INTO project (client_id, name, created_at) VALUES (?, ?, ?)",
                (client_id, name, now_iso()),
            )
        )
    return {"id": new_id, "client_id": client_id, "name": name}


def create_application(
    registry: Registry, project_id: int, name: str
) -> Dict[str, Any]:
    name = _clean_name("application", name)
    project = _get(registry, "project", project_id)
    _refuse_clash(registry, "application", name, project_id)
    with registry.conn:
        new_id = inserted_id(
            registry.conn.execute(
                "INSERT INTO application (client_id, project_id, name, created_at)"
                " VALUES (?, ?, ?, ?)",
                (project["client_id"], project_id, name, now_iso()),
            )
        )
    return {"id": new_id, "project_id": project_id, "name": name}


# -- read --------------------------------------------------------------------
def tree(registry: Registry, include_retired: bool = False) -> List[Dict[str, Any]]:
    """Clients with their projects and applications, for pickers and the list
    editor. Internal projects appear under a client with ``id`` None."""
    conn = registry.conn
    active = "" if include_retired else " AND retired_at IS NULL"
    repo_counts = _counts(conn, "repository")
    source_counts = {
        row[0]: row[1]
        for row in conn.execute(
            "SELECT client_id, COUNT(*) FROM source"
            " WHERE client_id IS NOT NULL GROUP BY client_id"
        )
    }

    def entry(row, kind) -> Dict[str, Any]:
        return {
            "id": row["id"],
            "name": row["name"],
            "retired": row["retired_at"] is not None,
            "repository_count": repo_counts[kind].get(row["id"], 0),
        }

    def projects_for(client_id: Optional[int]) -> List[Dict[str, Any]]:
        out = []
        for row in conn.execute(
            f"SELECT * FROM project WHERE client_id IS ?{active}"
            " ORDER BY name COLLATE NOCASE",
            (client_id,),
        ):
            project = entry(row, "project")
            project["applications"] = [
                entry(app, "application")
                for app in conn.execute(
                    f"SELECT * FROM application WHERE project_id = ?{active}"
                    " ORDER BY name COLLATE NOCASE",
                    (row["id"],),
                )
            ]
            out.append(project)
        return out

    clients = []
    for row in conn.execute(
        f"SELECT * FROM client WHERE 1 = 1{active} ORDER BY name COLLATE NOCASE"
    ):
        client = entry(row, "client")
        client["source_count"] = source_counts.get(row["id"], 0)
        client["projects"] = projects_for(row["id"])
        clients.append(client)
    internal = projects_for(None)
    if internal:
        clients.insert(
            0,
            {
                "id": None,
                "name": "Internal",
                "retired": False,
                "repository_count": 0,
                "source_count": 0,
                "projects": internal,
            },
        )
    return clients


def _counts(conn: sqlite3.Connection, table: str) -> Dict[str, Dict[int, int]]:
    return {
        kind: {
            row[0]: row[1]
            for row in conn.execute(
                f"SELECT {kind}_id, COUNT(*) FROM {table}"
                f" WHERE {kind}_id IS NOT NULL GROUP BY {kind}_id"
            )
        }
        for kind in KINDS
    }


# -- rename, retire, restore -------------------------------------------------
def update(
    registry: Registry,
    kind: str,
    item_id: int,
    *,
    name: Optional[str] = None,
    retired: Optional[bool] = None,
) -> Dict[str, Any]:
    row = _get(registry, kind, item_id)
    column = _PARENT[kind]
    parent = row[column] if column else None
    with registry.conn:
        if name is not None:
            name = _clean_name(kind, name)
            _refuse_clash(registry, kind, name, parent, exclude=item_id)
            registry.conn.execute(
                f"UPDATE {kind} SET name = ? WHERE id = ?", (name, item_id)
            )
        if retired is not None:
            registry.conn.execute(
                f"UPDATE {kind} SET retired_at = ? WHERE id = ?",
                (now_iso() if retired else None, item_id),
            )
    row = _get(registry, kind, item_id)
    return {"id": row["id"], "name": row["name"], "retired": bool(row["retired_at"])}


# -- merge -------------------------------------------------------------------
def merge(registry: Registry, kind: str, from_id: int, into_id: int) -> Dict[str, int]:
    """Move everything that uses ``from_id`` onto ``into_id`` (same kind and
    scope), merging same-named children, then retire ``from_id``. Returns how
    many repositories and sources moved. All or nothing."""
    if from_id == into_id:
        raise RegistryError(f"choose a different {kind} to merge into")
    source = _get(registry, kind, from_id)
    target = _get(registry, kind, into_id)
    if target["retired_at"]:
        raise RegistryError(f"cannot merge into a retired {kind}; restore it first")
    column = _PARENT[kind]
    if column and source[column] != target[column]:
        parent = "client" if kind == "project" else "project"
        raise RegistryError(f"only a {kind} under the same {parent} can be merged")
    conn = registry.conn
    moved = {
        "repositories": conn.execute(
            f"SELECT COUNT(*) FROM repository WHERE {kind}_id = ?", (from_id,)
        ).fetchone()[0],
        "sources": (
            conn.execute(
                "SELECT COUNT(*) FROM source WHERE client_id = ?", (from_id,)
            ).fetchone()[0]
            if kind == "client"
            else 0
        ),
    }
    with conn:
        _merge(conn, kind, from_id, into_id)
    return moved


def _merge(conn, kind: str, from_id: int, into_id: int) -> None:
    conn.execute(
        f"UPDATE repository SET {kind}_id = ? WHERE {kind}_id = ?", (into_id, from_id)
    )
    if kind == "client":
        conn.execute(
            "UPDATE source SET client_id = ? WHERE client_id = ?", (into_id, from_id)
        )
        conn.execute(
            "UPDATE observation SET client_id = ? WHERE client_id = ?",
            (into_id, from_id),
        )
        _move_children(conn, "project", "client_id", from_id, into_id)
        conn.execute(
            "UPDATE application SET client_id = ? WHERE client_id = ?",
            (into_id, from_id),
        )
    elif kind == "project":
        _move_children(conn, "application", "project_id", from_id, into_id)
    conn.execute(
        f"UPDATE {kind} SET retired_at = COALESCE(retired_at, ?) WHERE id = ?",
        (now_iso(), from_id),
    )


def _move_children(conn, kind, column, from_id, into_id) -> None:
    """Re-parent children. A child whose name already exists under the target
    is merged into that one instead (restoring it if it was retired, since it
    now carries what the child had); the merged child stays retired under its
    old parent, so names stay unique per scope."""
    for child in conn.execute(
        f"SELECT id, name, retired_at FROM {kind} WHERE {column} = ?", (from_id,)
    ).fetchall():
        twin = conn.execute(
            f"SELECT id FROM {kind} WHERE {column} = ? AND name = ? COLLATE NOCASE",
            (into_id, child["name"]),
        ).fetchone()
        if twin:
            _merge(conn, kind, child["id"], twin["id"])
            if child["retired_at"] is None:
                conn.execute(
                    f"UPDATE {kind} SET retired_at = NULL WHERE id = ?", (twin["id"],)
                )
        else:
            conn.execute(
                f"UPDATE {kind} SET {column} = ? WHERE id = ?", (into_id, child["id"])
            )


# -- likely duplicates -------------------------------------------------------
def _normalize(name: str) -> str:
    words = re.sub(r"[^a-z0-9]+", " ", name.lower().replace("&", " and ")).split()
    while len(words) > 1 and words[-1] in _SUFFIXES:
        words.pop()
    if len(words) > 1 and words[0] == "the":
        words.pop(0)
    return " ".join(words)


def _similar(a: str, b: str) -> bool:
    na, nb = _normalize(a), _normalize(b)
    if na == nb:
        return True
    return min(len(na), len(nb)) >= 5 and SequenceMatcher(None, na, nb).ratio() >= (
        _SIMILAR
    )


def duplicates(registry: Registry) -> List[Dict[str, Any]]:
    """Pairs of active entries in the same scope whose names look alike, for
    the administrator to review. Nothing is merged automatically."""
    out: List[Dict[str, Any]] = []
    for kind in KINDS:
        column = _PARENT[kind]
        rows = registry.conn.execute(
            f"SELECT id, name{', ' + column if column else ''} FROM {kind}"
            " WHERE retired_at IS NULL ORDER BY id"
        ).fetchall()
        groups: Dict[Any, List[Tuple[int, str]]] = {}
        for row in rows:
            groups.setdefault(row[column] if column else None, []).append(
                (row["id"], row["name"])
            )
        for members in groups.values():
            for i, (a_id, a_name) in enumerate(members):
                for b_id, b_name in members[i + 1 :]:
                    if _similar(a_name, b_name):
                        out.append(
                            {
                                "kind": kind,
                                "a": {"id": a_id, "name": a_name},
                                "b": {"id": b_id, "name": b_name},
                            }
                        )
    return out
