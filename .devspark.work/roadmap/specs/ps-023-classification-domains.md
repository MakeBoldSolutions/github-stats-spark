---
id: ps-023
title: Classification domains and managed lists
status: proposed
order: 56
depends_on: [ps-003, ps-004]
blockers: []
delivery: []
---

# ps-023: Classification domains and managed lists

## Outcome

Every repository property the administrator assigns is chosen from a list set up beforehand, never typed
as free text. Clients, projects, and applications are managed lists with cascading selection, and the
administrator can define their own classification domains (a named list of allowed values) such as Tier,
Type, Lifecycle, and Stack, then classify repositories from dropdowns, one at a time or in bulk. The same
values become filters and groupings across the dashboard and exports.

## Current Reality

Assigning a repository (`RepositoriesPanel.jsx`) offers three free-text inputs: client, project, and
application. `Registry.associate_repository` creates any name it has not seen ("names are created on first
use"), so a typo silently creates a second client; only case differences are absorbed (`COLLATE NOCASE`).
`POST /api/clients`, `/api/clients/{id}/projects`, and the application endpoint exist (ps-004) but no screen
lists, renames, or merges them. No other classification exists; ps-020 plans a tier (core, supporting,
archive) with overrides in `config/portfolio.yml`.

## Scope and Independence

In scope:

- **Managed hierarchy:** admin screens to create, rename, retire, and merge clients, projects, and
  applications (a merge moves every association, then retires the merged entry). Assignment uses cascading
  dropdowns (client narrows projects, project narrows applications). `associate_repository` stops creating
  names; the API rejects an unknown name with a clear error. An "Add new..." choice opens the list editor
  instead of accepting typed text.
- **Domains:** a domain has a key, label, description, display order, and a single- or multi-choice flag;
  each value has a key, label, optional description, order, and an active/retired state. Storage is generic
  (domain, domain value, repository classification) so a new domain needs no schema change. Keys are stable;
  labels may be renamed without touching assignments.
- **Seeded defaults, all editable:** Tier (single: core, supporting, archive); Type (single: website, web
  app, API, library, tool, docs, template); Lifecycle (single: active, maintenance, deprecated, experiment);
  Stack (multi: .NET, Python, Node/React, static site).
- **Retire, don't delete:** a retired value leaves the dropdowns but existing assignments keep it and stay
  readable; hard delete is allowed only for a value nothing uses.
- **Classification UI:** per-repository dropdowns in the Repositories panel, bulk assignment for a selected
  set, and an "unclassified" filter so gaps are visible.
- **Export:** classifications are written to `portfolio.json` and the per-source dashboard data so views can
  filter and group by them; unassigned is shown as unassigned, never as a default value.

Out of scope: automated tier rules (ps-020 supplies them on top of the Tier domain), per-client access
control, domains on subjects other than repositories (applications and websites can adopt the same storage
later). Standalone: useful on its own as clean portfolio data; ps-022 consumes it.

## Future Health

ps-020 becomes "automated rules that fill the Tier domain when the administrator has not set it, with
reasons"; ps-011 and later items can attach domains to websites and applications without new tables;
ps-018 reports group by client and domain values that are guaranteed consistent.

## Dependencies and Decisions

Adopted defaults (developer, 2026-11-21): Tier, Type, Lifecycle, and Stack as seeded above; Stack is the
only multi-choice domain; values are retired rather than deleted. Existing free-text clients, projects,
and applications are migrated as-is into the managed lists, with an admin prompt to merge near-duplicates.
Open: none.

## Completion Expectations

No admin screen accepts free text for a client, project, application, or domain value assignment; an
unknown name sent to the API is rejected; merging two clients moves every repository and source
association; a retired value is absent from dropdowns but still shown on repositories that carry it; a
multi-choice domain stores several values and a single-choice domain rejects a second; bulk assignment
changes exactly the selected repositories; the export carries classifications and an explicit unassigned;
pytest covers migration of existing names, merge, retire, and rejection; vitest covers cascading dropdowns,
bulk assignment, and accessibility of the new controls.
