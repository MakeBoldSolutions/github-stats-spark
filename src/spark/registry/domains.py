"""Classification domains: named lists of allowed values for repositories.

A domain is single-choice (a repository holds at most one of its values) or
multi-choice. Values are retired rather than deleted once anything uses them:
a retired value leaves the pickers but stays on the repositories that carry
it. Keys are stable identifiers; labels are free to change.
"""

from __future__ import annotations

import re
import sqlite3
from typing import Any, Dict, Iterable, List, Optional

from spark.registry.store import (
    NotFoundError,
    Registry,
    RegistryError,
    inserted_id,
    now_iso,
)

_KEY = re.compile(r"^[a-z0-9][a-z0-9-]{0,39}$")
MODES = ("set", "add", "remove")


def _key(value: Optional[str]) -> str:
    key = (value or "").strip().lower()
    if not _KEY.match(key):
        raise RegistryError(
            "key must be 1-40 lower-case letters, digits or hyphens (got " f"{value!r})"
        )
    return key


def _label(value: Optional[str], what: str = "label") -> str:
    label = " ".join((value or "").split())
    if not label or len(label) > 80:
        raise RegistryError(f"{what} must be 1-80 characters")
    return label


def _description(value: Optional[str]) -> Optional[str]:
    text = (value or "").strip()
    if len(text) > 300:
        raise RegistryError("description must be at most 300 characters")
    return text or None


def _domain(registry: Registry, domain_id: int) -> sqlite3.Row:
    row = registry.conn.execute(
        "SELECT * FROM domain WHERE id = ?", (domain_id,)
    ).fetchone()
    if not row:
        raise NotFoundError(f"no domain with id {domain_id}")
    return row


def _value(registry: Registry, value_id: int) -> sqlite3.Row:
    row = registry.conn.execute(
        "SELECT * FROM domain_value WHERE id = ?", (value_id,)
    ).fetchone()
    if not row:
        raise NotFoundError(f"no domain value with id {value_id}")
    return row


def _next_order(registry: Registry, table: str, where: str = "", params=()) -> int:
    row = registry.conn.execute(
        f"SELECT COALESCE(MAX(sort_order), 0) FROM {table} {where}", params
    ).fetchone()
    return row[0] + 10


# -- read --------------------------------------------------------------------
def list_domains(
    registry: Registry, include_retired: bool = False
) -> List[Dict[str, Any]]:
    """Domains in display order, each with its values and how many
    repositories use each value."""
    conn = registry.conn
    usage = {
        row[0]: row[1]
        for row in conn.execute(
            "SELECT value_id, COUNT(*) FROM repository_classification GROUP BY value_id"
        )
    }
    active = "" if include_retired else " WHERE retired_at IS NULL"
    out = []
    for row in conn.execute(
        f"SELECT * FROM domain{active} ORDER BY sort_order, label COLLATE NOCASE"
    ):
        values = [
            {
                "id": v["id"],
                "key": v["key"],
                "label": v["label"],
                "description": v["description"],
                "retired": v["retired_at"] is not None,
                "repository_count": usage.get(v["id"], 0),
            }
            for v in conn.execute(
                "SELECT * FROM domain_value WHERE domain_id = ?"
                + ("" if include_retired else " AND retired_at IS NULL")
                + " ORDER BY sort_order, label COLLATE NOCASE",
                (row["id"],),
            )
        ]
        out.append(
            {
                "id": row["id"],
                "key": row["key"],
                "label": row["label"],
                "description": row["description"],
                "multi": bool(row["multi"]),
                "retired": row["retired_at"] is not None,
                "values": values,
            }
        )
    return out


class Classifications:
    """Every repository's values, by domain key, for the active domains."""

    def __init__(self, domain_keys: List[str], held: Dict[int, Dict[str, List[str]]]):
        self.domain_keys = domain_keys
        self._held = held

    def get(self, repository_id: int) -> Dict[str, List[str]]:
        """A domain the repository has no value in is present with an empty
        list, so "unassigned" is explicit rather than missing."""
        held = self._held.get(repository_id, {})
        return {key: list(held.get(key, [])) for key in self.domain_keys}


def classifications(registry: Registry) -> Classifications:
    conn = registry.conn
    domain_keys = [
        row[0]
        for row in conn.execute(
            "SELECT key FROM domain WHERE retired_at IS NULL ORDER BY sort_order"
        )
    ]
    held: Dict[int, Dict[str, List[str]]] = {}
    for repo_id, domain_key, value_key in conn.execute(
        "SELECT rc.repository_id, d.key, v.key FROM repository_classification rc"
        " JOIN domain_value v ON v.id = rc.value_id"
        " JOIN domain d ON d.id = v.domain_id"
        " WHERE d.retired_at IS NULL"
        " ORDER BY rc.repository_id, d.sort_order, v.sort_order"
    ):
        held.setdefault(repo_id, {}).setdefault(domain_key, []).append(value_key)
    return Classifications(domain_keys, held)


# -- domains -----------------------------------------------------------------
def create_domain(
    registry: Registry,
    *,
    key: str,
    label: str,
    description: Optional[str] = None,
    multi: bool = False,
) -> Dict[str, Any]:
    key, label = _key(key), _label(label)
    if registry.conn.execute("SELECT 1 FROM domain WHERE key = ?", (key,)).fetchone():
        raise RegistryError(f"a domain with key {key!r} already exists")
    with registry.conn:
        new_id = inserted_id(
            registry.conn.execute(
                "INSERT INTO domain (key, label, description, multi, sort_order,"
                " created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (
                    key,
                    label,
                    _description(description),
                    int(multi),
                    _next_order(registry, "domain"),
                    now_iso(),
                ),
            )
        )
    return _present_domain(registry, new_id)


def update_domain(
    registry: Registry,
    domain_id: int,
    *,
    label: Optional[str] = None,
    description: Optional[str] = None,
    multi: Optional[bool] = None,
    retired: Optional[bool] = None,
    sort_order: Optional[int] = None,
) -> Dict[str, Any]:
    _domain(registry, domain_id)
    if multi is False:
        crowded = registry.conn.execute(
            "SELECT COUNT(*) FROM (SELECT rc.repository_id FROM"
            " repository_classification rc JOIN domain_value v ON v.id = rc.value_id"
            " WHERE v.domain_id = ? GROUP BY rc.repository_id HAVING COUNT(*) > 1)",
            (domain_id,),
        ).fetchone()[0]
        if crowded:
            raise RegistryError(
                f"{crowded} repositories hold several values in this domain;"
                " reduce them to one before making it single-choice"
            )
    changes: Dict[str, Any] = {}
    if label is not None:
        changes["label"] = _label(label)
    if description is not None:
        changes["description"] = _description(description)
    if multi is not None:
        changes["multi"] = int(multi)
    if retired is not None:
        changes["retired_at"] = now_iso() if retired else None
    if sort_order is not None:
        changes["sort_order"] = int(sort_order)
    if changes:
        with registry.conn:
            registry.conn.execute(
                "UPDATE domain SET "
                + ", ".join(f"{column} = ?" for column in changes)
                + " WHERE id = ?",
                (*changes.values(), domain_id),
            )
    return _present_domain(registry, domain_id)


def delete_domain(registry: Registry, domain_id: int) -> None:
    """Only a domain no repository uses can be deleted; retire it otherwise."""
    _domain(registry, domain_id)
    if _domain_usage(registry, domain_id):
        raise RegistryError("this domain is in use; retire it instead of deleting it")
    with registry.conn:
        registry.conn.execute("DELETE FROM domain WHERE id = ?", (domain_id,))


def _domain_usage(registry: Registry, domain_id: int) -> int:
    return registry.conn.execute(
        "SELECT COUNT(*) FROM repository_classification rc"
        " JOIN domain_value v ON v.id = rc.value_id WHERE v.domain_id = ?",
        (domain_id,),
    ).fetchone()[0]


def _present_domain(registry: Registry, domain_id: int) -> Dict[str, Any]:
    for domain in list_domains(registry, include_retired=True):
        if domain["id"] == domain_id:
            return domain
    raise NotFoundError(f"no domain with id {domain_id}")  # pragma: no cover


# -- values ------------------------------------------------------------------
def add_value(
    registry: Registry,
    domain_id: int,
    *,
    key: str,
    label: str,
    description: Optional[str] = None,
) -> Dict[str, Any]:
    _domain(registry, domain_id)
    key, label = _key(key), _label(label)
    if registry.conn.execute(
        "SELECT 1 FROM domain_value WHERE domain_id = ? AND key = ?", (domain_id, key)
    ).fetchone():
        raise RegistryError(f"this domain already has a value with key {key!r}")
    with registry.conn:
        new_id = inserted_id(
            registry.conn.execute(
                "INSERT INTO domain_value (domain_id, key, label, description,"
                " sort_order, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (
                    domain_id,
                    key,
                    label,
                    _description(description),
                    _next_order(
                        registry, "domain_value", "WHERE domain_id = ?", (domain_id,)
                    ),
                    now_iso(),
                ),
            )
        )
    return _present_value(registry, new_id)


def update_value(
    registry: Registry,
    value_id: int,
    *,
    label: Optional[str] = None,
    description: Optional[str] = None,
    retired: Optional[bool] = None,
    sort_order: Optional[int] = None,
) -> Dict[str, Any]:
    _value(registry, value_id)
    changes: Dict[str, Any] = {}
    if label is not None:
        changes["label"] = _label(label)
    if description is not None:
        changes["description"] = _description(description)
    if retired is not None:
        changes["retired_at"] = now_iso() if retired else None
    if sort_order is not None:
        changes["sort_order"] = int(sort_order)
    if changes:
        with registry.conn:
            registry.conn.execute(
                "UPDATE domain_value SET "
                + ", ".join(f"{column} = ?" for column in changes)
                + " WHERE id = ?",
                (*changes.values(), value_id),
            )
    return _present_value(registry, value_id)


def delete_value(registry: Registry, value_id: int) -> None:
    """Only a value no repository uses can be deleted; retire it otherwise."""
    _value(registry, value_id)
    if registry.conn.execute(
        "SELECT 1 FROM repository_classification WHERE value_id = ? LIMIT 1",
        (value_id,),
    ).fetchone():
        raise RegistryError("this value is in use; retire it instead of deleting it")
    with registry.conn:
        registry.conn.execute("DELETE FROM domain_value WHERE id = ?", (value_id,))


def _present_value(registry: Registry, value_id: int) -> Dict[str, Any]:
    row = _value(registry, value_id)
    used = registry.conn.execute(
        "SELECT COUNT(*) FROM repository_classification WHERE value_id = ?",
        (value_id,),
    ).fetchone()[0]
    return {
        "id": row["id"],
        "domain_id": row["domain_id"],
        "key": row["key"],
        "label": row["label"],
        "description": row["description"],
        "retired": row["retired_at"] is not None,
        "repository_count": used,
    }


# -- classifying repositories ------------------------------------------------
def classify(
    registry: Registry,
    full_names: Iterable[str],
    domain_key: str,
    value_keys: Iterable[str],
    mode: str = "set",
) -> int:
    """Classify repositories in one domain, all or nothing.

    ``set`` replaces the repository's values in the domain (an empty list
    clears it); ``add`` and ``remove`` apply to multi-choice domains only. A
    retired value can be kept where it already is but not newly assigned.
    Returns the number of repositories changed.
    """
    if mode not in MODES:
        raise RegistryError(f"mode must be one of {', '.join(MODES)}")
    conn = registry.conn
    domain = conn.execute(
        "SELECT * FROM domain WHERE key = ?", ((domain_key or "").lower(),)
    ).fetchone()
    if not domain:
        raise NotFoundError(f"unknown domain {domain_key!r}")
    if domain["retired_at"]:
        raise RegistryError(f"domain {domain['label']!r} is retired")
    keys = list(dict.fromkeys(k.lower() for k in value_keys))
    if not domain["multi"]:
        if mode != "set":
            raise RegistryError(f"{domain['label']} is single-choice; use set")
        if len(keys) > 1:
            raise RegistryError(f"{domain['label']} allows only one value")
    values = {
        row["key"]: row
        for row in conn.execute(
            "SELECT * FROM domain_value WHERE domain_id = ?", (domain["id"],)
        )
    }
    unknown = [k for k in keys if k not in values]
    if unknown:
        raise RegistryError(
            f"unknown {domain['label']} value(s): {', '.join(unknown)};"
            " add them under Admin > Domains first"
        )
    chosen = {values[k]["id"] for k in keys}
    retired = {values[k]["id"] for k in keys if values[k]["retired_at"]}
    domain_value_ids = {row["id"] for row in values.values()}

    repo_ids = []
    for name in dict.fromkeys(full_names):
        row = conn.execute(
            "SELECT id FROM repository WHERE full_name_lower = ?", (name.lower(),)
        ).fetchone()
        if not row:
            raise NotFoundError(f"unknown repository {name!r}")
        repo_ids.append(row["id"])

    changed = 0
    stamp = now_iso()
    with conn:
        for repo_id in repo_ids:
            held = {
                row[0]
                for row in conn.execute(
                    "SELECT value_id FROM repository_classification"
                    " WHERE repository_id = ?",
                    (repo_id,),
                )
                if row[0] in domain_value_ids
            }
            if mode == "set":
                target = chosen
            elif mode == "add":
                target = held | chosen
            else:
                target = held - chosen
            newly_retired = (target - held) & retired
            if newly_retired:
                raise RegistryError(
                    "a retired value cannot be newly assigned; restore it under"
                    " Admin > Domains first"
                )
            if target == held:
                continue
            for value_id in held - target:
                conn.execute(
                    "DELETE FROM repository_classification"
                    " WHERE repository_id = ? AND value_id = ?",
                    (repo_id, value_id),
                )
            for value_id in target - held:
                conn.execute(
                    "INSERT INTO repository_classification"
                    " (repository_id, value_id, assigned_at) VALUES (?, ?, ?)",
                    (repo_id, value_id, stamp),
                )
            changed += 1
    return changed
