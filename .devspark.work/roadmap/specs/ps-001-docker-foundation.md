---
id: ps-001
title: Docker foundation
status: proposed
order: 10
depends_on: []
blockers: []
delivery: []
---

# ps-001: Docker foundation

## Outcome

The existing dashboard, built from existing data, runs from `docker compose up` at port 8086 locally and,
as a Portainer stack, on the home server. Same UI, same data, nothing new.

## Current Reality

No container artifacts exist. The Vite build writes only to `docs/` or `.validation/site`
(`frontend/scripts/build-paths.mjs`) and copies `data/` and `output/` at build time; `base` is `/`, so a
root-served site works. The pipeline is the `spark` CLI (Python 3.11+, `requirements.txt`, which includes
Playwright that the image does not need).

## Scope and Independence

In scope: a `web` image (multi-stage build of the existing frontend, small static server, non-root); a
`worker` image (Python + `spark` CLI, no browsers, non-root); a Compose file with persistent mounts for
`data/`, `output/`, cache (`SPARK_CACHE_DIR`), and a future config directory; `GITHUB_TOKEN` via env or
Docker secret; port 8086, bound to the LAN interface; `.dockerignore` excluding `.env`, `.cache`,
`node_modules`, `.venv`; one-shot worker run on demand; short Portainer deployment doc; smoke check.

Out of scope: scheduling, registry, API, UI changes, private data, new data.
Shippable alone: Pages workflow and CLI are untouched.

## Future Health

Serve `/data` from a volume rather than a build-time copy so later items update data without rebuilding.
Reserve a separate `config` volume now so configuration and collected data never share a path.

## Dependencies and Decisions

No prerequisites. Open: bind mounts vs named volumes under Portainer; build on server vs registry (see ps-009).

## Completion Expectations

`docker compose up` serves a working dashboard at `http://localhost:8086`; a one-shot worker run refreshes
data in the volume and a reload shows it; images contain no token or `.env`; containers run non-root;
existing pytest, vitest, and Pages workflow still pass.
